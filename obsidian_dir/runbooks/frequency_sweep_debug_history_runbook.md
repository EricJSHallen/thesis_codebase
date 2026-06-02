# Frequency Sweep Plain-Spectre Debug History Runbook

**Scope:** this runbook records the debugging path that led to the currently functioning plain-Spectre frequency-sweep flow on the `thesis_reorg` branch of `thesis_codebase`.

**Current target repository layout:**

```text
thesis_codebase/
├── database/
└── experiments/
    └── frequency_sweep/
        ├── analysis/
        ├── formatting/
        ├── input_data/
        │   └── spike_train_output/
        ├── ocn_scripts/
        └── scripts/
            └── plain_spectre_helpers/
```

The current working bundle installs a startup script under:

```text
experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v3.sh
```

and helper scripts under:

```text
experiments/frequency_sweep/scripts/plain_spectre_helpers/
```

---

## 1. High-level diagnostic summary

The final successful architecture is:

```text
one Cadence/OCEAN or existing-ADE netlist template
        ↓
plain-Spectre template import and parameter/PWL patching
        ↓
parallel Spectre workers
        ↓
PSF result directories
        ↓
OCEAN/Virtuoso PSF-only export
        ↓
case/output_signals.txt
```

The major conclusion from the debugging process was that **parallelizing full Virtuoso/OCEAN netlisting for every case was fragile**, while **generating one clean Spectre template and then launching parallel plain Spectre jobs** was substantially more robust.

The last confirmed successful run used the v3 reorganized pipeline, including:

- Spectre wrapper discovery.
- IC/OCEAN export runtime-library resolution.
- PWL placeholder replacement.
- Explicit Spectre parameter patching.
- Quoted PWL string substitution in each copied case netlist.
- Post-Spectre OCEAN export from PSF into `output_signals.txt`.

---

## 2. What we tried

### 2.1 Earlier full-OCEAN / IPC flow

Initial work used OCEAN scripts and IPC-launched workers. The intended pattern was:

```text
prep shell script
    → create run directory
    → copy OCN worker script
    → paste ipcBeginProcess(...) commands into CIW
    → each worker netlists/runs/exports assigned cases
```

This flow encountered several recurring problems:

| Problem | Symptom | Practical interpretation | Outcome |
|---|---|---|---|
| Path drift after repo restructuring | Scripts referenced `processing/sim_run_code/...` or `thesis_database/...` after the repo was reorganized | Old hardcoded paths were no longer valid | Replaced by experiment-local paths under `experiments/frequency_sweep/...` and `database/...` |
| Job logs not in a stable location | Logs were scattered or expected under obsolete `ocean_apply_job*` locations | Monitoring became ambiguous | New flow writes logs under each run directory's `logs/` folder |
| Parallel Virtuoso/OCEAN netlisting contention | Some jobs progressed while others stalled or failed | Multiple jobs touched the same Cadence/OA/netlisting context | Avoided by generating one template, then running plain Spectre per copied netlist |
| CIW/IPC complexity | Commands were difficult to paste and restart cleanly | Manual interactive execution was brittle | Replaced by shell-level `run_all_workers.sh` for parallel plain-Spectre workers |
| OCEAN shell availability | `ocean not found in this shell` | The terminal shell had not loaded the site's Cadence/OCEAN command environment | Template generation became optional; use `ciw_template_command.il` only if template regeneration is needed |

### 2.2 Plain-Spectre template approach

We then shifted to the current approach:

1. Use one known-good Cadence-generated Spectre netlist as a template.
2. Import it into a run-local `netlist_template/raw/` directory.
3. Replace the PWL file paths with placeholders.
4. Patch the Cadence-generated bare parameter block into explicit Spectre parameter assignments.
5. Copy the template per case.
6. Substitute case-specific PWL file paths.
7. Run plain Spectre in parallel.
8. Export each case's PSF results to `output_signals.txt`.

This removed the need to run full Virtuoso/OCEAN netlisting for every single frequency combination.

---

## 3. Errors encountered and fixes

### 3.1 Collapsed shell-script files

**Symptom:** generated helper scripts had only one, two, or a few physical lines. Some started with:

```bash
#!/usr/bin/env bash set -euo pipefail ...
```

When a script is collapsed this way, the first physical line can become a shebang/comment line and large parts of the intended code may not execute correctly.

**Cause:** dynamic script-generation and/or copy/paste/bundle handling collapsed newlines.

**Fix:** move to stable helper scripts copied from:

```text
experiments/frequency_sweep/scripts/plain_spectre_helpers/
```

and validate line counts after prep. A healthy v3 bundle has scripts with many physical lines, for example:

