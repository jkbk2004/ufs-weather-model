import argparse, yaml, os
from pathlib import Path
from xmlbuilder_rocoto import RocotoXMLBuilder
from test_loader import TestLoader

def load_baseline_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def get_bl_date(conf_path="bl_date.conf"):
    with open(conf_path) as f:
        for line in f:
            if line.startswith("export BL_DATE="):
                return line.strip().split("=")[-1]
    raise ValueError("BL_DATE not found")

def extract_inputdata_entities(config, machine):
    keys = [
        "INPUTDATA_ROOT", "INPUTDATA_ROOT_WW3",
        "INPUTDATA_ROOT_BMIC", "INPUTDATA_ROOT_LM4"
    ]
    missing = [k for k in keys if k not in config[machine]]
    if missing:
        raise ValueError(f"Missing inputdata keys: {missing}")
    return {k: config[machine][k] for k in keys}

def main():
    parser = argparse.ArgumentParser(description="Generate Rocoto XML workflow")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--baseline_yaml", default="baseline_config.yaml")
    parser.add_argument("--manifest", default="app_manifest.yaml")
    parser.add_argument("--yamls_dir", default="tests-yamls/configs/by_app")
    parser.add_argument("-l", "--list_yaml", help="Unified test YAML (e.g. ufs_test.yaml)")
    parser.add_argument("-n", "--name", help="Single test name and compiler (e.g. 'cpld_control intel')")
    parser.add_argument("-b", "--changes_file", help="Plain text list of test IDs")
    parser.add_argument("--output", default="workflow.xml")
    parser.add_argument("--project", default="default")
    args = parser.parse_args()

    config = load_baseline_config(args.baseline_yaml)
    machine_config = config.get(args.machine)
    if not machine_config:
        raise ValueError(f"Machine '{args.machine}' not found")

    user = os.getenv("USER", "jongkim")
    for k, v in machine_config.items():
        if isinstance(v, str):
            machine_config[k] = v.replace("{{USER}}", user)

    bl_date = get_bl_date()
    pathrt = os.getcwd()
    pathtro = str(Path(pathrt).parent)
    log = os.path.join(pathrt, "logs", f"log_{args.machine}")
    rtpwd = os.path.join(machine_config["BASELINE_PATH"], f"NEMSfv3gfs/develop-{bl_date}")
    rundir_root = os.path.join(machine_config["RUNDIR_PATH"], f"rt_{os.getpid()}")
    new_baseline = machine_config["NEW_BASELIN_PATH"]
    inputdata_entities = extract_inputdata_entities(config, args.machine)

    loader = TestLoader(machine=args.machine)
    if args.list_yaml:
        tests = loader.from_list_yaml(args.list_yaml)
    elif args.name:
        tests = loader.from_name(args.name)
    elif args.changes_file:
        tests = loader.from_changes_file(args.changes_file)
    else:
        tests = loader.from_manifest(args.manifest, args.yamls_dir)

    builder = RocotoXMLBuilder(
        machine=args.machine,
        pathrt=pathrt,
        pathtro=pathtro,
        log=log,
        rtpwd=rtpwd,
        rundir_root=rundir_root,
        new_baseline=new_baseline,
        inputdata_entities=inputdata_entities,
        project=args.project,
        tests=tests
    )
    builder.generate()
    builder.write(args.output)

if __name__ == "__main__":
    main()
