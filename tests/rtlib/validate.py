"""Static checks on a Suite. Fast, needs no HPC, meant to run in CI on every PR.

Errors are things rt.sh would die on, or that make a test fail at runtime.
Warnings are things that work today only by accident.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .machines import KNOWN_MACHINES
from .schema import Build, Suite, Test


@dataclass
class Finding:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.where}: {self.message}"


def validate(
    suite: Suite, pathrt: str, machines: Sequence[str] = KNOWN_MACHINES
) -> List[Finding]:
    out: List[Finding] = []

    def err(where, msg):
        out.append(Finding("error", str(where), msg))

    def warn(where, msg):
        out.append(Finding("warning", str(where), msg))

    known = set(machines)

    # -- per entry ---------------------------------------------------------
    seen_builds: Dict[str, Build] = {}
    for b in suite.builds:
        if b.id in seen_builds:
            err(b.source, f"duplicate build {b.id} (first at {seen_builds[b.id].source})")
        seen_builds.setdefault(b.id, b)
        for m in b.machines.machines:
            if m not in known:
                err(b.source, f"build {b.id}: unknown machine '{m}'")
        if not b.tests:
            warn(b.source, f"build {b.id} has no tests")

        seen_tests: Dict[str, Test] = {}
        for t in b.tests:
            if t.name in seen_tests:
                err(t.source, f"test {t.name} listed twice in build {b.id}")
            seen_tests.setdefault(t.name, t)
            for m in t.machines.machines:
                if m not in known:
                    err(t.source, f"test {t.name}: unknown machine '{m}'")
            if not os.path.isfile(os.path.join(pathrt, "tests", t.name)):
                err(t.source, f"test file tests/{t.name} does not exist")

    # -- dependencies --------------------------------------------------------
    # index: (test name, compiler) -> [(build, test, position in file)]
    index: Dict[Tuple[str, str], List[Tuple[Build, Test, int]]] = {}
    pos = 0
    position = {}
    for b, t in suite.iter_tests():
        pos += 1
        position[id(t)] = pos
        index.setdefault((t.name, b.compiler), []).append((b, t, pos))

    for b, t in suite.iter_tests():
        if not t.depends:
            continue
        targets = index.get((t.depends, b.compiler), [])
        if not targets:
            err(t.source, f"{t.name} depends on {t.depends}, which has no {b.compiler} entry")
            continue
        if all(p > position[id(t)] for _, _, p in targets):
            warn(t.source, f"{t.name} depends on {t.depends}, which is listed after it")
        if t.creates_baseline and not any(dt.creates_baseline for _, dt, _ in targets):
            warn(
                t.source,
                f"{t.name} creates a baseline but its dependency {t.depends} does not; "
                "with -c it runs without it",
            )

    # -- per machine ---------------------------------------------------------
    for m in machines:
        for b, t in suite.iter_tests():
            if not t.machines.allows(m):
                continue
            if not b.machines.allows(m):
                # rt.sh still runs these against an executable it never built
                warn(
                    t.source,
                    f"{t.name} is enabled on {m} but build {b.id} is not; "
                    "rt.sh would run it with no executable",
                )
                continue
            if t.depends:
                runs = [
                    1
                    for db, dt, _ in index.get((t.depends, b.compiler), [])
                    if db.machines.allows(m) and dt.machines.allows(m)
                ]
                if not runs:
                    err(t.source, f"{t.name} runs on {m} but its dependency {t.depends} does not")
    return out
