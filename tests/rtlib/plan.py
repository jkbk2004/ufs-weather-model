"""Turn a Suite into the ordered list of compile and run tasks for one machine.

This replaces the selection half of rt.sh (update_rtconf + the main
`while read line` loop). It decides *what* runs; it does not run anything.

Behaviour matches rt.sh except for three deliberate fixes, each reported by
`python3 -m rtlib diff-legacy` so they can be reviewed before switching over:

  1. Machine names are matched exactly, not as a regex substring.
  2. A test whose build is skipped on this machine is skipped too. rt.sh
     instead runs it against the previous COMPILE_ID's variables, i.e. an
     executable that was never built.
  3. -n / -b pull in dependencies from the suite itself (same compiler,
     same machine, no duplicates) instead of grepping rt.conf text, which
     only works for intel/gnu and can pick up commented-out lines.

Use rtlib.legacy for a line-for-line reproduction of rt.sh.
"""

from dataclasses import dataclass
import json
from typing import Iterable, List, Optional, Sequence, Set, Tuple, Union

from .schema import Build, Suite, Test


@dataclass(frozen=True)
class CompileTask:
    compile_id: str
    make_opt: str

    def to_text(self) -> str:
        return f"COMPILE {self.compile_id} | {self.make_opt}"


@dataclass(frozen=True)
class RunTask:
    test_name: str  # file under tests/tests/ (differs from test_id for 35-day runs)
    test_id: str  # <test>_<compiler>
    compile_id: str
    dep_run: str  # test_id this test waits for, or ""

    def to_text(self) -> str:
        return (
            f"RUN {self.test_id} | test={self.test_name} | "
            f"compile={self.compile_id} | dep={self.dep_run or '-'}"
        )


Task = Union[CompileTask, RunTask]


@dataclass
class Plan:
    machine: str
    tasks: List[Task]
    notes: Tuple[str, ...] = ()  # non-fatal messages for the user (stderr)

    @property
    def compiles(self) -> List[CompileTask]:
        return [t for t in self.tasks if isinstance(t, CompileTask)]

    @property
    def runs(self) -> List[RunTask]:
        return [t for t in self.tasks if isinstance(t, RunTask)]

    def to_text(self) -> str:
        return "".join(t.to_text() + "\n" for t in self.tasks)

    def to_json(self) -> str:
        items = []
        for t in self.tasks:
            d = dict(t.__dict__)
            d["kind"] = "compile" if isinstance(t, CompileTask) else "run"
            items.append(d)
        return json.dumps({"machine": self.machine, "tasks": items}, indent=2)


@dataclass
class Options:
    machine: str
    create_baseline: bool = False  # -c
    compile_only: bool = False  # -o
    # -n "name compiler" or the lines of a -b file; None means "everything"
    selected: Optional[Sequence[Tuple[str, str]]] = None
    weekly_35d: bool = False  # rt.sh sets this when the conf file name has 35d/weekly


class SelectionError(Exception):
    pass


def parse_selection(lines: Iterable[str]) -> List[Tuple[str, str]]:
    """Parse '-n "control_p8 intel"' or the lines of a -b file."""
    out = []
    for raw in lines:
        words = raw.split()
        if not words:
            continue
        if len(words) != 2:
            raise SelectionError(f"expected '<test> <compiler>', got '{raw.strip()}'")
        out.append((words[0], words[1]))
    return out


def _runs_on(build: Build, test: Test, machine: str) -> bool:
    return build.machines.allows(machine) and test.machines.allows(machine)


def _find(suite: Suite, name: str, compiler: str, machine: str):
    return [
        (b, t)
        for b, t in suite.iter_tests()
        if t.name == name and b.compiler == compiler and _runs_on(b, t, machine)
    ]


def _resolve_selection(suite: Suite, opts: Options):
    """(build id, test name) pairs for -n/-b, plus everything they depend on.

    Entries that exist but cannot run on this machine are skipped with a
    note, as rt.sh does (one -b list is often shared by all machines).
    Entries that exist nowhere are an error: almost always a typo.
    """
    defined = {(t.name, b.compiler) for b, t in suite.iter_tests()}
    unknown = sorted({f"{n} {c}" for n, c in (opts.selected or []) if (n, c) not in defined})
    if unknown:
        raise SelectionError(f"not defined in {suite.path}: {', '.join(unknown)}")

    wanted: Set[Tuple[str, str]] = set()
    notes: List[str] = []
    todo = [(n, c, None) for n, c in (opts.selected or [])]
    while todo:
        name, compiler, needed_by = todo.pop()
        hits = _find(suite, name, compiler, opts.machine)
        if not hits:
            if needed_by:
                raise SelectionError(
                    f"{needed_by} needs {name} {compiler}, which cannot run on {opts.machine}"
                )
            notes.append(f"skipping {name} {compiler}: not enabled on {opts.machine}")
            continue
        for b, t in hits:
            key = (b.id, t.name)
            if key in wanted:
                continue
            wanted.add(key)
            if t.depends:
                todo.append((t.depends, b.compiler, f"{t.name} {b.compiler}"))
    return wanted, notes


def make_plan(suite: Suite, opts: Options) -> Plan:
    m = opts.machine
    wanted, notes = None, []
    if opts.selected is not None:
        wanted, notes = _resolve_selection(suite, opts)
    tasks: List[Task] = []

    for b in suite.builds:
        if not b.machines.allows(m):
            continue
        if opts.create_baseline and not b.builds_for_baseline:
            continue

        runs: List[RunTask] = []
        if not opts.compile_only:
            for t in b.tests:
                if not t.machines.allows(m):
                    continue
                if opts.create_baseline and not t.creates_baseline:
                    continue
                if wanted is not None and (b.id, t.name) not in wanted:
                    continue
                test_name = t.name
                if opts.weekly_35d and "35d" in t.name:
                    test_name = f"{t.name}_{t.date_35d}"
                dep = f"{t.depends}_{b.compiler}" if t.depends else ""
                runs.append(RunTask(test_name, b.test_id(t), b.id, dep))

        # With -n/-b only builds that have a selected test are compiled.
        if wanted is not None and not runs:
            continue
        tasks.append(CompileTask(b.id, b.make_opt))
        tasks.extend(runs)

    if wanted is not None and not tasks:
        if opts.create_baseline:
            raise SelectionError(
                "none of the selected tests creates a baseline "
                "(-c only runs tests marked 'baseline' in the conf file)"
            )
        raise SelectionError(
            f"the tests listed/chosen do not exist or cannot be run on {m}"
        )
    return Plan(m, tasks, tuple(sorted(notes)))
