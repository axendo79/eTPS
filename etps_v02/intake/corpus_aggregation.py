"""State-evolution diagnostics per arm within exactly one declared plan/repeat."""
import argparse
import base64
from collections import Counter
import json
from pathlib import Path

from ..dimension_accuracy import DIMENSIONS, fields_for
from ..scorer import InvalidRecord, OUTCOMES, digest
from ..workload import decode, encode, sha, validate_bundle
from .authoring import field_map
from .state_records import IntakeError, read_bounded

VERSION = "corpus-aggregation-v1"
MAX_REPORT_BYTES = 64 * 1024 * 1024


class AggregationError(IntakeError):
    pass


def need(condition, code, path, detail):
    if not condition:
        raise AggregationError(code, path, detail)


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator} if denominator else None


def observations(trial):
    scored = trial.get("score")
    if not scored or not trial.get("record"):
        return []
    events, labels = trial["record"]["events"], scored["classifications"]
    need(len(events) == len(labels), "report_shape", trial["slot"], "classification/event count differs")
    return [(event, label["class"]) for event, label in zip(events, labels)
            if event["kind"] == "probe" and label["class"] in OUTCOMES]


def phase_fields(manifest, trial, logical, phase):
    observed = observations(trial)
    event, outcome = observed[0 if phase == "first_attempt" else -1] if observed else (None, None)
    score = trial.get("score")
    node = manifest["nodes"][event["node"]] if event else None
    supplied = {name: query["dimension"] for name, query in logical.items() if node and name in node["expected"]}
    available = fields_for(manifest, node, event, outcome, supplied) if event else {}
    invalid = score is not None and not score["measurement_valid"]
    invalid_reason = (trial.get("reason_code") if trial["state"] == "aborted" and
                      score and score.get("reason") == "unfinished_slot" else None) or (score.get("reason") if score else None)
    result = {}
    for name in logical:
        attempted = int(name in supplied)
        if trial["state"] == "unattempted":
            status, reason = "unattempted", "unattempted"
        elif invalid:
            status, reason = "unavailable", invalid_reason or "invalid_measurement"
        elif phase == "terminal" and trial["state"] != "finished":
            status, reason = "unavailable", trial.get("reason_code") or "no_terminal_answer"
        elif event is None:
            status, reason = "unavailable", "no_scored_answer"
        elif name not in supplied:
            status, reason = "unavailable", "field_not_supplied"
        else:
            status = available[name]
            reason = "timeout" if outcome == "timeout" else status
        result[name] = {"status": status, "reason": reason, "attempted": attempted}
    return result


def bucket(rows):
    acceptance = {"planned": len(rows), "attempted": 0, "accepted": 0, "failed": 0, "unavailable": 0, "unattempted": 0}
    reasons = Counter()
    for row in rows:
        trial, scored = row["trial"], row["trial"].get("score")
        acceptance["attempted"] += trial["state"] != "unattempted"
        if trial["state"] == "unattempted":
            acceptance["unattempted"] += 1
            reasons["unattempted"] += 1
        elif scored and scored["measurement_valid"] and trial["state"] == "finished":
            if scored["accepted"]:
                acceptance["accepted"] += 1
            else:
                acceptance["failed"] += 1
                observed = observations(trial)
                reasons[observed[-1][1] if observed else "task_failed"] += 1
        else:
            acceptance["unavailable"] += 1
            reasons[trial.get("reason_code") or (scored or {}).get("reason") or "no_terminal_result"] += 1
    acceptance["reason_counts"] = dict(sorted(reasons.items()))
    acceptance["accepted_over_planned"] = ratio(acceptance["accepted"], acceptance["planned"])
    acceptance["complete_rate"] = (ratio(acceptance["accepted"], acceptance["planned"])
                                    if not acceptance["unattempted"] and not acceptance["unavailable"] else None)
    result = {"acceptance": acceptance}
    for phase in ("first_attempt", "terminal"):
        result[phase] = {}
        for dimension in DIMENSIONS:
            fields = [row[phase][name] for row in rows for name, query in row["logical"].items() if query["dimension"] == dimension]
            correct = sum(f["status"] == "correct" for f in fields)
            reasons = Counter(f["status"] for f in fields if f["status"] != "correct")
            unavailable = Counter(f["reason"] for f in fields if f["status"] == "unavailable")
            result[phase][dimension] = {"correct": correct, "planned": len(fields),
                "attempted": sum(f["attempted"] for f in fields), "unavailable": sum(unavailable.values()),
                "unattempted": reasons["unattempted"], "accuracy": ratio(correct, len(fields)),
                "reason_counts": dict(sorted(reasons.items())), "unavailable_reasons": dict(sorted(unavailable.items()))}
    return result


def coverage_labels(coverage):
    result = []
    for name, value in sorted(coverage.items()):
        result.extend("subcases=" + v for v in sorted(value)) if name == "subcases" else result.append(name + "=" + encode(value).decode("utf-8"))
    return result


