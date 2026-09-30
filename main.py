# Sampler control dashboard.
# Combines the MFC, pressure sensor and pump into a local Tkinter GUI.
# Run with:  python3 main.py

import time
import threading
import tkinter as tk
from queue import Empty, Queue
from tkinter import messagebox, ttk

from mfc import MFC
from pressure_sensor import Pressure_Sensor
from pump import Pump

POLL_INTERVAL = 1.0  # seconds between sensor reads
UI_POLL_INTERVAL = 200  # milliseconds between UI queue checks


def _connect(factory):
    """Return (device, error); error is None on success."""
    try:
        return factory(), None
    except Exception as exc:
        return None, exc


def _fmt(value, unit=""):
    try:
        return f"{float(value):.2f} {unit}".strip()
    except (TypeError, ValueError):
        return f"{value} {unit}".strip()


class Dashboard:
    """Local control dashboard for the sampler hardware."""

    def __init__(self, root):
        self.root = root
        self.root.title("Sampler Control Dashboard")
        self.root.geometry("820x470")
        self.root.minsize(680, 400)

        self._lock = threading.Lock()
        self._queue = Queue()      # worker -> UI updates
        self._actions = Queue()    # UI -> worker commands
        self._stop = threading.Event()
        self._pump_state = "OFF"

        self.mfc, mfc_err = _connect(MFC)
        self.sensor, sensor_err = _connect(Pressure_Sensor)
        self.pump, pump_err = _connect(Pump)

        self._build_ui()

        for name, err in (
            ("MFC", mfc_err),
            ("Pressure sensor", sensor_err),
            ("Pump", pump_err),
        ):
            if err:
                self._set_status(f"{name} not connected: {err}")

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        self.root.after(UI_POLL_INTERVAL, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self._var_serial = tk.StringVar(value="—")
        self._var_capacity = tk.StringVar(value="—")
        self._var_unit = tk.StringVar(value="—")
        self._var_flow = tk.StringVar(value="—")
        self._var_setpoint = tk.StringVar(value="—")
        self._var_pressure = tk.StringVar(value="—")
        self._var_firmware = tk.StringVar(value="—")
        self._var_pump = tk.StringVar(value="OFF")
        self._var_status = tk.StringVar(value="Ready")
        self._var_set_entry = tk.StringVar(value="0")

        self._set_flow_button = None
        self._stop_flow_button = None

        tk.Label(
            self.root,
            text="Sampler Control Dashboard",
            font=("Helvetica", 16, "bold"),
        ).grid(row=0, column=0, columnspan=3, pady=(10, 5))

        content = ttk.Frame(self.root)
        content.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10)
        content.columnconfigure((0, 1, 2), weight=1, uniform="panel")

        mfc_frame = ttk.LabelFrame(content, text="Mass Flow Controller (MFC)")
        mfc_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._build_mfc_panel(mfc_frame)

        pump_frame = ttk.LabelFrame(content, text="Pump")
        pump_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self._build_pump_panel(pump_frame)

        sensor_frame = ttk.LabelFrame(content, text="Pressure Sensor")
        sensor_frame.grid(row=0, column=2, sticky="nsew")
        self._build_sensor_panel(sensor_frame)

        tk.Label(
            self.root,
            textvariable=self._var_status,
            anchor="w",
            relief="sunken",
            padx=8,
        ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

        if self.mfc is None:
            self._set_flow_button.config(state="disabled")
            self._stop_flow_button.config(state="disabled")

    def _field(self, parent, row, text, variable, column=1):
        tk.Label(parent, text=text, anchor="w").grid(
            row=row, column=0, sticky="w", padx=8, pady=2
        )
        tk.Label(parent, textvariable=variable, anchor="w").grid(
            row=row, column=column, sticky="w", padx=8, pady=2
        )

    def _build_mfc_panel(self, frame):
        self._field(frame, 0, "Serial:", self._var_serial)
        self._field(frame, 1, "Capacity:", self._var_capacity)
        self._field(frame, 2, "Unit:", self._var_unit)
        self._field(frame, 3, "Flow:", self._var_flow)
        self._field(frame, 4, "Setpoint:", self._var_setpoint)

        entry_row = ttk.Frame(frame)
        entry_row.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 4))
        entry = ttk.Entry(entry_row, textvariable=self._var_set_entry, width=10)
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self._on_set_flow())

        self._set_flow_button = ttk.Button(
            entry_row, text="Set Flow", command=self._on_set_flow
        )
        self._set_flow_button.pack(side="left", padx=(6, 0))

        self._stop_flow_button = ttk.Button(
            frame, text="Stop Flow", command=lambda: self._submit("stop_flow")
        )
        self._stop_flow_button.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

    def _build_pump_panel(self, frame):
        self._pump_status_label = tk.Label(
            frame,
            textvariable=self._var_pump,
            font=("Helvetica", 12, "bold"),
            fg="#b22222",
        )
        self._pump_status_label.grid(row=0, column=0, padx=8, pady=4)

        on_button = tk.Button(
            frame,
            text="Pump ON",
            bg="#2e8b57",
            fg="white",
            activebackground="#3cb371",
            width=12,
            command=lambda: self._submit("pump_on"),
        )
        on_button.grid(row=1, column=0, padx=8, pady=6)

        off_button = tk.Button(
            frame,
            text="Pump OFF",
            bg="#b22222",
            fg="white",
            activebackground="#cd5c5c",
            width=12,
            command=lambda: self._submit("pump_off"),
        )
        off_button.grid(row=2, column=0, padx=8, pady=6)

        if self.pump is None:
            on_button.config(state="disabled")
            off_button.config(state="disabled")

    def _build_sensor_panel(self, frame):
        self._field(frame, 0, "Pressure:", self._var_pressure)
        self._field(frame, 1, "Firmware:", self._var_firmware)

    def _set_status(self, text):
        self._var_status.set(f"{time.strftime('%H:%M:%S')}  {text}")

    # ------------------------------------------------------------- actions

    def _submit(self, name, *args):
        self._actions.put((name, *args))

    def _on_set_flow(self):
        if self.mfc is None:
            return
        try:
            value = float(self._var_set_entry.get())
        except ValueError:
            messagebox.showerror("Invalid setpoint", "Enter a numeric flow.")
            return
        if value < 0:
            messagebox.showerror("Invalid setpoint", "Flow cannot be negative.")
            return
        if value > self.mfc.capacity:
            messagebox.showerror(
                "Invalid setpoint",
                f"Flow {value} exceeds capacity of "
                f"{self.mfc.capacity} {self.mfc.unit}.",
            )
            return
        self._submit("set_flow", value)
        self._set_status(f"Setting flow to {value} {self.mfc.unit}...")

    # -------------------------------------------------------------- worker

    def _run(self):
        while not self._stop.is_set():
            self._dispatch_actions()
            self._queue.put(self._read_all())
            self._stop.wait(POLL_INTERVAL)

    def _dispatch_actions(self):
        while not self._stop.is_set():
            try:
                action = self._actions.get_nowait()
            except Empty:
                return
            self._do_action(action)

    def _do_action(self, action):
        name, *args = action
        try:
            with self._lock:
                if name == "pump_on" and self.pump is not None:
                    self.pump.on()
                    self._pump_state = "ON"
                elif name == "pump_off" and self.pump is not None:
                    self.pump.off()
                    self._pump_state = "OFF"
                elif name == "set_flow" and self.mfc is not None:
                    self.mfc.set_flow(args[0])
                elif name == "stop_flow" and self.mfc is not None:
                    self.mfc.stop_flow()
        except Exception as exc:
            self._queue.put({"error": f"{name}: {exc}"})
        self._queue.put(self._read_all())

    def _read_all(self):
        status = {"pump": self._pump_state}
        with self._lock:
            if self.mfc is not None:
                try:
                    status["mfc"] = self.mfc.get_status()
                except Exception as exc:
                    status["mfc_error"] = str(exc)
            if self.sensor is not None:
                try:
                    status["pressure"] = self.sensor.get_pressure()
                    status["firmware"] = self.sensor.get_firmware()
                except Exception as exc:
                    status["pressure_error"] = str(exc)
        return status

    # ------------------------------------------------------------ UI loop

    def _poll(self):
        try:
            while True:
                self._populate(self._queue.get_nowait())
        except Empty:
            pass
        self.root.after(UI_POLL_INTERVAL, self._poll)

    def _populate(self, data):
        if "error" in data:
            self._set_status("Action failed: " + data["error"])
            return
        if "mfc_error" in data:
            self._set_status("MFC read failed: " + data["mfc_error"])
        if "mfc" in data:
            mfc = data["mfc"]
            self._var_serial.set(mfc["serial"])
            self._var_capacity.set(_fmt(mfc["capacity"]))
            self._var_unit.set(mfc["unit"])
            self._var_flow.set(_fmt(mfc["flow"], mfc["unit"]))
            self._var_setpoint.set(_fmt(mfc["setpoint"], mfc["unit"]))
        elif self.mfc is not None:
            self._set_status("MFC not responding.")
        if "pressure_error" in data:
            self._set_status("Pressure read failed: " + data["pressure_error"])
        if "pressure" in data:
            self._var_pressure.set(f"{data['pressure']:.3f} bar")
        if "firmware" in data:
            self._var_firmware.set(data["firmware"])
        if data.get("pump") != self._var_pump.get():
            self._var_pump.set(data["pump"])
            on = data["pump"] == "ON"
            self._pump_status_label.config(fg="#2e8b57" if on else "#b22222")
            self._set_status(f"Pump turned {'ON' if on else 'OFF'}")

    # ------------------------------------------------------------- cleanup

    def close(self):
        self._stop.set()
        self._worker.join(timeout=2)
        for device, name in (
            (self.pump, "pump"),
            (self.mfc, "MFC"),
            (self.sensor, "pressure sensor"),
        ):
            if device is not None and hasattr(device, "close"):
                try:
                    device.close()
                except Exception as exc:
                    print(f"Failed to close {name}: {exc}")
        self.root.destroy()


def main():
    root = tk.Tk()
    Dashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()