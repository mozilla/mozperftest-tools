from perftestnotebook.transformer import Transformer


class Testing(Transformer):
    entry_number = 0

    def merge(self, data):
        # Merge data from all subtests
        grouped_data = {}
        for entry in data:
            # print(entry)
            subtest = entry["subtest"]
            if subtest not in grouped_data:
                grouped_data[subtest] = []
            grouped_data[subtest].append(entry)

        merged_data = []
        for subtest in grouped_data:
            data = [(entry["xaxis"], entry["data"]) for entry in grouped_data[subtest]]

            dsorted = sorted(data, key=lambda t: t[0])

            merged = {"data": [], "xaxis": []}
            for xval, val in dsorted:
                merged["data"].append(val)
                merged["xaxis"].append(xval)
            merged["subtest"] = subtest

            merged_data.append(merged)

        self.entry_number = 0
        return merged_data

    def transform(self, data):
        ret = []
        self.entry_number += 1
        for field, val in data.items():
            ret.append({"data": val, "xaxis": self.entry_number, "subtest": field})
        return ret
