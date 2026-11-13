#Start dashboard: python main.py
#opens dashboard GUI
#connects classes 


import tkinter as tk

from co2_sensor import CO2Sensor
from config import load_config, make_co2_sensor, make_mfc, make_pressure_sensor, make_pump, make_valve
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
    logging_cfg = load_config().get("logging", {})

    co2_fields = [f.strip().upper() for f in logging_cfg.get("co2_fields", [])]
    co2_average = logging_cfg.get("co2_average")
    if co2 is not None:
        if co2_fields:
            try:
                co2.set_form(*co2_fields)
            except Exception as exc:
                print(f"CO2 FORM setup failed: {exc}")
        if co2_average is not None:
            try:
                co2.set_average(float(co2_average))
            except Exception as exc:
                print(f"CO2 AVERAGE setup failed: {exc}")
    co2_log_fields = [
        CO2Sensor.FORM_KEYS[field]
        for field in co2_fields
        if field in CO2Sensor.FORM_KEYS and CO2Sensor.FORM_KEYS[field] != "co2"
    ]

    Dashboard(
        root,
        valve=valve,
        mfc=mfc,
        pressure_sensor=sensor,
        pump=pump,
        co2=co2,
        valve_num_positions=valve_num_positions,
        co2_log_path=logging_cfg.get("co2_path", "co2_log.csv"),
        co2_log_window=float(logging_cfg.get("co2_window", 60)),
        co2_log_fields=co2_log_fields,
        co2_log_mode=logging_cfg.get("co2_mode", "average"),
    )
    root.mainloop()


if __name__ == "__main__":
    main()