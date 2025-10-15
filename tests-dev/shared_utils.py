def extract_bl_date(filepath="bl_date.conf"):
    """Extracts the BL_DATE value from a shell-style config file."""
    with open(filepath) as f:
        for line in f:
            if line.startswith("export BL_DATE="):
                return line.split("=")[1].strip()
    raise ValueError("BL_DATE not found in bl_date.conf")


def enrich_test_context(tests, machine_config, machine):
    """Adds job metadata to each test based on type and machine-specific resources."""
    for test in tests:
        if test["type"] == "compile":
            test["name"] = f"compile_{test['id']}"
            test["jobname"] = test["name"]
            test["command"] = (
                f"&PATHRT;/run_compile.sh &PATHRT; &RUNDIR_ROOT; \"{test['option']}\" {test['id']} "
                f"2>&1 | tee &LOG;/compile_{test['id']}.log"
            )
            test["nodes"] = "1:ppn=8"
            test["walltime"] = "01:00:00"

        elif test["type"] == "run":
            test["name"] = f"{test['id']}_{test['compiler']}"
            test["jobname"] = test["name"]
            test["command"] = (
                f"bash -c 'set -xe -o pipefail ; &PATHRT;/run_test.sh &PATHRT; &RUNDIR_ROOT; "
                f"{test['id']} {test['name']} {test['parent']} 2>&1 | tee &LOG;/run_{test['name']}.log'"
            )

            # Default resource values
            ppn = 40
            nodes = 8
            wlclk = 30

            # Override with machine-specific resources if available
            resources = test.get("resources", {})
            if machine in resources:
                r = resources[machine]
                ppn = r.get("ppn", ppn)
                nodes = r.get("nodes", nodes)
                wlclk = r.get("wlclk", wlclk)

            test["nodes"] = f"{nodes}:ppn={ppn}"
            test["walltime"] = f"00:{wlclk:02}:00"

        # Common metadata
        test["account"] = machine_config.get("ACCOUNT", "epic")
        test["queue"] = machine_config.get("QUEUE", "batch")
        test["partition"] = machine
        test["join"] = f"&RUNDIR_ROOT;/{test['name']}.log"
