#!/bin/bash
set -euo pipefail

TEST_NAME=$1
MACHINE_ID=$2

export RTVERBOSE=0

source "${PATHRT}/default_vars.sh"
source "${PATHRT}/rt_utils.sh"

TEST_SCRIPT="${PATHRT}/tests/${TEST_NAME}"
if [[ ! -f "${TEST_SCRIPT}" ]]; then
  echo "[ERROR] Missing test script: ${TEST_SCRIPT}" >&2
  exit 1
fi

source "${TEST_SCRIPT}"

if [[ "${ESMF_THREADING}" == true ]]; then
  compute_petbounds_and_tasks_esmf_threading
else
  compute_petbounds_and_tasks_traditional_threading
fi

: "${TPN:?TPN not set}"
: "${THRD:?THRD not set}"
: "${TASKS:?TASKS not set}"

TPN=$(( TPN / THRD ))
NODES=$(( TASKS / TPN ))
if (( NODES * TPN < TASKS )); then
  NODES=$(( NODES + 1 ))
fi
PPN=$(( TASKS / NODES ))
if (( TASKS - ( PPN * NODES ) > 0 )); then
  PPN=$(( PPN + 1 ))
fi

export WLCLK

echo "ppn: ${TPN}"
echo "nodes: ${NODES}"
echo "wlclk: ${WLCLK}"
