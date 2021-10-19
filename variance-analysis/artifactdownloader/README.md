# ArtifactDownloader

This repo contains a tool which downloads Taskcluster artifacts from a given task group ID.
Note that this is only supported in Python 3+.

## Gathering

The ArtifactDownloader (in artifact_downloader.py) works from the command-line and as an import. From the command-line the options available are:
```
$ python3 artifact_downloader.py --help
usage: This tool can download artifact data from a group of taskcluster tasks. It then extracts the data, suffixes it with a number and then stores it in an output directory.
       [-h] [--task-group-id TASK_GROUP_ID]
       [--test-suites-list TEST_SUITES_LIST [TEST_SUITES_LIST ...]]
       [--artifact-to-get ARTIFACT_TO_GET] [--unzip-artifact]
       [--platform PLATFORM] [--download-failures] [--ingest-continue]
       [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --task-group-id TASK_GROUP_ID
                        The group of tasks that should be parsed to find all
                        the necessary data to be used in this analysis.
  --test-suites-list TEST_SUITES_LIST [TEST_SUITES_LIST ...]
                        The listt of tests to look at. e.g. mochitest-browser-
                        chrome-e10s-2. If it`s empty we assume that it means
                        nothing, if `all` is given all suites will be
                        processed.
  --artifact-to-get ARTIFACT_TO_GET
                        Pattern matcher for the artifact you want to download.
                        By default, it is set to `grcov` to get ccov
                        artifacts. Use `per_test_coverage` to get data from
                        test-coverage tasks.
  --unzip-artifact      Set to False if you don`t want the artifact to be
                        extracted.
  --platform PLATFORM   Platform to obtain data from.
  --download-failures   Set this flag to download data from failed tasks.
  --ingest-continue     Continues from the same run it was doing before.
  --output OUTPUT       This is the directory where all the download,
                        extracted, and suffixed data will reside.
```

After the download is finished, a new directory will exist in the output directory named by the task group ID. The structure of the folders can be seen below (using perfherder-data as the `--artifact-to-get` setting):
```
OUTPUT_DIR:
	- TASK_GROUP_ID1:
		# The higher the number, the later it was created (i.e. [0, 1, 2] might have failed, while 3 was good)
		- RUN_NUMBER1:
			# Contains information about the task group
			- task-group-information.json
			# Contains a mapping of file name to task ID
			- taskid_to_file_map.json
			# One folder per test suite that was requested
			- TEST_SUITE1:
				# Contains all the downloaded files
				downloads:
					- TASKID_perfherder-data.json
					- ...
				# Contains the requested artifact data split by chunks/retriggers
				perfherder-data_data:
					# One folder per chunk/retrigger
					0:
						- TASKID_perfherder-data.json
					1:
						- TASKID_perfherder-data.json
			- TEST_SUITE2 ...
		- RUN_NUMBER2 ...
	- TASK_GROUP_ID2...		
```

## Processing

The `task_processor.py` file provides some handy methods to gather all the data that was downloaded since the directory structure might be difficult to handle. It returns a dict with the following format:
```
{
	"suite": [
		{
			"file": filename,
			"data": [] # Contains the data for the file
		},
		...
	],
	...
}
```

The two methods of interest in that function are `get_task_data` and `get_task_data_paths`, which return the data, or the paths to the data respectively:
```
import task_processor as tp

# Get the data
data = tp.get_task_data(
    'SssyewAFQiKm40PIouxo_g', # Task group ID
    '/home/sparky/mozilla-source/analysis-scripts/perfunct-testing-data', # Output directory (cannot contain the task group ID)
    artifact='perfherder-data', run_number='4' # Name of the artifact to get, and the run number to use for the data
)

# Get the paths to the data
data_paths = tp.get_task_data_paths(
    'SssyewAFQiKm40PIouxo_g',
    '/home/sparky/mozilla-source/analysis-scripts/perfunct-testing-data',
    artifact='perfherder-data', run_number='4'
)

```