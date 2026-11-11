"""Command line: python3 -m rtlib <command> ...

  validate      static checks on a conf file (CI-friendly exit status)
  plan          print the compile/run tasks rt.sh would schedule on a machine
  diff-legacy   compare rtlib's plan with the line-for-line rt.sh port
"""

import argparse
import difflib
import os
import sys
from typing import List, Optional

from . import legacy, plan as planmod, rtconf
from .machines import KNOWN_MACHINES
from .validate import validate

PATHRT_DEFAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _conf_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-l", "--conf", default="rt.conf",
                   help="conf file, relative to --pathrt unless absolute (default rt.conf)")
    p.add_argument("--pathrt", default=PATHRT_DEFAULT,
                   help="the tests/ directory (default: parent of rtlib)")


def _sel_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-m", "--machine", required=True, choices=KNOWN_MACHINES)
    p.add_argument("-c", dest="create_baseline", action="store_true", help="as rt.sh -c")
    p.add_argument("-o", dest="compile_only", action="store_true", help="as rt.sh -o")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-n", dest="single", metavar='"TEST COMPILER"', help="as rt.sh -n")
    g.add_argument("-b", dest="bl_file", metavar="FILE", help="as rt.sh -b")


def _conf_path(a) -> str:
    return a.conf if os.path.isabs(a.conf) else os.path.join(a.pathrt, a.conf)


def _selected_lines(a) -> Optional[List[str]]:
    if a.single:
        return [a.single]
    if a.bl_file:
        with open(a.bl_file, encoding="utf-8") as f:
            return [l.rstrip("\n") for l in f]
    return None


def _options(a) -> planmod.Options:
    sel = _selected_lines(a)
    conf = _conf_path(a)
    return planmod.Options(
        machine=a.machine,
        create_baseline=a.create_baseline,
        compile_only=a.compile_only,
        selected=planmod.parse_selection(sel) if sel is not None else None,
        # same test rt.sh applies to ${TESTS_FILE}; -n/-b rename it to rt_temp.conf
        weekly_35d=sel is None and ("35d" in conf or "weekly" in conf),
    )


def cmd_validate(a) -> int:
    suite = rtconf.load(_conf_path(a))
    findings = validate(suite, a.pathrt)
    for f in findings:
        if f.level == "error" or not a.quiet:
            print(f)
    n_err = sum(f.level == "error" for f in findings)
    n_warn = len(findings) - n_err
    n_tests = sum(len(b.tests) for b in suite.builds)
    print(f"{_conf_path(a)}: {len(suite.builds)} builds, {n_tests} tests, "
          f"{n_err} errors, {n_warn} warnings", file=sys.stderr)
    return 1 if n_err or (a.strict and n_warn) else 0


def cmd_plan(a) -> int:
    if a.legacy:
        p = legacy.legacy_plan(_conf_path(a), a.pathrt, a.machine, a.create_baseline,
                               a.compile_only, _selected_lines(a))
    else:
        p = planmod.make_plan(rtconf.load(_conf_path(a)), _options(a))
    for note in p.notes:
        print(f"note: {note}", file=sys.stderr)
    sys.stdout.write(p.to_json() + "\n" if a.json else p.to_text())
    return 0


def _diff_each_test(a, machines) -> int:
    """Run the -n comparison for every test/compiler pair in the conf file."""
    conf = _conf_path(a)
    suite = rtconf.load(conf)
    pairs = sorted({(t.name, b.compiler) for b, t in suite.iter_tests()})
    n_same = n_diff = 0
    for m in machines:
        differ = []
        for name, comp in pairs:
            sel = [f"{name} {comp}"]
            try:
                old = legacy.legacy_plan(conf, a.pathrt, m, a.create_baseline,
                                         a.compile_only, sel).to_text()
            except legacy.LegacyExit as e:
                old = f"EXIT {e}\n"
            opts = planmod.Options(m, a.create_baseline, a.compile_only,
                                   planmod.parse_selection(sel))
            try:
                new = planmod.make_plan(suite, opts).to_text()
            except planmod.SelectionError as e:
                new = f"EXIT {e}\n"
            if old == new or (old.startswith("EXIT") and new.startswith("EXIT")):
                n_same += 1
            else:
                n_diff += 1
                differ.append(f"{name} {comp}")
        print(f"{m}: {len(pairs) - len(differ)}/{len(pairs)} identical"
              + (f"; differ: {', '.join(differ)}" if differ else ""))
    print(f"total: {n_same} identical, {n_diff} differ "
          "(inspect one with: diff-legacy -m MACHINE -n \"TEST COMPILER\")")
    return 1 if n_diff else 0


def cmd_diff_legacy(a) -> int:
    machines = [a.machine] if a.machine else list(KNOWN_MACHINES)
    if a.each_test:
        return _diff_each_test(a, machines)
    rc = 0
    for m in machines:
        a.machine = m
        try:
            old = legacy.legacy_plan(_conf_path(a), a.pathrt, m, a.create_baseline,
                                     a.compile_only, _selected_lines(a)).to_text()
        except legacy.LegacyExit as e:
            old = f"EXIT {e}\n"
        try:
            new = planmod.make_plan(rtconf.load(_conf_path(a)), _options(a)).to_text()
        except planmod.SelectionError as e:
            new = f"EXIT {e}\n"
        if old == new or (old.startswith("EXIT") and new.startswith("EXIT")):
            print(f"{m}: identical ({old.count(chr(10))} tasks)")
            continue
        rc = 1
        print(f"{m}: DIFFERS")
        sys.stdout.writelines(difflib.unified_diff(
            old.splitlines(True), new.splitlines(True), f"rt.sh/{m}", f"rtlib/{m}", n=1))
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m rtlib", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="static checks on a conf file")
    _conf_args(p)
    p.add_argument("--strict", action="store_true", help="fail on warnings too")
    p.add_argument("-q", "--quiet", action="store_true", help="print errors only")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("plan", help="print the tasks for one machine")
    _conf_args(p)
    _sel_args(p)
    p.add_argument("--legacy", action="store_true", help="use the line-for-line rt.sh port")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("diff-legacy", help="compare rtlib with rt.sh behaviour")
    _conf_args(p)
    _sel_args(p)
    p.add_argument("--each-test", action="store_true",
                   help="compare -n for every test in the conf file")
    p.set_defaults(func=cmd_diff_legacy)
    for action in p._actions:  # machine is optional here: default all
        if action.dest == "machine":
            action.required = False

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except rtconf.ConfError as e:
        print(e, file=sys.stderr)
        return 2
    except (planmod.SelectionError, legacy.LegacyExit) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
