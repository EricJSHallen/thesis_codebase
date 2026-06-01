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
TEMPLATE_OCN_SRC="${TEMPLATE_OCN_SRC:-$OCN_DIR/make_spectre_template_v1.ocn}"

need_dir() { [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_file() { [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

need_dir "$EXP_DIR" "frequency_sweep experiment directory"
need_dir "$HELPER_DIR" "plain Spectre helper directory"
need_dir "$SPIKE_DIR" "frequency-sweep spike_train_output directory"
need_file "$TEMPLATE_OCN_SRC" "make_spectre_template_v1.ocn"
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh export_psf_to_txt.ocn; do
  need_file "$HELPER_DIR/$f" "helper $f"
done

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/support" "$RUN_DIR/netlist_template/raw" "$RUN_DIR/cases" "$RUN_DIR/worker_state" "$RUN_DIR/ocn"

cat > "$RUN_DIR/RUNINFO.txt" <<INFO
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
TOTAL_CASES=""
INFO

cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_v1.ocn"
cp -f "$HELPER_DIR/export_psf_to_txt.ocn" "$RUN_DIR/ocn/export_psf_to_txt.ocn"
cp -f "$HELPER_DIR/setup_spectre_env.sh" "$RUN_DIR/setup_spectre_env.sh"
cp -f "$HELPER_DIR/refresh_spectre_runtime.sh" "$RUN_DIR/refresh_spectre_runtime.sh"
cp -f "$HELPER_DIR/run_spectre_worker.sh" "$RUN_DIR/run_spectre_worker.sh"
cp -f "$HELPER_DIR/run_all_workers.sh" "$RUN_DIR/run_all_workers.sh"
cp -f "$HELPER_DIR/run_export_case.sh" "$RUN_DIR/run_export_case.sh"
chmod +x "$RUN_DIR"/*.sh
[[ -f "$ADE_E_SOURCE" ]] && cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true

python3 - "$SPIKE_DIR" "$RUN_DIR/cases.csv" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
st1_root = spike / 'st_1'
st2_root = spike / 'st_2'

def hz_key(p):
    m = re.search(r'(\d+)\s*_?hz', p.name, re.I)
    return int(m.group(1)) if m else p.name

def trial_key(p):
    m = re.search(r'trial[_-]?(\d+)', p.name, re.I)
    return int(m.group(1)) if m else p.stem

st1_files = sorted(st1_root.glob('*/*trial*.pwl'), key=lambda p:(hz_key(p.parent), trial_key(p)))
st2_files = sorted(st2_root.glob('*/*trial*.pwl'), key=lambda p:(hz_key(p.parent), trial_key(p)))
st2_by_trial = {}
for p in st2_files:
    st2_by_trial.setdefault(trial_key(p), []).append(p)
rows=[]
cid=0
for s1 in st1_files:
    t = trial_key(s1)
    for s2 in st2_by_trial.get(t, []):
        st1_hz = hz_key(s1.parent); st2_hz = hz_key(s2.parent)
        run_name = f'st1_{st1_hz}_hz__st2_{st2_hz}_hz__trial_{t}'
        case_dir = out.parent / 'cases' / run_name
        rows.append({'case_id': cid, 'run_name': run_name, 'st1_file': str(s1), 'st2_file': str(s2), 'case_dir': str(case_dir)})
        cid += 1
with out.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['case_id','run_name','st1_file','st2_file','case_dir'])
    w.writeheader(); w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES=$(($(wc -l < "$RUN_DIR/cases.csv") - 1))
sed -i "s|TOTAL_CASES=\"\"|TOTAL_CASES=\"$TOTAL_CASES\"|" "$RUN_DIR/RUNINFO.txt"

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
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
TEMPLATE="$RUN_DIR/netlist_template/raw"
SRC="${NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
if [[ ! -f "$SRC/input.scs" ]]; then
  echo "ERROR: cannot find template input.scs at $SRC/input.scs" >&2
  echo "Run one Cadence/OCEAN netlist first, or set NETLIST_SOURCE=/path/to/netlist." >&2
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
    try:
        s = p.read_text(errors='ignore')
    except Exception:
        continue
    ns = st1_pat.sub('__ST1_PWL__', s)
    ns = st2_pat.sub('__ST2_PWL__', ns)
    if ns != s:
        p.write_text(ns)
        patched.append(str(p))
for item in patched:
    print('patched', item)
print(f'patched_files={len(patched)}')
PY
python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
input_scs = root / 'input.scs'
if not input_scs.is_file():
    raise SystemExit(f'ERROR: missing {input_scs}')
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
if n != 1:
    raise SystemExit('ERROR: could not replace top-level parameters block in input.scs')
input_scs.write_text(ns)
(root / '.designVariables').write_text(param_line + '\n')
combined = ''
for p in root.rglob('*'):
    if p.is_file():
        try:
            combined += p.read_text(errors='ignore') + '\n'
        except Exception:
            pass
if '__ST1_PWL__' not in combined or '__ST2_PWL__' not in combined:
    raise SystemExit('ERROR: PWL placeholders missing after parameter patch')
block = re.search(r'parameters\b.*?(?=\s+include\s+")', input_scs.read_text(errors='ignore'), flags=re.S).group(0)
for token in ['m2w ', 'm2l ', 'm2wtb ', 'Vw ', 'Vthr ', 'Vtau ', 'capacitance ']:
    if token in block:
        raise SystemExit(f'ERROR: unresolved bare parameter remains in parameter block: {token!r}')
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
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$RUN_DIR/RUNINFO.txt"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/cadence_template_project"
if ! command -v ocean >/dev/null 2>&1; then
  echo "ocean not found in this shell. Use ciw_template_command.il in CIW instead." >&2
  exit 127
fi
CAD_REPO_DIR="$REPO_DIR" \
CAD_SPIKE_DIR="$SPIKE_DIR" \
CAD_TEMPLATE_DIR="$RUN_DIR/manual_template_ocean_result" \
CAD_PROJECT_DIR="$RUN_DIR/cadence_template_project" \
CAD_BATCH_EXIT=1 \
ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_v1.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
SH
chmod +x "$RUN_DIR/run_template_ocean.sh"

cat > "$RUN_DIR/ciw_template_command.il" <<SH
; Paste this into CIW if ./run_template_ocean.sh says ocean is not found.
ipcBeginProcess("sh -c 'cd $RUN_DIR && ./run_template_ocean.sh'")
SH

cat > "$RUN_DIR/monitoring_commands.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-progress}" in
  progress)
    watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt 2>/dev/null | wc -l; echo -n "done cases: "; grep -R "^DONE case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "SPECTRE_CMD=|DONE case_id=|FAILED case_id=|ERROR|SFE-|spectre completes|output_signals|export_rc" "$f" | tail -20; done'
    ;;
  count)
    find cases -name output_signals.txt 2>/dev/null | wc -l
    ;;
  *)
    echo "Usage: $0 {progress|count}" >&2
    exit 2
    ;;
esac
SH
chmod +x "$RUN_DIR/monitoring_commands.sh"

cat <<MSG
=== Plain Spectre frequency_sweep prep reorg v1 ===
Repo:        $REPO_DIR
Experiment:  $EXP_DIR
Spike dir:   $SPIKE_DIR
Run dir:     $RUN_DIR
NUM_JOBS:    $NUM_JOBS
TOTAL_CASES: $TOTAL_CASES

Next steps:
  cd $RUN_DIR
  ./run_template_ocean.sh     # optional; or paste ciw_template_command.il into CIW
  ./import_template.sh
  ./refresh_spectre_runtime.sh
  source ./setup_spectre_env.sh && check_spectre_runtime
  ./run_all_workers.sh
  ./monitoring_commands.sh progress
MSG
