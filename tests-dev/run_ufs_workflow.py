#!/usr/bin/env python3

from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
import time

SCRIPT_DIR = Path(__file__).resolve().parent
UTIL_DIR = SCRIPT_DIR / "util"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(UTIL_DIR))

from util.arg_parser import build_workflow_arg_parser
from util.machine_config import load_machine_config
from util.test_loader import TestLoader

from prepare_experiment_context import prepare_experiment_context
from setup_experiment_env import setup_experiment_env

from dag_builder import build_dag
from sequential_executor import run as run_sequential

from build_rocotoxml import write_rocotoxml_from_ctx


def load_bl_date():
    f = SCRIPT_DIR / "bl_date.conf"
    if not f.exists():
        return None
    for line in f.read_text().splitlines():
        if "BL_DATE=" in line:
            val = line.split("=", 1)[1].strip()
            return f"develop-{val}" if val.isdigit() else val
    return None


def run_with_modules(cmd: str, module_commands: list[str]):
    if module_commands:
        module_cmd = " && ".join(module_commands)
        full_cmd = f"{module_cmd} && {cmd}"
    else:
        full_cmd = cmd
    return subprocess.run(["bash", "-lc", full_cmd])


def run_rocoto(expid: str, module_commands: list[str]):
    cmd = f"rocotorun -w {expid}.xml -d {expid}.db -c 197001010000"
    run_with_modules(cmd, module_commands)


def monitor_rocoto(expid: str, module_commands: list[str]):
    cmd = f"rocotostat -w {expid}.xml -d {expid}.db"
    while True:
        run_with_modules(cmd, module_commands)
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            break


def main(args):

    # -----------------------------
    # Load machine config
    # -----------------------------
    machine = args.machine
    machine_config = load_machine_config(machine)

    module_commands = machine_config.get("MODULE_COMMANDS", [])

    PATHRT = str(SCRIPT_DIR)
    PATHTR = str(SCRIPT_DIR.parent)
    LOG = str(SCRIPT_DIR / "logs" / f"log_{machine}")
    RUNDIR_ROOT = args.rundir_root

    # -----------------------------
    # Baseline date
    # -----------------------------
    bl_date = load_bl_date()
    baseline_root = machine_config.get("BASELINE_PATH", "")
    RTPWD = f"{baseline_root}/{bl_date}" if bl_date else baseline_root

    # -----------------------------
    # New baseline path
    # -----------------------------
    user = os.environ.get("USER", "unknown")
    new_baseline_root = machine_config.get("NEW_BASELINE_PATH", "/work/noaa/stmp")
    default_new_baseline = f"{new_baseline_root}/{user}/FV3_RT/REGRESSION_TEST"

    if args.users_baseline:
        NEW_BASELINE = args.users_baseline
    elif args.create_baseline:
        NEW_BASELINE = default_new_baseline
    else:
        NEW_BASELINE = default_new_baseline

    # -----------------------------
    # Input data paths
    # -----------------------------
    INPUTDATA_ROOT = machine_config.get("INPUTDATA_ROOT", "")
    INPUTDATA_ROOT_WW3 = machine_config.get("INPUTDATA_ROOT_WW3", "")
    INPUTDATA_ROOT_BMIC = machine_config.get("INPUTDATA_ROOT_BMIC", "")
    INPUTDATA_ROOT_LM4 = machine_config.get("INPUTDATA_ROOT_LM4", "")

    # -----------------------------
    # Load tests (FIXED: pass machine_config)
    # -----------------------------
    loader = TestLoader(
        manifest_path=args.manifest,
        yamls_dir=args.yamls_dir,
        bl_date=bl_date or "unknown",
        machine_config=machine_config,
    )

    if args.user_yaml:
        loader.load_user_yaml(args.user_yaml)
    elif args.test_list:
        loader.load_from_test_list(args.test_list)
    elif args.single_test:
        loader.load_single_test(args.single_test, strict=True)
    else:
        loader.load_manifest()
        loader.attach_yaml_configs()

    tests = loader.get_tests()

    # -----------------------------
    # Extra vars for templates
    # -----------------------------
    extra_vars = {
        "CREATE_BASELINE": "true" if args.create_baseline else "false",
        "RTVERBOSE": "true" if args.rtverbose else "false",
        "skip_check_results": "true" if args.skip_check_results else "false",
        "delete_rundir": "true" if args.delete_rundir else "false",
        "RT_SUFFIX": args.rt_suffix or "",
        "BL_SUFFIX": args.bl_suffix or "",
    }

    # -----------------------------
    # Build experiment context
    # -----------------------------
    ctx = prepare_experiment_context(
        tests=tests,
        machine=machine,
        machine_config=machine_config,
        pathrt=PATHRT,
        patht=PATHTR,
        rundir_root=RUNDIR_ROOT,
        rtpwd=RTPWD,
        new_baseline=NEW_BASELINE,
        inputdata_root=INPUTDATA_ROOT,
        inputdata_root_ww3=INPUTDATA_ROOT_WW3,
        inputdata_root_bmic=INPUTDATA_ROOT_BMIC,
        inputdata_root_lm4=INPUTDATA_ROOT_LM4,
        extra_vars=extra_vars,
        expid=args.expid,
        app=args.app,
    )

    ctx.logdir = LOG  # for template

    ctx = setup_experiment_env(ctx)

    # -----------------------------
    # Build DAG
    # -----------------------------
    dag = build_dag(ctx.tests)

    # -----------------------------
    # Sequential mode
    # -----------------------------
    if args.sequential:
        run_sequential(
            dag=dag,
            expdir=Path(PATHRT),
            rundir_root=Path(RUNDIR_ROOT),
            logdir=Path(LOG),
            extra_vars=extra_vars,
        )
        return

    # -----------------------------
    # Rocoto mode
    # -----------------------------
    if args.rocoto:
        print("Generating Rocoto XML (template-based)...")
        write_rocotoxml_from_ctx(ctx)
        print("Rocoto XML generation complete.")

        if args.run_rocoto:
            run_rocoto(args.expid, module_commands)

        if args.monitor_rocoto:
            monitor_rocoto(args.expid, module_commands)

        return

    print("ERROR: Must specify --sequential or --rocoto")
    sys.exit(1)


if __name__ == "__main__":
    parser = build_workflow_arg_parser()
    args = parser.parse_args()
    main(args)
