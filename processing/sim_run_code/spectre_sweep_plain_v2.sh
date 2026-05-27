#!/usr/bin/env bash
set -euo pipefail

# spectre_sweep_plain_v2.sh
# Single-OCEAN-template + parallel plain-Spectre pipeline.
# Fixes: Spectre LD_LIBRARY_PATH setup and BrokenPipe/early-worker-exit logic.

MODE="${1:-prep}"
SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

if git -C "$SCRIPT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO_DIR="${REPO_DIR:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)}"
else
  REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
fi

SIM_RUN_DIR="$REPO_DIR/processing/sim_run_code"
OCN_SRC_DIR="$SIM_RUN_DIR/ocn_scripts"
SPIKE_DIR="${CAD_SPIKE_DIR:-$SIM_RUN_DIR/spike_train_output}"
ST1_DIR="$SPIKE_DIR/st_1"
ST2_DIR="$SPIKE_DIR/st_2"
DB_DIR="$REPO_DIR/thesis_database"
NUM_JOBS="${NUM_JOBS:-4}"
RUN_LABEL="${RUN_LABEL:-2channel_1syn_plain_spectre}"
TS="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${RUN_ID:-${TS}_${RUN_LABEL}}"
RUN_DIR="${RUN_DIR:-$DB_DIR/$RUN_ID}"

OCEAN_TEMPLATE_OCN_SRC="${OCEAN_TEMPLATE_OCN_SRC:-$OCN_SRC_DIR/make_spectre_template_v1.ocn}"
EXPORT_OCN_SRC="${EXPORT_OCN_SRC:-$OCN_SRC_DIR/export_psf_to_txt_v1.ocn}"
ADE_E_SOURCE="${ADE_E_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs}"
CADENCE_NETLIST_SOURCE="${CADENCE_NETLIST_SOURCE:-/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist}"
DEFAULT_SPECTRE_BIN="/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"

if [ -n "${SPECTRE_BIN:-}" ]; then
  DETECTED_SPECTRE_BIN="$SPECTRE_BIN"
elif command -v spectre >/dev/null 2>&1; then
  DETECTED_SPECTRE_BIN="$(command -v spectre)"
elif [ -x "$DEFAULT_SPECTRE_BIN" ]; then
  DETECTED_SPECTRE_BIN="$DEFAULT_SPECTRE_BIN"
else
  DETECTED_SPECTRE_BIN=""
fi

case "$MODE" in
  prep)
    echo "=== Plain Spectre sweep prep v2 ==="
    echo "Repo:        $REPO_DIR"
    echo "Spike dir:   $SPIKE_DIR"
    echo "Run dir:     $RUN_DIR"
    echo "NUM_JOBS:    $NUM_JOBS"
    echo "Spectre bin: ${DETECTED_SPECTRE_BIN:-NOT FOUND}"

    [ -d "$ST1_DIR" ] || { echo "ERROR: missing $ST1_DIR" >&2; exit 1; }
    [ -d "$ST2_DIR" ] || { echo "ERROR: missing $ST2_DIR" >&2; exit 1; }
    [ -f "$OCEAN_TEMPLATE_OCN_SRC" ] || { echo "ERROR: missing $OCEAN_TEMPLATE_OCN_SRC" >&2; exit 1; }
    [ -f "$EXPORT_OCN_SRC" ] || { echo "ERROR: missing $EXPORT_OCN_SRC" >&2; exit 1; }
    [ -n "$DETECTED_SPECTRE_BIN" ] || { echo "ERROR: Could not find Spectre. Set SPECTRE_BIN explicitly." >&2; exit 1; }

    mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/ocn" "$RUN_DIR/support" \
             "$RUN_DIR/netlist_template" "$RUN_DIR/cases" "$RUN_DIR/worker_state" \
             "$RUN_DIR/template_ocean_result" "$RUN_DIR/template_project"

    cp "$OCEAN_TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_v1.ocn"
    cp "$EXPORT_OCN_SRC" "$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"

    if [ -f "$ADE_E_SOURCE" ]; then
      cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs"
    else
      echo "WARNING: ADE_E_SOURCE not found: $ADE_E_SOURCE" >&2
    fi

    cat > "$RUN_DIR/RUNINFO.txt" <<INFO
RUN_ID=$RUN_ID
REPO_DIR=$REPO_DIR
SPIKE_DIR=$SPIKE_DIR
ST1_DIR=$ST1_DIR
ST2_DIR=$ST2_DIR
NUM_JOBS=$NUM_JOBS
RUN_DIR=$RUN_DIR
CADENCE_NETLIST_SOURCE=$CADENCE_NETLIST_SOURCE
ADE_E_SOURCE=$ADE_E_SOURCE
SPECTRE_BIN=$DETECTED_SPECTRE_BIN
ARCHITECTURE=single_ocean_template_then_parallel_plain_spectre_v2
INFO

    echo "=== Building cases.csv ==="
    python3 - "$ST1_DIR" "$ST2_DIR" "$RUN_DIR/cases.csv" "$RUN_DIR/cases" <<'PY'
