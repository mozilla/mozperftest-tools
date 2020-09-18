#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import collections
import csv
import datetime
import git
import json
import urllib
import numpy as np
import pathlib
from redo import retry
import requests
import statistics
import tempfile

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen


RETRY_SLEEP = 10
AD_QUERY = {
    "from":"task",
    "where":{"and":[
        {"in":{"repo.branch.name":["mozilla-central"]}},
        {"regex":{"run.name":".*fenix.*"}},
        {"regex":{"run.name":".*perftest.*"}}
    ]},
    "select":["task.artifacts", "action.start_time", "task.id"],
    "limit":100000
}

DEFAULT_TEST_NAME = "view"


def csv_generation_parser():
    """Parser for the CSV generation script."""
    parser = argparse.ArgumentParser("Run this tool to build CSVs containing Fenix data from some tasks " +
                                     "running with the multi-commit paradigm in mozilla-central " +
                                     "(must have perfherder data).")
    parser.add_argument("-t", "--test-name", type=str, default=DEFAULT_TEST_NAME,
                        help="The name of the test to get data from (must exist in the task name). " +
                        "Defaults to `view`. To get view data before Jul. 31, 2020, use `applink`.")
    parser.add_argument("-d", "--device", type=str, choices=["p2", "g5"], default="p2",
                        help="Device to get data from.")
    parser.add_argument("-c", "--cache-path", type=str, default=None,
                        help="Path to a cache for perfherder artifacts (so you don't re-download them). " +
                        "Disabled by default.")
    parser.add_argument("-r", "--fenix-repo", type=str, required=True,
                        help="Path to a local Fenix github repo.")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Path to the output directory. Defaults to current working directory.")
    parser.add_argument("--try", action="store_true", dest="try_data", default=False,
                        help="Include data from the try server.")
    parser.add_argument("--replicates", action="store_true", default=False,
                        help="Gather the replicates instead of the medians.")
    parser.add_argument("--median-per-day", action="store_true", default=False,
                        help="Returns a single result per day - the median - instead of per commit runs")
    return parser


def query_activedata(query_json):
    """Used to run queries on active data."""
    active_data_url = "http://activedata.allizom.org/query"

    req = urllib.request.Request(active_data_url)
    req.add_header("Content-Type", "application/json")
    jsondata = json.dumps(query_json)

    jsondataasbytes = jsondata.encode("utf-8")
    req.add_header("Content-Length", len(jsondataasbytes))

    print("Querying Active-data...")
    response = urllib.request.urlopen(req, jsondataasbytes)
    print("Status:" + str(response.getcode()))

    data = json.loads(response.read().decode("utf8").replace("'", '"'))["data"]
    return data



def download_file(url, target, retry_sleep=RETRY_SLEEP, attempts=3):
    """Downloads a file, given an URL in the target path.

    The function will attempt several times on failures.
    """

    def _download_file(url, target):
        req = requests.get(url, stream=True, timeout=30)
        target_dir = target.parent.resolve()
        if str(target_dir) != "":
            target_dir.mkdir(exist_ok=True)

        with target.open("wb") as f:
            for chunk in req.iter_content(chunk_size=1024):
                if not chunk:
                    continue
                f.write(chunk)
                f.flush()
        return target

    return retry(
        _download_file,
        args=(url, target),
        attempts=attempts,
        sleeptime=retry_sleep,
        jitter=0,
    )


