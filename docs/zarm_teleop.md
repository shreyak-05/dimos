# ZArm Teleop — Quick Start

## Prerequisites

```bash
# Install DimOS with required extras
pip install -e ".[manipulation,web,perception]"

# For real hardware only
pip install fairino
```

---

## Mock Test + Rerun Visualization (no hardware)

```bash
dimos run arm-teleop-zarm-visualizing-mock
```

- Rerun viewer opens automatically
- Quest web UI: `https://<your-ip>:8443`
- **Hold right A button** to engage, move controller → watch joints animate in Rerun

**What you'll see in Rerun:**
| Entity | What |
|---|---|
| `joints/arm_joint{1-6}/position_deg` | IK joint solution at 100 Hz |
| `world/teleop/right_controller` | Controller 3D pose |
| `world/teleop/right_controller/buttons/*` | Trigger, grip, A/B values |

---

## Real Hardware

ZArm must be powered on and reachable at `192.168.58.2`.

```bash
# Basic teleop (no visualization)
dimos run arm-teleop-zarm

# With Rerun visualization
dimos run arm-teleop-zarm-visualizing
```

---

## Record & Inspect an LCM Log

```bash
# Terminal 1 — record
lcmspy --log /tmp/zarm_session.lcm

# Terminal 2 — run teleop (mock or real)
dimos run arm-teleop-zarm

# After stopping, inspect the recording
python tools/inspect_zarm_log.py /tmp/zarm_session.lcm

# Save plot to file
python tools/inspect_zarm_log.py /tmp/zarm_session.lcm --save /tmp/analysis.png
```

The inspector plots:
- Per-joint positions over time (with URDF limit lines)
- Per-tick joint deltas (red line = 2° safety threshold)
- Safety violation markers

---

## Blueprint Reference

| Command | Use |
|---|---|
| `dimos run arm-teleop-zarm-visualizing-mock` | Mock + Rerun (pre-hardware testing) |
| `dimos run arm-teleop-zarm` | Real ZArm, no visualization |
| `dimos run arm-teleop-zarm-visualizing` | Real ZArm + Rerun |
| `dimos run coordinator-teleop-zarm` | Coordinator only (no Quest server) |
| `dimos run coordinator-zarm` | Trajectory control only |

---

## Safety Notes

- Max joint delta clamped to **2°/tick** (200°/s at 100 Hz)
- Press-and-hold **A button** to engage — release to stop immediately
- With realhand attached: keep movements slow, watch wrist joints (j4–j6)
- ZArm IP: `192.168.58.2` — ensure no other process is using the Fairino SDK simultaneously
