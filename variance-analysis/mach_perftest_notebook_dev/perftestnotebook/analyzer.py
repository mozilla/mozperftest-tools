import os

import numpy as np
import scipy.stats as stats


class NotebookAnalyzer(object):
    """
    Analyze the standardized data. The methods in these functions
    will be injected in an Iodide page in the future.
    """

    def __init__(self, data):
        """
        Initialize the Analyzer.

        :param dict data: Standardized data, post-transformation.
        """
        self.data = data

    def split_subtests(self):
        """
        If the subtest field exists, split the data based
        on it, grouping data into subtest groupings.
        """
        if "subtest" not in self.data[0]:
            return {"": self.data}

        split_data = {}
        for entry in self.data:
            subtest = entry["subtest"]
            if subtest not in split_data:
                split_data[subtest] = []
            split_data[subtest].append(entry)

        return split_data

    def get_header(self):
        template_header_path = "testing/resources/template/header"
        with open(template_header_path, "r") as f:
            template_header_content = f.read()
            return template_header_content

    def get_notebook_section(self, func):
        template_function_folder_path = "testing/resources/notebook-sections/"
        template_function_file_path = os.path.join(template_function_folder_path, func)
        with open(template_function_file_path, "r") as f:
            return f.read()
