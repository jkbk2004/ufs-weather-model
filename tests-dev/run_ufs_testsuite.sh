#!/bin/bash
set -eux

# === Check if -s was passed ===
LINK_TESTS=false
for arg in "$@"; do
  if [[ "$arg" == "-s" || "$arg" == "--link-tests" ]]; then
    LINK_TESTS=true
    break
  fi
done

# === Link test files only if -s is passed AND not already linked ===
if $LINK_TESTS; then
  if [[ ! -e "rt.sh" || ! -d "parm" || ! -d "scripts" ]]; then
    echo "[INFO] Copying test files from ../tests/ to current directory"
    cp -r ../tests/* .
  else
    echo "[INFO] Test files already present — skipping copy"
  fi
fi

# === Detect machine ===
if [[ -z "${MACHINE_ID:-}" ]]; then
  source default_machine.sh
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
