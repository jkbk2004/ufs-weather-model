"""Unit tests for rtlib. Standard library only:

    cd tests && python3 -m unittest rtlib.test_rtlib -v
"""

import contextlib
import io
import os
import tempfile
import textwrap
import unittest

from rtlib import cli, legacy, plan, rtconf
from rtlib.machines import KNOWN_MACHINES
from rtlib.schema import MachineFilter
from rtlib.validate import validate

PATHRT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Sandbox:
    """A throwaway PATHRT with a conf file and empty test files."""

    def __init__(self, conf: str, tests=()):
        self.dir = tempfile.TemporaryDirectory()
        self.path = self.dir.name
        os.mkdir(os.path.join(self.path, "tests"))
        for t in tests:
            open(os.path.join(self.path, "tests", t), "w").close()
        self.conf = os.path.join(self.path, "rt.conf")
        with open(self.conf, "w") as f:
            f.write(textwrap.dedent(conf))

    def suite(self):
        return rtconf.load(self.conf)

    def close(self):
        self.dir.cleanup()


SMALL = """\
    # comment
    COMPILE | atm | intel | -DAPP=ATM | | fv3 |
    RUN | control          |              | baseline |
    RUN | restart          |              |          | control
    RUN | hera_only        | + hera       |          |

    COMPILE | cpl | intel | -DAPP=S2S | - noaacloud | fv3 |
    RUN | cpl_control      | - noaacloud  | baseline |
    RUN | cpl_restart      | - noaacloud  |          | cpl_control
    RUN | cpl_restart2     | - noaacloud  |          | cpl_restart

    COMPILE | atm | gnu | -DAPP=ATM | + hera | fv3 |
    RUN | control          | + hera       | baseline |
"""
SMALL_TESTS = ["control", "restart", "hera_only", "cpl_control", "cpl_restart", "cpl_restart2"]


def run_ids(p):
    return [r.test_id for r in p.runs]


