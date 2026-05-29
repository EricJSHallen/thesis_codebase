import numpy as np
import matplotlib.pyplot as plt


# -----------------------------
# User variables
# -----------------------------

output_file = "./voltage_pulses.pwl"

total_time = 0.01          # seconds; 0.01 s = 10 ms
pulse_rate = 5000          # average pulse attempts per second
pulse_height = 1.8         # volts

pulse_width = 100e-6       # seconds; 100 microseconds
refractory_fraction = 0.5  # refractory period = 1/2 pulse width

rise_time = 1e-8           # seconds; finite rising edge for Cadence/Spectre PWL
fall_time = 1e-8           # seconds; finite falling edge for Cadence/Spectre PWL

plot_time_unit = "us"      # options: "s", "ms", "us", "ns"


# -----------------------------
# Pulse-width function
# -----------------------------

def get_pulse_width():
    """ 
    Replace this later with your own pulse-width function.

    Example Poisson-distributed width idea:

        mean_width = 100e-6
        time_step = 1e-6
        width_steps = np.random.poisson(lam=mean_width / time_step)
        return width_steps * time_step

    For now, this simply returns the fixed pulse_width variable.
    """
    return pulse_width


# -----------------------------
# Basic validation
# -----------------------------

if pulse_rate <= 0:
    raise ValueError("pulse_rate must be positive.")

if total_time <= 0:
    raise ValueError("total_time must be positive.")

if pulse_height <= 0:
    raise ValueError("pulse_height must be positive.")

if rise_time <= 0 or fall_time <= 0:
    raise ValueError("rise_time and fall_time must be positive.")

if refractory_fraction < 0:
    raise ValueError("refractory_fraction must be non-negative.")


# -----------------------------
# Random number generator
# -----------------------------

rng = np.random.default_rng()


# -----------------------------
# Generate piecewise pulses
# -----------------------------

points = []

# Start at 0 V
points.append((0.0, 0.0))

t = 0.0
pulse_count = 0

while t < total_time:
    # For a Poisson pulse-arrival process, the waiting times
    # between pulse attempts are exponentially distributed.
    dt = rng.exponential(1 / pulse_rate)

    start = t + dt

    if start >= total_time:
        break

    width = get_pulse_width()

    if width <= rise_time + fall_time:
        print(
            f"Skipping pulse: width={width:.3e} s is too small for "
            f"rise_time + fall_time={(rise_time + fall_time):.3e} s."
        )
        t = start
        continue

    end_high = start + width
    end_fall = end_high + fall_time

    if end_fall > total_time:
        break

    refractory_period = refractory_fraction * width
    next_allowed_time = end_fall + refractory_period

    # Stay at 0 V until pulse begins
    points.append((start, 0.0))

    # Linear rising edge
    points.append((start + rise_time, pulse_height))

    # Stay high
    points.append((end_high, pulse_height))

    # Linear falling edge
    points.append((end_fall, 0.0))

    pulse_count += 1

    # Enforce refractory period before the next random wait begins
    t = next_allowed_time

# End at 0 V
if points[-1][0] < total_time:
    points.append((total_time, 0.0))


# -----------------------------
# Write Cadence/Spectre-style PWL file
# -----------------------------
#
# This is intentionally not a CSV.
# It is a whitespace-separated two-column file:
#
#     time voltage
#
# with no header line.

with open(output_file, "w") as f:
    for time, voltage in points:
        f.write(f"{time:.12e} {voltage:.12e}\n")

print(f"PWL file written to {output_file}")
print(f"Generated {pulse_count} pulses.")


# -----------------------------
# Plot piecewise voltage signal
# -----------------------------

time_scale_factors = {
    "s": 1.0,
    "ms": 1e3,
    "us": 1e6,
    "ns": 1e9,
}

if plot_time_unit not in time_scale_factors:
    raise ValueError('plot_time_unit must be one of: "s", "ms", "us", "ns".')

scale = time_scale_factors[plot_time_unit]

times_scaled = [scale * p[0] for p in points]
voltages = [p[1] for p in points]

plt.figure(figsize=(10, 4))
plt.plot(times_scaled, voltages)
plt.xlabel(f"Time [{plot_time_unit}]")
plt.ylabel("Voltage [V]")
plt.title("Random PWL Voltage Pulses with Refractory Period")
plt.ylim(-0.2, pulse_height + 0.4)
plt.grid(True)
plt.show()