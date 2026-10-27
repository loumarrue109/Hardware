#%%
import importlib
import mfc

importlib.reload(mfc)

controller = mfc.MFC()

print("Serial:", controller.get_serial())
print("Flow:", controller.get_flow())
print("Setpoint:", controller.get_setpoint())

result = controller.set_flow(10)

print("New setpoint:", result)
print("Measured flow:", controller.get_flow())

controller.stop_flow()

print("Setpoint:", controller.get_setpoint())
print("Flow:", controller.get_flow())
print("Status:", controller.get_status())

# %%