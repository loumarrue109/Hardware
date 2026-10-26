#%%
import time
import serial

class Valve:
    """
    Interface for the VICI EUTA RS-232 valve actuator.

    Communicates over a serial port (default /dev/ttyUSB1 at 9600 baud)
    using the EUTA command set. Each command is terminated with a
    carriage return.

    Main functions:
        go(position)           - Move to an absolute position.
        home()                 - Move to the first position.
        clockwise(position)    - Move clockwise to a position.
        counterclockwise(position) - Move counter-clockwise to a position.
        toggle()               - Toggle to the opposite position.
        toggle_timed()         - Start a timed toggle.
        set_delay(ms)          - Set the delay time for the TT command.
        get_position()         - Read the current position.
        set_mode(mode)         - Set actuator mode (1, 2 or 3).
        set_baudrate(baud)     - Set the serial baud rate.
        set_device_id(dev_id)  - Set the device ID (0-9, A-Z).
        reset_device_id()      - Clear the device ID.
        set_num_positions(n)   - Set the number of positions.
        set_direction(d)       - Set the move direction (F, R or A).
        learn_stops()          - Run the stop learning routine.
        set_cycle_counter(n)   - Set the cycle counter.
        get_firmware()         - Read the firmware version(s).
        get_help()             - Request the command list.
    """

    MODES = (1, 2, 3)
    DIRECTIONS = ("F", "R", "A")
    BAUD_RATES = (300, 1200, 2400, 4800, 9600, 19200, 38400)
    ID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, port="/dev/ttyUSB1", baudrate=9600, timeout=2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

    # ------------------------------------------------------------ helpers

    def _write(self, command):
        self.ser.reset_input_buffer()
        payload = command.strip() + "\r"
        self.ser.write(payload.encode("ascii"))

    def _readline(self, timeout=None):
        old_timeout = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout
        line = b""
        try:
            while True:
                char = self.ser.read(1)
                if not char or char in (b"\r", b"\n"):
                    break
                line += char
        finally:
            self.ser.timeout = old_timeout
        return line.decode("ascii", errors="replace").strip()

    def send(self, command, timeout=None):
        """
        Send a command and return the first non-empty response line.

        Commands that produce no response return an empty string.
        A second line is read only if more data is already buffered
        (multi-line responses such as VR).
        """
        self._write(command)
        for _ in range(2):
            response = self._readline(timeout=timeout)
            if response or self.ser.in_waiting == 0:
                return response
        return response

    def _move(self, command, position):
        position = int(position)
        if position < 1 or position > 99:
            raise ValueError("Position must be between 1 and 99.")
        return self.send(f"{command}{position:02d}")

    # ------------------------------------------------------- basic controls

    def go(self, position):
        """Move to an absolute position."""
        return self._move("GO", position)

    def home(self):
        """Move to the first position."""
        return self.send("HM")

    def clockwise(self, position):
        """Move clockwise to a position."""
        return self._move("CW", position)

    def counterclockwise(self, position):
        """Move counter-clockwise to a position."""
        return self._move("CC", position)

    def toggle(self):
        """Toggle to the opposite position."""
        return self.send("TO")

    def toggle_timed(self):
        """Start a timed toggle using the delay set by set_delay()."""
        return self.send("TT")

    def set_delay(self, milliseconds):
        """Set the delay time in ms for the TT command (0-99999)."""
        milliseconds = int(milliseconds)
        if milliseconds < 0 or milliseconds > 99999:
            raise ValueError("Delay must be between 0 and 99999 ms.")
        return self.send(f"DT{milliseconds:05d}")

    # ----------------------------------------------------------- status / id

    def get_position(self):
        """Read the current position as an int (None if unavailable)."""
        response = self.send("CP")
        position = "".join(ch for ch in response if ch.isdigit())
        return int(position) if position else None

    def set_mode(self, mode):
        """
        Set the actuator mode:
            1 = two positions with stops,
            2 = two positions without stops,
            3 = multi position.
        """
        mode = int(mode)
        if mode not in self.MODES:
            raise ValueError(f"Mode must be one of {self.MODES}.")
        return self.send(f"AM{mode}")

    def set_baudrate(self, baudrate):
        """Set the serial baud rate on the actuator."""
        baudrate = int(baudrate)
        if baudrate not in self.BAUD_RATES:
            raise ValueError(f"Baud rate must be one of {self.BAUD_RATES}.")
        return self.send(f"SB{baudrate}")

    def set_device_id(self, device_id):
        """Set the device ID (0-9 or A-Z)."""
        device_id = str(device_id).upper()
        if len(device_id) != 1 or device_id not in self.ID_CHARS:
            raise ValueError("Device ID must be a single digit (0-9) or letter (A-Z).")
        return self.send(f"ID{device_id}")

    def reset_device_id(self):
        """Reset the device ID to none."""
        return self.send("*ID*")

    def set_num_positions(self, number):
        """Set the number of positions (1-99)."""
        number = int(number)
        if number < 1 or number > 99:
            raise ValueError("Number of positions must be between 1 and 99.")
        return self.send(f"NP{number:02d}")

    def set_direction(self, direction):
        """Set the move direction: F = forward, R = reverse, A = auto."""
        direction = str(direction).upper()
        if direction not in self.DIRECTIONS:
            raise ValueError(f"Direction must be one of {self.DIRECTIONS}.")
        return self.send(f"SM{direction}")

    def learn_stops(self):
        """Run the stop location learning routine."""
        return self.send("LRN", timeout=30)

    def set_cycle_counter(self, count):
        """Set the cycle counter (0-99999)."""
        count = int(count)
        if count < 0 or count > 99999:
            raise ValueError("Cycle counter must be between 0 and 99999.")
        return self.send(f"CNT{count:05d}")

    def get_firmware(self):
        """Read the firmware version(s)."""
        return self.send("VR")

    def get_help(self):
        """Request the command list and read the full multi-line response."""
        self._write("/?")
        lines = []
        idle = time.time() + 0.5
        while time.time() < idle:
            line = self._readline(timeout=0.2)
            if line:
                lines.append(line)
                idle = time.time() + 0.5
            elif len(lines) >= 40:
                break
        return "\n".join(lines)

    def close(self):
        """Close the serial port."""
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

