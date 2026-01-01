"""
sequential_executor.py

Sequential execution of UFS tests using a Python DAG executor.
Mirrors Rocoto's environment setup for run_compile.sh and run_test.sh.
"""

import os
import subprocess
from typing import Dict, Any

from dag_builder import build_dag, topological_sort


class SequentialRunError(Exception):
    """Raised when a sequential run cannot proceed."""
    pass


def _run_command(cmd, cwd=None, env=None):
    """
    Run a shell command synchronously.

    Parameters
    ----------
    cmd : str or list[str]
        Command to execute.
    cwd : str, optional
        Working directory.
    env : dict, optional
        Environment variables.

    Returns
    -------
    int
        Return code.
    """
    print(f"[SEQ] Executing: {cmd} (cwd={cwd})")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        shell=isinstance(cmd, str),
        text=True,
    )
    return result.returncode


def _get_attr(ctx: Any, name: str, default=None):
    if isinstance(ctx, dict):
        return ctx.get(name, default)
    return getattr(ctx, name, default)


def _get_kind(ctx: Any) -> str:
    k = _get_attr(ctx, "type") or _get_attr(ctx, "kind") or ""
    return str(k).lower()


def _get_rundir(ctx: Any) -> str:
    return _get_attr(ctx, "rundir") or _get_attr(ctx, "workdir")


def _build_env(base_env, ctx: Any):
    """
    Build environment for a given test context.
    Mirrors Rocoto <envar> injection.
    """
    env = dict(base_env)

    test_id = _get_attr(ctx, "id")
    app = _get_attr(ctx, "APP", _get_attr(ctx, "app", "ufs"))
    pathrt = _get_attr(ctx, "PATHRT", os.getcwd())
    rundir_root = _get_attr(ctx, "RUNDIR_ROOT", os.path.join(os.getcwd(), "run"))
    logdir = _get_attr(ctx, "LOGDIR", os.path.join(os.getcwd(), "logs"))
    rundir = _get_rundir(ctx)

    # Core Rocoto-style envs
    if test_id is not None:
        env["TEST_NAME"] = str(test_id)
    env["APP"] = str(app)
    env["PATHRT"] = str(pathrt)
    env["RUNDIR_ROOT"] = str(rundir_root)
    env["LOGDIR"] = str(logdir)

    if rundir:
        env["RUNDIR"] = str(rundir)

    # Baseline flags (already set by run_ufs_workflow)
    env["CREATE_BASELINE"] = os.environ.get("CREATE_BASELINE", "false")
    env["COMPARE_BASELINE"] = os.environ.get("COMPARE_BASELINE", "false")

    return env


def run_sequential(test_contexts: Dict[str, Any]) -> int:
    """
    Run all tests sequentially using the DAG derived from test_contexts.

    Parameters
    ----------
    test_contexts : dict[str, Any]
        Mapping from test id/name to an enriched context (dict or object).

    Returns
    -------
    int
        0 on success, non-zero on first failure.
    """
    dag = build_dag(test_contexts)
    order = topological_sort(dag)

    print("[SEQ] Topological order:")
    for n in order:
        print(f"  - {n}")

    base_env = os.environ.copy()

    for name in order:
        ctx = test_contexts[name]

        kind = _get_kind(ctx)
        if "compile" in kind:
            script = "./run_compile.sh"
        else:
            script = "./run_test.sh"

        rundir = _get_rundir(ctx)
        if rundir is None:
            raise SequentialRunError(f"Test {name} has no rundir/workdir defined")

        env = _build_env(base_env, ctx)

        print(f"[SEQ] Running {name} ({kind}) in {rundir} using {script}")
        rc = _run_command(script, cwd=rundir, env=env)

        if rc != 0:
            print(f"[SEQ][FAIL] {name} failed with return code {rc}")
            return rc

        print(f"[SEQ][OK] {name} completed successfully")

    print("[SEQ] All tests completed successfully")
    return 0
