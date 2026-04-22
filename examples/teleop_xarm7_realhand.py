#!/usr/bin/env python3
"""Quest VR teleop for XArm7 + RealHand L6 (separate blueprints).

Runs two independent blueprints in one process:
  - XArm7 arm:    teleop_quest_xarm7 (right controller pose → IK → servoj)
  - RealHand L6:  teleop_quest_realhand (Quest server + hand coordinator)

Both share the same LCM buttons channel so Quest events reach both.

Prerequisites:
    sudo ip link set can0 up type can bitrate 1000000

Usage:
    python examples/teleop_xarm7_realhand.py
    python examples/teleop_xarm7_realhand.py --no-hand   # arm only
    python examples/teleop_xarm7_realhand.py --no-arm    # hand only

VR Controls (right controller):
    Hold A          → engage arm tracking
    Move controller → arm follows via IK
    Trigger         → squeeze to close fingers, release to open
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quest VR teleop: XArm7 arm + RealHand L6 hand"
    )
    parser.add_argument("--no-arm", action="store_true", help="Skip arm (hand only)")
    parser.add_argument("--no-hand", action="store_true", help="Skip hand (arm only)")
    args = parser.parse_args()

    if args.no_arm and args.no_hand:
        print("ERROR: --no-arm and --no-hand both set, nothing to run")
        sys.exit(1)

    coordinators = []

    if not args.no_arm and not args.no_hand:
        # Both: arm blueprint (includes Quest server) + hand coordinator
        from dimos.control.blueprints.teleop import coordinator_realhand
        from dimos.teleop.quest.blueprints import teleop_quest_xarm7

        print("Building XArm7 teleop blueprint (includes Quest server)...")
        arm_coord = teleop_quest_xarm7.build()
        coordinators.append(arm_coord)
        print("XArm7 arm teleop started.")

        print("Building RealHand L6 coordinator...")
        hand_coord = coordinator_realhand.build()
        coordinators.append(hand_coord)
        print("RealHand L6 hand started.")

    elif args.no_arm:
        # Hand only: need Quest server + hand coordinator
        from dimos.teleop.quest.blueprints import teleop_quest_realhand

        print("Building RealHand L6 teleop blueprint (includes Quest server)...")
        hand_coord = teleop_quest_realhand.build()
        coordinators.append(hand_coord)
        print("RealHand L6 hand teleop started.")

    else:
        # Arm only
        from dimos.teleop.quest.blueprints import teleop_quest_xarm7

        print("Building XArm7 teleop blueprint...")
        arm_coord = teleop_quest_xarm7.build()
        coordinators.append(arm_coord)
        print("XArm7 arm teleop started.")

    print("\nControls (right controller):")
    if not args.no_arm:
        print("  Hold A          → engage arm tracking")
        print("  Move controller → arm follows via IK")
    if not args.no_hand:
        print("  Trigger         → squeeze to close fingers, release to open")
    print("\nPress Ctrl+C to stop.\n")

    # --- Shutdown ---
    stop_event = threading.Event()

    def shutdown(signum: int = 0, frame: object = None) -> None:
        print("\nShutting down...")
        stop_event.set()
        for coord in reversed(coordinators):
            try:
                coord.stop()
            except Exception:
                pass
        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
