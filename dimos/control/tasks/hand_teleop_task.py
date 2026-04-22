# Copyright 2025-2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Button-driven hand posture controller for RealHand L6.

Maps Quest controller buttons to hand postures:
  - B / Y (secondary, rising edge): open hand, reset grasp cycle + abduction
  - Grip (rising edge): cycle grasp primitives, or toggle thumb abduction
    when grasp cycle is empty
  - Trigger (analog): proportional finger curl (when no grasp is latched)

Grasp primitives are configurable via HandTeleopTaskConfig.grasp_primitives.
Defaults match MuJoCoDex teleop postures (open, power, pinch, tripod).

CAN joint order: [thumb_flex, thumb_abd, index, middle, ring, pinky]
(from linkerbot-py SDK O6Angle dataclass)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from dimos.control.task import (
    BaseControlTask,
    ControlMode,
    CoordinatorState,
    JointCommandOutput,
    ResourceClaim,
)
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from dimos.teleop.quest.quest_types import Buttons

logger = setup_logger()

# Default grasp primitives (CAN order):
#   [thumb_cmc_pitch, thumb_cmc_yaw, index_mcp_pitch,
#    middle_mcp_pitch, ring_mcp_pitch, pinky_mcp_pitch]
# Values match MuJoCoDex teleop_config.py postures (swapped to CAN byte order).
_DEFAULT_GRASP_PRIMITIVES: dict[str, list[float]] = {
    "open": [0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
    "power": [0.70, 1.05, 1.20, 1.20, 1.10, 1.00],
    "pinch": [0.3139, 1.248, 0.8157, 0.8157, 0.8157, 0.8157],
    "tripod": [0.35, 1.0, 0.95, 0.95, 0.35, 0.35],
}

# Maximum per-joint curl driven by trigger (thumb stays open)
_DEFAULT_TRIGGER_MAX = [0.00, 0.00, 1.20, 1.20, 1.10, 1.00]

_DOF = 6


@dataclass
class HandTeleopTaskConfig:
    """Configuration for the hand teleop task.

    Attributes:
        joint_names: 6 hand joint names in CAN order.
        hand: "left" or "right" — which controller to listen to.
        priority: Arbitration priority (lower than arm task by default).
        grasp_primitives: Named grasp postures. Must include "open".
            Grip button cycles through all non-open primitives.
        trigger_max: Per-joint maximum for trigger proportional curl.
        thumb_abd_angle: Preset angle (rad) for thumb abduction toggle.
            Grip button toggles abduction when grasp cycle is empty.
            Default 0.30 rad (max hardware limit is 0.58 rad).
    """

    joint_names: list[str]
    hand: Literal["left", "right"]
    priority: int = 9
    grasp_primitives: dict[str, list[float]] = field(
        default_factory=lambda: dict(_DEFAULT_GRASP_PRIMITIVES)
    )
    trigger_max: list[float] = field(
        default_factory=lambda: list(_DEFAULT_TRIGGER_MAX)
    )
    thumb_abd_angle: float = 0.30


class HandTeleopTask(BaseControlTask):
    """Button-driven hand posture controller.

    Always active after start(). Responds to:
      - B/Y button rising edge  → open hand, reset grasp cycle
      - Grip button rising edge → cycle grasp primitives (power → pinch → tripod → ...)
      - Trigger analog          → proportional finger curl (when no grasp latched)

    Outputs SERVO_POSITION commands every tick.
    """

    def __init__(self, name: str, config: HandTeleopTaskConfig) -> None:
        if not config.joint_names:
            raise ValueError(f"HandTeleopTask '{name}' requires at least one joint")
        if config.hand not in ("left", "right"):
            raise ValueError(f"HandTeleopTask '{name}' requires hand='left' or 'right'")
        if len(config.joint_names) != _DOF:
            raise ValueError(
                f"HandTeleopTask '{name}' requires exactly {_DOF} joint names, "
                f"got {len(config.joint_names)}"
            )
        if "open" not in config.grasp_primitives:
            raise ValueError(f"HandTeleopTask '{name}' grasp_primitives must include 'open'")

        self._name = name
        self._config = config

        # Build grasp cycle (all primitives except "open")
        self._grasp_cycle = [k for k in config.grasp_primitives if k != "open"]
        self._grasp_idx: int = -1  # -1 = no grasp latched

        self._lock = threading.Lock()
        self._active: bool = False  # inactive until first button interaction

        # Current position targets (start open)
        self._targets: list[float] = list(config.grasp_primitives["open"])

        # Thumb abduction step cycle: 0 → 0.15 → 0.30 → 0.50 → 0
        abd = config.thumb_abd_angle
        self._abd_steps: list[float] = [0.0, abd * 0.3, abd * 0.6, abd]
        self._abd_idx: int = 0

        # State for edge detection
        self._prev_secondary: bool = False
        self._prev_grip: bool = False

        logger.info(
            f"HandTeleopTask {name} initialized "
            f"(hand={config.hand}, joints={config.joint_names}, "
            f"grasps={list(config.grasp_primitives.keys())})"
        )

    @property
    def name(self) -> str:
        """Unique task identifier."""
        return self._name

    def claim(self) -> ResourceClaim:
        """Declare all hand joints at configured priority."""
        return ResourceClaim(
            joints=frozenset(self._config.joint_names),
            priority=self._config.priority,
            mode=ControlMode.SERVO_POSITION,
        )

    def is_active(self) -> bool:
        """Active whenever started."""
        with self._lock:
            return self._active

    def compute(self, state: CoordinatorState) -> JointCommandOutput | None:
        """Return current hand posture targets."""
        with self._lock:
            if not self._active:
                return None
            targets = list(self._targets)

        return JointCommandOutput(
            joint_names=list(self._config.joint_names),
            positions=targets,
            mode=ControlMode.SERVO_POSITION,
        )

    def on_preempted(self, by_task: str, joints: frozenset[str]) -> None:
        """Log preemption."""
        logger.warning(f"HandTeleopTask {self._name} preempted by {by_task} on {joints}")

    def on_buttons(self, msg: Buttons) -> bool:
        """Map button events to hand postures.

        - Secondary (B/Y) rising edge: open hand, reset abduction
        - Grip rising edge: cycle grasp primitives, or toggle thumb abduction
          when grasp cycle is empty
        - Trigger analog: proportional finger curl (when no grasp latched)
        """
        is_left = self._config.hand == "left"

        secondary = msg.left_secondary if is_left else msg.right_secondary
        grip = msg.left_grip if is_left else msg.right_grip
        trigger = msg.left_trigger_analog if is_left else msg.right_trigger_analog

        primitives = self._config.grasp_primitives

        with self._lock:
            if not self._active:
                self._active = True
                logger.info(f"HandTeleopTask {self._name}: activated on first button event")

            # Secondary (B/Y) rising edge → open hand, reset everything
            if secondary and not self._prev_secondary:
                logger.info(f"HandTeleopTask {self._name}: open (secondary button)")
                self._targets = list(primitives["open"])
                self._grasp_idx = -1
                self._abd_idx = 0

            # Grip rising edge → cycle grasps or toggle thumb abduction
            elif grip and not self._prev_grip:
                if self._grasp_cycle:
                    self._grasp_idx = (self._grasp_idx + 1) % len(self._grasp_cycle)
                    grasp_name = self._grasp_cycle[self._grasp_idx]
                    logger.info(f"HandTeleopTask {self._name}: {grasp_name} grasp")
                    self._targets = list(primitives[grasp_name])
                else:
                    self._abd_idx = (self._abd_idx + 1) % len(self._abd_steps)
                    self._targets[1] = self._abd_steps[self._abd_idx]
                    logger.info(
                        f"HandTeleopTask {self._name}: "
                        f"thumb abduction {self._targets[1]:.2f} rad"
                    )

            # Trigger analog → proportional finger curl (no grasp latched)
            if self._grasp_idx == -1:
                trigger_max = self._config.trigger_max
                for i in range(_DOF):
                    self._targets[i] = trigger * trigger_max[i]
                # Preserve abduction step (trigger_max[1] should be 0)
                self._targets[1] = self._abd_steps[self._abd_idx]

            self._prev_secondary = secondary
            self._prev_grip = grip

        return True

    def start(self) -> None:
        """Activate the task."""
        with self._lock:
            self._active = True
        logger.info(f"HandTeleopTask {self._name} started")

    def stop(self) -> None:
        """Deactivate the task."""
        with self._lock:
            self._active = False
        logger.info(f"HandTeleopTask {self._name} stopped")


__all__ = [
    "HandTeleopTask",
    "HandTeleopTaskConfig",
]
