#!/usr/bin/env bash
set -euo pipefail

# Plain Spectre sweep prep v5
# Fixes v3 runtime-library problem by resolving missing Spectre shared libraries
# across the Cadence install tree, not only the SPECTRE231 tree.

MODE="${1:-prep}"
if [ "$MODE" != "prep" ]; then
  echo "Usage: $0 prep" >&2
  exit 2
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_LABEL="${RUN_LABEL:-2channel_1syn_plain}"
NUM_JOBS="${NUM_JOBS:-4}"
TS="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${TS}_${RUN_LABEL}"
RUN_DIR="$REPO_DIR/thesis_database/$RUN_ID"
SPIKE_DIR="${SPIKE_DIR:-$REPO_DIR/processing/sim_run_code/spike_train_output}"
SRC_OCN="${SRC_OCN:-$REPO_DIR/processing/sim_run_code/ocn_scripts/make_spectre_template_v1.ocn}"
EXPORT_OCN_SRC="${EXPORT_OCN_SRC:-$REPO_DIR/processing/sim_run_code/ocn_scripts/export_psf_to_txt_v1.ocn}"
SPECTRE_BIN="${SPECTRE_BIN:-/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre}"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"

mkdir -p "$RUN_DIR"/{logs,ocn,netlist_template,worker_state,cases,support}
cp "$SRC_OCN" "$RUN_DIR/ocn/make_spectre_template_v1.ocn"
cp "$EXPORT_OCN_SRC" "$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"

cat > "$RUN_DIR/RUNINFO.txt" <<EOF_RUN
RUN_DIR=$RUN_DIR
REPO_DIR=$REPO_DIR
SPIKE_DIR=$SPIKE_DIR
NUM_JOBS=$NUM_JOBS
SPECTRE_BIN=$SPECTRE_BIN
CADENCE_INSTALL_ROOT=$CADENCE_INSTALL_ROOT
EOF_RUN

# Build cases.csv from paired st_1/st_2 trial_N files.
python3 - "$SPIKE_DIR" "$RUN_DIR" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
run_dir = pathlib.Path(sys.argv[2])
st1_root = spike / "st_1"
st2_root = spike / "st_2"
trial_re = re.compile(r"trial_(\d+)\.pwl$")
def hz_name(p): return p.name.replace("_hz", "")
rows=[]
cid=0
for st1_dir in sorted([p for p in st1_root.iterdir() if p.is_dir()], key=lambda p: int(hz_name(p)) if hz_name(p).isdigit() else p.name):
    st1_hz = hz_name(st1_dir)
    for st2_dir in sorted([p for p in st2_root.iterdir() if p.is_dir()], key=lambda p: int(hz_name(p)) if hz_name(p).isdigit() else p.name):
        st2_hz = hz_name(st2_dir)
        st1_trials = {trial_re.search(p.name).group(1): p for p in st1_dir.glob("trial_*.pwl") if trial_re.search(p.name)}
        st2_trials = {trial_re.search(p.name).group(1): p for p in st2_dir.glob("trial_*.pwl") if trial_re.search(p.name)}
        for tr in sorted(set(st1_trials) & set(st2_trials), key=lambda x:int(x)):
            run_name=f"st1_{st1_hz}_hz__st2_{st2_hz}_hz__trial_{tr}"
            rows.append({"case_id":cid,"run_name":run_name,"st1_file":str(st1_trials[tr]),"st2_file":str(st2_trials[tr]),"case_dir":str(run_dir/"cases"/run_name)})
            cid += 1
with (run_dir/"cases.csv").open("w", newline="") as f:
    w=csv.DictWriter(f, fieldnames=["case_id","run_name","st1_file","st2_file","case_dir"])
    w.writeheader(); w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES=$(($(wc -l < "$RUN_DIR/cases.csv") - 1))
echo "TOTAL_CASES=$TOTAL_CASES" >> "$RUN_DIR/RUNINFO.txt"

# Choose ade_e source and cache it.
ADE_E_SOURCE="${ADE_E_SOURCE:-}"
if [ -z "$ADE_E_SOURCE" ]; then
  ADE_E_SOURCE="$(find /home/s5117909/simulation -name ade_e.scs -path '*synapsedualinputtb*' -print 2>/dev/null | head -1 || true)"
fi
if [ -n "$ADE_E_SOURCE" ] && [ -f "$ADE_E_SOURCE" ]; then
  cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs"
  echo "ADE_E_SOURCE=$ADE_E_SOURCE" >> "$RUN_DIR/RUNINFO.txt"
