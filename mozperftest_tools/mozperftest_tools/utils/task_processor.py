# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import re
import glob
import json

TESTING = 0
SILENT = False


def log(msg):
    # Output message if we are not running on silent mode
    global SILENT
    if not SILENT:
        print(msg)


def pattern_match(name, artifacts_to_get):
    """
    Match an artifact that was requested with the name we have.
    """
    if not artifacts_to_get:
        return None
    for aname in artifacts_to_get:
        if aname in name:
            return aname
    return None


def sorted_nicely(data):
    """
    Sort the given iterable in the way that humans expect.
    """
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split("([0-9]+)", key)]
    return sorted(data, key=alphanum_key)


def match_vismets_with_videos(task_group_id, path, vismet_task_ids):
    """
    Returns a mapping from vismet task IDs to the videos.
    """
    task_dir = os.path.join(path, task_group_id)
    taskgraph_json = os.path.join(task_dir, "task-group-information.json")

    with open(taskgraph_json) as f:
        taskgraph = json.load(f)

    # First filter down to only browsertime tasks
    mapping = {task_id: None for task_id in vismet_task_ids}
    for task in taskgraph:
        task_id = task.get("status", {}).get("taskId", "")
        if task_id not in mapping:
            continue

        vismet_fetches = json.loads(task["task"]["payload"]["env"]["MOZ_FETCHES"])
        for fetch in vismet_fetches:
            if "browsertime-results" in fetch["artifact"]:
                mapping[task_id] = fetch["task"]
                break

        if all(mapping):
            break

    return mapping


def get_task_data_paths(
    task_group_id,
    path,
    run_number=None,
    artifact=[],
    artifact_dir="",
    suite_matcher="",
    silent=False,
):
    """
    Opens a folder for a task group and returns the files
    contained within it.
    """
    global SILENT
    SILENT = silent

    if type(artifact) not in (list,):
        artifact = [artifact]

    data = {}

    # Get the directory to search
    task_dir = os.path.join(path, task_group_id)
    if not os.path.exists(task_dir):
        log("Cannot open task directory: %s" % task_dir)
        return

    if run_number is None:
        curr_dir = os.getcwd()
        os.chdir(task_dir)
        dir_list = next(os.walk("."))[1]
        max_num = 0
        for subdir in dir_list:
            run_num = int(subdir)
            if run_num > max_num:
                if len(os.listdir(f"{run_num}")) > 2:
                    max_num = run_num
        os.chdir(curr_dir)
        run_number = max_num
        log("No run number supplied. Using the latest one, run number %s" % run_number)

    run_dir = os.path.join(task_dir, str(run_number))
    if not os.path.exists(run_dir):
        raise Exception(
            f"No requested tasks were found for task group ID {task_group_id}"
        )

    run_dir = os.path.join(task_dir, str(run_number))
    all_suites = [
        f for f in os.listdir(run_dir) if os.path.isdir(os.path.join(run_dir, f))
    ]

    # Find all the data for this task group
    for suite in all_suites:
        for aname in artifact:
            if suite_matcher and suite_matcher not in suite:
                continue

            suite_dir = os.path.join(run_dir, suite)

            # Get the suite's data directory
            if not artifact_dir:
                artifact_dir = aname
            all_dirs = [
                f
                for f in os.listdir(suite_dir)
                if os.path.isdir(os.path.join(suite_dir, f))
            ]
            suite_data_dir = None
            for d in all_dirs:
                if pattern_match(d, [aname]) or (
                    not artifact_dir and d.endswith("_data")
                ):
                    suite_data_dir = os.path.join(suite_dir, d)
                    break

            if not suite_data_dir:
                log("Cannot find data directory in %s, skipping" % suite_dir)
                continue

            # Now find all data files and order them
            all_files = glob.glob(os.path.join(suite_data_dir, "**/*"), recursive=True)

            all_files = [
                file
                for file in all_files
                if artifact and pattern_match(os.path.split(file)[-1], [aname])
            ]

            if suite not in data:
                data[suite] = []

            data[suite].extend(all_files)
            data[suite] = sorted_nicely(data[suite])

    return data


def get_task_data(
    task_group_id, path, run_number=None, artifact="", suite_matcher="", silent=False
):
    """
    Get the task data paths and opens the data into
    a detected file format. By default, when an unknown file
    format is encountered, the lines will be read and returned.
    """
    global SILENT
    SILENT = silent

    data = {}

    data_paths = get_task_data_paths(
        task_group_id,
        path,
        run_number=run_number,
        artifact=artifact,
        suite_matcher=suite_matcher,
        silent=silent,
    )

    for suite, paths in data_paths.items():
        data[suite] = []
        for path in paths:
            tmpdata = None
            log("Opening %s..." % path)
            if path.endswith(".json"):
                with open(path, "r") as f:
                    tmpdata = json.load(f)
            else:
                with open(path, "r") as f:
                    tmpdata = f.readlines()
            data[suite].append({"data": tmpdata, "file": path})

    return data
