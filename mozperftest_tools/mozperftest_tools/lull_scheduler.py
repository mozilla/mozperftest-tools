# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import json
import pathlib
import re
import requests

from datetime import datetime, timedelta, timezone
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
NEWEST_GECKO_DECISION_TASK = (
    "https://sql.telemetry.mozilla.org/api/queries/100281/"
    "results.json?api_key=6fBphrbYMV2znx0EgVfm180lBxLrkbbFb2Yq6mPd"
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
FTG_URL = (
    "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/"
    "{}/runs/0/artifacts/public/full-task-graph.json"
)
CACHE_PATH = pathlib.Path("~/.lull-schedule-cache").expanduser().resolve()

LULL_SCHEDULE_TIME_MATCHER = re.compile(r"(\d+)(w|d|h|m)")
LULL_SCHEDULE_UNITS = {"w": "weeks", "d": "days", "h": "hours", "m": "minutes"}

MAX_TIME_TO_ADD = 600  # minutes
MIN_MACHINES_AVAILABLE = 10
MACHINE_IDLE_TIME = 10  # minutes
DEFAULT_TASK_RUN_TIME = 20  # minutes
DEFAULT_TASK_FREQUENCY = 7  # days

# TODO: See if there's a way to do this dynamically, it currently
# restrics what platforms we can schedule on.
PLATFORM_TO_WORKER_TYPE = {
    "windows11-64-shippable-qr": {
        "workerType": "win11-64-2009-hw",
        "provisionerId": "releng-hardware",
    },
    "windows10-64-shippable-qr": {
        "workerType": "gecko-t-win10-64-1803-hw",
        "provisionerId": "releng-hardware",
    },
    "macosx1015-64-shippable-qr": {
        "workerType": "gecko-t-osx-1015-r8",
        "provisionerId": "releng-hardware",
    },
    "linux1804-64-shippable-qr": {
        "workerType": "gecko-t-linux-talos-1804",
        "provisionerId": "releng-hardware",
    },
    "android-hw-a55-14-0-android-aarch64-shippable-qr": {
        "workerType": "gecko-t-bitbar-gw-perf-a55",
        "provisionerId": "proj-autophone",
    },
    "android-hw-a51-11-0-aarch64-shippable-qr": {
        "workerType": "gecko-t-bitbar-gw-perf-a51",
        "provisionerId": "proj-autophone",
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


def schedule_to_timedelta(schedule):
    """Returns the time/schedule for a given task as a number of days.

    Accepted time-specifiers for the string are:
        `w` for weeks
        `d` for days
        `h` for hours
        `m` for minutes

    :param schedule str: The lull schedule of the task. Expected to have
        a format such as: 1d, 1d 1w 4h, or 2w
    :return float: The number of days (with fractional days) as a float.
    """
    return timedelta(**{
        LULL_SCHEDULE_UNITS[u]: int(val)
        for val, u in LULL_SCHEDULE_TIME_MATCHER.findall(schedule)
    }).total_seconds()/(24*60*60)


class LullScheduler:
    def __init__(
        self,
        use_cache=False,
        cache_path=CACHE_PATH,
        max_time_to_add=MAX_TIME_TO_ADD, # minutes
        min_machines_available=MIN_MACHINES_AVAILABLE,
        machine_idle_time=MACHINE_IDLE_TIME, # minutes
        default_task_run_time=DEFAULT_TASK_RUN_TIME, # minutes
        default_task_frequency=DEFAULT_TASK_FREQUENCY,  # days
        platform_to_worker_type=PLATFORM_TO_WORKER_TYPE,
    ):
        """Initialize the lull scheduler.

        :param bool use_cache: A boolean that indicates if we should use a cache
            for the full-task-graph.json file used for determining lull-scheduling
            frequency, and which tasks need to be lull-scheduled.
        :param str/Path cache_path: Path to the cache for the full-task-graph.json file.
            By default, this is `~/.lull-schedule-cache`.
        :param int max_time_to_add: The maximum amount of time (in minutes) that
            can be scheduled at a given time on a platform.
        :param int min_machines_available: The minimum number of machines that must
            be available to allow scheduling on a platform.
        :param int machine_idle_time: The amount time (in minutes) that a machine must
            be idle before considering it available for scheduling.
        :param int default_task_run_time: The default run time for any given task.
            Used when there is no information about how long a task may take (in minutes).
        :param int default_task_frequency: The default lull schedule frequency (in days)
            for a task that needs to be lull-scheduled.
        :param dict platform_to_worker_type: A mapping of platform names to the
            workerType, and provisionerId used for querying information about the
            current workload of the platforms.
        """
        self.use_cache = use_cache
        self.cache_path = cache_path
        self.max_time_to_add = max_time_to_add
        self.min_machines_available = min_machines_available
        self.machine_idle_time = machine_idle_time
        self.default_task_run_time = default_task_run_time
        self.default_task_frequency = default_task_frequency
        self.platform_to_worker_type = platform_to_worker_type

        if self.use_cache:
            self.cache_path = pathlib.Path(
                self.cache_path
            ).expanduser().resolve()
            self.cache_path.mkdir(exist_ok=True)

    def fetch_lull_schedule_tasks(self, task_id):
        """Fetches all the tasks that have a lull-schedule attribute setting.

        :param str task_id: A task ID of a decision task that should be used
            to gather the full-task-graph.json from.
        :return dict: A dictionary containing a mapping of the tasks to their
            lull-schedule (in days).
        """
        ftg_download_url = FTG_URL.format(task_id)

        cached_ftg = pathlib.Path(self.cache_path, f"{task_id}-ftg.json")
        if cached_ftg.exists() and self.use_cache:
            with cached_ftg.open() as f:
                ftg = json.load(f)
        else:
            print(f"Downloading full-task-graph.json from: {ftg_download_url}")
            ftg = fetch_data(ftg_download_url)
            if self.use_cache:
                with cached_ftg.open("w") as f:
                    json.dump(ftg, f)

        tasks = {}
        for task, task_info in ftg.items():
            extra = task_info.get("task", {}).get("extra", {})
            if "lull-schedule" in extra:
                tasks[task] = schedule_to_timedelta(extra["lull-schedule"])

        return tasks

    def fetch_all_data(self):
        """Performs all the requests required to get all data for decisions.
        
        :return tuple: A tuple containing the following (in order):
            1. Average time a task takes to run.
            2. Average time it takes for a task to run on a platform.
            3. Number of tasks currently scheduled per platform.
            4. Number of machines that are currently available to use.
            5. Last time a given task was run (days elapsed since).
        """
        # Get information for requests
        provision_ids = list(
            set([d["provisionerId"] for k, d in self.platform_to_worker_type.items()])
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
        for platform, info in self.platform_to_worker_type.items():
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
        for platform, info in self.platform_to_worker_type.items():
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
                    if minutes_since_last_active >= self.machine_idle_time:
                        machines_available += 1

                print(f"Found {machines_available} machines available for {platform}")
                if machines_available >= self.min_machines_available:
                    # Platform can have tasks scheduled. Determine how much time is available
                    # for tasks to run.
                    info["machines-available"] = machines_available
                    info["estimated-time-available"] = (
                        machines_available * avg_platform_time_data.get(
                            platform, {"CPU Minutes Spent": 45}
                        )["CPU Minutes Spent"]
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

    def _get_platform_name(self, task_name):
        """Used to determine the platform of a task.

        :param task_name str: The name of a task.
        :return str: Returns the string of the platform, or None if not found.
        """
        for platform, _ in self.platform_to_worker_type.items():
            if platform in task_name:
                return platform
        return None

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
            task_platform = self._get_platform_name(task_to_run)
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
                    f"{self.default_task_run_time} minutes."
                )
                task_runtime = {"CPU Minutes Spent": self.default_task_run_time}

            # This check will make sure we don't over-schedule above the time limit
            new_total_time = current_total_time + task_runtime["CPU Minutes Spent"]
            if new_total_time > self.max_time_to_add:
                print("Hit max time limit to schedule with this task. Not scheduling.")
                continue

            # Prevent scheduling the test when it has already run in the push
            if tasks_in_revision.get(task_to_run, None) is not None:
                print("Task has already been triggered on this push.")
                continue

            # Check to see if the task was already run within the requested frequency
            frequency = task_frequency or self.default_task_frequency
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
    # Get the newest decision task with lull-schedule info
    newest_decision_tasks = fetch_data(
        NEWEST_GECKO_DECISION_TASK
    )["query_result"]["data"]["rows"]
    newest_decision_task = newest_decision_tasks[0]

    # Branch is always mozilla-central
    branch = "mozilla-central"
    revision = newest_decision_task["revision"]
    task_id = newest_decision_task["task_id"]

    # Get the tasks that need to be lull scheduled, then run
    # the lull-scheduler
    lull_scheduler = LullScheduler()
    tasks = lull_scheduler.fetch_lull_schedule_tasks(task_id)
    tasks_selected, total_time_per_platform = lull_scheduler.run(
        revision,
        branch,
        tasks,
    )
