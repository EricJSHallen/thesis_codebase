# Dual-Bias Phase-Shift Analysis

This directory contains analysis entry points for dual-bias phase-shift sweeps.

Available sweep directories:

```text
vtau_vthr_sweep/
vtau_vw_sweep/
vw_vthr_sweep/
```

Each sweep directory contains:

```text
plot_phase_shift_csvs.py
plot_phase_shift_currents.py
plot_phase_shift_currents_filled.py
integrate_phase_shift_currents.py
integrate_phase_shift_currents_binned.py
plot_phase_shift_binned_integral_ratio_histogram.py
plot_phase_shift_binned_integral_ratio_line.py
plot_phase_shift_binned_integral_charge_difference_line.py
plot_phase_shift_integral_difference.py
plot_phase_shift_integral_heatmap.py
plot_phase_shift_integral_volume.py
```

The scripts expect formatted CSVs with this layout:

```text
database/formatted/phase_shift_1syn_<sweep>_v2/<bias_a>/<bias_b>/<phase_shift>.csv
database/formatted/phase_shift_2syn_<sweep>_v2/<bias_a>/<bias_b>/<phase_shift>.csv
```

Examples:

```text
database/formatted/phase_shift_1syn_vtau_vthr_v2/vtau_0p1/vthr_0p1/3.2e-5_phase_shift.csv
database/formatted/phase_shift_2syn_vtau_vthr_v2/vtau_0p1/vthr_0p1/3.2e-5_phase_shift.csv
```

## Integral Difference Plot Order

`plot_phase_shift_integral_difference.py` opens one figure per fixed second bias value.

For `vtau_vthr_sweep`, it plots pages in this order:

```text
vthr_0p1, vthr_0p2, vthr_0p3, ...
```

Each page contains one curve per `vtau_*` value.

For `vtau_vw_sweep`, pages are fixed `vw_*` values, with one curve per `vtau_*` value.

For `vw_vthr_sweep`, pages are fixed `vthr_*` values, with one curve per `vw_*` value.

## Examples

Integrate a small sample:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/integrate_phase_shift_currents.py --limit 5
```

Write integrals to a CSV:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/integrate_phase_shift_currents.py --output-csv /tmp/vtau_vthr_integrals.csv
```

Integrate signed baseline-subtracted currents in 1 us bins without plotting:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/integrate_phase_shift_currents_binned.py --bin-width-us 1 --limit 5
```

Write signed binned integrals with 0.5 us bins to a CSV:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/integrate_phase_shift_currents_binned.py --bin-width-us 0.5 --output-csv /tmp/vtau_vthr_binned_integrals.csv
```

Plot one histogram-style ratio bar chart per original current pair from binned integrals:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_histogram.py --binned-integrals-csv /tmp/vtau_vthr_binned_integrals.csv
```

Compute 1 us signed binned integrals directly and save one ratio chart per selected current pair:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_histogram.py --bin-width-us 1 --vthr 0p7 --save-images --no-show
```

Plot one continuous binned-ratio line per original current pair from binned integrals. The line plot overlays the two voltage input spike traces on a right-hand voltage axis:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_line.py --binned-integrals-csv /tmp/vtau_vthr_binned_integrals.csv
```

Disable the voltage input spike overlay:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_line.py --binned-integrals-csv /tmp/vtau_vthr_binned_integrals.csv --no-voltage-overlay
```

Compute 1 us signed binned integrals directly and plot continuous ratio lines:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_line.py --bin-width-us 1 --limit 5
```

Plot cumulative ratio lines where each point uses signed integrals from 0 through that bin:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_ratio_line.py --binned-integrals-csv /tmp/vtau_vthr_binned_integrals.csv --cumulative-ratio
```

Plot one continuous per-bin signed charge-difference line per original current pair from binned integrals. The charge difference is `2syn - 1syn` in pC, with voltage input spikes overlaid on the right-hand voltage axis:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_charge_difference_line.py --binned-integrals-csv /tmp/vtau_vthr_binned_integrals.csv
```

Compute 1 us signed binned integrals directly and plot charge-difference lines without the voltage overlay:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_binned_integral_charge_difference_line.py --bin-width-us 1 --limit 5 --no-voltage-overlay
```

Dry-run the integral-difference plot paging without opening windows:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_difference.py --dry-run
```

Plot only one fixed Vthr page:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_difference.py --vthr 0p7
```

Limit integral-difference plots to valid data at or below 20 us:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_difference.py --max-phase-shift-us 20
```

Plot heatmaps for each phase shift, with heatmap axes set by the two swept bias voltages. Each window contains absolute charge difference, charge ratio, and inverse charge ratio (`1 / ratio`):

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_heatmap.py --max-phase-shift-us 20
```

Dry-run heatmap page generation without opening windows:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_heatmap.py --max-phase-shift-us 20 --dry-run
```

Save generated heatmap images under `experiments/phaseshift_sweep/outputimages/` without opening windows:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_heatmap.py --max-phase-shift-us 20 --save-images --no-show
```

Show heatmaps sequentially instead of three at a time:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_heatmap.py --max-phase-shift-us 20 --sequential
```

Plot 3D volumes with the two bias voltages on x/y and phase shift on z. The default scatter view keeps internal structure visible and cycles through charge, ratio, then inverse ratio:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_volume.py --max-phase-shift-us 20
```

Plot translucent phase-shift slices instead of a scatter volume:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_volume.py --max-phase-shift-us 20 --metric ratio --view surfaces --alpha 0.4
```

Plot only one volume metric instead of cycling all three:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_volume.py --max-phase-shift-us 20 --metric ratio
```

Dry-run volume dimensions without opening a window:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_volume.py --max-phase-shift-us 20 --dry-run
```

Save volume images without opening windows:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_integral_volume.py --max-phase-shift-us 20 --save-images --no-show
```

Dry-run selected current plots:

```bash
python3 experiments/phaseshift_sweep/analysis/dual_bias_sweeps/vtau_vthr_sweep/plot_phase_shift_currents.py --vthr 0p1 --limit 5 --dry-run
```
