#%%
from gpiozero import OutputDevice


class Pump:
    """
    KNF N86 pump connected to Crydom D2410 solid-state relay

    Relay controlled by GPIO17 (physical pin 11).
    Pump has own power supply.

    Methods:
        on(): Turn the pump on.
        off(): Turn the pump off.
        close(): Release the GPIO resource.
    """

    def __init__(self, pin=17):
        self._relay = OutputDevice(
            pin,
            active_high=True,
            initial_value=False
        )

    def on(self):
        self._relay.on()

    def off(self):
        self._relay.off()

    def close(self):
        self._relay.close()

# %%
