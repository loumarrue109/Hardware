# Sampler Hardware Control

Control software for the sampler rig: a mass flow controller, a 16-port
rotary valve, a pressure sensor, a pump, and a CO2 sensor, driven from a
Raspberry Pi. The normal entry point is a local Tkinter dashboard.

## Architecture

```
config.toml  (data: which hardware is where)
     |
     v
config.py    (loaders: make_valve, make_mfc, ...)
     |
     +---------------------------+----------------------+
     v                           v                      v
device drivers               main.py             tests/
  valve.py                     |  (wiring /      (per-device
  mfc.py                       |   entry point)   smoke tests)
  pressure_sensor.py           v
  pump.py                 dashboard.py
  co2_sensor.py             (GUI, takes devices as inputs)
```

The dependency direction matters:

- **`config.toml`** is plain data (ports, baud rates, valve position
  count, ...). Non-programmers can edit it.
- **`config.py`** reads the TOML and builds configured device objects
  (`make_valve()`, `make_mfc()`, `make_pressure_sensor()`, `make_pump()`,
  `make_co2_sensor()`).
- **Device drivers** (`valve.py`, `mfc.py`, ...) contain the actual
  serial/GPIO logic. Their constructor arguments default to the standard
  rig settings, so a driver is usable standalone; config.toml overrides
  those defaults at startup.
- **`main.py`** is the wiring layer: load config, connect each device
  (tolerating missing ones), hand them to the dashboard, start the GUI.
- **`dashboard.py`** gets device *objects* injected via `__init__`. It
  never constructs hardware and never imports config, so it can run with
  any subset of devices (missing ones get disabled panels) and can be
  tested with fake devices.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point: config -> devices -> dashboard GUI | Note: e.g. The /dev/ttyUSB1 written in Valve.__init__ is only a default that applies when config.toml doesn't override it.
| `dashboard.py` | Tkinter GUI (panels with live values + controls) |
| `config.py` | TOML loaders, one small factory per device |
| `config.toml` | Rig configuration (ports, valve size, safety notes) |
| `valve.py` | `Valve` (VICI EUTA actuator) + `ValveConfig` |
| `mfc.py` | `MFC` (Bronkhorst EL-FLOW Prestige mass flow controller) |
| `pressure_sensor.py` | `Pressure_Sensor` (Keller, Keller protocol) |
| `pump.py` | `Pump` (relay on GPIO17) |
| `co2_sensor.py` | `CO2Sensor` (Vaisala GMP343) |
| `calibration.py` / `calibration.toml` | Calibration workflow (work in progress) |
| `scan_ports.py` | Diagnostic tool: probe ports/baud rates for a silent device |
| `tests/` | Per-device smoke tests (add the repo root to `sys.path` itself) |
| `Notes.md` | Scratch notes |

## Running

```bash
# Dashboard (all attached devices)
python3 main.py

# Per-device links
python3 tests/test_valve.py            # read-only link check
python3 tests/test_valve.py move       # also move the valve (16-port)
python3 tests/test_mfc.py
python3 tests/test_pressure_sensor.py
python3 tests/test_co2.py
python3 tests/test_pump.py
```

Use the project virtualenv so the serial libraries are found:

```bash
source .venv/bin/activate
```

## Device API (quick reference)

| Device | Class | Key methods |
|--------|-------|-------------|
| Valve | `Valve` | `go(pos, wait=)`, `home(wait=)`, `get_position()`, `get_help()`, `apply_config()` |
| MFC | `MFC` | `get_flow()` [ml/min], `get_setpoint()`, `set_flow(ml/min)`, `stop_flow()` |
| Pressure | `Pressure_Sensor` | `get_pressure()` [bar], `get_firmware()`, `wake()` |
| Pump | `Pump` | `on()`, `off()` |
| CO2 | `CO2Sensor` | `get_measurement()`, `get_co2()` [ppm] |

## Configuration model

Settings are resolved as:

1. **Driver default** (written in the class constructor).
2. **config.toml override** (applied by the `make_*` factory).

Example: `Valve()` opens `/dev/ttyUSB1`; if config.toml says
`port = "/dev/ttyUSB9"`, `make_valve()` opens that instead.

## Operationally relevant notes

- **USB numbering can shift** (identical Prolific adapters, hub in play).
  If a device shows "not connected", check `config.toml` — the MFC has
  been on both `ttyUSB0` and `ttyUSB2` depending on plug order. A udev
  rule for stable names (`/dev/sampler-*`) is the long-term fix.
- **Valve config persists in the actuator** (NP16, AM3, SM A, IFM2 live
  on the device); re-apply via `VALVE_CONFIG.apply(valve)` after a
  factory reset (`EE`).
- **MFC setpoint source**: the EL-FLOW can switch to its analog setpoint
  input after a power cycle. `set_flow()` detects this and switches to
  the digital (BUS/RS-232) setpoint automatically.
- **Dashboard threading**: a worker thread does all serial/GPIO reads and
  posts results to `dashboard._queue`; button presses are enqueued in
  `dashboard._actions`. The UI thread never blocks on hardware.