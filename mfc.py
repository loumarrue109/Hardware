#%%
import propar


class MFC:
    """
    Interface for the EL FLOW Prestige FG201CV Mass Flow Controller.

    Communicates via ProPar over RS232/USB at 38400 baud.
    The current MFC is configured for 0–1000 mln/min.

    Main functions:
        get_serial()      - Read the MFC serial number.
        get_flow()        - Read the current measured flow.
        get_setpoint()   - Read the current flow setpoint.
        get_capacity()   - Read the configured maximum capacity.
        get_unit()        - Read the configured flow unit.
        set_flow(flow)    - Set the desired flow.
        stop_flow()       - Set the flow setpoint to zero.
        get_status()      - Return the current MFC status.
    """
    def __init__(
        self,
        port="/dev/ttyUSB0",
        address=128,
        channel=1,
        baudrate=38400,
    ):
        self.port = port
        self.address = address
        self.channel = channel
        self.baudrate = baudrate

        self.instrument = propar.instrument(
            self.port,
            address=self.address,
            baudrate=self.baudrate,
            channel=self.channel,
        )

        self.capacity = 1000.0
        self.unit = "mln/min"

    def get_serial(self):
        serial = self.instrument.readParameter(1)
        return serial.strip("\x07")

    def get_flow(self):
        return self.instrument.read(1, 0, 34)

    def get_setpoint(self):
        return self.instrument.read(33, 3, 65)

    def get_capacity(self):
        return self.instrument.read(1, 13, 65)

    def get_unit(self):
        return self.instrument.read(1, 31, 96)

    def set_flow(self, flow):
        if flow < 0:
            raise ValueError("Flow cannot be negative.")

        if flow > self.capacity:
            raise ValueError(
                f"Flow {flow} exceeds MFC capacity "
                f"of {self.capacity} {self.unit}."
            )

        success = self.instrument.write(33, 3, 65, float(flow))

        if not success:
            raise RuntimeError("Failed to write flow setpoint.")

        return self.get_setpoint()

    def stop_flow(self):
        return self.set_flow(0)

    def get_status(self):
        return {
            "serial": self.get_serial(),
            "flow": self.get_flow(),
            "setpoint": self.get_setpoint(),
            "capacity": self.get_capacity(),
            "unit": self.get_unit(),
        }

if __name__ == "__main__":
    mfc = MFC()




# %%
