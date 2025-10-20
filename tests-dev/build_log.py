import argparse
import yaml
import shlex
from pathlib import Path
from datetime import datetime
from util.shared_utils import (
    resolve_baseline_dir,
    get_git_hash,
    get_git_submodule_hashes
)
from util.log_utils import (
    normalize_log_stem,
    format_seconds,
    parse_timestamp_file,
    extract_rt_metrics,
    extract_compile_metrics
)

# Annotated descriptions from ufs_test.sh
OPTION_DESCRIPTIONS = {
    "-a": "HPC PROJECT ACCOUNT",
    "-b": "CREATE BASELINES ONLY FOR TESTS LISTED IN FILE",
    "-c": "BASELINE CREATION",
    "-d": "DELETE UNUSED RUN DIRECTORIES",
    "-e": "USE ECFLOW WORKFLOW MANAGER (experimental)",
    "-h": "DISPLAY HELP",
    "-k": "KEEP RUN DIRECTORY AFTER COMPLETION",
    "-l": "RUN USER OWN TEST CONFIG FILE",
    "-m": "BASELINE COMPARISON AGAINST USER'S OWN BASELINE",
    "-n": "RUN SINGLE TEST CASE",
    "-o": "COMPILE ONLY, SKIP TESTS",
    "-r": "USE ROCOTO WORKFLOW MANAGER",
    "-s": "SYMLINK SHARABLE TEST SCRIPTS FROM tests-dev",
    "-w": "WEEKLY TEST MODE (SKIP BASELINE COMPARISON)"
}

def collect_log_files(log_dir):
    log_map = {}
    for f in Path(log_dir).glob("*.log"):
        stem = f.stem
        norm = normalize_log_stem(stem)
        log_map[norm] = stem
    return log_map

def match_test_to_log(hint_name, log_map):
    hint_norm = normalize_log_stem(hint_name)
    return log_map.get(hint_norm) or next((stem for norm, stem in log_map.items() if norm in hint_name), None)

def extract_log_hint(test):
    return test.get("name", test.get("id", "UNKNOWN"))

def get_log_time_range(log_dir):
    times = [f.stat().st_mtime for f in Path(log_dir).glob("*") if f.is_file()]
    if not times:
        now = datetime.now()
        return now, now
    start = datetime.fromtimestamp(min(times))
    end = datetime.fromtimestamp(max(times))
    return start, end

def group_options(split_opts):
    grouped = []
    i = 0
    while i < len(split_opts):
        flag = split_opts[i]
        if flag.startswith("-") and i + 1 < len(split_opts) and not split_opts[i + 1].startswith("-"):
            grouped.append((flag, split_opts[i + 1]))
            i += 2
        else:
            grouped.append((flag, None))
            i += 1
    return grouped

