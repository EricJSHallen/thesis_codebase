#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-prep}" != "prep" ]]; then echo "Usage: $0 prep" >&2; exit 2; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then REPO_DIR="${REPO_DIR:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)}"; else REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"; fi
EXP_DIR="${EXP_DIR:-$REPO_DIR/experiments/frequency_sweep}"
HELPER_DIR="${HELPER_DIR:-$EXP_DIR/scripts/plain_spectre_helpers}"
OCN_DIR="${OCN_DIR:-$EXP_DIR/ocn_scripts}"
SPIKE_DIR="${SPIKE_DIR:-$EXP_DIR/input_data/spike_train_output}"
DATABASE_DIR="${DATABASE_DIR:-$REPO_DIR/database}"
RUN_LABEL="${RUN_LABEL:-2channel_1syn_plain}"
RUN_LABEL_SAFE="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_//;s/_$//')"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_${RUN_LABEL_SAFE}}"
RUN_DIR="${RUN_DIR:-$DATABASE_DIR/$RUN_ID}"
NUM_JOBS="${NUM_JOBS:-4}"
SPECTRE_CMD="${SPECTRE_CMD:-}"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"
SPECTRE_STROBE_PERIOD="${SPECTRE_STROBE_PERIOD:-500u}"
NETLIST_SOURCE="${NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
ADE_E_SOURCE="${ADE_E_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs}"
TEMPLATE_OCN_SRC="${TEMPLATE_OCN_SRC:-$OCN_DIR/make_spectre_template_reorg_v2.ocn}"

