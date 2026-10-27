"""Load rig configuration from config.toml.

Example:
    from config import make_valve
    valve, valve_config = make_valve()
    valve_config.apply(valve)
"""

import tomllib
from pathlib import Path

from valve import Valve, ValveConfig

_CONFIG_PATH = Path(__file__).with_name("config.toml")


def load_config(path=_CONFIG_PATH):
    """Read the TOML file and return its parsed contents (a dict)."""
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def load_valve_config(path=_CONFIG_PATH):
    """Return a ValveConfig built from the ``[valve]`` section."""
    return ValveConfig(**load_config(path).get("valve", {}))


def make_valve(path=_CONFIG_PATH):
    """Open a Valve from the ``[serial]`` + ``[valve]`` sections.

    Returns (valve, ValveConfig). The valve is open and ready to use.
    """
    data = load_config(path)
    valve = Valve(**data.get("serial", {}))
    config = ValveConfig(**data.get("valve", {}))
    return valve, config


def make_mfc(path=_CONFIG_PATH):
    """Open an MFC from the ``[mfc]`` section."""
    from mfc import MFC
    return MFC(**load_config(path).get("mfc", {}))


def make_pressure_sensor(path=_CONFIG_PATH):
    """Open a Pressure_Sensor from the ``[pressure_sensor]`` section."""
    from pressure_sensor import Pressure_Sensor
    return Pressure_Sensor(**load_config(path).get("pressure_sensor", {}))


def make_pump(path=_CONFIG_PATH):
    """Create a Pump from the ``[pump]`` section."""
    from pump import Pump
    return Pump(**load_config(path).get("pump", {}))