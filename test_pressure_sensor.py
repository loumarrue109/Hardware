#%%
from pressure_sensor import Pressure_Sensor

keller = Pressure_Sensor()

print("Firmware:", keller.get_firmware())
print("Pressure:", keller.get_pressure())
print("Status:", keller.get_status())

# %%
