#!/bin/bash
module use -a /work/noaa/epic/conda/modulefiles.orion
module load anaconda/23.7.4
export EXP_PID=$$
python build_rocotoxml.py --machine orion --manifest app_manifest.yaml --output rocoto_orion.xml --yamls_dir tests-yamls/configs/by_app
