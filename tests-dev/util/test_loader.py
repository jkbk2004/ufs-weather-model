from pathlib import Path
import yaml

class TestLoader:
    def __init__(self, manifest_path, yamls_dir, bl_date):
        self.manifest_path = manifest_path
        self.yamls_dir = yamls_dir
        self.bl_date = bl_date
        self.tests = []
        self.selected_apps = []

    def load_manifest(self):
        with open(self.manifest_path) as f:
            manifest = yaml.safe_load(f)
        self.selected_apps = manifest.get("apps", [])

    def attach_yaml_configs(self):
        for yaml_file in Path(self.yamls_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                app_yaml = yaml.safe_load(f)

            for build_id, block in app_yaml.items():
                app_prefix = build_id.split("_")[0]
                if app_prefix not in self.selected_apps:
                    continue
                self._append_build_and_tests(build_id, block)

    def load_user_yaml(self, yaml_path):
        with open(yaml_path) as f:
            user_yaml = yaml.safe_load(f)

        for build_id, block in user_yaml.items():
            self._append_build_and_tests(build_id, block)

    def load_from_test_list(self, test_list_path):
        test_lookup = self._build_test_lookup()

        with open(test_list_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 2:
                    continue
                test_id, compiler_override = parts
                if test_id in test_lookup:
                    test = test_lookup[test_id]
                    test["compiler"] = compiler_override
                    self.tests.append(test)

    def load_single_test(self, test_id, compiler_override):
        test_lookup = self._build_test_lookup()
        if test_id in test_lookup:
            test = test_lookup[test_id]
            test["compiler"] = compiler_override
            self.tests.append(test)
        else:
            raise ValueError(f"[ERROR] Test case '{test_id}' not found in {self.yamls_dir}")

    def _build_test_lookup(self):
        test_lookup = {}
        for yaml_file in Path(self.yamls_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                app_yaml = yaml.safe_load(f)
            for build_id, block in app_yaml.items():
                for test_entry in block.get("tests", []):
                    for test_id, test_meta in test_entry.items():
                        test_lookup[test_id] = {
                            "id": test_id,
                            "compiler": block.get("build", {}).get("compiler", "intel"),
                            "parent": build_id,
                            "dependency": test_meta.get("dependency"),
                            "resources": test_meta.get("resources", {}),
                            "turnoff": test_meta.get("turnoff", []),
                            "type": "run"
                        }
        return test_lookup

    def _append_build_and_tests(self, build_id, block):
        build_info = block.get("build", {})
        compiler = build_info.get("compiler", "intel")
        option = build_info.get("option", "")
        turnoff = build_info.get("turnoff", [])

        self.tests.append({
            "id": build_id,
            "compiler": compiler,
            "option": option,
            "turnoff": turnoff,
            "type": "compile"
        })

        for test_entry in block.get("tests", []):
            for test_id, test_meta in test_entry.items():
                self.tests.append({
                    "id": test_id,
                    "compiler": compiler,
                    "parent": build_id,
                    "dependency": test_meta.get("dependency"),
                    "resources": test_meta.get("resources", {}),
                    "turnoff": test_meta.get("turnoff", []),
                    "type": "run"
                })

    def get_tests(self):
        return self.tests
