# moz-current-tests

This repository is a collection of various tools that are useful for the things we do in Performance and Performance Testing. You can find the most interesting ones documented below.

## Setup

For convenience, you can use poetry to manage dependencies and virtual environments.

When running for the first time, you will need to [install poetry](https://python-poetry.org/docs/#installation) and then run `poetry install` to create the virtual environment and install dependencies.

Then, you can simply run `poetry run python` followed by the path to the script you'd like to run. For example, `poetry run python generate_test_report.py --tests browsertime`.

You can update the dependencies by running `poetry update` and can add dependencies using `poetry add`. See the [poetry documentation](https://python-poetry.org/docs/) for more details.

## Generating a Test Report

The code in `generate_test_report.py` can be used to determine where all tests are running, what tests are running on which platform or what platforms are running which tests. It is produced from a given `full-task-graph.json` artifact.

Sample command: `python3 generate_test_report.py --tests raptor gecko --platform-breakdown --match-all-tests --ignore-no-projects`
This will print out all raptor gecko tests and where they are running broken down by platform:
```
Report Breakdown

test-android-hw-g5-7-0-arm7-api-16/opt
    raptor-tp6m-1-geckoview-e10s: mozilla-central
    raptor-tp6m-10-geckoview-e10s: mozilla-central
    raptor-tp6m-16-geckoview-cold-e10s: mozilla-central
    raptor-tp6m-2-geckoview-e10s: mozilla-central
    raptor-tp6m-3-geckoview-e10s: mozilla-central
    raptor-tp6m-4-geckoview-e10s: mozilla-central
    raptor-tp6m-5-geckoview-e10s: mozilla-central
    raptor-tp6m-6-geckoview-e10s: mozilla-central
    raptor-tp6m-7-geckoview-e10s: mozilla-central
    raptor-tp6m-8-geckoview-e10s: mozilla-central
    raptor-tp6m-9-geckoview-e10s: mozilla-central

test-android-hw-g5-7-0-arm7-api-16/pgo
    raptor-speedometer-geckoview-e10s: mozilla-beta, trunk
    raptor-tp6m-1-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-1-geckoview-e10s: mozilla-central
    raptor-tp6m-10-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-10-geckoview-e10s: mozilla-central
    raptor-tp6m-11-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-12-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-13-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-14-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-15-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-16-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-17-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-18-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-19-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-2-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-2-geckoview-e10s: mozilla-central
    raptor-tp6m-20-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-21-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-22-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-23-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-24-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-25-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-26-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-27-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-28-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-3-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-3-geckoview-e10s: mozilla-central
    raptor-tp6m-4-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-4-geckoview-e10s: mozilla-central
    raptor-tp6m-5-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-5-geckoview-e10s: mozilla-central
    raptor-tp6m-6-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-6-geckoview-e10s: mozilla-central
    raptor-tp6m-7-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-7-geckoview-e10s: mozilla-central
    raptor-tp6m-8-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-8-geckoview-e10s: mozilla-central
    raptor-tp6m-9-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-9-geckoview-e10s: mozilla-central
    raptor-unity-webgl-geckoview-e10s: mozilla-beta, mozilla-central
    raptor-youtube-playback-geckoview-e10s: mozilla-central

test-android-hw-p2-8-0-android-aarch64/opt
    raptor-speedometer-geckoview-e10s: mozilla-central
    raptor-tp6m-1-geckoview-e10s: mozilla-central
    raptor-tp6m-10-geckoview-e10s: mozilla-central
    raptor-tp6m-16-geckoview-cold-e10s: mozilla-central
    raptor-tp6m-2-geckoview-e10s: mozilla-central
    raptor-tp6m-3-geckoview-e10s: mozilla-central
    raptor-tp6m-4-geckoview-e10s: mozilla-central
    raptor-tp6m-5-geckoview-e10s: mozilla-central
    raptor-tp6m-6-geckoview-e10s: mozilla-central
    raptor-tp6m-7-geckoview-e10s: mozilla-central
    raptor-tp6m-8-geckoview-e10s: mozilla-central
    raptor-tp6m-9-geckoview-e10s: mozilla-central

test-android-hw-p2-8-0-android-aarch64/pgo
    raptor-speedometer-geckoview-e10s: mozilla-beta, trunk
    raptor-tp6m-1-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-1-geckoview-e10s: mozilla-central
    raptor-tp6m-10-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-10-geckoview-e10s: mozilla-central
    raptor-tp6m-11-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-12-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-13-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-14-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-15-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-16-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-17-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-18-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-19-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-2-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-2-geckoview-e10s: mozilla-central
    raptor-tp6m-20-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-21-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-22-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-23-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-24-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-25-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-26-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-27-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-28-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-3-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-3-geckoview-e10s: mozilla-central
    raptor-tp6m-4-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-4-geckoview-e10s: mozilla-central
    raptor-tp6m-5-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-5-geckoview-e10s: mozilla-central
    raptor-tp6m-6-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-6-geckoview-e10s: mozilla-central
    raptor-tp6m-7-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-7-geckoview-e10s: mozilla-central
    raptor-tp6m-8-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-8-geckoview-e10s: mozilla-central
    raptor-tp6m-9-geckoview-cold-e10s: mozilla-beta, trunk
    raptor-tp6m-9-geckoview-e10s: mozilla-central
    raptor-youtube-playback-geckoview-e10s: mozilla-central

test-android-hw-p2-8-0-arm7-api-16/opt
    No tests satisfying criteria

```

Run `python3 generate_test_report.py --help` for more options.


## Browsertime Side-by-Side Video Comparisons

The `generate_side_by_side.py` script can be used to generate a side-by-side comparion of two browsertime videos. This can be useful for determining if a regression/improvement is legitimate or not. It uses the similarity metric which is calculated using video histograms. See below for more information. 

```
$ python3 generate_side_by_side.py --help
usage: This tool can be used to generate a side-by-side visualization of two videos.

 When using this tool, make sure that the `--test-name` is an exact match, i.e. if you are comparing  the task `test-linux64-shippable-qr/opt-browsertime-tp6-firefox-linkedin-e10s` between two revisions, then use `browsertime-tp6-firefox-linkedin-e10s` as the suite name and `test-linux64-shippable-qr/opt` as the platform.

 The side-by-side video produced will be found in the output folder. The video on the left-hand side of the screen is the old/base video, and the video on the right-hand side of the screen is the new video.
       [-h] --base-revision BASE_REVISION [--base-branch BASE_BRANCH]
       --new-revision NEW_REVISION [--new-branch NEW_BRANCH] --test-name
       TEST_NAME --platform PLATFORM [--overwrite] [--skip-download]
       [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --base-revision BASE_REVISION
                        The base revision to compare a new revision to.
  --base-branch BASE_BRANCH
                        Branch to search for the base revision.
  --new-revision NEW_REVISION
                        The base revision to compare a new revision to.
  --new-branch NEW_BRANCH
                        Branch to search for the new revision.
  --test-name TEST_NAME
                        The name of the test task to get videos from.
  --platform PLATFORM   Platforms to return results for. Defaults to all.
  --overwrite           If set, the downloaded task group data will be deleted
                        before it gets re-downloaded.
  --skip-download       If set, we won't try to download artifacts again and
                        we'll try using what already exists in the output
                        folder.
  --output OUTPUT       This is where the data will be saved. Defaults to CWD.
                        You can include a name for the file here, otherwise it
                        will default to side-by-side.mp4.
```

## Other tools

There are other useful tools in this repo as well. For instance, the `high-value-tests` folder contains logic for determining the what tests are the most valuable given a set of alerts and also produces a minimized list of tests that could catch all alerts.


