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
        TC ON/OFF   - enable/disable temperature compensation (default ON)
        OC ON/OFF   - enable/disable oxygen compensation (default ON)
        PC ON/OFF   - enable/disable pressure compensation (default ON)
        RHC ON/OFF  - enable/disable relative humidity compensation
        AMODE       - analog output hardware: I (current) or U (voltage)
        ILOW        - current output low level (0..4 mA, default 4)
        UHIGH       - voltage output high level (0..5 V, default 5)
        AERR        - analog output error value
        ALOW/AHIGH  - analog output measurement range (low/high ppm)
        AVERAGE     - averaging filter time (0..60 s, default 10)
        SAVE        - store the current settings in EEPROM

    Main functions:
        get_co2()         - Return latest CO2 reading in ppm
        get_measurement() - Trigger one reading and return a dict
        get_status()      - Same as get_measurement()
        send_command()    - Send any command and return its response
    """

    NUMBER = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+)\s*([a-zA-Z%/]*)") #defines regex extracting a number plus optional unit from a line

    # Abbreviations accepted by the FORM command, mapped to dict keys used
    # in get_measurement() / logging.
    FORM_KEYS = {
        "CO2": "co2",              # filtered CO2
        "CO2RAW": "co2_raw",       # raw CO2
        "CO2RAWUC": "co2_raw_uc",  # uncompensated raw CO2
        "TIME": "time_since_reset",
        "ADDR": "address",
        "ERR": "error_flag",
        "T": "temperature",        # gas temperature
        "P": "pressure_set",       # user-set pressure value
        "RH": "humidity_set",      # user-set relative humidity value
        "O": "oxygen_set",         # user-set oxygen value
    }

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

        self._form = ["CO2"]

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

    def _drain(self, quiet=0.3, cap=4096):
        """Read everything available until the line sits quiet."""
        data = b""
        idle = time.time() + quiet
        while time.time() < idle:
            chunk = self.ser.read(256)
            if chunk:
                data += chunk
                idle = time.time() + quiet
            if len(data) >= cap:
                break
        return (
            data.decode("ascii", errors="replace")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )

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

    @staticmethod
    def _numbers(lines):
        """Extract the numeric values from a SEND response, in order."""
        values = []
        for line in lines:
            stripped = line.strip()
            if stripped in ("SEND", ">", ""):
                continue
            values.extend(float(t) for t in re.findall(r"[-+]?\d*\.?\d+", line))
        return values

    def get_measurement(self):
        """Trigger a single reading with SEND and return the parsed dict.

        The dict always contains 'co2' (the filtered value) and 'unit'.
        If a wider FORM has been set (see set_form), the additional
        quantities are included under their FORM_KEYS names, e.g.
        'co2_raw_uc', 'temperature', 'pressure_set', 'humidity_set',
        'oxygen_set'.
        """
        lines = self.send_command("SEND")
        values = self._numbers(lines)
        if not values:
            raise RuntimeError(
                "GMP343 did not return a reading. Response was: " + repr(lines)
            )
        reading = {}
        for abbreviation, value in zip(self._form, values):
            reading[self.FORM_KEYS.get(abbreviation, abbreviation.lower())] = value
        if "co2" not in reading:
            reading["co2"] = values[0]
        reading["unit"] = "ppm"
        return reading

    def get_co2(self):
        """Return the current CO2 (ppm)"""
        return self.get_measurement()["co2"]

    def get_status(self):
        """Return latest measurement as a dict"""
        return self.get_measurement()

    # ----------------------------------------------------------- quantities

    def calcs(self):
        """List the quantities available for the FORM command (CALCS)."""
        return self.send_command("CALCS")

    def set_form(self, *abbreviations):
        """Set the measurement output format (FORM).

        Pass one or more abbreviations from calcs(), e.g.
        sensor.set_form("CO2", "CO2RAWUC", "T", "P", "RH", "O").
        Persist with save() if it should survive a power cycle.
        """
        tokens = [str(abbreviation).strip().upper() for abbreviation in abbreviations]
        for token in tokens:
            if token not in self.FORM_KEYS:
                raise ValueError(f"Unknown FORM quantity: {token!r}")
        self._form = tokens
        return self.send_command("FORM " + " ".join(tokens))

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
        """Select RS-232 or RS-485 hardware (RSMODE): '232' or '485'."""
        mode = str(mode).strip()
        if mode not in ("232", "485"):
            raise ValueError("RSMODE must be '232' or '485'.")
        return self.send_command(f"RSMODE {mode}")

    def _set_compensation(self, command, enabled):
        """Send a <TC|OC|PC|RHC> ON/OFF command."""
        state = "ON" if enabled else "OFF"
        return self.send_command(f"{command} {state}")

    def set_temperature_compensation(self, enabled):
        """Enable or disable temperature compensation (TC)."""
        return self._set_compensation("TC", enabled)

    def set_oxygen_compensation(self, enabled):
        """Enable or disable oxygen compensation (OC)."""
        return self._set_compensation("OC", enabled)

    def set_pressure_compensation(self, enabled):
        """Enable or disable pressure compensation (PC)."""
        return self._set_compensation("PC", enabled)

    def set_humidity_compensation(self, enabled):
        """Enable or disable relative humidity compensation (RHC)."""
        return self._set_compensation("RHC", enabled)

    def disable_all_compensation(self):
        """Turn off temperature, oxygen, pressure and humidity compensation.

        Use this to capture the rawest CO2 value the sensor can report.
        Re-enable with enable_all_compensation() and persist with save().
        """
        reports = {}
        for command in ("TC", "OC", "PC", "RHC"):
            reports[command] = self._set_compensation(command, False)
        return reports

    def enable_all_compensation(self):
        """Re-enable all compensations (the factory default)."""
        reports = {}
        for command in ("TC", "OC", "PC", "RHC"):
            reports[command] = self._set_compensation(command, True)
        return reports

    def save(self):
        """Store the current settings in EEPROM (SAVE)."""
        return self.send_command("SAVE")

    # ------------------------------------------------------- analog output

    def set_analog_output_mode(self, mode):
        """Choose the analog output hardware (AMODE): 'I' or 'U'."""
        mode = str(mode).strip().upper()
        if mode not in ("I", "U"):
            raise ValueError("AMODE must be 'I' (current) or 'U' (voltage).")
        return self.send_command(f"AMODE {mode}")

    def set_current_low(self, value):
        """Set the current output low level (ILOW): 0..4 mA, default 4."""
        value = float(value)
        if not 0.0 <= value <= 4.0:
            raise ValueError("ILOW must be between 0 and 4 mA.")
        return self.send_command(f"ILOW {value}")

    def set_voltage_high(self, value):
        """Set the voltage output high level (UHIGH): 0..5 V, default 5."""
        value = float(value)
        if not 0.0 <= value <= 5.0:
            raise ValueError("UHIGH must be between 0 and 5 V.")
        return self.send_command(f"UHIGH {value}")

    def set_analog_error(self, value):
        """Set the analog output error value (AERR)."""
        return self.send_command(f"AERR {value}")

    def set_analog_range(self, low, high):
        """Set the analog output measurement range (ALOW/AHIGH in ppm)."""
        return {
            "ALOW": self.send_command(f"ALOW {low}"),
            "AHIGH": self.send_command(f"AHIGH {high}"),
        }

    def set_average(self, seconds):
        """Set the averaging filter time (AVERAGE): 0..60 s, default 10.

        The AVERAGE command is interactive on the GMP343: it prints the
        current value and prompts for a new one, and it wants an integer.
        This sends the bare command, drains the prompt, sends the value,
        and retries if the unit rejects it and re-prompts.
        """
        seconds = int(round(float(seconds)))
        if not 0 <= seconds <= 60:
            raise ValueError("AVERAGE must be between 0 and 60 s.")
        reply = ""
        for _ in range(3):
            self.ser.reset_input_buffer()
            self.ser.write(b"AVERAGE\r")
            self._drain()  # consume 'AVERAGE ... <current> ?' prompt
            self.ser.write(f"{seconds}\r".encode("ascii"))
            reply = self._drain()
            if not reply.endswith("?"):  # accepted (sensor returned '>')
                return reply
        return reply

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