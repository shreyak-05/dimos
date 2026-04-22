# XArm7 + RealHand L6 Quest Teleop

Fork-only addition on branch `teleop-xarm-realhand`. Adds Meta Quest VR
teleoperation for a UFactory XArm7 arm and a LinkerHand RealHand L6 hand,
wired through the existing dimos control coordinator / blueprints.

## Installation (fresh clone)

### 1. System dependencies

Follow the upstream dimos system install for your OS (installs LCM, build tools,
CUDA if applicable):

- Ubuntu 22.04 / 24.04: [`docs/installation/ubuntu.md`](docs/installation/ubuntu.md)
- NixOS / other Linux: [`docs/installation/nix.md`](docs/installation/nix.md)
- macOS: [`docs/installation/osx.md`](docs/installation/osx.md)

Or the one-shot interactive installer:

```bash
curl -fsSL https://raw.githubusercontent.com/dimensionalOS/dimos/main/scripts/install.sh | bash
```

### 2. Clone this fork

```bash
git clone -b teleop-xarm-realhand https://github.com/shreyak-05/dimos.git
cd dimos
```

> `-b teleop-xarm-realhand` pulls the branch that contains the teleop code.

### 3. Python environment (editable install from source)

PyPI's `dimos` package does **not** include these teleop files, so install the
cloned fork in editable mode:

```bash
uv venv --python "3.12"
source .venv/bin/activate
uv pip install -e '.[base,manipulation]'
```

`manipulation` pulls `xarm-python-sdk` and Drake for IK. If `uv` is missing:
`pip install uv`.

### 4. RealHand L6 SDK (not in pyproject extras)

```bash
uv pip install linkerbot-py
```

### 5. CAN bus for the hand

The RealHand L6 talks over CAN (default interface `can0` at 1 Mbps — e.g. via a
PCAN-USB adapter). Bring it up once per boot:

```bash
sudo ip link set can0 up type can bitrate 1000000
```

Physical hand side (defaults to `left`):

```bash
export REALHAND_SIDE=left   # or "right"
```

### 6. XArm7

Set the arm IP (or edit `dimos/control/blueprints/_hardware.py`):

```bash
export XARM7_IP=192.168.1.xxx
```

### 7. Meta Quest

Run the dimos Quest receiver (ships with the upstream Quest module) and make
sure the Quest streamer on the headset is pointed at this host.

## Running

```bash
# Both arm + hand
python examples/teleop_xarm7_realhand.py

# Arm only
python examples/teleop_xarm7_realhand.py --no-hand

# Hand only
python examples/teleop_xarm7_realhand.py --no-arm
```

## VR controls (right controller)

| Input              | Effect                                             |
| ------------------ | -------------------------------------------------- |
| Hold **A**         | Engage arm tracking                                |
| Move controller    | Arm follows via IK                                 |
| **Trigger** analog | Squeeze to curl all five fingers, release to open  |
| **Grip**           | Toggle thumb abduction (hand-only blueprint)       |

The trigger/grip are bound to the **right** VR controller by default
(`hand="right"` in `dimos/control/blueprints/teleop.py`). To drive the hand
from the **left** controller, change `hand="right"` → `hand="left"` in the
relevant `TaskConfig` entries.

## What was added in this fork

New files:
- `examples/teleop_xarm7_realhand.py` — dual-blueprint Quest teleop runner
- `dimos/control/tasks/hand_teleop_task.py` — button/trigger-driven hand task
- `dimos/hardware/manipulators/realhand_l6/` — RealHand L6 adapter (linkerbot-py)

Modified:
- `dimos/control/blueprints/_hardware.py` — `realhand_l6()` hardware factory
- `dimos/control/blueprints/teleop.py` — `coordinator_teleop_xarm7_realhand`, `coordinator_realhand`
- `dimos/control/coordinator.py` — hand-task wiring
- `dimos/control/tasks/teleop_task.py` — shared buttons handling
- `dimos/robot/all_blueprints.py` — registers the new coordinators
- `dimos/teleop/quest/blueprints.py` — `teleop_quest_xarm7`, `teleop_quest_realhand`

## Upstream

Forked from [`dimensionalOS/dimos`](https://github.com/dimensionalOS/dimos).
Base commit: `660b78280` (Merge branch 'main' into dev).
