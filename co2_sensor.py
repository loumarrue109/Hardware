#%%
import re
import time
import serial


class CO2Sensor:
    """
    Vaisala GMP343 (flow-through) CO2 sensor

        SEND        - output one measurement (works in STOP and POLL mode)
        R / S       - start / stop continuous measurement output
        INTV        - set the output interval
        FORM        - configure the measurement output format
        SMODE       - configure STOP / RUN / POLL measurement mode
        RSMODE      - select RS-232 (232) or RS-485 (485) hardware
        SERI        - configure serial communication parameters (baud, ...)

    Main functions:
        get_co2()         - Return latest CO2 reading in ppm
        get_measurement() - Trigger one reading and return a dict
        get_status()      - Same as get_measurement()
        send_command()    - Send any command and return its response
    """

    NUMBER = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+)\s*([a-zA-Z%/]*)") #defines regex extracting a number plus optional unit from a line

    def __init__(
        self,
        port="/dev/ttyUSB0",
        baudrate=19200,
        bytesize=8,
        parity=serial.PARITY_NONE,
        stopbits=1,
        timeout=2.0,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            xonxoff=xonxoff,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
        )

    # ------------------------------------------------------------ helpers

    def _readline(self, timeout=None):
        old_timeout = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout
        data = b""
        try:
            while True:
                char = self.ser.read(1)
                if not char or char == b"\n":
                    break
                data += char
        finally:
            self.ser.timeout = old_timeout
        return data.decode("utf-8", errors="replace").replace("\r", "").strip()

    def send_command(self, command, timeout=None):
        """Send any command (CR-terminated) and collect the response lines.

        Returns the lines up to the next command prompt ('>').
        """
        self.ser.reset_input_buffer()
        self.ser.write(command.strip().encode("ascii") + b"\r")
        lines = []
        deadline = time.time() + (timeout if timeout is not None else self.timeout)
        while time.time() < deadline:
            line = self._readline(timeout=0.3)
            if not line:
                break
            lines.append(line)
            if line.strip() == ">":
                break
        return lines

    # ------------------------------------------------------------ parsing

    @staticmethod
    def parse_response(lines):
        """Extract '<value> <unit>' lines into a dict.

        Returns {'co2': <float or None>, 'unit': <str or None>}.
        """
        result = {"co2": None, "unit": None}
        for line in lines:
            match = CO2Sensor.NUMBER.match(line)
            if match:
                value = float(match.group(1))
                if result["co2"] is None:
                    result["co2"] = value
                    result["unit"] = (match.group(2) or "ppm").strip()
        return result

    # ------------------------------------------------------- measurements

    def get_measurement(self):
        """Trigger a single reading with SEND and return the parsed dict."""
        lines = self.send_command("SEND")
        reading = self.parse_response(lines)
        if reading["co2"] is None:
            raise RuntimeError(
                "GMP343 did not return a reading. Response was: " + repr(lines)
            )
        return reading

    def get_co2(self):
        """Return the current CO2 (ppm)"""
        return self.get_measurement()["co2"]

    def get_status(self):
        """Return latest measurement as a dict"""
        return self.get_measurement()

    # ------------------------------------------------------------ control

    def start_output(self, interval=None):
        """Start continuous output (R command), optionally set the interval."""
        if interval is not None:
            self.set_interval(interval)
        return self.send_command("R")

    def stop_output(self):
        """Stop continuous output (S command)."""
        return self.send_command("S")

    def set_interval(self, value, unit="s"):
        """Set continuous output interval (INTV): value + s/min/h."""
        return self.send_command(f"INTV {value} {unit}")

    def set_mode(self, mode):
        """Set measurement mode (SMODE): STOP, RUN or POLL."""
        mode = str(mode).upper()
        if mode not in ("STOP", "RUN", "POLL"):
            raise ValueError("Mode must be STOP, RUN or POLL.")
        return self.send_command(f"SMODE {mode}")

    def set_serial_mode(self, mode):
        """Select (RS-)232 or (RS-)485"""
        mode = str(mode).strip()
        if mode not in ("232", "485"):
            raise ValueError("RSMODE must be '232' or '485'.")
        return self.send_command(f"RSMODE {mode}")

    def set_serial_parameters(self, expr):
        """SERI command to configure serial parameters (baud, ...).

        expr is the parameter string (see the manual)
        in the summary.
        """
        return self.send_command(f"SERI {expr}")

    def configure_format(self, expr):
        """FORM command to set the measurement output format

        expr is the format string
        """
        return self.send_command(f"FORM {expr}")

    def command_help(self):
        """Request command list (help)"""
        return self.send_command("?")

    # ---------------------------------------------------------------- misc

    def close(self):
        """Close serial port"""
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


# %%


if __name__ == "__main__":
    with CO2Sensor() as sensor:
        print("Port opened:", sensor.ser.is_open)
        try:
            print("Measurement:", sensor.get_measurement())
            print("CO2 (ppm):", sensor.get_co2())
        except RuntimeError as exc:
            print("No reading returned:", exc)

# %%