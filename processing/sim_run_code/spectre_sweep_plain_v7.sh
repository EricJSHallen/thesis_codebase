#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-prep}"
if [ "$cmd" != "prep" ]; then
  echo "Usage: $0 prep" >&2
  exit 2
fi

REPO_DIR="${REPO_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SPIKE_DIR="${SPIKE_DIR:-$REPO_DIR/processing/sim_run_code/spike_train_output}"
NUM_JOBS="${NUM_JOBS:-4}"
RUN_LABEL="${RUN_LABEL:-2channel_1syn_plain}"
RUN_ID="$(date +%Y%m%d_%H%M%S)_${RUN_LABEL}"
RUN_DIR="${RUN_DIR:-$REPO_DIR/thesis_database/$RUN_ID}"
SPECTRE_BIN="${SPECTRE_BIN:-/projects/bics/cadence/installs/SPECTRE231/tools.lnx86/spectre/bin/64bit/spectre}"
CADENCE_INSTALL_ROOT="${CADENCE_INSTALL_ROOT:-/projects/bics/cadence/installs}"
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
SPECTRE_BIN="$SPECTRE_BIN"
CADENCE_INSTALL_ROOT="$CADENCE_INSTALL_ROOT"
ADE_E_SOURCE="$ADE_E_SOURCE"
TOTAL_CASES=""
INFO

cp -f "$TEMPLATE_OCN_SRC" "$RUN_DIR/ocn/make_spectre_template_v1.ocn"
cp -f "$EXPORT_OCN_SRC" "$RUN_DIR/ocn/export_psf_to_txt_v1.ocn"
[ -f "$ADE_E_SOURCE" ] && cp -f "$ADE_E_SOURCE" "$RUN_DIR/support/ade_e.scs" || true

echo "=== Plain Spectre sweep prep v7 ==="
echo "Repo:        $REPO_DIR"
echo "Spike dir:   $SPIKE_DIR"
echo "Run dir:     $RUN_DIR"
echo "NUM_JOBS:    $NUM_JOBS"
echo "Spectre bin: $SPECTRE_BIN"

python3 - "$SPIKE_DIR" "$RUN_DIR/cases.csv" <<'PY'
import csv, pathlib, re, sys
spike = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
st1_root = spike / "st_1"
st2_root = spike / "st_2"

def hz_key(p):
    m = re.search(r'(\d+)\s*_?hz', p.name, re.I)
    return int(m.group(1)) if m else p.name

def trial_key(p):
    m = re.search(r'trial[_-]?(\d+)', p.name, re.I)
    return int(m.group(1)) if m else p.stem

st1_files = sorted(st1_root.glob("*/*trial*.pwl"), key=lambda p:(hz_key(p.parent), trial_key(p)))
st2_files = sorted(st2_root.glob("*/*trial*.pwl"), key=lambda p:(hz_key(p.parent), trial_key(p)))
st2_by_trial = {}
for p in st2_files:
    st2_by_trial.setdefault(trial_key(p), []).append(p)
rows=[]
cid=0
for s1 in st1_files:
    t = trial_key(s1)
    for s2 in st2_by_trial.get(t, []):
        st1_hz = hz_key(s1.parent); st2_hz = hz_key(s2.parent)
        run_name = f"st1_{st1_hz}_hz__st2_{st2_hz}_hz__trial_{t}"
        case_dir = out.parent / "cases" / run_name
        rows.append({"case_id": cid, "run_name": run_name, "st1_file": str(s1), "st2_file": str(s2), "case_dir": str(case_dir)})
        cid += 1
with out.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=["case_id","run_name","st1_file","st2_file","case_dir"])
    w.writeheader(); w.writerows(rows)
print(len(rows))
PY
TOTAL_CASES=$(($(wc -l < "$RUN_DIR/cases.csv") - 1))
sed -i "s|TOTAL_CASES=\"\"|TOTAL_CASES=\"$TOTAL_CASES\"|" "$RUN_DIR/RUNINFO.txt"
echo "TOTAL_CASES=$TOTAL_CASES"

python3 - "$RUN_DIR" <<'PYGEN'
import pathlib, stat, sys, textwrap
run = pathlib.Path(sys.argv[1])

def write_exe(name, content):
    p = run / name
    p.write_text(textwrap.dedent(content).lstrip())
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def write_file(name, content):
    p = run / name
    p.write_text(textwrap.dedent(content).lstrip())

