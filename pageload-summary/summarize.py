#!/usr/bin/python3
import argparse
import csv
import datetime
import json
import numpy as np
import os
import pathlib

import matplotlib.dates as md
from matplotlib import pyplot as plt


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
        "--timespan",
        type=int,
        default=24,
        help="Minimum time between each data point in hours.",
    )
    parser.add_argument(
        "--moving-average-window",
        type=int,
        default=7,
        help="Number of days to use for the moving average.",
    )
    parser.add_argument(
        "--by-site",
        action="store_true",
        default=False,
        help="Output summary by site",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        default=False,
        help="Show visualizations",
    )
    parser.add_argument(
        "--save-plots",
        action="store_true",
        default=False,
        help="Save visualizations",
    )
    parser.add_argument(
        "--save-directory",
        help="Directory to save visualizations",
    )
    parser.add_argument(
        "--platforms",
        nargs="*",
        default=[],
        help="Platforms to summarize. Default is all platforms.",
    )
    parser.add_argument(
        "--platform-pattern",
        help="pattern (substring-match) for platforms to summarize. Default is all platforms.",
    )
    parser.add_argument(
        "--start-date",
        type=datetime.datetime.fromisoformat,
        help="Date to start analysis (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        type=datetime.datetime.fromisoformat,
        help="Date to end analysis (inclusive).",
    )
    parser.add_argument(
        "--app",
        help="Apps to summarize (default is all).  Examples: firefox, chromium, chrome",
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


def organize_data(data, platforms, platform_pattern, start_date, end_date, by_site = False, app_only=None):
    """Organizes the data into a format that is easier to handle."""

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
        if platform_pattern and platform.find(platform_pattern) == -1:
            continue
        date = datetime.datetime.fromisoformat(entry[time_ind])
        if start_date != None and date < start_date:
            continue
        if end_date != None and date > end_date:
            continue

        test = entry[test_ind]
        app = entry[app_ind]
        if app_only != None and app_only != app:
            continue
        extras = entry[extra_ind].split()
        tags = entry[tag_ind].split()
        variants = "e10s"
        pl_type = "cold"

        # Without this, we might start pulling in data
        # from mozperftest tests
        if "warm" not in extras and "cold" not in extras:
            continue

        # Make sure we always ignore live site data
        if "live" in extras:
            continue

        # Make sure we always ignore profiler runs
        if "gecko-profile" in extras:
            continue

        if "warm" in extras:
            pl_type = "warm"

        if "fission" in extras:
            variants += "fission-"
        if "webrender" in extras:
            variants += "webrender"

        # Newer data no longer has the nocondprof option
        if "nocondprof" in extras:
            extras.remove("nocondprof")
        # Older data didn't have this flag
        if "visual" not in extras:
            extras.append("visual")

        if variants != "e10s":
            variants = variants.replace("e10s", "")

        if by_site:
            platform += "-" + test
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


def geo_mean(iterable):
    a = np.array(iterable)
    return a.prod() ** (1.0 / len(a))


def temporal_aggregation(times, timespan=24):
    """Aggregates times formatted like `YYYY-mm-dd HH:MM`.

    After aggregation, the result will contain lists of all
    points that were grouped together. Timespan distancing
    starts from the newest data point.
    """
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

    return aggr_times[::-1]


def summarize(data, platforms, platform_pattern, timespan, moving_average_window, start_date, end_date, by_site, app_only):
    org_data = organize_data(data, platforms, platform_pattern, start_date, end_date, by_site, app_only)

    summary = {}

    for platform, apps in org_data.items():

        for app, variants in apps.items():

            for variant, pl_types in variants.items():

                for pl_type, tests in pl_types.items():
                    # Get all the push times and aggregate them
                    all_push_times = []
                    for _, info in tests.items():
                        all_push_times.extend(list(info["values"].keys()))
                    all_push_times = temporal_aggregation(
                        list(set(all_push_times)), timespan
                    )

                    # Get a summary value for each push time
                    summarized_vals = []
                    for times in sorted(all_push_times):

                        vals = {}
                        for time in times:
                            for test, info in tests.items():
                                if time not in info["values"]:
                                    continue
                                vals.setdefault(test, []).extend(info["values"][time])

                        vals = [np.mean(v) for _, v in vals.items()]
                        summarized_vals.append((times[-1], geo_mean(np.asarray(vals))))

                    ma_vals = []
                    window = []
                    time_window = []
                    startdate = datetime.datetime.fromisoformat(summarized_vals[0][0])
                    enddate = datetime.datetime.fromisoformat(summarized_vals[-1][0])
                    if (enddate-startdate).days > moving_average_window:
                        for time, val in summarized_vals:
                            window.append(val)
                            time_window.append(time)
                            startdate = datetime.datetime.fromisoformat(time_window[0])
                            enddate = datetime.datetime.fromisoformat(time)
                            if (enddate-startdate).days > moving_average_window:
                                ma_vals.append((time, np.mean(window)))
                                window = window[1:]
                                time_window = time_window[1:]
                    else:
                        ma_vals = summarized_vals

                    if len(ma_vals) == 0:
                        continue

                    summary.setdefault(platform, {}).setdefault(app, {}).setdefault(
                        variant, {}
                    )[pl_type] = {
                        "values": summarized_vals,
                        "moving_average": ma_vals,
                    }

    return summary


def text_summary(summary, width=20, plat_width=50):
    """Outputs the two newest points of the summary as a table.

    Returns the results as a list that could be saved to a CSV file.

    Ex:

    Platform          | App       | Variant            | Type   | 04/12/2021 | 04/13/2021
    -------------------------------------------------------------------------------------
    linux64-shippable | firefox   | e10s               | cold   | 1900       | 1850
                      |           |                    | warm   | 800        | 750
                      |           -------------------------------------------------------
                      |           | webrender          | cold   |            |
                      |           |                    | warm   |            |
                      |           -------------------------------------------------------
                      |           | fission            | cold   |
                      |           |                    | warm   |
                      |           ------------------------------------------
                      |           | fission-webrender  | cold   |
                      |           |                    | warm   |
                      ------------------------------------------------------
                      | chrome    |                    |        |
                      ------------------------------------------------------
                      | chromium  |                    |        |
    ------------------------------------------------------------------------
    """

    csv_lines = []
    lines = []

    # Get the two newest data points, for tests without data at those points
    # we'll take the two newest data points they have regardless of date.
    all_times = []
    for platform, apps in summary.items():
        for app, variants in apps.items():
            for variant, pl_types in variants.items():
                for pl_type, data in pl_types.items():
                    # if len(data.get("moving_average", [])) > 0:
                    all_times.append(data["moving_average"][-1][0])
    sorted_times = sorted(list(set(all_times)))

    newest_point = sorted_times[-1]
    previous_point = newest_point
    if len(sorted_times) > 1:
        previous_point = sorted_times[-2]

    format_line = (
        "{:<{plat_width}}| {:<{width}}| {:<{width}}| {:<10}| {:<{width}}| {:<{width}}"
    )
    header_line = format_line.format(
        "Platform",
        "Application",
        "Variant",
        "Type",
        previous_point,
        newest_point,
        width=width,
        plat_width=plat_width,
    )
    table_len = len(header_line)
    lines.append(header_line)
    lines.append("-" * table_len)

    csv_lines.append(
        ["Platform", "Application", "Variant", "Type", previous_point, newest_point]
    )

    platform_output = False
    app_output = False
    variant_output = False

    for platform, apps in sorted(summary.items()):

        if platform_output:
            lines.append("-" * table_len)
        if len(platform) >= plat_width:
            platform = platform[: plat_width - 1]

        platform_output = False
        app_output = False
        variant_output = False
        for app, variants in sorted(apps.items(),reverse=1):

            if app_output:
                spacer = width * 2
                lines.append(" " * spacer + "-" * (table_len - spacer))

            app_output = False
            variant_output = False
            for variant, pl_types in sorted(variants.items(),reverse=1):
                if app in ("chrome", "chromium"):
                    variant = ""

                if variant_output:
                    spacer = width * 3
                    lines.append(" " * spacer + "-" * (table_len - spacer))

                variant_output = False
                for pl_type, data in pl_types.items():
                    platform_str = platform
                    app_str = app
                    variant_str = variant

                    if platform_output:
                        platform_str = ""
                    if variant_output:
                        variant_str = ""
                    if app_output:
                        app_str = ""

                    cur = np.round(data["moving_average"][-1][1], 2)
                    prev = cur
                    if len(data["moving_average"]) > 1:
                        prev = np.round(data["moving_average"][-2][1], 2)

                    if prev > 0.0:
                        delta = f" ({np.round(cur/prev,4)})";
                    else:
                        delta = " (NaN)"
                    lines.append(
                        format_line.format(
                            platform_str,
                            app_str,
                            variant_str,
                            pl_type,
                            prev,
                            str(cur) + delta,
                            width=width,
                            plat_width=plat_width,
                        )
                    )
                    csv_lines.append([platform, app, variant, pl_type, prev, cur])

                    if not variant_output:
                        variant_output = True
                    if not app_output:
                        app_output = True
                    if not platform_output:
                        platform_output = True

    for line in lines:
        print(line)

    return csv_lines


def visual_summary(summary, save=False, directory=None):

    for platform, apps in sorted(summary.items()):

        for app, variants in sorted(apps.items(),reverse=1):

            plt.figure(figsize=(10,10))
            plt.suptitle(platform + f" {app}")
            for variant, pl_types in sorted(variants.items(),reverse=1):

                """
                This is a simple visualization to show the metric. It
                can be modified to anything.
                """

                figc = 1
                for pl_type, data in pl_types.items():
                    plt.subplot(1, 2, figc)
                    figc += 1

                    variant = variant if variant != "None" else "e10s"
                    plt.title(f"{pl_type}")

                    times = [
                        datetime.datetime.strptime(x, "%Y-%m-%d %H:%M")
                        for x, y in data["values"]
                    ]
                    vals = [y for x, y in data["values"]]

                    ma_times = [
                        datetime.datetime.strptime(x, "%Y-%m-%d %H:%M")
                        for x, y in data["moving_average"]
                    ]
                    ma_vals = [y for x, y in data["moving_average"]]

                    md_times = md.date2num(times)
                    md_ma_times = md.date2num(ma_times)

                    ax = plt.gca()
                    xfmt = md.DateFormatter("%Y-%m-%d %H:%M:%S")
                    ax.xaxis.set_major_formatter(xfmt)
                    plt.xticks(rotation=25)

                    plt.plot(md_times, vals, label=variant)
                    plt.plot(md_ma_times, ma_vals, label=variant + " (avg)")
                    plt.legend()

            if save:
                if directory != None:
                    if directory[-1] != '/':
                        directory += '/'
                    dest = directory + platform + ".png"
                else:
                    dest = platform + ".png"
                plt.savefig(dest)
                plt.close()
            else:
                plt.show()


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
        if pathlib.Path(output_folder.parts[-1]).suffixes:
            # A JSON file name was given
            output_file = output_folder.parts[-1]
            output_folder = pathlib.Path(*output_folder.parts[:-1])
        output_folder.mkdir(parents=True, exist_ok=True)

    # Process the data and visualize the results (after saving)
    data = open_csv_data(data_path)

    results = summarize(data, args.platforms, args.platform_pattern, args.timespan, args.moving_average_window, args.start_date, args.end_date, args.by_site, args.app)
    with pathlib.Path(output_folder, output_file).open("w") as f:
        json.dump(results, f)

    csv_lines = text_summary(results)

    csv_file = pathlib.Path(output_folder, "newest-points.csv")
    if csv_file.exists():
        print(f"Deleting existing CSV summary file at: {csv_file}")
        csv_file.unlink()
    with csv_file.open("w") as f:
        writer = csv.writer(f, delimiter=",")
        for line in csv_lines:
            writer.writerow(line)

    if args.visualize:
        visual_summary(results, args.save_plots, args.save_directory)


if __name__ == "__main__":
    main()
