#%%
import numpy as np

#%% Calibrate Keller Sensor - Using Linear Regression
keller = np.array([0.00, 1.013])
reference = np.array([1.013, 942])

slope, offset = np.polyfit(keller, reference, 1)

print("slope:", slope)
print("offset:", offset)
