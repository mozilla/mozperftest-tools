#!/usr/bin/python3
"""
Used to produce comparisons of browsertime videos between a base
and a new revision.
"""
import argparse
import cv2
import gc
import numpy as np
import os
import pathlib
import json
import shutil
import subprocess

from matplotlib import pyplot as plt
from scipy.stats import spearmanr
from sys import stdout
from time import sleep

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib import urlencode, urlretrieve
    from urllib2 import urlopen

from artifact_downloader import artifact_downloader
from task_processor import get_task_data_paths


TASK_IDS = (
    "https://firefox-ci-tc.services.mozilla.com/api/index/v1/tasks/"
    + "gecko.v2.{}.revision.{}.taskgraph"
)

TASK_INFO = "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/{}"


def side_by_side_parser():
    parser = argparse.ArgumentParser(
        "This tool can be used to generate a side-by-side visualization of two videos. "
        "When using this tool, make sure that the `--test-name` is an exact match, i.e. "
        "if you are comparing  the task `test-linux64-shippable-qr/opt-browsertime-tp6-firefox-linkedin-e10s` "
        "between two revisions, then use `browsertime-tp6-firefox-linkedin-e10s` as the suite name "
        "and `test-linux64-shippable-qr/opt` as the platform."
    )
    parser.add_argument(
        "--base-revision",
        type=str,
        required=True,
        help="The base revision to compare a new revision to.",
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default="autoland",
        help="Branch to search for the base revision.",
    )
    parser.add_argument(
        "--new-revision",
        type=str,
        required=True,
        help="The base revision to compare a new revision to.",
    )
    parser.add_argument(
        "--new-branch",
        type=str,
        default="autoland",
        help="Branch to search for the new revision.",
    )
    parser.add_argument(
        "--test-name",
        "--base-test-name",
        type=str,
        required=True,
        dest="test_name",
        help="The name of the test task to get videos from.",
    )
    parser.add_argument(
        "--new-test-name",
        type=str,
        default=None,
        help="The name of the test task to get videos from in the new revision.",
    )
    parser.add_argument(
        "--platform",
        "--base-platform",
        type=str,
        required=True,
        dest="platform",
        help="Platform to return results for.",
    )
    parser.add_argument(
        "--new-platform",
        type=str,
        default=None,
        help="Platform to return results for in the new revision.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="If set, the downloaded task group data will be deleted before "
        + "it gets re-downloaded.",
    )
    parser.add_argument(
        "--cold",
        action="store_true",
        default=False,
        help="If set, we'll only look at cold pageload tests.",
    )
    parser.add_argument(
        "--warm",
        action="store_true",
        default=False,
        help="If set, we'll only look at warm pageload tests.",
    )
    parser.add_argument(
        "--most-similar",
        action="store_true",
        default=False,
        help="If set, we'll search for a video pairing that is the most similar.",
    )
    parser.add_argument(
        "--search-crons",
        action="store_true",
        default=False,
        help="If set, we will search for the tasks within the cron jobs as well. ",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        default=False,
        help="If set, we won't try to download artifacts again and we'll "
        + "try using what already exists in the output folder.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getcwd(),
        help="This is where the data will be saved. Defaults to CWD. "
        + "You can include a name for the file here, otherwise it will "
        + "default to side-by-side.mp4.",
    )
    return parser


def write_same_line(x, sleep_time=0.0001):
    stdout.write("\r%s" % str(x))
    stdout.flush()
    sleep(sleep_time)


def finish_same_line():
    stdout.write("\r  \r\n")


def get_json(url, params=None):
    if params is not None:
        url += "?" + urlencode(params)

    r = urlopen(url).read().decode("utf-8")

    return json.loads(r)


def find_task_group_id(revision, branch, search_crons=False):
    # Find the task IDs from this revision first
    task_ids_url = TASK_IDS.format(branch, revision)

    print("Downloading task ids from: %s" % task_ids_url)
    task_ids_data = get_json(task_ids_url)
    if "tasks" not in task_ids_data or len(task_ids_data["tasks"]) == 0:
        raise Exception("Cannot find any task IDs for %s!" % revision)

    task_group_ids = []
    for task in task_ids_data["tasks"]:
        # Only find the task group ID for the decision task if we
        # don't need to search for cron tasks
        if not search_crons and not task["namespace"].endswith("decision"):
            continue
        task_group_url = TASK_INFO.format(task["taskId"])
        print("Downloading task group id from: %s" % task_group_url)
        task_info = get_json(task_group_url)
        task_group_ids.append(task_info["taskGroupId"])

    return task_group_ids


