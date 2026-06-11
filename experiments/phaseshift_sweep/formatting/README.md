# Phase-Shift Formatting

This directory contains utilities for converting raw phase-shift OCEAN exports into analysis-ready CSV files.

## Naming Convention

The raw directories keep their original OCEAN run names:

```text
database/raw/phase_shift_1syn_ocean_output_v2/
database/raw/phase_shift_2syn_ocean_output_v2/
```

The formatted directories intentionally use cleaner names without the implementation/version suffixes:

```text
database/formatted/phase_shift_1syn/
database/formatted/phase_shift_2syn/
```

## Layout Mapping

Current flat phase-shift raw output:

```text
database/raw/phase_shift_1syn_ocean_output_v2/1e-7_phase_shift/output_signals.txt
```

Formatted output:

```text
database/formatted/phase_shift_1syn/1e-7_phase_shift.csv
```

Future Vtau-aware raw output:

```text
database/raw/phase_shift_1syn_ocean_output_v2/vtau_0p1/1e-7_phase_shift/output_signals.txt
```

Formatted output:

```text
database/formatted/phase_shift_1syn/vtau_0p1/1e-7_phase_shift.csv
```

The same convention applies to `2syn`.

## Vtau Sweep Formatter

Use `format_raw_phaseshift_vtau_outputs.py` for Vtau sweep outputs stored under:

```text
database/raw/phase_shift_1syn_ocean_output_vtau_v2/
database/raw/phase_shift_2syn_ocean_output_vtau_v2/
```

This formatter only processes nested lowercase `vtau_*p*` run folders and ignores flat phase-shift folders at the raw directory root.

Example raw input:

```text
database/raw/phase_shift_1syn_ocean_output_vtau_v2/vtau_0p1/1e-7_phase_shift/output_signals.txt
```

Formatted output:

```text
database/formatted/phase_shift_1syn_vtau_v2/vtau_0p1/1e-7_phase_shift.csv
```

Dry-run both `1syn` and `2syn` Vtau outputs with:

```bash
python3 experiments/phaseshift_sweep/formatting/format_raw_phaseshift_vtau_outputs.py --all --dry-run
```

## Vthr And Vw Sweep Formatters

Use `format_raw_phaseshift_vthr_outputs.py` for Vthr sweep outputs stored under:

```text
database/raw/phase_shift_1syn_ocean_output_vthr_v2/
database/raw/phase_shift_2syn_ocean_output_vthr_v2/
```

Use `format_raw_phaseshift_vw_outputs.py` for Vw sweep outputs stored under:

```text
database/raw/phase_shift_1syn_ocean_output_vw_v2/
database/raw/phase_shift_2syn_ocean_output_vw_v2/
```

These formatters only process nested lowercase `vthr_*p*` or `vw_*p*` run folders and ignore flat phase-shift folders at the raw directory root.

Example raw inputs:

```text
database/raw/phase_shift_1syn_ocean_output_vthr_v2/vthr_0p1/1e-7_phase_shift/output_signals.txt
database/raw/phase_shift_1syn_ocean_output_vw_v2/vw_0p1/1e-7_phase_shift/output_signals.txt
```

Formatted outputs:

```text
database/formatted/phase_shift_1syn_vthr_v2/vthr_0p1/1e-7_phase_shift.csv
database/formatted/phase_shift_1syn_vw_v2/vw_0p1/1e-7_phase_shift.csv
```

Dry-run both `1syn` and `2syn` outputs with:

```bash
python3 experiments/phaseshift_sweep/formatting/format_raw_phaseshift_vthr_outputs.py --all --dry-run
python3 experiments/phaseshift_sweep/formatting/format_raw_phaseshift_vw_outputs.py --all --dry-run
```
