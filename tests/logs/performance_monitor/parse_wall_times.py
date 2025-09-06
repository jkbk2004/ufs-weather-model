import re, os, json, csv
from datetime import datetime
from statistics import median
from collections import defaultdict

def parse_wall_time(line):
    match = re.search(r"

\[(\d+):(\d+)", line)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return h * 60 + m
    return None

def extract_baseline_dates(conf_path="bl_date.conf"):
    dates = []
    with open(conf_path) as f:
        for line in f:
            if "export BL_DATE=" in line:
                date_str = line.strip().split("=")[-1]
                try:
                    dates.append(datetime.strptime(date_str, "%Y%m%d").date())
                except ValueError:
                    continue
    return sorted(set(dates))

def extract_wall_times(log_dir=".", conf_path="bl_date.conf"):
    raw_data = defaultdict(list)
    for fname in sorted(os.listdir(log_dir)):
        if not fname.startswith("RegressionTests_") or not fname.endswith(".log"):
            continue
        path = os.path.join(log_dir, fname)
        date_match = re.search(r"_(\d{8})", fname)
        log_date = datetime.strptime(date_match.group(1), "%Y%m%d").date() if date_match else datetime.fromtimestamp(os.path.getmtime(path)).date()

        with open(path) as f:
            for line in f:
                if "PASS -- TEST" in line:
                    test = re.search(r"TEST '([^']+)'", line).group(1)
                    time = parse_wall_time(line)
                    if time:
                        raw_data[test].append((log_date, time))

    # Detect anomalies
    final_data = defaultdict(list)
    for test, entries in raw_data.items():
        times = [t for _, t in entries]
        med = median(times)
        for date, time in entries:
            anomaly = None
            if time > 1.5 * med:
                anomaly = "spike"
            elif time < 0.5 * med:
                anomaly = "drop"
            final_data[test].append({"date": date.isoformat(), "wall_time": time, "anomaly": anomaly})

    # Export
    with open("wall_time_data.json", "w") as jf:
        json.dump(final_data, jf, indent=2)

    with open("wall_time_data.csv", "w", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["Test", "Date", "WallTime", "Anomaly"])
        for test, entries in final_data.items():
            for entry in entries:
                writer.writerow([test, entry["date"], entry["wall_time"], entry["anomaly"] or ""])

    return final_data, extract_baseline_dates(conf_path)
