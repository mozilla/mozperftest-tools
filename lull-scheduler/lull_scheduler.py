# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
import pathlib
import requests

from datetime import datetime, timezone

# This query also provides us with information on if a task
# has run within the last 3 days. If it hasn't, it won't appear here.
AVG_TASK_TIME_URL = (
    "https://sql.telemetry.mozilla.org/api/queries/96329/"
    "results.json?api_key=NuDJ1o4F5Yb1I5qWr4cn2f4SlEqTvyLJiSZR1reE"
)
AVG_PLATFORM_TIME_URL = (
    "https://sql.telemetry.mozilla.org/api/queries/96330/"
    "results.json?api_key=2brn5EaAim76yNSyIXdAULysDPj1YelGQkfz0xaR"
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

# Requires at least the name, and platform in it
TASKS_TO_RUN_FILE = "sample_live_sites.json"

MAX_TIME_TO_ADD = 600
MIN_MACHINES_AVAILABLE = 10
MACHINE_IDLE_TIME = 10

# TODO: See if there's a way to do this dynamically
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
    # Parse the input timestamp
    time_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    parsed_time = datetime.strptime(timestamp, time_format).replace(tzinfo=timezone.utc)

    # Calculate the difference in minutes
    current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
    time_difference = current_time - parsed_time
    minutes_difference = time_difference.total_seconds() / 60

    return minutes_difference


def fetch_post_data(url, data):
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()
    raise Exception(
        f"Failed to make POST request. Status code: {response.status_code}\n"
        f"POST URL: {url}\n"
        f"POST data: {data}"
    )


def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    raise Exception(
        f"Failed to fetch data from {url}. Status code: {response.status_code}"
    )


def fetch_all_data():
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

    number_tasks_scheduled = {}
    for provision_id in provision_ids:
        NUMBER_TASKS_SCHEDULED_POST_DATA["variables"]["provisionerId"] = provision_id
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

    # Print info for debugging
    result = {
        "avg_task_time_data": avg_task_time_data,
        "avg_platform_time_data": avg_platform_time_data,
        "number_tasks_scheduled": number_tasks_scheduled,
        "number_machines_available": number_machines_available,
    }
    print(json.dumps(result, indent=4))

    return (
        avg_task_time_data,
        avg_platform_time_data,
        number_tasks_scheduled,
        number_machines_available,
    )


def get_platforms_to_schedule(
    number_tasks_scheduled, number_machines_available, avg_platform_time_data
):
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
                    and worker_type_info["node"].get("pendingTasks", None) is not None
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
                # print(platform_machine)
                latest_task = platform_machine.get("node", {}).get("latestTask", {})
                if not (
                    latest_task is not None
                    and latest_task["run"] is not None
                    and latest_task["run"]["state"] is not None
                    and latest_task["run"]["state"].lower() in ("completed", "failed")
                ):
                    # Skip machines that have not completed, or failed their task
                    continue
                if not (
                    platform_machine["node"].get("quarantineUntil", None) is not None
                    and minutes_since(platform_machine["node"]["quarantineUntil"]) > 0
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


def select_tasks_to_run(
    tasks_to_run, platforms_to_schedule, avg_task_time_data, avg_platform_time_data
):
    # Determine tests to schedule given the capacity
    tasks_selected = []
    total_time_per_platform = {platform: 0 for platform in platforms_to_schedule}
    for task_to_run in tasks_to_run:
        if platforms_to_schedule.get(task_to_run["platform"], None) is None:
            continue

        task_name = task_to_run["name"]
        task_platform = task_to_run["platform"]
        current_total_time = total_time_per_platform[task_platform]

        task_runtime = avg_task_time_data.get(
            task_name, avg_platform_time_data.get(task_platform, None)
        )
        if task_runtime is None:
            print(
                f"Task has unknown runtime for platform, and task. Not scheduling: "
                f"{task_to_run}"
            )
            continue

        # This check will make sure we don't over-schedule above the time limit
        new_total_time = current_total_time + task_runtime["CPU Minutes Spent"]
        if new_total_time > MAX_TIME_TO_ADD:
            continue

        # TODO: Task can be added, but we need to check if it's already ran/running
        # in the last X days (TBD). Check that the commit we're scheduling on
        # didn't already run/schedule it as well. If it has run recently, ignore it
        # for this run. Currently using avg_task_time_data as a proxy for this since
        # it only looks at the last 3 days worth of tests. This needs to be changed
        # to provide a stronger check. The for loop for this code could be changed to
        # a while loop to allow us to schedule additional tests even if they ran
        # recently.
        if avg_task_time_data.get(task_name, None) is not None:
            print(
                f"This task has been scheduled, and ran within the last 3 days. "
                f"Ignoring it: {task_name}"
            )
            continue

        total_time_per_platform[task_platform] = new_total_time
        tasks_selected.append(task_name)

    return tasks_selected, total_time_per_platform


def main():
    # Get tasks to schedule
    tasks_to_run = None
    with pathlib.Path(TASKS_TO_RUN_FILE).open() as f:
        tasks_to_run = json.load(f)

    (
        avg_task_time_data,
        avg_platform_time_data,
        number_tasks_scheduled,
        number_machines_available,
    ) = fetch_all_data()

    platforms_to_schedule = get_platforms_to_schedule(
        number_tasks_scheduled, number_machines_available, avg_platform_time_data
    )

    print("Platforms to schedule:")
    print(json.dumps(platforms_to_schedule, indent=4))

    tasks_selected, total_time_per_platform = select_tasks_to_run(
        tasks_to_run, platforms_to_schedule, avg_task_time_data, avg_platform_time_data
    )

    print("Tasks selected to run:")
    print(json.dumps(tasks_selected, indent=4))

    print("Total CPU minutes added to platforms:")
    print(json.dumps(total_time_per_platform, indent=4))


if __name__ == "__main__":
    main()