def build_csv(
        fenix_repo,
        test_name=DEFAULT_TEST_NAME,
        device_name="p2",
        output=None,
        cache_path=None,
        try_data=False,
        medians=False,
        median_per_day=False
    ):
    """Generates a CSV file containing per-commit fenix data
    for a given test name.
    """
    if not medians and median_per_day:
        raise NotImplementedError("Please specify either --replicates or --median-per-day. I didn't know\n" +
                                  "how these would work together so I didn't implement it.")

    if cache_path:
        cache_path = pathlib.Path(cache_path)
        cache_path.mkdir(parents=True, exist_ok=True)
    else:
        cache_path = tempfile.mkdtemp()

    if output:
        output = pathlib.Path(output)
        output.mkdir(parents=True, exist_ok=True)
    else:
        output = pathlib.Path(".")

    # Initialize the git directory now before the long steps below
    fenix = git.Repo(fenix_repo)

    print(f"Generating data for {test_name} on the {device_name} device...")

    ## Get the AD data
    AD_QUERY["where"]["and"].extend([
        {"regex": {"run.name": ".*%s.*" % test_name}},
        {"regex": {"run.name": ".*-%s-.*" % device_name}}
    ])
    if try_data:
        AD_QUERY["where"]["and"][0]["in"]["repo.branch.name"].append("try")
    data = query_activedata(AD_QUERY)

    allph = []
    for c, artifacts in enumerate(data["task.artifacts"]):
        if not artifacts: continue

        for artifact in artifacts:
            if not artifact: continue
            if not isinstance(artifact, dict): continue

            ph = artifact["url"].split("/")[-1]
            if "perfherder" not in ph or ph.startswith("perfherder"): continue

            allph.append(
                (artifact["url"], ph, ph.split("-")[0], data["task.id"][c])
            )

    ## Download the perfherder data and get its commit date
    nallph = []
    for url, file, rev, taskid in allph:
        file = f"{taskid}-{test_name}-{device_name}-{file}"
        fp = pathlib.Path(cache_path, file)
        if not fp.exists():
            print(f"Downloading to {fp}" )
            download_file(url, fp)
        with fp.open() as f:
            phd = json.load(f)

        # sanity checks
        if ("suites" not in phd or
            len(phd["suites"]) == 0 or
            "value" not in phd["suites"][0]):
            print("Bad data, skipping...")
            continue

        try:
            commitdate = fenix.commit(rev).committed_date
            vals = phd["suites"][0].get("subtests",[{}])[0].get("replicates", [])
            if medians:
                vals = [phd["suites"][0]["value"]]
            for val in vals:
                nallph.append((commitdate, val, rev))
        except ValueError:
            # Some commits don't exist which is really weird - I don't
            # understand how there's a build for them when we can't find them
            # in the fenix repo.
            print("Failed to find an actual commit for %s" % rev)

    # Sort the data by time
    allphs = sorted(nallph, key=lambda x: x[0])

    if median_per_day:
        allphs = transform_to_median_per_day(allphs)

    ## Store as a CSV
    csvfile_human_readable = pathlib.Path(output, f"{test_name}-{device_name}.csv")
    csvfile_raw = pathlib.Path(output, f"{test_name}-{device_name}-raw.csv")
    write_csv(csvfile_human_readable, optimize_for_human_readability(allphs))
    write_csv(csvfile_raw, allphs)
    print(f"Finished generation. Data contained in {str(csvfile_human_readable)} & {str(csvfile_raw)}")

    try:
        from matplotlib import pyplot as plt
        plot_allphs = optimize_for_plotting(allphs)
        plt.figure()
        plt.plot_date([v[0] for v in plot_allphs], [v[1] for v in plot_allphs])
        plt.show()
    except ImportError:
        print("Skipping print stage, cannot find matplotlib")
        return

def transform_to_median_per_day(data):
    date_to_iterations = collections.defaultdict(list)
    for row in data:
        dt = datetime.datetime.fromtimestamp(row[0])
        ymd = datetime.datetime(dt.year, dt.month, dt.day)
        date_to_iterations[ymd].append(row[1])

    out_data = []
    for i, (date, times) in enumerate(date_to_iterations.items()):
        transformed_row = [date.timestamp(), statistics.median(times), 'N/A']
        out_data.append(transformed_row)
    return out_data

def write_csv(csvfile, data):
    with csvfile.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["times", "data", "revision"])
        writer.writerows(data)

def optimize_for_human_readability(data):
    def transform_row(row):
        dt = datetime.datetime.fromtimestamp(row[0])
        date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        rounded_timestamp = round(row[1])
        abbrev_commit = row[2][:9]
        return [date_str, rounded_timestamp, abbrev_commit]
    return [transform_row(list(row)) for row in data]

def optimize_for_plotting(data):
    import matplotlib.dates
    def transform_row(row):
        matplot_date = matplotlib.dates.epoch2num(row[0])
        return [matplot_date] + row[1:]
    return [transform_row(list(row)) for row in data]

if __name__=="__main__":
    args = csv_generation_parser().parse_args()
    build_csv(
        args.fenix_repo,
        test_name=args.test_name,
        device_name=args.device,
        output=args.output,
        cache_path=args.cache_path,
        try_data=args.try_data,
        medians=not args.replicates,
        median_per_day=args.median_per_day
    )
