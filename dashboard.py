# Dashboard GUI for the sampler hardware
# drives Tkinter window
# device objects passed in

import collections
import time
import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from tkinter import messagebox, ttk

POLL_INTERVAL = 1.0  #seconds between sensor reads
UI_POLL_INTERVAL = 200  #milliseconds between UI queue checks

# Dark navy theme
BG = "#0d1b2a"          #window background
PANEL_BG = "#142a4d"    #panel / labelframe background
ENTRY_BG = "#1c3a63"    #entry field background
BUTTON_BG = "#1f3f6e"   #ttk button background
BUTTON_ACTIVE = "#3a67a3"
FG = "#e8e8f0"          #main text colour
FG_DIM = "#7fb3d9"      #disabled / secondary text
PUMP_ON = "#4ade80"
PUMP_OFF = "#ff5f5f"


def connect(factory):
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
    """
    Local control dashboard for sampler hardware
    """

    def __init__(
        self,
        root,
        valve=None,
        mfc=None,
        pressure_sensor=None,
        pump=None,
        co2=None,
        valve_num_positions=16,
        co2_log_path="co2_log.csv",
        co2_log_window=60.0,
        co2_log_fields=(),
        co2_log_mode="average",
    ):
        self.root = root
        self.root.title("Abbey ROAD (Remote Observation & Aquistion Dashboard)")
        self.root.geometry("1080x680")
        self.root.minsize(900, 560)
        self.root.configure(bg=BG)
        self._setup_style()

        self._lock = threading.Lock()
        self._queue = Queue()      # worker - UI updates every 1s automatically
        self._actions = Queue()    # UI - worker commands e.g. set flow, Pump on
        self._stop = threading.Event()

        self.valve = valve
        self.mfc = mfc
        self.sensor = pressure_sensor
        self.pump = pump
        self.co2 = co2
        self.valve_num_positions = valve_num_positions
        self.co2_log_path = co2_log_path
        self.co2_log_window = co2_log_window
        self.co2_log_fields = tuple(co2_log_fields)
        self._log_extra_fields = tuple(co2_log_fields) + ("mfc_flow", "calib_ppm")
        self.co2_log_mode = co2_log_mode
        self._co2_recorder = None
        self._co2_log_full = None
        self._co2_history = collections.deque(maxlen=1800)  # ~30 min at 1 Hz
        self._last_graph_draw = 0.0
        self._calib_ppm = None
        self._calib_buttons = {}
        self._pump_state = "OFF"

        self._build_ui()

        for name, device in (
            ("Valve", self.valve),
            ("MFC", self.mfc),
            ("Pressure sensor", self.sensor),
            ("Pump", self.pump),
            ("CO2 sensor", self.co2),
        ):
            if device is None:
                self._set_status(f"{name} not connected")

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        self.root.after(UI_POLL_INTERVAL, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------ UI

    def _setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dashboard.TFrame", background=BG)
        style.configure(
            "Dashboard.TLabelframe",
            background=PANEL_BG,
            foreground=FG,
        )
        style.configure(
            "Dashboard.TLabelframe.Label",
            background=PANEL_BG,
            foreground=FG,
        )
        style.layout(
            "Dashboard.TLabelframe", style.layout("TLabelframe")
        )
        style.layout(
            "Dashboard.TLabelframe.Label",
            style.layout("TLabelframe.Label"),
        )
        style.configure(
            "Dashboard.TEntry",
            fieldbackground=ENTRY_BG,
            foreground=FG,
            insertcolor=FG,
        )
        style.configure(
            "Dashboard.TSpinbox",
            fieldbackground=ENTRY_BG,
            foreground=FG,
            insertcolor=FG,
            arrowcolor=FG_DIM,
        )
        style.layout("Dashboard.TSpinbox", style.layout("TSpinbox"))
        style.configure(
            "Dashboard.TButton",
            background=BUTTON_BG,
            foreground=FG,
            bordercolor=BUTTON_BG,
            lightcolor=BUTTON_BG,
            darkcolor=BUTTON_BG,
            focuscolor=BUTTON_BG,
        )
        style.map(
            "Dashboard.TButton",
            background=[("active", BUTTON_ACTIVE), ("disabled", BUTTON_BG)],
            foreground=[("disabled", FG_DIM)],
        )

    def _build_ui(self):
        self._var_serial = tk.StringVar(value="—")
        self._var_capacity = tk.StringVar(value="—")
        self._var_unit = tk.StringVar(value="—")
        self._var_flow = tk.StringVar(value="—")
        self._var_setpoint = tk.StringVar(value="—")
        self._var_pressure = tk.StringVar(value="—")
        self._var_firmware = tk.StringVar(value="—")
        self._var_pump = tk.StringVar(value="OFF")
        self._var_valve_pos = tk.StringVar(value="—")
        self._var_co2 = tk.StringVar(value="—")
        self._var_log_state = tk.StringVar(value="Logging: off")
        self._var_log_mode = tk.StringVar(value=self.co2_log_mode)
        self._var_calib_state = tk.StringVar(value="Calib: none")
        self._var_status = tk.StringVar(value="Ready")
        self._var_set_entry = tk.StringVar(value="0")
        self._var_valve_entry = tk.StringVar(value="1")

        self._set_flow_button = None
        self._stop_flow_button = None
        self._valve_go_button = None
        self._valve_home_button = None

        tk.Label(
            self.root,
            text="Abbey ROAD",
            font=("Helvetica", 16, "bold"),
            bg=BG,
            fg=FG,
        ).grid(row=0, column=0, columnspan=4, pady=(10, 5))

        content = ttk.Frame(self.root, style="Dashboard.TFrame")
        content.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=10)
        content.columnconfigure((0, 1, 2, 3), weight=1, uniform="panel")
        content.rowconfigure(0, weight=1)

        mfc_frame = ttk.LabelFrame(
            content, text="Mass Flow Controller (MFC)",
            style="Dashboard.TLabelframe",
        )
        mfc_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._build_mfc_panel(mfc_frame)

        pump_frame = ttk.LabelFrame(
            content, text="Pump", style="Dashboard.TLabelframe"
        )
        pump_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self._build_pump_panel(pump_frame)

        sensor_frame = ttk.LabelFrame(
            content, text="Pressure Sensor", style="Dashboard.TLabelframe"
        )
        sensor_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 10))
        self._build_sensor_panel(sensor_frame)

        valve_frame = ttk.LabelFrame(
            content, text="Valve (EUTA)", style="Dashboard.TLabelframe"
        )
        valve_frame.grid(row=0, column=3, sticky="nsew")
        self._build_valve_panel(valve_frame)

        co2_frame = ttk.LabelFrame(
            content, text="CO2 Sensor (GMP343)", style="Dashboard.TLabelframe"
        )
        co2_frame.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        self._build_co2_panel(co2_frame)

        graph_frame = ttk.LabelFrame(
            self.root, text="CO2 — last 30 min", style="Dashboard.TLabelframe"
        )
        graph_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=10, pady=(10, 0))
        self._graph_canvas = tk.Canvas(
            graph_frame, bg=PANEL_BG, height=170, highlightthickness=0
        )
        self._graph_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._graph_canvas.bind("<Configure>", lambda e: self._draw_co2_graph())

        tk.Label(
            self.root,
            textvariable=self._var_status,
            anchor="w",
            relief="sunken",
            padx=8,
            bg=BG,
            fg=FG,
        ).grid(row=3, column=0, columnspan=4, sticky="ew", padx=10, pady=10)

        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

    def _field(self, parent, row, text, variable, column=1):
        tk.Label(parent, text=text, anchor="w", bg=PANEL_BG, fg=FG).grid(
            row=row, column=0, sticky="w", padx=8, pady=2
        )
        tk.Label(parent, textvariable=variable, anchor="w", bg=PANEL_BG, fg=FG).grid(
            row=row, column=column, sticky="w", padx=8, pady=2
        )

    def _build_mfc_panel(self, frame):
        self._field(frame, 0, "Serial:", self._var_serial)
        self._field(frame, 1, "Capacity:", self._var_capacity)
        self._field(frame, 2, "Unit:", self._var_unit)
        self._field(frame, 3, "Flow:", self._var_flow)
        self._field(frame, 4, "Setpoint:", self._var_setpoint)

        entry_row = ttk.Frame(frame, style="Dashboard.TFrame")
        entry_row.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 4))
        entry = ttk.Entry(
            entry_row, textvariable=self._var_set_entry, width=10,
            style="Dashboard.TEntry",
        )
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self._on_set_flow())

        self._set_flow_button = ttk.Button(
            entry_row, text="Set Flow", command=self._on_set_flow,
            style="Dashboard.TButton",
        )
        self._set_flow_button.pack(side="left", padx=(6, 0))

        self._stop_flow_button = ttk.Button(
            frame, text="Stop Flow", command=lambda: self._submit("stop_flow"),
            style="Dashboard.TButton",
        )
        self._stop_flow_button.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        if self.mfc is None:
            self._set_flow_button.config(state="disabled")
            self._stop_flow_button.config(state="disabled")

    def _build_pump_panel(self, frame):
        self._pump_status_label = tk.Label(
            frame,
            textvariable=self._var_pump,
            font=("Helvetica", 12, "bold"),
            fg=PUMP_OFF,
            bg=PANEL_BG,
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

    def _build_valve_panel(self, frame):
        self._field(frame, 0, "Position:", self._var_valve_pos)

        entry_row = ttk.Frame(frame, style="Dashboard.TFrame")
        entry_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 4))
        spinbox = ttk.Spinbox(
            entry_row,
            from_=1,
            to=self.valve_num_positions,
            textvariable=self._var_valve_entry,
            width=6,
            style="Dashboard.TSpinbox",
        )
        spinbox.pack(side="left")
        spinbox.bind("<Return>", lambda e: self._on_valve_go())

        self._valve_go_button = ttk.Button(
            entry_row, text="Go", command=self._on_valve_go,
            style="Dashboard.TButton",
        )
        self._valve_go_button.pack(side="left", padx=(6, 0))

        self._valve_home_button = ttk.Button(
            frame, text="Home (position 1)", command=lambda: self._submit("valve_home"),
            style="Dashboard.TButton",
        )
        self._valve_home_button.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        if self.valve is None:
            self._valve_go_button.config(state="disabled")
            self._valve_home_button.config(state="disabled")

    def _build_co2_panel(self, frame):
        frame.columnconfigure(1, weight=1)
        tk.Label(
            frame, text="CO2",
            font=("Helvetica", 12, "bold"), bg=PANEL_BG, fg=FG,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=8)
        tk.Label(
            frame, textvariable=self._var_co2,
            font=("Helvetica", 24, "bold"), bg=PANEL_BG, fg="#a5c8ff",
        ).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        controls = ttk.Frame(frame, style="Dashboard.TFrame")
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))
        self._log_button = ttk.Button(
            controls, text="Start Logging", command=self._on_toggle_logging,
            style="Dashboard.TButton",
        )
        self._log_button.pack(side="left")
        tk.Label(
            controls, text="log:", bg=PANEL_BG, fg=FG,
        ).pack(side="left", padx=(10, 2))
        tk.Radiobutton(
            controls, text="minute avg", variable=self._var_log_mode, value="average",
            bg=PANEL_BG, fg=FG, activebackground=PANEL_BG, activeforeground=FG,
            selectcolor=BG, highlightthickness=0,
        ).pack(side="left")
        tk.Radiobutton(
            controls, text="raw ~2 s", variable=self._var_log_mode, value="raw",
            bg=PANEL_BG, fg=FG, activebackground=PANEL_BG, activeforeground=FG,
            selectcolor=BG, highlightthickness=0,
        ).pack(side="left")
        tk.Label(
            controls, textvariable=self._var_log_state,
            anchor="w", bg=PANEL_BG, fg=FG_DIM,
        ).pack(side="left", padx=(12, 0))

        calib = ttk.Frame(frame, style="Dashboard.TFrame")
        calib.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        tk.Label(
            calib, text="Calib gas:", bg=PANEL_BG, fg=FG,
        ).pack(side="left")
        for value, label in ((0, "0 ppm"), (3, "3 ppm"), (400, "400 ppm")):
            button = tk.Button(
                calib, text=label, width=8, bg=BUTTON_BG, fg=FG,
                activebackground=BUTTON_ACTIVE,
                command=lambda v=value: self._on_calib_select(v),
            )
            button.pack(side="left", padx=(6, 0))
            self._calib_buttons[value] = button
        tk.Label(
            calib, textvariable=self._var_calib_state,
            bg=PANEL_BG, fg=FG_DIM,
        ).pack(side="left", padx=(12, 0))

    # ----------------------------------------------------------- CO2 graph

    def _maybe_draw_graph(self):
        now = time.time()
        if now - self._last_graph_draw < 2.0:
            return
        self._last_graph_draw = now
        self._draw_co2_graph()

    def _draw_co2_graph(self):
        canvas = self._graph_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 50 or height < 50:
            return

        now = time.time()
        window = 1800.0  # last 30 minutes
        points = [(t, c) for t, c in self._co2_history if now - t <= window]
        if len(points) < 2:
            canvas.create_text(width // 2, height // 2,
                               text="collecting CO2 data…", fill=FG_DIM)
            return

        co2s = [c for _, c in points]
        lo, hi = min(co2s), max(co2s)
        if hi - lo < 1.0:
            lo, hi = lo - 0.5, hi + 0.5
        pad = max(2.0, (hi - lo) * 0.1)
        lo, hi = lo - pad, hi + pad

        m_left, m_right, m_top, m_bottom = 46, 12, 12, 24
        plot_w = width - m_left - m_right
        plot_h = height - m_top - m_bottom
        t0 = now - window

        def tx(t):
            return m_left + (t - t0) / window * plot_w

        def ty(c):
            return m_top + (hi - c) / (hi - lo) * plot_h

        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            yy = m_top + frac * plot_h
            value = hi - frac * (hi - lo)
            canvas.create_line(m_left, yy, m_left + plot_w, yy, fill="#1e3a63")
            canvas.create_text(m_left - 6, yy, text=f"{value:.0f}",
                               anchor="e", fill=FG_DIM, font=("Helvetica", 8))

        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            tt = t0 + frac * window
            canvas.create_text(m_left + frac * plot_w, height - 10,
                               text=time.strftime("%H:%M", time.localtime(tt)),
                               anchor="n", fill=FG_DIM, font=("Helvetica", 8))

        coords = []
        for t, c in points:
            coords.extend((tx(t), ty(c)))
        if len(coords) >= 4:
            canvas.create_line(*coords, fill="#7ab8ff", width=1.5, smooth=True)

        last_c = points[-1][1]
        canvas.create_text(m_left + plot_w - 4, m_top + 4,
                           text=f"{last_c:.1f} ppm", anchor="ne",
                           fill="#a5c8ff", font=("Helvetica", 9, "bold"))

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

    def _on_valve_go(self):
        if self.valve is None:
            return
        try:
            value = int(self._var_valve_entry.get())
        except ValueError:
            messagebox.showerror("Invalid position", "Enter a number.")
            return
        if not 1 <= value <= self.valve_num_positions:
            messagebox.showerror(
                "Invalid position",
                f"Position must be between 1 and {self.valve_num_positions}.",
            )
            return
        self._submit("valve_go", value)
        self._set_status(f"Moving valve to position {value}...")

    def _new_log_path(self):
        """Return a fresh timestamped CSV path for a new logging session."""
        base = Path(self.co2_log_path)
        base.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        candidate = base / f"co2_{stamp}.csv"
        counter = 1
        while candidate.exists():
            candidate = base / f"co2_{stamp}_{counter}.csv"
            counter += 1
        return str(candidate)

    def _on_calib_select(self, value):
        """Select/deselect the synthetic calibration gas (0, 3 or 400 ppm)."""
        if self._calib_ppm == value:
            self._calib_ppm = None  # toggle off -> NaN in the log
        else:
            self._calib_ppm = value
        for button_value, button in self._calib_buttons.items():
            button.config(
                bg=BUTTON_ACTIVE if button_value == self._calib_ppm else BUTTON_BG
            )
        if self._calib_ppm is None:
            self._var_calib_state.set("Calib: none")
            self._set_status("Calibration gas: none (logged as NaN)")
        else:
            self._var_calib_state.set(f"Calib: {self._calib_ppm} ppm")
            self._set_status(f"Calibration gas: {self._calib_ppm} ppm")

    def _on_toggle_logging(self):
        from co2_logger import CO2LogRecorder

        if self._co2_recorder is None:
            self._co2_log_full = self._new_log_path()
            self._co2_recorder = CO2LogRecorder(
                self._co2_log_full, self.co2_log_window,
                extra_fields=self._log_extra_fields,
                mode=self._var_log_mode.get(),
            )
            self._log_button.config(text="Stop Logging")
            self._var_log_state.set(f"Logging to {self._co2_log_full}…")
            self._set_status(f"CO2 logging started: {self._co2_log_full}")
        else:
            with self._lock:
                self._co2_recorder.emit()
                self._co2_recorder = None
            self._log_button.config(text="Start Logging")
            self._var_log_state.set("Logging: off")
            self._set_status(f"CO2 logging stopped: {self._co2_log_full}")

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
                elif name == "valve_go" and self.valve is not None:
                    self.valve.go(args[0], wait=True)
                elif name == "valve_home" and self.valve is not None:
                    self.valve.home(wait=True)
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
                # Firmware (F48) first wakes the sensor; retry once with a
                # fresh wake if the read fails mid-session.
                try:
                    status["firmware"] = self.sensor.get_firmware()
                    status["pressure"] = self.sensor.get_pressure()
                except Exception as exc:
                    time.sleep(0.2)
                    try:
                        self.sensor.wake()
                        status["firmware"] = self.sensor.get_firmware()
                        status["pressure"] = self.sensor.get_pressure()
                    except Exception as exc2:
                        status["pressure_error"] = str(exc2)
            if self.valve is not None:
                try:
                    status["valve_position"] = self.valve.get_position()
                except Exception as exc:
                    status["valve_error"] = str(exc)
            if self.co2 is not None:
                try:
                    reading = self.co2.get_measurement()
                    status["co2"] = reading["co2"]
                    status["co2_unit"] = reading.get("unit") or "ppm"
                    self._co2_history.append((time.time(), reading["co2"]))
                    if self._co2_recorder is not None:
                        extras = {
                            key: reading[key]
                            for key in self.co2_log_fields
                            if key in reading
                        }
                        mfc_status = status.get("mfc")
                        if mfc_status and mfc_status.get("flow") is not None:
                            extras["mfc_flow"] = mfc_status["flow"]
                        extras["calib_ppm"] = (
                            self._calib_ppm
                            if self._calib_ppm is not None
                            else float("nan")
                        )
                        self._co2_recorder.add(
                            time.time(), reading["co2"], extras
                        )
                except Exception as exc:
                    status["co2_error"] = str(exc)
        return status

    # ------------------------------------------------------------ UI loop

    def _poll(self):
        try:
            while True:
                self._populate(self._queue.get_nowait())
        except Empty:
            pass
        self._maybe_draw_graph()
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
        if "valve_error" in data:
            self._set_status("Valve read failed: " + data["valve_error"])
        if "valve_position" in data:
            position = data["valve_position"]
            self._var_valve_pos.set(
                str(position) if position is not None else "moving…"
            )
        if "co2_error" in data:
            self._set_status("CO2 read failed: " + data["co2_error"])
        if "co2" in data:
            unit = data.get("co2_unit") or "ppm"
            self._var_co2.set(f"{data['co2']:.1f} {unit}")
        if self._co2_recorder is not None:
            count = self._co2_recorder.count
            since = self._co2_recorder.since
            if since is not None:
                if self._co2_recorder.mode == "raw":
                    self._var_log_state.set(
                        f"logging {self._co2_log_full} — {count} rows"
                    )
                else:
                    elapsed = int(time.time() - since)
                    self._var_log_state.set(
                        f"logging {self._co2_log_full} — {count} samples, "
                        f"{elapsed}/{int(self.co2_log_window)} s"
                    )
        if data.get("pump") != self._var_pump.get():
            self._var_pump.set(data["pump"])
            on = data["pump"] == "ON"
            self._pump_status_label.config(fg=PUMP_ON if on else PUMP_OFF)
            self._set_status(f"Pump turned {'ON' if on else 'OFF'}")

    # ------------------------------------------------------------- cleanup

    def close(self):
        self._stop.set()
        self._worker.join(timeout=2)
        if self._co2_recorder is not None:
            with self._lock:
                self._co2_recorder.emit()
            self._co2_recorder = None
        for device, name in (
            (self.pump, "pump"),
            (self.valve, "valve"),
            (self.mfc, "MFC"),
            (self.sensor, "pressure sensor"),
            (self.co2, "CO2 sensor"),
        ):
            if device is not None and hasattr(device, "close"):
                try:
                    device.close()
                except Exception as exc:
                    print(f"Failed to close {name}: {exc}")
        self.root.destroy()