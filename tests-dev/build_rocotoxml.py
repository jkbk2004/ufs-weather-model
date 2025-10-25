import argparse
import yaml
import os
from pathlib import Path
from util.test_loader import TestLoader
from xmlbuilder_rocoto import RocotoXMLBuilder
from setup_experiment_env import setup_experiment_env
from util.shared_utils import extract_bl_date, enrich_test_context

def build_rocoto_workflow():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--manifest", help="Path to app_manifest.yaml (ignored if --user-yaml or --test-list is used)")
    parser.add_argument("--yamls_dir", help="Directory of by_app YAMLs (required for --manifest or --test-list)")
    parser.add_argument("--user-yaml", help="Path to user-supplied test YAML", default=None)
    parser.add_argument("--test-list", help="Path to test_changes.list", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load machine config
    config_path = Path("machine_config") / f"runtime_config_{args.machine}.yaml"
    with open(config_path) as f:
        machine_config = yaml.safe_load(f)

    # Replace {{USER}} placeholders
    if not args.dry_run:
        username = os.environ.get("USER", "unknown")
        for key, value in machine_config.items():
            if isinstance(value, str):
                machine_config[key] = value.replace("{{USER}}", username)

    # Extract BL_DATE
    bl_date = extract_bl_date()

    # Load and enrich tests
    loader = TestLoader(args.manifest, args.yamls_dir, bl_date)
    if args.test_list:
        loader.load_from_test_list(args.test_list)
    elif args.user_yaml:
        loader.load_user_yaml(args.user_yaml)
    else:
        loader.load_manifest()
        loader.attach_yaml_configs()

    tests = loader.get_tests()
    enrich_test_context(tests, machine_config, args.machine)

    # Prepare paths
    pathrt = os.getcwd()
    pathtro = str(Path(pathrt).parent)
    log = f"{pathrt}/logs/log_{args.machine}"
    pid = os.environ.get("EXP_PID", str(os.getpid()))
    rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{pid}"
    rtpwd = f"{machine_config['BASELINE_PATH']}/NEMSfv3gfs/develop-{bl_date}"

    # Setup environment
    extra_vars = {
        "CREATE_BASELINE": "false",
        "RT_SUFFIX": "",
        "BL_SUFFIX": "",
        "SCHEDULER": machine_config.get("SCHEDULER", "slurm"),
        "ACCNR": machine_config.get("ACCOUNT", "epic"),
        "QUEUE": machine_config.get("QUEUE", "batch"),
        "PARTITION": machine_config.get("PARTITION", args.machine),
        "ROCOTO": "true",
        "ECFLOW": "false",
        "skip_check_results": "false",
        "delete_rundir": "false",
        "RTVERBOSE": "false"
    }

    setup_experiment_env(
        tests=tests,
        machine_config=machine_config,
        machine_id=args.machine,
        pathrt=pathrt,
        bl_date=bl_date,
        extra_vars=extra_vars
    )

    # Save enriched test config to current directory
    enriched_yaml_path = Path(f"enriched_tests_{args.machine}.yaml")
    with open(enriched_yaml_path, "w") as f:
        yaml.dump(tests, f, sort_keys=False, default_flow_style=False)
    print(f"[DEBUG] Enriched test config saved to: {enriched_yaml_path.resolve()}")

    # Generate Rocoto XML
    builder = RocotoXMLBuilder(
        machine=args.machine,
        machine_config=machine_config,
        pathrt=pathrt,
        pathtro=pathtro,
        log=log,
        rtpwd=rtpwd,
        rundir_root=rundir_root,
        new_baseline=machine_config["NEW_BASELINE_PATH"],
        inputdata_entities=[
            "INPUTDATA_ROOT",
            "INPUTDATA_ROOT_WW3",
            "INPUTDATA_ROOT_BMIC",
            "INPUTDATA_ROOT_LM4"
        ],
        project=machine_config.get("ACCOUNT", "epic"),
        tests=tests,
        bl_date=bl_date,
        dry_run=args.dry_run,
        output_path=args.output
    )

    builder.generate()
    builder.write()

if __name__ == "__main__":
    build_rocoto_workflow()
