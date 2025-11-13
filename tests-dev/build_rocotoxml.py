import argparse
import yaml
import os
from pathlib import Path
from util.test_loader import TestLoader
from xmlbuilder_rocoto import RocotoXMLBuilder
from setup_experiment_env import setup_experiment_env
from util.shared_utils import extract_bl_date

def enrich_test_context(tests, machine_config, machine_id, force=False):
    filtered = []
    for test in tests:
        turnoff = test.get("turnoff", [])
        if machine_id in turnoff:
            if force:
                print(f"[FORCE] Including test '{test['id']}' despite turnoff for {machine_id}")
                filtered.append(test)
            else:
                print(f"[INFO] Skipping test '{test['id']}' — turned off for {machine_id}")
        else:
            filtered.append(test)
    tests.clear()
    tests.extend(filtered)

def enrich_for_rocoto(tests, machine_config, machine_id):
    for test in tests:
        if test["type"] == "compile":
            test["name"] = f"compile_{test['id']}"
            test["command"] = f"&PATHRT;/run_compile.sh &PATHRT; &RUNDIR_ROOT; \"{test['option']}\" {test['id']} 2>&amp;1 | tee &LOG;/compile_{test['id']}.log"
            test["jobname"] = test["name"]
            test["nodes"] = "1:ppn=8"
            test["walltime"] = "01:00:00"
            test["join"] = f"&RUNDIR_ROOT;/compile_{test['id']}.log"
        elif test["type"] == "run":
            test["name"] = f"{test['id']}_{test['compiler']}"
            test["command"] = f"bash -c 'set -xe -o pipefail ; &PATHRT;/run_test.sh &PATHRT; &RUNDIR_ROOT; {test['id']} {test['name']} {test['parent']} 2>&amp;1 | tee &LOG;/run_{test['name']}.log'"
            test["jobname"] = test["name"]
            res = test["resources"].get(machine_id, {})
            ppn = res.get("ppn", 40)
            nodes = res.get("nodes", 1)
            wlclk = res.get("wlclk", 30)
            test["nodes"] = f"{nodes}:ppn={ppn}"
            test["walltime"] = f"00:{wlclk:02d}:00"
            test["join"] = f"&RUNDIR_ROOT;/{test['name']}.log"
            test["account"] = machine_config.get("ACCOUNT", "epic")
            test["queue"] = machine_config.get("QUEUE", "batch")
            test["partition"] = machine_config.get("PARTITION", machine_id)

def build_rocotoxml():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--manifest", help="Path to app_manifest.yaml")
    parser.add_argument("--yamls_dir", help="Directory of by_app YAMLs")
    parser.add_argument("--user-yaml", help="Path to enriched test YAML")
    parser.add_argument("--test-list", help="Path to test_changes.list")
    parser.add_argument("--single-test", help='Single test case in format "test_id compiler"')
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config_path = Path("machine_config") / f"runtime_config_{args.machine}.yaml"
    with open(config_path) as f:
        machine_config = yaml.safe_load(f)

    if not args.dry_run:
        username = os.environ.get("USER", "unknown")
        for key, value in machine_config.items():
            if isinstance(value, str):
                machine_config[key] = value.replace("{{USER}}", username)

    bl_date = extract_bl_date()
    default_manifest = "app_manifest.yaml"
    loader = TestLoader(args.manifest or default_manifest, args.yamls_dir, bl_date)

    if args.user_yaml:
        loader.load_user_yaml(args.user_yaml)
    elif args.single_test:
        parts = args.single_test.strip().split()
        if len(parts) != 2:
            raise ValueError("[ERROR] --single-test must be in format 'test_id compiler'")
        test_id, compiler = parts

        test_lookup = loader._build_test_lookup()
        if test_id not in test_lookup:
            raise ValueError(f"[ERROR] Test case '{test_id}' not found in {args.yamls_dir}")

        loaded_ids = set()
        run_test = test_lookup[test_id]
        parent_id = run_test.get("parent")

        if parent_id and parent_id not in loaded_ids:
            loader.load_compile_task(parent_id, compiler)
            loaded_ids.add(parent_id)

        if test_id not in loaded_ids:
            loader.load_single_test(test_id, compiler, strict=True)
            loaded_ids.add(test_id)

        for other_id, other_test in test_lookup.items():
            if other_test.get("dependency") == test_id and other_id not in loaded_ids:
                loader.load_single_test(other_id, compiler, strict=True)
                loaded_ids.add(other_id)
    elif args.test_list:
        loader.load_from_test_list(args.test_list)
    else:
        loader.load_manifest()
        loader.attach_yaml_configs()

    tests = loader.get_tests()
    enrich_test_context(tests, machine_config, args.machine, force=args.force)
    enrich_for_rocoto(tests, machine_config, args.machine)

    # ✅ Deduplicate by (id, type)
    unique = {}
    for t in tests:
        key = (t["id"], t["type"])
        if key not in unique:
            unique[key] = t
    tests[:] = list(unique.values())

    pathrt = os.getcwd()
    pathtro = str(Path(pathrt).parent)
    log = f"{pathrt}/logs/log_{args.machine}"
    pid = os.environ.get("EXP_PID", str(os.getpid()))
    rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{pid}"
    rtpwd = f"{machine_config['BASELINE_PATH']}/NEMSfv3gfs/develop-{bl_date}"

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

    enriched_yaml_path = Path(f"enriched_tests_{args.machine}.yaml")
    with open(enriched_yaml_path, "w") as f:
        yaml.dump(tests, f, sort_keys=False, default_flow_style=False)
    print(f"[DEBUG] Enriched test config saved to: {enriched_yaml_path.resolve()}")

    print(f"[DEBUG] Final test count: {len(tests)}")
    for t in tests:
        print(f"  - {t['type']:6} | {t['name']:35} | {t['nodes']:10} | {t['walltime']}")

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
    build_rocotoxml()
