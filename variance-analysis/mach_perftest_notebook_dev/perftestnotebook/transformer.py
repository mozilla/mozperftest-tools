import json
import importlib.util
import inspect
import os
import pathlib

from perftestnotebook.logger import NotebookLogger

logger = NotebookLogger()

top_level = pathlib.Path(os.path.dirname(__file__)).resolve().parent


class Transformer(object):
    """
    Abstract class for data transformers.
    """

    def __init__(self, files=None):
        """
        Initialize the transformer with files.

        :param list files: A list of files containing data to transform.
        """
        self._files = files

    @property
    def files(self):
        return self._files

    @files.setter
    def files(self, val):
        if not type(val) == list:
            logger.warning("`files` must be a list, got %s" % type(val))
            return
        self._files = val

    def transform(self, data):
        """
        Transform the data into the standardized data format. The
        `data` entry can be of any type and the subclass is responsible
        for knowing what they expect.

        :param data: Data to transform.
        :return: Data standardized in the perftest-notebook format. 
        """
        raise NotImplementedError

    def merge(self, standardized_data_entries):
        """
        Merge multiple standardized entries into a timeseries.

        :param list standardized_data_entries: List of standardized data entries.
        :return: Merged standardized data entries.
        """
        raise NotImplementedError

    def open_data(self, file):
        """
        Opens a file of data. If it's not a JSON file, then the data
        will be opened as a text file.

        :param str file: Path to the data file.
        :return: Data contained in the file.
        """
        data = None
        if file.endswith(".json"):
            with open(file, "r") as f:
                data = json.load(f)
        else:
            with open(file, "r") as f:
                data = f.readlines()
        return data

    def process(self, name):
        """
        Process all the known data into a merged, and standardized data format.

        :param str name: Name of the merged data.
        :return dict: Merged data.
        """
        trfmdata = []

        for file in self.files:
            data = {}

            # Open data
            try:
                data = self.open_data(file)
            except Exception as e:
                logger.warning("Failed to open file %s, skipping" % file)
                logger.warning("%s %s" % (e.__class__.__name__, e))

            # Transform data
            try:
                data = self.transform(data)
                if type(data) != list:
                    data = [data]
                trfmdata.extend(data)
            except Exception as e:
                logger.warning("Failed to transform file %s, skipping" % file)
                logger.warning("%s %s" % (e.__class__.__name__, e))

        merged = self.merge(trfmdata)

        if type(merged) == dict:
            merged["name"] = name
        else:
            for e in merged:
                e["name"] = name

        return merged


class SimplePerfherderTransformer(Transformer):
    """
    Transforms perfherder data into the standardized data format.
    """

    entry_number = 0

    def transform(self, data):
        self.entry_number += 1
        return {
            "data": [{"value": data["suites"][0]["value"], "xaxis": self.entry_number}]
        }

    def merge(self, sde):
        merged = {"data": []}
        for entry in sde:
            if type(entry["data"]) == list:
                merged["data"].extend(entry["data"])
            else:
                merged["data"].append(entry["data"])

        self.entry_number = 0
        return merged


def get_transformers(
    filepath=os.path.join(str(top_level), "perftestnotebook/customtransforms")
):
    """
    This function returns a dict of transformers under the given path.

    If more than one transformers have the same class name, an exception will be raised.

    :param str filepath: file path.
    :return dict: {"transformer name": Transformer class}.
    """
    ret = {}

    tfm_path = pathlib.Path(filepath).resolve()

    if not tfm_path.is_dir():
        raise Exception(f"{tfm_path} is not a directory or it does not exist.")

    tfm_files = list(tfm_path.glob("*.py"))

    for file in tfm_files:
        # Importing a source file directly
        spec = importlib.util.spec_from_file_location(
            name=file.name, location=file.resolve().as_posix()
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        members = inspect.getmembers(
            module, lambda c: inspect.isclass(c) and issubclass(c, Transformer)
        )

        for (name, tfm_class) in members:
            if name in ret and name != "Transformer":
                raise Exception(
                    f"""Duplicated transformer {name} is found in the folder {filepath}. 
                    Please define each transformer class with a unique class name."""
                )
            ret.update({name: tfm_class})

    return ret
