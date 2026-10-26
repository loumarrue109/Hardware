#%%
# Quick check that the VICI EUTA actuator responds on the serial link.
#
# Read-only by default (proves the link is alive).
# To also physically move the valve:  python3 test_valve.py move

import sys

from valve import Valve


def main():
    move = "move" in sys.argv[1:]

    valve = Valve()

    try:
        print("Port opened:", valve.ser.is_open)
        print()

        print("=== Firmware (VR) ===")
        print(valve.get_firmware())
        print()

        print("=== Current position (CP) ===")
        print("Position:", valve.get_position())
        print()

        print("=== Command list (/) ===")
        help_text = valve.get_help()
        print(help_text if help_text else "(no response)")

        if "GO[nn] - Move to nn position" in help_text:
            print()
            print("=== Link OK: actuator is talking back ===")
        else:
            print()
            print("=== WARNING: no help text received, check port/baud/cable ===")

        if move:
            print()
            print("=== Testing a move: GO01 -> HM -> back ===")
            print("Move to position 1:", valve.go(1))
            print("Move home:", valve.home())
            print("Position after:", valve.get_position())
            print("Move complete.")
    finally:
        valve.close()


if __name__ == "__main__":
    main()

# %%