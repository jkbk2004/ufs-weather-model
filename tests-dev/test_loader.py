import yaml
from pathlib import Path

class TestLoader:
    def __init__(self, machine):
        self.machine = machine

    def from_manifest(self, manifest_path, yamls_dir):
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        tests = []
        for app in manifest.get("apps", []):
            app_yaml = Path(yamls_dir) / f"{app}.yaml"
            if not app_yaml.is_file():
                print(f"⚠️ Skipping missing app YAML: {app_yaml}")
                continue
            with open(app_yaml) as f:
                block = yaml.safe_load(f)
            for group_name, group in block.items():
                compiler = group.get("build", {}).get("compiler", "unknown").lower()
                turnoff = group.get("build", {}).get("turnoff", [])
                for test_entry in group.get("tests", []):
                    for test_id, meta in test_entry.items():
                        if self.machine in turnoff or self.machine in meta.get("turnoff", []):
                            continue
                        tests.append({
                            "id": test_id,
                            "compiler": compiler,
                            "group": group_name,
                            "dependency": meta.get("dependency"),
                            "baseline": meta.get("baseline", False),
                            "project": meta.get("project", [])
                        })
        return tests

    def from_list_yaml(self, list_yaml_path):
        with open(list_yaml_path) as f:
            config = yaml.safe_load(f)
        tests = []
        for group_name, group in config.items():
            compiler = group.get("build", {}).get("compiler", "unknown").lower()
            turnoff = group.get("turnoff", [])
            for test_entry in group.get("tests", []):
                for test_id, meta in test_entry.items():
                    if self.machine in turnoff or self.machine in meta.get("turnoff", []):
                        continue
                    tests.append({
                        "id": test_id,
                        "compiler": compiler,
                        "group": group_name,
                        "dependency": meta.get("dependency"),
                        "baseline": meta.get("baseline", False),
                        "project": meta.get("project", [])
                    })
        return tests

    def from_name(self, name_str):
        parts = name_str.strip().split()
        if len(parts) != 2:
            raise ValueError("Format must be: 'test_id compiler'")
        return [{
            "id": parts[0],
            "compiler": parts[1],
            "group": "manual",
            "baseline": False,
            "project": []
        }]

    def from_changes_file(self, changes_path):
        tests = []
        with open(changes_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    test_id, compiler = line.split(":")
                else:
                    test_id, compiler = line, "intel"  # default
                tests.append({
                    "id": test_id.strip(),
                    "compiler": compiler.strip(),
                    "group": "changes",
                    "baseline": False,
                    "project": []
                })
        return tests
