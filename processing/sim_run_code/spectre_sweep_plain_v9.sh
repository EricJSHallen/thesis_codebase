#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-prep}"
if [ "$cmd" != "prep" ]; then
  echo "Usage: $0 prep" >&2
  exit 2
fi

REPO_DIR="${REPO_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER_DIR="${HELPER_DIR:-$SCRIPT_DIR/plain_spectre_helpers_v9}"
SPIKE_DIR="${SPIKE_DIR:-$REPO_DIR/processing/sim_run_code/spike_train_output}"
NUM_JOBS="${NUM_JOBS:-4}"
RUN_LABEL="${RUN_LABEL:-2channel_1syn_plain}"
RUN_ID="$(date +%Y%m%d_%H%M%S)_${RUN_LABEL}"
RUN_DIR="${RUN_DIR:-$REPO_DIR/thesis_database/$RUN_ID}"
SPECTRE_CMD="${SPECTRE_CMD:-}"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"
CADENCE_SEARCH_ROOT="${CADENCE_SEARCH_ROOT:-/projects/bics/cadence}"
TEMPLATE_OCN_SRC="${TEMPLATE_OCN_SRC:-$REPO_DIR/processing/sim_run_code/ocn_scripts/make_spectre_template_v1.ocn}"
EXPORT_OCN_SRC="${EXPORT_OCN_SRC:-$REPO_DIR/processing/sim_run_code/ocn_scripts/export_psf_to_txt_v1.ocn}"
ADE_E_SOURCE="${ADE_E_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs}"

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/support" "$RUN_DIR/ocn" "$RUN_DIR/cases" "$RUN_DIR/worker_state" "$RUN_DIR/netlist_template/raw"

cat > "$RUN_DIR/RUNINFO.txt" <<INFO
REPO_DIR="$REPO_DIR"
SPIKE_DIR="$SPIKE_DIR"
RUN_DIR="$RUN_DIR"
NUM_JOBS="$NUM_JOBS"
RUN_LABEL="$RUN_LABEL"
SPECTRE_CMD="$SPECTRE_CMD"
CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
CADENCE_SEARCH_ROOT="$CADENCE_SEARCH_ROOT"
ADE_E_SOURCE="$ADE_E_SOURCE"
TOTAL_CASES=""
INFO

cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_v1.ocn"
cp -f "$EXPORT_OCN_SRC" "$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"
[ -f "$ADE_E_SOURCE" ] && cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true

echo "=== Plain Spectre sweep prep v9 ==="
echo "Repo:        $REPO_DIR"
echo "Spike dir:   $SPIKE_DIR"
echo "Run dir:     $RUN_DIR"
echo "NUM_JOBS:    $NUM_JOBS"
echo "Spectre cmd: ${SPECTRE_CMD:-auto}"
echo "Helper dir:  $HELPER_DIR"

python3 - "$SPIKE_DIR" "$RUN_DIR/cases.csv" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
st1_root = spike / "st_1"
st2_root = spike / "st_2"

def hz_key(p):
    m = re.search(r'(\d+)\s*_?hz', p.name, re.I)
    return int(m.group(1)) if m else None

def trial_key(p):
    m = re.search(r'trial[_-]?(\d+)', p.name, re.I)
    return int(m.group(1)) if m else None

st1 = sorted([p for p in st1_root.rglob('trial*.pwl')], key=lambda p: (hz_key(p.parent) or -1, trial_key(p) or -1))
st2 = sorted([p for p in st2_root.rglob('trial*.pwl')], key=lambda p: (hz_key(p.parent) or -1, trial_key(p) or -1))
rows=[]
cid=0
for a in st1:
    h1=hz_key(a.parent); t1=trial_key(a)
    for b in st2:
        h2=hz_key(b.parent); t2=trial_key(b)
        if t1 != t2:
            continue
        run_name=f"st1_{h1}_hz__st2_{h2}_hz__trial_{t1}"
        rows.append({"case_id":cid,"run_name":run_name,"st1_file":str(a),"st2_file":str(b),"case_dir":""})
        cid += 1
for r in rows:
    r["case_dir"] = str(out.parent / "cases" / r["run_name"])
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', newline='') as f:
    w=csv.DictWriter(f, fieldnames=["case_id","run_name","st1_file","st2_file","case_dir"])
    w.writeheader(); w.writerows(rows)
print(len(rows))
PY

