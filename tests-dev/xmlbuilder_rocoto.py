from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import os

class RocotoXMLBuilder:
    def __init__(self, machine, machine_config, pathrt, pathtro, log, rtpwd,
                 rundir_root, new_baseline, inputdata_entities,
                 project, tests, bl_date, dry_run=False,
                 output_path="rocoto.xml"):
        self.machine = machine
        self.machine_config = machine_config
        self.pathrt = pathrt
        self.pathtro = pathtro
        self.log = log
        self.rtpwd = rtpwd
        self.rundir_root = rundir_root
        self.new_baseline = new_baseline
        self.inputdata_entities = inputdata_entities
        self.project = project
        self.tests = tests
        self.bl_date = bl_date
        self.dry_run = dry_run
        self.output_path = Path(output_path)
        self.xml_content = ""
        self.user_literal = "{{USER}}" if dry_run else os.environ.get("USER", "{{USER}}")

    def generate(self):
        env = Environment(
            loader=FileSystemLoader("templates"),
            trim_blocks=True,
            lstrip_blocks=True
        )
        template = env.get_template("rocoto_workflow.j2")

        context = {
            "PATHRT": self.pathrt,
            "PATHTR": self.pathtro,
            "LOG": self.log,
            "RTPWD": self.rtpwd,
            "RUNDIR_ROOT": self.rundir_root,
            "NEW_BASELINE": self.new_baseline,
            "INPUTDATA_ENTITIES": self.inputdata_entities,
            "PROJECT": self.project,
            "TESTS": self.tests,
            "BL_DATE": self.bl_date,
            "USER": self.user_literal,
            "DRY_RUN": self.dry_run,
            "machine_config": self.machine_config
        }

        self.xml_content = template.render(context)

    def write(self, output_path=None):
        path = Path(output_path) if output_path else self.output_path
        path.write_text(self.xml_content)
        print(f"✅ Rocoto XML written to {path}")
