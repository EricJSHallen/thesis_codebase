from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "output_currents.csv"
OUTPUT_FIGURE = BASE_DIR / "output_currents_plot.png"


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------
def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Could not find CSV file: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    required_columns = ["time_s", "current_A"]
    for column in required_columns:
        if column not in df.columns:
            raise ValueError(
                f"Missing required column: {column!r}. "
                f"Found columns: {list(df.columns)}"
            )

    plt.figure(figsize=(10, 6))
    plt.plot(df["time_s"], df["current_A"], linewidth=1)
    plt.xlabel("Time (s)")
    plt.ylabel("Current (A)")
    plt.title("Output Current vs Time")
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(OUTPUT_FIGURE, dpi=300)
    plt.show()

    print(f"Plot saved to: {OUTPUT_FIGURE}")


if __name__ == "__main__":
    main()
