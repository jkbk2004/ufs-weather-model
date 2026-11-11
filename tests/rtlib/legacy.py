"""Line-for-line port of rt.sh's selection logic, quirks included.

This exists so the new code can be checked against today's behaviour on
every machine without submitting anything. It ports:

  * update_rtconf()   - the -n / -b rewrite of rt.conf into rt_temp.conf
  * the main `while read -r line` loop over the conf file

and produces the same Plan objects as rtlib.plan. It is a reference, not
an API: once rt.sh calls rtlib for selection this module can be deleted.
"""

import os
import re
from typing import List, Optional, Sequence

from .plan import CompileTask, Plan, RunTask, Task


class LegacyExit(Exception):
    """rt.sh would have exited here (die / exit 1)."""


def _cut(line: str, n: int) -> str:
    """`cut -d'|' -fN`: a line with no delimiter is printed whole."""
    if "|" not in line:
        return line
    parts = line.split("|")
    return parts[n - 1] if len(parts) >= n else ""


def _trim(s: str) -> str:
    """sed -e 's/^ *//' -e 's/ *$//'  (spaces only, not tabs)."""
    return s.strip(" ")


def _match(machines: str, machine_id: str) -> bool:
    """[[ ${MACHINES} =~ ${MACHINE_ID} ]]"""
    return re.search(machine_id, machines) is not None


def _grep_w(pattern: str, line: str) -> bool:
    """grep -w PATTERN (test names are plain words, '.' stays a wildcard)."""
    return re.search(r"(?<![A-Za-z0-9_])" + pattern + r"(?![A-Za-z0-9_])", line) is not None


def _read_lines(path: str) -> List[str]:
    """`while read -r line || [[ -n $line ]]` with the leading-space strip."""
    with open(path, encoding="utf-8") as f:
        return [raw.rstrip("\n").lstrip() for raw in f]


def update_rtconf(
    conf_lines: List[str], rtconf_path: str, machine_id: str, test_with_compile: Sequence[str]
) -> List[str]:
    """Port of update_rtconf(): returns the lines rt.sh writes to rt_temp.conf.

    rtconf_path is grepped for dependencies; like rt.sh this is always
    ${PATHRT}/rt.conf even when -l selects another conf file.
    """
    with open(rtconf_path, encoding="utf-8") as f:
        rtconf_raw = [l.rstrip("\n") for l in f]

    twc = list(test_with_compile)
    temp: List[str] = []
    compile_line = ""
    compile_line_used = False
    rt_compiler_in = ""

    for line in conf_lines:
        if not line or line.startswith("#"):
            continue

        # rt.sh uses `=~ COMPILE` / `=~ RUN`: substring tests, both may fire.
        if "COMPILE" in line:
            machines = _trim(_cut(line, 5))
            rt_compiler_in = _trim(_cut(line, 3))
            if machines == "":
                compile_line = line
                compile_line_used = False
            elif machines.startswith("-"):
                # [[ .. =~ .. ]] || compile_line=${line}; COMPILE_LINE_USED=false
                if not _match(machines, machine_id):
                    compile_line = line
                compile_line_used = False
            elif machines.startswith("+"):
                if _match(machines, machine_id):
                    compile_line = line
                compile_line_used = False

        if "RUN" in line:
            tmp_test = _trim(_cut(line, 2))
            machines = _trim(_cut(line, 3))
            if machines == "":
                to_run = True
            elif machines.startswith("-"):
                to_run = not _match(machines, machine_id)
            elif machines.startswith("+"):
                to_run = _match(machines, machine_id)
            else:
                to_run = False
            if not to_run or f"{tmp_test} {rt_compiler_in}" not in twc:
                continue

            if not compile_line_used:
                temp.append("")
                temp.append(compile_line)
                compile_line_used = True

            dep_test = _trim(_cut(line, 5)) if _grep_w(tmp_test, line) else ""
            if dep_test and f"{dep_test} {rt_compiler_in}" not in twc:
                dep_lines = [l for l in rtconf_raw if _grep_w(dep_test, l)]
                dep_lines = [l for l in dep_lines if re.search(tmp_test, l) is None]
                dep_line = "\n".join(dep_lines).lstrip().replace("\n", "")
                fields = re.split("RUN|RUN", dep_line)
                f2 = fields[1] if len(fields) > 1 else ""
                f3 = fields[2] if len(fields) > 2 else ""
                if rt_compiler_in == "intel":
                    temp.append(f"RUN {f2}")
                elif rt_compiler_in == "gnu":
                    temp.append(f"RUN {f3}")
            temp.append(line)

    if not temp:
        raise LegacyExit(
            f"The tests listed/chosen do not exist or cannot be run on {machine_id}"
        )
    return temp


