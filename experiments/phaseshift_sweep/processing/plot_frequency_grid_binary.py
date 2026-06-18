import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


input_csv = Path(__file__).resolve().with_name("frequency_grid_binary.csv")
output_dir = Path(__file__).resolve().with_name("frequency_grid_binary_plots")

frequency_start_hz = 0
frequency_step_hz = 5
max_frequency_hz = 500


def get_frequency_values() -> list[int]:
    return list(range(frequency_start_hz, max_frequency_hz + 1, frequency_step_hz))


def read_frequency_grid_binary() -> dict[str, set[tuple[int, int]]]:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {input_csv}")

    matches_by_isi: dict[str, set[tuple[int, int]]] = {}

    with input_csv.open("r", newline="") as f:
        reader = csv.DictReader(f)
        base_columns = {"mean_frequency_1_hz", "mean_frequency_2_hz"}

        if reader.fieldnames is None:
            raise ValueError(f"Input CSV is empty: {input_csv}")

        missing_columns = base_columns - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                "Input CSV is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        isi_columns = [
            column for column in reader.fieldnames if column not in base_columns
        ]
        if not isi_columns:
            raise ValueError("Input CSV does not contain any ISI columns.")

        matches_by_isi = {isi_column: set() for isi_column in isi_columns}

        for row in reader:
            mean_frequency_1_hz = int(row["mean_frequency_1_hz"])
            mean_frequency_2_hz = int(row["mean_frequency_2_hz"])

            for isi_column in isi_columns:
                if int(row[isi_column]):
                    matches_by_isi[isi_column].add(
                        (mean_frequency_1_hz, mean_frequency_2_hz)
                    )

    return matches_by_isi


def validate_matching_pairs(
    matching_pairs: set[tuple[int, int]],
    frequency_values: list[int],
) -> None:
    frequency_to_index = {
        frequency: index for index, frequency in enumerate(frequency_values)
    }

    for mean_frequency_1_hz, mean_frequency_2_hz in matching_pairs:
        if mean_frequency_1_hz not in frequency_to_index:
            raise ValueError(f"Unexpected mean_frequency_1_hz: {mean_frequency_1_hz}")
        if mean_frequency_2_hz not in frequency_to_index:
            raise ValueError(f"Unexpected mean_frequency_2_hz: {mean_frequency_2_hz}")


def plot_filename(isi_column: str) -> str:
    return f"{isi_column}.png"


def plot_title(isi_column: str) -> str:
    if isi_column.startswith("isi_") and isi_column.endswith("us"):
        isi_us = isi_column.removeprefix("isi_").removesuffix("us")
        return f"ISI = {isi_us} us"
    return isi_column


def plot_isi_grid(
    isi_column: str,
    matching_pairs: set[tuple[int, int]],
    frequency_values: list[int],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / plot_filename(isi_column)

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

    for mean_frequency_1_hz, mean_frequency_2_hz in matching_pairs:
        x_index = frequency_to_index[mean_frequency_1_hz]
        y_index = frequency_to_index[mean_frequency_2_hz]
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

    title = plot_title(isi_column)
    x_label = "mean frequency 1 (Hz)"
    y_label = "mean frequency 2 (Hz)"
    draw.text((grid_left, 20), title, fill="black", font=font)
    draw.text(
        (grid_left + grid_size // 2 - 70, grid_bottom + 45),
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
    matches_by_isi = read_frequency_grid_binary()

    print(f"Read CSV: {input_csv}")
    print(f"Found {len(matches_by_isi)} ISI columns")

    for isi_column, matching_pairs in matches_by_isi.items():
        validate_matching_pairs(matching_pairs, frequency_values)
        output_path = plot_isi_grid(isi_column, matching_pairs, frequency_values)
        print(f"Wrote plot: {output_path}")


if __name__ == "__main__":
    main()
