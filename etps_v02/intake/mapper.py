"""Lossless authoring-v1 derivation; no prose inference or corpus execution."""
import argparse
import copy
import json
from pathlib import Path

from ..scorer import InvalidRecord
from ..workload import decode, encode, sha
from .authoring import AuthoringError, MAX_BYTES, validate_authoring
from .state_records import IntakeError, EventGraph, read_bounded, validate_state_records

VERSION = "authoring-mapper-v1"


class MappingError(IntakeError):
    pass


def need(condition, code, path, detail):
    if not condition:
        raise MappingError(code, path, detail)


def escape(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def paths(value, prefix=""):
    yield prefix
    if type(value) is dict:
        for key in sorted(value):
            yield from paths(value[key], prefix + "/" + escape(key))
    elif type(value) is list:
        for i, child in enumerate(value):
            yield from paths(child, prefix + "/" + str(i))


def set_order(value):
    return sorted(copy.deepcopy(value), key=encode)


def map_task(task, source_prefix, names):
    traces = {}

    def trace(source, artifact, pointer, kind, extra=()):
        traces[source_prefix + source] = [{"artifact": names[artifact], "pointer": pointer, "kind": kind}] + list(extra)

    metadata = {"version": "authoring-v1", "brief_version": "authoring-brief-v1", "task_id": task["id"],
                "family": task["family"], "coverage_tags": copy.deepcopy(task["coverage_tags"]),
                "logical_field_map": copy.deepcopy(task["field_map"])}
    metadata["coverage_tags"]["subcases"] = sorted(metadata["coverage_tags"]["subcases"])
    manifest = {"unit": "utf8_bytes", "answer_schema": "typed-v1", "answer_predicate": "set-v1",
                "nodes": {}, "obligations": {}, "metadata": {"authoring": metadata}}
    nodes = manifest["nodes"]
    accept, reject = "terminal:accept", "terminal:reject"
    nodes[accept], nodes[reject] = {"kind": "terminal", "accepted": True}, {"kind": "terminal", "accepted": False}
    sidecar = {"version": "state-records-v1", "records": [], "fields": {}, "probes": {}}
    trace("", "manifest", "/metadata/authoring", "metadata")
    for key in ("id", "family", "coverage_tags"):
        trace("/" + key, "manifest", "/metadata/authoring/" + ("task_id" if key == "id" else key), "metadata")
    trace("/field_map", "field_map", "", "field_map")
    for field, query in task["field_map"].items():
        need(query["kind"] != "clarification", "clarification_unrepresentable", source_prefix + "/field_map/" + field,
             "state-records-v1 has no clarification query projection; do not substitute a current query")
        sidecar["fields"][field] = {k: v for k, v in query.items() if k != "dimension"}
    recoveries = {r["id"]: r for r in task["recoveries"]}
    probes = {p["id"]: p for p in task["probes"]}
    for recovery in recoveries.values():
        need(len(recovery["failure_probes"]) == 1, "multi_failure_recovery", source_prefix + "/recoveries",
             "manifest user.failure supports one originating probe only (CORPUS_INTAKE section 3)")
    scheduled = []
    for message in task["conversation"]:
        scheduled.append(message["id"])
        for probe in task["probes"]:
            if probe["position"] == message["id"]:
                scheduled.extend(("question:" + probe["id"], probe["id"]))
    need(any(pid in scheduled for pid in probes), "schedule_unrepresentable", source_prefix + "/probes", "no scheduled question")
    successors = {node: scheduled[i+1] if i+1 < len(scheduled) else accept for i, node in enumerate(scheduled)}
    manifest["start"] = scheduled[0]

    def continuation(pid):
        seen = set()
        while pid not in successors:
            need(pid not in seen, "recovery_cycle", source_prefix + "/recoveries", "cyclic correction ancestry")
            seen.add(pid)
            recovery = recoveries.get(probes[pid]["position"])
            need(recovery is not None, "schedule_unrepresentable", source_prefix + "/probes", "unattached question")
            pid = recovery["failure_probes"][0]
        return successors[pid]

    def user(text, target, **extra):
        return {"kind": "user", "text": text, "sha256": sha(text.encode("utf-8")), "spans": [], "next": target, **extra}

    for i, message in enumerate(task["conversation"]):
        mid = message["id"]
        nodes[mid] = user(message["text"], successors[mid], metadata={"authoring": {"recap": message["recap"]}})
        trace(f"/conversation/{i}", "manifest", "/nodes/" + escape(mid), "node")
        trace(f"/conversation/{i}/text", "manifest", "/nodes/" + escape(mid) + "/text", "node")
        trace(f"/conversation/{i}/recap", "manifest", "/nodes/" + escape(mid) + "/metadata/authoring/recap", "metadata")
    for i, probe in enumerate(task["probes"]):
        pp, pid = f"/probes/{i}", probe["id"]
        need(not probe["alternative_answers"], "alternative_answers", source_prefix + pp, "set-v1 supports one correct answer object")
        nodes["question:" + pid] = user(probe["wording"], pid)
        expected = copy.deepcopy(probe["expected"])
        for field in probe["set_fields"]:
            expected[field] = set_order(expected[field])
        nodes[pid] = {"kind": "probe", "expected": expected, "unknown_answers": set_order(probe["unknown_answers"]),
                      "set_fields": sorted(probe["set_fields"]), "field_dimensions": {k: q["dimension"] for k, q in probe["field_map"].items()},
                      "obligations": sorted(probe["requirements"]),
                      "next": {outcome: continuation(pid) if target == "$continue" else reject if target == "$reject" else target
                               for outcome, target in probe["outcomes"].items()}}
        sidecar["probes"][pid] = sorted(probe["field_map"])
        trace(pp, "manifest", "/nodes/" + escape(pid), "node")
        trace(pp + "/wording", "manifest", "/nodes/" + escape("question:" + pid) + "/text", "node")
        for src, dst in (("expected", "expected"), ("unknown_answers", "unknown_answers"), ("set_fields", "set_fields"),
                         ("requirements", "obligations"), ("outcomes", "next"), ("field_map", "field_dimensions")):
            trace(pp + "/" + src, "manifest", "/nodes/" + escape(pid) + "/" + dst, "obligation" if src == "requirements" else "node")
        trace(pp + "/position", "manifest", "/nodes/" + escape("question:" + pid), "node")
    for i, recovery in enumerate(task["recoveries"]):
        rp, rid = f"/recoveries/{i}", recovery["id"]
        nodes[rid] = user(recovery["text"], "question:" + recovery["retry"],
                          spans=set_order(recovery["spans"]), failure=recovery["failure_probes"][0],
                          metadata={"authoring": {"new_spans": set_order(recovery["new_spans"])}})
        trace(rp, "manifest", "/nodes/" + escape(rid), "node")
        for src, dst, kind in (("spans", "spans", "span"), ("new_spans", "metadata/authoring/new_spans", "span"),
                               ("failure_probes", "failure", "node"), ("text", "text", "node"), ("retry", "next", "node")):
            trace(rp + "/" + src, "manifest", "/nodes/" + escape(rid) + "/" + dst, kind)
    trace("/state_history", "sidecar", "/records", "state")
    for i, record in enumerate(task["state_history"]):
        rp = f"/state_history/{i}"
        output = {"id": record["id"], "entity": record["entity"], "property": record["property"], "scope": record["scope"],
                  "status_values": copy.deepcopy(record["status_labels"]), "versions": []}
        sidecar["records"].append(output)
        trace(rp, "sidecar", f"/records/{i}", "state")
        trace(rp + "/status_labels", "sidecar", f"/records/{i}/status_values", "state")
        for j, version in enumerate(record["versions"]):
            vp, target = f"{rp}/versions/{j}", f"/records/{i}/versions/{j}"
            versions = record["versions"]
            vout = {"id": version["id"], "number": j+1, "previous": versions[j-1]["id"] if j else None,
                    "next": versions[j+1]["id"] if j+1 < len(versions) else None,
                    "event": version["message"], "transition": version["change"], "status": version["status"],
                    "value": version["value"], "claims": [{"source": s["message"], "authority": s["authority"], "value": s["value"]}
                                                           for s in version["sources"]],
                    "valid_time": copy.deepcopy(version["time"]), "applicability": version["applicability"], "obligations": []}
            output["versions"].append(vout)
            trace(vp, "sidecar", target, "state")
            for src, dst in (("message", "event"), ("change", "transition"), ("sources", "claims"), ("time", "valid_time")):
                trace(vp + "/" + src, "sidecar", target + "/" + dst, "state")
            for k, req in enumerate(version["requirements"]):
                need(req["begin_after"] == version["message"], "delayed_obligation", source_prefix + vp,
                     "pilot requires begin_after == establishing message (CORPUS_INTAKE section 3)")
                manifest["obligations"][req["id"]] = {"source": version["message"], "begin_after": req["begin_after"], "end_before": req["end_before"]}
                vout["obligations"].append(copy.deepcopy(req))
                trace(vp + f"/requirements/{k}", "manifest", "/obligations/" + escape(req["id"]), "obligation",
                      [{"artifact": names["sidecar"], "pointer": target + f"/obligations/{k}", "kind": "obligation"}])
    trace("/predictions", "predictions", "", "prediction")
    raw_sidecar = encode(sidecar)
    manifest["metadata"]["state_records"] = {"version": "state-records-v1", "sha256": sha(raw_sidecar)}
    try:
        intake = validate_state_records(manifest, raw_sidecar)
    except IntakeError as exc:
        raise MappingError(exc.code, exc.path, exc.detail) from exc
    graph = EventGraph(manifest)
    for pid, probe in probes.items():
        for oid in probe["requirements"]:
            obligation = manifest["obligations"][oid]
            begin, end = obligation["begin_after"], obligation["end_before"]
            need(bool(graph.dominators[pid] & graph.bits[begin]) and
                 (end == "$trial_end" or not (graph.ancestors[pid] & graph.bits[end])),
                 "probe_obligation_inactive", source_prefix + "/probes/" + pid, "tested requirement is not active on every incoming path")
    files = {names["manifest"]: encode(manifest), names["sidecar"]: raw_sidecar,
             names["keys"]: encode({p["id"]: nodes[p["id"]]["expected"] for p in task["probes"]}),
             names["field_map"]: encode(task["field_map"]), names["predictions"]: encode(set_order(task["predictions"])),
             names["intake"]: encode(intake)}
    return files, traces


def map_authoring(raw):
    try:
        document = validate_authoring(raw)
    except AuthoringError as exc:
        raise MappingError(exc.code, exc.path, exc.detail) from exc
    files, traces, tasks = {"source.json": raw}, {}, []
    index = {"version": VERSION, "authoring_format_version": document["version"], "brief_version": document["brief_version"],
             "dataset": document["dataset"], "source_sha256": sha(raw), "tasks": tasks,
             "counts": {"tasks": len(document["tasks"]), "families": {}, "coverage_tags": {}},
             "family_predictions": "family-predictions.json"}
    prediction_summary = {}
    for i, task in enumerate(document["tasks"]):
        prefix = f"task-{i+1:04d}"
        names = {kind: prefix + "." + kind + ".json" for kind in
                 ("manifest", "sidecar", "keys", "field_map", "predictions", "derivation", "intake")}
        derived, mappings = map_task(task, f"/tasks/{i}", names)
        files.update(derived)
        traces.update(mappings)
        family_summary = prediction_summary.setdefault(task["family"], {
            arm: {"failing": [], "not_failing": [], "unknown": [], "reasons": []} for arm in "ABCDEF"})
        for prediction in task["predictions"]:
            grouping = "unknown" if prediction["failing"] is None else "failing" if prediction["failing"] else "not_failing"
            family_summary[prediction["arm"]][grouping].append(task["id"])
            family_summary[prediction["arm"]]["reasons"].append({"task": task["id"], "reason": prediction["reason"]})
        traces[f"/tasks/{i}/predictions"].append({"artifact": "family-predictions.json", "pointer": "/families/" + task["family"], "kind": "prediction"})
        tasks.append({"id": task["id"], "family": task["family"], "coverage_tags": copy.deepcopy(task["coverage_tags"]),
                      **names, "manifest_sha256": sha(derived[names["manifest"]])})
        families = index["counts"]["families"]
        families[task["family"]] = families.get(task["family"], 0) + 1
        for key, value in task["coverage_tags"].items():
            tags = ["subcases=" + v for v in value] if key == "subcases" else [key + "=" + encode(value).decode("utf-8")]
            for tag in tags:
                index["counts"]["coverage_tags"][tag] = index["counts"]["coverage_tags"].get(tag, 0) + 1
    for arms in prediction_summary.values():
        for values in arms.values():
            for key in ("failing", "not_failing", "unknown"):
                values[key].sort()
            values["reasons"].sort(key=lambda item: item["task"])
    files["family-predictions.json"] = encode({"version": "prediction-summary-v1", "families": prediction_summary})
    for key, target in (("version", "authoring_format_version"), ("brief_version", "brief_version"), ("dataset", "dataset")):
        traces["/" + key] = [{"artifact": "bundle.json", "pointer": "/" + target, "kind": "metadata"}]
    traces[""] = [{"artifact": "bundle.json", "pointer": "", "kind": "metadata"}]
    traces["/tasks"] = [{"artifact": "bundle.json", "pointer": "/tasks", "kind": "metadata"}]
    entries = []
    for path in paths(document):
        prefix = path
        while prefix not in traces:
            prefix = prefix.rsplit("/", 1)[0]
        entries.append({"source": path, "targets": copy.deepcopy(traces[prefix]),
                        "mapping": "exact field" if prefix == path else "within mapped container"})
    for item in tasks:
        files[item["derivation"]] = encode({"version": "derivation-v1", "source_sha256": sha(raw),
            "task_id": item["id"], "entries": entries,
            "generated": ["question nodes deliver authored wording", "contiguous version numbers and neighbor links",
                          "correct continuation and declared rejection terminals", "exact-text SHA-256", "sorted set collections"]})
    files["bundle.json"] = encode(index)
    return files


def recover_source(files):
    try:
        index = decode(files["bundle.json"])
        raw = files["source.json"]
        need(sha(raw) == index["source_sha256"], "bundle_changed", "source.json", "source bytes changed")
        need(map_authoring(raw) == files, "bundle_changed", "bundle", "derived bytes changed or artifacts missing")
        return raw
    except (KeyError, InvalidRecord) as exc:
        raise MappingError("bundle_changed", "bundle", "missing or malformed derived artifact") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        output = Path(args.output)
        need(not output.exists(), "output_exists", str(output), "refuse to overwrite derived bundle")
        files = map_authoring(read_bounded(args.source, MAX_BYTES))
        output.mkdir(parents=True, exist_ok=False)
        for name, raw in sorted(files.items()):
            (output / name).write_bytes(raw)
        result = {"version": VERSION, "status": "mapped", "files": len(files), "semantics_verified": False}
    except IntakeError as exc:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}, sort_keys=True))
        return 2
    except OSError:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": "file_unavailable"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
