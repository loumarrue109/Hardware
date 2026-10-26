#%%
# Probe serial ports / baud rates to find the VICI EUTA actuator.
# Sends '/?\r' and 'VR\r' and prints anything that comes back, as
# hex and ASCII, so we can spot a mismatch (port/baud/cable).

import time

import serial

PORTS = ["/dev/ttyUSB0", "/dev/ttyUSB1"]
BAUD_RATES = [300, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200]
COMMANDS = [b"/?\r", b"VR\r", b"CP\r"]


def try_port(port, baud, command, read_time=0.6):
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=0.1,
        )
    except serial.SerialException as exc:
        return None, str(exc)

    response = b""
    try:
        ser.reset_input_buffer()
        ser.write(command)
        deadline = time.time() + read_time
        while time.time() < deadline:
            chunk = ser.read(64)
            if not chunk:
                continue
            response += chunk
            deadline = time.time() + read_time  # keep reading while data flows
    finally:
        ser.close()

    if response:
        try:
            ascii_text = response.decode("ascii", errors="replace")
        except Exception:
            ascii_text = ""
        return response, ascii_text
    return b"", ""


def main():
    hit = False
    for port in PORTS:
        for baud in BAUD_RATES:
            for command in COMMANDS:
                raw, text = try_port(port, baud, command)
                if not raw:
                    continue
                hit = True
                print(f"RESPONSE  {port}  {baud} baud  cmd={command!r}")
                print(f"    hex:   {raw.hex(' ')}")
                print(f"    ascii: {text!r}")
                print()
    if not hit:
        print("No response from any port/baud combination.")
        print("Check that the actuator is powered and wired to an adapter.")
    else:
        print("Done. Match found above; use that port + baud rate.")


if __name__ == "__main__":
    main()

# %%