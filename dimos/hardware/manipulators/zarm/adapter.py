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

"""ZArm adapter - implements ManipulatorAdapter protocol.

SDK Units: angles=degrees
DimOS Units: angles=radians
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dimos.hardware.manipulators.registry import AdapterRegistry

from dimos.hardware.manipulators.spec import (
    ControlMode,
    JointLimits,
    ManipulatorAdapter,
    ManipulatorInfo,
)

# Joint limits from zarm.urdf (radians)
_JOINT_LOWER = [-3.0543, -4.6251, -2.8274, -4.6251, -3.0543, -3.0543]
_JOINT_UPPER = [3.0543, 1.4835, 2.8274, 1.4835, 3.0543, 3.0543]

# ServoJ parameters
_SERVO_VEL = 0.0   # velocity (0 = use controller default)
_SERVO_ACC = 0.0   # acceleration (0 = use controller default)
_SERVO_T = 0.016   # time step (s) — smoother interpolation with realhand attached
_SERVO_LOOKAHEAD = 0.05
_SERVO_GAIN = 1000


class ZArmAdapter(ManipulatorAdapter):
    """ZArm (Fairino 6-DOF) adapter.

    Implements ManipulatorAdapter protocol via duck typing.
    No inheritance required - just matching method signatures.
    """

    def __init__(self, address: str, dof: int = 6, **_: object) -> None:
        if not address:
            raise ValueError("address (IP) is required for ZArmAdapter")
        self._ip = address
        self._dof = dof
        self._robot = None
        self._connected: bool = False
        self._enabled: bool = False
        self._control_mode: ControlMode = ControlMode.SERVO_POSITION

    # =========================================================================
    # Connection
    # =========================================================================

    def connect(self) -> bool:
        """Connect to ZArm via TCP/IP using Fairino SDK."""
        try:
            from fairino import Robot

            self._robot = Robot.RPC(self._ip)
            self._connected = True
            return True
        except Exception as e:
            print(f"ERROR: Failed to connect to ZArm at {self._ip}: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from ZArm."""
        if self._robot is not None:
            try:
                self._robot.CloseRPC()
            except Exception:
                pass
            self._robot = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to ZArm."""
        return self._connected and self._robot is not None

    # =========================================================================
    # Info
    # =========================================================================

    def get_info(self) -> ManipulatorInfo:
        """Get ZArm information."""
        return ManipulatorInfo(
            vendor="Fairino",
            model="ZArm6",
            dof=self._dof,
        )

    def get_dof(self) -> int:
        """Get degrees of freedom."""
        return self._dof

    def get_limits(self) -> JointLimits:
        """Get joint limits from zarm.urdf."""
        return JointLimits(
            position_lower=list(_JOINT_LOWER),
            position_upper=list(_JOINT_UPPER),
            velocity_max=[math.pi] * self._dof,  # ~180 deg/s
        )

    # =========================================================================
    # Control Mode
    # =========================================================================

    def set_control_mode(self, mode: ControlMode) -> bool:
        """Set control mode.

        ZArm ServoJ is used for high-frequency joint position control.
        Only SERVO_POSITION is fully supported.
        """
        self._control_mode = mode
        return mode == ControlMode.SERVO_POSITION

    def get_control_mode(self) -> ControlMode:
        """Get current control mode."""
        return self._control_mode

    # =========================================================================
    # State Reading
    # =========================================================================

    def read_joint_positions(self) -> list[float]:
        """Read joint positions (degrees -> radians)."""
        if not self.is_connected():
            raise RuntimeError("Not connected")

        ret, angles = self._robot.GetActualJointPosDegree()
        if ret != 0 or not angles:
            raise RuntimeError(f"Failed to read joint positions (ret={ret})")
        return [math.radians(a) for a in angles[: self._dof]]

    def read_joint_velocities(self) -> list[float]:
        """Read joint velocities.

        ZArm does not provide real-time velocity feedback.
        Returns zeros.
        """
        return [0.0] * self._dof

    def read_joint_efforts(self) -> list[float]:
        """Read joint torques.

        ZArm does not expose real-time torque feedback via RPC.
        Returns zeros.
        """
        return [0.0] * self._dof

    def read_state(self) -> dict[str, int]:
        """Read robot state."""
        return {"connected": int(self._connected), "enabled": int(self._enabled)}

    def read_error(self) -> tuple[int, str]:
        """Read error code and message."""
        return 0, ""

    # =========================================================================
    # Motion Control (Joint Space)
    # =========================================================================

    def write_joint_positions(
        self,
        positions: list[float],
        velocity: float = 1.0,
    ) -> bool:
        """Write joint positions for servo mode (radians -> degrees).

        Uses ServoJ for high-frequency joint position streaming.

        Args:
            positions: Target positions in radians
            velocity: Unused (ServoJ manages velocity internally)
        """
        if not self.is_connected():
            return False

        angles = [math.degrees(p) for p in positions]
        ret = self._robot.ServoJ(
            angles,
            _SERVO_VEL,
            _SERVO_ACC,
            _SERVO_T,
            _SERVO_LOOKAHEAD,
            _SERVO_GAIN,
        )
        return ret == 0

    def write_joint_velocities(self, velocities: list[float]) -> bool:
        """Write joint velocities.

        Not supported by ZArm via Fairino RPC SDK.
        """
        return False

    def write_stop(self) -> bool:
        """Stop all motion."""
        if not self.is_connected():
            return False
        try:
            self._robot.StopMotion()
            return True
        except Exception:
            return False

    # =========================================================================
    # Servo Control
    # =========================================================================

    def write_enable(self, enable: bool) -> bool:
        """Enable or disable servos."""
        if not self.is_connected():
            return False
        try:
            state = 1 if enable else 0
            ret = self._robot.RobotEnable(state)
            if ret == 0:
                self._enabled = enable
                return True
            return False
        except Exception:
            return False

    def read_enabled(self) -> bool:
        """Check if servos are enabled."""
        return self._enabled

    def write_clear_errors(self) -> bool:
        """Clear error state.

        ZArm does not expose an explicit clear-error RPC in the SDK.
        Re-enabling the robot typically clears errors.
        """
        return self.write_enable(True)

    # =========================================================================
    # Cartesian Control (not supported)
    # =========================================================================

    def read_cartesian_position(self) -> dict[str, float] | None:
        """Read end-effector pose. Not used — IK is done in DimOS."""
        return None

    def write_cartesian_position(
        self,
        pose: dict[str, float],
        velocity: float = 1.0,
    ) -> bool:
        """Cartesian position control not supported via this adapter."""
        return False

    # =========================================================================
    # Gripper (none fitted)
    # =========================================================================

    def read_gripper_position(self) -> float | None:
        """No gripper on ZArm."""
        return None

    def write_gripper_position(self, position: float) -> bool:
        """No gripper on ZArm."""
        return False

    # =========================================================================
    # Force/Torque Sensor (not available)
    # =========================================================================

    def read_force_torque(self) -> list[float] | None:
        """No F/T sensor available via Fairino RPC."""
        return None


def register(registry: "AdapterRegistry") -> None:
    """Register this adapter with the registry."""
    registry.register("zarm", ZArmAdapter)


__all__ = ["ZArmAdapter"]
