#%%
from gpiozero import OutputDevice


class Pump:
    """
    Controls a pump connected to a Crydom D2410 solid-state relay.

    The relay is controlled via GPIO17 (physical pin 11) of the
    Raspberry Pi. The pump must have its own power supply.

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
