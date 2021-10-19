import argparse
import numpy as np
import os
import pathlib
import json
import shutil
import yaml

from sys import stdout
from time import sleep

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

from artifactdownloader.artifact_downloader import artifact_downloader
from artifactdownloader.task_processor import get_task_data_paths

from perftestnotebook.perftestnotebook import PerftestNotebook

from variance_analysis import run_variance_analysis


TASK_IDS = (
    "https://firefox-ci-tc.services.mozilla.com/api/index/v1/tasks/"
    + "gecko.v2.{}.revision.{}.taskgraph"
)

TASK_INFO = "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/{}"


def variance_analysis_parser():
    parser = argparse.ArgumentParser(
        "This tool can download artifact data from a group of "
        + "taskcluster tasks. It then extracts the data, suffixes it with "
        + "a number and then stores it in an output directory."
    )

    # Artifact downloader arguments
    parser.add_argument(
        "--base-revision",
        type=str,
        required=True,
        help="The base revision to compare a new revision to.",
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default="autoland",
        help="Branch to search for the base revision.",
    )
    parser.add_argument(
        "--new-revision",
        type=str,
        required=True,
        help="The base revision to compare a new revision to.",
    )
    parser.add_argument(
        "--new-branch",
        type=str,
        default="autoland",
        help="Branch to search for the new revision.",
    )
    parser.add_argument(
        "--tests",
        type=str,
        nargs="*",
        default=["all"],
        help="A list of test names to download data from. Defaults to all.",
    )
    parser.add_argument(
        "--platform",
        "--base-platform",
        type=str,
        required=True,
        dest="platform",
        help="Platform to return results for.",
    )
    parser.add_argument(
        "--new-platform",
        type=str,
        default=None,
        help="Platform to return results for in the new revision.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="If set, the downloaded task group data will be deleted before "
        + "it gets re-downloaded.",
    )
    parser.add_argument(
        "--search-crons",
        action="store_true",
        default=False,
        help="If set, we will search for the tasks within the cron jobs as well. ",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        default=False,
        help="If set, we won't try to download artifacts again and we'll "
        + "try using what already exists in the output folder.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getcwd(),
        help="This is where the data will be saved. Defaults to CWD. ",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="A prefix to prepend onto the output data/files.",
    )

    # Perftest Notebook arguments
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="A config to use in the perftest-notebook data standardization step.",
    )
    parser.add_argument(
        "--sort-files",
        action="store_true",
        default=False,
        help="Sort files in the perftest notebook.",
    )

    return parser


def get_json(url, params=None):
    if params is not None:
        url += "?" + urlencode(params)

    r = urlopen(url).read().decode("utf-8")

    return json.loads(r)


def find_task_group_id(revision, branch, search_crons=False):
    # Find the task IDs from this revision first
    task_ids_url = TASK_IDS.format(branch, revision)

    print("Downloading task ids from: %s" % task_ids_url)
    task_ids_data = get_json(task_ids_url)
    if "tasks" not in task_ids_data or len(task_ids_data["tasks"]) == 0:
        raise Exception("Cannot find any task IDs for %s!" % revision)

    task_group_ids = []
    for task in task_ids_data["tasks"]:
        # Only find the task group ID for the decision task if we
        # don't need to search for cron tasks
        if not search_crons and not task["namespace"].endswith("decision"):
            continue
        task_group_url = TASK_INFO.format(task["taskId"])
        print("Downloading task group id from: %s" % task_group_url)
        task_info = get_json(task_group_url)
        task_group_ids.append(task_info["taskGroupId"])

    return task_group_ids