need_dir(){ [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_file(){ [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_dir "$EXP_DIR" "frequency_sweep experiment directory"
need_dir "$HELPER_DIR" "plain Spectre helper directory"
need_dir "$SPIKE_DIR" "frequency-sweep spike_train_output directory"
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh extract_missing_outputs.sh export_psf_to_txt.ocn; do need_file "$HELPER_DIR/$f" "helper $f"; done

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/support" "$RUN_DIR/netlist_template/raw" "$RUN_DIR/cases" "$RUN_DIR/worker_state" "$RUN_DIR/ocn"
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh extract_missing_outputs.sh; do cp -f "$HELPER_DIR/$f" "$RUN_DIR/$f"; done
cp -f "$HELPER_DIR/export_psf_to_txt.ocn" "$RUN_DIR/ocn/export_psf_to_txt.ocn"
[[ -f "$TEMPLATE_OCN_SRC" ]] && cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_reorg_v2.ocn"
chmod +x "$RUN_DIR"/*.sh

cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUNINFO
REPO_DIR="$REPO_DIR"
EXP_DIR="$EXP_DIR"
HELPER_DIR="$HELPER_DIR"
OCN_DIR="$OCN_DIR"
SPIKE_DIR="$SPIKE_DIR"
DATABASE_DIR="$DATABASE_DIR"
RUN_DIR="$RUN_DIR"
RUN_ID="$RUN_ID"
RUN_LABEL="$RUN_LABEL"
NUM_JOBS="$NUM_JOBS"
SPECTRE_CMD="$SPECTRE_CMD"
CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
SPECTRE_STROBE_PERIOD="$SPECTRE_STROBE_PERIOD"
NETLIST_SOURCE="$NETLIST_SOURCE"
ADE_E_SOURCE="$ADE_E_SOURCE"
EOF_RUNINFO

python3 - "$SPIKE_DIR" "$RUN_DIR" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1]); run_dir = pathlib.Path(sys.argv[2])
st1_root, st2_root = spike/'st_1', spike/'st_2'
if not st1_root.is_dir() or not st2_root.is_dir(): raise SystemExit(f'ERROR: missing {st1_root} or {st2_root}')
def hz_key(p):
    m=re.search(r'(\d+)_hz', str(p)); return int(m.group(1)) if m else 10**18
def trial_key(p):
    m=re.search(r'trial_(\d+)\.pwl$', p.name); return int(m.group(1)) if m else 10**18
st1_files=sorted(st1_root.glob('*_hz/trial_*.pwl'), key=lambda p:(hz_key(p),trial_key(p)))
st2_files=sorted(st2_root.glob('*_hz/trial_*.pwl'), key=lambda p:(hz_key(p),trial_key(p)))
rows=[]; cid=0
for st1 in st1_files:
    t=trial_key(st1)
    for st2 in st2_files:
        if trial_key(st2) != t: continue
        run_name=f'st1_{hz_key(st1)}_hz__st2_{hz_key(st2)}_hz__trial_{t}'
        rows.append({'case_id':cid,'run_name':run_name,'st1_file':str(st1),'st2_file':str(st2),'case_dir':str(run_dir/'cases'/run_name)})
        cid += 1
with (run_dir/'cases.csv').open('w', newline='') as f:
    w=csv.DictWriter(f, fieldnames=['case_id','run_name','st1_file','st2_file','case_dir']); w.writeheader(); w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES="$(python3 - <<PY
import csv
with open('$RUN_DIR/cases.csv', newline='') as f: print(sum(1 for _ in csv.DictReader(f)))
PY
)"
echo "TOTAL_CASES=\"$TOTAL_CASES\"" >> "$RUN_DIR/RUNINFO.txt"

cat > "$RUN_DIR/select_cases.py" <<'PY'
#!/usr/bin/env python3
import csv, sys
cases_csv, job_idx, num_jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(cases_csv, newline='') as f:
    for row in csv.DictReader(f):
        cid=int(row['case_id'])
        if cid % num_jobs == job_idx:
            print('\t'.join([str(cid), row['run_name'], row['st1_file'], row['st2_file'], row['case_dir']]))
PY
chmod +x "$RUN_DIR/select_cases.py"

cat > "$RUN_DIR/import_template.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
source "$RUN_DIR/RUNINFO.txt"
TEMPLATE="$RUN_DIR/netlist_template/raw"
SRC="${NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
[[ -f "$SRC/input.scs" ]] || { echo "ERROR: cannot find template input.scs at $SRC/input.scs" >&2; exit 1; }
rm -rf "$TEMPLATE"; mkdir -p "$TEMPLATE"; cp -a "$SRC"/. "$TEMPLATE"/
[[ -f "$RUN_DIR/support/ade_e.scs" ]] && cp -f "$RUN_DIR/support/ade_e.scs" "$TEMPLATE/ade_e.scs"
python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
root=pathlib.Path(sys.argv[1])
st1_pat=re.compile(r'"?/home/[^"\s]*?/spike_train_output/st_1/[^"\s]*?\.pwl"?')
st2_pat=re.compile(r'"?/home/[^"\s]*?/spike_train_output/st_2/[^"\s]*?\.pwl"?')
patched=[]
for p in root.rglob('*'):
    if not p.is_file(): continue
    try: s=p.read_text(errors='ignore')
    except Exception: continue
    ns=st1_pat.sub('__ST1_PWL__', s); ns=st2_pat.sub('__ST2_PWL__', ns)
    if ns != s: p.write_text(ns); patched.append(str(p))
for item in patched: print('patched', item)
print(f'patched_files={len(patched)}')
PY
python3 - "$TEMPLATE" "${SPECTRE_STROBE_PERIOD:-500u}" <<'PY'
import pathlib, re, sys
root=pathlib.Path(sys.argv[1]); strobe_period=sys.argv[2]; input_scs=root/'input.scs'
if not input_scs.is_file(): raise SystemExit(f'ERROR: missing {input_scs}')
param_line=('parameters m2w=3u m2l=200n m3w=2.1u m3l=4u m4w=2.1u m4l=1.05u m5w=2.1u m5l=1.05u '
            'm4wtb=2.1u m4ltb=1.05u m2wtb=2.1u m2ltb=1.05u pw=100u T=1m Vin=0 vmax=1.8 '
            'Vw=0.5 Vthr=0.9 Vtau=1.6 capacitance=6p pwlFile_st2=__ST2_PWL__ pwlFile_st1=__ST1_PWL__')
s=input_scs.read_text(errors='ignore')
ns,n=re.subn(r'parameters\b.*?(?=\s+include\s+")', param_line+'\n', s, count=1, flags=re.S)
if n != 1: raise SystemExit('ERROR: could not replace top-level parameters block in input.scs')
# Insert an ideal zero-volt voltage source between I56's output pin and ground.
# This is the standard non-resistive current probe: it does not add a 1-ohm
# shunt or any deliberate voltage drop. The branch current of VSENSE_I56 is
# then exported as the I56 output current.
ns, n_sense = re.subn(
    r'\bI56\s+\(\s*0\s+Vdd\s+Vin\s+Vtau\s+Vthr\s*\)\s+dynapse1\b',
    'VSENSE_I56 (i56_iout 0) vsource dc=0 type=dc\nI56 (i56_iout Vdd Vin Vtau Vthr) dynapse1',
    ns,
    count=1,
)
if n_sense != 1 and 'VSENSE_I56' not in ns:
    raise SystemExit('ERROR: could not insert VSENSE_I56 current probe before I56')

# Request terminal currents in the PSF. This keeps the current-probe branch
# current available to the OCEAN exporter.
if re.search(r'^saveOptions\s+options\b.*$', ns, flags=re.M):
    ns = re.sub(r'^saveOptions\s+options\b.*$', 'saveOptions options save=allpub currents=all', ns, count=1, flags=re.M)
else:
    ns += '\nsaveOptions options save=allpub currents=all\n'

# Save the two voltage nodes and the current-probe branch current. Different
# Spectre/OCEAN versions expose the current name differently, so the exporter
# also probes several possible names robustly.
ns = re.sub(r'^save\s+.*$', 'save vpre vpre1 VSENSE_I56:p VSENSE_I56:n', ns, count=1, flags=re.M) if re.search(r'^save\s+', ns, flags=re.M) else ns + '\nsave vpre vpre1 VSENSE_I56:p VSENSE_I56:n\n'
# Limit saved transient output to a regular grid before OCEAN export.  This is
# the v9 fix for high-frequency cases: Spectre was completing, but ocnPrint
# exceeded the 45 s exporter timeout when PSF contained tens of thousands of
# adaptive solver points.  The solver can still take internal adaptive steps;
# this only regularizes the saved output density.
def add_or_replace_strobe(m):
    line = m.group(0)
    line = re.sub(r'\bstrobeperiod\s*=\s*\S+', 'strobeperiod=' + strobe_period, line)
    if 'strobeperiod=' not in line:
        line = line + ' strobeperiod=' + strobe_period
    return line
ns, n_tran = re.subn(r'^tran\s+tran\b.*$', add_or_replace_strobe, ns, count=1, flags=re.M)
if n_tran != 1:
    raise SystemExit('ERROR: could not patch tran line with strobeperiod')

input_scs.write_text(ns)
(root/'.designVariables').write_text(param_line+'\n')
block=re.search(r'^saveOptions\s+options\b.*$', ns, flags=re.M)
if not block: raise SystemExit('ERROR: saveOptions was not inserted')
if 'VSENSE_I56' not in ns: raise SystemExit('ERROR: VSENSE_I56 was not inserted into input.scs')
if re.search(r'^save\s+.*VSENSE_I56', ns, flags=re.M) is None: raise SystemExit('ERROR: VSENSE_I56 current probe is not in the save statement')
combined='\n'.join(p.read_text(errors='ignore') for p in root.rglob('*') if p.is_file())
if '__ST1_PWL__' not in combined or '__ST2_PWL__' not in combined: raise SystemExit('ERROR: PWL placeholders missing after parameter patch')
print(f'patched parameters in {input_scs}')
print(f'verified saveOptions: {block.group(0)}')
print('verified ideal current probe: VSENSE_I56 (i56_iout 0) vsource dc=0 type=dc')
print('verified current signal save: VSENSE_I56:p / VSENSE_I56:n')
print(f'verified transient strobeperiod: {strobe_period}')
PY
echo "Imported template into $TEMPLATE"
echo "Template placeholders, parameters, and ideal I56 current-probe saving verified."
SH
chmod +x "$RUN_DIR/import_template.sh"

cat > "$RUN_DIR/run_template_ocean.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"; source "$RUN_DIR/RUNINFO.txt"; mkdir -p "$RUN_DIR/logs" "$RUN_DIR/cadence_template_project"
if ! command -v ocean >/dev/null 2>&1; then echo "ocean not found in this shell. Use ciw_template_command.il in CIW instead." >&2; exit 127; fi
CAD_REPO_DIR="$REPO_DIR" CAD_EXP_DIR="$EXP_DIR" CAD_SPIKE_DIR="$SPIKE_DIR" CAD_TEMPLATE_DIR="$RUN_DIR/manual_template_ocean_result" CAD_PROJECT_DIR="$RUN_DIR/cadence_template_project" CAD_BATCH_EXIT=1 ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_reorg_v2.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
SH
chmod +x "$RUN_DIR/run_template_ocean.sh"

cat > "$RUN_DIR/ciw_template_command.il" <<EOF_CIW
setShellEnvVar("CAD_REPO_DIR=$REPO_DIR")
setShellEnvVar("CAD_EXP_DIR=$EXP_DIR")
setShellEnvVar("CAD_SPIKE_DIR=$SPIKE_DIR")
setShellEnvVar("CAD_TEMPLATE_DIR=$RUN_DIR/manual_template_ocean_result")
setShellEnvVar("CAD_PROJECT_DIR=$RUN_DIR/cadence_template_project")
load("$RUN_DIR/ocn/make_spectre_template_reorg_v2.ocn")
EOF_CIW

cat > "$RUN_DIR/monitoring_commands.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-progress}" in
  progress) watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt 2>/dev/null | wc -l; echo -n "done cases: "; grep -R "^DONE case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "DONE case_id=|FAILED case_id=|ERROR|SFE-|spectre completes|output_signals|export_rc|Using current signal|currents=all|Using current signal|VSENSE_I56" "$f" | tail -30; done' ;;
  count) find cases -name output_signals.txt 2>/dev/null | wc -l ;;
  *) echo "Usage: $0 {progress|count}" >&2; exit 2 ;;
esac
SH
chmod +x "$RUN_DIR/monitoring_commands.sh"

[[ -f "$ADE_E_SOURCE" ]] && cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true

echo "=== Plain Spectre frequency sweep reorg v9 prep ==="
echo "Repo:       $REPO_DIR"
echo "Experiment: $EXP_DIR"
echo "Spike dir:  $SPIKE_DIR"
echo "Run dir:    $RUN_DIR"
echo "NUM_JOBS:   $NUM_JOBS"
echo "TOTAL_CASES=$TOTAL_CASES"
echo "SPECTRE_STROBE_PERIOD=$SPECTRE_STROBE_PERIOD"
echo
printf 'Next steps:\n  cd %s\n  ./import_template.sh\n  ./refresh_spectre_runtime.sh\n  source ./setup_spectre_env.sh && check_spectre_runtime && check_export_runtime\n  ./run_all_workers.sh\n  ./monitoring_commands.sh progress\n' "$RUN_DIR"
for f in "$RUN_DIR"/*.sh; do lines=$(wc -l < "$f"); [[ "$lines" -ge 5 ]] || { echo "ERROR: generated $f appears malformed: only $lines lines" >&2; exit 1; }; done
