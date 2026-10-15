"""SYNTHETIC brief-v2 tooling data; never real authoring material."""
import copy

from etps_v02.workload import decode, encode


def synthetic_v2(document):
    """Rename declared identities and references; preserve byte span content."""
    doc = copy.deepcopy(document)
    doc["brief_version"] = "authoring-brief-v2"
    for task in doc["tasks"]:
        ids = {}
        for collection, letter in (("conversation", "m"), ("probes", "q"), ("state_history", "p"),
                                   ("recoveries", "c")):
            for i, item in enumerate(task[collection], 1):
                ids[item["id"]] = f"{task['id']}-{letter}{i:03d}"
        versions = [v for r in task["state_history"] for v in r["versions"]]
        for i, version in enumerate(versions, 1):
            ids[version["id"]] = f"{task['id']}-v{i:03d}"
        requirements = [r for v in versions for r in v["requirements"]]
        for i, req in enumerate(requirements, 1):
            ids[req["id"]] = f"{task['id']}-r{i:03d}"
        # Only the public correction prefix changes; preserve the designated
        # UTF-8 content by shifting its byte spans by the prefix-length delta.
        for recovery in task["recoveries"]:
            delta = len(ids[recovery["id"]].encode("utf-8")) - len(recovery["id"].encode("utf-8"))
            for span in recovery["spans"] + recovery["new_spans"]:
                span[0] += delta
                span[1] += delta
        def rename(value):
            if type(value) is str:
                if value in ids:
                    return ids[value]
                for old, new in ids.items():
                    value = value.replace("[" + old + "] ", "[" + new + "] ")
                return value
            if type(value) is list:
                return [rename(v) for v in value]
            if type(value) is dict:
                return {k: rename(v) for k, v in value.items()}
            return value
        task.update(rename(task))
    return doc


def synthetic_rename(doc, old, new):
    """Exact identity/text substitution for synthetic admission counterexamples."""
    return decode(encode(doc).replace(old.encode(), new.encode()))