def find_videos(artifact_dir):
    # Find the cold/warm browsertime.json files
    cold_path = ""
    warm_path = ""
    for path in pathlib.Path(artifact_dir).rglob("*-browsertime.json"):
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
            str(pathlib.Path(cold_path.parents[0], file))
            for file in cold_data[0]["files"]["video"]
        ],
        "warm": [
            str(pathlib.Path(warm_path.parents[0], file))
            for file in warm_data[0]["files"]["video"]
        ],
    }


def get_similarity(
    old_videos_info, new_videos_info, output, prefix="", most_similar=False
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


def find_lowest_similarity(base_videos, new_videos, output, prefix, most_similar=False):
    def _open_data(file):
        return cv2.VideoCapture(str(file))

    return get_similarity(
        [{"data": _open_data(str(f)), "path": str(f)} for f in base_videos],
        [{"data": _open_data(str(f)), "path": str(f)} for f in new_videos],
        output,
        prefix,
        most_similar=most_similar,
    )


def build_side_by_side(base_video, new_video, base_ind, new_ind, output_dir, filename):
    before_vid = pathlib.Path(output_dir, "before.mp4")
    after_vid = pathlib.Path(output_dir, "after.mp4")
    before_cut_vid = pathlib.Path(output_dir, "before-cut.mp4")
    after_cut_vid = pathlib.Path(output_dir, "after-cut.mp4")
    before_rs_vid = pathlib.Path(output_dir, "before-rs.mp4")
    after_rs_vid = pathlib.Path(output_dir, "after-rs.mp4")

    for apath in (
        before_vid,
        after_vid,
        before_cut_vid,
        after_cut_vid,
        before_rs_vid,
        after_rs_vid,
    ):
        if apath.exists():
            apath.unlink()

    overlay_text = (
        "fps=fps=60,drawtext=text={}\\\\ :fontsize=(h/20):fontcolor=black:y=10:"
        + "timecode=00\\\\:00\\\\:00\\\\:00:rate=60*1000/1001:fontcolor=white:x=(w-tw)/2:"
        + "y=10:box=1:boxcolor=0x00000000@1[vid]"
    )
    common_options = [
        "-map",
        "[vid]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "veryfast",
    ]

    # Cut the videos
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(base_video),
            "-vf",
            "select=gt(n\\,%s)" % base_ind,
        ]
        + [str(before_cut_vid)]
    )
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(new_video),
            "-vf",
            "select=gt(n\\,%s)" % new_ind,
        ]
        + [str(after_cut_vid)]
    )

    # Resample
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(before_cut_vid),
            "-filter:v",
            "fps=fps=60",
        ]
        + [str(before_rs_vid)]
    )
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(after_cut_vid),
            "-filter:v",
            "fps=fps=60",
        ]
        + [str(after_rs_vid)]
    )

    # Generate the before and after videos
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(before_rs_vid),
            "-filter_complex",
            overlay_text.format("BEFORE"),
        ]
        + common_options
        + [str(before_vid)]
    )
    subprocess.check_output(
        [
            "ffmpeg",
            "-i",
            str(after_rs_vid),
            "-filter_complex",
            overlay_text.format("AFTER"),
        ]
        + common_options
        + [str(after_vid)]
    )

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
        + common_options
        + [str(pathlib.Path(output_dir, filename))]
    )


