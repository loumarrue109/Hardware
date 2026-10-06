#%%
import serial

ser = serial.Serial(
    port="/dev/ttyUSB1",
    baudrate=9600,
    bytesize=8,
    parity=serial.PARITY_NONE,
    stopbits=1,
    timeout=2,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False
)

print("Port opened:", ser.is_open)

# Ask the EUTA for its command/help information
ser.write(b"/?\r")

response = ser.read(500)

print("Raw response:", repr(response))
print("Decoded response:")
print(response.decode(errors="replace"))

ser.close()

