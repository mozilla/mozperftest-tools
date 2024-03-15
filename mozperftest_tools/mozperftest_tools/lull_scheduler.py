# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
import pathlib
import requests

from datetime import datetime, timezone
from mozperftest_tools.utils.utils import get_tasks_in_revisions

AVG_TASK_TIME_URL = (
    "https://sql.telemetry.mozilla.org/api/queries/96329/"
    "results.json?api_key=NuDJ1o4F5Yb1I5qWr4cn2f4SlEqTvyLJiSZR1reE"
)
AVG_PLATFORM_TIME_URL = (
    "https://sql.telemetry.mozilla.org/api/queries/96330/"
    "results.json?api_key=2brn5EaAim76yNSyIXdAULysDPj1YelGQkfz0xaR"
)
LAST_TASK_RUN_DATES = (
    "https://sql.telemetry.mozilla.org/api/queries/96922/"
    "results.json?api_key=Kt78Zk1zfzJjOiRliTxKUEsUI8c0vlrPQ2m3QVjG"
)
NUMBER_TASKS_SCHEDULED_URL = "https://firefox-ci-tc.services.mozilla.com/graphql"
NUMBER_MACHINES_AVAILABLE_URL = "https://firefox-ci-tc.services.mozilla.com/graphql"

NUMBER_TASKS_SCHEDULED_POST_DATA = {
    "operationName": "ViewWorkerTypes",
    "variables": {
        "provisionerId": "releng-hardware",
        "workerTypesConnection": {"limit": 1000},
    },
    "query": (
        "query ViewWorkerTypes($provisionerId: String!, $workerTypesConnection: "
        "PageConnection) {\n  workerTypes(provisionerId: $provisionerId, connection: "
        "$workerTypesConnection) {\n    pageInfo {\n      hasNextPage\n      "
        "hasPreviousPage\n      cursor\n      previousCursor\n      nextCursor\n      "
        "__typename\n    }\n    edges {\n      node {\n        provisionerId\n        "
        "workerType\n        stability\n        description\n        expires\n        "
        "lastDateActive\n        pendingTasks\n        __typename\n      }\n      "
        "__typename\n    }\n    __typename\n  }\n  provisioners {\n    "
        "edges {\n      node {\n        provisionerId\n        __typename\n      "
        "}\n      __typename\n    }\n    __typename\n  }\n}\n"
    ),
}

NUMBER_MACHINES_AVAILABLE_POST_DATA = {
    "operationName": "ViewWorkers",
    "variables": {
        "provisionerId": "releng-hardware",
        "workerType": "gecko-1-b-osx-1015",
        "workersConnection": {"limit": 1000},
        "quarantined": None,
        "workerState": None,
    },
    "query": (
        "query ViewWorkers($provisionerId: String!, $workerType: String!, "
        "$workersConnection: PageConnection, $quarantined: Boolean, $workerState: String) "
        "{ workers(provisionerId: $provisionerId workerType: $workerType connection: "
        "$workersConnection isQuarantined: $quarantined workerState: $workerState) "
        "{ pageInfo { hasNextPage hasPreviousPage cursor previousCursor nextCursor __typename } "
        "edges { node { workerId workerGroup latestTask { run { taskId runId started resolved "
        "state __typename } __typename } firstClaim quarantineUntil lastDateActive state "
        "capacity providerId workerPoolId __typename } __typename } __typename } "
        "workerType(provisionerId: $provisionerId, workerType: $workerType) { actions "
        "{ name description title url __typename } __typename } provisioners { edges { "
        "node { provisionerId __typename } __typename } __typename } }"
    ),
}

# A list of task names to schedule
TASKS_TO_RUN_FILE = pathlib.Path(
    pathlib.Path(__file__).parent, "sample_live_sites.json"
)

MAX_TIME_TO_ADD = 600  # minutes
MIN_MACHINES_AVAILABLE = 10
MACHINE_IDLE_TIME = 10  # minutes
DEFAULT_TASK_RUN_TIME = 20  # minutes
DEFAULT_TASK_FREQUENCY = 7  # days

# TODO: See if there's a way to do this dynamically, it currently
# restrics what platforms we can schedule on.
PLATFORM_TO_WORKER_TYPE = {
    "windows10-64-shippable-qr": {
        "workerType": "gecko-t-win10-64-1803-hw",
        "provisionerId": "releng-hardware",
    },
    "android-hw-a51-11-0-aarch64-shippable-qr": {
        "workerType": "gecko-t-bitbar-gw-perf-a51",
        "provisionerId": "proj-autophone",
    },
    "macosx1015-64-shippable-qr": {
        "workerType": "gecko-t-osx-1015-r8",
        "provisionerId": "releng-hardware",
    },
    "linux1804-64-shippable-qr": {
        "workerType": "gecko-t-linux-talos-1804",
        "provisionerId": "releng-hardware",
    },
}


