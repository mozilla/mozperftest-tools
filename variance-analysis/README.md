# moz-current-tests - variance analysis

This subfolder contains a tool that can be used to analyze the variance between two CI test runs.

## Setup

The first time you run, you'll need to run
```
cd variance-analysis/mach_perftest_notebook_dev
python3 setup.py develop
cd ..
```

## Running a Variance Analysis

Here's a sample command that can be used:
```
python3 run_variance_analysis.py --base-revision 5e4047061e46c5cb86d1ef694bc206fc8f4e7d20 --new-revision 5e4047061e46c5cb86d1ef694bc206fc8f4e7d20 --base-branch autoland --new-branch autoland --tests cnn --platform linux --output testing --config ptnb-config-linux-new.yml --search-crons
```

Only one platform may be specified at a time, but multiple tests are ok. The tests can be specified as exact matches or a substring of the test (e.g. cnn). The config can be used to specify the Transformer to use on the data - all of fields get replaced.

The base revision should be a CI run without changes and the new revision should point to the CI run with changes.

Run `python3 run_variance_analysis.py --help` for more help and options.

At the end of the run, you will see a list of the subtests that were analyzed and you will also see a table like this output with information about the variance:
```
linux - warm total: X/18
Average noise diff: ...
Significance of the average: ...
Number of tests with lower noise: ...
Number of tests with higher noise: ...
Averager decrease in noise for lower: ...
Average increase in noise for higher: ...

The Average noise diff gives a ratio between the new and the base grouping. A ratio greater than 1 implies that the noise is larger in new

linux - cold total: Y/18
Average noise diff: ...
Significance of the average:...
Number of tests with lower noise: ...
Number of tests with higher noise: ...
Averager decrease in noise for lower: ...
Average increase in noise for higher: ...

The Average noise diff gives a ratio between the new and the base grouping. A ratio greater than 1 implies that the noise is larger in new

```
