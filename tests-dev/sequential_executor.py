"""
sequential_executor.py

Execute UFS regression tests sequentially using the unified experiment
context. This executor is deterministic, scheduler-free, and ideal for
local development and CI/CD environments.

Assumptions:
  - setup_experiment_env() has already created all experiment directories
    and exported experiment-level environment variables.
  - dag_builder.build_dag() has produced a valid DAG of test dependencies.
  - Each test is a DICTIONARY with keys:
        id: str
        type: "compile", "run", or "combined"
        rundir: str
        logfile: str
        compile_script: str
        run_script: str
"""

from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Dict
import networkx as nx


class SequentialExecutor:
    """
    Execute tests in topological order according to the DAG.
    """

    def __init__(
        self,
        dag: nx.DiGraph,
        expdir: Path,
        rundir_root: Path,
        logdir: Path,
        extra_vars: Dict[str, str],
    ):
        self.dag = dag
        self.expdir = Path(expdir)
        self.rundir_root = Path(rundir_root)
        self.logdir = Path(logdir)
        self.extra_vars = extra_vars

    # ------------------------------------------------------------------
    def run(self):
        """
        Execute all tests in topological order.
        """
        ordered_tests = list(nx.topological_sort(self.dag))

        print(f"Sequential execution order ({len(ordered_tests)} tests):")
        for t in ordered_tests:
            print(f"  - {t}")

        for test_id in ordered_tests:
            test = self.dag.nodes[test_id]["test"]
            self._run_single_test(test)

    # ------------------------------------------------------------------
    def _run_single_test(self, test: Dict):
        """
        Run a single test (compile, run, or combined).
        """

        test_id = test["id"]
        print(f"\n=== Running test: {test_id} ===")

        # Per-test environment variables
        env = os.environ.copy()
        env["TEST_NAME"] = test_id
        env["RUNDIR"] = test["rundir"]
        env["LOGFILE"] = test["logfile"]

        # Add experiment-level variables
        for k, v in self.extra_vars.items():
            env[k] = str(v)

        # Ensure run directory exists
        Path(test["rundir"]).mkdir(parents=True, exist_ok=True)

        # Compile phase
        if test["type"] in ("compile", "combined"):
            self._run_phase(
                phase="compile",
                script=test["compile_script"],
                test=test,
                env=env,
            )

        # Run phase
        if test["type"] in ("run", "combined"):
            self._run_phase(
                phase="run",
                script=test["run_script"],
                test=test,
                env=env,
            )

        print(f"=== Completed test: {test_id} ===")

    # ------------------------------------------------------------------
    def _run_phase(self, phase: str, script: str, test: Dict, env: Dict[str, str]):
        """
        Execute a single phase (compile or run) of a test.
        """

        test_id = test["id"]
        print(f"  -> {phase.upper()} phase")

        script_path = Path(script)
        if not script_path.exists():
            raise FileNotFoundError(
                f"{phase} script not found for test {test_id}: {script}"
            )

        logfile = Path(test["logfile"])
        logfile.parent.mkdir(parents=True, exist_ok=True)

        with open(logfile, "a") as log:
            log.write(f"\n===== {phase.upper()} PHASE: {test_id} =====\n")

            proc = subprocess.Popen(
                ["/bin/bash", str(script_path)],
                cwd=test["rundir"],
                stdout=log,
                stderr=log,
                env=env,
            )
            ret = proc.wait()

        if ret != 0:
            raise RuntimeError(
                f"{phase} phase failed for test {test_id} with exit code {ret}"
            )

        print(f"    {phase} phase OK")


# ----------------------------------------------------------------------
def run(
    dag: nx.DiGraph,
    expdir: Path,
    rundir_root: Path,
    logdir: Path,
    extra_vars: Dict[str, str],
):
    """
    Convenience wrapper used by run_ufs_workflow.py.
    """
    executor = SequentialExecutor(
        dag=dag,
        expdir=expdir,
        rundir_root=rundir_root,
        logdir=logdir,
        extra_vars=extra_vars,
    )
    executor.run()
