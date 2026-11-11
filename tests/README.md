# rtlib: the Python layer for rt.sh, built one step at a time

`rtlib` lives inside `tests/`, next to `rt.sh`, and reads the same
`rt.conf`, `tests/` and `parm/` files in place. There is no second copy of
anything to keep in sync. Each step replaces one job rt.sh does today. Each
step is checked against the real rt.sh on every machine before it is
switched on.

Requirements: Python 3.8 or newer, standard library only (wcoss2/acorn
ship 3.8.6). Bash is needed only for the parity check.

## Step 1 (this change): read and select, but run nothing

rt.sh is not modified. This step adds:

| module | replaces in rt.sh |
|---|---|
| `schema.py` | the implicit structure of rt.conf (a build owns the tests below it) |
| `rtconf.py` | the `cut -d'|' … | sed` parsing, with every error reported as `file:line` |
| `plan.py` | `update_rtconf` (`-n`/`-b`) and the main `while read line` selection loop |
| `validate.py` | nothing: new checks rt.sh never made |
| `legacy.py` | a line-for-line port of the rt.sh code above, kept only as a reference to check against |
| `parity/` | runs rt.sh's **own** bash (extracted at run time) with job submission stubbed out |

### Commands

```bash
cd tests
python3 -m rtlib validate                 # all checks on rt.conf; exit 1 on errors
python3 -m rtlib validate -l rt_weekly.conf
python3 -m rtlib plan -m hera             # what rt.sh would compile/run on hera
python3 -m rtlib plan -m hera -c -n "cpld_restart_gfsv17_iau intel"
python3 -m rtlib plan -m orion -b my_list.txt --json
python3 -m rtlib diff-legacy              # rtlib vs rt.sh behaviour, every machine
python3 -m rtlib diff-legacy --each-test  # ... and -n for every test
python3 -m unittest rtlib.test_rtlib -v   # unit tests (< 1 s)
python3 rtlib/parity/check_legacy_port.py # real rt.sh bash vs legacy.py (a few minutes)
```

### How it was verified

1. **The real rt.sh matches `legacy.py`.** `parity/check_legacy_port.py`
   cuts `update_rtconf`, `rt_35d` and the main loop out of `rt.sh` and runs
   them with `run_compile.sh` and `run_test.sh` stubbed. Each test file is
   still sourced and its task counts computed. The result matched
   `legacy.py` in **150 of 150 cases**: 10 machines, default/`-c`/`-o`, all
   4 conf files, 60 random `-n` and 30 random `-b` selections.
2. **`legacy.py` matches `plan.py`** except for the deliberate fixes listed
   below. `diff-legacy` prints every difference. Full and `-c` runs are
   identical on 9 of 10 machines (noaacloud is fix 1), and `-o` runs are
   identical on all 10. With `-n`, 2,461 of 2,480
   test×machine cases are identical.

### Deliberate differences from rt.sh (all bugs found by step 1)

1. **Tests run against a build that was skipped.** When a COMPILE line is
   excluded on a machine, rt.sh still runs the RUN lines under it that lack
   the same filter, using an executable it never built. With `-n` or `-b`,
   they get the *previous* build's executable instead. Today this happens on
   noaacloud, rt.conf lines 72, 75, 78 and 81 (`cpld_control_{c48_5deg,
   c24_5deg,c24_9deg,c12_9deg}`). rtlib skips these tests, and `validate`
   warns about them. **Fix in rt.conf:** add `- noaacloud` to those four
   lines.
2. **Dependencies more than one level deep.** `-n cpld_restart_gfsv17_iau`
   needs `cpld_control_gfsv17_iau`, which needs `cpld_control_gfsv17`. rt.sh
   adds only the first. rtlib follows the whole chain.
3. **The dependency lookup is a grep of rt.conf text.** rt.sh takes the
   first and second `RUN` it finds and assumes they are the intel and gnu
   entries, so it fails when that isn't true:
   - `-n "rap_restart_dyn32_phy32 gnu"` on hercules/derecho picks the
     hera/ursa-only control line, so the restart runs without its control.
   - `-n "hrrr_control_restart_noqr gnu"` on hera/ursa makes rt.sh die with
     "tests/RUN does not exist".
   - Dependencies are never added for `intelllvm`.

   rtlib looks the dependency up in the parsed suite (same compiler,
   enabled on the same machine).
4. **`-c` with only non-baseline tests.** rt.sh compiles the build and then
   runs nothing. rtlib stops before compiling and says why.
5. **Machine names are matched exactly.** rt.sh uses a regex substring
   match (`[[ $MACHINES =~ $MACHINE_ID ]]`). No current machine names
   overlap, so nothing changes today, but a future `gaea` would match
   `+ gaeac6`.
6. **`-c -b` skips builds that have nothing left to run.** rt.sh compiles
   them anyway.

`-b` entries that exist but are not enabled on the current machine are
skipped with a note, as rt.sh does. Entries that exist nowhere are an
error, because they are almost always typos.

## The next steps

Each step is a separate PR. Each one is switched on only once its parity
diff is clean, and each one deletes the bash it replaces.

| step | what moves to Python | parity check |
|---|---|---|
| **2** | rt.sh calls `python3 -m rtlib plan` for selection, behind `RT_PY=1`. Bash still sources each test file to get task counts and writes the `.env` files. | `rtsh_plan.sh` output with `RT_PY=0` vs `RT_PY=1` |
| **3** | The machine `case` block in rt.sh becomes `machines.yaml` (DISKNM, STMP, PTMP, QUEUE, PARTITION, SCHEDULER, module loads). | the generated env per machine |
| **4** | The Rocoto XML and ecFlow `.def` generators move behind one `Backend` interface (`direct`, `rocoto`, `ecflow`). | byte diff of `rocoto_workflow.xml` / `*.def` on dry runs |
| **5** | `generate_log` moves to Python, with byte-identical `RegressionTests_<machine>.log`, which `ci/check_status.py` parses. | log diff on real run directories |
| **6** | Phase B: `rt.conf` becomes `rt.yaml` in **one** PR. A converter is generated from the same `schema.py`, the YAML is never hand-edited alongside rt.conf, and `-n`/`-b` become filters rather than file rewrites. | plan diff on every machine |
| **7+** | Test definitions: a snapshot of `source default_vars.sh; source tests/X; env` becomes per-test YAML using profiles (`fv3`, `tiled`, `cpl`, …), converted one family at a time. | env diff for every test |

When `RT_PY=1` has been the default for a while, `legacy.py` and the bash
selection loop are deleted.

## Lessons from tests-dev that shaped this

- **One location.** No `ufs_test.sh` beside `rt.sh` and no copied test
  files. If rt.sh doesn't depend on the Python, it goes stale.
- **One source of truth at a time.** Read `rt.conf` until the single PR
  that replaces it.
- **CI that fails on drift.** `validate` and the unit tests run in seconds
  without HPC, so they can run on every PR. The parity check runs whenever
  rt.sh or rt_utils.sh changes.