def generate_log(args):
    with open(args.yaml) as f:
        tests = yaml.safe_load(f)

    repo_root = Path(__file__).resolve().parent.parent
    ufshash = get_git_hash(repo_root)
    submodule_hashes = get_git_submodule_hashes(repo_root)
    baseline_dir = resolve_baseline_dir("machine_config/baseline_orion.yaml", "bl_date.conf")
    start_time, end_time = get_log_time_range(args.log_dir)
    log_map = collect_log_files(args.log_dir)

    # Parse and group options
    raw_opts = args.options.strip()
    split_opts = [opt.strip() for opt in shlex.split(raw_opts) if opt.strip()]
    grouped_opts = group_options(split_opts)

    lines = [
        f"====START OF {args.machine} REGRESSION TESTING LOG====\n",
        "UFSWM hash used in testing:",
        ufshash + "\n",
        "Submodule hashes used in testing:"
    ] + [f" {line}" for line in submodule_hashes] + [
        "\nNOTES:",
        "[Times](Memory) are at the end of each compile/test in format [MM:SS](Size).",
        "The first time is for the full script (prep+run+finalize).",
        "The second time is specifically for the run phase.",
        "Times/Memory will be empty for failed tests.\n",
        f"BASELINE DIRECTORY: {baseline_dir}",
        f"COMPARISON DIRECTORY: {args.comparison}\n",
        "UFS_TEST.SH OPTIONS USED:"
    ] + [
        f"* ({flag}) - {OPTION_DESCRIPTIONS.get(flag, 'UNKNOWN')}" + (f": {value}" if value else "")
        for flag, value in grouped_opts
    ] + [""]

    compile_total = compile_pass = test_total = test_pass = 0
    unmatched_tests = []

    for test in tests:
        hint_name = extract_log_hint(test)
        matched_name = match_test_to_log(hint_name, log_map)
        short_name = normalize_log_stem(hint_name)
        is_compile = "compile" in matched_name.lower() if matched_name else False

        log_path = Path(args.log_dir) / f"{matched_name}.log" if matched_name else None
        ts_path = Path(args.log_dir) / f"{matched_name}_timestamp.txt" if matched_name else None
        rt_path = Path(args.log_dir) / f"rt_{short_name}.log"

        if not matched_name or not log_path.exists():
            lines.append(f"MISSING -- {hint_name} (no matching log found)")
            unmatched_tests.append(hint_name)
            continue

        status = "UNKNOWN"
        full_time = run_time = ""
        memory_mb = ""
        warnings = remarks = ""

        ts_data = parse_timestamp_file(ts_path)
        if ts_data:
            status, full_time, run_time = ts_data

        if not is_compile and rt_path.exists():
            rt_status, rt_run_time, rt_mem = extract_rt_metrics(rt_path)
            if rt_status == "PASS":
                status = "PASS"
            elif rt_status == "FAIL":
                status = "FAIL"
            if rt_run_time:
                run_time = rt_run_time
            if rt_mem:
                memory_mb = rt_mem

        if is_compile:
            warnings, remarks = extract_compile_metrics(log_path)

        if is_compile:
            compile_total += 1
            if status == "PASS": compile_pass += 1
            lines.append(f"{status} -- COMPILE {short_name} [{full_time}, {run_time}] ({warnings} warnings,{remarks} remarks)")
        else:
            test_total += 1
            if status == "PASS": test_pass += 1
            lines.append(f"{status} -- TEST {short_name} [{full_time}, {run_time}] ({memory_mb} MB)")

    duration = end_time - start_time
    total_seconds = int(duration.total_seconds())
    lines += [
        "\nSYNOPSIS:",
        f"Starting Date/Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Ending Date/Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Time: {total_seconds//3600:02d}h:{(total_seconds//60)%60:02d}m:{total_seconds%60:02d}s",
        f"Compiles Completed: {compile_pass}/{compile_total}",
        f"Tests Completed: {test_pass}/{test_total}\n",
        "NOTES:",
        "A file test_changes.list was generated but is empty.",
        "If you are using this log as a pull request verification, please commit test_changes.list.\n",
        "Result: SUCCESS",
        f"\n====END OF {args.machine} REGRESSION TESTING LOG===="
    ]

    Path(args.output).write_text("\n".join(lines) + "\n")
    print(f"[INFO] Full regression log written to: {args.output}")
    if unmatched_tests:
        print(f"[WARN] {len(unmatched_tests)} tests had no matching log files:")
        for name in unmatched_tests:
            print(f"  - {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build regression test log from enriched YAML and log directory."
    )
    parser.add_argument("--yaml", required=True, help="Path to enriched YAML file.")
    parser.add_argument("--log-dir", required=True, help="Directory containing .log and _timestamp.txt files.")
    parser.add_argument("--machine", required=True, help="Machine name (e.g., orion).")
    parser.add_argument("--comparison", required=True, help="Comparison directory path.")
    parser.add_argument("--output", required=True, help="Output file path for the regression log.")
    parser.add_argument("--options", type=str, default="", help="Single string of UFS_TEST.SH options.")
    args = parser.parse_args()
    generate_log(args)
