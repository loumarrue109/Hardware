#%%
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pressure_sensor import Pressure_Sensor

keller = Pressure_Sensor()

print("Firmware:", keller.get_firmware())
print("Pressure:", keller.get_pressure())
print("Status:", keller.get_status())

# %%
