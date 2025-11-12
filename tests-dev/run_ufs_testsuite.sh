#!/bin/bash
set -eux

# === Help message ===
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  echo "Usage: ./run_ufs_testsuite.sh [options]"
  echo ""
  echo "Options:"
  echo "  -s, --link-tests        One-time setup: copy test files from ../tests/ into current directory"
  echo "  -a, --account <name>    Required HPC account name for job submission"
  echo "  -r, --rocoto            Run workflow using Rocoto"
  echo "  -e, --ecflow            Run workflow using ecFlow"
  echo "  -n, --single-test <id>  Run a single test by ID"
  echo "  -l, --test-list <file>  Run tests listed in a file"
  echo "  -b, --baseline-list <file>  Compare against baseline tests listed in a file"
  echo "  -c, --create-baseline   Create baseline outputs"
  echo "  -m, --compare-baseline  Compare outputs against baseline"
  echo "  -o, --compile-only      Compile only, no test execution"
  echo "  -d, --delete-rundir     Delete run directory after completion"
  echo "  -k, --keep-rundir       Keep run directory after completion"
  echo "  -w, --weekly            Run weekly test mode"
  echo "  -f, --manifest          Run with app_manifest.yaml (ignored if other modes are used)"
  echo "  -y, --yamls_dir         Directory of by_app YAMLs (required for manifest, test-list, or single-test)"
  echo "  -u, --user-yaml         Path to user-supplied test YAML"
  echo "      --force             Force overwrite of existing workflow XML"
  echo "      --dry-run           Print commands without executing"
  echo ""
  echo "Example:"
  echo "  ./run_ufs_testsuite.sh -s -a myaccount -r -l test_list.txt"
  exit 0
fi

# === Check if -s was passed ===
LINK_TESTS=false
for arg in "$@"; do
  if [[ "$arg" == "-s" || "$arg" == "--link-tests" ]]; then
    LINK_TESTS=true
    break
  fi
done

export EXP_PID=$$

# === Link test files only if -s is passed AND not already linked ===
if $LINK_TESTS; then
  if [[ ! -e "rt.sh" || ! -d "parm" || ! -d "scripts" ]]; then
    echo "[INFO] Copying test files from ../tests/ to current directory"
    cp ../tests/rt.conf .
    cp ../tests/bl_date.conf .
    cp -r ../tests/fv3_conf .
    cp -r ../tests/parm .
    cp -r ../tests/tests .
    cp ../test/*.sh .
  else
    echo "[INFO] Test files already present — skipping copy"
  fi
fi

# === Detect machine ===
if [[ -z "${MACHINE_ID:-}" ]]; then
  source detect_machine.sh
fi

# === Load modules from runtime_config_${MACHINE_ID}.yaml ===
RUNTIME_YAML="machine_config/runtime_config_${MACHINE_ID}.yaml"
MODULE_LINES=$(awk '/^MODULE_COMMANDS:/,/^[^ ]/' "$RUNTIME_YAML" | grep '^  - ' | sed 's/^  - //')
while IFS= read -r line; do
  [[ "$line" =~ ^# ]] && continue
  eval "$line"
done <<< "$MODULE_LINES"

# === Set Rocoto paths ===
export ROCOTORUN=$(grep 'ROCOTORUN:' "$RUNTIME_YAML" | awk '{print $2}')
export ROCOTOSTAT=$(grep 'ROCOTOSTAT:' "$RUNTIME_YAML" | awk '{print $2}')
export ROCOTOCOMPLETE=$(grep 'ROCOTOCOMPLETE:' "$RUNTIME_YAML" | awk '{print $2}')
export ROCOTO_SCHEDULER=$(grep 'ROCOTO_SCHEDULER:' "$RUNTIME_YAML" | awk '{print $2}')
export MACHINE_ID

# === Run Python workflow ===
python3 run_ufs_workflow.py "$@"
