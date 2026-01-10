#!/usr/bin/env python3

from __future__ import annotations
from pathlib import Path


def write_env_file(path: Path, env_vars: dict):
    """Write a .env file with sorted key=value pairs."""
    lines = [f"{k}={v}" for k, v in sorted(env_vars.items())]
    path.write_text("\n".join(lines) + "\n")


def setup_experiment_env(ctx):
    """
    Create experiment-level and test-level environment files.
    Populate run directories.
    Ensure MACHINE_ID, LOG_DIR, SCHEDULER, ACCNR, QUEUE, PARTITION,
    RT_COMPILER, ROCOTO, and all required UFS variables are included.
    """

    expdir = Path(ctx.pathrt)
    rundir_root = Path(ctx.rundir_root)
    machine = ctx.machine_id

    # Machine-level settings
    scheduler = ctx.machine_config.get("SCHEDULER", "")
    accnr = ctx.machine_config.get("ACCNR", "")
    queue = ctx.machine_config.get("QUEUE", "")
    partition = ctx.machine_config.get("PARTITION", "")
    rt_compiler = ctx.machine_config.get("RT_COMPILER", "")

    # Workflow mode (YES/NO)
    rocoto_flag = ctx.extra_vars.get("ROCOTO", "NO")

    # ----------------------------------------------------------------------
    # 1. EXPERIMENT-LEVEL ENV FILE
    # ----------------------------------------------------------------------
    exp_env = {
        # Core paths
        "PATHRT": ctx.pathrt,
        "PATHTR": ctx.patht,
        "RUNDIR_ROOT": ctx.rundir_root,

        # Baseline
        "RTPWD": ctx.rtpwd,
        "NEW_BASELINE": ctx.new_baseline,

        # Input data roots
        "INPUTDATA_ROOT": ctx.inputdata_root,
        "INPUTDATA_ROOT_WW3": ctx.inputdata_root_ww3,
        "INPUTDATA_ROOT_BMIC": ctx.inputdata_root_bmic,
        "INPUTDATA_ROOT_LM4": ctx.inputdata_root_lm4,

        # Machine + experiment metadata
        "MACHINE_ID": machine,
        "SCHEDULER": scheduler,
        "ACCNR": accnr,
        "QUEUE": queue,
        "PARTITION": partition,
        "RT_COMPILER": rt_compiler,
        "ROCOTO": rocoto_flag,
        "EXPID": ctx.expid,
        "APP": ctx.app or "",

        # Logging
        "LOG_DIR": str(ctx.logdir),
    }

    exp_env.update(ctx.extra_vars)

    exp_env_path = expdir / f"{ctx.expid}.env"
    write_env_file(exp_env_path, exp_env)

    # ----------------------------------------------------------------------
    # 2. TEST-LEVEL ENV FILES (compile + run)
    # ----------------------------------------------------------------------
    for t in ctx.tests:

        test_id = t["id"]                     # bare ID expected
        test_type = t.get("type", "")
        parent = t.get("parent", "")          # compile ID for run tasks

        # Create run directory
        test_rundir = rundir_root / test_id
        test_rundir.mkdir(parents=True, exist_ok=True)

        # Base env vars for all tasks
        env_vars = {
            # Core paths
            "PATHRT": ctx.pathrt,
            "PATHTR": ctx.patht,
            "RUNDIR_ROOT": ctx.rundir_root,
            "RUNDIR": str(test_rundir),

            # Baseline + input data
            "RTPWD": ctx.rtpwd,
            "NEW_BASELINE": ctx.new_baseline,
            "INPUTDATA_ROOT": ctx.inputdata_root,
            "INPUTDATA_ROOT_WW3": ctx.inputdata_root_ww3,
            "INPUTDATA_ROOT_BMIC": ctx.inputdata_root_bmic,
            "INPUTDATA_ROOT_LM4": ctx.inputdata_root_lm4,

            # Machine + experiment metadata
            "MACHINE_ID": machine,
            "SCHEDULER": scheduler,
            "ACCNR": accnr,
            "QUEUE": queue,
            "PARTITION": partition,
            "RT_COMPILER": rt_compiler,
            "ROCOTO": rocoto_flag,
            "EXPID": ctx.expid,
            "APP": ctx.app or "",

            # Test metadata
            "TEST_ID": test_id,
            "TEST_TYPE": test_type,
            "MAKE_OPT": t.get("option", ""),

            # Logging
            "LOG_DIR": str(ctx.logdir),
        }

        # ------------------------------------------------------------------
        # Compile tasks: COMPILE_ID must be bare
        # ------------------------------------------------------------------
        if test_type == "compile":
            bare_id = test_id.replace("compile_", "", 1)
            env_vars["COMPILE_ID"] = bare_id
            env_filename = f"compile_{bare_id}.env"

        # ------------------------------------------------------------------
        # Run tasks: TEST_NAME + PARENT_COMPILE_ID
        # ------------------------------------------------------------------
        elif test_type == "run":
            env_vars["TEST_NAME"] = test_id
            env_vars["PARENT_COMPILE_ID"] = parent
            env_filename = f"run_test_{test_id}.env"

        # ------------------------------------------------------------------
        # Fallback (rare)
        # ------------------------------------------------------------------
        else:
            env_filename = f"{test_id}.env"

        # User-specified config overrides
        env_vars.update(ctx.extra_vars)

        if "config" in t:
            for k, v in t["config"].items():
                env_vars[k.upper()] = v

        # Write the env file
        env_path = rundir_root / env_filename
        write_env_file(env_path, env_vars)

    return ctx
