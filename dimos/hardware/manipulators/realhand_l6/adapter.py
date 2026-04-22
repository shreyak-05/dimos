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

"""RealHand L6 (LinkerHand) adapter — uses linkerbot-py SDK (pip install linkerbot-py).

Wraps the ``linkerbot.O6`` class which manages CAN bus communication,
background polling, and frame encoding/decoding internally.

CAN byte order: [thumb_flex, thumb_abd, index, middle, ring, pinky]

The SDK uses a 0–100 scale (0 = fully flexed/closed, 100 = fully extended/open).
This adapter converts to/from radians using the O6 URDF joint limits.

Unit conversion (sdk ↔ radians):
    sdk = (1.0 - rad / MAX_RAD[i]) * 100
    rad = (1.0 - sdk / 100) * MAX_RAD[i]
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from dimos.hardware.manipulators.registry import AdapterRegistry

from dimos.hardware.manipulators.spec import (
    ControlMode,
    JointLimits,
    ManipulatorInfo,
)

_DOF = 6

# Max joint angles (radians) from linkerhand_o6_left.urdf actuated joints.
# Order: thumb_flex (cmc_yaw), thumb_abd (cmc_pitch), index, middle, ring, pinky
_MAX_RAD = [1.3, 0.58, 1.60, 1.60, 1.60, 1.60]


def _rad_to_sdk(rad: float, dof_idx: int) -> float:
    """Convert radians to SDK 0–100 scale (0=closed/flexed, 100=open/extended)."""
    clamped = max(0.0, min(_MAX_RAD[dof_idx], rad))
    return (1.0 - clamped / _MAX_RAD[dof_idx]) * 100.0


def _sdk_to_rad(sdk_val: float, dof_idx: int) -> float:
    """Convert SDK 0–100 scale to radians."""
    clamped = max(0.0, min(100.0, sdk_val))
    return (1.0 - clamped / 100.0) * _MAX_RAD[dof_idx]


class RealHandL6Adapter:
    """RealHand L6 (LinkerHand 6-DOF) adapter using linkerbot-py SDK.

    Uses the official ``linkerbot`` pip package (``O6`` class) for CAN bus
    communication. Same underlying CAN protocol as MuJoCoDex's
    ``LinkerHandL6Controller``, but with a cleaner pip-installable SDK.

    Args:
        address: CAN interface name (e.g. "can0").
        side: Hand side ("left" or "right"). Falls back to env var
              ``REALHAND_SIDE``, then "left".
    """

    def __init__(
        self,
        address: str,
        side: Literal["left", "right"] | None = None,
        dof: int = _DOF,
        **_: object,
    ) -> None:
        if not address:
            raise ValueError("address (CAN interface) is required for RealHandL6Adapter")
        self._interface = address
        self._side: Literal["left", "right"] = side or os.environ.get("REALHAND_SIDE", "left")  # type: ignore[assignment]
        self._dof = dof

        self._hand = None  # linkerbot.O6 instance
        self._connected: bool = False
        self._control_mode: ControlMode = ControlMode.SERVO_POSITION

    # =========================================================================
    # Connection
    # =========================================================================

    def connect(self) -> bool:
        """Create O6 SDK instance (opens CAN bus, starts background polling)."""
        try:
            from linkerbot import O6

            self._hand = O6(
                side=self._side,
                interface_name=self._interface,
            )
            self._connected = True
            return True
        except Exception as e:
            print(f"ERROR: Failed to connect to RealHandL6 on {self._interface}: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the SDK instance and release CAN resources."""
        if self._hand is not None:
            try:
                self._hand.close()
            except Exception:
                pass
            self._hand = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._hand is not None and not self._hand.is_closed()

    # =========================================================================
    # Info
    # =========================================================================

    def get_info(self) -> ManipulatorInfo:
        return ManipulatorInfo(
            vendor="LinkerHand",
            model="RealHandL6",
            dof=self._dof,
        )

    def get_dof(self) -> int:
        return self._dof

    def get_limits(self) -> JointLimits:
        return JointLimits(
            position_lower=[0.0] * _DOF,
            position_upper=list(_MAX_RAD),
            velocity_max=[1.0] * _DOF,
        )

    # =========================================================================
    # Control Mode
    # =========================================================================

    def set_control_mode(self, mode: ControlMode) -> bool:
        self._control_mode = mode
        return mode == ControlMode.SERVO_POSITION

    def get_control_mode(self) -> ControlMode:
        return self._control_mode

    # =========================================================================
    # State Reading
    # =========================================================================

    def read_joint_positions(self) -> list[float]:
        """Return current joint positions in radians (converted from SDK 0-100)."""
        if not self.is_connected():
            return [0.0] * self._dof
        try:
            data = self._hand.angle.get_blocking(timeout_ms=100)
            if data is not None:
                sdk_vals = data.angles.to_list()
                return [_sdk_to_rad(sdk_vals[i], i) for i in range(_DOF)]
        except Exception:
            pass
        # Fallback to cached snapshot
        try:
            snap = self._hand.get_snapshot()
            if snap.angle is not None:
                sdk_vals = snap.angle.angles.to_list()
                return [_sdk_to_rad(sdk_vals[i], i) for i in range(_DOF)]
        except Exception:
            pass
        return [0.0] * self._dof

    def read_joint_velocities(self) -> list[float]:
        return [0.0] * self._dof

    def read_joint_efforts(self) -> list[float]:
        return [0.0] * self._dof

    def read_state(self) -> dict[str, int]:
        return {"connected": int(self._connected)}

    def read_error(self) -> tuple[int, str]:
        return 0, ""

    # =========================================================================
    # Motion Control
    # =========================================================================

    def write_joint_positions(
        self,
        positions: list[float],
        velocity: float = 1.0,
    ) -> bool:
        """Send joint positions (radians) to the hand via the SDK."""
        if not self.is_connected():
            return False
        if len(positions) < _DOF:
            return False
        try:
            sdk_vals = [_rad_to_sdk(positions[i], i) for i in range(_DOF)]
            self._hand.angle.set_angles(sdk_vals)
            return True
        except Exception as e:
            print(f"RealHandL6: write_joint_positions failed: {e}")
            return False

    def write_joint_velocities(self, velocities: list[float]) -> bool:
        return False

    def write_stop(self) -> bool:
        """Stop motion by holding current position."""
        current = self.read_joint_positions()
        return self.write_joint_positions(current)

    # =========================================================================
    # Servo Control
    # =========================================================================

    def write_enable(self, enable: bool) -> bool:
        return True

    def read_enabled(self) -> bool:
        return self._connected

    def write_clear_errors(self) -> bool:
        return False

    # =========================================================================
    # Cartesian / Gripper / F-T (not supported)
    # =========================================================================

    def read_cartesian_position(self) -> dict[str, float] | None:
        return None

    def write_cartesian_position(self, pose: dict[str, float], velocity: float = 1.0) -> bool:
        return False

    def read_gripper_position(self) -> float | None:
        return None

    def write_gripper_position(self, position: float) -> bool:
        return False

    def read_force_torque(self) -> list[float] | None:
        return None


def register(registry: "AdapterRegistry") -> None:
    """Register this adapter with the registry."""
    registry.register("realhand_l6", RealHandL6Adapter)


__all__ = ["RealHandL6Adapter"]