def _aggregate_report(plan_raw, artifacts, report, grouping):
    need(type(plan_raw) is bytes, "multiple_plans", "plan", "exactly one plan byte string required")
    need(type(report) is dict, "multiple_reports", "report", "exactly one per-plan report required")
    need(type(grouping) is dict and grouping.keys() == {"version", "repeat_id", "plan_sha256"},
         "grouping_fields", "grouping", "closed grouping declaration required")
    need(grouping["version"] == "corpus-grouping-v1" and type(grouping["repeat_id"]) is str and bool(grouping["repeat_id"]),
         "repeat_identity", "grouping", "exactly one nonempty repeat ID required")
    need(grouping["plan_sha256"] == sha(plan_raw) == report.get("plan_sha256"),
         "plan_mismatch", "report.plan_sha256", "report and frozen grouping must bind the exact plan bytes")
    try:
        plan = validate_bundle(plan_raw, artifacts, authoring=False, allow_remote=True)
    except InvalidRecord as exc:
        raise AggregationError("plan_invalid", "plan", str(exc)) from exc
    trials = report.get("trials")
    need(type(trials) is list and len(trials) == len(plan["slots"]), "slot_accounting", "report.trials", "preserve every planned slot once")
    by_id = {}
    for trial in trials:
        need(type(trial) is dict and type(trial.get("slot")) is str and trial["slot"] not in by_id,
             "slot_accounting", "report.trials", "duplicate or malformed trial ID")
        by_id[trial["slot"]] = trial
    need(by_id.keys() == {slot["id"] for slot in plan["slots"]}, "slot_accounting", "report.trials", "planned slot IDs differ")
    rows = []
    for slot in plan["slots"]:
        trial = by_id[slot["id"]]
        need(trial.get("state") in ("unattempted", "running", "aborted", "finished"), "report_shape", slot["id"], "unsupported trial state")
        need(all(trial.get(key, slot[key]) == slot[key] for key in ("arm", "task")), "slot_accounting", slot["id"], "trial identity differs")
        manifest = decode(artifacts[plan["tasks"][slot["task"]]])
        meta = manifest.get("metadata", {}).get("authoring", {})
        need(type(meta) is dict and all(k in meta for k in ("family", "coverage_tags", "logical_field_map")),
             "field_identity", slot["id"], "frozen authoring family/coverage/logical map missing")
        logical = meta["logical_field_map"]
        field_map(logical, slot["id"])
        for node in manifest["nodes"].values():
            if node["kind"] == "probe":
                need(node.get("field_dimensions") == {name: logical[name]["dimension"] for name in node["expected"] if name in logical}
                     and node["expected"].keys() <= logical.keys(), "field_identity", slot["id"], "probe redefines frozen fields")
        scored = trial.get("score")
        need(scored is None or type(scored) is dict and scored.get("manifest_sha256") == digest(manifest),
             "plan_mismatch", slot["id"], "score manifest binding differs")
        need(trial["state"] != "finished" or scored is not None, "report_shape", slot["id"], "finished trial lacks score")
        rows.append({"slot": slot, "trial": trial, "logical": logical, "family": meta["family"],
                     "tags": coverage_labels(meta["coverage_tags"]),
                     **{phase: phase_fields(manifest, trial, logical, phase) for phase in ("first_attempt", "terminal")}})
    arms = {}
    for arm in sorted({slot["arm"] for slot in plan["slots"]}):
        selected = [r for r in rows if r["slot"]["arm"] == arm]
        arms[arm] = {"overall": bucket(selected),
            "families": {family: bucket([r for r in selected if r["family"] == family]) for family in sorted({r["family"] for r in selected})},
            "coverage_tags": {tag: bucket([r for r in selected if tag in r["tags"]]) for tag in sorted({tag for r in selected for tag in r["tags"]})}}
    return {"version": VERSION, "plan_sha256": sha(plan_raw), "repeat_id": grouping["repeat_id"],
            "arms": arms, "slots": [{"slot": row["slot"]["id"], "arm": row["slot"]["arm"],
                                     "task": row["slot"]["task"], "state": row["trial"]["state"],
                                     "first_fields": row["first_attempt"], "terminal_fields": row["terminal"]} for row in rows]}


def aggregate_report(plan_raw, artifacts, report, grouping):
    """Reject corrupt report structure instead of leaking container exceptions."""
    try:
        return _aggregate_report(plan_raw, artifacts, report, grouping)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise AggregationError("report_shape", "report", "missing or malformed observation fields") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True)
    parser.add_argument("--grouping", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        from ..runner import replay_export
        exported = decode(read_bounded(args.export, MAX_REPORT_BYTES))
        report = replay_export(exported)
        plan_raw = base64.b64decode(exported["plan_base64"], validate=True)
        artifacts = {key: base64.b64decode(value, validate=True) for key, value in exported["artifacts"].items()}
        grouping = decode(read_bounded(args.grouping, 1024 * 1024))
        result = aggregate_report(plan_raw, artifacts, report, grouping)
        with Path(args.output).open("xb") as stream:
            stream.write(encode(result))
    except IntakeError as exc:
        print(json.dumps({"status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}, sort_keys=True))
        return 2
    except (OSError, InvalidRecord, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "rejected", "code": "evidence_unavailable", "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"version": VERSION, "status": "aggregated", "plan_sha256": result["plan_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