TOTAL_CASES=$(($(wc -l < "$RUN_DIR/cases.csv") - 1))
sed -i "s|TOTAL_CASES=\"\"|TOTAL_CASES=\"$TOTAL_CASES\"|" "$RUN_DIR/RUNINFO.txt"
echo "TOTAL_CASES=$TOTAL_CASES"

# Copy stable helper scripts instead of generating them dynamically.
if [ ! -d "$HELPER_DIR" ]; then
  echo "ERROR: missing helper directory: $HELPER_DIR" >&2
  echo "Create it and copy the v9 helper scripts there." >&2
  exit 1
fi
for f in setup_spectre_env.sh refresh_spectre_runtime.sh run_spectre_worker.sh run_all_workers.sh; do
  cp -f "$HELPER_DIR/$f" "$RUN_DIR/$f"
  chmod +x "$RUN_DIR/$f"
done

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

cat > "$RUN_DIR/run_template_ocean.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$RUN_DIR/logs"
echo "Running one OCEAN/Virtuoso template generation pass..."
ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_v1.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
SH
chmod +x "$RUN_DIR/run_template_ocean.sh"

cat > "$RUN_DIR/import_template.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
TEMPLATE="$RUN_DIR/netlist_template/raw"
SRC="${NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
if [ ! -f "$SRC/input.scs" ]; then
  echo "ERROR: cannot find template input.scs at $SRC/input.scs" >&2
  echo "Set NETLIST_SOURCE=/path/to/netlist and rerun ./import_template.sh" >&2
  exit 1
fi
rm -rf "$TEMPLATE"; mkdir -p "$TEMPLATE"
cp -a "$SRC"/. "$TEMPLATE"/
[ -f "$RUN_DIR/support/ade_e.scs" ] && cp -f "$RUN_DIR/support/ade_e.scs" "$TEMPLATE/ade_e.scs"
first=$(awk -F, 'NR==2{print $3 "\n" $4}' "$RUN_DIR/cases.csv")
st1=$(echo "$first" | sed -n '1p')
st2=$(echo "$first" | sed -n '2p')
python3 - "$TEMPLATE" "$st1" "$st2" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]); st1=sys.argv[2]; st2=sys.argv[3]
for p in root.rglob('*'):
    if not p.is_file():
        continue
    try:
        s=p.read_text(errors='ignore')
    except Exception:
        continue
    ns=s.replace(st1, '__ST1_PWL__').replace(st2, '__ST2_PWL__')
    if ns != s:
        p.write_text(ns)
        print('patched', p)
PY
echo "Imported template into $TEMPLATE"
grep -RniE 'pwl|__ST1_PWL__|__ST2_PWL__|ade_e' "$TEMPLATE" | head -80 || true
SH
chmod +x "$RUN_DIR/import_template.sh"

cat > "$RUN_DIR/ciw_template_command.il" <<IL
ipcBeginProcess("sh -c 'cd $RUN_DIR && ./run_template_ocean.sh'")
IL

cat > "$RUN_DIR/monitoring_commands.sh" <<'MON'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-progress}" in
  progress)
    watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt 2>/dev/null | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; tail -12 "$f"; done'
    ;;
  *) echo "Usage: $0 progress" ;;
esac
MON
chmod +x "$RUN_DIR/monitoring_commands.sh"

# Validate helper scripts have real lines.
wc -l "$RUN_DIR"/*.sh | tee "$RUN_DIR/logs/generated_script_line_counts.txt"
if [ "$(wc -l < "$RUN_DIR/setup_spectre_env.sh")" -lt 20 ]; then
  echo "ERROR: setup_spectre_env.sh has too few lines after copy" >&2
  exit 1
fi
if [ "$(wc -l < "$RUN_DIR/run_spectre_worker.sh")" -lt 40 ]; then
  echo "ERROR: run_spectre_worker.sh has too few lines after copy" >&2
  exit 1
fi

echo "=== Created run ==="
echo "$RUN_DIR"
echo
echo "Next steps:"
echo "  cd $RUN_DIR"
echo "  ./run_template_ocean.sh     # or load ciw_template_command.il in CIW"
echo "  ./import_template.sh"
echo "  ./refresh_spectre_runtime.sh"
echo "  source ./setup_spectre_env.sh && check_spectre_runtime"
echo "  ./run_all_workers.sh"
echo "  ./monitoring_commands.sh progress"
