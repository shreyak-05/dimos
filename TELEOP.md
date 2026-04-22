# RealHand L6 Quest Teleop

Fork of [`dimensionalOS/dimos`](https://github.com/dimensionalOS/dimos) that
adds Meta Quest VR teleoperation for a LinkerHand RealHand L6 hand, wired
through the existing dimos control coordinator / blueprints. Everything lives
on branch `teleop-xarm-realhand`.

These instructions cover **hand-only** use on a clean machine with no existing
dimos clone. (The same branch also supports a UFactory XArm7 arm — ignore that
if you only have the hand.)

---

## 1. System dependencies (one-time per machine)

Installs LCM, build tools, CUDA if applicable. Use the upstream dimos
one-shot installer:

```bash
curl -fsSL https://raw.githubusercontent.com/dimensionalOS/dimos/main/scripts/install.sh | bash
```

Or follow the OS-specific guide manually — after the clone step below you'll
find them at `docs/installation/{ubuntu,nix,osx}.md`.

## 2. Clone this fork

```bash
git clone -b teleop-xarm-realhand https://github.com/shreyak-05/dimos.git
cd dimos
```

Verify:

```bash
git status                                       # "On branch teleop-xarm-realhand"
ls TELEOP.md examples/teleop_xarm7_realhand.py   # both should exist
```

## 3. Python environment (editable install from source)

PyPI's `dimos` package does **not** include these teleop files, so install the
clone in editable mode:

```bash
uv venv --python "3.12"
source .venv/bin/activate
uv pip install -e '.[base,manipulation]'
```

If `uv` is missing: `pip install uv`.

## 4. RealHand L6 SDK (not in pyproject extras)

```bash
uv pip install linkerbot-py
```

## 5. CAN bus for the hand

The RealHand L6 talks over CAN — typically `can0` at 1 Mbps via a PCAN-USB
adapter.

Plug in the PCAN-USB adapter, then check the kernel sees it:

```bash
ip -br link show | grep can      # should list can0
lsusb | grep -i peak             # should show the PEAK-System adapter
```

If `can0` is missing, load the driver:

```bash
sudo modprobe peak_usb
```

Bring the interface up at 1 Mbps (needed once per boot):

```bash
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 up type can bitrate 1000000
ip -br link show can0              # should print "can0  UP  ..."
```

> If you see `[Errno 19] No such device` at runtime, `can0` was never brought
> up — re-run the commands above.

Physical hand side (defaults to `left`):

```bash
export REALHAND_SIDE=left   # or "right"
```

## 6. Meta Quest

The example starts the Quest receiver for you via the `teleop_quest_realhand`
blueprint — it listens on `https://0.0.0.0:8443` (you'll see the URL in the
startup logs). Point the Quest streamer app on the headset at this host's IP.

---

## Running

```bash
python examples/teleop_xarm7_realhand.py --no-arm
```

## VR controls (right controller)

Mappings are on the **right** controller by default (`hand="right"` in
`dimos/control/blueprints/teleop.py`). To use the left controller, change
`hand="right"` → `hand="left"` in the `coordinator_realhand` `TaskConfig`.

| Input                | Effect                                                                  |
| -------------------- | ----------------------------------------------------------------------- |
| **Trigger** (analog) | Proportional curl of thumb flex + all four fingers (release = open)     |
| **Grip** (press)     | Step thumb **abduction** through `0 → 0.16 → 0.31 → 0.52 rad → 0 …`      |
| **B** (press)        | Reset everything: open fingers, abduction back to 0                     |

Tuning (in `dimos/control/blueprints/teleop.py` → `coordinator_realhand`):

- `trigger_max=[1.00, 0.00, 1.20, 1.20, 1.10, 1.00]` — per-joint max curl
  in CAN order `[thumb_flex, thumb_abd, index, middle, ring, pinky]`. The
  second entry is 0 because thumb abduction is driven by grip, not trigger.
- `thumb_abd_angle=0.52` — max step for the grip-button abduction cycle
  (hardware limit is 0.58 rad).
- `grasp_primitives={"open": [...]}` — only "open" is defined, which is why
  grip toggles abduction instead of cycling grasp presets.

---

## What was added in this fork

New files:
- `examples/teleop_xarm7_realhand.py` — Quest teleop runner (supports `--no-arm`)
- `dimos/control/tasks/hand_teleop_task.py` — button/trigger-driven hand task
- `dimos/hardware/manipulators/realhand_l6/` — RealHand L6 adapter (linkerbot-py)

Modified:
- `dimos/control/blueprints/_hardware.py` — `realhand_l6()` hardware factory
- `dimos/control/blueprints/teleop.py` — `coordinator_realhand` (and `coordinator_teleop_xarm7_realhand`)
- `dimos/control/coordinator.py` — hand-task wiring
- `dimos/control/tasks/teleop_task.py` — shared buttons handling
- `dimos/robot/all_blueprints.py` — registers the new coordinators
- `dimos/teleop/quest/blueprints.py` — `teleop_quest_realhand` (and `teleop_quest_xarm7`)

## Upstream

Forked from [`dimensionalOS/dimos`](https://github.com/dimensionalOS/dimos).
Base commit: `660b78280` (Merge branch 'main' into dev).