def minutes_since(timestamp):
    """Used to determine the time elapsed since a machine had a task running.

    :param timestamp str: The timestamp to calculate minutes elapsed from.
    :return int: Minutes elapsed since the given timestamp.
    """
    # Parse the input timestamp
    time_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    parsed_time = datetime.strptime(timestamp, time_format).replace(tzinfo=timezone.utc)

    # Calculate the difference in minutes
    current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
    time_difference = current_time - parsed_time
    minutes_difference = time_difference.total_seconds() / 60

    return minutes_difference


def fetch_post_data(url, data):
    """Fetches post data from the FirefoxCI graphQL queries.

    Raises an exception when the data cannot be fetched.

    :param url str: The URL to fetch the post data from.
    :param data dict: The data to post to the URL.
    :return dict: Dictionary of the data obtained.
    """
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()
    raise Exception(
        f"Failed to make POST request. Status code: {response.status_code}\n"
        f"POST URL: {url}\n"
        f"POST data: {data}"
    )


def fetch_data(url):
    """Fetches JSON data from a given URL.

    Raises an exception when the data cannot be fetched.

    :param url str: The URL to fetch the data from.
    :return dict: Dictionary of the data obtained.
    """
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    raise Exception(
        f"Failed to fetch data from {url}. Status code: {response.status_code}"
    )


def get_platform_name(task_name):
    """Used to determine the platform of a task.

    :param task_name str: The name of a task.
    :return str: Returns the string of the platform, or None if not found.
    """
    for platform, _ in PLATFORM_TO_WORKER_TYPE.items():
        if platform in task_name:
            return platform
    return None


