#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="$(cd "$(dirname "$0")" && pwd -P)"
if [[ -f "$RUN_DIR/RUNINFO.txt" ]]; then
  source "$RUN_DIR/RUNINFO.txt"
fi

TEMPLATE="$RUN_DIR/netlist_template/raw/input.scs"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: missing run template: $TEMPLATE" >&2
  echo "Run this from a prepared run directory after ./import_template.sh." >&2
  exit 1
fi

python3 - "$TEMPLATE" <<'PY'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text(errors='ignore')

# Normalize the save statement so both voltages and the I56 output current are saved.
ns = re.sub(r'\bsave\s+vpre\s+vpre1\s+I56:Iout\b', 'save vpre vpre1 I56:Iout', s, count=1)
if ns == s:
    ns = re.sub(r'\bsave\s+vpre\s+vpre1\b', 'save vpre vpre1 I56:Iout', s, count=1)
if ns == s and 'save vpre vpre1 I56:Iout' not in s:
    ns = re.sub(r'\bsaveOptions\b', 'save vpre vpre1 I56:Iout\n saveOptions', s, count=1)

if 'save vpre vpre1 I56:Iout' not in ns:
    raise SystemExit('ERROR: could not add save vpre vpre1 I56:Iout to input.scs')

p.write_text(ns)
print('patched template:', p)
print('verified current save directive: save vpre vpre1 I56:Iout')
PY

mkdir -p "$RUN_DIR/ocn"
if [[ -f "$RUN_DIR/ocn/export_psf_to_txt.ocn" ]]; then
  cp -f "$RUN_DIR/ocn/export_psf_to_txt.ocn" "$RUN_DIR/ocn/export_psf_to_txt.ocn.bak_before_i56_current"
fi

cat > "$RUN_DIR/ocn/export_psf_to_txt.ocn" <<'OCN'
; export_psf_to_txt.ocn
caseDir = getShellEnvVar("CAD_CASE_DIR")
unless(caseDir error("CAD_CASE_DIR is not set.\n"))
psfDir  = strcat(caseDir "/psf")
outTmp  = strcat(caseDir "/output_signals.txt.tmp")
outFile = strcat(caseDir "/output_signals.txt")
unless(isDir(psfDir) error("Cannot find PSF directory: %s\n" psfDir))
openResults(psfDir)
selectResult('tran)
iout_56 = i("/I56/Iout")
unless(iout_56 error("Could not read i(\"/I56/Iout\"). Confirm netlist saved I56:Iout and rerun Spectre.\n"))
vpre  = v("/vpre")
vpre1 = v("/vpre1")
unless(vpre error("Could not read v(\"/vpre\").\n"))
unless(vpre1 error("Could not read v(\"/vpre1\").\n"))
when(isFile(outTmp) system(strcat("rm -f \"" outTmp "\"")))
ocnPrint(?output outTmp ?precision 10 ?numSpaces 1 iout_56 vpre vpre1)
unless(isFile(outTmp) error("ocnPrint did not create %s\n" outTmp))
system(strcat("mv -f \"" outTmp "\" \"" outFile "\""))
closeResults(psfDir)
printf("Wrote %s with i(/I56/Iout), v(/vpre), v(/vpre1)\n" outFile)
when(getShellEnvVar("CAD_BATCH_EXIT") == "1" exit())
OCN

echo "Patched run export OCN: $RUN_DIR/ocn/export_psf_to_txt.ocn"
echo "IMPORTANT: PSF files generated before this patch probably do not contain I56:Iout."
echo "Delete old case PSF/output files and rerun workers, or start a clean run."
