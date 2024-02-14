#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Used to find the associated mozilla-central commit of a
firefox-android commit.
"""

import argparse
import json
import pathlib
import re

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

TASK_INFO = "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/{}"
TASK_LINK = "https://firefox-ci-tc.services.mozilla.com/tasks/{}"

MOZHARNESS_URL_MATCHER = re.compile(r"'MOZHARNESS_URL':\s'.*/task/(.*)/artifacts.*',")

def commit_parser():
    parser = argparse.ArgumentParser(
        "This tool can be used to get the mozilla-central commit that Raptor/Browsertime "
        "is using in a particular firefox-android commit."
    )
    parser.add_argument(
        "LOG",
        type=str,
        help=(
            "The log of a browsertime task from firefox-android to parse, and determine "
            "which mozilla-central commit it's using."
        ),
    )
    return parser


def get_json(url, params=None):
    if params is not None:
        url += "?" + urlencode(params)

    r = urlopen(url).read().decode("utf-8")

    return json.loads(r)


def get_mozilla_central_commit(log_path):
    log = pathlib.Path(log_path).expanduser().resolve()
    log_contents = log.read_text()

    match = MOZHARNESS_URL_MATCHER.search(log_contents)
    if match is None:
        raise Exception("Could not find a match for a task ID in the supplied log")

    task_id = match.group(1)
    task_link_url = TASK_LINK.format(task_id)
    print("\nFound task ID:", task_id)
    print("Task URL:", task_link_url)

    task_info = get_json(TASK_INFO.format(task_id))
    print(
        "\nTreeherder Description, and Job Link:",
        task_info["metadata"]["description"] + "\n"
    )


if __name__ == "__main__":
    args = commit_parser().parse_args()
    get_mozilla_central_commit(args.LOG)
