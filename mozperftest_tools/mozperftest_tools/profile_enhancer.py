#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Used to enhance profiles. Currently it adds regression/improvement
markers to the profiles.
"""

import copy
import json
import pathlib


class ProfileEnhancer:
    def __init__(self, output_dir):
        self.output_dir = pathlib.Path(output_dir).resolve()

    def get_geckomain_thread(self, data_after):
        """Searches through a profile to find a GeckoMain thread.

        At the same time, it also finds a start time that is later
        used for correcting the delta that gets added to the visual
        metrics regression/improvement markers. See here:
        https://github.com/firefox-devtools/profiler/blob/
        a69c98867d185c069560c5b1aa56da8c61ac97b9/src/profile-logic/
        process-profile.js#L1398-L1399
        """
        gecko_main = None
        start_time = None

        for proc in data_after["processes"]:
            for thread in proc["threads"]:
                if thread["name"] == "GeckoMain":
                    gecko_main = thread
                    start_time = proc["meta"]["startTime"]
                    break

        return gecko_main, start_time

    def get_test_category(self, data_after):
        """Finds, and returns the index of the Test category."""
        for i, cat in enumerate(data_after["meta"]["categories"]):
            if cat["name"].lower() == "test":
                return i
        raise Exception("Could not find the test category in the given profile.")

    def insert_into_string_table(self, gecko_main):
        gecko_main["stringTable"].append("Performance Changes Detected (from ProfileEnhancer)")
        return len(gecko_main["stringTable"]) - 1

    def detect_changes(self, vismet_before_ns, vismet_after_ns, threshold=5):
        """Returns the changes (improvements, AND regressions) found.

        We go through both lists and once we find a mismatch, we begin
        marking either a regression, OR, an improvment and then store it
        once we hit an equalization point.

        DO NOT use approximations here because the visual completeness
        can absolutely change in flash. This means that we begin counting
        a regression, then stop when we hit a point that is unregressed
        in the other.

        Use the threshold to determine how large the distance in progress
        must be to be classified as a change.
        """ 
        changes = []

        # Standardize the timestamps
        vismet_before = []
        vismet_after = []
        for prog in vismet_before_ns:
            new_prog = copy.deepcopy(prog)
            new_prog["timestamp"] = prog["timestamp"] - vismet_before_ns[0]["timestamp"]
            vismet_before.append(new_prog)
        for prog in vismet_after_ns:
            new_prog = copy.deepcopy(prog)
            new_prog["timestamp"] = prog["timestamp"] - vismet_after_ns[0]["timestamp"]
            vismet_after.append(new_prog)

        start_ts = None
        end_ts = None
        curr_ind = 0
        for i, prog in enumerate(vismet_before):
            if prog["percent"] == vismet_after[curr_ind]["percent"]:
                curr_ind += 1
            elif (
                prog["percent"] > vismet_after[curr_ind]["percent"] and
                prog["timestamp"] <= vismet_after[curr_ind]["timestamp"]
            ):
                # Create a regression
                # From this point until we find an inflection in the progress
                # we no longer care about the timestamp. This is because we already
                # know we're slower in the vismet_after starting from now, and
                # until the progress flips again. The same is true for an improvement.
                start_ts = vismet_after[curr_ind]["timestamp"]
                while (
                    prog["percent"] > vismet_after[curr_ind]["percent"] and
                    curr_ind + 1 < len(vismet_after)
                ):
                    curr_ind += 1
                    end_ts = vismet_after[curr_ind]["timestamp"]

                changes.append({
                    "type": "regression",
                    "start": start_ts + vismet_after_ns[0]["timestamp"],
                    "end": end_ts + vismet_after_ns[0]["timestamp"],
                })
            elif (
                prog["percent"] < vismet_after[curr_ind]["percent"] and
                prog["timestamp"] >= vismet_after[curr_ind]["timestamp"]
            ):
                # Create an improvement
                start_ts = vismet_after[curr_ind]["timestamp"]
                while (
                    prog["percent"] < vismet_after[curr_ind]["percent"] and 
                    curr_ind + 1 < len(vismet_after)
                ):
                    curr_ind += 1
                    end_ts = vismet_after[curr_ind]["timestamp"]

                changes.append({
                    "type": "improvement",
                    "start": start_ts + vismet_after_ns[0]["timestamp"],
                    "end": end_ts + vismet_after_ns[0]["timestamp"],
                })

            if curr_ind >= len(vismet_after):
                # Finished searching
                break

        # Merge the changes we've found in case there's overlap,
        # this could be resolved above but I prefer getting steps
        # of regressions as an intermediate value for debugging
        merged_changes = []
        curr_change = None
        for change in changes:
            if curr_change is None:
                curr_change = change
            elif (
                curr_change["type"] == change["type"] and 
                curr_change["end"] == change["start"]
            ):
                curr_change["end"] = change["end"]
            else:
                merged_changes.append(curr_change)
                curr_change = change
        if curr_change:
            merged_changes.append(curr_change)

        return merged_changes

    def run(self, profile_before, profile_after):
        """
        This method will go through the visual metrics in both
        profiles to try to find all areas where there is either
        a regression or improvement and mark them into a new
        profile in the given output directory.
        """
        profile_before = pathlib.Path(profile_before).resolve()
        with profile_before.open() as f:
            data_before = json.load(f)

        profile_after = pathlib.Path(profile_after).resolve()
        with profile_after.open() as f:
            data_after = json.load(f)

        gecko_main, start_time = self.get_geckomain_thread(data_after)

        # Calculate regression ranges
        vismets_before = data_before["meta"].get("visualMetrics", None)
        vismets_after = data_after["meta"].get("visualMetrics", None)

        # Calculate a regression/improvment range for each visual progress metric
        psi_changes = self.detect_changes(
            vismets_before.get("PerceptualSpeedIndexProgress", []),
            vismets_after.get("PerceptualSpeedIndexProgress", [])
        )
        print(psi_changes)

        csi_changes = self.detect_changes(
            vismets_before.get("ContentfulSpeedIndexProgress", []),
            vismets_after.get("ContentfulSpeedIndexProgress", [])
        )
        print(csi_changes)

        si_changes = self.detect_changes(
            vismets_before.get("VisualProgress", []),
            vismets_after.get("VisualProgress", [])
        )
        print(si_changes)

        # Insert the change markers into the after profile
        perfchange_name_ind = self.insert_into_string_table(gecko_main)
        test_cat_ind = self.get_test_category(data_after)
        diff = start_time - data_after["meta"]["startTime"]
        for prog_type, changes in [
            ("PerceptualSpeedIndex", psi_changes),
            ("ContenfulSpeedIndex", csi_changes),
            ("SpeedIndex", si_changes)
        ]:
            for change in changes:
                print(f"{prog_type}: {change}")
                gecko_main["markers"]["data"].append(
                    [
                        perfchange_name_ind,
                        change["start"] - diff,
                        change["end"] - diff,
                        1,
                        test_cat_ind,
                        {
                            "type": "Task",
                            "name": f"{prog_type} - {change['type']}",
                        }
                    ]
                )

        # Save the data
        profile_after_name = profile_after.name.split(".")[0]
        res = pathlib.Path(self.output_dir, f"{profile_after_name}-enhanced.json.gz")

        print(f"Saving enhanced profile to {str(res.resolve())}")
        with res.open("w") as f:
            json.dump(data_after, f)