```text
spectre_sweep_plain_reorg_v3.sh       ~287 lines
refresh_spectre_runtime.sh            ~161 lines
run_spectre_worker.sh                  ~99 lines
setup_spectre_env.sh                   ~79 lines
run_export_case.sh                     ~54 lines
run_all_workers.sh                     ~30 lines
extract_missing_outputs.sh             ~31 lines
export_psf_to_txt.ocn                  ~37 lines
```

**Reproduction check:**

```bash
find experiments/frequency_sweep -type f \( -name "*.sh" -o -name "*.ocn" \) -print -exec wc -l {} \;
```

Any substantial helper script with only 1–5 lines should be treated with suspicion.

---

### 3.2 Missing Spectre runtime libraries

**Symptom:** `check_spectre_runtime` reported missing shared libraries such as:

```text
libSpectreEH_sh.so => not found
libmdl_sh.so => not found
libfmc.so => not found
libvisadev.so => not found
```

**Cause:** the raw Spectre ELF binary under:

```text
/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre
```

was being invoked directly without the broader Cadence runtime environment.

**Fix:** prefer the site wrapper:

```text
/projects/bics/cadence/installs/SPECTRE231/tools/bin/spectre
```

The working flow uses `refresh_spectre_runtime.sh` and `setup_spectre_env.sh` to select and cache the launcher. If the selected command is a wrapper/script launcher, the runtime check deliberately skips `ldd` on the wrapper.

**Working diagnostic pattern:**

```bash
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
```

Expected acceptable output includes:

```text
Using wrapper/script launcher; skipping ldd on wrapper.
```

---

### 3.3 PWL placeholders not found in template

**Symptom:**

```text
WARNING: __ST1_PWL__ placeholder not found in template.
WARNING: __ST2_PWL__ placeholder not found in template.
```

or workers ran but did not use the correct case-specific spike trains.

**Cause:** the import script initially replaced only exact PWL paths from one selected case. If the template netlist contained different PWL file names, the replacement failed.

**Fix:** `import_template.sh` now replaces any absolute path matching:

```text
.../spike_train_output/st_1/.../*.pwl
.../spike_train_output/st_2/.../*.pwl
```

with:

```text
__ST1_PWL__
__ST2_PWL__
```

**Required check before running workers:**

```bash
grep -R "__ST1_PWL__\|__ST2_PWL__" netlist_template/raw | head -20
```

Workers should not be launched unless both placeholders are present.

---

### 3.4 Unquoted PWL file paths

**Symptom:** Spectre failed with messages like:

```text
ERROR (SFE-874): "input.scs": Unexpected operator "/"
ERROR (SFE-683): Badly formed parameters statement
```

**Cause:** workers substituted bare absolute file paths into Spectre parameter assignments, producing a malformed line such as:

```spectre
pwlFile_st1=/home/s5117909/.../trial_1.pwl
```

Spectre parsed `/` as an operator rather than as part of a string.

**Fix:** `run_spectre_worker.sh` now substitutes quoted Spectre string values:

```spectre
pwlFile_st1="/home/s5117909/.../trial_1.pwl"
pwlFile_st2="/home/s5117909/.../trial_1.pwl"
```

---

### 3.5 Unassigned Spectre design variables

**Symptom:** Spectre launched but failed with `SFE-1997` unassigned-parameter errors, for example:

```text
no value has been assigned to parameter `m2w'
no value has been assigned to parameter `Vw'
no value has been assigned to parameter `Vthr'
no value has been assigned to parameter `Vtau'
```

**Cause:** the Cadence-generated `input.scs` template included a top-level `parameters` statement with bare variable names rather than assigned values.

**Fix:** `import_template.sh` now rewrites the top-level parameter block with explicit values, including:

```spectre
m2w=3u m2l=200n
m3w=2.1u m3l=4u
m4w=2.1u m4l=1.05u
m5w=2.1u m5l=1.05u
m4wtb=2.1u m4ltb=1.05u
m2wtb=2.1u m2ltb=1.05u
pw=100u T=1m Vin=0 vmax=1.8
Vw=0.5 Vthr=0.9 Vtau=1.6
capacitance=6p
pwlFile_st2=__ST2_PWL__
pwlFile_st1=__ST1_PWL__
```

The `capacitance=6p` assignment was added to match the OCEAN runtime variable:

```lisp
desVar("capacitance" 6p)
```

---

### 3.6 Spectre completed, but no `output_signals.txt`

**Symptom:** workers displayed successful Spectre completion in logs, PSF directories existed, but:

```bash
find cases -name output_signals.txt | wc -l
```

returned `0`.

**Cause:** the plain-Spectre worker initially ran Spectre only. It did not perform the equivalent of the original OCEAN `ocnPrint(...)` waveform export.

**Fix:** add a post-Spectre export stage:

```text
run_spectre_worker.sh
    → Spectre creates case/psf
    → run_export_case.sh launches OCEAN/Virtuoso in nograph mode
    → export_psf_to_txt.ocn opens PSF and writes output_signals.txt
```

