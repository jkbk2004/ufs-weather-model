#!/bin/bash
TEST_NAME=$1
MACHINE_ID=$2

export RTVERBOSE=0

source "${PATHRT}/default_vars.sh"

TEST_SCRIPT="${PATHRT}/tests/${TEST_NAME}"
if [[ ! -f "${TEST_SCRIPT}" ]]; then
  echo "[ERROR] Missing test script: ${TEST_SCRIPT}" >&2
  exit 1
fi

source "${TEST_SCRIPT}"
source "${PATHRT}/ufs_test_utils.sh"

set_run_task "${TEST_NAME}" "${MACHINE_ID}"

# Emit clean key-value pairs for YAML parsing
echo "ppn: ${TPN}"
echo "nodes: ${NODES}"
echo "wlclk: ${WLCLK}"

