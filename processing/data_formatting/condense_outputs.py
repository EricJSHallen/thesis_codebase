from pathlib import Path
import re
import csv
import shutil


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DATA_DIR = BASE_DIR / "output_data"
CONDENSED_DATA_DIR = BASE_DIR / "condensed_data"

INPUT_TXT_NAME = "output_signals.txt"

# If True, existing CSV files in condensed_data may be overwritten.
OVERWRITE = True


# ---------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------

SUFFIX_MULTIPLIERS = {
    "p": 1e-12,  # pico
    "n": 1e-9,   # nano
    "u": 1e-6,   # micro
    "m": 1e-3,   # milli
    "": 1.0,     # no suffix
}


def parse_engineering_number(value: str) -> float:
    """
    Convert strings like:
        152m  -> 152e-3
        3.2u  -> 3.2e-6
        -13.6n -> -13.6e-9
        1.8   -> 1.8

    into ordinary floating-point numbers.
    """

    value = value.strip()

    pattern = r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([pnum]?)$"
    match = re.match(pattern, value)

    if not match:
        raise ValueError(f"Could not parse numeric value: {value!r}")

    number_str, suffix = match.groups()

    multiplier = SUFFIX_MULTIPLIERS[suffix]
    return float(number_str) * multiplier


# ---------------------------------------------------------------------
# Folder-name parsing
# ---------------------------------------------------------------------

def parse_trial_folder_name(folder_name: str):
    """
    Parse names of the form:

        st1_1_hz__st2_5_hz__trial_3

    and return:

        combination_name = st1_1hz_st2_5hz
        trial_number = 3
    """

    pattern = (
        r"^st1_(?P<st1>\d+)_hz__"
        r"st2_(?P<st2>\d+)_hz__"
        r"trial_(?P<trial>\d+)$"
    )

    match = re.match(pattern, folder_name)

    if not match:
        return None

    st1 = match.group("st1")
    st2 = match.group("st2")
    trial = int(match.group("trial"))

    combination_name = f"st1_{st1}hz_st2_{st2}hz"

    return combination_name, trial


# ---------------------------------------------------------------------
# Header handling
# ---------------------------------------------------------------------

def clean_header(raw_header_line: str):
    """
    The input header contains names like:

        time (s)   i("/I172/Iout"   i("/I56/Iout"   v("/vp re ?res ...

    This function replaces it with cleaner CSV column names.

    Adjust these names if you want different labels.
    """

    return [
        "time_s",
        "i_I172_Iout_A",
        "i_I56_Iout_A",
        "v_vp_res_V",
        "v_vpre1_res_V",
    ]


# ---------------------------------------------------------------------
# File conversion
# ---------------------------------------------------------------------

def convert_txt_to_csv(input_txt: Path, output_csv: Path):
    with input_txt.open("r", encoding="utf-8", errors="replace") as infile:
        lines = infile.readlines()

    # Remove empty lines.
    lines = [line.strip() for line in lines if line.strip()]

    if len(lines) < 2:
        raise ValueError(f"File contains no usable data: {input_txt}")

    # First non-empty line is assumed to be the header.
    csv_header = clean_header(lines[0])

    converted_rows = []

    for line_number, line in enumerate(lines[1:], start=2):
        parts = line.split()

        if len(parts) != len(csv_header):
            raise ValueError(
                f"Unexpected number of columns in {input_txt} on line {line_number}.\n"
                f"Expected {len(csv_header)} columns, got {len(parts)}.\n"
                f"Line content: {line!r}"
            )

        converted_row = [parse_engineering_number(value) for value in parts]
        converted_rows.append(converted_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if output_csv.exists() and not OVERWRITE:
        raise FileExistsError(f"Output file already exists: {output_csv}")

    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(csv_header)
        writer.writerows(converted_rows)


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------

def main():
    if not OUTPUT_DATA_DIR.exists():
        raise FileNotFoundError(f"Could not find output_data directory: {OUTPUT_DATA_DIR}")

    CONDENSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    converted_count = 0
    skipped_count = 0

    for trial_dir in sorted(OUTPUT_DATA_DIR.iterdir()):
        if not trial_dir.is_dir():
            continue

        parsed = parse_trial_folder_name(trial_dir.name)

        if parsed is None:
            print(f"Skipping unrecognised directory name: {trial_dir.name}")
            skipped_count += 1
            continue

        combination_name, trial_number = parsed

        input_txt = trial_dir / INPUT_TXT_NAME

        if not input_txt.exists():
            print(f"Skipping {trial_dir.name}: no {INPUT_TXT_NAME} found")
            skipped_count += 1
            continue

        output_dir = CONDENSED_DATA_DIR / combination_name
        output_csv = output_dir / f"trial_{trial_number}.csv"

        convert_txt_to_csv(input_txt, output_csv)

        print(f"Converted: {input_txt} -> {output_csv}")
        converted_count += 1

    print()
    print(f"Finished.")
    print(f"Converted files: {converted_count}")
    print(f"Skipped directories/files: {skipped_count}")


if __name__ == "__main__":
    main()