if __name__ == "__main__":
    args = side_by_side_parser().parse_args()
    overwrite = args.overwrite

    if shutil.which("ffmpeg") is None:
        raise Exception(
            "Cannot find ffmpeg in path! Please install it before continuing."
        )
    if "vismet-" in args.platform:
        args.platform = args.platform.replace("vismet-", "")
        if not args.test_name.endswith("-e10s"):
            args.test_name += "-e10s"
        print(
            "Vismet tasks do not contain browsertime video recordings."
            + "We'll assume you meant this platform: %s" % args.platform
        )

    # Parse the given output argument
    filename = "side-by-side.mp4"
    output = pathlib.Path(args.output)
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
        args.base_revision, args.base_branch, search_crons=args.search_crons
    )
    new_revision_ids = find_task_group_id(
        args.new_revision, args.new_branch, search_crons=args.search_crons
    )

    base_task_dirs = [pathlib.Path(output, revid) for revid in base_revision_ids]
    new_task_dirs = [pathlib.Path(output, revid) for revid in new_revision_ids]
    if overwrite:
        for task_dir in base_task_dirs + new_task_dirs:
            if task_dir.exists():
                print("Removing existing task group folder: %s" % str(task_dir))
                shutil.rmtree(str(task_dir))

    def _search_for_paths(rev_ids):
        found_paths = []
        for rev_id in rev_ids:
            if found_paths:
                break
            # Get the paths to the directory holding the artifacts
            found_paths = list(
                get_task_data_paths(
                    rev_id, str(output), artifact="browsertime-results"
                ).values()
            )
        return found_paths

    # Download the artifacts
    if not args.skip_download:
        base_paths = []
        for base_revision_id in base_revision_ids:
            if base_paths:
                break
            artifact_downloader(
                base_revision_id,
                output_dir=str(output),
                test_suites=[args.test_name],
                platform=args.platform,
                artifact_to_get=["browsertime-results"],
                unzip_artifact=True,
                download_failures=True,
                ingest_continue=False,
            )
            base_paths = _search_for_paths([base_revision_id])

        new_paths = []
        for new_revision_id in new_revision_ids:
            if new_paths:
                break
            artifact_downloader(
                new_revision_id,
                output_dir=str(output),
                test_suites=[args.new_test_name or args.test_name],
                platform=args.new_platform or args.platform,
                artifact_to_get=["browsertime-results"],
                unzip_artifact=True,
                download_failures=True,
                ingest_continue=False,
            )
            new_paths = _search_for_paths([new_revision_id])
    else:
        base_paths = _search_for_paths(base_revision_ids)
        new_paths = _search_for_paths(new_revision_ids)

    # Make sure we only downloaded one task
    failure_msg = (
        "Not enough or too many artifacts downloaded for %s, can't compare! "
        + "Found paths: %s \nTry using --search-crons if you are sure the task exists."
    )
    if not base_paths or len(base_paths) > 1:
        raise Exception(failure_msg % (args.base_revision, base_paths))
    if not new_paths or len(new_paths) > 1:
        raise Exception(failure_msg % (args.new_revision, new_paths))

    # Gather the videos and split them between warm and cold
    base_videos = find_videos(base_paths[0][0])
    new_videos = find_videos(new_paths[0][0])

    run_cold = args.cold
    run_warm = args.warm
    if not args.cold and not args.warm:
        run_cold = True
        run_warm = True

    # Find the worst video pairing for cold and warm
    print("Starting comparisons, this may take a few minutes")
    if run_cold:
        print("Running comparison for cold pageloads...")
        cold_pairing = find_lowest_similarity(
            base_videos["cold"],
            new_videos["cold"],
            str(output),
            "cold_",
            most_similar=args.most_similar,
        )
    if run_warm:
        gc.collect()
        print("Running comparison for warm pageloads...")
        warm_pairing = find_lowest_similarity(
            base_videos["warm"],
            new_videos["warm"],
            str(output),
            "warm_",
            most_similar=args.most_similar,
        )

    # Build up the side-by-side comparisons now
    if run_cold:
        output_name = str(pathlib.Path(output, "cold-" + filename))
        build_side_by_side(
            cold_pairing["oldvid"],
            cold_pairing["newvid"],
            cold_pairing["oldvid_ind"],
            cold_pairing["newvid_ind"],
            output,
            "cold-" + filename,
        )
        print("Successfully built a side-by-side cold comparison: %s" % output_name)
    if run_warm:
        output_name = str(pathlib.Path(output, "warm-" + filename))
        build_side_by_side(
            warm_pairing["oldvid"],
            warm_pairing["newvid"],
            warm_pairing["oldvid_ind"],
            warm_pairing["newvid_ind"],
            output,
            "warm-" + filename,
        )
        print("Successfully built a side-by-side warm comparison: %s" % output_name)
