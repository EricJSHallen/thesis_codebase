from pathlib import Path
import re
import csv

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_TXT = BASE_DIR / "testoutput" / "test" / "output_currents.txt"
OUTPUT_CSV = BASE_DIR / "condensed_data" / "output_currents.csv"

OVERWRITE = True


# ---------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------

SUFFIX_MULTIPLIERS = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

ENGINEERING_NUMBER_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([fpnumkKMG]?)$"
)


def parse_engineering_number(value: str) -> float:
    value = value.strip()
    match = ENGINEERING_NUMBER_RE.match(value)

    if match is None:
        raise ValueError(f"Could not parse numeric value: {value!r}")

    number_string, suffix = match.groups()
    return float(number_string) * SUFFIX_MULTIPLIERS[suffix]


# ---------------------------------------------------------------------
# File conversion
# ---------------------------------------------------------------------

def find_first_data_line(lines: list[str], expected_columns: int) -> int:
    for index, line in enumerate(lines):
        parts = line.split()

        if len(parts) != expected_columns:
            continue

        try:
            for part in parts:
                parse_engineering_number(part)
        except ValueError:
            continue

        return index

    raise ValueError(
        "No two-column numeric data rows were found. Expected rows like:\n"
        "    0    -18.3369275u"
    )


def convert_txt_to_csv(input_txt: Path, output_csv: Path) -> int:
    if not input_txt.exists():
        raise FileNotFoundError(f"Could not find input file: {input_txt}")

    with input_txt.open("r", encoding="utf-8", errors="replace") as infile:
        lines = [line.strip() for line in infile if line.strip()]

    if not lines:
        raise ValueError(f"File contains no usable data: {input_txt}")

    csv_header = ["time_s", "current_A"]
    expected_columns = len(csv_header)

    first_data_index = find_first_data_line(lines, expected_columns)

    converted_rows = []

    for line_number, line in enumerate(lines[first_data_index:], start=first_data_index + 1):
        parts = line.split()

        if len(parts) != expected_columns:
            raise ValueError(
                f"Unexpected number of columns in {input_txt} on line {line_number}.\n"
                f"Expected {expected_columns} columns, got {len(parts)}.\n"
                f"Line content: {line!r}"
            )

        converted_row = [parse_engineering_number(part) for part in parts]
        converted_rows.append(converted_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if output_csv.exists() and not OVERWRITE:
        raise FileExistsError(f"Output file already exists: {output_csv}")

    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(csv_header)
        writer.writerows(converted_rows)

    return len(converted_rows)


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------

def main() -> None:
    row_count = convert_txt_to_csv(INPUT_TXT, OUTPUT_CSV)

    print(f"Converted: {INPUT_TXT} -> {OUTPUT_CSV}")
    print(f"Rows written: {row_count}")


if __name__ == "__main__":
    main()