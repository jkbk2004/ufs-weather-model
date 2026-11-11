"""Read rt.conf-format files into a Suite.

Field layout (see the header of rt.conf):

  COMPILE | name | compiler | cmake options | machines | fv3 |
  RUN     | test | machines | baseline      | depends  | [35d date]

Parsing follows rt.sh's rules: leading whitespace is stripped, blank lines
and lines starting with '#' are skipped, each field is `cut -d'|'` and
trimmed of spaces.
"""

from typing import List, Tuple

from .schema import COMPILERS, Build, MachineFilter, Source, Suite, Test


class ConfError(Exception):
    """One or more problems in a conf file. .errors holds every message."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def _field(parts: List[str], n: int) -> str:
    """Equivalent of `cut -d'|' -fN | sed 's/^ *//; s/ *$//'` (1-based)."""
    return parts[n - 1].strip(" ") if len(parts) >= n else ""


def iter_lines(path: str) -> List[Tuple[int, str]]:
    """(line number, text) for every non-blank, non-comment line.

    Matches rt.sh: `line="${line#"${line%%[![:space:]]*}"}"` strips leading
    whitespace; empty lines and lines starting with '#' are skipped.
    """
    out = []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, start=1):
            line = raw.rstrip("\n").lstrip()
            if not line or line.startswith("#"):
                continue
            out.append((n, line))
    return out


def load(path: str) -> Suite:
    """Parse an rt.conf-format file. Raises ConfError listing every problem."""
    suite = Suite(path=path)
    errors: List[str] = []
    current = None

    for n, line in iter_lines(path):
        src = Source(path, n)
        parts = line.split("|")

        if line.startswith("COMPILE"):
            name, compiler = _field(parts, 2), _field(parts, 3)
            if not name:
                errors.append(f"{src}: COMPILE line has no name")
            if compiler not in COMPILERS:
                errors.append(
                    f"{src}: compiler '{compiler}' must be one of {', '.join(COMPILERS)}"
                )
            try:
                machines = MachineFilter.parse(_field(parts, 5))
            except ValueError as e:
                errors.append(f"{src}: {e}")
                machines = MachineFilter()
            current = Build(
                name=name,
                compiler=compiler,
                make_opt=_field(parts, 4),
                machines=machines,
                control_flag=parts[5] if len(parts) >= 6 else "",
                source=src,
            )
            suite.builds.append(current)

        elif line.startswith("RUN"):
            if current is None:
                errors.append(f"{src}: RUN line before any COMPILE line")
                continue
            try:
                machines = MachineFilter.parse(_field(parts, 3))
            except ValueError as e:
                errors.append(f"{src}: {e}")
                machines = MachineFilter()
            name = _field(parts, 2)
            if not name:
                errors.append(f"{src}: RUN line has no test name")
            current.tests.append(
                Test(
                    name=name,
                    machines=machines,
                    baseline_flag=parts[3] if len(parts) >= 4 else "",
                    depends=_field(parts, 5),
                    date_35d=_field(parts, 6),
                    source=src,
                )
            )
        else:
            errors.append(f"{src}: unknown command (expected COMPILE or RUN): {line}")

    if errors:
        raise ConfError(errors)
    return suite
