#%%
# Quick check that the Vaisala GMP343 CO2 sensor responds and reports gas.
#
# Uses the documented GMP343 command set: SEND gets one reading.
# If the unit is silent, the raw response to 'SEND' is shown so you can
# see whether anything came back at all.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from co2_sensor import CO2Sensor


def main():
    from config import make_co2_sensor
    sensor = make_co2_sensor()  # read the port from config.toml
    try:
        print("Port opened:", sensor.ser.is_open)
        print()

        print("=== Measurement (SEND command) ===")
        try:
            reading = sensor.get_measurement()
            print("CO2:", reading["co2"], reading["unit"])
        except RuntimeError as exc:
            print("No reading parsed:", exc)
            print()
            print("=== Raw response to SEND ===")
            raw = sensor.send_command("SEND")
            print("lines:", raw)
            print()
            print("If 'lines' is empty, the sensor returned no bytes;")
            print("check power, wiring/adapter, and RS-232 vs RS-485 mode.")
    finally:
        sensor.close()


if __name__ == "__main__":
    main()

# %%