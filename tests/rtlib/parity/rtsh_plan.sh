#!/bin/bash
# Run rt.sh's *own* selection code with job submission stubbed out and print
# the plan in rtlib's text format. Nothing is compiled, submitted or written
# outside a temporary directory.
#
#   rtsh_plan.sh PATHRT MACHINE_ID [-c] [-o] [-l CONF] [-n "TEST COMPILER"] [-b FILE]
#
# update_rtconf(), rt_35d() and the main `while read -r line` loop are cut
# out of ${PATHRT}/rt.sh at run time, so this always tests the current rt.sh.
# Each test file is still sourced and its task counts computed, exactly as
# rt.sh does, so a test file that breaks under `set -eu` shows up here too.
#
# Output: one line per task, or a final "EXIT" line if rt.sh would have
# stopped with an error. Everything rt.sh itself prints goes to stderr.

set -eu
[[ $# -ge 2 ]] || { echo "usage: $0 PATHRT MACHINE_ID [options]" >&2; exit 2; }
PATHRT_REAL=$(cd "$1" && pwd -P)
MACHINE_ID=$2
shift 2

CREATE_BASELINE=false
COMPILE_ONLY=false
RUN_SINGLE_TEST=false
NEW_BASELINES_FILE=''
TESTS_FILE='rt.conf'
SRT_NAME='' SRT_COMPILER=''
while getopts ":col:n:b:" opt; do
  case ${opt} in
    c) CREATE_BASELINE=true ;;
    o) COMPILE_ONLY=true ;;
    l) TESTS_FILE=${OPTARG} ;;
    n) RUN_SINGLE_TEST=true; read -r SRT_NAME SRT_COMPILER <<< "${OPTARG}" ;;
    b) NEW_BASELINES_FILE=$(cd "$(dirname "${OPTARG}")" && pwd -P)/$(basename "${OPTARG}") ;;
    *) echo "bad option" >&2; exit 2 ;;
  esac
done

WORK=$(mktemp -d)
PLAN=${WORK}/plan.txt
: > "${PLAN}"
exec 3>&1  # the real stdout; everything rt.sh prints goes to stderr below
finish() {
  rc=$?
  [[ ${rc} -ne 0 ]] && echo "EXIT" >> "${PLAN}"
  cat "${PLAN}" >&3
  rm -rf "${WORK}"
  exit 0
}
trap finish EXIT

# A shadow PATHRT: real test files (symlinked one by one, so rt_35d's
# `cp tests/X tests/X_date` lands here), copies of the conf files, and stub
# run_compile.sh / run_test.sh that record what would have been run.
mkdir -p "${WORK}/tests" "${WORK}/run" "${WORK}/logs"
for f in "${PATHRT_REAL}"/tests/*; do ln -s "${f}" "${WORK}/tests/"; done
cp "${PATHRT_REAL}"/*.conf "${WORK}/"
cat > "${WORK}/run_test.sh" << 'EOF'
#!/bin/bash
# args: PATHRT RUNDIR_ROOT TEST_NAME TEST_ID COMPILE_ID
source "$2/run_test_$4.env"
echo "RUN $4 | test=$3 | compile=$5 | dep=${DEP_RUN:--}" >> "${PLAN}"
EOF
chmod +x "${WORK}/run_test.sh"
export PLAN

cd "${WORK}"
PATHRT=${WORK}
PATHTR=@PATHTR@
RUNDIR_ROOT=${WORK}/run
LOG_DIR=${WORK}/logs
ROCOTO=false
ECFLOW=false
RTVERBOSE=false
skip_check_results=false
delete_rundir=false
export skip_check_results delete_rundir RTVERBOSE
ACCNR=@ACCNR@ SCHEDULER=@SCHEDULER@ QUEUE=@QUEUE@ COMPILE_QUEUE=@QUEUE@ PARTITION=@PARTITION@
RTPWD=@RTPWD@ NEW_BASELINE=@NEW_BASELINE@ REGRESSIONTEST_LOG=@LOG@ DISKNM=@DISKNM@
INPUTDATA_ROOT=@INPUTDATA_ROOT@
INPUTDATA_ROOT_WW3=${INPUTDATA_ROOT}/WW3
INPUTDATA_LM4=${INPUTDATA_ROOT}/LM4
INPUTDATA_GFSv17opn=@INPUTDATA_GFSv17opn@
TEST_35D=false
# default_vars.sh reads the cloud provider on noaacloud; always set there
[[ ${MACHINE_ID} == noaacloud ]] && export PW_CSP=${PW_CSP:-aws}

die() { echo "$@" >&2; exit 1; }
create_or_run_compile_task() { echo "COMPILE ${COMPILE_ID} | ${MAKE_OPT}" >> "${PLAN}"; }

{
  source "${PATHRT_REAL}/rt_utils.sh"
  eval "$(awk '/^update_rtconf\(\) \{/,/^\}/' "${PATHRT_REAL}/rt.sh")"
  eval "$(awk '/^rt_35d\(\) \{/,/^\}/' "${PATHRT_REAL}/rt.sh")"
  MAIN_LOOP=$(awk '/^declare -A compiles/,/^done < "\$\{TESTS_FILE\}"/' "${PATHRT_REAL}/rt.sh")
  [[ -n ${MAIN_LOOP} ]] || die "could not find the main loop in rt.sh"

  # same order as rt.sh: update_rtconf, then the 35d check, then default_vars
  update_rtconf
  if [[ ${TESTS_FILE} =~ '35d' ]] || [[ ${TESTS_FILE} =~ 'weekly' ]]; then
    TEST_35D=true
  fi
  source "${PATHRT_REAL}/default_vars.sh"
  new_compile=false
  in_metatask=false
  eval "${MAIN_LOOP}"
} 1>&2
