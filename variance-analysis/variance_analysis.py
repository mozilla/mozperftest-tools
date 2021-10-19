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
    groupings=None,
):

    if isinstance(data, str):
        with open(data) as f:
            data = json.load(f)

    tmp_groupings = set()
    subtests = set()
    grouped_data = {}
    for entry in data:
        tuned = "pooled"
        pltype = "warm"
        grouping = entry["name"]
        tmp_groupings.add(grouping)
        if "cold" in entry["subtest"]:
            pltype = "cold"

        grouped_data.setdefault(pltype, {}).setdefault(grouping, {})[
            entry["subtest"]
        ] = entry["data"]

        subtests.add(entry["subtest"])

    if groupings is None:
        groupings = sorted(list(tmp_groupings))
    if len(groupings) != 2:
        raise Exception(
            "Unable to compare variance. The number of groupings must be 2."
        )

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

        levene_vals = []
        std_dev_ratios = []
        for subtest in subtests:
            group_1 = grouped_data[pltype][groupings[0]].get(subtest, None)
            group_2 = grouped_data[pltype][groupings[1]].get(subtest, None)
            if group_1 is not None and group_2 is not None:
                group_1 = filter(group_1)
                group_2 = filter(group_2)
                lval, pv = stats.levene(group_1, group_2)
                if np.std(group_2 - np.mean(group_2)) == 0:
                    continue
                std_dev_ratio = np.std(group_1 - np.mean(group_1)) / np.std(
                    group_2 - np.mean(group_2)
                )
                # Uncomment to check what the outliers look like
                # if diff < 0.7:
                #     print(subtest)
                #     plt.figure()
                #     plt.title(subtest)
                #     print(len(group_1))
                #     print(len([v for v in group_1 if v < 1100]))
                #     plt.scatter([1 for _ in group_1], group_1)
                #     plt.scatter([2 for _ in group_2], group_2)
                #     plt.ylabel("Time")
                #     plt.xticks([1,2], ["chimera", "normal"])
                #     plt.show()
                #     continue
                levene_vals.append(pv)
                std_dev_ratios.append(std_dev_ratio)

        plt.subplot(2, 1, 1)
        plt.plot(std_dev_ratios)
        plt.title("Std. Dev.")
        plt.ylabel("StdDev Diff - >1 is increased noise in group %s" % groupings[0])
        plt.xlabel("Subtests")
        plt.subplot(2, 1, 2)
        plt.plot(levene_vals)
        plt.title("Levene's")
        plt.ylabel("P Value")
        plt.xlabel("Subtests")

        levene_vals = np.asarray(levene_vals)
        levene_vals = np.asarray([v for v in levene_vals if not np.isnan(v)])
        std_dev_ratios = np.asarray([v for v in std_dev_ratios if not np.isnan(v)])
        print(
            "%s - %s total: %s/%s"
            % (
                platform,
                pltype,
                len(
                    std_dev_ratios[
                        np.where((levene_vals <= 0.05) & (np.isfinite(levene_vals)))
                    ]
                ),
                len(std_dev_ratios),
            )
        )
        print(
            "Average noise diff: %s"
            % np.mean(
                std_dev_ratios[
                    np.where((levene_vals <= 0.05) & (np.isfinite(levene_vals)))
                ]
            )
        )
        print(
            "Significance of the average: %s"
            % np.mean(
                levene_vals[
                    np.where((levene_vals <= 0.05) & (np.isfinite(levene_vals)))
                ]
            )
        )

        sigs = std_dev_ratios[
            np.where((levene_vals <= 0.05) & (np.isfinite(levene_vals)))
        ]
        sigsl = np.where(sigs < 1)[0]
        sigsh = np.where(sigs >= 1)[0]
        print(f"Number of tests with lower noise in {groupings[0]}: {len(sigsl)}")
        print(f"Number of tests with higher noise in {groupings[0]}: {len(sigsh)}")

        print(f"Averager decrease in noise for lower: {np.mean(sigs[sigsl])}")
        print(f"Average increase in noise for higher: {np.mean(sigs[sigsh])}")
        print(
            "\nThe Average noise diff gives a ratio between the "
            f"{groupings[0]} and the {groupings[1]} grouping. "
            f"A ratio greater than 1 implies that the noise is larger in {groupings[0]}."
        )

    plt.show()
