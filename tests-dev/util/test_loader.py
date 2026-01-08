from pathlib import Path
import yaml


class TestLoader:
    """
    Loads test definitions from:
      - manifest (apps list)
      - by_app YAMLs
      - optional user YAML
      - optional test_list
      - optional single test

    Produces normalized test entries:
      {
        "id": str,
        "type": "compile" | "run",
        "compiler": str,
        "parent": str | None,
        "dependency": str | None,
        "nodes": str,
        "walltime": str,
        "turnoff": list,
        "option": str (compile only)
      }
    """

    def __init__(self, manifest_path, yamls_dir, bl_date, machine_config):
        self.manifest_path = manifest_path
        self.yamls_dir = yamls_dir
        self.bl_date = bl_date
        self.machine_config = machine_config

        self.platform = machine_config["PLATFORM"]  # e.g., "orion"
        self.tests = []
        self.selected_apps = []

    # --------------------------------------------------------------------------
    # Manifest
    # --------------------------------------------------------------------------
    def load_manifest(self):
        with open(self.manifest_path) as f:
            manifest = yaml.safe_load(f)
        self.selected_apps = manifest.get("apps", [])

    # --------------------------------------------------------------------------
    # Extract resources for run tasks
    # --------------------------------------------------------------------------
    def _extract_run_resources(self, test_meta):
        """Extract nodes and walltime for run tasks."""
        res = test_meta.get("resources", {}).get(self.platform, {})

        if not res:
            return {"nodes": "1:ppn=1", "walltime": "00:10:00"}

        nodes = f"{res.get('nodes', '1')}:ppn={res.get('ppn', '1')}"
        walltime = res.get("wlclk", "00:10:00")

        return {"nodes": nodes, "walltime": walltime}

    # --------------------------------------------------------------------------
    # Extract resources for compile tasks
    # --------------------------------------------------------------------------
    def _extract_compile_resources(self):
        """Extract nodes and walltime for compile tasks from machine config."""
        ppn = self.machine_config.get("BUILD_CORES", "8")
        walltime = self.machine_config.get("BUILD_WALLTIME", "00:30:00")

        nodes = f"1:ppn={ppn}"

        return {"nodes": nodes, "walltime": walltime}

    # --------------------------------------------------------------------------
    # Attach YAML configs for selected apps
    # --------------------------------------------------------------------------
    def attach_yaml_configs(self):
        for yaml_file in Path(self.yamls_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                app_yaml = yaml.safe_load(f)

            for build_id, block in app_yaml.items():
                app_prefix = build_id.split("_")[0]
                if app_prefix not in self.selected_apps:
                    continue
                self._append_build_and_tests(build_id, block)

    # --------------------------------------------------------------------------
    # User YAML override
    # --------------------------------------------------------------------------
    def load_user_yaml(self, yaml_path):
        with open(yaml_path) as f:
            user_yaml = yaml.safe_load(f)
        for build_id, block in user_yaml.items():
            self._append_build_and_tests(build_id, block)

    # --------------------------------------------------------------------------
    # Test list
    # --------------------------------------------------------------------------
    def load_from_test_list(self, test_list_path):
        test_lookup = self._build_test_lookup()
        loaded_ids = set()

        with open(test_list_path) as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue

                test_id = parts[0]

                if test_id in test_lookup:
                    test = test_lookup[test_id]
                    self.tests.append(test)
                    loaded_ids.add(test_id)

                    parent_id = test.get("parent")
                    if parent_id and parent_id not in loaded_ids:
                        self._load_compile_task(parent_id)
                        loaded_ids.add(parent_id)

    # --------------------------------------------------------------------------
    # Single test
    # --------------------------------------------------------------------------
    def load_single_test(self, test_id, strict=False):
        test_lookup = self._build_test_lookup()
        if test_id not in test_lookup:
            raise ValueError(f"[ERROR] Test case '{test_id}' not found in {self.yamls_dir}")

        test = test_lookup[test_id]
        self.tests.append(test)

        if strict and test["type"] == "run":
            parent_id = test.get("parent")
            self._load_compile_task(parent_id)

    # --------------------------------------------------------------------------
    # Load compile task by build_id
    # --------------------------------------------------------------------------
    def _load_compile_task(self, build_id):
        compile_id = f"compile_{build_id}"

        for yaml_file in Path(self.yamls_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                app_yaml = yaml.safe_load(f)

            if build_id in app_yaml:
                block = app_yaml[build_id]
                build_info = block.get("build", {})

                res = self._extract_compile_resources()

                self.tests.append({
                    "id": compile_id,
                    "type": "compile",
                    "compiler": build_info.get("compiler", "intel"),
                    "option": build_info.get("option", ""),
                    "turnoff": build_info.get("turnoff", []),
                    "parent": None,
                    "dependency": None,
                    "nodes": res["nodes"],
                    "walltime": res["walltime"],
                })
                return

        raise ValueError(f"[ERROR] Compile block '{build_id}' not found in {self.yamls_dir}")

    # --------------------------------------------------------------------------
    # Build lookup table for run tests
    # --------------------------------------------------------------------------
    def _build_test_lookup(self):
        test_lookup = {}

        for yaml_file in Path(self.yamls_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                app_yaml = yaml.safe_load(f)

            for build_id, block in app_yaml.items():
                compiler = block.get("build", {}).get("compiler", "intel")
                compile_id = f"compile_{build_id}"

                for test_entry in block.get("tests", []):
                    for test_id, test_meta in test_entry.items():

                        res = self._extract_run_resources(test_meta)

                        test_lookup[test_id] = {
                            "id": test_id,
                            "type": "run",
                            "compiler": compiler,
                            "parent": compile_id,
                            "dependency": test_meta.get("dependency") or "",
                            "nodes": res["nodes"],
                            "walltime": res["walltime"],
                            "turnoff": test_meta.get("turnoff", []),
                            "option": "",
                        }

        return test_lookup

    # --------------------------------------------------------------------------
    # Append build + tests from a block
    # --------------------------------------------------------------------------
    def _append_build_and_tests(self, build_id, block):
        build_info = block.get("build", {})
        compiler = build_info.get("compiler", "intel")
        compile_id = f"compile_{build_id}"

        # Compile task
        cres = self._extract_compile_resources()

        self.tests.append({
            "id": compile_id,
            "type": "compile",
            "compiler": compiler,
            "option": build_info.get("option", ""),
            "turnoff": build_info.get("turnoff", []),
            "parent": None,
            "dependency": None,
            "nodes": cres["nodes"],
            "walltime": cres["walltime"],
        })

        # Run tasks
        for test_entry in block.get("tests", []):
            for test_id, test_meta in test_entry.items():

                rres = self._extract_run_resources(test_meta)

                self.tests.append({
                    "id": test_id,
                    "type": "run",
                    "compiler": compiler,
                    "parent": compile_id,
                    "dependency": test_meta.get("dependency") or "",
                    "nodes": rres["nodes"],
                    "walltime": rres["walltime"],
                    "turnoff": test_meta.get("turnoff", []),
                    "option": "",
                })

    # --------------------------------------------------------------------------
    # Return all tests
    # --------------------------------------------------------------------------
    def get_tests(self):
        return self.tests