class LullScheduler:
    def fetch_all_data(self):
        # Get information for requests
        provision_ids = list(
            set([d["provisionerId"] for k, d in PLATFORM_TO_WORKER_TYPE.items()])
        )

        # Make the requests, and reformat the data into dicts
        avg_task_time_data = {}
        avg_task_time = fetch_data(AVG_TASK_TIME_URL)["query_result"]["data"]["rows"]
        for task_time in avg_task_time:
            avg_task_time_data[task_time["name"]] = task_time

        avg_platform_time_data = {}
        avg_platform_time = fetch_data(AVG_PLATFORM_TIME_URL)["query_result"]["data"][
            "rows"
        ]
        for platform_time in avg_platform_time:
            avg_platform_time_data[platform_time["platform"]] = platform_time

        last_task_run_dates_data = {}
        last_task_run_dates = fetch_data(LAST_TASK_RUN_DATES)["query_result"]["data"][
            "rows"
        ]
        for last_task_run_date in last_task_run_dates:
            last_task_run_dates_data[last_task_run_date["name"]] = last_task_run_date

        number_tasks_scheduled = {}
        for provision_id in provision_ids:
            NUMBER_TASKS_SCHEDULED_POST_DATA["variables"][
                "provisionerId"
            ] = provision_id
            number_tasks_scheduled[provision_id] = fetch_post_data(
                NUMBER_TASKS_SCHEDULED_URL, NUMBER_TASKS_SCHEDULED_POST_DATA
            )["data"]["workerTypes"]["edges"]

        number_machines_available = {}
        for platform, info in PLATFORM_TO_WORKER_TYPE.items():
            NUMBER_MACHINES_AVAILABLE_POST_DATA["variables"]["provisionerId"] = info[
                "provisionerId"
            ]
            NUMBER_MACHINES_AVAILABLE_POST_DATA["variables"]["workerType"] = info[
                "workerType"
            ]
            number_machines_available[platform] = fetch_post_data(
                NUMBER_MACHINES_AVAILABLE_URL, NUMBER_MACHINES_AVAILABLE_POST_DATA
            )["data"]["workers"]["edges"]

        return (
            avg_task_time_data,
            avg_platform_time_data,
            number_tasks_scheduled,
            number_machines_available,
            last_task_run_dates_data,
        )

    def get_platforms_to_schedule(
        self, number_tasks_scheduled, number_machines_available, avg_platform_time_data
    ):
        """Gets the platforms that can have tasks scheduled on them.

        For a platform to be selected, it must have MIN_MACHINES_AVAILABLE that satisfy
        the following conditions:
            i)   Last task was completed.
            ii)  Idle for MACHINE_IDLE_TIME minutes.
            iv)  Machine is not quarantined.
        Furthermore, the platform needs to have no pending tasks on it.

        :param number_tasks_scheduled dict: Provides the number of tasks scheduled on a
            given hardware provisioner.
        :param number_machines_available dict: Dictionary of all machines per platform
            containing information about each machine.
        :param avg_platform_time_data dict: Used to estimate the amount of CPU minutes
            we have available per platform for scheduling.
        :return dict: Dictionary containing all the platforms that can have tasks
            scheduled on them, along with information about how many CPU minutes
            they have available.
        """
        # Get number of machines available, and that satisfies the conditions:
        # i) completed task, and ii) idle for min minutes
        platforms_to_schedule = {}
        for platform, info in PLATFORM_TO_WORKER_TYPE.items():
            platform_worker_type = info["workerType"]
            for worker_type_info in number_tasks_scheduled[info["provisionerId"]]:
                if not (
                    worker_type_info["node"]["workerType"] == platform_worker_type
                    and worker_type_info["node"]["pendingTasks"] == 0
                ):
                    if (
                        worker_type_info["node"]["workerType"] == platform_worker_type
                        and worker_type_info.get("node", None) is not None
                        and worker_type_info["node"].get("pendingTasks", None)
                        is not None
                    ):
                        print(
                            f"Not scheduling on {platform} due to "
                            f"{worker_type_info['node']['pendingTasks']} pending tasks"
                        )
                    continue

                # There are no pending tasks on this platform, check to make
                # sure some time has passed since they were
                machines_available = 0
                for platform_machine in number_machines_available[platform]:
                    latest_task = platform_machine.get("node", {}).get("latestTask", {})
                    if not (
                        latest_task is not None
                        and latest_task["run"] is not None
                        and latest_task["run"]["state"] is not None
                        and latest_task["run"]["state"].lower()
                        in ("completed", "failed")
                    ):
                        # Skip machines that have not completed, or failed their task
                        continue
                    if not (
                        platform_machine["node"].get("quarantineUntil", None)
                        is not None
                        and minutes_since(platform_machine["node"]["quarantineUntil"])
                        > 0
                    ):
                        # Machine is quarantined
                        continue
                    if latest_task["run"].get("resolved", None) is None:
                        continue

                    minutes_since_last_active = minutes_since(
                        latest_task["run"]["resolved"]
                    )
                    if minutes_since_last_active >= MACHINE_IDLE_TIME:
                        machines_available += 1

                print(f"Found {machines_available} machines available for {platform}")
                if machines_available >= MIN_MACHINES_AVAILABLE:
                    # Platform can have tasks scheduled. Determine how much time is available
                    # for tasks to run.
                    info["machines-available"] = machines_available
                    info["estimated-time-available"] = (
                        machines_available
                        * avg_platform_time_data[platform]["CPU Minutes Spent"]
                    )
                    platforms_to_schedule[platform] = info

        return platforms_to_schedule

    def _task_was_scheduled_recently(self, last_task_run_date, task_frequency):
        """Determine if the test should be scheduled based on the given frequency.

        If the last known run date is unknown, we assume that it hasn't run before
        and that we should schedule. Otherwise, we check if the days elapsed since the
        last run is greater than the requested frequency.
        """
        if last_task_run_date is None:
            return False
        return float(last_task_run_date) > task_frequency

    def select_tasks_to_run(
        self,
        tasks_to_run,
        platforms_to_schedule,
        avg_task_time_data,
        avg_platform_time_data,
        tasks_in_revision,
        last_task_run_dates,
    ):
        """Select the tests to run from the given options in `tasks_to_run`.

        This method iterates over the tasks to run specified and determines which
        of them should be scheduled. It goes through the tasks in ascending order from
        highest frequency, to lowest frequency, i.e. a task with a frequency of 1 day,
        will be checked before a task with a frequency of 3 days.

        If the platform of a task is unknown (based on the PLATFORM_TO_WORKER_TYPE), then
        we won't attempt to schedule it. If a platform is not in the platforms_to_schedule,
        then all tests requested for it will also be ignored.

        The task runtime is determined based on the AVG_TASK_TIME or AVG_PLATFORM_TIME
        queries. If it can't be found with either of those, we default to DEFAULT_TASK_RUN_TIME.
        This task runtime is used to keep track of how much we schedule in a given run, and
        is currently limited to 600 minutes (or 10 CPU hours, see MAX_TIME_TO_ADD).

        Finally, we check if the number of days elapsed is greater than the frequency, and
        that the test hasn't already been triggered on the given push/revision. If these
        pass, then the test gets selected for scheduling.

        :param tasks_to_run dict: Dictionary of the name of tasks to run as
            keys, and the frequency that they should be scheduled at as the
            value.
        :param platforms_to_schedule dict: Dictionary containing the platforms we can
            schedule, along with information about how much capacity there is.
        :param avg_task_time_data dict: Dictionary containing information about
            the average length of time a task might take.
        :param avg_platform_time_data dict: Dictionary containing information about
            the average length of time a task on a platform might take.
        :param tasks_in_revision list: List of tasks that have run in the current
            push/revision.
        :param last_task_run_dates dict: Dictionary containing the task names as keys
            with the number of days since they were last run.
        :return tuple: First element is the tasks that should be run, and the second
            element contains information about how many CPU minutes were used in this
            run.
        """
        # Determine tests to schedule given the capacity
        tasks_selected = []
        total_time_per_platform = {platform: 0 for platform in platforms_to_schedule}
        for task_to_run, task_frequency in sorted(
            tasks_to_run.items(), key=lambda x: x[1]
        ):
            print(f"Attempting to schedule {task_to_run}")
            task_platform = get_platform_name(task_to_run)
            if task_platform is None:
                print("Cannot schedule as the platform is unknown.")
                continue
            if platforms_to_schedule.get(task_platform, None) is None:
                print("Cannot schedule on this platform as there is no capacity.")
                continue

            current_total_time = total_time_per_platform[task_platform]
            task_runtime = avg_task_time_data.get(
                task_to_run, avg_platform_time_data.get(task_platform, None)
            )
            if task_runtime is None:
                # This setup allows us to trigger tests that have never run
                # before or haven't run in the
                print(
                    f"Task has unknown runtime for platform, and task. Setting to default of "
                    f"{DEFAULT_TASK_RUN_TIME} minutes."
                )
                task_runtime = {"CPU Minutes Spent": DEFAULT_TASK_RUN_TIME}

            # This check will make sure we don't over-schedule above the time limit
            new_total_time = current_total_time + task_runtime["CPU Minutes Spent"]
            if new_total_time > MAX_TIME_TO_ADD:
                print("Hit max time limit to schedule with this task. Not scheduling.")
                continue

            # Prevent scheduling the test when it has already run in the push
            if tasks_in_revision.get(task_to_run, None) is not None:
                print("Task has already been triggered on this push.")
                continue

            # Check to see if the task was already run within the requested frequency
            frequency = task_frequency or DEFAULT_TASK_FREQUENCY
            if self._task_was_scheduled_recently(
                last_task_run_dates.get(task_to_run, {}).get("Days Elapsed", None),
                frequency,
            ):
                print(
                    "Test was already scheduled within the requested {frequency} days. "
                    "Not scheduling."
                )
                continue

            total_time_per_platform[task_platform] = new_total_time
            tasks_selected.append(task_to_run)

        return tasks_selected, total_time_per_platform

    def run(self, revision, branch, tasks_to_run):
        """Run the lull scheduler to select which tasks to run.

        Given a revision, branch, and a set of tasks that can be selected from,
        this will return the set of tasks that should be scheduled. The tasks
        are expected to have the format:
        {
            "task-name": 1 # Frequency in days
        }

        See select_tasks_to_run for more information on how the tasks are
        selected to run.

        :param revision str: The revision that tasks will be created on.
        :param branch str: The branch of the revision.
        :param tasks_to_run dict: Dictionary of the name of tasks to run as
            keys, and the frequency that they should be scheduled at as the
            value.
        """
        tasks_in_revision = get_tasks_in_revisions([revision], branch)
        all_task_names = {}
        for task in tasks_in_revision:
            all_task_names[task["task"]["metadata"]["name"]] = True

        (
            avg_task_time_data,
            avg_platform_time_data,
            number_tasks_scheduled,
            number_machines_available,
            last_task_run_dates,
        ) = self.fetch_all_data()

        platforms_to_schedule = self.get_platforms_to_schedule(
            number_tasks_scheduled, number_machines_available, avg_platform_time_data
        )

        print("Platforms to schedule:")
        print(json.dumps(platforms_to_schedule, indent=4))

        tasks_selected, total_time_per_platform = self.select_tasks_to_run(
            tasks_to_run,
            platforms_to_schedule,
            avg_task_time_data,
            avg_platform_time_data,
            all_task_names,
            last_task_run_dates,
        )

        print("Tasks selected to run:")
        print(json.dumps(tasks_selected, indent=4))

        print("Total CPU minutes added to platforms:")
        print(json.dumps(total_time_per_platform, indent=4))

        return tasks_selected, total_time_per_platform


if __name__ == "__main__":
    lull_scheduler = LullScheduler()

    # Get tasks to schedule, expected format is:
    # {"task-name": frequency_in_days, ...}
    tasks_to_run = None
    with pathlib.Path(TASKS_TO_RUN_FILE).open() as f:
        tasks_to_run = json.load(f)

    branch = "mozilla-central"
    revision = "8d93c10892064c983f5603645b9f6db6494fac24"
    tasks_selected, total_time_per_platform = lull_scheduler.run(
        revision,
        branch,
        tasks_to_run,
    )
