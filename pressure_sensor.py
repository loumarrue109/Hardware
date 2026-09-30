#%%
import keller_protocol.keller_protocol as kp


class Pressure_Sensor:
    """
    Interface for a Keller pressure sensor.

    Communicates via the Keller protocol over /dev/ttySC0
    at 9600 baud.

    Main functions:'
        get_firmware()  - Read the sensor firmware.
        get_pressure()  - Read the current pressure.
        get_status()    - Return the current sensor status.
    """

    def __init__(
        self,
        port="/dev/ttySC0",
        address=1,
        channel=1,
        baud_rate=9600,
        timeout=0.5,
        echo=False,
    ):
        self.port = port
        self.address = address
        self.channel = channel
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.echo = echo

        self.pressure_unit = "bar"

        self.bus = kp.KellerProtocol(
            port=self.port,
            baud_rate=self.baud_rate,
            timeout=self.timeout,
            echo=self.echo,
        )

    def get_firmware(self):
        return self.bus.f48(self.address)

    def get_pressure(self):
        return self.bus.f73(
            self.address,
            self.channel
        )

    def get_status(self):
        return {
            "firmware": self.get_firmware(),
            "pressure": self.get_pressure(),
            "unit": self.pressure_unit,
        }


# %%