class TestMachineFilter(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(MachineFilter.parse("").mode, "all")
        f = MachineFilter.parse("+ hera  orion")
        self.assertEqual((f.mode, f.machines), ("only", ("hera", "orion")))
        f = MachineFilter.parse("- wcoss2 acorn")
        self.assertEqual((f.mode, f.machines), ("exclude", ("wcoss2", "acorn")))
        with self.assertRaises(ValueError):
            MachineFilter.parse("hera")

    def test_exact_vs_legacy_substring(self):
        f = MachineFilter.parse("+ gaeac6")
        self.assertFalse(f.allows("gaea"))
        self.assertTrue(f.allows("gaea", legacy=True))  # rt.sh's =~ quirk
        self.assertTrue(f.allows("gaeac6"))
        self.assertFalse(MachineFilter.parse("- hera").allows("hera"))
        self.assertTrue(MachineFilter.parse("- hera").allows("orion"))


class TestRtconf(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox(SMALL, SMALL_TESTS)

    def tearDown(self):
        self.sb.close()

    def test_structure(self):
        s = self.sb.suite()
        self.assertEqual([b.id for b in s.builds], ["atm_intel", "cpl_intel", "atm_gnu"])
        atm = s.builds[0]
        self.assertEqual([t.name for t in atm.tests], ["control", "restart", "hera_only"])
        self.assertTrue(atm.tests[0].creates_baseline)
        self.assertEqual(atm.tests[1].depends, "control")
        self.assertEqual(atm.tests[1].source.line, 4)

    def test_errors_are_collected(self):
        bad = Sandbox("""\
            RUN | orphan | | |
            COMPILE | x | ifort | -DAPP=ATM | | fv3 |
            RUN | t | hera | |
            BUILD | nope |
        """)
        try:
            with self.assertRaises(rtconf.ConfError) as cm:
                bad.suite()
            msg = "\n".join(cm.exception.errors)
            self.assertIn(":1: RUN line before any COMPILE", msg)
            self.assertIn(":2: compiler 'ifort'", msg)
            self.assertIn(":3: machine spec must be empty or start with", msg)
            self.assertIn(":4: unknown command", msg)
        finally:
            bad.close()


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox(SMALL, SMALL_TESTS)
        self.suite = self.sb.suite()

    def tearDown(self):
        self.sb.close()

    def mk(self, machine, **kw):
        if "selected" in kw:
            kw["selected"] = plan.parse_selection(kw["selected"])
        return plan.make_plan(self.suite, plan.Options(machine, **kw))

    def test_full_run_on_hera(self):
        p = self.mk("hera")
        self.assertEqual([c.compile_id for c in p.compiles], ["atm_intel", "cpl_intel", "atm_gnu"])
        self.assertEqual(run_ids(p), ["control_intel", "restart_intel", "hera_only_intel",
                                      "cpl_control_intel", "cpl_restart_intel",
                                      "cpl_restart2_intel", "control_gnu"])
        self.assertEqual(p.runs[1].dep_run, "control_intel")

    def test_machine_filters(self):
        p = self.mk("noaacloud")
        self.assertEqual([c.compile_id for c in p.compiles], ["atm_intel"])
        self.assertEqual(run_ids(p), ["control_intel", "restart_intel"])

    def test_create_baseline(self):
        self.assertEqual(run_ids(self.mk("hera", create_baseline=True)),
                         ["control_intel", "cpl_control_intel", "control_gnu"])

    def test_compile_only(self):
        p = self.mk("orion", compile_only=True)
        self.assertEqual(p.runs, [])
        self.assertEqual(len(p.compiles), 2)

    def test_single_test_pulls_dependencies_transitively(self):
        p = self.mk("hera", selected=["cpl_restart2 intel"])
        self.assertEqual([c.compile_id for c in p.compiles], ["cpl_intel"])
        self.assertEqual(run_ids(p), ["cpl_control_intel", "cpl_restart_intel",
                                      "cpl_restart2_intel"])

    def test_selection_keeps_file_order_and_dedups(self):
        p = self.mk("hera", selected=["restart intel", "control intel", "control gnu"])
        self.assertEqual(run_ids(p), ["control_intel", "restart_intel", "control_gnu"])

    def test_b_list_skips_tests_not_on_this_machine(self):
        p = self.mk("orion", selected=["hera_only intel", "control intel"])
        self.assertEqual(run_ids(p), ["control_intel"])
        self.assertEqual(p.notes, ("skipping hera_only intel: not enabled on orion",))

    def test_selection_errors(self):
        with self.assertRaisesRegex(plan.SelectionError, "not defined"):
            self.mk("hera", selected=["controll intel"])  # typo
        with self.assertRaisesRegex(plan.SelectionError, "cannot be run on orion"):
            self.mk("orion", selected=["hera_only intel"])
        with self.assertRaisesRegex(plan.SelectionError, "creates a baseline"):
            self.mk("hera", create_baseline=True, selected=["hera_only intel"])
        with self.assertRaises(plan.SelectionError):
            plan.parse_selection(["control"])

    def test_text_and_json(self):
        p = self.mk("noaacloud")
        self.assertTrue(p.to_text().startswith("COMPILE atm_intel | -DAPP=ATM\nRUN control_intel"))
        self.assertIn('"kind": "run"', p.to_json())


class TestSkippedBuild(unittest.TestCase):
    """A test enabled on a machine where its build is not (rt.conf:72 today)."""

    CONF = """\
        COMPILE | good | intel | -DA | | fv3 |
        RUN | a |  | baseline |
        COMPILE | skipped | intel | -DB | - noaacloud | fv3 |
        RUN | b |  | baseline |
    """

    def test_rtlib_skips_but_rtsh_runs_with_wrong_build(self):
        sb = Sandbox(self.CONF, ["a", "b"])
        try:
            p = plan.make_plan(sb.suite(), plan.Options("noaacloud"))
            self.assertEqual(run_ids(p), ["a_intel"])
            old = legacy.legacy_plan(sb.conf, sb.path, "noaacloud")
            self.assertEqual(old.runs[-1].test_id, "b_intel")
            self.assertEqual(old.runs[-1].compile_id, "skipped_intel")  # never compiled
            warnings = [str(f) for f in validate(sb.suite(), sb.path)]
            self.assertTrue(any("b is enabled on noaacloud but build skipped_intel is not" in w
                                for w in warnings), warnings)
        finally:
            sb.close()


class TestValidate(unittest.TestCase):
    def test_findings(self):
        sb = Sandbox("""\
            COMPILE | a | intel | -DX | + hera horizon | fv3 |
            RUN | t1 | + hera | baseline |
            RUN | t1 | + hera | |
            RUN | t2 | + hera | | nothere
            COMPILE | a | intel | -DX | | fv3 |
            RUN | t3 | | | t1
            RUN | missing_file | | |
        """, ["t1", "t2", "t3"])
        try:
            msgs = [str(f) for f in validate(sb.suite(), sb.path)]
            text = "\n".join(msgs)
            self.assertIn("unknown machine 'horizon'", text)
            self.assertIn("test t1 listed twice", text)
            self.assertIn("t2 depends on nothere, which has no intel entry", text)
            self.assertIn("duplicate build a_intel", text)
            self.assertIn("tests/missing_file does not exist", text)
            self.assertIn("t3 runs on orion but its dependency t1 does not", text)
        finally:
            sb.close()


class TestRealConfFiles(unittest.TestCase):
    """Checks against the conf files in this tests/ directory."""

    CONFS = ["rt.conf", "rt_weekly.conf", "rt_gfsv17opn.conf", "error-test.conf"]

    def test_load_and_validate_without_errors(self):
        for conf in self.CONFS:
            with self.subTest(conf=conf):
                suite = rtconf.load(os.path.join(PATHRT, conf))
                errors = [f for f in validate(suite, PATHRT) if f.level == "error"]
                self.assertEqual(errors, [])

    def test_matches_rtsh_except_reviewed_differences(self):
        """rtlib == rt.sh for full, -c and -o runs on every machine, except
        tests that validate() flags as running without their build."""
        conf = os.path.join(PATHRT, "rt.conf")
        suite = rtconf.load(conf)
        flagged = {
            (f.message.split()[0], f.message.split(" on ")[1].split()[0])
            for f in validate(suite, PATHRT)
            if "rt.sh would run it with no executable" in f.message
        }
        for m in KNOWN_MACHINES:
            for cb, co in ((False, False), (True, False), (False, True)):
                with self.subTest(machine=m, c=cb, o=co):
                    old = legacy.legacy_plan(conf, PATHRT, m, cb, co).tasks
                    new = plan.make_plan(suite, plan.Options(m, cb, co)).tasks
                    extra = [t for t in old if t not in new]
                    self.assertTrue(all(t in old for t in new))
                    for t in extra:
                        self.assertIn((t.test_id.rsplit("_", 1)[0], m), flagged, t)


class TestCli(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_plan_and_validate(self):
        rc, out, _ = self.run_cli("plan", "-m", "hera", "-n", "control_p8 intel")
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines()[1].split(" | ")[0], "RUN control_p8_intel")
        rc, _, err = self.run_cli("validate", "-q")
        self.assertEqual(rc, 0)
        self.assertIn("0 errors", err)
        rc, _, err = self.run_cli("plan", "-m", "hera", "-n", "no_such_test intel")
        self.assertEqual(rc, 1)
        self.assertIn("not defined", err)


if __name__ == "__main__":
    unittest.main()
