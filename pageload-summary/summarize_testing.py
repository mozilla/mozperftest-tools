#!/usr/bin/python3
import argparse
import csv
import numpy as np
import os
import pathlib

from matplotlib import pyplot as plt
from scipy.stats.mstats import gmean


def summary_parser():
    parser = argparse.ArgumentParser(
        "This tool can be used to generate a summary of the pageload numbers for a single "
        "given subtest, i.e. ContenfulSpeedIndex. We provide the summary through a geomean "
        "and you can also perform a comparison with competing browsers using "
        "`--compare-browsers`. You must provide data in the CSV format that is returned from "
        "this query: https://sql.telemetry.mozilla.org/queries/79289"
    )
    parser.add_argument(
        "data", metavar="CSV_DATA", type=str, help="The data to summarize."
    )
    parser.add_argument(
        "--compare-browsers",
        action="store_true",
        default=False,
        help="Provide a comparison between the browsers found.",
    )
    parser.add_argument(
        "--timespan",
        type=int,
        default=24,
        help="Minimum time between each data point in hours.",
    )
    parser.add_argument(
        "--platforms",
        nargs="*",
        default=[
            #     "linux64-shippable-qr",
            #     "windows10-64-shippable-qr",
            #     "macosx1015-64-shippable-qr"
        ],
        help="Platforms to summarize.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getcwd(),
        help="This is where the data will be saved in JSON format. If the "
        "path has a `.json` suffix then we'll use the part immediately "
        "before it as the file name.",
    )
    return parser


def open_csv_data(path):
    """Opens a CSV data file from a given path."""
    rows = []
    with path.open() as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_data_ind(data, fieldname):
    """Returns an index for the requested field."""
    for i, entry in enumerate(data[0]):
        if fieldname in entry:
            return i
    return None


def organize_data(data, platforms):
    """Organizes the data into a format that is easier to handle.

    Ex: data = {
        "platform1": {
            "test1": {
                "extra_options": set(),
                "tags": set(),
                "values": {
                    "time": val,
                    ...
                }
            },
            ...
        },
        ...
    }
    """
    platform_ind = get_data_ind(data, "platform")
    test_ind = get_data_ind(data, "suite")
    extra_ind = get_data_ind(data, "extra_options")
    tag_ind = get_data_ind(data, "tags")
    val_ind = get_data_ind(data, "value")
    time_ind = get_data_ind(data, "push_timestamp")
    app_ind = get_data_ind(data, "application")

    org_data = {}
    for entry in data[1:]:
        platform = entry[platform_ind]
        if platforms and platform not in platforms:
            continue

        test = entry[test_ind]
        app = entry[app_ind]
        extras = entry[extra_ind].split()
        tags = entry[tag_ind].split()
        variants = "None"
        pl_type = "cold"

        if "warm" not in extras and "cold" not in extras:
            continue

        if "live" in extras:
            continue

        if "warm" in extras:
            pl_type = "warm"

        if "fission" in extras:
            variants += "fission-"
        if "webrender" in extras:
            variants += "webrender"

        if "nocondprof" in extras:
            extras.remove("nocondprof")
        # if "nocondprof" in tags:
        #     tags.remove("nocondprof")
        if "visual" not in extras:
            extras.append("visual")
        # if "visual" not in tags:
        #     tags.append("visual")

        # if test not in ("amazon", "google-mail", "google-slides", "imgur", "tumblr", "twitch", "twitter"):
        #     continue

        if variants != "None":
            print("here")
            variants = variants.replace("None", "")

        mod_test_name = f"{test}-{app}" + "-".join(sorted(extras))
        test_data = (
            org_data.setdefault(platform, {})
            .setdefault(app, {})
            .setdefault(variants, {})
            .setdefault(pl_type, {})
            .setdefault(mod_test_name, {})
        )

        # Make sure we're never mixing data
        if "extra_options" in test_data:
            assert test_data["extra_options"] == set(list(extras))
        else:
            test_data["extra_options"] = set(list(extras))
        # if "tags" in test_data:
        #     print("awlkhwalkhd")
        #     print(test_data["tags"])
        #     print(tags)
        #     assert test_data["tags"] == set(list(tags))
        # else:
        #     test_data["tags"] = set(list(tags))

        test_data.setdefault("values", {}).setdefault(entry[time_ind], []).append(
            float(entry[val_ind])
        )

    if not org_data:
        possible_platforms = set([entry[platform_ind] for entry in data])
        raise Exception(
            "Could not find any requested platforms in the data. Possible choices are: "
            f"{possible_platforms}"
        )

    return org_data


