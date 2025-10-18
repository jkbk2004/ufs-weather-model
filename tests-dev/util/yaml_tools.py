# tests-dev/util/yaml_tools.py

import os
import yaml
import subprocess
import re
from pathlib import Path
from collections import defaultdict

class InlineDict(dict):
    pass

def inline_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)

yaml.add_representer(InlineDict, inline_dict_representer)

def get_pathrt():
    return os.getcwd()

def get_resource_info(test_name, machine, pathrt, compiler):
    wrapper = os.path.join(pathrt, "extract_resources.sh")
    env = os.environ.copy()
    env["PATHRT"] = pathrt
    env["RT_COMPILER"] = compiler
    cmd = [wrapper, test_name, machine]
    try:
        output = subprocess.check_output(cmd, env=env, text=True)
        info = {}
        for line in output.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().replace("__", "_").strip("_")
                info[key] = int(value.strip())
        return InlineDict(info)
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Resource extraction failed for {test_name} on {machine}: {e}")
        return InlineDict()

def inject_resources_into_yaml(yaml_path, platforms):
    pathrt = get_pathrt()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    for variant_key, block in data.items():
        compiler = block.get("build", {}).get("compiler", "intel")
        tests = block.get("tests", [])
        for test_entry in tests:
            for test_name, test_config in test_entry.items():
                resources = {}
                for platform in platforms:
                    info = get_resource_info(test_name, platform, pathrt, compiler)
                    if info:
                        resources[platform] = info
                test_config["resources"] = resources

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)

def normalize_keys(data):
    cleaned = {}
    for k, v in data.items():
        new_k = k.replace("default", "")
        new_k = re.sub(r"_+", "_", new_k).strip("_")
        if new_k != k:
            print(f"[INFO] Renamed key: {k} → {new_k}")
        cleaned[new_k] = v
    return cleaned

def clean_yaml_file(yaml_path):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    cleaned = normalize_keys(data)
    with open(yaml_path, "w") as f:
        yaml.dump(cleaned, f, sort_keys=False, default_flow_style=False)

def cleanup_all_yaml_keys():
    base_dir = Path("tests-yamls/configs/by_app")
    for file in base_dir.glob("*.yaml"):
        print(f"[CLEANUP] Processing {file.name}")
        clean_yaml_file(file)
