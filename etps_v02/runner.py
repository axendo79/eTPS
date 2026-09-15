"""Offline finite-branch runner. Executes supplied response fixtures, never models."""
import base64
from fractions import Fraction
from pathlib import Path

from . import scorer
from .scorer import InvalidRecord, classify, require, score, summarize, validate
from .workload import decode, encode, script_responses, sha, validate_bundle


def implementation():
    return {"scorer_sha256": sha(Path(scorer.__file__).read_bytes()),
            "runner_sha256": sha(Path(__file__).read_bytes())}


def answer_from_raw(raw):
    try:
        return decode(raw)
    except InvalidRecord:
        return None  # Preserve bytes; malformed is a system outcome, not a protocol fix.


class OfflineFailure(InvalidRecord):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def _next_response(responses, index, messages):
    """Adapter boundary: receives public conversation only, no answer keys/arm IDs."""
    if index >= len(responses):
        raise OfflineFailure("script_exhausted", "response script exhausted: corpus coverage defect")
    return decode(encode(responses[index]))


def run_offline(store, slot):
    require(store.plan["schema"] == "etps-offline-plan-v2", "legacy plans are replay-only; author a new plan")
    manifest = store.manifest(slot)
    validate(manifest)  # Old evidence can replay; new execution must pass current authoring checks.
    script_hash = store.slots[slot]["script_sha256"]
    responses = script_responses(store.artifacts[script_hash])
    store.append(slot, "start", {"evidence": "synthetic-offline", **implementation()})
    current, index, messages = manifest["start"], 0, []
    try:
        while manifest["nodes"][current]["kind"] != "terminal":
            node = manifest["nodes"][current]
            if node["kind"] == "user":
                event = {"node": current, "kind": "user", "text": node["text"]}
                store.append(slot, "event", event)
                messages.append({"role": "user", "text": node["text"]})
                current = node["next"]
            else:
                # Intent is durable before the adapter is called. A crash never
                # silently resumes or reissues this request.
                store.append(slot, "request", {"node": current, "messages": messages})
                response = _next_response(responses, index, decode(encode(messages)))
                index += 1
                raw = base64.b64decode(response["raw_base64"], validate=True)
                event = {"node": current, "kind": "probe", **response,
                         "answer": answer_from_raw(raw)}
                store.append(slot, "event", event)
                messages.append({"role": "assistant", "raw_base64": response["raw_base64"]})
                current = node["next"][classify(event, node["expected"], node["unknown_answers"])]
        if index != len(responses):
            raise OfflineFailure("script_leftover", "unused scripted responses: authoring count error")
        result = replay_slot(store, slot, allow_running=True)
        require(result["score"] is not None and result["score"]["measurement_valid"],
                "completed path has invalid scoring provenance")
        # Offline execution speed is not model task time. Do not manufacture wall TPS.
        store.append(slot, "finish", {"terminal": current, "wall_seconds": None,
                                      "resolved_obligations": result["score"]["resolved_obligations"],
                                      "reason_code": None if result["score"]["accepted"] else "system_terminal_failure"})
    except BaseException as exc:
        # If persistence itself failed, keep the durable prefix and propagate.
        # Reopen then explicitly abort it; never imply exactly-once external delivery.
        try:
            code = exc.code if isinstance(exc, OfflineFailure) else (
                "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "execution_error")
            store.abort(slot, code, f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
    return replay_slot(store, slot)


def replay_slot(store, slot, allow_running=False):
    entries = store.entries(slot)
    if not entries:
        return {"slot": slot, "state": "unattempted", "score": None, "reason": "unattempted"}
    recorded = {k: entries[0]["payload"].get(k) for k in implementation()}
    current_implementation = implementation()
    mismatches = [k for k, value in current_implementation.items() if recorded[k] != value]
    warnings = ["implementation_mismatch: values recomputed with current code"] if mismatches else []
    if store.plan["schema"] == "etps-offline-plan-v1":
        warnings.append("legacy_plan: positional boundaries/unit/policy may be unpinned")
    manifest = store.manifest(slot)
    state = {"finish": "finished", "abort": "aborted"}.get(entries[-1]["kind"], "running")
    events, messages, pending = [], [], None
    for entry in entries[1:]:
        kind, payload = entry["kind"], entry["payload"]
        if kind == "request":
            require(pending is None and payload["messages"] == messages, "request history mismatch")
            pending = payload["node"]
        elif kind == "event":
            event = payload
            if event["kind"] == "user":
                require(pending is None, "user event before pending response")
                messages.append({"role": "user", "text": event["text"]})
            elif event["kind"] == "probe":
                require(pending == event["node"], "probe lacks matching request intent")
                raw = base64.b64decode(event["raw_base64"], validate=True)
                require(event["answer"] == answer_from_raw(raw), "raw answer projection mismatch")
                messages.append({"role": "assistant", "raw_base64": event["raw_base64"]})
                pending = None
            else:
                raise InvalidRecord("unsupported persisted event")
            events.append(event)
    record = {"manifest_sha256": scorer.digest(manifest), "events": events, "wall_seconds": None,
              "purpose": "offline-verification"}
    result = score(manifest, record)
    if result["authoring_findings"]:
        warnings.append("authoring_findings: repeated failure grants recomputed without duplicate credit")
    if result["legacy_unknown_probes"]:
        warnings.append("legacy_unknown_answers: historical implicit shapes used during replay")
    if state != "finished" and not allow_running:
        result.update(measurement_valid=False, reason="unfinished_slot", R=None, RR=None,
                      rr_unavailable_reason="unfinished_slot", accepted=None, experimental_eTPS=None)
    if state == "finished":
        require(pending is None, "unfinished request in finished journal")
        if not result["measurement_valid"]:
            warnings.append("recomputed_measurement_invalid")
        stored_resolution = entries[-1]["payload"].get("resolved_obligations")
        if stored_resolution is not None and stored_resolution != result["resolved_obligations"]:
            warnings.append("resolved_obligations_differ_from_recorded")
    return {"slot": slot, "arm": store.slots[slot]["arm"], "task": store.slots[slot]["task"],
            "state": state, "evidence": "synthetic-offline", "record": record,
            "reason": entries[-1]["payload"].get("reason"),
            "reason_code": entries[-1]["payload"].get("reason_code"),
            "warnings": warnings, "implementation_mismatch": bool(mismatches),
            "implementation": {"recorded": recorded, "current": current_implementation, "changed": mismatches},
            "recorded_resolution": entries[-1]["payload"].get("resolved_obligations"),
            "score": result}


def report(store):
    trials = [replay_slot(store, slot["id"]) for slot in store.plan["slots"]]
    counts = {state: sum(t["state"] == state for t in trials)
              for state in ("unattempted", "running", "aborted", "finished")}
    finished = [t["score"] for t in trials if t["state"] == "finished"]
    rr_available = sum(r["measurement_valid"] and r["RR"] is not None for r in finished)
    accepted = sum(r["accepted"] is True for r in finished)
    attempted = len(trials) - counts["unattempted"]
    groups = {}
    for slot, trial in zip(store.plan["slots"], trials):
        groups.setdefault((slot["task"], slot["arm"]), []).append(trial)
    summaries = []
    for (task, arm), grouped in groups.items():
        metrics = summarize([t["score"] for t in grouped if t["score"] is not None], planned=len(grouped))
        summaries.append({"task": task, "arm": arm,
                          "task_artifact_sha256": store.plan["tasks"][task], **metrics})
    return {"purpose": "offline-verification", "plan_sha256": store.plan_hash,
            "summaries": summaries,
            "planned": len(trials), "attempted": attempted, **counts,
            "accepted": accepted, "failed": sum(r["accepted"] is False for r in finished),
            "measurement_valid": sum(r["measurement_valid"] for r in finished), "rr_available": rr_available,
            "implementation_mismatch": any(t.get("implementation_mismatch") for t in trials),
            "warnings": sorted({w for t in trials for w in t.get("warnings", [])}),
            "rr_unavailable_attempted": attempted - rr_available,
            "comparison_incomplete": rr_available != len(trials),
            "trials": trials}


def json_default(value):
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    raise TypeError(type(value).__name__)


def export_bundle(store):
    """Lossless input/journal export plus derived observations, not a public release."""
    return {"format": "etps-offline-export-v1", "plan_sha256": store.plan_hash,
            "plan_base64": base64.b64encode(store.plan_raw).decode("ascii"),
            "artifacts": {key: base64.b64encode(raw).decode("ascii") for key, raw in store.artifacts.items()},
            "journal": {slot: store.entries(slot) for slot in store.slots}, "report": report(store)}


def replay_export(bundle, *, validate_authoring=False):
    """Recompute from exported evidence without trusting its old derived report."""
    class ExportView:
        def entries(self, slot):
            previous = sha(encode([self.plan_hash, slot]))
            state = "unattempted"
            entries = bundle["journal"][slot]
            for i, entry in enumerate(entries):
                kind = entry["kind"]
                expected = sha(encode([slot, i, kind, previous]) + encode(entry["payload"]))
                require(entry["sha256"] == expected, "export journal integrity failure")
                require((i == 0 and kind == "start") or
                        (state == "running" and kind in {"event", "request", "finish", "abort"}),
                        "invalid export lifecycle")
                state = {"start": "running", "finish": "finished", "abort": "aborted"}.get(kind, state)
                previous = expected
            return entries

        def manifest(self, slot):
            return decode(self.artifacts[self.plan["tasks"][self.slots[slot]["task"]]])

    require(bundle["format"] == "etps-offline-export-v1", "unsupported export format")
    view = ExportView()
    view.plan_raw = base64.b64decode(bundle["plan_base64"], validate=True)
    view.plan_hash = sha(view.plan_raw)
    require(view.plan_hash == bundle["plan_sha256"], "export plan hash mismatch")
    view.artifacts = {k: base64.b64decode(v, validate=True) for k, v in bundle["artifacts"].items()}
    view.plan = validate_bundle(view.plan_raw, view.artifacts, allow_legacy=True,
                                authoring=validate_authoring)
    view.slots = {s["id"]: s for s in view.plan["slots"]}
    require(set(bundle["journal"]) == set(view.slots), "export omitted planned slots")
    result = report(view)
    result["authoring_gate_reasserted"] = validate_authoring
    return result
