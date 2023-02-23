# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import json
import os
import zipfile
import requests
import shutil
import threading
import time
import glob

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

NAME_SPLITTER = "+-+"

# Use this program to dowwnload, extract, and distribute artifact
# files that are to be used for the analyses.

# Use just the groupID, it absoutely needs to be given. With that, get the task details
# for the entire group, and find all the tests specified with the suite, chunk, and mode
# given through the parser arguments. For each of those tests, take the taskId
# and download the artifact data chunk. Continue suffixing them, however, store
# a json for a mapping from numbers to taskID's for future reference.

# The suite should include the flavor. It makes no sense to aggregate the data from
# multiple flavors together because they don't run the same tests. This is also
# why you cannot specify more than one suite and chunk.
def artifact_downloader_parser():
    parser = argparse.ArgumentParser(
        "This tool can download artifact data from a group of "
        + "taskcluster tasks. It then extracts the data, suffixes it with "
        + "a number and then stores it in an output directory."
    )
    parser.add_argument(
        "--task-group-id",
        type=str,
        nargs=1,
        help="The group of tasks that should be parsed to find all the necessary "
        + "data to be used in this analysis. ",
    )
    parser.add_argument(
        "--test-suites-list",
        type=str,
        nargs="+",
        help="The listt of tests to look at. e.g. mochitest-browser-chrome-e10s-2."
        + " If it`s empty we assume that it means nothing, if `all` is given all suites"
        + " will be processed.",
    )
    parser.add_argument(
        "--artifact-to-get",
        type=str,
        nargs="+",
        default=["grcov"],
        help="Pattern matcher for the artifact you want to download. By default, it"
        + " is set to `grcov` to get ccov artifacts. Use `per_test_coverage` to get data"
        + " from test-coverage tasks.",
    )
    parser.add_argument(
        "--unzip-artifact",
        action="store_true",
        default=False,
        help="Set to False if you don`t want the artifact to be extracted.",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="test-linux64-ccov",
        help="Platform to obtain data from.",
    )
    parser.add_argument(
        "--download-failures",
        action="store_true",
        default=False,
        help="Set this flag to download data from failed tasks.",
    )
    parser.add_argument(
        "--ingest-continue",
        action="store_true",
        default=False,
        help="Continues from the same run it was doing before.",
    )
    parser.add_argument(
        "--output",
        type=str,
        nargs=1,
        help="This is the directory where all the download, extracted, and suffixed "
        + "data will reside.",
    )
    return parser


# Used to limit the number of concurrent data requests
START_TIME = time.time()
MAX_REQUESTS = 5
CURR_REQS = 0
RETRY = 5
TOTAL_TASKS = 0
CURR_TASK = 0
FAILED = []
ALL_TASKS = []
TC_PREFIX = "https://firefox-ci-tc.services.mozilla.com/api/queue/"

SECONDARYMETHOD = False
TC_PREFIX2 = "https://firefoxci.taskcluster-artifacts.net/"


def log(msg):
    global CURR_TASK
    global TOTAL_TASKS
    elapsed_time = time.time() - START_TIME
    val = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    pc = round((CURR_TASK / TOTAL_TASKS) * 100, 1) if TOTAL_TASKS else 0
    print(
        "[%s][INFO] %s/%s %s -  %s"
        % (val, str(CURR_TASK + 1), str(TOTAL_TASKS), pc, msg)
    )


def warning(msg):
    global CURR_TASK
    global TOTAL_TASKS
    elapsed_time = time.time() - start_time
    val = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    pc = round((CURR_TASK / TOTAL_TASKS) * 100, 1) if TOTAL_TASKS else 0
    print(
        "[%s][WARNING] %s/%s %s -  %s"
        % (val, str(CURR_TASK + 1), str(TOTAL_TASKS), pc, msg)
    )


def get_json(url, params=None):
    if params is not None:
        url += "?" + urlencode(params)

    r = urlopen(url).read().decode("utf-8")

    return json.loads(r)


def get_task_details(task_id):
    task_details = get_json(TC_PREFIX + "v1/task/" + task_id)
    return task_details


def get_task_artifacts(task_id):
    artifacts = get_json(TC_PREFIX + "v1/task/" + task_id + "/artifacts")
    return artifacts["artifacts"]