def main():
    args = variance_analysis_parser().parse_args()
    overwrite = args.overwrite
    prefix = args.prefix
    tests = args.tests

    output_dir = pathlib.Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    config = None
    with pathlib.Path(args.config).open() as f:
        config = yaml.safe_load(f)

    # Get the task group IDs for the revisions
    base_revision_ids = find_task_group_id(
        args.base_revision, args.base_branch, search_crons=args.search_crons
    )
    new_revision_ids = find_task_group_id(
        args.new_revision, args.new_branch, search_crons=args.search_crons
    )

    base_task_dirs = [pathlib.Path(output_dir, revid) for revid in base_revision_ids]
    new_task_dirs = [pathlib.Path(output_dir, revid) for revid in new_revision_ids]
    if overwrite:
        for task_dir in base_task_dirs + new_task_dirs:
            if task_dir.exists():
                print("Removing existing task group folder: %s" % str(task_dir))
                shutil.rmtree(str(task_dir))

    def _search_for_paths(rev_ids):
        found_paths = []
        for rev_id in rev_ids:
            if found_paths:
                break
            # Get the paths to the directory holding the artifacts
            found_paths = list(
                get_task_data_paths(
                    rev_id, str(output_dir), artifact="perfherder-data"
                ).values()
            )
        return found_paths

    # Setup the perftest notebook
    custom_transform = config.get("custom_transform", None)
    config["file_groups"] = {}
    file_group = {
        "task_group_id": None,
        "path": None,
        "artifact": "perfherder",
        "run_number": None,
    }

    # Download the artifacts for the base revision
    base_results = []
    for base_revision_id in base_revision_ids:
        if not args.skip_download:
            print(tests)
            artifact_downloader(
                base_revision_id,
                output_dir=str(output_dir),
                test_suites=tests,
                platform=args.platform,
                artifact_to_get=["perfherder-data"],
                unzip_artifact=False,
                download_failures=True,
                ingest_continue=False,
            )

        # Standardize the data
        file_group["task_group_id"] = base_revision_id
        file_group["path"] = str(pathlib.Path(output_dir).resolve())

        config["file_groups"] = {"new": file_group}
        config["output"] = str(
            pathlib.Path(output_dir, f"{prefix}base-ptnb-data-{base_revision_id}.json")
        )

        ptnb = PerftestNotebook(
            {"new": file_group},
            config,
            custom_transform=custom_transform,
            sort_files=args.sort_files,
        )
        base_results.append(ptnb.process(True))

    # Download the artifacts for the new revision
    new_results = []
    for new_revision_id in new_revision_ids:
        if not args.skip_download:
            artifact_downloader(
                new_revision_id,
                output_dir=str(output_dir),
                test_suites=tests,
                platform=args.new_platform or args.platform,
                artifact_to_get=["perfherder-data"],
                unzip_artifact=False,
                download_failures=True,
                ingest_continue=False,
            )

        # Standardize the data
        file_group["task_group_id"] = new_revision_id
        file_group["path"] = str(pathlib.Path(output_dir).resolve())

        config["file_groups"] = {"base": file_group}
        config["output"] = str(
            pathlib.Path(output_dir, f"{prefix}new-ptnb-data-{new_revision_id}.json")
        )

        ptnb = PerftestNotebook(
            {"base": file_group},
            config,
            custom_transform=custom_transform,
            sort_files=args.sort_files,
        )
        new_results.append(ptnb.process(True))

    # Now we have all of the perfherder-data requested and it's been standardized.
    # Combine all the standardized data within each `new`/`base` folders into a single
    # file. This handles gathering tasks from crons.
    # new_/base_results contain formatted JSON data and they all need to be within a single JSON
    results = {"base": [], "new": []}
    inds = {"base": {}, "new": {}}
    counts = {"base": 0, "new": 0}
    for blob in new_results + base_results:
        for res in blob:
            grouping = res["name"]
            subtest = res["subtest"]
            if subtest not in inds[grouping]:
                inds[grouping][subtest] = counts[grouping]
                results[grouping].append(res)
                counts[grouping] += 1
                continue

            existing_res = results[grouping][inds[grouping][subtest]]
            existing_res["data"].extend(res["data"])
            # The xaxis slightly loses its meaning with this change
            existing_res["xaxis"].extend(
                list(np.asarray(res["xaxis"]) + existing_res["xaxis"][-1])
            )

    # Analyze the data
    run_variance_analysis(results["base"] + results["new"], tests, args.platform)

    return task_dir


if __name__ == "__main__":
    main()
