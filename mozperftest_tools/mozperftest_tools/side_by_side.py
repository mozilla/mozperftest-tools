#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Used to produce comparisons of browsertime videos between a base
and a new revision.
"""

import cv2
import gc
import numpy as np
import os
import pathlib
import json
import shutil
import subprocess

from scipy.stats import spearmanr

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

from mozperftest_tools.utils.artifact_downloader import artifact_downloader
from mozperftest_tools.utils.task_processor import get_task_data_paths, match_vismets_with_videos, sorted_nicely

from mozperftest_tools.utils.utils import write_same_line, finish_same_line, find_task_group_id


class SideBySide:
    def __init__(self, output_dir, executable="ffmpeg"):
        self.executable = executable
        self._common_options = [
            "-map",
            "[vid]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
        ]
        self._vid_paths = {
            "before_vid": pathlib.Path(output_dir, "before.mp4"),
            "after_vid": pathlib.Path(output_dir, "after.mp4"),
            "before_cut_vid": pathlib.Path(output_dir, "before-cut.mp4"),
            "after_cut_vid": pathlib.Path(output_dir, "after-cut.mp4"),
            "before_rs_vid": pathlib.Path(output_dir, "before-rs.mp4"),
            "after_rs_vid": pathlib.Path(output_dir, "after-rs.mp4")
        }
        self._overlay_text = (
                "fps=fps=60,drawtext=text={}\\\\ :fontsize=(h/20):fontcolor=black:y=10:"
                + "timecode=00\\\\:00\\\\:00\\\\:00:rate=60*1000/1001:fontcolor=white:x=(w-tw)/2:"
                + "y=10:box=1:boxcolor=0x00000000@1[vid]"
        )
        self._common_options = [
            "-map",
            "[vid]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
        ]
        self._output_dir = output_dir

    def generate_step_chart(self, oldvid, newvid, vismetPath, prefix, metric, output):
        print("Generating step chart for %s" % metric)

        try:
            from matplotlib import pyplot as plt
        except Exception:
            print("Please install matplotlib before using step charts")
            raise

        oldvid_metrics = json.loads(
            subprocess.check_output(
                [
                    "python",
                    vismetPath,
                    "--orange",
                    "--perceptual",
                    "--contentful",
                    "--force",
                    "--renderignore",
                    "5",
                    "--json",
                    "--viewport",
                    "--video",
                    oldvid,
                ]
            )
        )

        newvid_metrics = json.loads(
            subprocess.check_output(
                [
                    "python",
                    vismetPath,
                    "--orange",
                    "--perceptual",
                    "--contentful",
                    "--force",
                    "--renderignore",
                    "5",
                    "--json",
                    "--viewport",
                    "--video",
                    newvid,
                ]
            )
        )

        if metric.lower() == "perceptualspeedindex":
            progress = "PerceptualSpeedIndexProgress"
            metricName = "PerceptualSpeedIndex"
        elif metric.lower() == "contentfulspeedindex":
            progress = "ContentfulSpeedIndexProgress"
            metricName = "ContentfulSpeedIndex"
        else:
            progress = "VisualProgress"
            metricName = "SpeedIndex"

        x = []
        y = []
        for pt in oldvid_metrics[progress].split(","):
            x_val, y_val = pt.split("=")
            x.append(int(x_val))
            y.append(int(y_val))
        plt.step(x, y, label="Before (%d)" % oldvid_metrics[metricName])

        x = []
        y = []
        for pt in newvid_metrics[progress].split(","):
            x_val, y_val = pt.split("=")
            x.append(int(x_val))
            y.append(int(y_val))
        plt.step(x, y, label="After (%d)" % newvid_metrics[metricName])

        plt.legend(loc="lower right")
        plt.title("%s %s" % (prefix.rstrip("_"), metricName))
        plt.savefig(str(output / "%s-%s-step.png" % (prefix.rstrip("_"), metric)))
        plt.clf()

    def _search_for_paths(self, rev_ids, artifact, open_data=False):
        found_paths = []
        for rev_id in rev_ids:
            if found_paths:
                break
            # Get the paths to the directory holding the artifacts, the 0
            # index is because we are only looking at one suite here.
            found_paths = list(
                get_task_data_paths(rev_id, str(self._output_dir), artifact=artifact).values()
            )
            if len(found_paths) > 0:
                found_paths = found_paths[0]
            else:
                found_paths = []
        return found_paths

    def _find_videos_with_retriggers(self, artifact_dirs, original=False):
        results = {"cold": [], "warm": []}

        for artifact_dir in artifact_dirs:
            videos = self._find_videos(artifact_dir, original=original)
            results["cold"].extend(videos["cold"])
            results["warm"].extend(videos["warm"])

        return results

    def _find_videos(self, artifact_dir, original=False):
        # Find the cold/warm browsertime.json files
        cold_path = ""
        warm_path = ""
        for path in pathlib.Path(artifact_dir).rglob("*-browsertime.json"):
            if "profiling" not in path.parts:
                if "cold" in str(path):
                    cold_path = path
                elif "warm" in str(path):
                    warm_path = path
        if not cold_path:
            raise Exception("Cannot find a browsertime.json file for the cold pageloads.")
        if not warm_path:
            raise Exception("Cannot find a browsertime.json file for the warm pageloads.")

        with cold_path.open() as f:
            cold_data = json.load(f)
        with warm_path.open() as f:
            warm_data = json.load(f)

        return {
            "cold": [
                str(pathlib.Path(cold_path.parents[0], file)).replace(".mp4", "-original.mp4")
                if original
                else str(pathlib.Path(cold_path.parents[0], file))
                for file in cold_data[0]["files"]["video"]
            ],
            "warm": [
                str(pathlib.Path(warm_path.parents[0], file)).replace(".mp4", "-original.mp4")
                if original
                else str(pathlib.Path(warm_path.parents[0], file))
                for file in warm_data[0]["files"]["video"]
            ],
        }

    def _open_and_organize_perfherder(self, files, metric):
        def _open_perfherder(filen):
            with open(filen) as f:
                return json.load(f)

        res = {"cold": [], "warm": []}

        for filen in files:
            data = _open_perfherder(filen)

            for suite in data["suites"]:
                pl_type = "warm"
                if "cold" in suite["extraOptions"]:
                    pl_type = "cold"

                for subtest in suite["subtests"]:
                    if subtest["name"].lower() != metric.lower():
                        continue
                    # Each entry here will be a single retrigger of
                    # the test for the requested metric (ordered
                    # based on the `files` ordering)
                    res[pl_type].append(subtest)

        return res

    def _find_lowest_similarity(self, base_videos, new_videos, output, prefix, most_similar=False):
        def _open_data(file):
            return cv2.VideoCapture(str(file))

        return self.get_similarity(
            [{"data": _open_data(str(f)), "path": str(f)} for f in base_videos],
            [{"data": _open_data(str(f)), "path": str(f)} for f in new_videos],
            output,
            prefix,
            most_similar=most_similar,
        )

    def find_closest_videos(
        self, base_videos, base_vismet, new_videos, new_vismet, vismetPath, output, prefix, metric
    ):
        base_btime_id = ""
        base_min_idx = None

        # Recalculate median for all values, then find the new video
        # by searching in the list for it (use index) to determine
        # the matching video.
        replicates = []
        for retrigger in base_vismet:
            replicates.extend(retrigger["replicates"])
        median_value = np.median(replicates)

        # Find the video which most closely matches the average
        diff = [abs(replicate - median_value) for replicate in replicates]
        min_diff = min(diff)
        base_min_idx = diff.index(min_diff)

        print(
            "BASE: metric=%s prefix=%s mean=%d closest=%d index=%d"
            % (
                metric,
                prefix,
                median_value,
                min_diff,
                base_min_idx,
            )
        )

        replicates = []
        for retrigger in new_vismet:
            replicates.extend(retrigger["replicates"])
        median_value = np.median(replicates)

        # Find the video which most closely matches the average
        diff = [abs(replicate - median_value) for replicate in replicates]
        min_diff = min(diff)
        new_min_idx = diff.index(min_diff)

        print(
            "NEW: metric=%s prefix=%s mean=%d closest=%d index=%d"
            % (
                metric,
                prefix,
                median_value,
                min_diff,
                new_min_idx,
            )
        )

        oldvid = base_videos[base_min_idx]
        oldvid = oldvid.replace("\\", "/")
        oldvidnewpath = str(pathlib.Path(output, "%sold_video.mp4" % prefix))
        shutil.copyfile(oldvid, oldvidnewpath)

        newvid = new_videos[new_min_idx]
        newvid = newvid.replace("\\", "/")
        newvidnewpath = str(pathlib.Path(output, "%snew_video.mp4" % prefix))
        shutil.copyfile(newvid, newvidnewpath)

        if vismetPath:
            generate_step_chart(oldvid, newvid, vismetPath, prefix, metric, output)

        # The index values used here are for frame selection during video editing.
        # We use 0 to select all frames.
        return {
            "oldvid": oldvidnewpath,
            "oldvid_ind": 0,
            "newvid": newvidnewpath,
            "newvid_ind": 0,
        }

    def get_similarity(
            self, old_videos_info, new_videos_info, output, prefix="", most_similar=False
    ):
        """Calculates a similarity score for two groupings of videos.

        The technique works as follows:
            2. For each UxV video pairings, build a cross-correlation matrix:
                1. Get each of the videos and calculate their histograms
                   across the full videos.
                2. Calculate the correlation coefficient between these two.
            3. Average the cross-correlation matrix to obtain the score.

        Args:
            old_videos: List of old videos.
            new_videos: List of new videos (from this task).
            output: Location to output videos with low similarity scores.
            prefix: Prefix a string to the output.
        Returns:
            A dictionary containing the worst pairing and the 3D similarity score.
        """

        try:
            from matplotlib import pyplot as plt
        except Exception:
            print("Please install matplotlib before using the similarity metric")
            raise

        def _get_frames(video):
            """Gets all frames from a video into a list."""
            allframes = []
            orange_pixind = 0
            orange_frameind = 0
            frame_count = 0
            check_for_orange = True
            while video.isOpened():
                ret, frame = video.read()
                if ret:
                    # Convert to gray to simplify the process
                    allframes.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))

                    # Check if it's orange still
                    if check_for_orange:
                        frame = allframes[-1]
                        histo, _, _ = plt.hist(np.asarray(frame).flatten(), bins=255)

                        maxi = np.argmax(histo)
                        if not orange_pixind:
                            if maxi > 130:
                                continue
                            orange_pixind = maxi
                        elif maxi == orange_pixind:
                            orange_frameind = frame_count
                        else:
                            check_for_orange = False

                    frame_count += 1

                else:
                    video.release()
                    break

            return allframes[orange_frameind:], orange_frameind

        nhists = []

        old_videos = [entry["data"] for entry in old_videos_info]
        new_videos = [entry["data"] for entry in new_videos_info]

        new_orange_frameinds = []
        old_orange_frameinds = []
        total_vids = min(len(old_videos), len(new_videos))
        xcorr = np.zeros((total_vids, total_vids))

        for i in range(total_vids):
            datao, old_orange_frameind = _get_frames(old_videos[i])
            datao = np.asarray(datao)
            old_orange_frameinds.append(old_orange_frameind)

            histo, _, _ = plt.hist(datao.flatten(), bins=255)
            plt.clf()
            gc.collect()

            for j in range(total_vids):
                write_same_line("Comparing old video %s to new video %s" % (i + 1, j + 1))
                if i == 0:
                    # Only calculate the histograms once; it takes time
                    datan, new_orange_frameind = _get_frames(new_videos[j])
                    datan = np.asarray(datan)
                    new_orange_frameinds.append(new_orange_frameind)

                    histn, _, _ = plt.hist(datan.flatten(), bins=255)
                    plt.clf()
                    gc.collect()

                    nhists.append(histn)
                else:
                    histn = nhists[j]

                rho, _ = spearmanr(histo, histn)

                xcorr[i, j] = rho

        finish_same_line()

        similarity = np.nanmean(xcorr)

        print("Average 3D similarity: %s" % str(np.round(similarity, 5)))

        if most_similar:
            inds = np.unravel_index(np.argmax(xcorr, axis=None), xcorr.shape)
        else:
            inds = np.unravel_index(np.argmin(xcorr, axis=None), xcorr.shape)

        oldvid = old_videos_info[inds[0]]["path"]
        oldvidnewpath = str(pathlib.Path(output, "%sold_video.mp4" % prefix))
        shutil.copyfile(oldvid, oldvidnewpath)

        newvid = new_videos_info[inds[1]]["path"]
        newvidnewpath = str(pathlib.Path(output, "%snew_video.mp4" % prefix))
        shutil.copyfile(newvid, newvidnewpath)

        return {
            "sim3": np.round(similarity, 5),
            "oldvid": oldvidnewpath,
            "oldvid_ind": old_orange_frameinds[inds[0]],
            "newvid": newvidnewpath,
            "newvid_ind": new_orange_frameinds[inds[1]],
        }

    def clean_videos(self, videos=[]):
        for v in videos:
            if v.exists():
                v.unlink()

    def cut(self, base_video, cut_vid, base_ind):
        self.clean_videos(videos=[cut_vid])
        subprocess.check_output(
            ["ffmpeg", "-i", str(base_video), "-vf", "select=gt(n\\,%s)" % base_ind]
            + [str(cut_vid)]
        )
        self.clean_videos(videos=[pathlib.Path(self._output_dir, base_video)])

    # Recalculate median for all values, then find the new video
    # by searching in the list for it (use index) to determine
    # the matching video.
    replicates = []
    def resample(self, cut_vid, rs_vid):
        self.clean_videos(videos=[rs_vid])
        subprocess.check_output(
            ["ffmpeg", "-i", str(cut_vid), "-filter:v", "fps=fps=60"]
            + [str(rs_vid)]
        )
        self.clean_videos(videos=[cut_vid])

    def filter_complex(self, rs_vid, vid, overlay_text=""):
        self.clean_videos(videos=[vid])
        subprocess.check_output(
            [
                "ffmpeg",
                "-i",
                str(rs_vid),
                "-filter_complex",
                self._overlay_text.format(overlay_text),
            ]
            + self._common_options
            + [str(vid)]
        )
        self.clean_videos(videos=[rs_vid])

    def generate(self, before_vid, after_vid, filename):
        self.clean_videos(videos=[pathlib.Path(self._output_dir, filename)])
        subprocess.check_output(
            [
                "ffmpeg",
                "-i",
                str(before_vid),
                "-i",
                str(after_vid),
                "-filter_complex",
                "[0:v]pad=iw*2:ih[int];[int][1:v]overlay=W/2:0[vid]",
            ]
            + self._common_options
            + [str(pathlib.Path(self._output_dir, filename))]
        )
        self.clean_videos(videos=[before_vid, after_vid])

    def convert_to_gif(self, path_to_mp4, path_to_gif, slow_motion=False):
        path_to_gif = str(path_to_gif)
        fps = 30
        # Use slow motion for more subtle differences
        if slow_motion:
            fps = 80
            path_to_gif = path_to_gif.replace(".gif", "-slow-motion.gif")

        # Generate palette for a better quality
        subprocess.check_output(
            [
                "ffmpeg",
                "-i",
                str(path_to_mp4),
                "-vf",
                f"fps={fps},scale=1024:-1:flags=lanczos,palettegen",
                "-y",
            ]
            + [path_to_gif.replace(".gif", "-palette.gif")]
        )

        subprocess.check_output(
            [
                "ffmpeg",
                "-i",
                str(path_to_mp4),
                "-i",
                path_to_gif.replace(".gif", "-palette.gif"),
                "-filter_complex",
                f"fps={fps},scale=1024:-1:flags=lanczos[x];[x][1:v]paletteuse",
                "-loop",
                "-1",
            ]
            + [str(path_to_gif)]
        )
        subprocess.check_output(["rm", path_to_gif.replace(".gif", "-palette.gif")])

        return str(path_to_gif)

    def build_side_by_side(self, base_video, new_video, base_ind, new_ind, filename):
        # Cut the videos
        self.cut(base_video, self._vid_paths["before_cut_vid"], base_ind)
        self.cut(new_video, self._vid_paths["after_cut_vid"], new_ind)

        # Resample
        self.resample(self._vid_paths["before_cut_vid"], self._vid_paths["before_rs_vid"])
        self.resample(self._vid_paths["after_cut_vid"], self._vid_paths["after_rs_vid"])

        # Generate the before and after videos
        self.filter_complex(self._vid_paths["before_rs_vid"], self._vid_paths["before_vid"], "BEFORE")
        self.filter_complex(self._vid_paths["after_rs_vid"], self._vid_paths["after_vid"], "AFTER")
        self.generate(self._vid_paths["before_vid"], self._vid_paths["after_vid"], filename)

    def run(self, test_name="", new_test_name="", platform="", new_platform="", vismetPath="", metric="speedindex", base_branch="autoland", new_branch="autoland", base_revision="", new_revision="", cold="", warm="", most_similar="", original=False, search_crons=False, overwrite=True, skip_download=False, skip_slow_gif=False):
        '''
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
        '''

        if shutil.which("ffmpeg") is None:
            raise Exception(
                "Cannot find ffmpeg in path! Please install it before continuing."
            )
        if vismetPath and not pathlib.Path(vismetPath).exists():
            raise Exception("Cannot find the vismet script at: %s" % vismetPath)
        if metric != "similarity" and skip_download:
            print(
                "WARNING: Downloads will not be skipped as you are using something other "
                "than the similarity metric (only supported for this metric)."
            )

        # Parse the given output argument
        filename = "side-by-side.mp4"
        output = pathlib.Path(self._output_dir)
        if output.exists() and output.is_file():
            print("Deleting existing output file...")
            output.unlink()
        elif not output.suffixes:
            output.mkdir(parents=True, exist_ok=True)
        else:
            filename = output.name
            output = output.parents[0]
            output.mkdir(parents=True, exist_ok=True)

        # Make sure we remove the old side-by-side visualization
        # for the FFMPEG operations
        cold_path = pathlib.Path(output, "cold-" + filename)
        warm_path = pathlib.Path(output, "warm-" + filename)
        if cold_path.exists():
            cold_path.unlink()
        if warm_path.exists():
            warm_path.unlink()

        # Get the task group IDs for the revisions
        base_revision_ids = find_task_group_id(
            base_revision, base_branch, search_crons=search_crons
        )
        new_revision_ids = find_task_group_id(
            new_revision, new_branch, search_crons=search_crons
        )

        base_task_dirs = [pathlib.Path(output, revid) for revid in base_revision_ids]
        new_task_dirs = [pathlib.Path(output, revid) for revid in new_revision_ids]

        if overwrite:
            for task_dir in base_task_dirs + new_task_dirs:
                if task_dir.exists():
                    print("Removing existing task group folder: %s" % str(task_dir))
                    shutil.rmtree(str(task_dir))

        # Download the artifacts
        if not skip_download:
            print(
                f"\nDownloading data for base revision: {base_revision}, "
                f"task-group-ids: {base_revision_ids}\n"
            )
            base_paths = []
            for base_revision_id in base_revision_ids:
                if base_paths:
                    break
                artifact_downloader(
                    base_revision_id,
                    output_dir=str(output),
                    test_suites=[test_name],
                    platform=platform,
                    artifact_to_get=["browsertime-results", "perfherder-data"],
                    unzip_artifact=True,
                    download_failures=False,
                    ingest_continue=False,
                )
                base_paths = self._search_for_paths([base_revision_id], "browsertime-results")
                base_vismet = self._search_for_paths([base_revision_id], "perfherder-data")

            print(
                f"\nDownloading data for new revision: {new_revision}, "
                f"task-group-ids: {new_revision_ids}\n"
            )
            new_paths = []
            for new_revision_id in new_revision_ids:
                if new_paths:
                    break
                artifact_downloader(
                    new_revision_id,
                    output_dir=str(output),
                    test_suites=[new_test_name or test_name],
                    platform=new_platform or platform,
                    artifact_to_get=["browsertime-results", "perfherder-data"],
                    unzip_artifact=True,
                    download_failures=False,
                    ingest_continue=False,
                )
                new_paths = self._search_for_paths([new_revision_id], "browsertime-results")
                new_vismet = self._search_for_paths([new_revision_id], "perfherder-data")
        else:
            base_paths = self._search_for_paths(base_revision_ids, "browsertime-results")
            base_vismet = self._search_for_paths(base_revision_ids, "perfherder-data")

            new_paths = self._search_for_paths(new_revision_ids, "browsertime-results")
            new_vismet = self._search_for_paths(new_revision_ids, "perfherder-data")

        # Make sure we only downloaded one task
        failure_msg = (
                "Not enough artifacts downloaded for %s, can't compare! "
                + "Found paths: %s \nTry using --search-crons if you are sure the task exists."
        )
        if not base_paths:
            raise Exception(failure_msg % (base_revision, base_paths))
        if not new_paths:
            raise Exception(failure_msg % (new_revision, new_paths))

        # Gather the videos and split them between warm and cold
        base_videos = self._find_videos_with_retriggers(base_paths, original=original)
        new_videos = self._find_videos_with_retriggers(new_paths, original=original)

        # If we are looking at something other than similarity,
        # prepare the data for this (open, and split between
        # cold and warm)
        if metric != "similarity":
            print("Opening, and organizing perfherder data...")
            org_base_vismet = self._open_and_organize_perfherder(base_vismet, metric)
            org_new_vismet = self._open_and_organize_perfherder(new_vismet, metric)

            if (not org_new_vismet["cold"] and not org_new_vismet["warm"]) or (
                not org_base_vismet["cold"] and not org_base_vismet["warm"]
            ):
                raise Exception("Could not find any data with the metric: %s" % metric)

        run_cold = cold
        run_warm = warm
        if not cold and not warm:
            run_cold = True
            run_warm = True

        # Find the worst video pairing for cold and warm
        print("Starting comparisons, this may take a few minutes")
        if run_cold:
            print("Running comparison for cold pageloads...")
            if metric == "similarity":
                cold_pairing = self._find_lowest_similarity(
                    base_videos["cold"],
                    new_videos["cold"],
                    str(output),
                    "cold_",
                    most_similar=most_similar,
                )
            else:
                cold_pairing = self.find_closest_videos(
                    base_videos["cold"],
                    org_base_vismet["cold"],
                    new_videos["cold"],
                    org_new_vismet["cold"],
                    vismetPath,
                    str(output),
                    "cold_",
                    metric,
                )
        if run_warm:
            gc.collect()
            print("Running comparison for warm pageloads...")
            if metric == "similarity":
                warm_pairing = self._find_lowest_similarity(
                    base_videos["warm"],
                    new_videos["warm"],
                    str(output),
                    "warm_",
                    most_similar=most_similar,
                )
            else:
                warm_pairing = self.find_closest_videos(
                    base_videos["warm"],
                    org_base_vismet["warm"],
                    new_videos["warm"],
                    org_new_vismet["warm"],
                    vismetPath,
                    str(output),
                    "warm_",
                    metric,
                )

        # Build up the side-by-side comparisons now
        if run_cold:
            output_name = str(pathlib.Path(output, "cold-" + filename))
            self.build_side_by_side(
                cold_pairing["oldvid"],
                cold_pairing["newvid"],
                cold_pairing["oldvid_ind"],
                cold_pairing["newvid_ind"],
                "cold-" + filename,
            )
            print("Successfully built a side-by-side cold comparison: %s" % output_name)

            gif_output_name = pathlib.Path(
                output, "cold-" + filename.replace(".mp4", ".gif")
            )
            gif_output_name = self.convert_to_gif(output_name, gif_output_name)
            print(
                "Successfully converted the side-by-side cold comparison to gif: %s"
                % gif_output_name
            )
            print(
                "Successfully converted the side-by-side cold comparison to slow motion gif: %s" % gif_output_name)

            if not skip_slow_gif:
                gif_output_name = self.convert_to_gif(
                    output_name, gif_output_name, slow_motion=True
                )
                print(
                    "Successfully converted the side-by-side cold comparison to slow motion gif: %s"
                    % gif_output_name
                )
        if run_warm:
            output_name = str(pathlib.Path(output, "warm-" + filename))
            self.build_side_by_side(
                warm_pairing["oldvid"],
                warm_pairing["newvid"],
                warm_pairing["oldvid_ind"],
                warm_pairing["newvid_ind"],
                "warm-" + filename,
            )
            print("Successfully built a side-by-side warm comparison: %s" % output_name)

            gif_output_name = pathlib.Path(
                output, "warm-" + filename.replace(".mp4", ".gif")
            )
            gif_output_name = self.convert_to_gif(output_name, gif_output_name)
            print(
                "Successfully converted the side-by-side warm comparison to gif: %s"
                % gif_output_name
            )

            if not skip_slow_gif:
                gif_output_name = self.convert_to_gif(
                    output_name, gif_output_name, slow_motion=True
                )
                print(
                    "Successfully converted the side-by-side warm comparison to slow motion gif: %s"
                    % gif_output_name
                )
