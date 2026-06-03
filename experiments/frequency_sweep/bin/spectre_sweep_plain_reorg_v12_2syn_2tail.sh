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
HELPER_DIR="${HELPER_DIR:-$EXP_DIR/scripts/plain_spectre_helpers}"
OCN_DIR="${OCN_DIR:-$EXP_DIR/ocn_scripts}"
SPIKE_DIR="${SPIKE_DIR:-$EXP_DIR/input_data/spike_train_output}"
DATABASE_DIR="${DATABASE_DIR:-$REPO_DIR/database}"
RUN_LABEL="${RUN_LABEL:-2syn_2tail_plain}"
RUN_LABEL_SAFE="$(printf '%s' "$RUN_LABEL" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_//;s/_$//')"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_${RUN_LABEL_SAFE}}"
RUN_DIR="${RUN_DIR:-$DATABASE_DIR/$RUN_ID}"
NUM_JOBS="${NUM_JOBS:-4}"
SPECTRE_CMD="${SPECTRE_CMD:-}"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"

# Two-synapse / 2-tail circuit defaults.
NETLIST_SOURCE="${NETLIST_SOURCE:-/home/s5117909/simulation/dynapsetb1/spectre/schematic/netlist}"
ADE_E_SOURCE="${ADE_E_SOURCE:-/home/s5117909/simulation/dynapsetb1/spectre/schematic/netlist/ade_e.scs}"
TEMPLATE_OCN_SRC="${TEMPLATE_OCN_SRC:-$OCN_DIR/make_spectre_template_reorg_v12_2syn_2tail.ocn}"

