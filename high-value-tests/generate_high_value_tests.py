# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import csv
import numpy as np
import os
import random


def highvalue_parser():
    """
    Parser for the high-value test generator.
    """
    parser = argparse.ArgumentParser(
        "This tool can be used to determine high-value tests from a "
        + "CSV file produced by the Redash query in `sql_query.txt`."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the data that contains information on regressions.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="The number of minimzations to do while trying to find a minimal "
        "test set that maximizes the number of alerts caught. Defaults to 100.",
    )
    parser.add_argument(
        "--view",
        action="store_true",
        default=False,
        help="View how the regressions are spread across tests, showing the "
        "number of regressions each test caught, as well as the unique "
        "number of regressions the tests caught.",
    )
    return parser


def open_csv_data(path):
    """
    Opens a CSV data file from a given path.
    """
    rows = []
    with open(path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_data_ind(data, fieldname):
    """
    Returns an index for the requested field.
    """
    for i, entry in enumerate(data[0]):
        if fieldname in entry:
            return i
    return None


def get_suites_and_alerts(data):
    """
    Returns the suites and alert IDs found. The two
    lists returned in the tuple have a 1:1 relationship between
    their entries.
    """
    summaryid_ind = get_data_ind(data, "summary_id")
    suite_ind = get_data_ind(data, "suite")

    suites = []
    summary_ids = []
    for row in data[1:]:
        suites.append(row[suite_ind])
        summary_ids.append(row[summaryid_ind])

    return (suites, summary_ids)


def get_alert_matrix(data, suites=None, summary_ids=None, randomize=True):
    """
    Returns the data in matrix form. Rows are alerts,
    and columns are tests. It also returns the suites and
    alert IDs that were found and used to build the matrix.

    The values' indices in the unique_suites, and the unique_ids
    correspond to the column or row in the alert_mat returned.
    """
    if not suites and not summary_ids:
        suites, summary_ids = get_suites_and_alerts(data)

    unique_suites = list(set(suites))
    if randomize:
        random.shuffle(unique_suites)

    unique_suites_dict = {s: c for c, s in enumerate(unique_suites)}

    unique_ids = list(set(summary_ids))
    if randomize:
        random.shuffle(unique_ids)

    unique_ids_dict = {s: c for c, s in enumerate(unique_ids)}

    # Organize all the data to make it easier to build the
    # alert matrix.
    summaryid_ind = get_data_ind(data, "summary_id")
    suite_ind = get_data_ind(data, "suite")
    summary_ids_dict = {}
    for row in data[1:]:
        if row[summaryid_ind] not in summary_ids_dict:
            summary_ids_dict[row[summaryid_ind]] = {}
            summary_ids_dict[row[summaryid_ind]]["tests"] = []
        test = row[suite_ind]
        if test not in summary_ids_dict[row[summaryid_ind]]["tests"]:
            summary_ids_dict[row[summaryid_ind]]["tests"].append(test)

    # Build matrix to analyze
    alert_mat = np.zeros((len(unique_ids), len(unique_suites)))
    for alertid, alertinfo in summary_ids_dict.items():
        for test in alertinfo["tests"]:
            alert_mat[unique_ids_dict[alertid], unique_suites_dict[test]] = 1

    return alert_mat, unique_suites, unique_ids


def get_minimal_testset(data, iterations=100):
    """
    Returns a minimal set of tests to run to catch all
    known regressions.
    """
    suites, summary_ids = get_suites_and_alerts(data)

    best_suites = None
    best_ids = None
    minimal_testset = None
    maximal_alerts = []
    for _ in range(iterations):
        alert_mat, suites, summary_ids = get_alert_matrix(
            data, suites=suites, summary_ids=summary_ids
        )

        ## Algorithm for minimzation starts here
        allchosentests = []
        caught_alerts = []
        for i in range(alert_mat.shape[0]):
            # Pick a test for each row
            chosentest = -1
            row = np.squeeze(alert_mat[i, :])
            alltests = [c for c, j in enumerate(row) if j == 1]
            if len(alltests) == 1:
                chosentest = alltests[0]
            else:
                # Check if it's already been caught
                if any([t in allchosentests for t in alltests]):
                    caught_alerts.append(i)
                    continue

                # Not caught; let's pick a test which maximizes the
                # number of alerts we catch (excluding those we already
                # caught)
                max_col = -1
                max_alerts = -1
                for j in alltests:
                    col = alert_mat[:, j]
                    rowinds = [c for c, a in enumerate(col) if a == 1]
                    rowinds = list(set(rowinds) - set(caught_alerts))
                    if len(rowinds) > max_alerts:
                        max_alerts = len(rowinds)
                        max_col = j
                chosentest = max_col

            if chosentest not in allchosentests and chosentest > -1:
                allchosentests.append(chosentest)
            caught_alerts.append(i)

        ## Check if this round of minimization worked any better
        if not minimal_testset:
            best_suites = suites.copy()
            best_ids = summary_ids.copy()
            minimal_testset = allchosentests
            maximal_alerts = caught_alerts
        elif len(allchosentests) < len(minimal_testset):
            best_suites = suites.copy()
            best_ids = summary_ids.copy()
            minimal_testset = allchosentests
            maximal_alerts = caught_alerts

    rejected_inds = list(set(list(range(len(best_suites)))) - set(minimal_testset))
    info = {
        "total_caught": 100 * (float(len(maximal_alerts)) / len(best_ids)),
        "total_tests_left": 100 * (float(len(minimal_testset)) / len(best_suites)),
        "tests": [best_suites[j] for j in minimal_testset],
        "rejected_tests": [best_suites[j] for j in rejected_inds],
    }

    print(
        "Total alerts caught: %s (%s/%s)"
        % (info["total_caught"], len(maximal_alerts), len(best_ids))
    )
    print(
        "Percentage of total tests left: %s (%s/%s)\n"
        % (info["total_tests_left"], len(minimal_testset), len(best_suites))
    )
    print("Chosen tests: %s\n" % info["tests"])
    print("Rejected tests: %s" % info["rejected_tests"])

    return info


def view_histogram(data):
    from matplotlib import pyplot as plt

    alert_mat, suites, summary_ids = get_alert_matrix(data)

    x_coords = np.arange(len(suites))
    suites_counts = [np.sum(np.squeeze(alert_mat[:, j])) for j, _ in enumerate(suites)]

    summed_am = np.sum(alert_mat, axis=1)
    uni_counts = [0 for _ in suites]
    for i, val in enumerate(summed_am):
        if val == 1:
            test = [j for j, v in enumerate(alert_mat[i, :]) if v == 1]
            uni_counts[test[0]] += 1

    plt.figure()
    plt.suptitle(
        "Number of regressions/improvements, excluding duplicate entries\n"
        "Red is number of times only that test caught the regression/improvement\n"
        "Blue is number of times that test caught a regression/improvement"
    )
    plt.barh(x_coords, suites_counts)
    plt.barh(x_coords, uni_counts, color="red")
    plt.yticks(x_coords, suites)
    plt.title("Regressions")
    plt.show()


def main():
    args = highvalue_parser().parse_args()
    data = open_csv_data(args.input)

    get_minimal_testset(data, args.iterations)

    if args.view:
        view_histogram(data)


if __name__ == "__main__":
    main()
