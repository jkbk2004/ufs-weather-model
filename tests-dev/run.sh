#!/bin/bash
export EXP_PID=$$

pid = os.environ.get("EXP_PID", str(os.getpid()))
rundir_root = f"{machine_config['RUNDIR_PATH']}/rt_{pid}"

python build_rocotoxml.py --machine orion --manifest app_manifest.yaml --output rocoto_orion.xml --yamls_dir tests-yamls/configs/by_app
