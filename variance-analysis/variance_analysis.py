import os
import json
import numpy as np

from scipy import stats as stats
from matplotlib import pyplot as plt


def run_variance_analysis(
    data,
    tests=[
        "amazon",
        "apple",
        "bing",
        "ebay",
        "fandom",
        "facebook",
        "docs",
        "google-mail",
        "google",
    ],
    platform="Unknown Platform",
):

    if isinstance(data, str):
        with open(data) as f:
            data = json.load(f)

    groupings = set()
    subtests = set()
    grouped_data = {}
    for entry in data:
        tuned = "pooled"
        pltype = "warm"
        grouping = entry["name"]
        groupings.add(grouping)
        if "cold" in entry["subtest"]:
            pltype = "cold"

        grouped_data.setdefault(pltype, {}).setdefault(grouping, {})[
            entry["subtest"]
        ] = entry["data"]

        subtests.add(entry["subtest"])

    if len(groupings) != 2:
        raise Exception(
            "Unable to compare variance. The number of groupings must be 2."
        )
    groupings = list(groupings)

    def filter(data):
        # Apply a gaussian filter
        data = np.asarray(data)
        data = data[np.where(data > np.mean(data) - np.std(data) * 2)[0]]
        data = list(data[np.where(data < np.mean(data) + np.std(data) * 2)[0]])
        return data

    subtests = list(subtests)
    print("Subtests to analyze (%s):" % len(subtests))
    for i in sorted(subtests):
        print("    " + i)
    print("")

    for pltype in ("warm", "cold"):
        plt.figure()
        plt.suptitle("%s Variance Analysis - %s" % (platform, pltype))

        g5lvals = []
        g5stds = []
        for subtest in subtests:
            p2t = grouped_data[pltype][groupings[0]].get(subtest, None)
            p2wt = grouped_data[pltype][groupings[1]].get(subtest, None)
            if p2t is not None and p2wt is not None:
                p2t = filter(p2t)
                p2wt = filter(p2wt)
                lval, pv = stats.levene(p2t, p2wt)
                if np.std(p2wt - np.mean(p2wt)) == 0:
                    continue
                diff = np.std(p2t - np.mean(p2t)) / np.std(p2wt - np.mean(p2wt))
                # Uncomment to check what the outliers look like
                # if diff < 0.7:
                #     print(subtest)
                #     plt.figure()
                #     plt.title(subtest)
                #     print(len(p2t))
                #     print(len([v for v in p2t if v < 1100]))
                #     plt.scatter([1 for _ in p2t], p2t)
                #     plt.scatter([2 for _ in p2wt], p2wt)
                #     plt.ylabel("Time")
                #     plt.xticks([1,2], ["chimera", "normal"])
                #     plt.show()
                #     continue
                g5lvals.append(pv)
                g5stds.append(diff)

        plt.subplot(2, 1, 1)
        plt.plot(g5stds)
        plt.title("Std. Dev.")
        plt.ylabel("StdDev Diff - >1 is increased noise in group %s" % grouping[0])
        plt.xlabel("Subtests")
        plt.subplot(2, 1, 2)
        plt.plot(g5lvals)
        plt.title("Levene's")
        plt.ylabel("P Value")
        plt.xlabel("Subtests")

        g5lvals = np.asarray(g5lvals)
        g5lvals = np.asarray([v for v in g5lvals if not np.isnan(v)])
        g5stds = np.asarray([v for v in g5stds if not np.isnan(v)])
        print(
            "%s - %s total: %s/%s"
            % (
                platform,
                pltype,
                len(g5stds[np.where((g5lvals <= 0.05) & (np.isfinite(g5lvals)))]),
                len(g5stds),
            )
        )
        print(
            "Average noise diff: %s"
            % np.mean(g5stds[np.where((g5lvals <= 0.05) & (np.isfinite(g5lvals)))])
        )
        print(
            "Significance of the average: %s"
            % np.mean(g5lvals[np.where((g5lvals <= 0.05) & (np.isfinite(g5lvals)))])
        )

        sigs = g5stds[np.where((g5lvals <= 0.05) & (np.isfinite(g5lvals)))]
        sigsl = np.where(sigs < 1)[0]
        sigsh = np.where(sigs >= 1)[0]
        print(f"Number of tests with lower noise: {len(sigsl)}")
        print(f"Number of tests with higher noise: {len(sigsh)}")

        print(f"Averager decrease in noise for lower: {np.mean(sigs[sigsl])}")
        print(f"Average increase in noise for higher: {np.mean(sigs[sigsh])}")
        print(
            "\nThe Average noise diff gives a ratio between the %s and the %s grouping. "
            "A ratio greater than 1 implies that the noise is larger in %s"
            % (groupings[0], groupings[1], groupings[0])
        )

    plt.show()
