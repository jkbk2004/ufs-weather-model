#!/usr/bin/env python3
import argparse, os, sys
from runtime_manager import RuntimeManager

def build_rocoto_xml(manager, machine, output, args):
    cmd = ["python3", "build_rocotoxml.py", "--machine", machine, "--output", output]

    # Use user-provided yamls_dir if available, else default
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

    print(f"[INFO] Using yamls_dir: {yamls_dir}")
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
    parser.add_argument("-f", "--manifest", default="app_manifest.yaml",
                        help="Path to user-provided manifest file (default: app_manifest.yaml)")
    parser.add_argument("-y", "--yamls_dir",
                        help="Directory of by_app YAMLs (required for manifest, test-list, or single-test)")
    parser.add_argument("-u", "--user-yaml", default=None,
                        help="Path to user-supplied test YAML")    
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