else
  echo "WARNING: no ade_e.scs cached; set ADE_E_SOURCE=/path/to/ade_e.scs if needed" >&2
  echo "ADE_E_SOURCE=" >> "$RUN_DIR/RUNINFO.txt"
fi

cat > "$RUN_DIR/setup_spectre_env.sh" <<'EOF_ENV'
#!/usr/bin/env bash
# Source this file before invoking the direct Spectre binary.
# v5 searches both SPECTRE231 and IC231/other Cadence install trees for the
# shared libraries that the direct Spectre binary needs.

RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"

if [ -z "${SPECTRE_BIN:-}" ]; then
  SPECTRE_BIN="/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre"
fi
if [ ! -x "$SPECTRE_BIN" ]; then
  echo "ERROR: SPECTRE_BIN not executable: $SPECTRE_BIN" >&2
  return 1 2>/dev/null || exit 1
fi

prepend_path() {
  [ -d "${1:-}" ] || return 0
  case ":${PATH:-}:" in *":$1:"*) ;; *) export PATH="$1:${PATH:-}" ;; esac
}
prepend_ld() {
  [ -d "${1:-}" ] || return 0
  case ":${LD_LIBRARY_PATH:-}:" in *":$1:"*) ;; *) export LD_LIBRARY_PATH="$1:${LD_LIBRARY_PATH:-}" ;; esac
}

SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
SPECTRE_HOME="$(cd "$SPECTRE_BIN_DIR/../.." && pwd)"
SPECTRE_TOOLS="$(cd "$SPECTRE_HOME/.." && pwd)"
SPECTRE_INSTALL="$(cd "$SPECTRE_TOOLS/.." && pwd)"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"

export SPECTRE_BIN
prepend_path "$SPECTRE_BIN_DIR"

# High-probability locations first.
for d in \
  "$SPECTRE_HOME/lib/64bit" "$SPECTRE_HOME/lib" \
  "$SPECTRE_TOOLS/lib/64bit" "$SPECTRE_TOOLS/lib" \
  "$SPECTRE_TOOLS/spectre/lib/64bit" "$SPECTRE_TOOLS/spectre/lib" \
  "$SPECTRE_INSTALL/lib/64bit" "$SPECTRE_INSTALL/lib" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib/64bit" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib/64bit" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib" \
  "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt" \
  "$CADENCE_INSTALL_ROOT/IC231/oa_v22.61.002/lib/linux_rhel70_gcc93x_64/opt" \
  "$CADENCE_INSTALL_ROOT/SPECTRE231/oa_v22.61.002/lib/linux_rhel70_gcc93x_64/opt"; do
  prepend_ld "$d"
done

# Resolve known missing direct-Spectre libraries from anywhere under the
# Cadence install tree. This is the important v5 fix.
if [ -d "$CADENCE_INSTALL_ROOT" ]; then
  while IFS= read -r lib; do
    prepend_ld "$(dirname "$lib")"
  done < <(find "$CADENCE_INSTALL_ROOT" \
    \( -name 'libSpectreEH_sh.so' -o -name 'libfmc.so' -o -name 'libvisadev.so' -o -name 'libabv.so' -o -name 'libcds*.so' -o -name 'liboa*.so' -o -name 'libdd*.so' \) \
    -type f 2>/dev/null | sort -u)
fi

check_spectre_runtime() {
  if command -v ldd >/dev/null 2>&1; then
    ldd "$SPECTRE_BIN" 2>/dev/null | grep -i 'not found' || true
  fi
}
export -f check_spectre_runtime 2>/dev/null || true
EOF_ENV
chmod +x "$RUN_DIR/setup_spectre_env.sh"

cat > "$RUN_DIR/select_cases.py" <<'PY'
import csv, sys
cases_csv, job_index, num_jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(cases_csv, newline='') as f:
    for row in csv.DictReader(f):
        cid = int(row['case_id'])
        if cid % num_jobs == job_index:
            print('\t'.join([str(cid), row['run_name'], row['st1_file'], row['st2_file'], row['case_dir']]))
PY

cat > "$RUN_DIR/run_template_ocean.sh" <<'EOF_TPL'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
CAD_TEMPLATE_RUN_DIR="$RUN_DIR/template_ocean_run" CAD_BATCH_EXIT=1 ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_v1.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
EOF_TPL
chmod +x "$RUN_DIR/run_template_ocean.sh"