write_exe('refresh_spectre_runtime.sh', r'''
    #!/usr/bin/env bash
    set -euo pipefail
    RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
    source "$RUN_DIR/RUNINFO.txt"
    OUT="$RUN_DIR/support/spectre_runtime.env"
    TMP="$OUT.tmp"
    : > "$TMP"
    echo "# generated $(date -Is)" >> "$TMP"
    echo "export SPECTRE_BIN=\"$SPECTRE_BIN\"" >> "$TMP"
    declare -a DIRS=()
    add_dir() { [ -d "$1" ] && DIRS+=("$1"); }
    SPECTRE_BIN_DIR="$(cd "$(dirname "$SPECTRE_BIN")" && pwd)"
    add_dir "$SPECTRE_BIN_DIR"
    add_dir "$(cd "$SPECTRE_BIN_DIR/../.." 2>/dev/null && pwd)/lib/64bit"
    add_dir "$(cd "$SPECTRE_BIN_DIR/../.." 2>/dev/null && pwd)/lib"
    add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib/64bit"
    add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/spectre/lib"
    add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib/64bit"
    add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/lib"
    add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib/64bit"
    add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/lib"
    add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib/64bit"
    add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/dfII/lib"
    add_dir "$CADENCE_INSTALL_ROOT/IC231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"
    add_dir "$CADENCE_INSTALL_ROOT/SPECTRE231/tools.lnx86/oa/lib/linux_rhel70_gcc93x_64/opt"

    # Resolve missing libraries iteratively, but only during refresh, never during worker startup.
    for pass in 1 2 3 4; do
      export LD_LIBRARY_PATH="$(IFS=:; echo "${DIRS[*]}"):${LD_LIBRARY_PATH:-}"
      missing=$(ldd "$SPECTRE_BIN" 2>/dev/null | awk '/not found/{print $1}' | sort -u || true)
      [ -z "$missing" ] && break
      while read -r lib; do
        [ -z "$lib" ] && continue
        found=$(find "$CADENCE_INSTALL_ROOT" -name "$lib" -type f -print -quit 2>/dev/null || true)
        if [ -n "$found" ]; then
          DIRS+=("$(dirname "$found")")
        fi
      done <<< "$missing"
    done
    # de-duplicate while preserving order
    LD=""
    for d in "${DIRS[@]}"; do
      [ -d "$d" ] || continue
      case ":$LD:" in *":$d:"*) ;; *) LD="$d${LD:+:$LD}" ;; esac
    done
    echo "export PATH=\"$SPECTRE_BIN_DIR:\${PATH:-}\"" >> "$TMP"
    echo "export LD_LIBRARY_PATH=\"$LD:\${LD_LIBRARY_PATH:-}\"" >> "$TMP"
    mv "$TMP" "$OUT"
    echo "Wrote $OUT"
    source "$OUT"
    echo "Missing after refresh, if any:"
    ldd "$SPECTRE_BIN" 2>/dev/null | grep 'not found' || echo "none"
''')

write_file('setup_spectre_env.sh', r'''
    #!/usr/bin/env bash
    RUN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$RUN_DIR/RUNINFO.txt"
    if [ -f "$RUN_DIR/support/spectre_runtime.env" ]; then
      source "$RUN_DIR/support/spectre_runtime.env"
    fi
    export SPECTRE_BIN
    check_spectre_runtime() {
      ldd "$SPECTRE_BIN" 2>/dev/null | grep -i 'not found' || true
    }
    export -f check_spectre_runtime 2>/dev/null || true
''')

write_file('select_cases.py', r'''
    #!/usr/bin/env python3
    import csv, sys
    cases_csv, job_idx, num_jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    with open(cases_csv, newline='') as f:
        for row in csv.DictReader(f):
            cid = int(row['case_id'])
            if cid % num_jobs == job_idx:
                print('\t'.join([str(cid), row['run_name'], row['st1_file'], row['st2_file'], row['case_dir']]))
''')
(run / 'select_cases.py').chmod(0o755)

write_exe('run_template_ocean.sh', r'''
    #!/usr/bin/env bash
    set -euo pipefail
    RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
    mkdir -p "$RUN_DIR/logs"
    echo "Running one OCEAN/Virtuoso template generation pass..."
    ocean -nograph -restore "$RUN_DIR/ocn/make_spectre_template_v1.ocn" > "$RUN_DIR/logs/template_ocean.log" 2>&1
''')

write_file('ciw_template_command.il', r'''
    ipcBeginProcess("sh -c 'cd __RUN_DIR__ && ./run_template_ocean.sh'")
'''.replace('__RUN_DIR__', str(run)))

write_exe('import_template.sh', r'''
    #!/usr/bin/env bash
    set -euo pipefail
    RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
    source "$RUN_DIR/RUNINFO.txt"
    TEMPLATE="$RUN_DIR/netlist_template/raw"
    mkdir -p "$TEMPLATE"
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
''')

