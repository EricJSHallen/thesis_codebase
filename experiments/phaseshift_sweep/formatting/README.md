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
