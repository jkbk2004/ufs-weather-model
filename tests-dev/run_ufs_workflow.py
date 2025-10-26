#!/usr/bin/env python3
import argparse, os, sys
from runtime_manager import RuntimeManager

def build_rocoto_xml(manager, machine, output, args):
    cmd = ["python3", "tests-dev/build_rocotoxml.py", "--machine", machine, "--output", output]
    if args.single_test:
        cmd += ["--single-test", args.single_test, "--yamls_dir", "tests-dev/by_app"]
    elif args.test_list:
        cmd += ["--test-list", args.test_list, "--yamls_dir", "tests-dev/by_app"]
    elif args.baseline_list:
        cmd += ["--test-list", args.baseline_list, "--yamls_dir", "tests-dev/by_app"]
    else:
        cmd += ["--manifest", "tests-dev/app_manifest.yaml", "--yamls_dir", "tests-dev/by_app"]
    if args.force: cmd.append("--force")
    if args.dry_run: cmd.append("--dry-run")
    manager.run_subprocess(cmd)

def run_rocoto(manager, xml, db):
    manager.run_subprocess([os.environ["ROCOTORUN"], "-w", xml, "-d", db])
    manager.run_subprocess([os.environ["ROCOTOSTAT"], "-w", xml, "-d", db])

def run_sequential(manager):
    manager.run_subprocess(["./rt.sh", "-e"])

def main():
    parser = argparse.ArgumentParser(description="Unified UFS workflow runner")
    parser.add_argument("-a", "--account", required=True)
    parser.add_argument("-b", "--baseline-list")
    parser.add_argument("-c", "--create-baseline", action="store_true")
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
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    machine = os.environ.get("MACHINE_ID", "orion")
    lockdir = os.path.join(os.getcwd(), "lock")
    manager = RuntimeManager(lockdir, rocoto=args.rocoto, ecflow=args.ecflow)

    rocoto_xml = "rocoto_workflow.xml"
    rocoto_db = "rocoto_workflow.db"

    if args.rocoto:
        build_rocoto_xml(manager, machine, rocoto_xml, args)
        run_rocoto(manager, rocoto_xml, rocoto_db)
    else:
        run_sequential(manager)

if __name__ == "__main__":
    main()
