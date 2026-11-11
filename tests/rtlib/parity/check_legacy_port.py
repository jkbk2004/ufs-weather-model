#!/usr/bin/env python3
"""Prove rtlib.legacy reproduces the real rt.sh selection code.

Runs rtsh_plan.sh (rt.sh's own bash, with job submission stubbed) and
rtlib.legacy over every machine, the -c/-o modes, every conf file, plus a
seeded sample of -n tests and -b lists, and compares the plans.

    python3 tests/rtlib/parity/check_legacy_port.py [--jobs 8] [--samples 40]

Exit status 0 only if every case is identical. Takes a few minutes; needs
bash but no HPC, scheduler or model build.
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PATHRT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, PATHRT)

from rtlib import legacy, rtconf  # noqa: E402
from rtlib.machines import KNOWN_MACHINES  # noqa: E402


def normalise(text: str) -> str:
    """Any early exit counts as just 'EXIT' (messages and partial output differ)."""
    lines = text.splitlines()
    if any(l.startswith("EXIT") for l in lines):
        return "EXIT\n"
    return "".join(l + "\n" for l in lines)


def run_bash(case) -> str:
    machine, conf, flags, sel = case
    cmd = [os.path.join(HERE, "rtsh_plan.sh"), PATHRT, machine, "-l", conf] + flags
    tmp = None
    if sel is not None and len(sel) == 1:
        cmd += ["-n", sel[0]]
    elif sel is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        tmp.write("".join(s + "\n" for s in sel))
        tmp.close()
        cmd += ["-b", tmp.name]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, check=True).stdout
    finally:
        if tmp:
            os.unlink(tmp.name)
    return normalise(out)


def run_python(case) -> str:
    machine, conf, flags, sel = case
    try:
        p = legacy.legacy_plan(os.path.join(PATHRT, conf), PATHRT, machine,
                               "-c" in flags, "-o" in flags, sel)
        return normalise(p.to_text())
    except legacy.LegacyExit:
        return "EXIT\n"


def cases(samples: int, seed: int):
    confs = sorted(f for f in os.listdir(PATHRT) if f.endswith(".conf") and f != "bl_date.conf")
    for conf in confs:
        for m in KNOWN_MACHINES:
            for flags in ([], ["-c"], ["-o"]):
                if conf != "rt.conf" and flags:
                    continue
                yield (m, conf, flags, None)

    suite = rtconf.load(os.path.join(PATHRT, "rt.conf"))
    pairs = sorted({f"{t.name} {b.compiler}" for b, t in suite.iter_tests()})
    rng = random.Random(seed)
    for _ in range(samples):  # -n
        yield (rng.choice(KNOWN_MACHINES), "rt.conf",
               ["-c"] if rng.random() < 0.3 else [], [rng.choice(pairs)])
    for _ in range(samples // 2):  # -b
        yield (rng.choice(KNOWN_MACHINES), "rt.conf",
               ["-c"] if rng.random() < 0.5 else [], rng.sample(pairs, rng.randint(2, 15)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--samples", type=int, default=40, help="number of -n cases (half as many -b)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    todo = list(cases(a.samples, a.seed))
    with ThreadPoolExecutor(a.jobs) as pool:
        bash_out = list(pool.map(run_bash, todo))

    bad = 0
    for case, b in zip(todo, bash_out):
        p = run_python(case)
        machine, conf, flags, sel = case
        label = f"{machine:9s} {conf:20s} {' '.join(flags):3s} " + (
            "" if sel is None else (f"-n '{sel[0]}'" if len(sel) == 1 else f"-b <{len(sel)} tests>"))
        if b == p:
            print(f"ok    {label}  ({b.count(chr(10))} tasks)")
        else:
            bad += 1
            print(f"FAIL  {label}")
            for line in sorted(set(b.splitlines()) ^ set(p.splitlines()))[:10]:
                side = "bash  " if line in b.splitlines() else "python"
                print(f"        {side}: {line}")
    print(f"\n{len(todo) - bad}/{len(todo)} cases identical")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
