#!/bin/bash
module use -a /work/noaa/epic/conda/modulefiles.orion
module load anaconda/23.7.4
export EXP_PID=$$
python build_rocotoxml.py --machine orion --manifest app_manifest.yaml --output rocoto_orion.xml --yamls_dir tests-yamls/configs/by_app
python build_log.py --yaml enriched_tests_orion.yaml --log-dir logs/log_orion --machine orion --comparison /work/noaa/stmp/jongkim/FV3_RT/rt_$EXP_PID --output logs/RegressionTests_orion.log --options "-a epic -r"
