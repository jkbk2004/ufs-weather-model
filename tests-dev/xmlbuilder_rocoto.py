from pathlib import Path
from jinja2 import Environment, FileSystemLoader

class RocotoXMLBuilder:
    def __init__(self, machine, pathrt, pathtro, log, rtpwd,
                 rundir_root, new_baseline, inputdata_entities,
                 project, tests):
        self.machine = machine
        self.pathrt = pathrt
        self.pathtro = pathtro
        self.log = log
        self.rtpwd = rtpwd
        self.rundir_root = rundir_root
        self.new_baseline = new_baseline
        self.inputdata_entities = inputdata_entities
        self.project = project
        self.tests = tests
        self.xml_content = ""

    def generate(self):
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("rocoto_workflow.j2")

        context = {
            "PATHRT": self.pathrt,
            "PATHTR": self.pathtro,
            "LOG": self.log,
            "RTPWD": self.rtpwd,
            "RUNDIR_ROOT": self.rundir_root,
            "NEW_BASELINE": self.new_baseline,
            "scheduler": "slurm",
            "start": "20251001T00",
            "end": "20251001T00",
            "interval": "06:00",
            "account": self.project,
            "tests": self.tests,
            **self.inputdata_entities
        }

        self.xml_content = template.render(context)

    def write(self, output_path):
        with open(output_path, "w") as f:
            f.write(self.xml_content)
        print(f"✅ Rocoto XML written to {output_path}")
