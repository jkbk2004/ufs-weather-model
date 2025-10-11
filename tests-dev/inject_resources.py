import os
import yaml
import subprocess
from pathlib import Path

# Custom class to force inline formatting for each machine's resource block
class InlineDict(dict):
    pass

# Custom representer to serialize InlineDict as a single-line dictionary
def inline_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)

yaml.add_representer(InlineDict, inline_dict_representer)

def get_pathrt():
    return os.getcwd()

def get_resource_info(test_name, machine, pathrt):
    wrapper = os.path.join(pathrt, "extract_resources.sh")
    env = os.environ.copy()
    env["PATHRT"] = pathrt
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

    # Inject only the resources block, preserving all other content
    for variant_key, block in data.items():
        tests = block.get("tests", [])
        for test_entry in tests:
            for test_name, test_config in test_entry.items():
                resources = {}
                for platform in platforms:
                    info = get_resource_info(test_name, platform, pathrt)
                    if info:
                        resources[platform] = info
                test_config["resources"] = resources

    # Dump YAML with block style globally; InlineDict forces single-line formatting for resources
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)

def main():
    platforms = ["orion", "hera", "ursa", "derecho", "hercules", "gaeac6"]
    yaml_dir = Path("tests-yamls/configs/by_app")
    for fname in yaml_dir.glob("*.yaml"):
        print(f"[INJECT] Processing {fname.name}")
        inject_resources_into_yaml(fname, platforms)

if __name__ == "__main__":
    main()
