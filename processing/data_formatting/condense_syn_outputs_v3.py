from pathlib import Path
import re
import csv

# condense_syn_outputs_v3.py
# Converts output_signals.txt files from output_single_data and output_duo_data
# into CSV files in cadence_extracted/condensed1syn and cadence_extracted/condensed2syn.

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

INPUT_TXT_NAME = "output_signals.txt"
OVERWRITE = True

# True: write one long list of CSV files directly into condensed1syn/condensed2syn.
# False: write condensed.../st1_1hz_st2_81hz/trial_1.csv, like the older script.
FLAT_OUTPUT = True


# ---------------------------------------------------------------------
# Project-root detection
# ---------------------------------------------------------------------

def find_project_dirs() -> tuple[Path, Path]:
    """
    Return:
        cadence_extraction_dir
        cadence_extracted_dir

    This lets the script work whether you place it in:
        processing/cadence_extraction/
    or directly in:
        processing/
    """
    here = Path(__file__).resolve().parent

    candidates = []

    # Case 1: script is inside processing/cadence_extraction/
    candidates.append((here, here.parent / "cadence_extracted"))

    # Case 2: script is inside processing/
    candidates.append((here / "cadence_extraction", here / "cadence_extracted"))

    for cadence_extraction_dir, cadence_extracted_dir in candidates:
        if (
            cadence_extraction_dir.exists()
            and (cadence_extraction_dir / "output_single_data").exists()
            and (cadence_extraction_dir / "output_duo_data").exists()
        ):
            return cadence_extraction_dir, cadence_extracted_dir

    raise FileNotFoundError(
        "Could not find both output_single_data and output_duo_data.\n"
        "Put this script either in processing/cadence_extraction/ or in processing/."
    )


CADENCE_EXTRACTION_DIR, CADENCE_EXTRACTED_DIR = find_project_dirs()

JOBS = [
    {
        "kind": "single",
        "input_dir": CADENCE_EXTRACTION_DIR / "output_single_data",
        "output_dir": CADENCE_EXTRACTED_DIR / "condensed1syn",
        "header": [
            "time_s",
            "i_I56_Iout_A",
            "v_vpre_res_V",
            "v_vpre1_res_V",
        ],
    },
    {
        "kind": "duo",
        "input_dir": CADENCE_EXTRACTION_DIR / "output_duo_data",
        "output_dir": CADENCE_EXTRACTED_DIR / "condensed2syn",
        "header": [
            "time_s",
            "i_I172_Iout_A",
            "i_I56_Iout_A",
            "v_vpre_res_V",
            "v_vpre1_res_V",
        ],
    },
]


# ---------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------

SUFFIX_MULTIPLIERS = {
    "a": 1e-18,  # atto
    "f": 1e-15,  # femto
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


def parse_engineering_number(value: str) -> float:
    """Convert strings such as 152m, -13.657u, -222a, 1, 3.2e-6 into floats."""
    value = value.strip()
    pattern = r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([afpnumkKMG]?)$"
    match = re.match(pattern, value)
    if not match:
        raise ValueError(f"Could not parse numeric value: {value!r}")
    number_str, suffix = match.groups()
    return float(number_str) * SUFFIX_MULTIPLIERS[suffix]


# ---------------------------------------------------------------------
# Folder-name parsing
# ---------------------------------------------------------------------

def parse_trial_folder_name(folder_name: str):
    """
    Parse folder names such as:
        st1_1_hz__st2_81_hz__trial_1

    Returns:
        ("st1_1hz_st2_81hz", 1)
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
    return f"st1_{st1}hz_st2_{st2}hz", trial


# ---------------------------------------------------------------------
# File conversion
# ---------------------------------------------------------------------

def read_non_empty_lines(input_txt: Path) -> list[str]:
    with input_txt.open("r", encoding="utf-8", errors="replace") as infile:
        return [line.strip() for line in infile if line.strip()]


def convert_txt_to_csv(input_txt: Path, output_csv: Path, csv_header: list[str]) -> None:
    lines = read_non_empty_lines(input_txt)

    if len(lines) < 2:
        raise ValueError(f"File contains no usable data: {input_txt}")

    # First non-empty line is the raw simulator header. Replace it with csv_header.
    data_lines = lines[1:]
    rows = []

    for line_number, line in enumerate(data_lines, start=2):
        parts = line.split()

        if len(parts) != len(csv_header):
            raise ValueError(
                f"Unexpected number of columns in {input_txt} on line {line_number}.\n"
                f"Expected {len(csv_header)} columns, got {len(parts)}.\n"
                f"Line content: {line!r}"
            )

        rows.append([parse_engineering_number(value) for value in parts])

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if output_csv.exists() and not OVERWRITE:
        raise FileExistsError(f"Output file already exists: {output_csv}")

    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(csv_header)
        writer.writerows(rows)


def make_output_csv_path(output_dir: Path, folder_name: str, combination_name: str, trial_number: int) -> Path:
    if FLAT_OUTPUT:
        return output_dir / f"{folder_name}.csv"
    return output_dir / combination_name / f"trial_{trial_number}.csv"


# ---------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------

def process_job(job: dict) -> tuple[int, int, int]:
    kind = job["kind"]
    input_dir = job["input_dir"]
    output_dir = job["output_dir"]
    csv_header = job["header"]

    print(f"\nProcessing {kind} data")
    print(f"  input : {input_dir}")
    print(f"  output: {output_dir}")

    if not input_dir.exists():
        print(f"  ERROR: input directory not found")
        return 0, 1, 0

    output_dir.mkdir(parents=True, exist_ok=True)

    converted_count = 0
    skipped_count = 0
    error_count = 0

    trial_dirs = [p for p in sorted(input_dir.iterdir()) if p.is_dir()]
    print(f"  found trial directories: {len(trial_dirs)}")

    for trial_dir in trial_dirs:
        parsed = parse_trial_folder_name(trial_dir.name)
        if parsed is None:
            print(f"  skipped unrecognised directory name: {trial_dir.name}")
            skipped_count += 1
            continue

        combination_name, trial_number = parsed
        input_txt = trial_dir / INPUT_TXT_NAME

        if not input_txt.exists():
            print(f"  skipped {trial_dir.name}: no {INPUT_TXT_NAME}")
            skipped_count += 1
            continue

        output_csv = make_output_csv_path(
            output_dir=output_dir,
            folder_name=trial_dir.name,
            combination_name=combination_name,
            trial_number=trial_number,
        )

        try:
            convert_txt_to_csv(input_txt, output_csv, csv_header)
        except Exception as exc:
            print(f"  ERROR converting {trial_dir.name}: {exc}")
            error_count += 1
            continue

        converted_count += 1

    print(f"  converted: {converted_count}")
    print(f"  skipped  : {skipped_count}")
    print(f"  errors   : {error_count}")

    return converted_count, skipped_count, error_count


def main() -> None:
    print("Resolved directories")
    print(f"  cadence_extraction: {CADENCE_EXTRACTION_DIR}")
    print(f"  cadence_extracted : {CADENCE_EXTRACTED_DIR}")

    total_converted = 0
    total_skipped = 0
    total_errors = 0

    for job in JOBS:
        converted, skipped, errors = process_job(job)
        total_converted += converted
        total_skipped += skipped
        total_errors += errors

    print("\nFinished.")
    print(f"Total converted: {total_converted}")
    print(f"Total skipped  : {total_skipped}")
    print(f"Total errors   : {total_errors}")


if __name__ == "__main__":
    main()
