import yaml
from pathlib import Path

class TestLoader:
    def __init__(self, manifest_path, yamls_dir=None, bl_date=None):
        self.manifest_path = Path(manifest_path)
        self.yamls_dir = Path(yamls_dir) if yamls_dir else None
        self.bl_date = bl_date
        self.tests = []

    def load_manifest(self):
        with open(self.manifest_path) as f:
            manifest = yaml.safe_load(f)

        apps = manifest.get("apps", [])
        if isinstance(apps, dict):
            for app_id, config in apps.items():
                if isinstance(config, dict) and config.get("enabled", True):
                    config["id"] = app_id
                    self.tests.append(config)
        elif isinstance(apps, list):
            self.tests = [{"id": app, "enabled": True} for app in apps]
        else:
            raise ValueError("Invalid 'apps' format in manifest")

    def inject_baseline_tag(self):
        if self.bl_date:
            for test in self.tests:
                test["BL_DATE"] = self.bl_date

    def attach_yaml_configs(self):
        if not self.yamls_dir:
            return
        for test in self.tests:
            yaml_path = self.yamls_dir / f"{test['id']}.yaml"
            if yaml_path.exists():
                with open(yaml_path) as f:
                    config = yaml.safe_load(f)
                test.update(config)
            else:
                print(f"⚠️ Missing config for {test['id']}: {yaml_path}")

    def get_tests(self):
        return self.tests
