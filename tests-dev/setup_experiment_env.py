#!/usr/bin/env python3

from __future__ import annotations
import os
from pathlib import Path


def write_env_file(path: Path, env_vars: dict):
    """Write a .env file with sorted key=value pairs."""
    lines = [f"{k}={v}" for k, v in sorted(env_vars.items())]
    path.write_text("\n".join(lines) + "\n")


def setup_experiment_env(ctx):
    """
    Create experiment-level and test-level environment files.
    Populate run directories.
    Ensure MACHINE_ID is included in every .env file.
    """

    expdir = Path(ctx.pathrt)
    rundir_root = Path(ctx.rundir_root)
    machine = ctx.machine_id  # ⭐ FIXED

    # ----------------------------------------------------------------------
    # 1. EXPERIMENT-LEVEL ENV FILE
    # ----------------------------------------------------------------------
    exp_env = {
        "PATHRT": ctx.pathrt,
        "PATHTR": ctx.patht,
        "RUNDIR_ROOT": ctx.rundir_root,
        "RTPWD": ctx.rtpwd,
        "NEW_BASELINE": ctx.new_baseline,
        "INPUTDATA_ROOT": ctx.inputdata_root,
        "INPUTDATA_ROOT_WW3": ctx.inputdata_root_ww3,
        "INPUTDATA_ROOT_BMIC": ctx.inputdata_root_bmic,
        "INPUTDATA_ROOT_LM4": ctx.inputdata_root_lm4,
        "MACHINE_ID": machine,
        "EXPID": ctx.expid,
        "APP": ctx.app or "",
    }

    exp_env.update(ctx.extra_vars)

    exp_env_path = expdir / f"{ctx.expid}.env"
    write_env_file(exp_env_path, exp_env)

    # ----------------------------------------------------------------------
    # 2. TEST-LEVEL ENV FILES
    # ----------------------------------------------------------------------
    for t in ctx.tests:

        test_id = t["id"]
        test_rundir = rundir_root / test_id
        test_rundir.mkdir(parents=True, exist_ok=True)

        env_vars = {
            "PATHRT": ctx.pathrt,
            "PATHTR": ctx.patht,
            "RUNDIR_ROOT": ctx.rundir_root,
            "RUNDIR": str(test_rundir),
            "RTPWD": ctx.rtpwd,
            "NEW_BASELINE": ctx.new_baseline,
            "INPUTDATA_ROOT": ctx.inputdata_root,
            "INPUTDATA_ROOT_WW3": ctx.inputdata_root_ww3,
            "INPUTDATA_ROOT_BMIC": ctx.inputdata_root_bmic,
            "INPUTDATA_ROOT_LM4": ctx.inputdata_root_lm4,
            "MACHINE_ID": machine,
            "EXPID": ctx.expid,
            "APP": ctx.app or "",
            "TEST_ID": test_id,
            "TEST_TYPE": t.get("type", ""),
            "MAKE_OPT": t.get("option", ""),
        }

        env_vars.update(ctx.extra_vars)

        if "config" in t:
            for k, v in t["config"].items():
                env_vars[k.upper()] = v

        env_path = rundir_root / f"{test_id}.env"
        write_env_file(env_path, env_vars)

    return ctx
