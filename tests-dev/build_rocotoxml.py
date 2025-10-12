import argparse
import yaml
import os
from pathlib import Path
from test_loader import TestLoader
from xmlbuilder_rocoto import RocotoXMLBuilder

def enrich_test_context(tests, machine_config, machine):
    for test in tests:
        if test["type"] == "compile":
            test["name"] = f"compile_{test['id']}"
            test["jobname"] = test["name"]
            test["command"] = (
                f"&PATHRT;/run_compile.sh &PATHRT; &RUNDIR_ROOT; \"{test['option']}\" {test['id']} "
                f"2>&1 | tee &LOG;/compile_{test['id']}.log"
            )
            test["nodes"] = "1:ppn=8"
            test["walltime"] = "01:00:00"

        elif test["type"] == "run":
            test["name"] = f"{test['id']}_{test['compiler']}"
            test["jobname"] = test["name"]
            test["command"] = (
                f"bash -c 'set -xe -o pipefail ; &PATHRT;/run_test.sh &PATHRT; &RUNDIR_ROOT; "
                f"{test['id']} {test['name']} {test['parent']} 2>&1 | tee &LOG;/run_{test['name']}.log'"
            )

            ppn = 40
            nodes = 8
            wlclk = 30
            resources = test.get("resources", {})
            if machine in resources:
                r = resources[machine]
                ppn = r.get("ppn", ppn)
                nodes = r.get("nodes", nodes)
                wlclk = r.get("wlclk", wlclk)

            test["nodes"] = f"{nodes}:ppn={ppn}"
            test["walltime"] = f"00:{wlclk:02}:00"

        test["account"] = machine_config.get("ACCOUNT", "epic")
        test["queue"] = machine_config.get("QUEUE", "batch")
        test["partition"] = machine
        test["join"] = f"&RUNDIR_ROOT;/{test['name']}.log"

def extract_bl_date(filepath="bl_date.conf"):
    with open(filepath) as f:
        for line in f:
            if line.startswith("export BL_DATE="):
                return line.split("=")[1].strip()
    raise ValueError("BL_DATE not found in bl_date.conf")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--yamls_dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = Path("machine_config") / f"baseline_{args.machine}.yaml"
    with open(config_path) as f:
        machine_config = yaml.safe_load(f)

    if not args.dry_run:
        username = os.environ.get("USER", "unknown")
        for key, value in machine_config.items():
            if isinstance(value, str):
                machine_config[key] = value.replace("{{USER}}", username)

    bl_date = extract_bl_date()

    loader = TestLoader(args.manifest, args.yamls_dir, bl_date)
    loader.load_manifest()
    loader.attach_yaml_configs()
    tests = loader.get_tests()

    enrich_test_context(tests, machine_config, args.machine)

    pathrt = os.getcwd()
    pathtro = str(Path(pathrt).parent)
    log = f"{pathrt}/logs/log_{args.machine}"
    rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{os.getpid()}"
    rtpwd = f"{machine_config['BASELINE_PATH']}/NEMSfv3gfs/develop-{bl_date}"

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
