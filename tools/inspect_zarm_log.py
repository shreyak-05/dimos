#!/usr/bin/env python3
"""Offline inspector for ZArm teleop LCM recordings.

Decodes /coordinator/joint_state messages from an LCM log file and:
  - Plots per-joint positions over time
  - Plots per-tick joint deltas (flags ticks exceeding the safety threshold)
  - Reports joint limit proximity warnings

Usage:
    python tools/inspect_zarm_log.py /tmp/zarm_mock.lcm
    python tools/inspect_zarm_log.py /tmp/zarm_mock.lcm --delta-limit 2.0
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import lcm
import matplotlib.pyplot as plt
import numpy as np

from dimos_lcm.sensor_msgs import JointState as LCMJointState

# LCM topic written by coordinator
JOINT_STATE_TOPIC = "/coordinator/joint_state#sensor_msgs.JointState"

# Joint limits from zarm.urdf (radians)
JOINT_LOWER = [-3.0543, -4.6251, -2.8274, -4.6251, -3.0543, -3.0543]
JOINT_UPPER = [3.0543, 1.4835, 2.8274, 1.4835, 3.0543, 3.0543]
JOINT_NAMES = ["j1_pan", "j2_lift", "j3_elbow", "j4_wrist1", "j5_wrist2", "j6_wrist3"]

# Safety threshold: max joint change per tick (degrees)
DEFAULT_DELTA_LIMIT_DEG = 2.0
# Warn when within this fraction of a joint limit
LIMIT_WARN_FRACTION = 0.1


def load_log(path: str, delta_limit_deg: float) -> dict:
    """Read LCM log and decode all JointState messages."""
    log = lcm.EventLog(path, "r")

    timestamps: list[float] = []
    positions: list[list[float]] = []  # [tick][joint]

    n_decoded = 0
    n_skipped = 0

    for event in log:
        if event.channel != JOINT_STATE_TOPIC:
            continue
        try:
            msg = LCMJointState.decode(event.data)
            ts = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            pos = list(msg.position)
            if len(pos) >= 6:
                timestamps.append(ts)
                positions.append(pos[:6])
                n_decoded += 1
        except Exception:
            n_skipped += 1

    log.close()

    print(f"Decoded {n_decoded} JointState messages ({n_skipped} skipped)")
    if n_decoded == 0:
        print(f"No messages found on channel: {JOINT_STATE_TOPIC}")
        print("Available channels in log:")
        log2 = lcm.EventLog(path, "r")
        channels: set[str] = set()
        for ev in log2:
            channels.add(ev.channel)
            if len(channels) > 20:
                break
        log2.close()
        for ch in sorted(channels):
            print(f"  {ch}")
        return {}

    t = np.array(timestamps)
    t -= t[0]  # relative time from start
    pos_arr = np.array(positions)  # shape (N, 6)

    # Per-tick joint deltas in degrees
    deltas = np.zeros_like(pos_arr)
    deltas[1:] = np.abs(np.diff(pos_arr, axis=0))
    deltas_deg = np.degrees(deltas)

    # Safety violations: ticks where any joint exceeded delta limit
    delta_limit_rad = math.radians(delta_limit_deg)
    violations = np.any(np.diff(pos_arr, axis=0, prepend=pos_arr[:1]) > delta_limit_rad, axis=1)

    # Limit proximity warnings: any joint within 10% of its range from limit
    limit_warnings: list[str] = []
    for j in range(6):
        lo, hi = JOINT_LOWER[j], JOINT_UPPER[j]
        span = hi - lo
        margin = span * LIMIT_WARN_FRACTION
        too_low = np.where(pos_arr[:, j] < lo + margin)[0]
        too_high = np.where(pos_arr[:, j] > hi - margin)[0]
        if len(too_low):
            limit_warnings.append(
                f"  {JOINT_NAMES[j]}: {len(too_low)} ticks near lower limit "
                f"({math.degrees(lo + margin):.1f}°)"
            )
        if len(too_high):
            limit_warnings.append(
                f"  {JOINT_NAMES[j]}: {len(too_high)} ticks near upper limit "
                f"({math.degrees(hi - margin):.1f}°)"
            )

    return {
        "t": t,
        "pos": pos_arr,
        "deltas_deg": deltas_deg,
        "violations": violations,
        "limit_warnings": limit_warnings,
        "delta_limit_deg": delta_limit_deg,
        "n_ticks": n_decoded,
        "duration": t[-1] if len(t) else 0.0,
    }


def print_summary(data: dict) -> None:
    duration = data["duration"]
    n = data["n_ticks"]
    rate = n / duration if duration > 0 else 0
    n_viol = int(data["violations"].sum())
    deltas = data["deltas_deg"]

    print(f"\n=== Summary ===")
    print(f"  Duration : {duration:.1f}s  ({n} ticks, {rate:.0f} Hz)")
    print(f"  Delta limit: {data['delta_limit_deg']:.1f}°/tick")
    print(f"  Safety violations (delta > limit): {n_viol} ticks  ({100*n_viol/n:.1f}%)")
    print(f"  Max delta seen: {deltas.max():.2f}°  (joint {JOINT_NAMES[int(deltas.max(axis=0).argmax())]})")

    if data["limit_warnings"]:
        print(f"\n  Joint limit proximity warnings:")
        for w in data["limit_warnings"]:
            print(w)
    else:
        print(f"\n  No joint limit proximity warnings.")


def plot(data: dict, save_path: str | None = None) -> None:
    t = data["t"]
    pos_deg = np.degrees(data["pos"])
    deltas = data["deltas_deg"]
    violations = data["violations"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle("ZArm Teleop — Joint Analysis", fontsize=13, fontweight="bold")

    # ---- Plot 1: Joint positions ----
    ax = axes[0]
    colors = plt.cm.tab10(np.linspace(0, 1, 6))
    for j in range(6):
        ax.plot(t, pos_deg[:, j], label=JOINT_NAMES[j], color=colors[j], linewidth=1.2)
        # Shade joint limit range
        lo_deg = math.degrees(JOINT_LOWER[j])
        hi_deg = math.degrees(JOINT_UPPER[j])
        ax.axhline(lo_deg, color=colors[j], linestyle=":", linewidth=0.6, alpha=0.5)
        ax.axhline(hi_deg, color=colors[j], linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_ylabel("Position (°)")
    ax.set_title("Joint Positions  (dotted = URDF limits)")
    ax.legend(ncol=6, fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    # ---- Plot 2: Per-tick deltas ----
    ax = axes[1]
    for j in range(6):
        ax.plot(t, deltas[:, j], label=JOINT_NAMES[j], color=colors[j], linewidth=0.8, alpha=0.8)
    ax.axhline(
        data["delta_limit_deg"],
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"limit ({data['delta_limit_deg']:.1f}°)",
    )
    ax.set_ylabel("Delta (°/tick)")
    ax.set_title("Per-tick Joint Delta  (red = safety threshold)")
    ax.legend(ncol=7, fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    # ---- Plot 3: Violation markers ----
    ax = axes[2]
    ax.fill_between(t, violations.astype(float), alpha=0.6, color="red", label="violation")
    ax.set_ylabel("Violation")
    ax.set_xlabel("Time (s)")
    ax.set_title("Safety Violations (any joint delta > limit)")
    ax.set_ylim(-0.1, 1.3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["OK", "VIOLATION"])
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\nPlot saved to: {save_path}")
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ZArm LCM teleop log")
    parser.add_argument("log", help="Path to .lcm log file")
    parser.add_argument(
        "--delta-limit",
        type=float,
        default=DEFAULT_DELTA_LIMIT_DEG,
        metavar="DEG",
        help=f"Safety delta limit in degrees/tick (default: {DEFAULT_DELTA_LIMIT_DEG})",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="Save plot to file instead of showing (e.g. --save /tmp/analysis.png)",
    )
    args = parser.parse_args()

    if not Path(args.log).exists():
        print(f"Error: log file not found: {args.log}")
        return

    data = load_log(args.log, args.delta_limit)
    if not data:
        return

    print_summary(data)
    plot(data, save_path=args.save)


if __name__ == "__main__":
    main()
