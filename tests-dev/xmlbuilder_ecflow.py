import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

class XMLBuilderEcflow:
    def __init__(self, test_loader, manifest, platform, suite_name="ufs_suite"):
        self.test_loader = test_loader
        self.manifest = manifest
        self.platform = platform
        self.suite_name = suite_name
        self.task_groups = []

    def build(self):
        for app_name, test_cases in self.test_loader.group_by_app().items():
            task_group = {
                "app": app_name,
                "tasks": []
            }
            for case in test_cases:
                task = {
                    "name": case.name,
                    "command": case.get_run_command(),  # assumes method exists
                    "variables": case.get_env_vars(),   # assumes method exists
                    "depends": case.get_dependencies()  # assumes method exists
                }
                task_group["tasks"].append(task)
            self.task_groups.append(task_group)

    def write_def(self, output_path):
        env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "templates"),
            trim_blocks=True,
            lstrip_blocks=True
        )
        template = env.get_template("ecflow_workflow.j2")
        rendered = template.render(
            suite_name=self.suite_name,
            task_groups=self.task_groups
        )
        with open(output_path, "w") as f:
            f.write(rendered)
