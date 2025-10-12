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

                build_info = block.get("build", {})
                compiler = build_info.get("compiler", "intel")
                option = build_info.get("option", "")
                turnoff = build_info.get("turnoff", [])

                self.tests.append({
                    "id": build_id,
                    "compiler": compiler,
                    "option": option,
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
                            "type": "run"
                        })

    def get_tests(self):
        return self.tests
