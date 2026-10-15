"""Content-free opt-in answer-contract diagnostic for a mapper bundle.

Run: python -B -m etps_v02.conformance path/to/bundle.json
Exit 0: no detected violations. Exit 2: violations or malformed input.
Only fixed schema/rule IDs, task IDs, field names and counts are emitted.
"""
from collections import Counter
import copy
import json
from pathlib import Path
import sys

from .intake.state_records import EventGraph, projected
from .question_contract import apply, digest, is_junction, read_named, read_release, unique_json

SCHEMA = "etps-conformance-v1"
STATUSES = ("active", "expired", "unestablished", "unresolved")


def check_bundle(bundle):
    violations = Counter()
    tasks_checked = fields_checked = 0

    def issue(task, field, rule):
        violations[task, field, rule] += 1

    try:
        bundle = Path(bundle)
        if (bundle.name != "bundle.json" or bundle.is_symlink() or is_junction(bundle) or
                bundle.parent.is_symlink() or is_junction(bundle.parent)):
            raise ValueError("file boundary")
        root = bundle.parent
        raw = read_named(root, "bundle.json")
        index = unique_json(raw)
        release = read_release(root, digest(raw))
        if release is None:
            issue("", "", "R1-CONTRACT")
        elif index.get("version") != "authoring-mapper-v1":
            issue("", "", "R1-BUNDLE")
        else:
            if type(index["tasks"]) is not list or not index["tasks"]:
                raise ValueError("tasks required")
            task_ids = [item["id"] for item in index["tasks"]]
            if any(type(tid) is not str for tid in task_ids) or len(task_ids) != len(set(task_ids)):
                raise ValueError("task identity")
            for item in index["tasks"]:
                tid = item["id"]
                tasks_checked += 1
                try:
                    manifest = unique_json(read_named(root, item["manifest"]))
                    side_raw = read_named(root, item["sidecar"])
                    side = unique_json(side_raw)
                    keys = unique_json(read_named(root, item["keys"]))
                    loaded = {"question_contract": release, "tasks": index["tasks"],
                              "files": {item["sidecar"]: side_raw}}
                    try:
                        apply(loaded, item, copy.deepcopy(manifest))
                    except (ValueError, KeyError, TypeError):
                        issue(tid, "", "R1-DESCRIPTOR")
                    records = {r["id"]: r for r in side["records"]}
                    for record in records.values():
                        labels = record.get("status_values", {})
                        for name in STATUSES:
                            if labels.get(name) != name:
                                issue(tid, "status_values", "R1-LABEL")
                        if set(labels) != set(STATUSES):
                            issue(tid, "status_values", "R1-LABEL")
                        for version in record["versions"]:
                            if version["status"] not in ("active", "expired", "unresolved"):
                                issue(tid, "status", "R1-STATE-LABEL")
                            if version["status"] == "active" and version["value"] is None:
                                issue(tid, "value", "R1-ACTIVE-NULL")
                    graph = EventGraph(manifest)
                    questions = release["declaration"]["tasks"][tid]["questions"]
                    probes = {p: n for p, n in manifest["nodes"].items() if n["kind"] == "probe"}
                    if set(keys) != set(probes):
                        issue(tid, "", "R1-KEY-FIELDS")
                    for pid, node in probes.items():
                        spec = questions.get(pid)
                        if spec is None:
                            continue
                        names = set(spec["fields"])
                        if set(node.get("set_fields", [])) != {f for f, d in spec["fields"].items() if d["kind"] == "set"}:
                            issue(tid, "", "R1-SET-DECLARATION")
                        for answer in (node["expected"], keys.get(pid, {})):
                            if type(answer) is not dict:
                                issue(tid, "", "R1-KEY-FIELDS")
                                continue
                            if set(answer) != names:
                                issue(tid, "", "R1-KEY-FIELDS")
                            for field, desc in spec["fields"].items():
                                fields_checked += 1
                                if field not in answer:
                                    continue
                                value = answer[field]
                                query = side["fields"][field]
                                kind = desc["kind"]
                                record = records[query["record"]]
                                point = query.get("checkpoint") if query["kind"] == "at-checkpoint" else pid
                                version = graph.at(record["versions"], point, "checker")
                                if kind == "status":
                                    status = version["status"] if version else "unestablished"
                                    if type(value) is not str or value not in STATUSES:
                                        issue(tid, field, "R1-STATUS")
                                    elif value != status:
                                        issue(tid, field, "R1-STATUS-PROJECTION")
                                elif kind == "missing_status":
                                    if value != "missing_information" or query["kind"] != "missing_information":
                                        issue(tid, field, "R1-STATUS")
                                    missing = records[query["missing_item"]]
                                    if graph.at(missing["versions"], pid, "checker") is not None:
                                        issue(tid, field, "R1-MISSING-DESIGNATION")
                                elif kind == "set":
                                    if type(value) is not list:
                                        issue(tid, field, "R1-SET-FORM")
                                        continue
                                    expected_type = int if desc["value_type"] == "integer" else str
                                    if any(type(v) is not expected_type for v in value):
                                        issue(tid, field, "R1-TYPE")
                                    identities = [json.dumps([type(v).__name__, v], sort_keys=True) for v in value]
                                    if len(identities) != len(set(identities)):
                                        issue(tid, field, "R1-SET-DUPLICATE")
                                    projected_set = projected(record, version, "values")
                                    if sorted(identities) != sorted(json.dumps([type(v).__name__, v], sort_keys=True) for v in projected_set):
                                        issue(tid, field, "R1-SET-PROJECTION")
                                elif kind == "scalar":
                                    expected_type = int if desc["value_type"] == "integer" else str
                                    if value is not None and type(value) is not expected_type:
                                        issue(tid, field, "R1-TYPE")
                                    should_be_null = version is None or version["status"] != "active"
                                    if value in ("null", "") or (value is None) != should_be_null:
                                        issue(tid, field, "R1-TYPED-NULL")
                                elif kind in ("source", "item", "other"):
                                    expected = (projected(record, version, "provenance") if kind == "source" else
                                                query["missing_item"] if kind == "item" else None)
                                    if value is not None and (type(value) is not str or value != value.strip() or
                                                              value.startswith("[") or value.endswith("]")):
                                        issue(tid, field, "R1-BARE-ID")
                                    if kind in ("source", "item") and (type(value) is not type(expected) or value != expected):
                                        issue(tid, field, "R1-ID-PROJECTION")
                                    if value in ("null", "") or kind == "item" and value is None:
                                        issue(tid, field, "R1-TYPED-NULL")
                        if keys.get(pid) != node["expected"]:
                            issue(tid, "", "R1-KEY-BINDING")
                except (ValueError, TypeError, KeyError, OSError, UnicodeError, AttributeError):
                    issue(tid, "", "R1-STRUCTURE")
    except Exception:
        # Never serialize an exception: parsers and OS errors can carry content.
        issue("", "", "R1-INPUT")
    rows = [{"task_id": t, "field_name": f, "rule_id": r, "count": n}
            for (t, f, r), n in sorted(violations.items())]
    return {"schema": SCHEMA, "tasks_checked": tasks_checked, "fields_checked": fields_checked,
            "violation_count": sum(violations.values()), "violations": rows}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    # Avoid argparse's argument/path echoes, including on malformed invocations.
    result = check_bundle(args[0] if len(args) == 1 else None)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 2 if result["violation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
