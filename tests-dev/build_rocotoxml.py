import argparse
import yaml
import os
from pathlib import Path
from test_loader import TestLoader
from xmlbuilder_rocoto import RocotoXMLBuilder
from setup_experiment_env import setup_experiment_env
from shared_utils import extract_bl_date, enrich_test_context

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--yamls_dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load machine config
    config_path = Path("machine_config") / f"baseline_{args.machine}.yaml"
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
    loader.load_manifest()
    loader.attach_yaml_configs()
    tests = loader.get_tests()
    enrich_test_context(tests, machine_config, args.machine)

    # Prepare paths
    pathrt = os.getcwd()
    pathtro = str(Path(pathrt).parent)
    log = f"{pathrt}/logs/log_{args.machine}"
    rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{os.getpid()}"
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
    main()
