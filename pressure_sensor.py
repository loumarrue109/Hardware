import keller_protocol.keller_protocol as kp


class Pressure_Sensor:
    """
    Interface for a Keller pressure sensor.
    """

    def __init__(
        self,
        port="/dev/ttySC0",
        address=1,
        channel=1,
        baud_rate=9600,
        timeout=0.5,
        echo=False,
        calibration_slope=1.0,
        calibration_offset=0.0,
    ):
        self.port = port
        self.address = address
        self.channel = channel
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.echo = echo

        self.pressure_unit = "bar"

        # Calibration
        self.calibration_slope = calibration_slope
        self.calibration_offset = calibration_offset

        self.bus = kp.KellerProtocol(
            port=self.port,
            baud_rate=self.baud_rate,
            timeout=self.timeout,
            echo=self.echo,
        )

    def get_firmware(self):
        return self.bus.f48(self.address)

    def get_pressure(self):
        """Return the raw pressure from the Keller."""
        return self.bus.f73(
            self.address,
            self.channel
        )

    def get_calibrated_pressure(self):
        """Return the pressure after applying calibration."""
        raw_pressure = self.get_pressure()

        return (
            self.calibration_slope * raw_pressure
            + self.calibration_offset
        )

    def get_status(self):
        return {
            "firmware": self.get_firmware(),
            "pressure": self.get_calibrated_pressure(),
            "unit": self.pressure_unit,
        }
