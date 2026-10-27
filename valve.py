#%%
import time

import serial


class ValveConfig:
    """
    Intended configuration for the EUTA actuator, as a single object.

    Only the fields you set are sent to the valve (None skips the
    command), so a partial config can update just one thing:

        ValveConfig(num_positions=16).apply(valve)

    Warning: setting baudrate changes the link speed immediately; the
    host must follow at the new speed or the valve becomes unreachable.
    """

    FIELDS = (
        ("mode", "set_mode"),
        ("direction", "set_direction"),
        ("response_mode", "set_response_mode"),
        ("legacy_response", "set_legacy_response"),
        ("baudrate", "set_baudrate"),
        ("device_id", "set_device_id"),
        ("num_positions", "set_num_positions"),
        ("offset", "set_offset"),
        ("high_speed", "set_high_speed"),
        ("cycle_counter", "set_cycle_counter"),
    )

    def __init__(
        self,
        mode=None,
        direction=None,
        response_mode=None,
        legacy_response=None,
        baudrate=None,
        device_id=None,
        num_positions=None,
        offset=None,
        high_speed=None,
        cycle_counter=None,
    ):
        self.mode = mode
        self.direction = direction
        self.response_mode = response_mode
        self.legacy_response = legacy_response
        self.baudrate = baudrate
        self.device_id = device_id
        self.num_positions = num_positions
        self.offset = offset
        self.high_speed = high_speed
        self.cycle_counter = cycle_counter

    def apply(self, valve, save=False):
        """
        Push every set field to the valve and report each reply.

        Returns a dict {field_name: actuator_response}. Pass save=True
        to also store the new configuration as the backup (WP).
        """
        reports = {}
        for field, method in self.FIELDS:
            value = getattr(self, field)
            if value is None:
                continue
            reports[field] = getattr(valve, method)(value)
        if save:
            valve.save_config()
        return reports