import csv, pathlib, re, sys
st1 = pathlib.Path(sys.argv[1])
st2 = pathlib.Path(sys.argv[2])
out_csv = pathlib.Path(sys.argv[3])
cases_root = pathlib.Path(sys.argv[4])

def natural_key(path):
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', path.name)]

def freq_dirs(base):
    return sorted([p for p in base.iterdir() if p.is_dir()], key=natural_key)

def trial_num(path):
    m = re.search(r"trial_(\d+)\.pwl$", path.name)
    return int(m.group(1)) if m else 10**12

rows = []
case_id = 0
for st1_fd in freq_dirs(st1):
    st1_trials = sorted(st1_fd.glob("*.pwl"), key=trial_num)
    for st2_fd in freq_dirs(st2):
        for st1_file in st1_trials:
            st2_file = st2_fd / st1_file.name
            if not st2_file.is_file():
                continue
            run_name = f"st1_{st1_fd.name}__st2_{st2_fd.name}__{st1_file.stem}"
            rows.append({
                "case_id": case_id,
                "run_name": run_name,
                "st1_frequency": st1_fd.name,
                "st2_frequency": st2_fd.name,
                "trial_file": st1_file.name,
                "st1_file": str(st1_file),
                "st2_file": str(st2_file),
                "case_dir": str(cases_root / run_name),
            })
            case_id += 1

out_csv.parent.mkdir(parents=True, exist_ok=True)
with out_csv.open("w", newline="") as f:
    fields = ["case_id","run_name","st1_frequency","st2_frequency","trial_file","st1_file","st2_file","case_dir"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print(len(rows))
PY
    TOTAL_CASES="$(($(wc -l < "$RUN_DIR/cases.csv") - 1))"
    echo "TOTAL_CASES=$TOTAL_CASES" | tee -a "$RUN_DIR/RUNINFO.txt"

    cat > "$RUN_DIR/select_cases.py" <<'PY'
import csv, sys
cases_csv, job_index, num_jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(cases_csv, newline="") as f:
    for row in csv.DictReader(f):
        cid = int(row["case_id"])
        if cid % num_jobs == job_index:
            print("\t".join([str(cid), row["run_name"], row["st1_file"], row["st2_file"], row["case_dir"]]), flush=True)
PY

    cat > "$RUN_DIR/setup_spectre_env.sh" <<'SENV'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"

if [ -z "${SPECTRE_BIN:-}" ]; then
  if command -v spectre >/dev/null 2>&1; then
    SPECTRE_BIN="$(command -v spectre)"
  else
    SPECTRE_BIN="/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"
  fi
fi

if [ ! -x "$SPECTRE_BIN" ]; then
  echo "ERROR: SPECTRE_BIN is not executable: $SPECTRE_BIN" >&2
  return 1 2>/dev/null || exit 1
fi

SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
SPECTRE_HOME="$(cd "$SPECTRE_BIN_DIR/../.." && pwd)"
CAD_TOOLS_HOME="$(cd "$SPECTRE_HOME/.." && pwd)"

export SPECTRE_BIN
export PATH="$SPECTRE_BIN_DIR:$PATH"

for d in \
  "$SPECTRE_HOME/lib/64bit" \
  "$SPECTRE_HOME/lib" \
  "$SPECTRE_HOME/tools/64bit/lib" \
  "$CAD_TOOLS_HOME/lib/64bit" \
  "$CAD_TOOLS_HOME/lib" \
  "$CAD_TOOLS_HOME/tools.lnx86/lib/64bit" \
  "$CAD_TOOLS_HOME/tools.lnx86/lib" \
  "/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/lib/64bit" \
  "/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/lib";
do
  if [ -d "$d" ]; then
    case ":${LD_LIBRARY_PATH:-}:" in
      *":$d:"*) ;;
      *) export LD_LIBRARY_PATH="$d:${LD_LIBRARY_PATH:-}" ;;
    esac
  fi
done
SENV
    chmod +x "$RUN_DIR/setup_spectre_env.sh"

    cat > "$RUN_DIR/run_template_ocean.sh" <<RTO
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_DIR"
export CAD_REPO_DIR="$REPO_DIR"
export CAD_SPIKE_DIR="$SPIKE_DIR"
export CAD_TEMPLATE_DIR="$RUN_DIR/template_ocean_result"
export CAD_PROJECT_DIR="$RUN_DIR/template_project"
export CAD_BATCH_EXIT=1

