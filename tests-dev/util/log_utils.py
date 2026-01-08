import re
from pathlib import Path

def normalize_log_stem(stem):
    return stem.replace("compile_", "").replace("run_", "")

def format_seconds(sec):
    try:
        sec = int(float(sec))
        return f"{sec // 60:02d}:{sec % 60:02d}"
    except:
        return "??:??"

def parse_timestamp_file(path):
    if not path or not path.exists():
        return None
    line = path.read_text().strip()
    parts = line.split(",")
    if len(parts) != 6:
        return None
    try:
        start_full = int(parts[1])
        start_run = int(parts[2])
        end_run = int(parts[3])
        end_full = int(parts[4])
        status_flag = int(parts[5])
        full_time = format_seconds(end_full - start_full)
        run_time = format_seconds(end_run - start_run)
        status = "PASS" if status_flag == 1 else "FAIL"
        return status, full_time, run_time
    except:
        return None

def extract_rt_metrics(rt_path):
    if not rt_path.exists():
        return "UNKNOWN", "", ""
    status = "UNKNOWN"
    run_time = ""
    memory_mb = ""
    for line in rt_path.read_text().splitlines():
        line_upper = line.strip().upper()
        if "TEST" in line_upper and "PASS" in line_upper:
            status = "PASS"
        elif "TEST" in line_upper and "FAIL" in line_upper:
            status = "FAIL"
        elif "TOTAL AMOUNT OF WALL TIME" in line_upper:
            match = re.search(r"=\s*([\d.]+)", line)
            if match:
                run_time = format_seconds(float(match.group(1)))
        elif "MAXIMUM RESIDENT SET SIZE" in line_upper:
            match = re.search(r"=\s*(\d+)", line)
            if match:
                memory_kb = int(match.group(1))
                memory_mb = str(memory_kb // 1024)
    return status, run_time, memory_mb

def extract_compile_metrics(log_path):
    warnings = remarks = 0
    if not log_path.exists():
        return "", ""
    for line in log_path.read_text().splitlines():
        line_lower = line.strip().lower()
        if "warning" in line_lower:
            warnings += 1
        if "remark" in line_lower:
            remarks += 1
    return str(warnings), str(remarks)