cat > "$RUN_DIR/ciw_template_command.il" <<EOF_CIW
ipcBeginProcess("sh -c 'cd $RUN_DIR && CAD_TEMPLATE_RUN_DIR=$RUN_DIR/template_ocean_run CAD_BATCH_EXIT=1 ocean -nograph -restore $RUN_DIR/ocn/make_spectre_template_v1.ocn > $RUN_DIR/logs/template_ocean.log 2>&1'")
EOF_CIW

cat > "$RUN_DIR/import_template.sh" <<'EOF_IMP'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
RAW="$RUN_DIR/netlist_template/raw"
rm -rf "$RAW"; mkdir -p "$RAW"
# Prefer the newest input.scs generated by the template OCEAN run.
SRC_INPUT="$(find /home/s5117909/simulation "$RUN_DIR" -name input.scs -type f 2>/dev/null | sort -r | head -1 || true)"
if [ -z "$SRC_INPUT" ]; then echo "ERROR: could not find generated input.scs" >&2; exit 1; fi
cp -a "$(dirname "$SRC_INPUT")"/. "$RAW"/
[ -f "$RUN_DIR/support/ade_e.scs" ] && cp -f "$RUN_DIR/support/ade_e.scs" "$RAW/ade_e.scs"
# Patch one template case path to placeholders. These are deliberately broad.
ST1_TEMPLATE_PATH="$(find "$SPIKE_DIR/st_1" -name 'trial_*.pwl' | sort | head -1)"
ST2_TEMPLATE_PATH="$(find "$SPIKE_DIR/st_2" -name 'trial_*.pwl' | sort | head -1)"
python3 - "$RAW" "$ST1_TEMPLATE_PATH" "$ST2_TEMPLATE_PATH" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]); st1=sys.argv[2]; st2=sys.argv[3]
for p in root.rglob('*'):
    if p.is_file():
        try: s=p.read_text(errors='ignore')
        except Exception: continue
        ns=s.replace(st1,'__ST1_PWL__').replace(st2,'__ST2_PWL__')
        if ns != s: p.write_text(ns)
PY
echo "Imported template into: $RAW"
grep -RniE 'pwl|__ST1_PWL__|__ST2_PWL__|ade_e' "$RAW" | head -80 || true
EOF_IMP
chmod +x "$RUN_DIR/import_template.sh"

cat > "$RUN_DIR/run_spectre_worker.sh" <<'EOF_WORKER'
#!/usr/bin/env bash
set -u -o pipefail
JOB_INDEX="${1:?usage: run_spectre_worker.sh JOB_INDEX}"
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
source "$RUN_DIR/setup_spectre_env.sh"
TEMPLATE="$RUN_DIR/netlist_template/raw"
LOG="$RUN_DIR/logs/spectre_worker_${JOB_INDEX}.log"
STATE="$RUN_DIR/worker_state/job_${JOB_INDEX}.state"
ASSIGNED_TSV="$RUN_DIR/worker_state/job_${JOB_INDEX}_cases.tsv"
EXPORT_OCN="$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/worker_state"
{
  echo "worker=$JOB_INDEX start=$(date -Is)"
  echo "SPECTRE_BIN=$SPECTRE_BIN"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
  echo "runtime_missing_libs:"
  check_spectre_runtime
} > "$LOG" 2>&1

echo "worker=$JOB_INDEX start=$(date -Is)" > "$STATE"
if [ ! -f "$TEMPLATE/input.scs" ]; then echo "ERROR: missing $TEMPLATE/input.scs" | tee -a "$LOG"; exit 1; fi
python3 "$RUN_DIR/select_cases.py" "$RUN_DIR/cases.csv" "$JOB_INDEX" "$NUM_JOBS" > "$ASSIGNED_TSV"
echo "assigned_cases=$(wc -l < "$ASSIGNED_TSV")" | tee -a "$LOG" >> "$STATE"
while IFS=$'\t' read -r case_id run_name st1_file st2_file case_dir; do
  {
    echo "========== case_id=$case_id run_name=$run_name =========="
    mkdir -p "$case_dir/netlist"
    if [ -f "$case_dir/output_signals.txt" ]; then echo "SKIP existing output_signals.txt"; continue; fi
    rm -rf "$case_dir/netlist" "$case_dir/psf"; mkdir -p "$case_dir/netlist"
    cp -a "$TEMPLATE"/. "$case_dir/netlist"/
    [ -f "$RUN_DIR/support/ade_e.scs" ] && cp -f "$RUN_DIR/support/ade_e.scs" "$case_dir/netlist/ade_e.scs"
    python3 - "$case_dir/netlist" "$st1_file" "$st2_file" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]); st1=sys.argv[2]; st2=sys.argv[3]
