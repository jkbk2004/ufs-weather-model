import argparse, yaml, os
from pathlib import Path
from xmlbuilder import RocotoXMLBuilder

def load_baseline_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def get_bl_date(conf_path="bl_date.conf"):
    with open(conf_path) as f:
        line = f.readline().strip()
        return line.split("=")[-1] if "=" in line else line

def resolve_env_vars(path):
    return os.path.expandvars(path)

def extract_inputdata_entities(config, machine):
    return {k: v for k, v in config[machine].items() if k.startswith("INPUTDATA_")}

def get_rtpwd(disknm, bl_date):
    return f"{disknm}/NEMSfv3gfs/develop-{bl_date}"

def get_rundir_root(ptmp):
    return f"{ptmp}/FV3_RT/rt_2882393"

def get_new_baseline(stmp):
    return f"{stmp}/FV3_RT/REGRESSION_TEST"

def load_manifest(path):
    with open(path) as f:
        return yaml.safe_load(f).get("apps", [])

def load_all_app_yamls(yaml_dir):
    merged = {}
    for path in Path(yaml_dir).glob("*.yaml"):
        with open(path) as f:
            merged.update(yaml.safe_load(f))
    return merged

def merge_app_yamls(apps, base_dir):
    merged = {}
    for app in apps:
        app_path = Path(base_dir) / f"{app}.yaml"
        if app_path.exists():
            with open(app_path) as f:
                merged.update(yaml.safe_load(f))
    return merged

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--baseline_yaml", default="baseline_setup.yaml")
    parser.add_argument("--manifest", default="app_manifest.yaml")
    parser.add_argument("--yamls_dir", default="tests-yamls/configs/by_app")
    parser.add_argument("--output", default="workflow.xml")
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    config = load_baseline_config(args.baseline_yaml)
    if args.machine not in config:
        raise ValueError(f"Machine '{args.machine}' not found in baseline config.")

    disknm = resolve_env_vars(config[args.machine]["DISKNM"])
    stmp   = resolve_env_vars(config[args.machine]["STMP"])
    ptmp   = resolve_env_vars(config[args.machine]["PTMP"])
    bl_date = get_bl_date()
    rtpwd = get_rtpwd(disknm, bl_date)
    rundir_root = get_rundir_root(ptmp)
    new_baseline = get_new_baseline(stmp)
    inputdata_entities = extract_inputdata_entities(config, args.machine)
    pathrt = os.getcwd()

    apps = load_manifest(args.manifest)
    rt_yaml = merge_app_yamls(apps, args.yamls_dir)

    builder = RocotoXMLBuilder(
        machine=args.machine,
        rt_yaml=rt_yaml,
        baseline_yaml=args.baseline_yaml,
        project=args.project,
        pathrt=pathrt,
        rtpwd=rtpwd,
        inputdata_entities=inputdata_entities,
        rundir_root=rundir_root,
        new_baseline=new_baseline
    )
    builder.generate()
    builder.write(args.output)

if __name__ == "__main__":
    main()