write_exe('run_spectre_worker.sh', r'''
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
    if [ ! -f "$TEMPLATE/input.scs" ]; then
      echo "ERROR: missing $TEMPLATE/input.scs" | tee -a "$LOG"
      exit 1
    fi
    python3 "$RUN_DIR/select_cases.py" "$RUN_DIR/cases.csv" "$JOB_INDEX" "$NUM_JOBS" > "$ASSIGNED_TSV"
    echo "assigned_cases=$(wc -l < "$ASSIGNED_TSV")" | tee -a "$LOG" > "$STATE"
    while IFS=$'\t' read -r case_id run_name st1_file st2_file case_dir; do
      {
        echo "========== case_id=$case_id run_name=$run_name =========="
        if [ -f "$case_dir/output_signals.txt" ]; then
          echo "SKIP existing output_signals.txt"
          continue
        fi
        rm -rf "$case_dir/netlist" "$case_dir/psf"
        mkdir -p "$case_dir/netlist"
        cp -a "$TEMPLATE"/. "$case_dir/netlist"/
        [ -f "$RUN_DIR/support/ade_e.scs" ] && cp -f "$RUN_DIR/support/ade_e.scs" "$case_dir/netlist/ade_e.scs"
        python3 - "$case_dir/netlist" "$st1_file" "$st2_file" <<'PY'
    import pathlib, sys
    root=pathlib.Path(sys.argv[1]); st1=sys.argv[2]; st2=sys.argv[3]
    changed=0
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        try:
            s=p.read_text(errors='ignore')
        except Exception:
            continue
        ns=s.replace('__ST1_PWL__', st1).replace('__ST2_PWL__', st2)
        if ns != s:
            p.write_text(ns); changed += 1
    print(f"patched_files={changed}")
    PY
        ( cd "$case_dir/netlist" && "$SPECTRE_BIN" input.scs +escchars +log "$case_dir/spectre.out" -format psfxl -raw "$case_dir/psf" )
        rc=$?
        if [ "$rc" -ne 0 ]; then
          echo "FAILED case_id=$case_id run_name=$run_name reason=spectre_rc_$rc"
          continue
        fi
        CAD_CASE_DIR="$case_dir" CAD_BATCH_EXIT=1 ocean -nograph -restore "$EXPORT_OCN" > "$case_dir/export_ocean.log" 2>&1
        rc=$?
        if [ "$rc" -ne 0 ]; then
          echo "FAILED case_id=$case_id run_name=$run_name reason=export_rc_$rc"
          continue
        fi
        [ -f "$case_dir/output_signals.txt" ] && echo "DONE $run_name" || echo "FAILED case_id=$case_id run_name=$run_name reason=no_output_signals"
      } >> "$LOG" 2>&1
    done < "$ASSIGNED_TSV"
    echo "worker=$JOB_INDEX end=$(date -Is)" >> "$STATE"
''')

write_exe('run_all_workers.sh', r'''
    #!/usr/bin/env bash
    set -euo pipefail
    RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
    source "$RUN_DIR/RUNINFO.txt"
    source "$RUN_DIR/setup_spectre_env.sh"
    missing=$(check_spectre_runtime || true)
    if [ -n "$missing" ]; then
      echo "ERROR: Spectre runtime libraries are still missing:" >&2
      echo "$missing" >&2
      echo "Run: ./refresh_spectre_runtime.sh" >&2
      exit 1
    fi
    for j in $(seq 0 $((NUM_JOBS-1))); do
      bash "$RUN_DIR/run_spectre_worker.sh" "$j" > "$RUN_DIR/logs/worker_${j}.launcher.log" 2>&1 &
    done
    wait
''')

write_exe('monitoring_commands.sh', r'''
    #!/usr/bin/env bash
    set -euo pipefail
    RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
    source "$RUN_DIR/RUNINFO.txt"
    case "${1:-progress}" in
      progress)
        watch -n 10 'echo -n "outputs: "; find cases -name output_signals.txt | wc -l; echo -n "failed cases: "; grep -R "^FAILED case_id=" logs/spectre_worker_*.log 2>/dev/null | wc -l; echo; for f in logs/spectre_worker_*.log; do [ -f "$f" ] || continue; echo "--- $f"; grep -E "assigned_cases|DONE |FAILED case_id=|runtime_missing_libs|not found|error while loading shared libraries" "$f" | tail -20; done'
        ;;
      count)
        find cases -name output_signals.txt | wc -l
        ;;
      *)
        echo "Usage: $0 {progress|count}" >&2; exit 2;;
    esac
''')
PYGEN

# Refresh once during prep, but do not block forever if the filesystem is slow.
if command -v timeout >/dev/null 2>&1; then
  timeout 120 "$RUN_DIR/refresh_spectre_runtime.sh" || true
else
  "$RUN_DIR/refresh_spectre_runtime.sh" || true
fi

# Sanity: prove helper scripts have real line breaks.
wc -l "$RUN_DIR"/run_all_workers.sh "$RUN_DIR"/run_spectre_worker.sh "$RUN_DIR"/setup_spectre_env.sh "$RUN_DIR"/refresh_spectre_runtime.sh

cat <<MSG
=== Created run ===
$RUN_DIR

Next steps:
  cd $RUN_DIR
  ./run_template_ocean.sh        # or load ciw_template_command.il in CIW
  ./import_template.sh
  source ./setup_spectre_env.sh
  check_spectre_runtime          # should print nothing
  ./run_all_workers.sh
  ./monitoring_commands.sh progress
MSG