changed=0
for p in root.rglob('*'):
    if not p.is_file(): continue
    try: s=p.read_text(errors='ignore')
    except Exception: continue
    ns=s.replace('__ST1_PWL__', st1).replace('__ST2_PWL__', st2)
    if ns != s:
        p.write_text(ns); changed += 1
print(f"patched_files={changed}")
PY
    ( cd "$case_dir/netlist" && "$SPECTRE_BIN" input.scs +escchars +log "$case_dir/spectre.out" -format psfxl -raw "$case_dir/psf" )
    rc=$?
    if [ "$rc" -ne 0 ]; then echo "FAILED case_id=$case_id run_name=$run_name reason=spectre_rc_$rc"; continue; fi
    CAD_CASE_DIR="$case_dir" CAD_BATCH_EXIT=1 ocean -nograph -restore "$EXPORT_OCN" > "$case_dir/export_ocean.log" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then echo "FAILED case_id=$case_id run_name=$run_name reason=export_rc_$rc"; continue; fi
    [ -f "$case_dir/output_signals.txt" ] && echo "DONE $run_name" || echo "FAILED case_id=$case_id run_name=$run_name reason=no_output_signals"
  } >> "$LOG" 2>&1
done < "$ASSIGNED_TSV"
echo "worker=$JOB_INDEX end=$(date -Is)" >> "$STATE"
EOF_WORKER
chmod +x "$RUN_DIR/run_spectre_worker.sh"

cat > "$RUN_DIR/run_all_workers.sh" <<'EOF_ALL'
#!/usr/bin/env bash
set -euo pipefail
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$RUN_DIR/RUNINFO.txt"
for j in $(seq 0 $((NUM_JOBS-1))); do
  bash "$RUN_DIR/run_spectre_worker.sh" "$j" > "$RUN_DIR/logs/worker_${j}.launcher.log" 2>&1 &
done
wait
EOF_ALL
chmod +x "$RUN_DIR/run_all_workers.sh"

cat > "$RUN_DIR/monitoring_commands.sh" <<'EOF_MON'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-progress}" in
progress)
  watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do echo "--- $f"; grep -E "runtime_missing_libs|not found|error while loading shared libraries|assigned_cases|^FAILED case_id=|^DONE" "$f" 2>/dev/null | tail -8; done'
  ;;
*) echo "Usage: $0 progress" ;;
esac
EOF_MON
chmod +x "$RUN_DIR/monitoring_commands.sh"

# Sanity check: generated helper scripts must contain real newline characters.
# If one of these is 1-2 lines, it means the file was corrupted during transfer/copy.
for helper in run_all_workers.sh run_spectre_worker.sh setup_spectre_env.sh select_cases.py monitoring_commands.sh; do
  nlines=$(wc -l < "$RUN_DIR/$helper")
  case "$helper" in
    run_all_workers.sh) min_lines=8 ;;
    run_spectre_worker.sh) min_lines=70 ;;
    setup_spectre_env.sh) min_lines=50 ;;
    select_cases.py) min_lines=6 ;;
    monitoring_commands.sh) min_lines=8 ;;
  esac
  if [ "$nlines" -lt "$min_lines" ]; then
    echo "ERROR: generated $helper is malformed: only $nlines lines" >&2
    echo "This usually means the script was copied with newlines collapsed." >&2
    exit 1
  fi
done

echo "=== Plain Spectre sweep prep v5 ==="
echo "Repo:        $REPO_DIR"
echo "Run dir:     $RUN_DIR"
echo "NUM_JOBS:    $NUM_JOBS"
echo "SPECTRE_BIN: $SPECTRE_BIN"
echo "TOTAL_CASES: $TOTAL_CASES"
echo
echo "Next steps:"
echo "  cd $RUN_DIR"
echo "  ./run_template_ocean.sh     # or paste ciw_template_command.il in CIW"
echo "  ./import_template.sh"
echo "  ./run_all_workers.sh"
echo "  ./monitoring_commands.sh progress"
