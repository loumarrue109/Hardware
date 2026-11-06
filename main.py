# Sampler rig entry point.
# Builds the hardware from config.toml and opens the dashboard GUI.
# Run with:  python3 main.py
#
# This is the wiring layer: it hardcodes which device classes are used and
# how they are connected. Later, different mechanisms (calibration runs,
# automated sequences, new hardware) can be added here without touching
# the dashboard itself.

import tkinter as tk

from config import make_co2_sensor, make_mfc, make_pressure_sensor, make_pump, make_valve
from dashboard import Dashboard, connect


def main():
    try:
        valve, valve_cfg = make_valve()
        valve_err = None
    except Exception as exc:
        valve, valve_cfg, valve_err = None, None, exc
    valve_num_positions = valve_cfg.num_positions if valve_cfg else 16

    mfc, mfc_err = connect(make_mfc)
    sensor, sensor_err = connect(make_pressure_sensor)
    pump, pump_err = connect(make_pump)
    co2, co2_err = connect(make_co2_sensor)

    for name, err in (
        ("Valve", valve_err),
        ("MFC", mfc_err),
        ("Pressure sensor", sensor_err),
        ("Pump", pump_err),
        ("CO2 sensor", co2_err),
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
        co2=co2,
        valve_num_positions=valve_num_positions,
    )
    root.mainloop()


if __name__ == "__main__":
    main()