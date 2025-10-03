from pathlib import Path

class RocotoXMLBuilder:
    def __init__(self, machine, rt_yaml, baseline_yaml, project=None,
                 pathrt=None, rtpwd=None, inputdata_entities=None,
                 rundir_root=None, new_baseline=None):
        self.machine = machine
        self.rt_yaml = rt_yaml
        self.baseline_yaml = baseline_yaml
        self.project = project
        self.pathrt = pathrt or "/default/path"
        self.pathtro = str(Path(self.pathrt).parent)
        self.rtpwd = rtpwd or "/default/rtpwd"
        self.inputdata_entities = inputdata_entities or {}
        self.rundir_root = rundir_root or "/default/rundir"
        self.new_baseline = new_baseline or "/default/baseline"
        self.xml_content = ""

    def generate(self):
        scheduler = "lsf" if self.machine == "orion" else "slurm"
        entity_lines = f"""  <!ENTITY PATHRT         "{self.pathrt}">
  <!ENTITY LOG            "{self.pathrt}/logs/log_orion">
  <!ENTITY PATHTR         "{self.pathtro}">
  <!ENTITY RTPWD          "{self.rtpwd}">
"""
        for key, value in self.inputdata_entities.items():
            entity_lines += f'  <!ENTITY {key} "{value}">\n'

        entity_lines += f"""  <!ENTITY RUNDIR_ROOT    "{self.rundir_root}">
  <!ENTITY NEW_BASELINE   "{self.new_baseline}">
"""

        header = f"""<?xml version="1.0"?>
<!DOCTYPE workflow [
{entity_lines}]>
<workflow realtime="F" scheduler="{scheduler}">
  <cycledef group="forecast" start="20251001T00" end="20251001T00" interval="06:00"/>
"""

        tasks = ""
        for key, block in self.rt_yaml.items():
            build = block.get("build", {})
            compiler = build.get("compiler", "unknown").lower()
            tests = block.get("tests", [])
            for test_group in tests:
                for test_name in test_group:
                    label = f"{test_name}_{compiler}"
                    tasks += f"""
  <task name="build_{label}" cycle="forecast">
    <command>&PATHRT;/scripts/build.sh {label}</command>
    <jobname>build_{label}</jobname>
    <account>{self.project or "default"}</account>
  </task>

  <task name="run_{label}" cycle="forecast">
    <command>&PATHRT;/scripts/run.sh {label}</command>
    <jobname>run_{label}</jobname>
    <account>{self.project or "default"}</account>
    <dependency>
      <taskdep task="build_{label}"/>
    </dependency>
  </task>

  <task name="compare_{label}" cycle="forecast">
    <command>&PATHRT;/scripts/compare.sh {label}</command>
    <jobname>compare_{label}</jobname>
    <account>{self.project or "default"}</account>
    <dependency>
      <taskdep task="run_{label}"/>
    </dependency>
  </task>
"""

        self.xml_content = header + tasks + "</workflow>\n"

    def write(self, output_path):
        with open(output_path, "w") as f:
            f.write(self.xml_content)
        print(f"✅ Rocoto XML written to {output_path}")