class Valve:
    """
    Interface for the VICI EUTA valve actuator (firmware MUA_MAIN_ST_2.56).

    Communicates over a serial port (default /dev/ttyUSB1 at 9600 baud)
    using the EUTA command set. Commands are terminated with CR, responses
    are CR terminated (multi-line responses separated by LF CR).

    Command list (from 'VICI_MU_Actuator_User_Manual_V2'):
        AL         - Move valve to index
        AM[n]      - Valve type: [1] 2 POS w/STOPS, [2] 2 POS wo/STOPS,
                     [3] MULTIPOS
        CC[nn]     - Move Counter Clockwise to position [nn]
        CNT[nnnnn] - Cycle Counter [nnnnn]
        CP         - Current Position
        CW[nn]     - Clockwise to position [nn]
        GO[nn]     - Move to position [nn]
        HM         - Move to position 1
        ID[c/n]    - Set device ID (A-Z, 0-9); *ID* clears all on line
        IFM[n]     - Response Mode: None[0], Limited[1], Extended[2]
        LG[n]      - Legacy Response Mode: OFF[0], ON[1]
        NP[nn]     - Number of Positions [nn]
        SB[nnnnn]  - Set the Baud Rate to [nnnnn]
        SM[c]      - Set the Direction [F]orward, [R]everse, [A]uto
        SO[nn]     - Set Valve Port Numbering to start at offset [nn]
        TM         - Returns the time of the last move in milliSec
        VR[n]      - Firmware Version: Main[], Interface Module[2]
        AK         - Always responds with MUA
        HS[n]      - Set High Speed Mode [1] Enabled, [0] Disabled
        WP         - Set Current Configuration as backup restore
        EE         - Erase backup configuration and use Factory Defaults
        ?          - Displays This List

    Main functions:
        go(position)            - Move to an absolute position.
        home()                  - Move to the first position.
        clockwise(position)     - Move clockwise to a position.
        counterclockwise(position) - Move counter-clockwise to a position.
        move_to_index()         - Move the valve to the index position.
        get_position()          - Read the current position.
        get_last_move_time()    - Read the duration of the last move.
        get_firmware()          - Read the firmware version.
        get_help()              - Request the command list.
        ping()                  - Link test (always replies "MUA").
        set_mode(mode)          - Set the valve type (1, 2 or 3).
        set_response_mode(mode) - Set response mode (0, 1 or 2).
        set_legacy_response(on) - Toggle legacy response mode.
        set_baudrate(baud)      - Set the serial baud rate.
        set_device_id(dev_id)   - Set the device ID (0-9, A-Z).
        reset_device_id()       - Clear all device IDs on the line.
        set_num_positions(n)    - Set the number of positions.
        set_offset(offset)      - Start valve port numbering at an offset.
        set_direction(d)        - Set the move direction (F, R or A).
        set_high_speed(on)      - Toggle high speed mode.
        set_cycle_counter(n)    - Set the cycle counter.
        save_config()           - Back up current configuration (WP).
        restore_factory()       - Restore factory defaults (EE).
    """

    MODES = (1, 2, 3)
    DIRECTIONS = ("F", "R", "A")
    RESPONSE_MODES = (0, 1, 2)
    BAUD_RATES = (300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200)
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
        self.ser.write(command.strip().encode("ascii") + b"\r")

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
        Send a command and return the full response text.

        All incoming bytes are collected until the line sits quiet, so
        multi-line responses (VR, ?) are fully consumed and no stale data
        leaks into the next command. Returns '' if nothing came back.
        """
        timeout = timeout if timeout is not None else self.timeout
        self._write(command)

        deadline = time.time() + timeout + 0.2
        idle = time.time() + 0.05
        data = b""
        while time.time() < deadline:
            self.ser.timeout = min(0.1, max(0.01, deadline - time.time()))
            chunk = self.ser.read(256)
            if not chunk:
                if data and time.time() >= idle:
                    break
                continue
            data += chunk
            idle = max(idle, time.time() + 0.05)

        self.ser.timeout = self.timeout
        if not data:
            return ""
        return (
            data.decode("ascii", errors="replace")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )

    def _move(self, command, position):
        position = int(position)
        if position < 1 or position > 99:
            raise ValueError("Position must be between 1 and 99.")
        return self.send(f"{command}{position:02d}", timeout=30)

    # ------------------------------------------------------- basic controls

    def _wait_position(self, target, timeout=30.0, interval=0.25):
        """
        Poll CP until the valve reports the target position.

        Returns True on success, False if the position never settled.
        """
        deadline = time.time() + timeout
        last = None
        stable = 0
        while time.time() < deadline:
            position = self.get_position()
            if position == target:
                return True
            if position is not None and position == last:
                stable += 1
                if stable >= 4:
                    return False
            else:
                stable = 0
            last = position
            time.sleep(interval)
        return False

    def go(self, position, wait=False):
        """Move to an absolute position."""
        response = self._move("GO", position)
        if wait:
            self._wait_position(int(position))
        return response

    def home(self, wait=False):
        """Move to the first position."""
        response = self.send("HM", timeout=30)
        if wait:
            self._wait_position(1)
        return response

    def clockwise(self, position, wait=False):
        """Move clockwise to a position."""
        response = self._move("CW", position)
        if wait:
            self._wait_position(int(position))
        return response

    def counterclockwise(self, position, wait=False):
        """Move counter-clockwise to a position."""
        response = self._move("CC", position)
        if wait:
            self._wait_position(int(position))
        return response

    def move_to_index(self, wait=False):
        """Move the valve to its index position."""
        response = self.send("AL", timeout=30)
        if wait:
            self._wait_position(0)
        return response

    # ---------------------------------------------------------- status / id

    def get_position(self):
        """Read the current position as an int (None if unavailable)."""
        response = self.send("CP")
        position = "".join(ch for ch in response if ch.isdigit())
        return int(position) if position else None

    def get_last_move_time(self):
        """Read the duration of the last move in milliseconds."""
        response = self.send("TM")
        ms = "".join(ch for ch in response if ch.isdigit())
        return int(ms) if ms else None

    def get_firmware(self):
        """Read the firmware version(s)."""
        return self.send("VR", timeout=5)

    def ping(self):
        """Link test; the actuator always responds with 'MUA'."""
        return self.send("AK")

    def get_help(self):
        """Request the command list and read the full multi-line response."""
        self._write("?")
        lines = []
        idle = time.time() + 0.5
        while time.time() < idle:
            line = self._readline(timeout=0.2)
            if line:
                lines.append(line)
                idle = time.time() + 0.5
            elif len(lines) >= 30:
                break
        return "\n".join(lines)

    # -------------------------------------------------------- configuration

    def set_mode(self, mode):
        """
        Set the valve type:
            1 = two positions with stops,
            2 = two positions without stops,
            3 = multi position.
        """
        mode = int(mode)
        if mode not in self.MODES:
            raise ValueError(f"Mode must be one of {self.MODES}.")
        return self.send(f"AM{mode}")

    def set_response_mode(self, mode):
        """
        Set the response mode:
            0 = none (no replies to commands),
            1 = limited,
            2 = extended (full replies).
        """
        mode = int(mode)
        if mode not in self.RESPONSE_MODES:
            raise ValueError(f"Response mode must be one of {self.RESPONSE_MODES}.")
        return self.send(f"IFM{mode}")

    def set_legacy_response(self, enabled):
        """Toggle legacy response mode (LG): ON[1] / OFF[0]."""
        return self.send(f"LG{1 if enabled else 0}")

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
        """Reset the device ID to none (clears all devices on the line)."""
        return self.send("*ID*")

    def set_num_positions(self, number):
        """Set the number of positions (1-99)."""
        number = int(number)
        if number < 1 or number > 99:
            raise ValueError("Number of positions must be between 1 and 99.")
        return self.send(f"NP{number:02d}")

    def set_offset(self, offset):
        """Set the valve port numbering to start at this offset (0-99)."""
        offset = int(offset)
        if offset < 0 or offset > 99:
            raise ValueError("Offset must be between 0 and 99.")
        return self.send(f"SO{offset:02d}")

    def set_direction(self, direction):
        """Set the move direction: F = forward, R = reverse, A = auto."""
        direction = str(direction).upper()
        if direction not in self.DIRECTIONS:
            raise ValueError(f"Direction must be one of {self.DIRECTIONS}.")
        return self.send(f"SM{direction}")

    def set_high_speed(self, enabled):
        """Toggle high speed mode (HS): ON[1] / OFF[0]."""
        return self.send(f"HS{1 if enabled else 0}")

    def set_cycle_counter(self, count):
        """Set the cycle counter (0-99999)."""
        count = int(count)
        if count < 0 or count > 99999:
            raise ValueError("Cycle counter must be between 0 and 99999.")
        return self.send(f"CNT{count:05d}")

    def save_config(self):
        """Save the current configuration as the backup (WP)."""
        return self.send("WP")

    def restore_factory(self):
        """Erase the backup configuration and restore factory defaults (EE)."""
        return self.send("EE")

    # ---------------------------------------------------------------- misc

    def apply_config(self, config, save=False):
        """
        Push a ValveConfig (or dict of field->value) to the actuator.

        Returns the per-field replies from ValveConfig.apply().
        """
        if not isinstance(config, ValveConfig):
            config = ValveConfig(**config)
        return config.apply(self, save=save)

    def close(self):
        """Close the serial port."""
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

