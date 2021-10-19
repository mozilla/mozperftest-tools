#!/usr/bin/env python3
import json
import os
import pathlib
import webbrowser
import yaml
import perftestnotebook.transformer as tfmr
from collections import OrderedDict
from flask import Flask, Response, request, send_file
from perftestnotebook.analyzer import NotebookAnalyzer
from perftestnotebook.constant import Constant
from perftestnotebook.logger import NotebookLogger
from perftestnotebook.notebookparser import parse_args
from perftestnotebook.task_processor import get_task_data_paths

logger = NotebookLogger()


class PerftestNotebook(object):
    """
    Controller class for the Perftest-Notebook.
    """

    def __init__(self, file_groups, config, custom_transform=None, sort_files=False):
        """
        Initializes PerftestNotebook.

        :param dict file_groups: A dict of file groupings. The value
            of each of the dict entries is the name of the data that
            will be produced.
        :param str custom_transform: Path to a file containing custom
            transformation logic. Must implement the Transformer
            interface.
        """
        self.fmt_data = {}
        self.file_groups = file_groups
        self.config = config
        self.sort_files = sort_files

        const = Constant()
        plugin_path = os.getenv("NOTEBOOK_PLUGIN")
        tfms_dict = const.predefined_transformers
        if plugin_path:
            tfms_dict.update(tfmr.get_transformers(plugin_path))

        if custom_transform:
            tfm_cls = tfms_dict.get(custom_transform)
            if tfm_cls:
                self.transformer = tfm_cls(files=[])
                logger.info(f"Found {custom_transform} transformer")
            else:
                raise Exception(f"Could not get a {custom_transform} transformer.")
        else:
            self.transformer = tfmr.SimplePerfherderTransformer(files=[])

        self.analyzer = NotebookAnalyzer(data=None)

    def parse_file_grouping(self, file_grouping):
        """
        Handles differences in the file_grouping definitions. It can either be a
        path to a folder containing the files, a list of files, or it can contain
        settings from an artifact_downloader instance.

        :param file_grouping: A file grouping entry.
        :return: A list of files to process.
        """
        files = []
        print(files)
        if type(file_grouping) == list:
            # A list of files was provided
            files = file_grouping
        elif type(file_grouping) == dict:
            # A dictionary of settings from an artifact_downloader instance
            # was provided here
            files = get_task_data_paths(
                file_grouping["task_group_id"],
                file_grouping["path"],
                artifact=file_grouping["artifact"],
                artifact_dir=file_grouping.get("artifact_dir", None),
                run_number=file_grouping["run_number"],
            )
        elif type(file_grouping) == str:
            # Assume a path to files was given
            filepath = files

            newf = [f for f in pathlib.Path(filepath).rglob("*.json")]
            if not newf:
                # Couldn't find any JSON files, so take all the files
                # in the directory
                newf = [f for f in pathlib.Path(filepath).rglob("*")]

            files = newf
        else:
            raise Exception(
                "Unknown file grouping type provided here: %s" % file_grouping
            )

        if self.sort_files:
            if type(files) == list:
                files.sort()
            else:
                for _, file_list in files.items():
                    file_list.sort()
                files = OrderedDict(sorted(files.items(), key=lambda entry: entry[0]))

        if not files:
            raise Exception(
                "Could not find any files in this configuration: %s" % file_grouping
            )

        return files

    def parse_output(self):
        prefix = "output" if "prefix" not in self.config else self.config["prefix"]
        filepath = "%s_fmt_data.json" % prefix

        if "output" in self.config:
            filepath = self.config["output"]

        return filepath

    def process(self, no_iodide=False):
        """
        Process the file groups and return the results of the requested analyses.

        :return: All the results in a dictionary. The field names are the Analyzer
            funtions that were called.
        """
        fmt_data = []
        notebook_sections = ""

        for name, files in self.file_groups.items():
            files = self.parse_file_grouping(files)
            if isinstance(files, dict):
                for subtest, files in files.items():
                    self.transformer.files = files

                    trfm_data = self.transformer.process(name)

                    if type(trfm_data) == list:
                        for e in trfm_data:
                            if "subtest" not in e:
                                e["subtest"] = subtest
                            else:
                                e["subtest"] = "%s-%s" % (subtest, e["subtest"])
                        fmt_data.extend(trfm_data)
                    else:
                        if "subtest" not in trfm_data:
                            trfm_data["subtest"] = subtest
                        else:
                            trfm_data["subtest"] = "%s-%s" % (
                                subtest,
                                trfm_data["subtest"],
                            )
                        fmt_data.append(trfm_data)
            else:
                # Transform the data
                self.transformer.files = files
                trfm_data = self.transformer.process(name)

                if type(trfm_data) == list:
                    fmt_data.extend(trfm_data)
                else:
                    fmt_data.append(trfm_data)

        self.fmt_data = fmt_data

        # Write formatted data output to filepath
        output_data_filepath = self.parse_output()

        print("Writing results to %s" % output_data_filepath)

        with open(output_data_filepath, "w") as f:
            json.dump(self.fmt_data, f, indent=4, sort_keys=True)

        # Gather config["analysis"] corresponding notebook sections
        if "analysis" in self.config:
            for func in self.config["analysis"]:
                notebook_sections += self.analyzer.get_notebook_section(func)

        # Post to Iodide server
        if not no_iodide:
            self.post_to_iodide(output_data_filepath, notebook_sections)

        return self.fmt_data

    def post_to_iodide(self, output_data_filepath, notebook_sections):

        template_header_path = "testing/resources/notebook-sections/header"

        with open(template_header_path, "r") as f:
            template_content = f.read()
            template_content = template_content + notebook_sections

        with open("template_upload_file.html", "r") as f:
            html = f.read()
            html = html.replace("replace_me", repr(template_content))

        with open("upload_file.html", "w+") as f:
            f.write(html)

        webbrowser.open_new_tab("upload_file.html")

        # Set up local server data API.
        # Iodide will visit localhost:5000/data
        app = Flask(__name__)
        app.config["DEBUG"] = False

        @app.route("/data", methods=["GET"])
        def return_data():

            response = flask.make_response(send_file(output_data_filepath))
            response.headers["Access-Control-Allow-Origin"] = "*"

            return response

        app.run()


def main():
    args = parse_args()

    NotebookLogger.debug = args.debug

    config = None
    with open(args.config, "r") as f:
        logger.info("yaml_path: {}".format(args.config))
        config = yaml.safe_load(f)

    custom_transform = config.get("custom_transform", None)

    ptnb = PerftestNotebook(
        config["file_groups"],
        config,
        custom_transform=custom_transform,
        sort_files=args.sort_files,
    )
    results = ptnb.process(args.no_iodide)


if __name__ == "__main__":
    main()
