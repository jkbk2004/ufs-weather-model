import argparse
import yaml
import os
from pathlib import Path
from test_loader import TestLoader
from xmlbuilder_rocoto import RocotoXMLBuilder

def main():
    parser = argparse.ArgumentParser(description="Build Rocoto XML workflow")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--yamls_dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load machine config
    config_path = Path("machine_config") / f"baseline_{args.machine}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing machine config: {config_path}")
    with open(config_path) as f:
        machine_config = yaml.safe_load(f)

    # Validate required keys
    required_keys = ["RUNDIR_PATH", "BASELINE_PATH", "NEW_BASELINE_PATH"]
    missing = [key for key in required_keys if key not in machine_config]
    if missing:
        raise KeyError(f"Missing keys in machine config: {missing}")

    # Resolve {{USER}} placeholders if not in dry-run mode
    if not args.dry_run:
        username = os.environ.get("USER", "unknown")
        for key, value in machine_config.items():
            if isinstance(value, str):
                machine_config[key] = value.replace("{{USER}}", username)

    # Load baseline date
    bl_date_path = Path("bl_date.conf")
    if not bl_date_path.exists():
        raise FileNotFoundError("Missing bl_date.conf")
    with open(bl_date_path) as f:
        bl_date = f.read().strip()

    # Load and enrich test entries
    loader = TestLoader(args.manifest, args.yamls_dir, bl_date)
    loader.load_manifest()
    loader.inject_baseline_tag()
    loader.attach_yaml_configs()
    tests = loader.get_tests()

    # Inject default compiler if missing
    for test in tests:
        test.setdefault("compiler", machine_config.get("DEFAULT_COMPILER", "unknown"))

    # Initialize builder
    builder = RocotoXMLBuilder(
        machine=args.machine,
        machine_config=machine_config,
        pathrt=machine_config["RUNDIR_PATH"],
        pathtro=machine_config["RUNDIR_PATH"],
        log=f"{machine_config['RUNDIR_PATH']}/logs",
        rtpwd=machine_config["RUNDIR_PATH"],
        rundir_root=f"{machine_config['RUNDIR_PATH']}/tests",
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
