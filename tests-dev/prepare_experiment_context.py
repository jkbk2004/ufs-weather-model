#!/usr/bin/env python3

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExperimentContext:
    machine_id: str
    machine_config: dict
    expid: str
    app: str | None

    # Core paths
    pathrt: Path
    patht: Path
    expdir: Path
    rundir_root: Path
    logdir: Path

    # Baseline
    rtpwd: str
    new_baseline: str

    # Input data roots
    inputdata_root: str
    inputdata_root_ww3: str
    inputdata_root_bmic: str
    inputdata_root_lm4: str

    # Extra vars for env files
    extra_vars: dict

    # Tests (enriched later)
    tests: list


def prepare_experiment_context(
    *,
    tests,
    machine,
    machine_config,
    pathrt,
    patht,
    rundir_root,
    rtpwd,
    new_baseline,
    inputdata_root,
    inputdata_root_ww3,
    inputdata_root_bmic,
    inputdata_root_lm4,
    extra_vars,
    expid,
    app,
):
    """
    Pure function: compute experiment-level context.
    Does NOT create directories or write files.
    """

    pathrt = Path(pathrt)
    patht = Path(patht)
    rundir_root = Path(rundir_root)

    expdir = patht
    logdir = pathrt / "logs" / f"log_{machine}"
    logdir.mkdir(parents=True, exist_ok=True)

    return ExperimentContext(
        machine_id=machine,
        machine_config=machine_config,
        expid=expid,
        app=app,
        pathrt=pathrt,
        patht=patht,
        expdir=expdir,
        rundir_root=rundir_root,
        logdir=logdir,
        rtpwd=rtpwd,
        new_baseline=new_baseline,
        inputdata_root=inputdata_root,
        inputdata_root_ww3=inputdata_root_ww3,
        inputdata_root_bmic=inputdata_root_bmic,
        inputdata_root_lm4=inputdata_root_lm4,
        extra_vars=extra_vars,
        tests=tests,
    )
