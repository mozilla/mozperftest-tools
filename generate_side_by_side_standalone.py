#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

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
import shutil
import subprocess


def side_by_side_parser():
    parser = argparse.ArgumentParser(
        "You can use this tool to make arbitrary side-by-side videos of any combination of videos. "
        "Use --remove-orange if you are comparing browsertime videos with orange frames (note that "
        "this requires matplotlib). "
    )
    parser.add_argument(
        "--base-video",
        type=str,
        required=True,
        help="The path to the base/before video.",
    )
    parser.add_argument(
        "--new-video",
        type=str,
        default="autoland",
        help="The path to the new/after video.",
    )
    parser.add_argument(
        "--remove-orange",
        action="store_true",
        default=False,
        help="If set, orange frames are removed.",
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


def remove_orange_frames(video):
    """Removes orange frames."""

    try:
        from matplotlib import pyplot as plt
    except:
        print("Missing matplotlib, please install")
        raise

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
        ["ffmpeg", "-i", str(base_video), "-vf", "select=gt(n\\,%s)" % base_ind]
        + [str(before_cut_vid)]
    )
    subprocess.check_output(
        ["ffmpeg", "-i", str(new_video), "-vf", "select=gt(n\\,%s)" % new_ind]
        + [str(after_cut_vid)]
    )

    # Resample
    subprocess.check_output(
        ["ffmpeg", "-i", str(before_cut_vid), "-filter:v", "fps=fps=60"]
        + [str(before_rs_vid)]
    )
    subprocess.check_output(
        ["ffmpeg", "-i", str(after_cut_vid), "-filter:v", "fps=fps=60"]
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

    if shutil.which("ffmpeg") is None:
        raise Exception(
            "Cannot find ffmpeg in path! Please install it before continuing."
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

    def _open_data(file):
        return cv2.VideoCapture(str(file))

    base_video_path = str(pathlib.Path(args.base_video).resolve())
    new_video_path = str(pathlib.Path(args.new_video).resolve())
    base_ind = 0
    new_ind = 0
    if args.remove_orange:
        _, base_ind = remove_orange_frames(_open_data(base_video_path))
        _, new_ind = remove_orange_frames(_open_data(new_video_path))

    output_name = str(pathlib.Path(output, "cold-" + filename))
    build_side_by_side(
        args.base_video,
        args.new_video,
        base_ind,
        new_ind,
        output,
        "custom-" + filename,
    )
    print("Successfully built a side-by-side comparison: %s" % output_name)
