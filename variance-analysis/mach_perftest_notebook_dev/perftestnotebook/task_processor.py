import glob
import json
import os
import re

TESTING = 0
SILENT = False


def log(msg):
    # Output message if we are not running on silent mode
    global SILENT
    if not SILENT:
        print(msg)


def sorted_nicely(data):
    """
    Sort the given iterable in the way that humans expect.
    """
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split("([0-9]+)", key)]
    return sorted(data, key=alphanum_key)


def get_task_data_paths(
    task_group_id,
    path,
    run_number=None,
    artifact="",
    artifact_dir="",
    suite_matcher="",
    silent=False,
):
    """
    Opens a folder for a task group and returns the files
    contined within it.
    """
    global SILENT
    SILENT = silent

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
                max_num = run_num
        os.chdir(curr_dir)
        run_number = max_num
        log("No run number supplied. Using the latest one, run number %s" % run_number)

    run_dir = os.path.join(task_dir, str(run_number))
    all_suites = [
        f for f in os.listdir(run_dir) if os.path.isdir(os.path.join(run_dir, f))
    ]

    # Find all the data for this task group
    for suite in all_suites:
        if suite_matcher and suite_matcher not in suite:
            continue

        suite_dir = os.path.join(run_dir, suite)

        # Get the suite's data directory
        if not artifact_dir:
            artifact_dir = artifact
        all_dirs = [
            f
            for f in os.listdir(suite_dir)
            if os.path.isdir(os.path.join(suite_dir, f))
        ]
        suite_data_dir = None
        for d in all_dirs:
            if artifact_dir in d or (not artifact_dir and d.endswith("_data")):
                suite_data_dir = os.path.join(suite_dir, d)
                break

        if not suite_data_dir:
            log("Cannot find data directory in %s, skipping" % suite_dir)
            continue

        # Now find all data files and order them
        all_files = glob.glob(os.path.join(suite_data_dir, "**/*"), recursive=True)

        all_files = sorted_nicely(
            [
                file
                for file in all_files
                if artifact and artifact in os.path.split(file)[-1]
            ]
        )

        data[suite] = all_files

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


if __name__ == "__main__":
    if TESTING:
        data = get_task_data_paths(
            "SssyewAFQiKm40PIouxo_g",
            "/home/sparky/mozilla-source/analysis-scripts/perfunct-testing-data",
            artifact="perfherder-data",
            run_number="4",
        )
        print(json.dumps(data, indent=4))

        data = get_task_data(
            "SssyewAFQiKm40PIouxo_g",
            "/home/sparky/mozilla-source/analysis-scripts/perfunct-testing-data",
            artifact="perfherder-data",
            run_number="4",
        )
