#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-prep}" != "prep" ]]; then
  echo "Usage: $0 prep" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO_DIR="${REPO_DIR:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)}"
else
  REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"
fi

EXP_DIR="${EXP_DIR:-$REPO_DIR/experiments/frequency_sweep}"
BIN_DIR="${BIN_DIR:-$EXP_DIR/bin}"
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
NETLIST_SOURCE="${NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
ADE_E_SOURCE="${ADE_E_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs}"
TEMPLATE_OCN_SRC="${TEMPLATE_OCN_SRC:-$OCN_DIR/make_spectre_template_reorg_v2.ocn}"

need_dir() { [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_file() { [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

need_dir "$EXP_DIR" "frequency_sweep experiment directory"
need_dir "$HELPER_DIR" "plain Spectre helper directory"
need_dir "$SPIKE_DIR" "frequency-sweep spike_train_output directory"
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh extract_missing_outputs.sh export_psf_to_txt.ocn; do
  need_file "$HELPER_DIR/$f" "helper $f"
done

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/support" "$RUN_DIR/netlist_template/raw" "$RUN_DIR/cases" "$RUN_DIR/worker_state" "$RUN_DIR/ocn"
cp -f "$HELPER_DIR/setup_spectre_env.sh" "$RUN_DIR/setup_spectre_env.sh"
cp -f "$HELPER_DIR/refresh_spectre_runtime.sh" "$RUN_DIR/refresh_spectre_runtime.sh"
cp -f "$HELPER_DIR/run_spectre_worker.sh" "$RUN_DIR/run_spectre_worker.sh"
cp -f "$HELPER_DIR/run_all_workers.sh" "$RUN_DIR/run_all_workers.sh"
cp -f "$HELPER_DIR/run_export_case.sh" "$RUN_DIR/run_export_case.sh"
cp -f "$HELPER_DIR/extract_missing_outputs.sh" "$RUN_DIR/extract_missing_outputs.sh"
cp -f "$HELPER_DIR/export_psf_to_txt.ocn" "$RUN_DIR/ocn/export_psf_to_txt.ocn"
if [[ -f "$TEMPLATE_OCN_SRC" ]]; then
  cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_reorg_v2.ocn"
fi
chmod +x "$RUN_DIR"/*.sh

cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUNINFO
REPO_DIR="$REPO_DIR"
EXP_DIR="$EXP_DIR"
BIN_DIR="$BIN_DIR"
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
NETLIST_SOURCE="$NETLIST_SOURCE"
ADE_E_SOURCE="$ADE_E_SOURCE"
EOF_RUNINFO

python3 - "$SPIKE_DIR" "$RUN_DIR" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
run_dir = pathlib.Path(sys.argv[2])
st1_root = spike / 'st_1'
st2_root = spike / 'st_2'
if not st1_root.is_dir() or not st2_root.is_dir():
    raise SystemExit(f'ERROR: missing {st1_root} or {st2_root}')

def hz_key(p):
    m = re.search(r'(\d+)_hz', str(p))
    return int(m.group(1)) if m else 10**18

def trial_key(p):
    m = re.search(r'trial_(\d+)\.pwl$', p.name)
    return int(m.group(1)) if m else 10**18

st1_files = sorted(st1_root.glob('*_hz/trial_*.pwl'), key=lambda p: (hz_key(p), trial_key(p)))
st2_files = sorted(st2_root.glob('*_hz/trial_*.pwl'), key=lambda p: (hz_key(p), trial_key(p)))
if not st1_files or not st2_files:
    raise SystemExit('ERROR: no st_1/st_2 trial_*.pwl files found')

# Pair by matching trial number. This keeps the current experiment at one trial-comparable case per frequency pair.
rows = []
case_id = 0
for st1 in st1_files:
    t1 = trial_key(st1)
    for st2 in st2_files:
        if trial_key(st2) != t1:
            continue
        run_name = f"st1_{hz_key(st1)}_hz__st2_{hz_key(st2)}_hz__trial_{t1}"
        rows.append({
            'case_id': case_id,
            'run_name': run_name,
            'st1_file': str(st1),
            'st2_file': str(st2),
            'case_dir': str(run_dir / 'cases' / run_name),
        })
        case_id += 1

with (run_dir / 'cases.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['case_id','run_name','st1_file','st2_file','case_dir'])
    w.writeheader(); w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES="$(python3 - <<PY
import csv
with open('$RUN_DIR/cases.csv', newline='') as f:
    print(sum(1 for _ in csv.DictReader(f)))
PY
)"
echo "TOTAL_CASES=\"$TOTAL_CASES\"" >> "$RUN_DIR/RUNINFO.txt"

cat > "$RUN_DIR/select_cases.py" <<'PY'
#!/usr/bin/env python3
import csv, sys
cases_csv, job_idx, num_jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(cases_csv, newline='') as f:
    for row in csv.DictReader(f):
        cid = int(row['case_id'])
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
if [[ ! -f "$SRC/input.scs" ]]; then
  echo "ERROR: cannot find template input.scs at $SRC/input.scs" >&2
  exit 1
fi
rm -rf "$TEMPLATE"
mkdir -p "$TEMPLATE"
cp -a "$SRC"/. "$TEMPLATE"/
[[ -f "$RUN_DIR/support/ade_e.scs" ]] && cp -f "$RUN_DIR/support/ade_e.scs" "$TEMPLATE/ade_e.scs"

python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
st1_pat = re.compile(r'"?/home/[^"\s]*?/spike_train_output/st_1/[^"\s]*?\.pwl"?')
st2_pat = re.compile(r'"?/home/[^"\s]*?/spike_train_output/st_2/[^"\s]*?\.pwl"?')
patched = []
for p in root.rglob('*'):
    if not p.is_file():
        continue
    try: s = p.read_text(errors='ignore')
    except Exception: continue
    ns = st1_pat.sub('__ST1_PWL__', s)
    ns = st2_pat.sub('__ST2_PWL__', ns)
    if ns != s:
        p.write_text(ns); patched.append(str(p))
for item in patched: print('patched', item)
print(f'patched_files={len(patched)}')
PY

python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
input_scs = root / 'input.scs'
if not input_scs.is_file(): raise SystemExit(f'ERROR: missing {input_scs}')
param_line = (
    'parameters '
    'm2w=3u m2l=200n '
    'm3w=2.1u m3l=4u '
    'm4w=2.1u m4l=1.05u '
    'm5w=2.1u m5l=1.05u '
    'm4wtb=2.1u m4ltb=1.05u '
    'm2wtb=2.1u m2ltb=1.05u '
    'pw=100u T=1m Vin=0 vmax=1.8 '
    'Vw=0.5 Vthr=0.9 Vtau=1.6 '
    'capacitance=6p '
    'pwlFile_st2=__ST2_PWL__ '
    'pwlFile_st1=__ST1_PWL__'
)
s = input_scs.read_text(errors='ignore')
ns, n = re.subn(r'parameters\b.*?(?=\s+include\s+")', param_line + '\n', s, count=1, flags=re.S)
if n != 1: raise SystemExit('ERROR: could not replace top-level parameters block in input.scs')
input_scs.write_text(ns)
(root / '.designVariables').write_text(param_line + '\n')
combined = ''
for p in root.rglob('*'):
    if p.is_file():
        try: combined += p.read_text(errors='ignore') + '\n'
        except Exception: pass
if '__ST1_PWL__' not in combined or '__ST2_PWL__' not in combined:
    raise SystemExit('ERROR: PWL placeholders missing after parameter patch')
block = re.search(r'parameters\b.*?(?=\s+include\s+")', input_scs.read_text(errors='ignore'), flags=re.S).group(0)
for token in ['m2w ', 'm2l ', 'm2wtb ', 'Vw ', 'Vthr ', 'Vtau ', 'capacitance ']:
    if token in block: raise SystemExit(f'ERROR: unresolved bare parameter remains in parameter block: {token!r}')
print(f'patched parameters in {input_scs}')
print('template parameter block verified')
PY

echo "Imported template into $TEMPLATE"
echo "Template placeholders and parameters verified."
SH
chmod +x "$RUN_DIR/import_template.sh"

cat > "$RUN_DIR/run_template_ocean.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/cadence_template_project"
if ! command -v ocean >/dev/null 2>&1; then
  echo "ocean not found in this shell. Use ciw_template_command.il in CIW instead." >&2
  exit 127
fi
CAD_REPO_DIR="$REPO_DIR" \
CAD_EXP_DIR="$EXP_DIR" \
CAD_SPIKE_DIR="$SPIKE_DIR" \
CAD_TEMPLATE_DIR="$RUN_DIR/manual_template_ocean_result" \
CAD_PROJECT_DIR="$RUN_DIR/cadence_template_project" \
CAD_BATCH_EXIT=1 \
ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_reorg_v2.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
SH
chmod +x "$RUN_DIR/run_template_ocean.sh"

cat > "$RUN_DIR/ciw_template_command.il" <<EOF_CIW
; Paste this into the Cadence CIW if ./run_template_ocean.sh cannot find ocean.
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
  progress)
    watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt 2>/dev/null | wc -l; echo -n "done cases: "; grep -R "^DONE case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "SPECTRE_CMD=|CADENCE_EXPORT_LAUNCHER=|DONE case_id=|FAILED case_id=|ERROR|SFE-|spectre completes|output_signals|export_rc|lib.*not found" "$f" | tail -30; done'
    ;;
  count) find cases -name output_signals.txt 2>/dev/null | wc -l ;;
  *) echo "Usage: $0 {progress|count}" >&2; exit 2 ;;
esac
SH
chmod +x "$RUN_DIR/monitoring_commands.sh"

# Copy ADE include if present.
if [[ -f "$ADE_E_SOURCE" ]]; then
  cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true
fi

printf '=== Plain Spectre frequency sweep reorg v3 prep ===\n'
printf 'Repo:       %s\n' "$REPO_DIR"
printf 'Experiment: %s\n' "$EXP_DIR"
printf 'Spike dir:  %s\n' "$SPIKE_DIR"
printf 'Run dir:    %s\n' "$RUN_DIR"
printf 'NUM_JOBS:   %s\n' "$NUM_JOBS"
printf 'TOTAL_CASES=%s\n' "$TOTAL_CASES"
printf '\nNext steps:\n'
printf '  cd %s\n' "$RUN_DIR"
printf '  ./import_template.sh\n'
printf '  ./refresh_spectre_runtime.sh\n'
printf '  source ./setup_spectre_env.sh && check_spectre_runtime && check_export_runtime\n'
printf '  ./run_all_workers.sh\n'
printf '  ./monitoring_commands.sh progress\n'

# Guard against newline collapse.
for f in "$RUN_DIR"/*.sh; do
  lines=$(wc -l < "$f")
  if [[ "$lines" -lt 5 ]]; then
    echo "ERROR: generated $f appears malformed: only $lines lines" >&2
    exit 1
  fi
done
