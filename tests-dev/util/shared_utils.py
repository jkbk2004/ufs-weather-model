import yaml
import re
from pathlib import Path
import subprocess

def resolve_baseline_dir(machine_config_path, date_conf_path):
    """
    Constructs full baseline path from:
    - BASELINE_PATH in machine_config YAML
    - Hardcoded subpath: /NEMSfv3gfs/develop-
    - BL_DATE from bl_date.conf
    """
    try:
        with open(machine_config_path) as f:
            config = yaml.safe_load(f)
        base_prefix = config.get("BASELINE_PATH", "").strip()
    except Exception as e:
        print(f"[ERROR] Failed to read {machine_config_path}: {e}")
        base_prefix = ""

    subpath = "/NEMSfv3gfs/develop-"

    try:
        lines = Path(date_conf_path).read_text().splitlines()
        date_line = next((line for line in lines if "BL_DATE" in line), "")
        match = re.search(r"BL_DATE=(\d+)", date_line)
        bl_date = match.group(1) if match else ""
    except Exception as e:
        print(f"[ERROR] Failed to read {date_conf_path}: {e}")
        bl_date = ""

    if base_prefix and bl_date:
        return f"{base_prefix}{subpath}{bl_date}"
    else:
        return "UNKNOWN"

def get_git_hash(repo_root):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root).decode().strip()
    except Exception as e:
        print(f"[ERROR] Failed to get top-level Git hash: {e}")
        return "unknown"

def get_git_submodule_hashes(repo_root):
    try:
        output = subprocess.check_output(
            ["git", "submodule", "status", "--recursive"],
            cwd=repo_root
        ).decode().splitlines()
    except Exception as e:
        print(f"[ERROR] Failed to get submodule status: {e}")
        return []

    hashes = []
    for line in output:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        hash_part = parts[0].lstrip("-")
        path_part = parts[1]
        tag_part = line[line.find("("):] if "(" in line else ""
        hashes.append(f"{hash_part} {path_part} {tag_part}".strip())
    return hashes

def extract_bl_date(filepath="bl_date.conf"):
    """Extracts the BL_DATE value from a shell-style config file."""
    with open(filepath) as f:
        for line in f:
            if line.startswith("export BL_DATE="):
                return line.split("=")[1].strip()
    raise ValueError("BL_DATE not found in bl_date.conf")


def enrich_test_context(tests, machine_config, machine):
    """Adds job metadata to each test based on type and machine-specific resources."""
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

            # Default resource values
            ppn = 40
            nodes = 8
            wlclk = 30

            # Override with machine-specific resources if available
            resources = test.get("resources", {})
            if machine in resources:
                r = resources[machine]
                ppn = r.get("ppn", ppn)
                nodes = r.get("nodes", nodes)
                wlclk = r.get("wlclk", wlclk)

            test["nodes"] = f"{nodes}:ppn={ppn}"
            test["walltime"] = f"00:{wlclk:02}:00"

        # Common metadata
        test["account"] = machine_config.get("ACCOUNT", "epic")
        test["queue"] = machine_config.get("QUEUE", "batch")
        test["partition"] = machine
        test["join"] = f"&RUNDIR_ROOT;/{test['name']}.log"
