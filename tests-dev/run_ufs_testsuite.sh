#!/bin/bash
set -eux

# === Determine script directory (absolute path) ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
ln -sfn "$RUNDIR_ROOT" "$SCRIPT_DIR/run_dir"
echo "[INFO] Using run directory: $RUNDIR_ROOT"

# === Detect machine ===
if [[ -z "${MACHINE_ID:-}" ]]; then
  source "${SCRIPT_DIR}/../tests/detect_machine.sh"
fi

# === Load runtime config ===
RUNTIME_CONFIG="${SCRIPT_DIR}/machine_config/runtime_config_${MACHINE_ID}.yaml"

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

  if [[ "$cmd" == module\ use* ]] || [[ "$cmd" == module\ load\ anaconda* ]]; then
      echo "[INFO] Loading Python module: $cmd"
      eval "$cmd"
  fi
done <<< "$module_cmds"

# === Optional: link/copy legacy tests ===
if [[ " $* " == *" --link-tests "* ]]; then
  echo "[INFO] Linking/copying legacy tests from $SCRIPT_DIR/../tests"

  [[ -f rt.conf ]] || cp "$SCRIPT_DIR/../tests/rt.conf" .
  [[ -f bl_date.conf ]] || cp "$SCRIPT_DIR/../tests/bl_date.conf" .
  [[ -d fv3_conf ]] || cp -r "$SCRIPT_DIR/../tests/fv3_conf" .
  [[ -d parm ]] || cp -r "$SCRIPT_DIR/../tests/parm" .
  [[ -d tests ]] || cp -r "$SCRIPT_DIR/../tests/tests" .

  cp "$SCRIPT_DIR/../tests/"*.sh .
  cp "$SCRIPT_DIR/../tests/atparse.bash" .
fi

# === Detect baseline creation flag ===
CREATE_BASELINE="false"
if [[ " $* " == *" --create-baseline "* ]]; then
  CREATE_BASELINE="true"
fi
export CREATE_BASELINE

# === Remove wrapper-only flags before calling Python ===
CLEAN_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --link-tests)
      # consumed by wrapper, do not forward
      ;;
    *)
      CLEAN_ARGS+=("$arg")
      ;;
  esac
done

# === Run Python workflow ===
python3 "${SCRIPT_DIR}/run_ufs_workflow.py" \
  --machine "$MACHINE_ID" \
  --rundir-root "$RUNDIR_ROOT" \
  "${CLEAN_ARGS[@]}"
