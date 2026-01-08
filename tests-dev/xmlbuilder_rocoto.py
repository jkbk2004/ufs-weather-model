#!/usr/bin/env python3

from lxml import etree


class RocotoXMLBuilder:
    """
    Build Rocoto XML from normalized test entries.
    Test entries come from TestLoader and have fields:
      id, type, compiler, parent, dependency, resources, option
    """

    def __init__(self, ctx):
        self.ctx = ctx
        self.root = etree.Element("workflow", attrib={
            "cycledef": "197001010000 197001010000 01:00:00",
            "scheduler": "slurm"
        })

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    def build(self):
        for test in self.ctx.tests:
            if test["type"] == "compile":
                self._add_compile_task(test)
            else:
                self._add_run_task(test)
        return self.root

    # ----------------------------------------------------------------------
    # Compile task
    # ----------------------------------------------------------------------
    def _add_compile_task(self, test):
        """
        Compile task name = test["id"]
        Example: compile_lnd-lm4_datm_cdeps_lm4_intel
        """
        task_name = test["id"]

        task = etree.SubElement(self.root, "task", attrib={
            "name": task_name,
            "maxtries": "3"
        })

        command = f"{self.ctx.pathrt}/run_compile.sh {self.ctx.pathrt} {self.ctx.rundir_root} {test['option']} {task_name.replace('compile_', '')}"
        etree.SubElement(task, "command").text = command

        # No dependencies for compile tasks
        etree.SubElement(task, "jobname").text = task_name

    # ----------------------------------------------------------------------
    # Run task
    # ----------------------------------------------------------------------
    def _add_run_task(self, test):
        """
        Run task name = test["id"]
        Parent = compile_<build_id>
        """
        task_name = test["id"]
        parent = test["parent"]  # already compile_<build_id>

        task = etree.SubElement(self.root, "task", attrib={
            "name": task_name,
            "maxtries": "3"
        })

        # Dependencies
        deps = etree.SubElement(task, "dependency")
        etree.SubElement(deps, "taskdep", attrib={"task": parent})

        # Optional extra dependency
        if test["dependency"]:
            etree.SubElement(deps, "taskdep", attrib={"task": test["dependency"]})

        # Command
        command = f"{self.ctx.pathrt}/run_test.sh {self.ctx.pathrt} {self.ctx.rundir_root} {task_name}"
        etree.SubElement(task, "command").text = command

        etree.SubElement(task, "jobname").text = task_name
