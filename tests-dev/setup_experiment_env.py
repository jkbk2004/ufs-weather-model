import os
import shutil
from pathlib import Path
from util.shared_utils import extract_bl_date

def rrmdir(path):
    shutil.rmtree(path)

def prepare_runtime_environment(pathrt, rundir_root, machine_id):
    run_dir_path = Path(pathrt) / "run_dir"
    log_dir_path = Path(pathrt) / "logs" / f"log_{machine_id}"

    if run_dir_path.is_symlink() or run_dir_path.is_file():
        run_dir_path.unlink()
    elif run_dir_path.is_dir():
        rrmdir(run_dir_path)

    os.symlink(rundir_root, run_dir_path)
    os.makedirs(log_dir_path, exist_ok=True)
    return str(log_dir_path)

def write_env_file(env_path, env_vars):
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"📄 Wrote {env_path.name} to {env_path}")

def setup_experiment_env(tests, machine_config, machine_id, pathrt, bl_date, extra_vars):
    rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{os.getpid()}"
    rtpwd = f"{machine_config['BASELINE_PATH']}/NEMSfv3gfs/develop-{bl_date}"
    new_baseline = f"{machine_config['RUNDIR_PATH']}/FV3_RT/REGRESSION_TEST}"
    log_dir = prepare_runtime_environment(pathrt, rundir_root, machine_id)

    for i, test in enumerate(tests):
        test_id = test["id"]
        test_type = test.get("type", "run")
        test_dir = Path(rundir_root) / (f"compile_{test_id}" if test_type == "compile" else test_id)
        test_dir.mkdir(parents=True, exist_ok=True)

        # 🧾 Place .env file directly under rundir_root
        env_filename = f"compile_{test_id}.env" if test_type == "compile" else f"run_test_{test_id}.env"
        env_path = Path(rundir_root) / env_filename

        res = test.get("resources", {}).get(machine_id, {})
        env_vars = {
            "JOB_NR": i + 1,
            "TEST_ID": test_id,
            "MACHINE_ID": machine_id,
            "RT_COMPILER": test.get("compiler"),
            "RTPWD": rtpwd,
            "INPUTDATA_ROOT": machine_config.get("INPUTDATA_ROOT", "/inputdata"),
            "INPUTDATA_ROOT_WW3": machine_config.get("INPUTDATA_ROOT_WW3", "/inputdata_ww3"),
            "INPUTDATA_ROOT_BMIC": machine_config.get("INPUTDATA_ROOT_BMIC", "/inputdata_bmic"),
            "INPUTDATA_LM4": f"{machine_config.get('INPUTDATA_ROOT', '/inputdata')}/LM4_input_data",
            "PATHRT": pathrt,
            "PATHTR": str(Path(pathrt).parent),
            "NEW_BASELINE": new_baseline,
            "CREATE_BASELINE": extra_vars.get("CREATE_BASELINE", "false"),
            "RT_SUFFIX": extra_vars.get("RT_SUFFIX", ""),
            "BL_SUFFIX": extra_vars.get("BL_SUFFIX", ""),
            "SCHEDULER": extra_vars.get("SCHEDULER", "slurm"),
            "ACCNR": extra_vars.get("ACCNR", "default"),
            "QUEUE": extra_vars.get("QUEUE", "batch"),
            "PARTITION": extra_vars.get("PARTITION", "compute"),
            "ROCOTO": extra_vars.get("ROCOTO", "true"),
            "ECFLOW": extra_vars.get("ECFLOW", "false"),
            "REGRESSIONTEST_LOG": f"{pathrt}/regression.log",
            "LOG_DIR": log_dir,
            "DEP_RUN": test.get("dependency", ""),
            "skip_check_results": extra_vars.get("skip_check_results", "false"),
            "delete_rundir": extra_vars.get("delete_rundir", "false"),
            "WLCLK": res.get("wlclk", "00:30:00"),
            "RTVERBOSE": extra_vars.get("RTVERBOSE", "false")
        }

        write_env_file(env_path, env_vars)

    return rundir_root, rtpwd, log_dir