def get_tasks_in_group(group_id):
    reply = get_json(
        TC_PREFIX + "v1/task-group/" + group_id + "/list", {"limit": "200"}
    )
    tasks = reply["tasks"]
    while "continuationToken" in reply:
        reply = get_json(
            TC_PREFIX + "v1/task-group/" + group_id + "/list",
            {"limit": "200", "continuationToken": reply["continuationToken"]},
        )
        tasks += reply["tasks"]
    return tasks


def download_artifact(task_id, artifact, output_dir):
    global FAILED

    fname = os.path.join(output_dir, task_id + NAME_SPLITTER + os.path.basename(artifact["name"]))
    log("Downloading " + artifact["name"] + " to: " + fname)
    if os.path.exists(fname):
        log("File already exists.")
        return fname

    tries = 0
    if not SECONDARYMETHOD:
        url_data = TC_PREFIX + "v1/task/" + task_id + "/artifacts/" + artifact["name"]
    else:
        url_data = TC_PREFIX2 + task_id + "/0/" + artifact["name"]

    while tries < RETRY:
        try:
            # Make the actual request
            request = requests.get(url_data, timeout=60, stream=True)

            # Open the output file and make sure we write in binary mode
            with open(fname, "wb") as fh:
                # Walk through the request response in chunks of 1024 * 1024 bytes, so 1MiB
                for chunk in request.iter_content(1024 * 1024):
                    # Write the chunk to the file
                    fh.write(chunk)
            break
        except Exception as e:
            log(
                "Failed to get data from %s: %s - %s"
                % (url_data, e.__class__.__name__, e)
            )
            if tries < RETRY:
                tries += 1
                log("Retrying %s more times..." % str(RETRY - tries))
            else:
                warning("No more retries. Failed to download %s" % url)
                FAILED.append(task_id)
                raise

    # urlretrieve(
    #     'https://queue.taskcluster.net/v1/task/' + task_id + '/artifacts/' + artifact['name'],
    #     fname
    # )
    return fname


def suite_name_from_task_name(name):
    psn = name.split("/")[-1]
    psn = "-".join(psn.split("-")[1:])
    return psn


def make_count_dir(a_path):
    os.makedirs(a_path, exist_ok=True)
    return a_path


def extract_tgz(tar_url, extract_path="."):
    import tarfile

    tar = tarfile.open(tar_url, "r")
    for item in tar:
        tar.extract(item, extract_path)
        if item.name.find(".tgz") != -1 or item.name.find(".tar") != -1:
            extract(item.name, "./" + item.name[: item.name.rfind("/")])


def unzip_file(abs_zip_path, output_dir, count=0):
    tmp_path = ""
    tmp_path = os.path.join(output_dir, str(count))
    if not os.path.exists(tmp_path):
        make_count_dir(tmp_path)
    if abs_zip_path.endswith(".zip"):
        with zipfile.ZipFile(abs_zip_path, "r") as z:
            z.extractall(tmp_path)
    else:
        task_id = os.path.split(abs_zip_path)[1].split(NAME_SPLITTER)[0]
        extract_tgz(abs_zip_path, tmp_path)
        os.rename(
            os.path.join(tmp_path, "browsertime-results"),
            os.path.join(tmp_path, task_id + NAME_SPLITTER + "browsertime-results"),
        )
    return tmp_path


def move_file(abs_filepath, output_dir, count=0):
    tmp_path = os.path.join(output_dir, str(count))
    _, fname = os.path.split(abs_filepath)
    if not os.path.exists(tmp_path):
        make_count_dir(tmp_path)
    if os.path.exists(os.path.join(tmp_path, fname)):
        return

    shutil.copyfile(abs_filepath, os.path.join(tmp_path, fname))
    return tmp_path


