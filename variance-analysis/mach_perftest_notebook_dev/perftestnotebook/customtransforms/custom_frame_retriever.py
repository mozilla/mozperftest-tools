import time
from sys import stdout

import numpy as np

import cv2
from perftestnotebook.logger import NotebookLogger
from perftestnotebook.transformer import Transformer

logger = NotebookLogger()


def write_same_line(msg, sleep_time=0.01):
    stdout.write("\r%s" % str(msg))
    stdout.flush()
    time.sleep(sleep_time)


def finish_same_line():
    stdout.write("\r  \r\n")


class FrameRetriever(Transformer):
    entry_number = 0

    def open_data(self, file):
        cap = cv2.VideoCapture(file)
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def merge(self, sde):
        if NotebookLogger.debug:
            finish_same_line()
        merged = {"data": [], "xaxis": []}

        for entry in sde:
            if type(entry["xaxis"]) in (dict, list):
                raise Exception(
                    "Expecting non-iterable data type in xaxis entry, found %s"
                    % type(entry["xaxis"])
                )

        data = [(entry["xaxis"], entry["data"]) for entry in sde]

        dsorted = sorted(data, key=lambda t: t[0])

        for xval, val in dsorted:
            merged["data"].extend(val)
            merged["xaxis"].append(xval)

        self.entry_number = 0
        return merged

    def transform(self, data):
        self.entry_number += 1
        if NotebookLogger.debug:
            write_same_line("On data point %s" % self.entry_number)
        return [{"data": [data], "xaxis": self.entry_number}]
