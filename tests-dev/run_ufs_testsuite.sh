#!/bin/bash
set -eux

export USER="${USER:-$(whoami)}"

# === Help message ===
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: ./run_ufs_testsuite.sh [options]"
  echo
  echo "Examples:"
  echo "  ./run_ufs_testsuite.sh --rocoto -a epic -f app_manifest.yaml"
  echo "  ./run_ufs_testsuite.sh --sequential -a epic -f app_manifest.yaml"
  exit 0
fi

# === EXP_PID controlled by bash ===
export EXP_PID=$$

# === Create run directory and symlink ===
export RUNDIR_ROOT="/work/noaa/stmp/${USER}/FV3_RT/rt_${EXP_PID}"
mkdir -p "$RUNDIR_ROOT"
ln -sfn "$RUNDIR_ROOT" run_dir
echo "[INFO] Using run directory: $RUNDIR_ROOT"

# === Detect machine ===
if [[ -z "${MACHINE_ID:-}" ]]; then
  source detect_machine.sh
fi

# === Load runtime config ===
RUNTIME_CONFIG="machine_config/runtime_config_${MACHINE_ID}.yaml"

# === Extract MODULE_COMMANDS from YAML ===
module_cmds=$(awk '
  /^MODULE_COMMANDS:/ {flag=1; next}
  /^[A-Z_]+:/ {flag=0}
  flag && NF
' "$RUNTIME_CONFIG" | sed -E 's/^[[:space:]]*-[[:space:]]*//')

# === Load ONLY conda-related modules here (Python environment) ===
while IFS= read -r cmd; do
  [[ -z "$cmd" ]] && continue
  [[ $cmd =~ ^# ]] && continue

  # Load only the modules needed for Python
  if [[ "$cmd" == module\ use* ]] || [[ "$cmd" == module\ load\ anaconda* ]]; then
      echo "[INFO] Loading Python module: $cmd"
      eval "$cmd"
  fi
done <<< "$module_cmds"

# === Optional: link/copy legacy tests ===
if [[ " $* " == *" --link-tests "* ]]; then
  echo "[INFO] Linking/copying legacy tests from ../tests"
  [[ -f rt.conf ]] || cp ../tests/rt.conf .
  [[ -f bl_date.conf ]] || cp ../tests/bl_date.conf .
  [[ -d fv3_conf ]] || cp -r ../tests/fv3_conf .
  [[ -d parm ]] || cp -r ../tests/parm .
  [[ -d tests ]] || cp -r ../tests/tests .
  cp ../tests/*.sh .
  cp ../tests/atparse.bash .
fi

# === Detect baseline creation flag ===
CREATE_BASELINE="false"
if [[ " $* " == *" --create-baseline "* ]]; then
  CREATE_BASELINE="true"
fi
export CREATE_BASELINE

# === Run Python workflow ===
python3 run_ufs_workflow.py \
  --machine "$MACHINE_ID" \
  --rundir-root "$RUNDIR_ROOT" \
  "$@"
