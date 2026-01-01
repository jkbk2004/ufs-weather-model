"""
sequential_executor.py

Phase 1:
- Uses dag_builder.build_dag + topological_sort
- Executes tests sequentially by calling run_compile.sh / run_test.sh
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


def _build_env(base_env, ctx: Any):
    """
    Build environment for a given test context.

    ctx may be a dict or an object.
    """
    env = dict(base_env)

    def get_attr(name, default=None):
        if isinstance(ctx, dict):
            return ctx.get(name, default)
        return getattr(ctx, name, default)

    for attr in ("PATHRT", "RUNDIR", "RUNDIR_ROOT", "LOGDIR", "APP", "TEST_NAME"):
        val = get_attr(attr)
        if val is not None:
            env[attr] = str(val)

    return env


def _get_kind(ctx: Any) -> str:
    if isinstance(ctx, dict):
        k = ctx.get("type") or ctx.get("kind") or ""
    else:
        k = getattr(ctx, "type", None) or getattr(ctx, "kind", None) or ""
    return str(k).lower()


def _get_rundir(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("rundir") or ctx.get("workdir")
    return getattr(ctx, "rundir", None) or getattr(ctx, "workdir", None)


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
