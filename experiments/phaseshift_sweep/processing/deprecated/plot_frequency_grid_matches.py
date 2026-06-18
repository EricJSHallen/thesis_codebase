import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


input_csv = Path(__file__).resolve().with_name("frequency_grid_matches.csv")
output_dir = Path(__file__).resolve().with_name("frequency_grid_plots")

frequency_start_hz = 0
frequency_step_hz = 20
max_frequency_hz = 1000


def get_frequency_values() -> list[int]:
    return list(range(frequency_start_hz, max_frequency_hz + 1, frequency_step_hz))


def read_frequency_grid_matches() -> dict[float, set[tuple[int, int]]]:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {input_csv}")

    matches_by_prior: dict[float, set[tuple[int, int]]] = {}

    with input_csv.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required_columns = {
            "prior_s",
            "vpre_0_frequency_hz",
            "vpre_1_frequency_hz",
            "gap_less_than_prior",
        }

        if reader.fieldnames is None:
            raise ValueError(f"Input CSV is empty: {input_csv}")

        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                "Input CSV is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row in reader:
            prior = float(row["prior_s"])
            vpre_0_frequency = int(row["vpre_0_frequency_hz"])
            vpre_1_frequency = int(row["vpre_1_frequency_hz"])
            gap_less_than_prior = bool(int(row["gap_less_than_prior"]))

            matches_by_prior.setdefault(prior, set())
            if gap_less_than_prior:
                matches_by_prior[prior].add((vpre_0_frequency, vpre_1_frequency))

    return matches_by_prior


def validate_matching_pairs(
    matching_pairs: set[tuple[int, int]],
    frequency_values: list[int],
) -> None:
    frequency_to_index = {
        frequency: index for index, frequency in enumerate(frequency_values)
    }

    for vpre_0_frequency, vpre_1_frequency in matching_pairs:
        if vpre_0_frequency not in frequency_to_index:
            raise ValueError(f"Unexpected vpre_0 frequency: {vpre_0_frequency}")
        if vpre_1_frequency not in frequency_to_index:
            raise ValueError(f"Unexpected vpre_1 frequency: {vpre_1_frequency}")


def prior_plot_filename(prior: float) -> str:
    prior_us = prior * 1e6
    if prior_us.is_integer():
        return f"isi_{int(prior_us)}us.png"
    return f"prior_{prior:.6e}.png"


def plot_prior_grid(
    prior: float,
    matching_pairs: set[tuple[int, int]],
    frequency_values: list[int],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / prior_plot_filename(prior)

    cell_size = 4
    left_margin = 90
    right_margin = 30
    top_margin = 55
    bottom_margin = 75
    grid_size = len(frequency_values) * cell_size
    image_width = left_margin + grid_size + right_margin
    image_height = top_margin + grid_size + bottom_margin
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    frequency_to_index = {
        frequency: index for index, frequency in enumerate(frequency_values)
    }
    grid_left = left_margin
    grid_top = top_margin
    grid_bottom = grid_top + grid_size

    draw.rectangle(
        [grid_left, grid_top, grid_left + grid_size, grid_bottom],
        fill="black",
    )

    for vpre_0_frequency, vpre_1_frequency in matching_pairs:
        x_index = frequency_to_index[vpre_0_frequency]
        y_index = frequency_to_index[vpre_1_frequency]
        x0 = grid_left + x_index * cell_size
        y0 = grid_top + (len(frequency_values) - 1 - y_index) * cell_size
        draw.rectangle(
            [x0, y0, x0 + cell_size - 1, y0 + cell_size - 1],
            fill="white",
        )

    draw.rectangle(
        [grid_left, grid_top, grid_left + grid_size, grid_bottom],
        outline="black",
    )

    title = f"ISI = {prior * 1e6:g} us"
    x_label = "vpre_0 mean frequency (Hz)"
    y_label = "vpre_1 mean frequency (Hz)"
    draw.text((grid_left, 20), title, fill="black", font=font)
    draw.text(
        (grid_left + grid_size // 2 - 75, grid_bottom + 45),
        x_label,
        fill="black",
        font=font,
    )
    draw.text((10, grid_top + grid_size // 2), y_label, fill="black", font=font)

    tick_values = [
        frequency_start_hz,
        (frequency_start_hz + max_frequency_hz) // 2,
        max_frequency_hz,
    ]
    for tick_value in tick_values:
        tick_index = frequency_to_index[tick_value]
        x = grid_left + tick_index * cell_size
        y = grid_bottom - tick_index * cell_size

        draw.line([(x, grid_bottom), (x, grid_bottom + 5)], fill="black")
        draw.text((x - 10, grid_bottom + 8), str(tick_value), fill="black", font=font)

        draw.line([(grid_left - 5, y), (grid_left, y)], fill="black")
        draw.text((grid_left - 40, y - 5), str(tick_value), fill="black", font=font)

    image.save(output_path)

    return output_path


def main() -> None:
    frequency_values = get_frequency_values()
    matches_by_prior = read_frequency_grid_matches()

    print(f"Read CSV: {input_csv}")
    print(f"Found {len(matches_by_prior)} ISI/prior values")

    for prior in sorted(matches_by_prior, reverse=True):
        validate_matching_pairs(matches_by_prior[prior], frequency_values)
        output_path = plot_prior_grid(prior, matches_by_prior[prior], frequency_values)
        print(f"Wrote plot: {output_path}")


if __name__ == "__main__":
    main()
