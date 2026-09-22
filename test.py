#%%
import serial
from keller_protocol import keller_protocol as kp

#%%
ser = serial.Serial(
    port="/dev/ttySC0",
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.5
)

print("Port geöffnet:", ser.is_open)

ser.close()

# %%
bus = kp.KellerProtocol(
    port="/dev/ttySC0",
    baud_rate=9600,
    timeout=0.5,
    echo=False
)

print(bus.f48(1))

#%%
for address in range(1, 32):
    try:
        firmware = bus.f48(address)
        print(f"✅ Gerät gefunden: Adresse {address}, Firmware: {firmware}")
    except Exception as e:
        print(f"Adresse {address}: keine Antwort")
# %%