echo "Running one OCEAN/Virtuoso template generation pass..."
ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_v1.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
RTO
    chmod +x "$RUN_DIR/run_template_ocean.sh"

    cat > "$RUN_DIR/import_template.sh" <<'IMPT'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"

SRC="${CADENCE_NETLIST_SOURCE}"
DST="$RUN_DIR/netlist_template/raw"
[ -d "$SRC" ] || { echo "ERROR: netlist source not found: $SRC" >&2; exit 1; }
rm -rf "$DST"
mkdir -p "$DST"
cp -a "$SRC"/. "$DST"/

if [ -f "$RUN_DIR/support/ade_e.scs" ]; then
  cp -f "$RUN_DIR/support/ade_e.scs" "$DST/ade_e.scs"
fi

ST1_TEMPLATE_PATH="$(grep -RhoE '/[^"[:space:]]*/st_1/[^"[:space:]]+\.pwl' "$DST" 2>/dev/null | head -1 || true)"
ST2_TEMPLATE_PATH="$(grep -RhoE '/[^"[:space:]]*/st_2/[^"[:space:]]+\.pwl' "$DST" 2>/dev/null | head -1 || true)"

echo "ST1_TEMPLATE_PATH=$ST1_TEMPLATE_PATH" | tee "$RUN_DIR/netlist_template/template_paths.env"
echo "ST2_TEMPLATE_PATH=$ST2_TEMPLATE_PATH" | tee -a "$RUN_DIR/netlist_template/template_paths.env"

if [ -z "$ST1_TEMPLATE_PATH" ] || [ -z "$ST2_TEMPLATE_PATH" ]; then
  echo "WARNING: Could not find PWL file paths in template." >&2
  echo "Inspect with: grep -RniE 'pwl|st_1|st_2|trial|pwlFile' $DST" >&2
else
  python3 - "$DST" "$ST1_TEMPLATE_PATH" "$ST2_TEMPLATE_PATH" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
st1 = sys.argv[2]
st2 = sys.argv[3]
for p in root.rglob("*"):
    if not p.is_file():
        continue
    try:
        s = p.read_text(errors="ignore")
    except Exception:
        continue
    ns = s.replace(st1, "__ST1_PWL__").replace(st2, "__ST2_PWL__")
    if ns != s:
        p.write_text(ns)
        print(f"patched {p}")
PY
fi

echo "Imported template into: $DST"
echo "Check template with: grep -RniE 'pwl|__ST1_PWL__|__ST2_PWL__|ade_e' $DST | head -80"
IMPT
    chmod +x "$RUN_DIR/import_template.sh"

    cat > "$RUN_DIR/run_spectre_worker.sh" <<'WORKER'
#!/usr/bin/env bash
set -u -o pipefail
JOB_INDEX="${1:?usage: run_spectre_worker.sh JOB_INDEX}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
source "$RUN_DIR/setup_spectre_env.sh"

TEMPLATE="$RUN_DIR/netlist_template/raw"
CASES_CSV="$RUN_DIR/cases.csv"
LOG="$RUN_DIR/logs/spectre_worker_${JOB_INDEX}.log"
STATE="$RUN_DIR/worker_state/job_${JOB_INDEX}.state"
EXPORT_OCN="$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"
ASSIGNED_TSV="$RUN_DIR/worker_state/job_${JOB_INDEX}_cases.tsv"

mkdir -p "$RUN_DIR/worker_state" "$RUN_DIR/logs"
echo "worker=$JOB_INDEX start=$(date -Is)" > "$STATE"
echo "SPECTRE_BIN=$SPECTRE_BIN" > "$LOG"
echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}" >> "$LOG"

if [ ! -d "$TEMPLATE" ]; then
  echo "ERROR: missing template $TEMPLATE. Run ./import_template.sh first." | tee -a "$LOG" >&2
  exit 1
fi

python3 "$RUN_DIR/select_cases.py" "$CASES_CSV" "$JOB_INDEX" "$NUM_JOBS" > "$ASSIGNED_TSV"
total_assigned="$(wc -l < "$ASSIGNED_TSV")"
echo "assigned_cases=$total_assigned" >> "$STATE"
echo "assigned_cases=$total_assigned" >> "$LOG"