def main_loop(
    lines: List[str],
    pathrt: str,
    machine_id: str,
    create_baseline: bool = False,
    compile_only: bool = False,
    test_35d: bool = False,
) -> List[Task]:
    """Port of rt.sh's `while read -r line ... done < ${TESTS_FILE}` loop."""
    tasks: List[Task] = []
    compiles = set()
    compile_id: Optional[str] = None
    rt_compiler: Optional[str] = None

    def skip_for_machine(machines: str) -> bool:
        if machines == "":
            return False
        if machines.startswith("-"):
            return _match(machines, machine_id)
        if machines.startswith("+"):
            return not _match(machines, machine_id)
        raise LegacyExit(
            "MACHINES spec must be either an empty string or start with either '+' or '-'"
        )

    for line in lines:
        line = line.lstrip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("COMPILE"):
            name = _trim(_cut(line, 2))
            rt_compiler = _trim(_cut(line, 3))
            make_opt = _trim(_cut(line, 4))
            machines = _trim(_cut(line, 5))
            cb = _cut(line, 6)
            compile_id = f"{name}_{rt_compiler}"
            if compile_id in compiles:
                raise LegacyExit(
                    f"Error! Duplicated compilation {name} for compiler {rt_compiler}!"
                )
            compiles.add(compile_id)
            if create_baseline and "fv3" not in cb:
                continue
            if skip_for_machine(machines):
                continue
            tasks.append(CompileTask(compile_id, make_opt))

        elif line.startswith("RUN"):
            if compile_only:
                continue
            if compile_id is None:
                raise LegacyExit("RT_COMPILER: unbound variable")
            test_name = _trim(_cut(line, 2))
            machines = _trim(_cut(line, 3))
            cb = _cut(line, 4)
            dep_run = _trim(_cut(line, 5))
            date_35d = _trim(_cut(line, 6))
            if dep_run:
                dep_run = f"{dep_run}_{rt_compiler}"
            test_id = f"{test_name}_{rt_compiler}"
            if not os.path.exists(os.path.join(pathrt, "tests", test_name)):
                raise LegacyExit(f"run test file tests/{test_name} does not exist")
            if create_baseline and "baseline" not in cb:
                continue
            if skip_for_machine(machines):
                continue
            if test_35d and "35d" in test_name:
                test_name = f"{test_name}_{date_35d}"
            tasks.append(RunTask(test_name, test_id, compile_id, dep_run))
        else:
            raise LegacyExit(f"Unknown command {line}")
    return tasks


def legacy_plan(
    conf_path: str,
    pathrt: str,
    machine_id: str,
    create_baseline: bool = False,
    compile_only: bool = False,
    selected: Optional[Sequence[str]] = None,
) -> Plan:
    """What rt.sh would schedule. `selected` is the -n / -b list ('name compiler')."""
    lines = _read_lines(conf_path)
    tests_file = conf_path
    if selected is not None:
        lines = update_rtconf(lines, os.path.join(pathrt, "rt.conf"), machine_id, selected)
        tests_file = "rt_temp.conf"  # rt.sh checks 35d/weekly *after* this rename
    test_35d = "35d" in tests_file or "weekly" in tests_file
    tasks = main_loop(lines, pathrt, machine_id, create_baseline, compile_only, test_35d)
    return Plan(machine_id, tasks)
