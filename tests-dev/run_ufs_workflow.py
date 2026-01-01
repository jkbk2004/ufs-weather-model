#!/usr/bin/env python3
"""
Unified UFS workflow runner.

- If --rocoto is given: build Rocoto XML (existing behavior).
- Otherwise: run sequential mode using Python DAG executor.
"""

import argparse
import os
import sys
import time

from runtime_manager import RuntimeManager
from util.test_loader import TestLoader
from sequential_executor import run_sequential as run_sequential_executor


def build_rocoto_xml(manager, machine, output, args):
    cmd = ["python3", "build_rocotoxml.py", "--machine", machine, "--output", output]

    yamls_dir = args.yamls_dir if args.yamls_dir else "tests-yamls/configs/by_app"

    if args.single_test:
        cmd += ["--single-test", args.single_test, "--yamls_dir", yamls_dir]
    elif args.test_list:
        cmd += ["--test-list", args.test_list, "--yamls_dir", yamls_dir]
    elif args.baseline_list:
        cmd += ["--test-list", args.baseline_list, "--yamls_dir", yamls_dir]
    elif args.manifest:
        cmd += ["--manifest", args.manifest, "--yamls_dir", yamls_dir]
    else:
        cmd += ["--manifest", "app_manifest.yaml", "--yamls_dir", yamls_dir]

    if args.user_yaml:
        cmd += ["--user-yaml", args.user_yaml]

    if args.force:
        cmd.append("--force")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.create_baseline:
        cmd.append("--create-baseline")

    print(f"[INFO] Using yamls_dir: {yamls_dir}")
    manager.run_subprocess(cmd)


def run_rocoto(manager, xml, db, once=False, sleep_interval=None, max_iterations=None):
    """Drive Rocoto until workflow completion (or once if requested)."""
    rocotorun = os.environ.get("ROCOTORUN", "rocotorun")
    rocotostat = os.environ.get("ROCOTOSTAT", "rocotostat")
    sleep_interval = sleep_interval or int(os.environ.get("ROCOTO_SLEEP", "60"))

    iteration = 0
    while True:
        iteration += 1
        print(f"[INFO] Iteration {iteration}: running {rocotorun}...")
        run_proc = manager.run_subprocess(
            [rocotorun, "-w", xml, "-d", db],
            capture_output=True,
            text=True
        )
        print("[DEBUG] rocotorun returncode:", getattr(run_proc, "returncode", None))
        print("[DEBUG] rocotorun stdout:", getattr(run_proc, "stdout", None))
        print("[DEBUG] rocotorun stderr:", getattr(run_proc, "stderr", None))

        print(f"[INFO] Checking status with {rocotostat}...")
        status_proc = manager.run_subprocess(
            [rocotostat, "-w", xml, "-d", db],
            capture_output=True,
            text=True
        )
        print("[DEBUG] rocotostat returncode:", getattr(status_proc, "returncode", None))
        print("[DEBUG] rocotostat stdout:", getattr(status_proc, "stdout", None))
        print("[DEBUG] rocotostat stderr:", getattr(status_proc, "stderr", None))

        status_output = status_proc.stdout or ""

        if "Done" in status_output:
            print("[INFO] Workflow completed successfully.")
            break

        if once:
            print("[INFO] Single-run mode enabled. Exiting after one iteration.")
            break

        if max_iterations and iteration >= max_iterations:
            print("[WARN] Reached max iterations without completion. Exiting.")
            break

        print(f"[INFO] Sleeping {sleep_interval} seconds before next iteration...")
        time.sleep(sleep_interval)


