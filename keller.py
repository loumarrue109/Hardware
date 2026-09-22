#%%
import keller_protocol.keller_protocol as kp
import time

#.json schreiben zum Kalibrieren mit einem linearen Fit falls der Sensor driftet!
#%%
bus = kp.KellerProtocol(
    port="/dev/ttySC0",
    baud_rate=9600,
    timeout=0.5,
    echo=False
)

#%%
address = 1

# F48 – Firmware
print("Firmware:", bus.f48(address))

# F73 – Druck Kanal 1
pressure = bus.f73(address, 1)
print("Druck:", bus.f73(address, 1))


# %%
