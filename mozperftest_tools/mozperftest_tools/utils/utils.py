import json
import requests

from sys import stdout
from time import sleep

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen


TASK_IDS = (
    "https://firefox-ci-tc.services.mozilla.com/api/index/v1/tasks/"
    + "gecko.v2.{}.revision.{}.taskgraph"
)

TASK_INFO = "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/{}"

BRANCH_URLS = {"autoland": "https://hg.mozilla.org/integration/autoland"}

PUSHLOG_TMPL = "{}/json-pushes?version=2&startID={}&endID={}"

REVISION_JSON_URL = "{}/json-rev/{}"


def write_same_line(x, sleep_time=0.0001):
    stdout.write("\r%s" % str(x))
    stdout.flush()
    sleep(sleep_time)


def finish_same_line():
    stdout.write("\r  \r\n")


def get_json(url, params=None):
    if params is not None:
        url += "?" + urlencode(params)

    r = urlopen(url).read().decode("utf-8")

    return json.loads(r)


def get_revision_json(revision, branch="autoland"):
    if branch not in BRANCH_URLS:
        raise Exception("Unkown project/branch given.")
    url = REVISION_JSON_URL.format(BRANCH_URLS.get(branch), revision)
    print(f"Downloading {url}...")
    r = get_json(url)
    print(f"Finished downloading {url}")
    return r


def get_pushes(project, end_id, depth, full_response=False):
    """
    Modified version from here: 
    https://searchfox.org/mozilla-central/rev/
    4d2b1f753871ce514f9dccfc5b1b5e867f499229/taskcluster/
    gecko_taskgraph/actions/util.py#123-142
    """
    pushes = []
    print("Downloading pushes...")
    while True:
        start_id = max(end_id - depth, 0)
        pushlog_url = PUSHLOG_TMPL.format(BRANCH_URLS.get(project), start_id, end_id)
        print(f"Downloading {pushlog_url}...")
        r = requests.get(pushlog_url)
        r.raise_for_status()
        pushes = pushes + list(r.json()["pushes"].keys())
        if len(pushes) >= depth:
            break

        end_id = start_id - 1
        start_id -= depth
        if start_id < 0:
            break
    print("Finished downloading pushes")
    pushes = sorted(pushes)[-depth:]
    push_dict = {push: r.json()["pushes"][push] for push in pushes}
    return push_dict if full_response else pushes


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
