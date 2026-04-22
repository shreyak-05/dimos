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

"""Advanced control coordinator blueprints: servo, velocity, cartesian IK, and teleop IK.

Usage:
    dimos run coordinator-teleop-xarm6         # Servo streaming (XArm6)
    dimos run coordinator-velocity-xarm6       # Velocity streaming (XArm6)
    dimos run coordinator-combined-xarm6       # Servo + velocity (XArm6)
    dimos run coordinator-cartesian-ik-mock    # Cartesian IK (mock)
    dimos run coordinator-cartesian-ik-piper   # Cartesian IK (Piper)
    dimos run coordinator-teleop-xarm7         # TeleopIK (XArm7)
    dimos run coordinator-teleop-piper         # TeleopIK (Piper)
    dimos run coordinator-teleop-dual          # TeleopIK dual arm
"""

from __future__ import annotations

from dimos.control.blueprints._hardware import (
    PIPER_MODEL_PATH,
    XARM6_MODEL_PATH,
    XARM7_MODEL_PATH,
    mock_arm,
    piper,
    realhand_l6,
    xarm6,
    xarm7,
)
from dimos.control.components import make_gripper_joints
from dimos.control.coordinator import ControlCoordinator, TaskConfig
from dimos.core.transport import LCMTransport
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.teleop.quest.quest_types import Buttons

# XArm6 teleop - streaming position control
coordinator_teleop_xarm6 = ControlCoordinator.blueprint(
    hardware=[xarm6()],
    tasks=[
        TaskConfig(
            name="servo_arm",
            type="servo",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("joint_command", JointState): LCMTransport("/teleop/joint_command", JointState),
    }
)

# XArm6 velocity control - streaming velocity for joystick
coordinator_velocity_xarm6 = ControlCoordinator.blueprint(
    hardware=[xarm6()],
    tasks=[
        TaskConfig(
            name="velocity_arm",
            type="velocity",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("joint_command", JointState): LCMTransport("/joystick/joint_command", JointState),
    }
)

# XArm6 combined (servo + velocity tasks)
coordinator_combined_xarm6 = ControlCoordinator.blueprint(
    hardware=[xarm6()],
    tasks=[
        TaskConfig(
            name="servo_arm",
            type="servo",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
        TaskConfig(
            name="velocity_arm",
            type="velocity",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("joint_command", JointState): LCMTransport("/control/joint_command", JointState),
    }
)


# Mock 6-DOF arm with CartesianIK
coordinator_cartesian_ik_mock = ControlCoordinator.blueprint(
    hardware=[mock_arm("arm", 6)],
    tasks=[
        TaskConfig(
            name="cartesian_ik_arm",
            type="cartesian_ik",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
            model_path=PIPER_MODEL_PATH,
            ee_joint_id=6,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
    }
)

# Piper arm with CartesianIK
coordinator_cartesian_ik_piper = ControlCoordinator.blueprint(
    hardware=[piper()],
    tasks=[
        TaskConfig(
            name="cartesian_ik_arm",
            type="cartesian_ik",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
            model_path=PIPER_MODEL_PATH,
            ee_joint_id=6,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
    }
)


# Single XArm7 with TeleopIK
coordinator_teleop_xarm7 = ControlCoordinator.blueprint(
    hardware=[xarm7(gripper=False)],
    tasks=[
        TaskConfig(
            name="teleop_xarm",
            type="teleop_ik",
            joint_names=[f"arm_joint{i + 1}" for i in range(7)],
            priority=10,
            model_path=XARM7_MODEL_PATH,
            ee_joint_id=7,
            hand="right",
            gripper_joint=make_gripper_joints("arm")[0],
            gripper_open_pos=0.85,
            gripper_closed_pos=0.0,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)

# Single Piper with TeleopIK
coordinator_teleop_piper = ControlCoordinator.blueprint(
    hardware=[piper()],
    tasks=[
        TaskConfig(
            name="teleop_piper",
            type="teleop_ik",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
            model_path=PIPER_MODEL_PATH,
            ee_joint_id=6,
            hand="left",
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)

# Dual arm teleop: XArm6 + Piper with TeleopIK
coordinator_teleop_dual = ControlCoordinator.blueprint(
    hardware=[xarm6("xarm_arm"), piper("piper_arm")],
    tasks=[
        TaskConfig(
            name="teleop_xarm",
            type="teleop_ik",
            joint_names=[f"xarm_arm_joint{i + 1}" for i in range(6)],
            priority=10,
            model_path=XARM6_MODEL_PATH,
            ee_joint_id=6,
            hand="left",
        ),
        TaskConfig(
            name="teleop_piper",
            type="teleop_ik",
            joint_names=[f"piper_arm_joint{i + 1}" for i in range(6)],
            priority=10,
            model_path=PIPER_MODEL_PATH,
            ee_joint_id=6,
            hand="right",
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


_arm_joints_7 = [f"arm_joint{i + 1}" for i in range(7)]
_hand_joints_6 = [f"hand_joint{i + 1}" for i in range(6)]

# XArm7 + RealHand L6 (real hardware)
coordinator_teleop_xarm7_realhand = ControlCoordinator.blueprint(
    hardware=[xarm7(gripper=False), realhand_l6()],
    tasks=[
        TaskConfig(
            name="teleop_xarm",
            type="teleop_ik",
            joint_names=_arm_joints_7,
            priority=10,
            model_path=XARM7_MODEL_PATH,
            ee_joint_id=7,
            hand="right",
        ),
        TaskConfig(
            name="teleop_hand",
            type="hand_teleop",
            joint_names=_hand_joints_6,
            hand="right",
            priority=9,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("cartesian_command", PoseStamped): LCMTransport(
            "/coordinator/cartesian_command", PoseStamped
        ),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


# RealHand L6 only — trigger curls all 5 fingers, grip toggles thumb abduction.
# Only "open" in grasp_primitives → grip toggles abduction instead of cycling grasps.
# Limits from linkerbot-py SDK: thumb_flex max 1.30, thumb_abd max 0.58.
coordinator_realhand = ControlCoordinator.blueprint(
    hardware=[realhand_l6()],
    tasks=[
        TaskConfig(
            name="teleop_hand",
            type="hand_teleop",
            joint_names=_hand_joints_6,
            hand="right",
            priority=9,
            grasp_primitives={"open": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
            trigger_max=[1.00, 0.00, 1.20, 1.20, 1.10, 1.00],
            thumb_abd_angle=0.52,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/hand_joint_state", JointState),
        ("buttons", Buttons): LCMTransport("/teleop/buttons", Buttons),
    }
)


__all__ = [
    # Cartesian IK
    "coordinator_cartesian_ik_mock",
    "coordinator_cartesian_ik_piper",
    "coordinator_combined_xarm6",
    "coordinator_teleop_dual",
    "coordinator_teleop_piper",
    # Hand only
    "coordinator_realhand",
    # Servo / Velocity
    "coordinator_teleop_xarm6",
    # TeleopIK
    "coordinator_teleop_xarm7",
    "coordinator_teleop_xarm7_realhand",
    "coordinator_velocity_xarm6",
]
