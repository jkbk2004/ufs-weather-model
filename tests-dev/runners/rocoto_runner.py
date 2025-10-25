import xml.etree.ElementTree as ET
import subprocess
from collections import defaultdict

class RocotoRunner:
    def __init__(self, xml_path):
        self.xml_path = xml_path
        self.tasks = {}
        self.dependency_graph = defaultdict(list)

    def parse_xml(self):
        tree = ET.parse(self.xml_path)
        root = tree.getroot()

        for task in root.findall("task"):
            name = task.get("name")
            command = task.find("command").text.strip()
            depends = [d.text for d in task.findall("depend")]
            self.tasks[name] = {
                "command": command,
                "depends": depends
            }
            for dep in depends:
                self.dependency_graph[dep].append(name)

    def resolve_order(self):
        resolved = []
        visited = set()

        def visit(task):
            if task in visited:
                return
            for dep in self.tasks[task]["depends"]:
                visit(dep)
            visited.add(task)
            resolved.append(task)

        for task in self.tasks:
            visit(task)

        return resolved

    def run_sequentially(self):
        self.parse_xml()
        execution_order = self.resolve_order()

        for task_name in execution_order:
            cmd = self.tasks[task_name]["command"]
            print(f"🔧 Running {task_name}: {cmd}")
            result = subprocess.run(cmd, shell=True)
            if result.returncode != 0:
                print(f"❌ {task_name} failed.")
                break
            print(f"✅ {task_name} completed.")
