#%%
import numpy as np

#%% Calibrate Keller Sensor - Using Linear Regression
keller = np.array([0.12, 2.13, 5.10, 8.09])
reference = np.array([0.0, 2.0, 5.0, 8.0])

slope, offset = np.polyfit(keller, reference, 1)

print("slope:", slope)
print("offset:", offset)
