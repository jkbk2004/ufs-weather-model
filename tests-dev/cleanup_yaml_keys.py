import os
import yaml
from pathlib import Path
import re

def normalize_keys(data):
    """Remove 'default' from keys and clean up underscores."""
    cleaned = {}
    for k, v in data.items():
        new_k = k.replace("default", "")
        new_k = re.sub(r"_+", "_", new_k)  # collapse multiple underscores
        new_k = new_k.strip("_")           # remove leading/trailing underscores
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

if __name__ == "__main__":
    cleanup_all_yaml_keys()
