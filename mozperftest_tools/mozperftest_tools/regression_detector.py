#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Used to detect performance changes in-tree.
"""

import copy
import json
import numpy as np
import pathlib
import scipy
import shutil

from mozperftest_tools.side_by_side import SideBySide
from mozperftest_tools.utils.artifact_downloader import artifact_downloader
from mozperftest_tools.utils.task_processor import (
    get_task_data_paths,
    match_vismets_with_videos,
    sorted_nicely,
)
from mozperftest_tools.utils.utils import (
    finish_same_line,
    find_task_group_id,
    get_pushes,
    get_revision_json,
    write_same_line,
)

"""
TODO:
* Add sliding window parameter to new method.
* Detect across all tests, and platforms.

"""

ALLOWED_METHODS = ["mwu"]
MAX_WINDOW = 1


class MethodNotFoundError(Exception):
    """Raised when a specified detection method is not found."""

    pass


class ZeroDepthError(Exception):
    """Raised when the auto-computed depth is zero."""

    pass


class BranchMismatchError(Exception):
    """Raised when branches do not match."""

    pass


class NoDataError(Exception):
    """Raised when we can't find enough data."""

    pass


class ChangeDetector(SideBySide):
    def __init__(self, output_dir, method="mwu"):
        self._output_dir = pathlib.Path(output_dir).resolve()
        self._cache = None

        self.method = method
        if method not in ALLOWED_METHODS:
            raise MethodNotFoundError(f"Unknown method: {method}")

    def _gather_revisions(self, start, end, branch, depth):
        """Returns all revisions/pushes found in a given range.

        Either the entire range of pushes from start (base) to end (new)
        is returned or a maximum of "depth" number of pushes (end-depth).
        """
        end_id = get_revision_json(end, branch=branch, cache=self._cache)["pushid"]
        if depth == -1:
            # We need to determine the depth to search
            if start == end:
                raise ZeroDepthError(
                    "The starting, and ending revisions can't be the same when"
                    "depth is set to -1 (auto-computed)."
                )
            start_info = get_revision_json(start, branch=branch, cache=self._cache)
            depth = (int(end_id) - int(start_info["pushid"])) + 1
            print(f"Using an auto-computed depth of {depth} to gather revisions")
        pushes = get_pushes(
            branch,
            end_id,
            depth,
            True,
            cache=self._cache,
        )

        push_revisions = []
        for push_id in sorted_nicely(list(pushes.keys())):
            push_revisions.append(pushes[push_id]["changesets"][-1])

        return push_revisions

    def _open_and_organize_perfherder(self, files):
        def _open_perfherder(filen):
            with open(filen) as f:
                return json.load(f)

        res = {"cold": {}, "warm": {}}

        for filen in files:
            data = _open_perfherder(filen)

            for suite in data["suites"]:
                pl_type = "warm"
                if "cold" in suite["extraOptions"]:
                    pl_type = "cold"

                for subtest in suite["subtests"]:
                    if "cputime" in subtest["name"].lower():
                        continue
                    # Each entry here will be a single retrigger of
                    # the test for the requested metric (ordered
                    # based on the `files` ordering)
                    res[pl_type].setdefault(subtest["name"], []).extend(
                        subtest["replicates"]
                    )

        return res

    def detect_changes(
        self,
        test_name="",
        new_test_name="",
        platform="",
        new_platform="",
        base_branch="autoland",
        new_branch="autoland",
        base_revision="",
        new_revision="",
        depth=None,
        search_crons=True,
        overwrite=True,
        skip_download=False,
        absolute_diff_threshold=0.02,
        pvalue_threshold=0.05,
    ):
        """
        This method is the main method of the class and uses all other methods to make the actual side-by-side comparison.

        :param test_name: The name of the test task to get videos from.
        :param new_test_name: The name of the test task to get videos from in the new revision.
        :param platform: Platform to return results for.
        :param new_platform: Platform to return results for in the new revision.
        :param vismetPath: Paths to visualmetrics.py for step chart generation.
        :param metric: Metric to use for side-by-side comparison.
        :param base_branch: Branch to search for the base revision.
        :param new_branch: Branch to search for the new revision.
        :param base_revision: The base revision to compare a new revision to
        :param new_revision: The base revision to compare a new revision to.
        :param search_crons: If set, we will search for the tasks within the cron jobs as well.
        :param cold: If set, we'll only look at cold pageload tests.
        :param warm: If set, we'll only look at warm pageload tests.
        :param most_similar: If set, we'll search for a video pairing that is the most similar.
        :param overwrite: If set, the downloaded task group data will be deleted before it gets re-downloaded.
        :param skip_download: If set, we won't try to download artifacts again and we'll try using what already exists in the output folder.
        :param original: If set, use the original videos in the side-by-side instead of the postprocessed videos.
        :return:
        """
        # Parse the given output argument
        output = pathlib.Path(self._output_dir)
        if not output.suffixes:
            output.mkdir(parents=True, exist_ok=True)
        else:
            filename = output.name
            output = output.parents[0]
            output.mkdir(parents=True, exist_ok=True)

        # Make a cache for the push revision downloads which can require
        # a lot of artifacts to find enough data
        self._cache = pathlib.Path(output, ".cache")
        self._cache.mkdir(exist_ok=True)

        revisions = [
            (base_revision, base_branch, test_name, platform),
            (new_revision, new_branch, new_test_name, new_platform),
        ]
        if depth is not None:
            if base_branch != new_branch:
                raise BranchMismatchError(
                    "Can't compare using depth across multiple branches! "
                    f"{base_branch} != {new_branch}"
                )
            push_revisions = self._gather_revisions(
                base_revision, new_revision, base_branch, depth
            )

            revisions = list(
                zip(
                    push_revisions,
                    [base_branch] * len(push_revisions),
                    [test_name] * len(push_revisions),
                    [platform] * len(push_revisions),
                )
            )

        return self.compare_revisions(
            revisions,
            output,
            overwrite,
            skip_download,
            absolute_diff_threshold=absolute_diff_threshold,
            pvalue_threshold=pvalue_threshold,
        )

    def compare_revisions(
        self,
        revisions,
        output,
        overwrite,
        skip_download,
        absolute_diff_threshold=0.02,
        pvalue_threshold=0.05,
    ):
        """Compare multiple revisions together.

        Revisions must be ordered with the oldest first (base),
        and newest last (new).
        """

        # Get the task group IDs for the revisions
        all_revision_ids = []
        for revision, branch, _, _ in revisions:
            all_revision_ids.append(
                find_task_group_id(
                    revision, branch, search_crons=True, cache=self._cache
                )
            )

        all_revision_dirs = [
            [pathlib.Path(output, revid) for revid in revision_ids]
            for revision_ids in all_revision_ids
        ]

        if overwrite:
            for task_dirs in all_revision_dirs:
                for task_dir in task_dirs:
                    if task_dir.exists():
                        print("Removing existing task group folder: %s" % str(task_dir))
                        shutil.rmtree(str(task_dir))

        # Download the artifacts
        new_revisions = []
        all_revision_data_paths = []
        for i, (revision, _, test_name, platform) in enumerate(revisions):
            revision_ids = all_revision_ids[i]
            if skip_download and not overwrite:
                try:
                    data_paths = self._search_for_paths(revision_ids, "perfherder-data")
                except (AttributeError, FileNotFoundError) as e:
                    print("No data was found for revision %s" % revision)
                    data_paths = []
            else:
                data_paths = []
                for revision_id in revision_ids:
                    if data_paths:
                        break
                    artifact_downloader(
                        revision_id,
                        output_dir=str(output),
                        test_suites=[test_name],
                        platform=platform,
                        artifact_to_get=["perfherder-data"],
                        unzip_artifact=False,
                        download_failures=False,
                        ingest_continue=False,
                    )
                    try:
                        data_paths = self._search_for_paths(
                            [revision_id], "perfherder-data"
                        )
                    except (AttributeError, FileNotFoundError) as e:
                        print("No data was found for revision %s" % revision)
                        data_paths = []
            if data_paths:
                new_revisions.append(revision)
                all_revision_data_paths.append(data_paths)

        if len([paths for paths in all_revision_data_paths if paths]) < 2:
            print("All paths found: %s" % all_revision_data_paths)
            raise NoDataError("Not enough artifacts downloaded, can't compare! ")

        all_revision_data = []
        for revision_data_paths in all_revision_data_paths:
            all_revision_data.append(
                self._open_and_organize_perfherder(revision_data_paths)
            )

        # We have all the data downloaded, now organize it into lists or metrics
        # and detect any changes.
        all_metric_names = {"warm": {}, "cold": {}}
        for data in all_revision_data:
            for pl_type in ("warm", "cold"):
                for metric in data[pl_type]:
                    all_metric_names[pl_type].setdefault(metric, 0)
                    all_metric_names[pl_type][metric] += 1

        use_step_detector = False
        data_org_by_metric = {"warm": {}, "cold": {}}
        revisions_org_by_metric = {"warm": {}, "cold": {}}
        for i, data in enumerate(all_revision_data):
            for pl_type in ("warm", "cold"):
                for metric in data[pl_type]:
                    if all_metric_names[pl_type][metric] != len(all_revision_data):
                        # This metric doesn't exist in one, or more revisions but
                        # other metrics do exist
                        print(
                            "Missing data for metric %s, found %s, expected %s"
                            % (
                                metric,
                                all_metric_names[pl_type][metric],
                                all_revision_data,
                            )
                        )
                        continue

                    if use_step_detector:
                        data_org_by_metric[pl_type].setdefault(metric, []).extend(
                            data[pl_type][metric]
                        )
                        revisions_org_by_metric[pl_type].setdefault(metric, []).extend(
                            [new_revisions[i]] * len(data[pl_type][metric])
                        )
                    else:
                        data_org_by_metric[pl_type].setdefault(metric, []).append(
                            data[pl_type][metric]
                        )
                        revisions_org_by_metric[pl_type].setdefault(metric, []).append(
                            new_revisions[i]
                        )

        results = {"warm": {}, "cold": {}}
        for pl_type in ("warm", "cold"):
            for metric in data_org_by_metric[pl_type]:
                print("Using non-sliding window method")
                segments = [0]
                diffs = [0]
                prev_data_group = data_org_by_metric[pl_type][metric][0]
                for i, data_group in enumerate(
                    data_org_by_metric[pl_type][metric][1:], 1
                ):
                    m_score = scipy.stats.mannwhitneyu(
                        prev_data_group,
                        data_group,
                        alternative="two-sided",
                    )
                    print("\nCurrent score: ", m_score)
                    print("Metric: ", pl_type, metric)
                    print("Revision: ", revisions_org_by_metric[pl_type][metric][i])

                    window = 0
                    while (
                        (window + 1) <= MAX_WINDOW
                        and m_score.pvalue < 0.06
                        and m_score.pvalue > 0.001
                    ):
                        # For scores that are borderline, try to improve it by adding data to both sides.
                        # At the moment, this is very experimental, but it theoretically can improve, and
                        # has improved results already.
                        window += 1
                        print("Recomputing %s" % str(m_score))
                        if i - (window + 1) >= 0:
                            prev_data_group.extend(
                                data_org_by_metric[pl_type][metric][
                                    i - (window + 1)
                                ]
                            )
                        if i + window < len(data_org_by_metric[pl_type][metric]):
                            data_group.extend(
                                data_org_by_metric[pl_type][metric][i + window]
                            )

                        m_score = scipy.stats.mannwhitneyu(
                            prev_data_group,
                            data_group,
                            alternative="two-sided",
                        )
                        print("Recomputed to %s" % str(m_score))
                    print("New score: ", m_score)

                    if m_score.pvalue <= pvalue_threshold:
                        # Check if the differences in the median cross the threshold
                        prev_med = np.median(prev_data_group)
                        prev_std = np.std(prev_data_group)
                        curr_med = np.median(data_group)

                        # MWU results is U1, use effect size from here:
                        # https://en.wikipedia.org/wiki/Mann%E2%80%93Whitney_U_test#Rank-biserial_correlation
                        effect_size = (2 * m_score.statistic) / (
                            len(prev_data_group) * len(data_group)
                        )

                        # Get a threshold to apply based on the noise, and
                        # then check if against the %-difference between
                        # the previous and current median. Medians are used here
                        # since MWU is based on them as well.
                        fuzz = absolute_diff_threshold
                        threshold = (prev_std + (prev_med * fuzz)) / prev_med
                        diff = abs(prev_med - curr_med) / prev_med
                        if diff > threshold:
                            print(
                                f"**** Found difference:",
                                threshold,
                                diff,
                                effect_size,
                                "*******",
                            )
                            segments.append(i)
                            diffs.append(diff)

                    prev_data_group = data_group

                results[pl_type][metric] = segments, diffs

        all_changed_revisions = set()
        changed_metric_revisions = {"warm": {}, "cold": {}}
        for pl_type in ("warm", "cold"):
            for metric in results[pl_type]:
                segments, diffs = results[pl_type][metric]
                if len(revisions) > 2:
                    if len(segments) <= 2:
                        # There was no regression/improvment
                        continue

                    for changed_index in segments[1:]:
                        revision = revisions_org_by_metric[pl_type][metric][changed_index]
                        changed_metric_revisions[pl_type].setdefault(metric, {}).setdefault(
                            revision, []
                        ).append(diffs[changed_index])
                        all_changed_revisions |= set([revision])
                else:
                    # For two revisions, it doesn't matter how they're ordered to
                    # trigger a detected change.
                    for changed_index in segments[1:]:
                        revision = revisions_org_by_metric[pl_type][metric][changed_index]
                        changed_metric_revisions[pl_type].setdefault(metric, {}).setdefault(
                            revision, []
                        ).append(diffs[changed_index])
                        all_changed_revisions |= set([revision])                   

        print("Changed, and ordered revisions:")
        for pl_type in ("warm", "cold"):
            for metric in results[pl_type]:
                print(f"{pl_type} {metric}")
                if metric not in changed_metric_revisions[pl_type]:
                    continue
                for revision, _, _, _ in revisions:
                    if revision in changed_metric_revisions[pl_type][metric]:
                        print(
                            f"{revision} **CHANGED** (%-DIFFERENCE: "
                            f"{changed_metric_revisions[pl_type][metric][revision]})"
                        )
                    else:
                        print(f"{revision} NO-CHANGE")

        print("Overall result:")
        for revision, _, _, _ in revisions:
            if revision in all_changed_revisions:
                print(f"{revision} **CHANGED**")
            else:
                print(f"{revision} NO-CHANGE")

        return all_changed_revisions, changed_metric_revisions


if __name__ == "__main__":
    detector = ChangeDetector("~/detector-testing/")
    detector.detect_changes(
        test_name="browsertime-tp6m-geckoview-sina-nofis",
        platform="test-android-hw-a51-11-0-aarch64-shippable-qr/opt",
        base_revision="9b8e7381f776fa84a55e0a764c2ed4dad82316c5",
        new_revision="b1dad9107c06df86f3107e58c27d88a50b6c53c1",
        # Depth of -1 means auto-computed (everything in between the two given revisions),
        # None is direct comparisons, anything else uses the new_revision as a start
        # and goes backwards from there.
        depth=-1,
        skip_download=True,
        overwrite=False,
    )
