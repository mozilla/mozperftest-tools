import csv
import json
from datetime import datetime

def find_resolution_time(history):
    resolution_time = ""
    for changes in history:
        for change in changes["changes"]:
            if change["field_name"] == "resolution":
                resolution_time = changes["when"]
                break
    return resolution_time

def time_difference(creation_time, resolution_time):
    dt1 = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%SZ")
    dt2 = datetime.strptime(resolution_time, "%Y-%m-%dT%H:%M:%SZ")
    diff = dt2 - dt1
    days_float = diff.total_seconds() / (24 * 60 * 60)
    
    return days_float

def get_month_year(time_str):
    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%B %Y")

def read_csv_as_dicts_with_json_history(file_path):
    data = []
    total_per_year = {
        "2022": 0,
        "2023": 0,
        "2024": 0,
        "2025": 0,
    }
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert the "history" column from a JSON string to a Python object
            if 'history' in row and row['history']:
                row['history'] = eval(row['history'])
                row["resolution_time"] = find_resolution_time(row["history"])
                row["time_elapsed"] = None
                if row["resolution_time"]:
                    row["time_elapsed"] = time_difference(row["creation_time"], row["resolution_time"])
                row["creation_month"] = get_month_year(row["creation_time"])
            if row["resolution"].lower() == "duplicate": continue
            for year in total_per_year:
                if row["creation_time"].startswith(year):
                    total_per_year[year] += 1
                    break
            data.append(row)
    print(total_per_year)
    return data

def get_bugs_closed_per_month(data):
    bugs_closed = {}
    avg_time = {}
    bugs_opened = {}
    total = 0
    for bug in data:
        total += 1
        month_year = bug["creation_month"]
        if month_year == "May 2025": continue
        # if month_year == "April 2025": continue
        # if month_year == "March 2025": continue
        bugs_opened.setdefault(month_year, 0)
        bugs_opened[month_year] += 1
        if bug["time_elapsed"]:# and bug["time_elapsed"] < 90:
            bugs_closed.setdefault(month_year, 0)
            bugs_closed[month_year] += 1

            avg_time.setdefault(month_year, 0)
            avg_time[month_year] += bug["time_elapsed"]

    for month_year in avg_time:
        avg_time[month_year] = avg_time[month_year] / bugs_closed[month_year]

    return {
        "bugs_closed": bugs_closed,
        "avg_time": avg_time,
        "bugs_opened": bugs_opened
    }

"""
Run this query to get the required data: https://sql.telemetry.mozilla.org/queries/108063/source
"""

fpath = "/home/sparky/Downloads/Copy_of_(#68911)_perf-alert_bugs_2025_05_15.csv"
fpath = "/home/sparky/Downloads/jan_2024_now_perf_alert_bugs.csv"
fpath = "/home/sparky/Downloads/jan_2023_now_perf_alert_bugs.csv"
fpath = "/home/sparky/Downloads/jan_2022_now_perf_alert_bugs.csv"
fpath = "/home/sparky/Downloads/jan_2020_now_perf_alert_bugs.csv"

data = read_csv_as_dicts_with_json_history(
    fpath
)

results = get_bugs_closed_per_month(data)

import numpy as np
from matplotlib import pyplot as plt

def parse_month_year(label):
    return datetime.strptime(label, "%B %Y")

# Get sorted list of months
months = sorted(results['bugs_closed'].keys(), key=parse_month_year)

# Prepare data for plotting
bugs_closed = [results['bugs_closed'][month] for month in months]
bugs_opened = [results['bugs_opened'][month] for month in months]
avg_time = [results['avg_time'][month] for month in months]

# Compute 3-month moving average of avg_time
window_size = 3
avg_time_array = np.array(avg_time)
moving_avg = np.convolve(avg_time_array, np.ones(window_size)/window_size, mode='valid')

# Adjust x-values for moving average
ma_months = months[window_size - 1:]

avg_by_year = {}
for month, value in results['avg_time'].items():
    year = month.split()[-1]
    avg_by_year.setdefault(year, []).append(value)

# Compute per-year averages
yearly_avgs = {year: np.mean(times) for year, times in avg_by_year.items()}

# Get month ranges per year for line spans
month_indices = {m: i for i, m in enumerate(months)}
year_ranges = {}
for m in months:
    y = m.split()[-1]
    year_ranges.setdefault(y, [None, None])
    idx = month_indices[m]
    if year_ranges[y][0] is None or idx < year_ranges[y][0]:
        year_ranges[y][0] = idx
    if year_ranges[y][1] is None or idx > year_ranges[y][1]:
        year_ranges[y][1] = idx

# Plotting
fig, ax1 = plt.subplots(figsize=(12, 6))

# Left y-axis for bugs closed
ax1.plot(months, bugs_closed, 'b-', marker='o', label='Bugs Closed')
ax1.plot(months, bugs_opened, 'g-', marker='^', label='Bugs Opened')
ax1.set_xlabel('Month')
ax1.set_ylabel('Bugs Closed', color='b')
ax1.tick_params(axis='y', labelcolor='b')
plt.xticks(rotation=45)

# Right y-axis for avg time
ax2 = ax1.twinx()
# ax2.plot(months, avg_time, 'r--', marker='s', label='Avg Time (days)')
ax2.plot(ma_months, moving_avg, 'r', linewidth=2, label='3-Month Moving Average Time to Close')

for year, avg_val in yearly_avgs.items():
    start_idx, end_idx = year_ranges[year]
    ax2.hlines(y=avg_val, xmin=months[start_idx], xmax=months[end_idx],
               colors='purple', linewidth=2,
               label=f'Yearly Average Time to Close' if year == list(yearly_avgs.keys())[0] else None)  # avoid duplicate legend

ax2.set_ylabel('Avg Time to Close (days)', color='r')
ax2.tick_params(axis='y', labelcolor='r')

ax1.set_xlim(left=0)
ax1.set_ylim(bottom=0)
ax2.set_xlim(left=0)
ax2.set_ylim(bottom=0)

# Add title and grid
plt.title('Monthly Bugs Closed and Average Time to Close')
ax1.grid(True)

ax1.legend()
ax2.legend()
# plt.tight_layout()
plt.show()