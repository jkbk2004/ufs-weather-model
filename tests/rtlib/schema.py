"""Data model for regression-test suites.

A suite is an ordered list of Builds; each Build owns the Tests that run
with its executable. This is the same structure rt.conf encodes implicitly
("a RUN line belongs to the COMPILE line above it"), made explicit.

Only the standard library is used so this works with python 3.8 on WCOSS2.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional, Tuple

COMPILERS = ("intel", "intelllvm", "gnu")


@dataclass(frozen=True)
class Source:
    """Where an entry came from, for error messages (file:line)."""

    path: str = "<memory>"
    line: int = 0

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class MachineFilter:
    """Which machines an entry runs on.

    mode is one of:
      "all"     - empty spec in rt.conf
      "only"    - "+ hera orion"   (run only on these)
      "exclude" - "- wcoss2 acorn" (run everywhere except these)

    raw keeps the original rt.conf text, needed to reproduce rt.sh exactly.
    """

    mode: str = "all"
    machines: Tuple[str, ...] = ()
    raw: str = ""

    @classmethod
    def parse(cls, spec: str) -> "MachineFilter":
        spec = spec.strip()
        if spec == "":
            return cls("all", (), spec)
        if spec[0] not in "+-":
            raise ValueError(
                f"machine spec must be empty or start with '+' or '-': '{spec}'"
            )
        names = tuple(spec[1:].split())
        return cls("only" if spec[0] == "+" else "exclude", names, spec)

    def allows(self, machine: str, legacy: bool = False) -> bool:
        """True if this entry should run on `machine`.

        legacy=True reproduces rt.sh's `[[ ${MACHINES} =~ ${MACHINE_ID} ]]`,
        a regex *substring* test on the whole spec (so "+ gaeac6" would also
        match a machine called "gaea"). The default is an exact name match.
        """
        if self.mode == "all":
            return True
        if legacy:
            hit = re.search(machine, self.raw) is not None
        else:
            hit = machine in self.machines
        return hit if self.mode == "only" else not hit


@dataclass
class Test:
    name: str
    machines: MachineFilter = field(default_factory=MachineFilter)
    baseline_flag: str = ""  # rt.conf field 4, e.g. "baseline" or ""
    depends: str = ""  # rt.conf field 5: test whose output this one needs
    date_35d: str = ""  # rt.conf field 6 (35-day/weekly runs only)
    source: Source = field(default_factory=Source)

    @property
    def creates_baseline(self) -> bool:
        # rt.sh: [[ ${CB} != *baseline* ]] && skip   (substring test)
        return "baseline" in self.baseline_flag


@dataclass
class Build:
    name: str
    compiler: str
    make_opt: str  # cmake options, passed verbatim to run_compile.sh
    machines: MachineFilter = field(default_factory=MachineFilter)
    control_flag: str = "fv3"  # rt.conf field 6
    tests: List[Test] = field(default_factory=list)
    source: Source = field(default_factory=Source)

    @property
    def id(self) -> str:
        """COMPILE_ID used everywhere in rt.sh: <name>_<compiler>."""
        return f"{self.name}_{self.compiler}"

    @property
    def builds_for_baseline(self) -> bool:
        # rt.sh: [[ ${CREATE_BASELINE} == true && ${CB} != *fv3* ]] && skip
        return "fv3" in self.control_flag

    def test_id(self, test: Test) -> str:
        """TEST_ID used everywhere in rt.sh: <test>_<compiler>."""
        return f"{test.name}_{self.compiler}"


@dataclass
class Suite:
    builds: List[Build] = field(default_factory=list)
    path: str = "<memory>"

    def find_build(self, build_id: str) -> Optional[Build]:
        for b in self.builds:
            if b.id == build_id:
                return b
        return None

    def iter_tests(self):
        for b in self.builds:
            for t in b.tests:
                yield b, t
