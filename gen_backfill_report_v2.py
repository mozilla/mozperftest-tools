# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
This script can be used to generate a report of the amount of
machine time used during all backfills between a start and end
date.
"""

import argparse
import io
import gzip
import os
import json
import re
import shutil
import signal
import tempfile
import threading
import time
import urllib

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

DEBUG = False
TOTAL_REQUESTS = 0
MAX_REQUESTS = 50
OVERRIDE = False
TREEHERDER_LINK = "https://treeherder.mozilla.org/#/jobs?repo={}&tier=1%2C2%2C3&revision={}&searchStr={}"
BACKFILL_CACHE = os.path.join(os.path.expanduser("~"), ".backfill-cache")
TMPDIR = tempfile.mkdtemp()

"""
`where` clause will be created in the script.

It will be similar to this:
	"where": {"and": [
		{"eq":{"job.type.symbol":"Bk"}},
		{"gte": {"date": STARTTIME},
		{"lt": {"date": ENDTIME},
	]}

All TIME values must follow the standards laid out in:
https://github.com/mozilla/ActiveData/blob/dev/docs/jx_time.md

"""
AD_BACKFILL_QUERY = {
    "from": "treeherder",
    "where": None,
    "select": [
        "build.revision",
        "job.details.url",
        "repo.branch.name",
        "run.taskcluster.id",
    ],
    "limit": 10000,
}


"""
This query is used to determine the owners of the backfill
request so that we can filter backfills based on owners.

To get specific tasks, this condition will be added to the
query: {"in":{"task.id": [<BACKFILL_TASK_IDS>]}},
"""
AD_BK_OWNER_QUERY = {
    "from": "task",
    "where": {
        "and": [
            {"eq": {"treeherder.symbol": "Bk"}},
            {"in": {"task.tags.name": ["action.context.clientId"]}},
        ]
    },
    "select": ["task.tags.value", "task.id"],
    "limit": 10000,
}


"""
`where` clause will be created in the script

It will be similar to this:
	"where": {"and": [
		# Make sure action.duration is positive
		{"gt":{"action.duration":0}},
		{"in": {"run.taskcluster.id": [TASKIDS]}}
	]}
"""
AD_TIME_QUERY = {
    "from": "treeherder",
    "where": None,
    "select": [
        {"name": "action.duration", "value": "action.duration"},
        # The rest of these are used to provide
        # additional information to the user.
        {"name": "build.revision", "value": "build.revision"},
        {"name": "repo.branch.name", "value": "repo.branch.name"},
        {"name": "run.key", "value": "run.key"},
        {"name": "job.type.name", "value": "job.type.name"},
        {"name": "job.type.group.symbol", "value": "job.type.group.symbol"},
        {"name": "job.type.symbol", "value": "job.type.symbol"},
    ],
    "limit": 10000,
}


def backfill_parser():
    """
    Parser for the backfill generation script.
    """
    parser = argparse.ArgumentParser(
        "This tool can be used to generate a report of how much machine time "
        + "is being consumed by backfills."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="",
        help="The start date for where to start looking for backfilled jobs. "
        "Defaults to 1 year back.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="",
        help="The end date for where to start looking for backfilled jobs.",
    )
    parser.add_argument(
        "--branches",
        type=str,
        nargs="+",
        default=["autoland"],
        help="The branch to find backfilled jobs in.",
    )
    parser.add_argument(
        "--owners",
        type=str,
        nargs="+",
        default=[],
        help="The owners to search for in backfilled tasks.",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=[],
        help="The task group symbols to search for.",
    )
    parser.add_argument(
        "--talos",
        action="store_true",
        default=False,
        help="Set this to search for talos backfilled tasks.",
    )
    parser.add_argument(
        "--raptor",
        action="store_true",
        default=False,
        help="Set this to search for raptor backfilled tasks.",
    )
    parser.add_argument(
        "--browsertime",
        action="store_true",
        default=False,
        help="Set this to search for browsertime backfilled tasks.",
    )
    parser.add_argument(
        "--awsy",
        action="store_true",
        default=False,
        help="Set this to search for AWSY backfilled tasks.",
    )
    parser.add_argument(
        "--task-name-regex",
        type=str,
        default="",
        help="A regular expression used to find a particular set of tasks (using run.key).",
    )
    parser.add_argument(
        "--additional-conditions",
        type=str,
        nargs="+",
        default=[],
        help="Additional conditions for an ActiveData `where` clause. Used when finding the "
        "backfilled task times. Expected a dict per entry in this command, i.e. "
        '{"eq": {"job.type.group.symbol": "Btime"}}',
    )
    parser.add_argument(
        "--find-long-tasks",
        action="store_true",
        default=False,
        help="Outputs all long running tasks, along with their treeherder links. "
        "A long running task is defined as one that exceeds x2 the run time of the "
        "average task.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="This will disable caching the downloaded data for future runs.",
    )
    parser.add_argument(
        "--clobber-cache",
        action="store_true",
        default=False,
        help="This will delete the current cache.",
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Print debug statements."
    )
    return parser


def debug(msg):
    """Helper function for debug prints"""
    if DEBUG:
        print(msg)


def get_artifact(url, params=None):
    """
    Gets a JSON artifact from a given URL.
    """
    if params is not None:
        url += "?" + urlencode(params)

    tmpfile = os.path.join(TMPDIR, "tmpfile.txt")
    urlretrieve(url, tmpfile)

    data = None
    try:
        with open(tmpfile, "r") as f:
            data = f.read()
    except Exception as e:
        # Sometimes the logs are gzipped and
        # I have no idea why...
        with open(tmpfile, "rb") as f:
            gzip_f = gzip.GzipFile(fileobj=f)
            data = str(gzip_f.read())

    return data


def open_artifact(path):
    """
    Opens a JSON file and returns the data.
    """
    data = ""
    with open(path, "r") as f:
        data = f.read()
    return data


def write_artifact(data, path):
    """
    Writes the given data at the given path.
    """
    with open(path, "w") as f:
        f.write(data)


def query_activedata(query_json):
    """
    Used to run queries on active data.
    """
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


def get_owner_information(owners, taskids):
    """
    Uses the given task IDs to determine the owner or
    person who created them.
    """
    filter_by_owners = {}

    AD_BK_OWNER_QUERY["where"]["and"].append(
        {"in": {"task.id": taskids}},
    )
    owner_data = query_activedata(AD_BK_OWNER_QUERY)

    for c, taskid in enumerate(owner_data["task.id"]):
        possible_owners = [o for o in owner_data["task.tags.value"][c] if o]
        if not possible_owners:
            # Missing owner information
            continue

        # There should only ever be one owner. If
        # either of the requested owners match it,
        # then we keep this task and download
        # artifacts from it.
        task_owner = possible_owners[0]
        for owner in owners:
            if owner in task_owner:
                filter_by_owners[taskid] = True
                break

    return filter_by_owners


def generate_backfill_report(
    start_date="",
    end_date="",
    task_name_regex="",
    talos=False,
    raptor=False,
    browsertime=False,
    awsy=False,
    symbols=[],
    branches=["autoland"],
    find_long_tasks=False,
    owners=[],
    additional_conditions=[],
    no_cache=False,
    clobber_cache=False,
):
    """
    This generation works as follows:
            (i):   Find all backfill tasks between the given dates.
            If no dates are given, then we look over the past year.
            If only a start date is given, then we look from then to now.
            If only an end date is given, then we look from 1 year ago up
            to the end date.

            (ii):  Using the backfill tasks that were found, download all
            the to-run-<PUSH_ID>.json files and label-to-taskid-<PUSH_ID>.json
            files.

            (iii): For each to-run file, find the tests that are
            being retriggered and their taskid. Then, obtain the sum
            of the runtime for all these taskids.
    """
    if clobber_cache and os.path.exists(BACKFILL_CACHE):
        shutil.rmtree(BACKFILL_CACHE)

    if no_cache:
        print("Not caching downloaded data")
    else:
        print("Downloaded data will be cached here: %s" % BACKFILL_CACHE)
        os.makedirs(BACKFILL_CACHE, exist_ok=True)

    conditions = [
        {"eq": {"job.type.symbol": "Bk"}},
        {"in": {"repo.branch.name": branches}},
    ]

    where_clause = {"and": conditions}

    # Setup the time range
    if end_date:
        conditions.append({"lt": {"action.start_time": {"date": str(end_date)}}})
    if start_date:
        conditions.append({"gte": {"action.start_time": {"date": str(start_date)}}})
    else:
        # Restrict to 1 year back
        print("Setting start-date as 1 year ago. This query will take some time...")
        conditions.append({"gte": {"action.start_time": {"date": "today-year"}}})

    if start_date or end_date:
        print(
            "Date specifications detected. "
            "Ensure that they follow these guidelines: "
            "https://github.com/mozilla/ActiveData/blob/dev/docs/jx_time.md"
        )

    # Query active data for the backfilled tasks
    AD_BACKFILL_QUERY["where"] = where_clause
    debug(json.dumps(AD_BACKFILL_QUERY, indent=4))
    data = query_activedata(AD_BACKFILL_QUERY)

    if "build.revision" not in data:
        print("No backfill tasks found for the given time range")
        return

    debug("Analyzing backfills performed on the revisions: %s" % data["build.revision"])

    # Find the tasks that are specific to the requested owners
    filter_by_owners = {}
    if owners:
        # Get the owners of the backfills  if needed
        print("Getting backfill task owner information...")
        filter_by_owners = get_owner_information(owners, data["run.taskcluster.id"])

    # Go through all the URL groupings and match up data from each PUSHID
    alltaskids = []
    total_groups = len(data["job.details.url"])
    matcher = re.compile(r"-([\d]+).log")

    for c, url_grouping in enumerate(data["job.details.url"]):
        if not url_grouping:
            continue
        if filter_by_owners and data["run.taskcluster.id"][c] not in filter_by_owners:
            continue

        print(
            "\nProcessing %s from %s (%s/%s)"
            % (
                data["build.revision"][c],
                data["repo.branch.name"][c],
                (c + 1),
                total_groups,
            )
        )
        push_data = {}

        # Gather groupings
        for url in url_grouping:
            if not url:
                continue
            if "live_backing" not in url:
                continue

            pushid = str(c)
            if pushid not in push_data:
                push_data[pushid] = {}

            fname = url.split("/")[-1]
            orig_fname = fname
            if "live_backing" in fname:
                fname = "live_backing"
            else:
                # We don't care about these files
                continue

            push_data[pushid][fname] = {"url": url, "data": None}
            if not no_cache:
                # Setup the cache file name
                cache_file = "%s_%s" % (data["run.taskcluster.id"][c], orig_fname)
                if not cache_file.endswith(".log"):
                    cache_file = cache_file + ".log"
                push_data[pushid][fname]["cache-file"] = os.path.join(
                    BACKFILL_CACHE, cache_file
                )

        # Setup a signal handler for simple timeouts
        def handler(signum, frame):
            raise Exception("Timed out.")

        signal.signal(signal.SIGALRM, handler)

        def download(url, storage):
            """Downloads a JSON through a thread"""
            global TOTAL_REQUESTS
            global MAX_REQUESTS
            global OVERRIDE

            while TOTAL_REQUESTS >= MAX_REQUESTS and not OVERRIDE:
                time.sleep(0.5)

            TOTAL_REQUESTS += 1
            print("Downloading %s" % url)
            try:
                # Timeout after 20 seconds
                signal.alarm(20)
                storage["data"] = get_artifact(url)
                if "cache-file" in storage:
                    write_artifact(storage["data"], storage["cache-file"])
            except Exception as e:
                print(e)
                pass
            TOTAL_REQUESTS -= 1

        # Download all the artifacts - batch them in case
        # we are looking very far back.
        threads = []
        for _, push_files in push_data.items():
            for file, file_info in push_files.items():
                if not no_cache:
                    cached = file_info["cache-file"]
                    if os.path.exists(cached):
                        file_info["data"] = open_artifact(cached)
                        continue

                t = threading.Thread(
                    target=download, args=(file_info["url"], file_info)
                )
                t.daemon = True

                t.start()
                threads.append(t)
        for t in threads:
            try:
                t.join()
            except Exception:
                pass

        # Cancel the timeout alarm
        signal.alarm(0)

        # Get all of the TASKIDs of the backfilled jobs
        taskids = []
        for pid, push_files in push_data.items():
            log = push_files["live_backing"]["data"]
            if not log:
                print("Skipping push %s, could not obtain required artifacts" % pid)
                continue

            # Get all tasks that were created in this decision task
            matcher = re.compile(r"\s+Creating task with taskId\s+(\S+)\s+for")
            matches = matcher.findall(str(log))
            if len(matches) == 0:
                print("No created tasks found...skipping")
                continue
            print("Found tasks: %s" % matches)
            taskids.extend(matches)

        alltaskids.extend(taskids)

    conditions = [
        {"gt": {"action.duration": 0}},
        {"in": {"run.taskcluster.id": alltaskids}},
    ]

    # Setup additional settings
    if talos:
        symbols.append("T")
    if raptor:
        symbols.append("Rap")
    if browsertime:
        symbols.append("Btime")
    if awsy:
        symbols.append("SY")

    if symbols:
        conditions.append({"in": {"job.type.group.symbol": symbols}})
    if task_name_regex:
        conditions.append({"regex": {"run.key": regex}})
    if additional_conditions:
        conditions.extend(additional_conditions)

    where_clause = {"and": conditions}
    AD_TIME_QUERY["where"] = where_clause
    debug(json.dumps(AD_TIME_QUERY, indent=4))
    data = query_activedata(AD_TIME_QUERY)

    if "action.duration" not in data:
        print("No backfilled tasks found matching the given criteria")
        return

    if DEBUG:
        print("\nAll times:")
        print(data["action.duration"])
        print("")

    total = 0
    for c, i in enumerate(data["action.duration"]):
        total += i
    avgtime = total / len(data["action.duration"])
    print("Average task time: %s" % avgtime)

    if find_long_tasks:
        print("Searching for tasks that are x2 this value...")
        printed = False
        for c, i in enumerate(data["action.duration"]):
            if i > avgtime * 2:
                if not printed:
                    print("Long running tasks:")
                    printed = True
                url = TREEHERDER_LINK.format(
                    data["repo.branch.name"][c],
                    data["build.revision"][c],
                    data["job.type.name"][c],
                )
                print("Test %s: %s" % (data["run.key"][c], url))
                print("    Time: %s\n" % i)

    print("Total runtime of backfilled tasks: %s hours" % (int(total) / 3600))


def main():
    global DEBUG
    args = backfill_parser().parse_args()
    DEBUG = args.debug

    report = generate_backfill_report(
        start_date=args.start_date,
        end_date=args.end_date,
        task_name_regex=args.task_name_regex,
        owners=args.owners,
        talos=args.talos,
        raptor=args.raptor,
        browsertime=args.browsertime,
        awsy=args.awsy,
        symbols=args.symbols,
        branches=args.branches,
        find_long_tasks=args.find_long_tasks,
        additional_conditions=args.additional_conditions,
        no_cache=args.no_cache,
        clobber_cache=args.clobber_cache,
    )


if __name__ == "__main__":
    main()