need_dir(){ [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_file(){ [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

need_dir "$EXP_DIR" "frequency_sweep experiment directory"
need_dir "$HELPER_DIR" "plain Spectre helper directory"
need_dir "$SPIKE_DIR" "frequency-sweep spike_train_output directory"
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh extract_missing_outputs.sh export_psf_to_txt.ocn; do
  need_file "$HELPER_DIR/$f" "helper $f"
done
need_file "$OCN_DIR/2syn_2tail.ocn" "direct OCEAN script 2syn_2tail.ocn"

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/support" "$RUN_DIR/netlist_template/raw" "$RUN_DIR/cases" "$RUN_DIR/worker_state" "$RUN_DIR/ocn"

for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh run_export_case.sh extract_missing_outputs.sh; do
  cp -f "$HELPER_DIR/$f" "$RUN_DIR/$f"
done
cp -f "$HELPER_DIR/export_psf_to_txt.ocn" "$RUN_DIR/ocn/export_psf_to_txt.ocn"
cp -f "$OCN_DIR/2syn_2tail.ocn" "$RUN_DIR/ocn/2syn_2tail.ocn"
[[ -f "$TEMPLATE_OCN_SRC" ]] && cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_reorg_v12_2syn_2tail.ocn"
chmod +x "$RUN_DIR"/*.sh

python3 - "$SPIKE_DIR" "$RUN_DIR/cases.csv" "$RUN_DIR/cases" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
out_csv = pathlib.Path(sys.argv[2])
cases_root = pathlib.Path(sys.argv[3])
st1 = spike / 'st_1'
st2 = spike / 'st_2'
if not st1.is_dir():
    raise SystemExit(f'ERROR: missing st_1: {st1}')
if not st2.is_dir():
    raise SystemExit(f'ERROR: missing st_2: {st2}')

def safe(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')

rows = []
case_id = 0
for st1_freq in sorted([p for p in st1.iterdir() if p.is_dir()]):
    for st2_freq in sorted([p for p in st2.iterdir() if p.is_dir()]):
        for st1_file in sorted(st1_freq.glob('*.pwl')):
            st2_file = st2_freq / st1_file.name
            if not st2_file.is_file():
                continue
            trial_stem = st1_file.stem
            run_name = f"st1_{safe(st1_freq.name)}__st2_{safe(st2_freq.name)}__{safe(trial_stem)}"
            case_dir = cases_root / run_name
            rows.append({
                'case_id': case_id,
                'run_name': run_name,
                'st1_file': str(st1_file),
                'st2_file': str(st2_file),
                'case_dir': str(case_dir),
            })
            case_id += 1
with out_csv.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['case_id','run_name','st1_file','st2_file','case_dir'])
    w.writeheader()
    w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES="$(($(wc -l < "$RUN_DIR/cases.csv") - 1))"

cat > "$RUN_DIR/RUNINFO.txt" <<EOF
REPO_DIR="$REPO_DIR"
EXP_DIR="$EXP_DIR"
HELPER_DIR="$HELPER_DIR"
OCN_DIR="$OCN_DIR"
SPIKE_DIR="$SPIKE_DIR"
DATABASE_DIR="$DATABASE_DIR"
RUN_ID="$RUN_ID"
RUN_DIR="$RUN_DIR"
NUM_JOBS="$NUM_JOBS"
TOTAL_CASES="$TOTAL_CASES"
SPECTRE_CMD="$SPECTRE_CMD"
CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
NETLIST_SOURCE="$NETLIST_SOURCE"
ADE_E_SOURCE="$ADE_E_SOURCE"
TEMPLATE_OCN_SRC="$TEMPLATE_OCN_SRC"
OUTPUT_COLUMNS="iout_172 iout_56 vpre vpre1"
EOF

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

cat > "$RUN_DIR/import_template.sh" <<'SH2'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck disable=SC1090
source "$RUN_DIR/RUNINFO.txt"
TEMPLATE="$RUN_DIR/netlist_template/raw"
SRC="${NETLIST_SOURCE:-/home/s5117909/simulation/dynapsetb1/spectre/schematic/netlist}"
[[ -f "$SRC/input.scs" ]] || { echo "ERROR: cannot find template input.scs at $SRC/input.scs" >&2; exit 1; }
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
    print('patched PWL placeholder', item)
print(f'pwl_placeholder_patched_files={len(patched)}')
PY
python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
input_scs = root / 'input.scs'
if not input_scs.is_file():
    raise SystemExit(f'ERROR: missing {input_scs}')
param_line = (
    'parameters m2w=3u m2l=200n m3w=2.1u m3l=4u m4w=2.1u m4l=1.05u m5w=2.1u m5l=1.05u '
    'm4wtb=2.1u m4ltb=1.05u m2wtb=2.1u m2ltb=1.05u pw=100u T=1m Vin=0 vmax=1.8 '
    'Vw=0.5 Vthr=0.9 Vtau=1.6 capacitance=6p pwlFile_st2=__ST2_PWL__ pwlFile_st1=__ST1_PWL__'
)
s = input_scs.read_text(errors='ignore')
ns, n = re.subn(r'parameters\b.*?(?=\s+include\s+")', param_line + '\n', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('ERROR: could not replace top-level parameters block in input.scs')

# Insert ideal zero-volt current probes on I172/Iout and I56/Iout when the instance
# line has the common dynapse1 form. This does not add a 1-ohm shunt.
probe_specs = [
    ('I172', 'VSENSE_I172', 'i172_iout'),
    ('I56',  'VSENSE_I56',  'i56_iout'),
]
for inst, sense, node in probe_specs:
    if sense in ns:
        continue
    pat = rf'\b{inst}\s+\(\s*0\s+Vdd\s+Vin\s+Vtau\s+Vthr\s*\)\s+dynapse1\b'
    repl = f'{sense} ({node} 0) vsource dc=0 type=dc\n{inst} ({node} Vdd Vin Vtau Vthr) dynapse1'
    ns, changed = re.subn(pat, repl, ns, count=1)
    if changed == 0:
        print(f'WARNING: could not insert {sense}; exporter will try original {inst}/Iout current names.')
    else:
        print(f'inserted ideal current probe {sense}')

if re.search(r'^saveOptions\s+options\b.*$', ns, flags=re.M):
    ns = re.sub(r'^saveOptions\s+options\b.*$', 'saveOptions options save=allpub currents=all', ns, count=1, flags=re.M)
else:
    ns += '\nsaveOptions options save=allpub currents=all\n'

save_line = 'save vpre vpre1 VSENSE_I172:p VSENSE_I172:n VSENSE_I56:p VSENSE_I56:n I172:Iout I56:Iout'
if re.search(r'^save\s+', ns, flags=re.M):
    ns = re.sub(r'^save\s+.*$', save_line, ns, count=1, flags=re.M)
else:
    ns += '\n' + save_line + '\n'

ns = re.sub(r'\bstrobeperiod\s*=\s*\S+', '', ns)
if 'strobeperiod' in ns.lower():
    raise SystemExit('ERROR: strobeperiod still present after removal')
input_scs.write_text(ns)
(root / '.designVariables').write_text(param_line + '\n')
combined = '\n'.join(p.read_text(errors='ignore') for p in root.rglob('*') if p.is_file())
if '__ST1_PWL__' not in combined or '__ST2_PWL__' not in combined:
    raise SystemExit('ERROR: PWL placeholders missing after parameter patch')
print(f'patched parameters in {input_scs}')
print('verified saveOptions options save=allpub currents=all')
print('verified output columns: iout_172 iout_56 vpre vpre1')
print('verified no transient strobeperiod: full adaptive-output data will be exported')
PY
echo "Imported template into $TEMPLATE"
echo "Template placeholders, parameters, saveOptions, and two-current export support verified."
SH2
chmod +x "$RUN_DIR/import_template.sh"

cat > "$RUN_DIR/monitoring_commands.sh" <<'SH3'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-progress}" in
  progress)
    watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt 2>/dev/null | wc -l; echo -n "done cases: "; grep -R "^DONE case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "DONE case_id=|FAILED case_id=|ERROR|SFE-|spectre completes|output_signals|export|I172|I56|VSENSE" "$f" | tail -30; done'
    ;;
  count)
    find cases -name output_signals.txt 2>/dev/null | wc -l
    ;;
  *)
    echo "Usage: $0 {progress|count}" >&2
    exit 2
    ;;
esac
SH3
chmod +x "$RUN_DIR/monitoring_commands.sh"

[[ -f "$ADE_E_SOURCE" ]] && cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true

echo "=== Plain Spectre frequency sweep reorg v12 2syn_2tail prep ==="
echo "Repo: $REPO_DIR"
echo "Experiment: $EXP_DIR"
echo "Spike dir: $SPIKE_DIR"
echo "Run dir: $RUN_DIR"
echo "NUM_JOBS: $NUM_JOBS"
echo "TOTAL_CASES=$TOTAL_CASES"
echo "Output columns: iout_172 iout_56 vpre vpre1"
printf 'Next steps:\n cd %s\n ./import_template.sh\n ./refresh_spectre_runtime.sh\n source ./setup_spectre_env.sh && check_spectre_runtime && check_export_runtime\n ./run_all_workers.sh\n ./monitoring_commands.sh progress\n' "$RUN_DIR"

for f in "$RUN_DIR"/*.sh; do
  lines=$(wc -l < "$f")
  [[ "$lines" -ge 5 ]] || { echo "ERROR: generated $f appears malformed: only $lines lines" >&2; exit 1; }
done
