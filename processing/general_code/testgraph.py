import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# --------------------------------
# Edit this path to select the CSV
# --------------------------------

csv_path = Path("./spike_train_output/st_1/20_hz/trial_1.csv")


# --------------------------------
# Load CSV
# --------------------------------
# The generated files contain metadata lines beginning with "#",
# so pandas skips those automatically.

data = pd.read_csv(csv_path, comment="#")


# --------------------------------
# Basic validation
# --------------------------------

required_columns = {"time_s", "voltage_v"}

if not required_columns.issubset(data.columns):
    raise ValueError(
        f"CSV must contain columns {required_columns}, "
        f"but found {set(data.columns)}"
    )


# --------------------------------
# Plot spike train
# --------------------------------

plt.figure(figsize=(10, 4))
plt.plot(data["time_s"], data["voltage_v"])

plt.xlabel("Time [s]")
plt.ylabel("Voltage [V]")
plt.title(f"Spike Train: {csv_path}")
plt.grid(True)

plt.tight_layout()
plt.show()