def summarize(data, platforms):
    org_data = organize_data(data, platforms)

    summary = {}
    for platform, apps in org_data.items():

        for app, variants in apps.items():

            for variant, pl_types in variants.items():

                for pl_type, tests in pl_types.items():

                    platform_summary = {"tests": list(tests.keys()), "values": []}
                    # Get all the push times
                    all_push_times = []
                    for _, info in tests.items():
                        print(info)
                        all_push_times.extend(list(info["values"].keys()))
                    all_push_times = list(set(all_push_times))

                    all_push_times = temporal_aggregation(all_push_times, 24)

                    print(all_push_times)

                    # Get a summary value for each push time
                    summarized_vals = []
                    tests_per_val = {}
                    prev_time = None
                    prev_test_times = {}
                    for c, times in enumerate(sorted(all_push_times)):

                        vals = {}
                        for time in times:
                            if not prev_time:
                                prev_time = time

                            good = True
                            testsc = []
                            testsg = []
                            for test, info in tests.items():
                                if time not in info["values"]:
                                    good = False
                                    testsc.append(test)
                                    continue
                                if test not in prev_test_times:
                                    prev_test_times[test] = time

                                vals.setdefault(test, []).extend(info["values"][time])
                                testsg.append(
                                    (
                                        test,
                                        time,
                                        prev_test_times[test],
                                        np.mean(info["values"][time]),
                                        np.mean(info["values"][prev_test_times[test]]),
                                    )
                                )

                                prev_test_times[test] = time

                            if not good:
                                print(
                                    f"Tests which failed and prevent a summary at time {time}:",
                                    testsc,
                                )

                        vals = [np.mean(v) for _, v in vals.items()]
                        summarized_vals.append((times[-1], gmean(np.asarray(vals))))

                        tests_per_val[str(c)] = {
                            "good": testsg,
                            "bad": testsc,
                            "vals": vals,
                        }

                        prev_time = time
                    """
                                "wikia-firefox-cold-webrender",
                                "espn-firefox-cold-webrender",
                                "cnn-firefox-cold-webrender",
                                "nytimes-firefox-cold-webrender",
                                "buzzfeed-firefox-cold-webrender",
                                "expedia-firefox-cold-webrender"
                    """

                    """
                                "wikia-firefox-cold-webrender",
                                "espn-firefox-cold-webrender",
                                "cnn-firefox-cold-webrender",
                                "nytimes-firefox-cold-webrender",
                                "buzzfeed-firefox-cold-webrender",
                                "expedia-firefox-cold-webrender"
                    """

                    import json

                    print("hereeee")
                    print(json.dumps(tests_per_val, indent=4))

                    # # Get the ratios over time
                    # prev_test_times = {}
                    # all_ratios = []
                    # prev_ratio = np.nan

                    # for time in sorted(all_push_times):

                    #     ratios = []
                    #     for test, info in tests.items():
                    #         if info["values"].get(time, None):
                    #             if prev_test_times.get(test, None):
                    #                 ratios.append(
                    #                     np.mean(
                    #                         info["values"][time]
                    #                     ) / np.mean(
                    #                         info["values"][prev_test_times[test]]
                    #                     )
                    #                 )
                    #             else:
                    #                 prev_test_times[test] = time
                    #         else:
                    #             continue

                    #     gmean_ratios = gmean(ratios)
                    #     if np.isnan(gmean_ratios) and not np.isnan(prev_ratio):
                    #         all_ratios.append(prev_ratio)
                    #         continue
                    #     prev_ratio = gmean_ratios
                    #     all_ratios.append(gmean_ratios)

                    # new_ratios = []
                    # first_good = None
                    # for y in all_ratios:
                    #     if not np.isnan(y):
                    #         first_good = y
                    #         break
                    # for y in all_ratios:
                    #     if np.isnan(y) and first_good:
                    #         new_ratios.append(first_good)
                    #     else:
                    #         new_ratios.append(y)
                    #         first_good = None

                    # all_ratios = new_ratios
                    # all_ratios = np.asarray(all_ratios)

                    # plt.figure()
                    variant = variant if variant != "None" else "e10s"
                    plt.title(platform + f"\n{app}-{pl_type}-{variant}")
                    # plt.plot(list(((all_ratios-min(all_ratios))/(max(all_ratios)-min(all_ratios)))), label="Ratios geomean")
                    # plt.show()

                    # plt.figure()

                    x = np.asarray(
                        [y for x, y in sorted(summarized_vals, key=lambda x: x[0])]
                    )
                    times = np.asarray(
                        [x for x, y in sorted(summarized_vals, key=lambda x: x[0])]
                    )
                    sorted_summary = (x - min(x)) / (max(x) - min(x))
                    print(sorted_summary)
                    print(platform)
                    print(variant)

                    # break
                    # plt.plot([i for i in range(len(sorted_summary))], [y for x, y in sorted_summary])
                    plt.plot(x, label="Geomean")

                    plt.legend()
                    plt.show()

                    summary.setdefault(platform, {}).setdefault(variant, {}).setdefault(
                        app, {}
                    )[pl_type] = {
                        "tests": list(tests.keys()),
                        "values-gmean": x,
                        "times": times,
                    }


def temporal_aggregation(times, timespan=24):
    import datetime

    aggr_times = []
    diff = datetime.timedelta(hours=timespan)

    curr = []
    for t in sorted(times)[::-1]:

        dt = datetime.datetime.strptime(t, "%Y-%m-%d %H:%M")
        if len(curr) == 0:
            curr.append(dt)
        elif curr[0] - dt < diff:
            curr.append(dt)
        else:
            aggr_times.append([c.strftime("%Y-%m-%d %H:%M") for c in curr])
            curr = [dt]

    return aggr_times


def main():
    args = summary_parser().parse_args()

    # Check data path and setup output
    data_path = pathlib.Path(args.data)
    if not data_path.exists():
        raise Exception(f"The given data file doesn't exist: {args.data}")

    output_folder = pathlib.Path(args.output)
    output_file = "summary.json"

    if output_folder.exists() and output_folder.is_file():
        print(f"Deleting existing JSON file at: {output_folder}")
        output_folder.unlink()

    if not output_folder.exists():
        # possible_folder, possible_file = output_folder.parts()
        if pathlib.Path(output_folder.parts[-1]).suffixes:
            # A CSV file name was given
            output_file = output_folder.parts[-1]
            output_folder = pathlib.Path(*output_folder.parts[:-1])
        output_folder.mkdir(parents=True, exist_ok=True)

    # Open data
    data = open_csv_data(data_path)
    results = summarize(data, args.platforms)
    agr = temporal_aggregation(results, args.timespan)


if __name__ == "__main__":
    main()