while IFS=$'\t' read -r case_id run_name st1_file st2_file case_dir; do
  {
    echo "========== case_id=$case_id run_name=$run_name =========="
    echo "case_dir=$case_dir"
    mkdir -p "$case_dir"

    if [ -f "$case_dir/output_signals.txt" ]; then
      echo "SKIP existing output_signals.txt"
      continue
    fi

    rm -rf "$case_dir/netlist" "$case_dir/psf"
    mkdir -p "$case_dir/netlist"
    cp -a "$TEMPLATE"/. "$case_dir/netlist"/

    if [ -f "$RUN_DIR/support/ade_e.scs" ]; then
      cp -f "$RUN_DIR/support/ade_e.scs" "$case_dir/netlist/ade_e.scs"
    fi

    python3 - "$case_dir/netlist" "$st1_file" "$st2_file" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
st1 = sys.argv[2]
st2 = sys.argv[3]
changed = 0
for p in root.rglob("*"):
    if not p.is_file():
        continue
    try:
        s = p.read_text(errors="ignore")
    except Exception:
        continue
    ns = s.replace("__ST1_PWL__", st1).replace("__ST2_PWL__", st2)
    ns = re.sub(r'(pwlFile_st1\s*=\s*)"[^"]*"', r'\1"' + st1 + '"', ns)
    ns = re.sub(r'(pwlFile_st2\s*=\s*)"[^"]*"', r'\1"' + st2 + '"', ns)
    if ns != s:
        p.write_text(ns)
        changed += 1
print(f"patched_files={changed}")
PY

    if [ ! -f "$case_dir/netlist/input.scs" ]; then
      echo "FAILED case_id=$case_id run_name=$run_name case_dir=$case_dir reason=missing_input_scs"
      continue
    fi

    (
      cd "$case_dir/netlist"
      "$SPECTRE_BIN" input.scs +escchars +log "$case_dir/spectre.out" -format psfxl -raw "$case_dir/psf"
    )
    spectre_rc=$?
    if [ "$spectre_rc" -ne 0 ]; then
      echo "FAILED case_id=$case_id run_name=$run_name case_dir=$case_dir reason=spectre_rc_$spectre_rc"
      continue
    fi

    CAD_CASE_DIR="$case_dir" CAD_BATCH_EXIT=1 ocean -nograph -restore "$EXPORT_OCN" > "$case_dir/export_ocean.log" 2>&1
    export_rc=$?
    if [ "$export_rc" -ne 0 ]; then
      echo "FAILED case_id=$case_id run_name=$run_name case_dir=$case_dir reason=export_rc_$export_rc"
      continue
    fi

    if [ -f "$case_dir/output_signals.txt" ]; then
      echo "DONE $run_name"
    else
      echo "FAILED case_id=$case_id run_name=$run_name case_dir=$case_dir reason=no_output_signals"
    fi
  } >> "$LOG" 2>&1
done < "$ASSIGNED_TSV"

echo "worker=$JOB_INDEX end=$(date -Is)" >> "$STATE"
WORKER
    chmod +x "$RUN_DIR/run_spectre_worker.sh"

    cat > "$RUN_DIR/run_all_workers.sh" <<'RAW'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$RUN_DIR"
source "$RUN_DIR/RUNINFO.txt"
source "$RUN_DIR/setup_spectre_env.sh"

echo "Using SPECTRE_BIN=$SPECTRE_BIN"
for j in $(seq 0 $((NUM_JOBS - 1))); do
  ./run_spectre_worker.sh "$j" &
done
wait
RAW
    chmod +x "$RUN_DIR/run_all_workers.sh"

    cat > "$RUN_DIR/ciw_template_command.il" <<CIW
; Optional CIW launch for the single template-generation OCEAN pass.
ipcBeginProcess("sh -c 'cd $RUN_DIR && ./run_template_ocean.sh'")
CIW

    cat > "$RUN_DIR/monitoring_commands.sh" <<'MON'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
cmd="${1:-summary}"
case "$cmd" in
  progress)
    watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "^assigned_cases=|^========== case_id=|^DONE |^FAILED case_id=|error while loading shared libraries|ERROR|FATAL|SFE-|SPECTRE-" "$f" | tail -10; done'
    ;;
  summary)
    echo "RUN_DIR=$RUN_DIR"
    echo -n "total cases: "; tail -n +2 cases.csv | wc -l
    echo -n "outputs: "; find cases -name output_signals.txt | wc -l
    echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l || true
    echo "worker assignment:"
    grep -H "^assigned_cases=" logs/spectre_worker_*.log 2>/dev/null || true
    ;;
  errors)
    grep -RniE "FAILED case_id|ERROR|FATAL|SFE-|SPECTRE-|Cannot open|Cannot find|error while loading shared libraries" logs cases 2>/dev/null | tail -200 || true
    ;;
  *)
    echo "Usage: $0 {summary|progress|errors}" >&2
    exit 2
    ;;
esac
MON
    chmod +x "$RUN_DIR/monitoring_commands.sh"

    echo "=== Created run ==="
    echo "$RUN_DIR"
    echo
    echo "Next steps:"
    echo "  cd $RUN_DIR"
    echo "  ./run_template_ocean.sh        # or load ciw_template_command.il in CIW"
    echo "  ./import_template.sh"
    echo "  ./run_all_workers.sh"
    echo "  ./monitoring_commands.sh progress"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