The export OCN reads the case directory through `CAD_CASE_DIR`, opens the PSF results, selects the transient result, and prints:

```text
i("/I56/Iout")
v("/vpre")
v("/vpre1")
```

into `output_signals.txt`.

---

### 3.7 OCEAN/Virtuoso export launcher missing `libvsacpp.so`

**Symptom:** Spectre completed, but export failed with:

```text
export_rc=127
virtuoso: error while loading shared libraries: libvsacpp.so: cannot open shared object file
```

**Cause:** Spectre runtime had been resolved, but the IC/OCEAN export launcher had its own missing shared-library dependencies.

**Fix:** `refresh_spectre_runtime.sh` now resolves both:

1. Spectre runtime paths.
2. IC/OCEAN or Virtuoso export runtime paths.

It writes generated environment files under:

```text
support/spectre_runtime.env
support/cadence_ic_runtime.env
```

and `setup_spectre_env.sh` loads them.

**Required checks:**

```bash
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
```

Do not run workers if `check_export_runtime` reports missing libraries.

---

## 4. What finally worked

The confirmed working run used the reorganized frequency-sweep pipeline with:

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v3.sh prep
```

followed by:

```bash
cd database/<new_run_id>

./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

A successful run is indicated by:

```bash
find cases -name output_signals.txt | wc -l
```

matching the expected number of cases, and by `failed cases: 0` in the monitoring output.

---

## 5. Information needed to reproduce the code

### 5.1 Repository and branch

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
git checkout thesis_reorg
```

### 5.2 Required repo-local paths

```text
experiments/frequency_sweep/input_data/spike_train_output/st_1/
experiments/frequency_sweep/input_data/spike_train_output/st_2/
experiments/frequency_sweep/scripts/plain_spectre_helpers/
experiments/frequency_sweep/ocn_scripts/
database/
```

### 5.3 Required external Cadence paths

The scripts assume the BIC/FSE Cadence installation is available under:

```text
/projects/bics/cadence/installs
```

The working Spectre launcher is expected near:

```text
/projects/bics/cadence/installs/SPECTRE231/tools/bin/spectre
```

The IC/OCEAN/Virtuoso launcher is expected under the IC231 installation and is resolved by `refresh_spectre_runtime.sh`.

### 5.4 Required pre-existing template netlist

The import step defaults to:

```text
/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist
```

and expects at least:

```text
input.scs
```

If you need to regenerate this netlist, use `run_template_ocean.sh` in an OCEAN-capable shell or paste `ciw_template_command.il` into the Cadence CIW.

### 5.5 Environment variables

Common override variables:

```bash
NUM_JOBS=4
RUN_LABEL=2channel_1syn_plain
RUN_ID=<manual_run_id>
DATABASE_DIR=/custom/database/path
NETLIST_SOURCE=/path/to/spectre/schematic/netlist
SPECTRE_CMD=/path/to/spectre/wrapper
CADENCE_INSTALL_ROOT=/projects/bics/cadence/installs
IC_VERSION=IC231
```

---

## 6. Minimal preflight checklist

Before launching workers, verify:

```bash
pwd                         # must be database/<run_id>
ls RUNINFO.txt cases.csv import_template.sh run_all_workers.sh
./import_template.sh
grep -R "__ST1_PWL__\|__ST2_PWL__" netlist_template/raw | head
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
```

Only then:

```bash
./run_all_workers.sh
./monitoring_commands.sh progress
```

---

## 7. Debugging commands

### Monitor progress

```bash
./monitoring_commands.sh progress
```

### Count outputs

```bash
find cases -name output_signals.txt | wc -l
```

### Inspect failures

```bash
grep -R "^FAILED case_id=" logs/spectre_worker_*.log | tail -50
```

### Inspect Spectre errors

```bash
grep -R "ERROR\|SFE-\|fatal\|terminated prematurely" cases/*/spectre.out | head -80
```

### Inspect export errors

```bash
grep -R "ERROR\|lib.*not found\|export launcher failed" cases/*/export_ocean.log | head -80
```

### Salvage completed PSF results

If Spectre completed but export failed:

```bash
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_export_runtime
./extract_missing_outputs.sh
find cases -name output_signals.txt | wc -l
```

---

## 8. Current caveats

1. The plain-Spectre approach depends on a valid Cadence-generated netlist template. If the schematic changes, regenerate/import the template before production runs.
2. The parameter patch is explicit. If the schematic introduces new design variables, add them to the patched parameter block.
3. The OCEAN export script assumes the signal names remain:
   - `/I56/Iout`
   - `/vpre`
   - `/vpre1`
4. The PSF export still uses OCEAN/Virtuoso. Plain Spectre handles simulation, but OCEAN remains responsible for waveform printing.
5. Always check both `check_spectre_runtime` and `check_export_runtime`; they test different executables.
