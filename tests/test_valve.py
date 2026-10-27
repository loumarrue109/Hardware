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

        print("=== Link test (AK) ===")
        print("Reply:", valve.ping())
        print()

        print("=== Firmware (VR) ===")
        print(valve.get_firmware())
        print()

        print("=== Current position (CP) ===")
        print("Position:", valve.get_position())
        print()

        print("=== Command list (?) ===")
        help_text = valve.get_help()
        print(help_text if help_text else "(no response)")

        if "Control Command List" in help_text:
            print()
            print("=== Link OK: actuator is talking back ===")
        else:
            print()
            print("=== WARNING: no help text received, check port/baud/cable ===")

        if move:
            print()
            print("=== Move test: GO02 -> GO05 -> GO16 -> HM (16-port) ===")
            print("Setting response mode to Extended (IFM2)...")
            print("IFM2:", valve.set_response_mode(2))
            print("Position before:", valve.get_position())
            print("GO02:", valve.go(2, wait=True))
            print("Position after GO02:", valve.get_position())
            print("GO05:", valve.go(5, wait=True))
            print("Position after GO05:", valve.get_position())
            print("GO16:", valve.go(16, wait=True))
            print("Position after GO16:", valve.get_position())
            print("HM:", valve.home(wait=True))
            print("Position after HM:", valve.get_position())
            print("Move time of last move (TM):", valve.get_last_move_time())
            print("Move complete.")
    finally:
        valve.close()


if __name__ == "__main__":
    main()

# %%