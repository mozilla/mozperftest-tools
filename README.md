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
                        The new revision to compare a base revision to.
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

## General Side-by-Side Video Comparisons

The `generate_side_by_side_standalone.py` script can be used to generate a side-by-side comparion of any two videos (regardles of if they are browsertime or not). This comes with the ability to remove orange frames if necessary.
```
$ python3 generate_side_by_side_standalone.py --help
usage: You can use this tool to make arbitrary side-by-side videos of any combination of videos. Use --remove-orange if you are comparing browsertime videos with orange frames (note that this requires matplotlib). 
       [-h] --base-video BASE_VIDEO [--new-video NEW_VIDEO] [--remove-orange]
       [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --base-video BASE_VIDEO
                        The path to the base/before video.
  --new-video NEW_VIDEO
                        The path to the new/after video.
  --remove-orange       If set, orange frames are removed.
  --output OUTPUT       This is where the data will be saved. Defaults to CWD.
                        You can include a name for the file here, otherwise it
                        will default to side-by-side.mp4.
```


## Artifact Downloader

In [mozperftest_tools/mozperftest_tools/utils/artifact_downloader.py](https://github.com/mozilla/mozperftest-tools/blob/b3d3d0cabe8411d1c7ba56905e35bc462321e9e0/mozperftest_tools/mozperftest_tools/utils/artifact_downloader.py) you'll find a script that lets you download large amounts of data from a specific commit. It's primarily used for downloading `browsertime-videos-original.tar.gz` files, unzipping them, and organizing them in a given folder (or the current working directory) with the top-level folder being the task-group-id of the tasks downloaded Note that it can download any of the artifacts even logs which can be useful when parsed for debugging. Subsequent runs continue using that folder, but produce an integer labelled folder representing the current run (it's possible to reuse past folders).

See below for the options from this tool:
```
$ python3 mozperftest_tools/mozperftest_tools/utils/artifact_downloader.py --help
usage: This tool can download artifact data from a group of taskcluster tasks. It then extracts the data, suffixes it with a number and then stores it in an output directory.
       [-h] [--task-group-id TASK_GROUP_ID] [--test-suites-list TEST_SUITES_LIST [TEST_SUITES_LIST ...]] [--artifact-to-get ARTIFACT_TO_GET [ARTIFACT_TO_GET ...]] [--unzip-artifact]
       [--platform PLATFORM] [--download-failures] [--ingest-continue] [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --task-group-id TASK_GROUP_ID
                        The group of tasks that should be parsed to find all the necessary data to be used in this analysis.
  --test-suites-list TEST_SUITES_LIST [TEST_SUITES_LIST ...]
                        The list of tests to look at. e.g. mochitest-browser-chrome-e10s-2. If it`s empty we assume that it means nothing, if `all` is given all suites will be processed.
  --artifact-to-get ARTIFACT_TO_GET [ARTIFACT_TO_GET ...]
                        Pattern matcher for the artifact you want to download. By default, it is set to `grcov` to get ccov artifacts. Use `per_test_coverage` to get data from test-
                        coverage tasks.
  --unzip-artifact      Set to False if you don`t want the artifact to be extracted.
  --platform PLATFORM   Platform to obtain data from.
  --download-failures   Set this flag to download data from failed tasks.
  --ingest-continue     Continues from the same run it was doing before.
  --output OUTPUT       This is the directory where all the download, extracted, and suffixed data will reside.
```

It's also possible to use this within a script. For instance, [see here for how it can be used to download, and retrieve an organized list of the data you want](https://github.com/mozilla/mozperftest-tools/blob/b3d3d0cabe8411d1c7ba56905e35bc462321e9e0/mozperftest_tools/mozperftest_tools/side_by_side.py#L994-L1008). You will need to install the `mozperftest-tools` module to do that:
```
pip install mozperftest-tools
```

The tool will be found in `mozperftest_tools.utils.artifact_downloader`, along with the helper methods for data organization in `mozperftest_tools.utils.task_processor`.

To find a `task-group-id`, on Treeherder, select any task within the push you want to download from. Next, in the interface that opens at the bottom of the page, click on the ID for the `Task` in the left-most panel. For example, [this task](https://treeherder.mozilla.org/jobs?repo=mozilla-central&group_state=expanded&selectedTaskRun=AY9lVbObRn-xjRka_-f_ig.0&resultStatus=pending%2Crunning%2Csuccess%2Ctestfailed%2Cbusted%2Cexception%2Cretry%2Cusercancel&searchStr=browsertime&revision=52f516546de7ac66228e074000877d32ebf093af), has a task group id of `G-hf6KDRQiCGZsio8TvADw`. Now you can use that to compose the command for the artifacts you'd like to download. In the following example, `artifact_downloader.py` will download all tasks from that push/task-group that run on the linux platform that contain either the `browsertime-videos-original` archive, or the `perfherder-data` JSON file, and will unzip any artifacts for you - the data will be output into a folder called `test-download` in the CWD:
`python mozperftest_tools/mozperftest_tools/utils/artifact_downloader.py --task-group-id G-hf6KDRQiCGZsio8TvADw --artifact-to-get browsertime-videos-original perfherder-data --output ./test-download/ --platform test-linux1804-64-shippable-qr/opt --test-suites-list all --unzip-artifact`

For the `--platform` option, it will always need to match a platform exactly. The same is true for the `--test-suites-list` arguments (except for the special argument `all`). For instance, the task linked in the push above, has the name `test-linux1804-64-shippable-qr/opt-browsertime-tp6-essential-firefox-amazon` which has a platform of `test-linux1804-64-shippable-qr/opt`, and test suite of `browsertime-tp6-essential-firefox-amazon`.

Note that for organizing the downloaded data, there are some helper functions in [mozperftest_tools/mozperftest_tools/utils/task_processor.py](https://github.com/mozilla/mozperftest-tools/blob/b3d3d0cabe8411d1c7ba56905e35bc462321e9e0/mozperftest_tools/mozperftest_tools/utils/task_processor.py). You can also have a look at the side-by-side tool's code to see an example of this.


## Other tools

There are other useful tools in this repo as well. For instance, the `high-value-tests` folder contains logic for determining the what tests are the most valuable given a set of alerts and also produces a minimized list of tests that could catch all alerts.


