# moz-current-tests

This code can be used to determine where all tests are running, what tests are running on which platform or what platforms are running which tests. It is produced from a given `full-task-graph.json` artifact.

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