def artifact_downloader(
    task_group_id,
    output_dir=os.getcwd(),
    test_suites=[],
    download_failures=False,
    artifact_to_get="grcov",
    unzip_artifact=True,
    platform="test-linux64-ccov",
    ingest_continue=False,
):
    global CURR_REQS
    global CURR_TASK
    global TOTAL_TASKS
    global FAILED
    global ALL_TASKS

    head_rev = ""
    all_tasks = False
    if "all" in test_suites:
        all_tasks = True

    # For compatibility
    if type(artifact_to_get) not in (list,):
        artifact_to_get = [artifact_to_get]

    # Make the data directories
    task_dir = os.path.join(output_dir, task_group_id)

    run_number = 0
    max_num = 0
    if not os.path.exists(task_dir):
        os.makedirs(task_dir, exist_ok=True)
    else:
        # Get current run number
        curr_dir = os.getcwd()
        os.chdir(task_dir)
        dir_list = next(os.walk("."))[1]
        max_num = 0
        for subdir in dir_list:
            run_num = int(subdir)
            if run_num > max_num:
                max_num = run_num
        os.chdir(curr_dir)

    if not ingest_continue:
        run_number = max_num + 1

    output_dir = os.path.join(task_dir, str(run_number))
    os.makedirs(output_dir, exist_ok=True)

    log("Artifacts will be stored in %s" % output_dir)
    config_json_path = os.path.join(output_dir, "config.json")
    with open(config_json_path, "w") as f:
        json.dump(
            {
                "test_suites": test_suites,
                "platform": platform,
                "artifact": artifact_to_get,
                "download_failures": download_failures,
                "task_group_id": task_group_id,
            },
            f,
            indent=4,
        )

    log("Saved run configuration to %s" % config_json_path)

    task_ids = []
    log("Getting task group information...")
    tgi_path = os.path.join(task_dir, "task-group-information.json")
    if os.path.exists(tgi_path):
        with open(tgi_path, "r") as f:
            tasks = json.load(f)
    else:
        tasks = get_tasks_in_group(task_group_id)
        with open(tgi_path, "w") as f:
            json.dump(tasks, f, indent=4)
    log("Obtained")

    # Used to keep track of how many grcov files
    # we are downloading per test.
    task_counters = {}
    taskid_to_file_map = {}

    # For each task in this group
    threads = []
    TOTAL_TASKS = len(tasks)
    for task in tasks:
        download_this_task = False
        # Get the test name
        if platform not in task["task"]["metadata"]["name"]:
            continue
        test_name = suite_name_from_task_name(task["task"]["metadata"]["name"])
        log(
            "Found %s with suite-name: %s"
            % (task["task"]["metadata"]["name"], test_name)
        )

        if (
            task.get("status", {}).get("state", "") in ("failed",)
            and not download_failures
        ):
            log("Skipped failed task")
            continue
            
        # If all tests weren't asked for but this test is
        # asked for, set the flag.
        if (not all_tasks) and test_name in test_suites:
            download_this_task = True

        if all_tasks or download_this_task:
            if "GECKO_HEAD_REV" in task["task"]["payload"]["env"]:
                # Some tasks are missing this variable
                head_rev = task["task"]["payload"]["env"]["GECKO_HEAD_REV"]

            # Make directories for this task
            grcov_dir = os.path.join(output_dir, test_name)
            downloads_dir = os.path.join(os.path.join(grcov_dir, "downloads"))
            data_dir = {
                aname: os.path.join(
                    os.path.join(grcov_dir, (aname.replace(".", "")) + "_data")
                )
                for aname in artifact_to_get
            }

            if test_name not in task_counters:
                os.makedirs(grcov_dir, exist_ok=True)
                os.makedirs(downloads_dir, exist_ok=True)
                for _, p in data_dir.items():
                    os.makedirs(p, exist_ok=True)
                task_counters[test_name] = 0
            else:
                task_counters[test_name] += 1
            task_id = task["status"]["taskId"]
            ALL_TASKS.append(task_id)

            def get_artifacts(
                task_id,
                downloads_dir,
                data_dir,
                unzip_artifact,
                test_counter,
                test_name,
                artifact_to_get,
                download_failures,
                taskid_to_file_map,
            ):
                global CURR_REQS

                try:

                    def _pattern_match(name, artifacts_to_get):
                        for aname in artifacts_to_get:
                            if aname in name:
                                return aname
                        return None

                    def _check_unzip(filen):
                        return unzip_artifact and (
                            filen.endswith(".zip") or filen.endswith(".tgz")
                        )

                    files = os.listdir(downloads_dir)
                    ffound = [
                        f
                        for f in files
                        if _pattern_match(f, artifact_to_get) and task_id in f
                    ]
                    if ffound:
                        log("File already exists.")
                        CURR_REQS -= 1
                        # There should only be file found
                        filen = ffound[0]
                        aname = _pattern_match(filen, artifact_to_get)

                        if aname == "grcov" or "grcov" in aname or _check_unzip(filen):
                            unzip_file(filen, data_dir[aname], test_counter)
                        else:
                            move_file(filen, data_dir[aname], test_counter)

                        taskid_to_file_map[task_id] = os.path.join(
                            data_dir[aname], str(test_counter)
                        )

                        return filen

                    CURR_REQS += 1
                    log("Getting task artifacts for %s" % task_id)
                    artifacts = get_task_artifacts(task_id)
                    CURR_REQS -= 1

                    # Check if the artifact to get exists before checking for
                    # failures in the task
                    exists = False
                    for artifact in artifacts:
                        if _pattern_match(artifact["name"], artifact_to_get):
                            exists = True
                    if not exists:
                        log("Missing %s in %s" % (artifact_to_get, task_id))
                        CURR_REQS -= 1
                        return

                    if not download_failures:
                        log("Checking for failures on %s" % task_id)
                        failed = None
                        for artifact in artifacts:
                            if "log_error" in artifact["name"]:
                                CURR_REQS += 1
                                filen = download_artifact(
                                    task_id, artifact, downloads_dir
                                )
                                CURR_REQS -= 1
                                if os.stat(filen).st_size != 0:
                                    failed = artifact["name"]
                        if failed:
                            log("Skipping a failed test: " + failed)
                            return

                    for artifact in artifacts:
                        aname = _pattern_match(artifact["name"], artifact_to_get)
                        if aname:
                            filen = download_artifact(task_id, artifact, downloads_dir)
                            CURR_REQS -= 1

                            if aname == "grcov" or _check_unzip(filen):
                                unzip_file(filen, data_dir[aname], test_counter)
                            else:
                                move_file(filen, data_dir[aname], test_counter)
                            taskid_to_file_map[task_id] = os.path.join(
                                data_dir[aname], str(test_counter)
                            )
                            log("Finished %s for %s" % (task_id, test_name))
                except Exception as e:
                    log("Failed to get artifacts from %s: %s" % (task_id, str(e)))
                    CURR_REQS -= 1
                    return

            CURR_REQS += 1
            log(artifact_to_get)
            t = threading.Thread(
                target=get_artifacts,
                args=(
                    task_id,
                    downloads_dir,
                    data_dir,
                    unzip_artifact,
                    task_counters[test_name],
                    test_name,
                    artifact_to_get,
                    download_failures,
                    taskid_to_file_map,
                ),
            )
            t.daemon = True

            t.start()
            threads.append(t)

            start = time.time()
            while CURR_REQS >= MAX_REQUESTS and time.time() - start < 60:
                time.sleep(1)
                log("Waiting for requests to finish, currently at %s" % str(CURR_REQS))
            if time.time() - start > 60:
                CURR_REQS = 0

        CURR_TASK += 1

    for t in threads:
        t.join()

    with open(os.path.join(output_dir, "taskid_to_file_map.json"), "w") as f:
        json.dump(taskid_to_file_map, f, indent=4)

    log("Finished processing.")
    log(
        "Stats: %s PASSED, %s FAILED, %s TOTAL"
        % (str(len(ALL_TASKS) - len(FAILED)), str(len(FAILED)), str(len(ALL_TASKS)))
    )
    if FAILED:
        log(
            "Tasks the failed to have their artifact downloaded: %s"
            % "\n\t".join(FAILED)
        )

    # Return the directory where all the tasks were downloaded to
    # and split into folders.
    return output_dir, head_rev


def main():
    parser = artifact_downloader_parser()
    args = parser.parse_args()

    task_group_id = args.task_group_id[0]
    test_suites = args.test_suites_list
    artifact_to_get = args.artifact_to_get
    unzip_artifact = args.unzip_artifact
    platform = args.platform
    download_failures = args.download_failures
    ingest_continue = args.ingest_continue
    output_dir = args.output[0] if args.output is not None else os.getcwd()

    task_dir, head_rev = artifact_downloader(
        task_group_id,
        output_dir=output_dir,
        test_suites=test_suites,
        artifact_to_get=artifact_to_get,
        unzip_artifact=unzip_artifact,
        platform=platform,
        download_failures=download_failures,
        ingest_continue=ingest_continue,
    )

    return task_dir
