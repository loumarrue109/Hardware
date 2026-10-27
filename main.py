# Sampler rig entry point.
# Builds the hardware from config.toml and opens the dashboard GUI.
# Run with:  python3 main.py
#
# This is the wiring layer: it hardcodes which device classes are used and
# how they are connected. Later, different mechanisms (calibration runs,
# automated sequences, new hardware) can be added here without touching
# the dashboard itself.

import tkinter as tk

from config import load_valve_config, make_mfc, make_pressure_sensor, make_pump, make_valve
from dashboard import Dashboard, connect


def main():
    valve, valve_cfg = make_valve()
    valve_num_positions = valve_cfg.num_positions or 16

    mfc, mfc_err = connect(make_mfc)
    sensor, sensor_err = connect(make_pressure_sensor)
    pump, pump_err = connect(make_pump)

    for name, err in (
        ("MFC", mfc_err),
        ("Pressure sensor", sensor_err),
        ("Pump", pump_err),
    ):
        if err:
            print(f"{name} not connected: {err}")

    root = tk.Tk()
    Dashboard(
        root,
        valve=valve,
        mfc=mfc,
        pressure_sensor=sensor,
        pump=pump,
        valve_num_positions=valve_num_positions,
    )
    root.mainloop()


if __name__ == "__main__":
    main()