def load_test_contexts(args, machine):
    """
    Use existing TestLoader to build the test list for both Rocoto and sequential.
    """
    yamls_dir = args.yamls_dir if args.yamls_dir else "tests-yamls/configs/by_app"

    loader = TestLoader(
        machine=machine,
        yamls_dir=yamls_dir,
    )

    if args.single_test:
        loader.load_single_test(args.single_test, compiler_override=None, strict=False)
    elif args.test_list:
        loader.load_from_test_list(args.test_list)
    elif args.baseline_list:
        loader.load_from_test_list(args.baseline_list)
    elif args.manifest:
        loader.load_manifest(args.manifest)
        loader.attach_yaml_configs()
    else:
        loader.load_manifest("app_manifest.yaml")
        loader.attach_yaml_configs()

    if args.user_yaml:
        loader.load_user_yaml(args.user_yaml)

    tests = loader.get_tests()

    test_contexts = {}
    for t in tests:
        test_id = t.get("id")
        if not test_id:
            continue
        test_contexts[test_id] = t

    return test_contexts


def run_sequential(manager, args, machine):
    """
    Sequential mode:
    - load/enrich tests from YAMLs/manifest (same inputs as Rocoto)
    - build DAG
    - run tests sequentially via run_compile.sh / run_test.sh
    """
    print("[INFO] Sequential mode selected (Python DAG executor)")

    test_contexts = load_test_contexts(args, machine)
    if not test_contexts:
        print("[WARN] No tests loaded for sequential mode.")
        return 0

    rc = run_sequential_executor(test_contexts)
    return rc


def main():
    parser = argparse.ArgumentParser(description="Unified UFS workflow runner")
    parser.add_argument("-a", "--account", required=True)
    parser.add_argument("-b", "--baseline-list")
    parser.add_argument("-c", "--create-baseline", action="store_true",
                        help="Enable baseline creation setup (propagates to CREATE_BASELINE)")
    parser.add_argument("-d", "--delete-rundir", action="store_true")
    parser.add_argument("-e", "--ecflow", action="store_true")
    parser.add_argument("-k", "--keep-rundir", action="store_true")
    parser.add_argument("-l", "--test-list")
    parser.add_argument("-m", "--compare-baseline", action="store_true")
    parser.add_argument("-n", "--single-test")
    parser.add_argument("-o", "--compile-only", action="store_true")
    parser.add_argument("-r", "--rocoto", action="store_true")
    parser.add_argument("-w", "--weekly", action="store_true")
    parser.add_argument("-s", "--link-tests", action="store_true")
    parser.add_argument("-f", "--manifest", default="app_manifest.yaml",
                        help="Path to user-provided manifest file (default: app_manifest.yaml)")
    parser.add_argument("-y", "--yamls_dir",
                        help="Directory of by_app YAMLs (required for manifest, test-list, or single-test)")
    parser.add_argument("-u", "--user-yaml", default=None,
                        help="Path to user-supplied test YAML")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Baseline flag
    os.environ["CREATE_BASELINE"] = "true" if args.create_baseline else "false"
    print(f"[DEBUG] CREATE_BASELINE={os.environ['CREATE_BASELINE']}")

    # Optional compare-baseline flag (if used by scripts)
    if args.compare_baseline:
        os.environ["COMPARE_BASELINE"] = "true"
    else:
        os.environ.setdefault("COMPARE_BASELINE", "false")
    print(f"[DEBUG] COMPARE_BASELINE={os.environ['COMPARE_BASELINE']}")

    machine = os.environ.get("MACHINE_ID", "orion")
    lockdir = os.path.join(os.getcwd(), "lock")
    manager = RuntimeManager(lockdir, rocoto=args.rocoto, ecflow=args.ecflow)

    rocoto_xml = "rocoto_workflow.xml"
    rocoto_db = "rocoto_workflow.db"

    if args.rocoto:
        build_rocoto_xml(manager, machine, rocoto_xml, args)
        # To drive Rocoto from here, uncomment:
        # run_rocoto(manager, rocoto_xml, rocoto_db,
        #            once=False, sleep_interval=60, max_iterations=None)
    else:
        rc = run_sequential(manager, args, machine)
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
