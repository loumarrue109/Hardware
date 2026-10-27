#%%
from pump import Pump
import time


pump = Pump()

try:
    print("Turning pump ON...")
    pump.on()

    time.sleep(5) 

    print("Turning pump OFF...")
    pump.off()

finally:
    pump.close()
    print("Done.")

# %%
