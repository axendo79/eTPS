"""Offline finite-branch runner. Executes supplied response fixtures, never models."""
import base64
import sqlite3
from fractions import Fraction
from pathlib import Path

from . import scorer
from .scorer import InvalidRecord, classify, identity, mapping, require, score, summarize, validate
from .workload import LEGACY_INVALIDATION_POLICY, decode, encode, raw_response, script_responses, sha, validate_bundle


def implementation():
    return {"scorer_sha256": sha(Path(scorer.__file__).read_bytes()),
            "runner_sha256": sha(Path(__file__).read_bytes())}


def answer_from_raw(raw):
    try:
        answer = decode(raw)
        # The finite answer language is a flat string-field object. Do not let
        # arbitrary decoded JSON (infinities, surrogates, deep containers) reach
        # journal serialization. Raw bytes remain on the response event.
        if not isinstance(answer, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in answer.items()):
            return None
        for key, value in answer.items():
            key.encode("utf-8")
            value.encode("utf-8")
        return answer
    except (InvalidRecord, UnicodeError, RecursionError, OverflowError):
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
                raw = raw_response(response["raw_base64"])
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
                "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else
                "storage_error" if isinstance(exc, (sqlite3.Error, OSError)) and
                "storage_error" in store.plan["invalidation_policy"] else "execution_error")
            store.abort(slot, code, f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise
    return replay_slot(store, slot)


def replay_slot(store, slot, allow_running=False):
    entries = store.entries(slot)
    manifest = store.manifest(slot)
    findings = validate(manifest, authoring=False)
    warnings = ["authoring_findings: " + code for code in sorted({f["code"] for f in findings})]
    if not entries:
        return {"slot": slot, "state": "unattempted", "score": None, "reason": "unattempted",
                "warnings": warnings, "authoring_findings": findings, "evidence_verified": None}
    mapping(entries[0]["payload"], "journal.start")
    recorded = {k: entries[0]["payload"].get(k) for k in implementation()}
    current_implementation = implementation()
    mismatches = [k for k, value in current_implementation.items() if recorded[k] != value]
    if mismatches:
        warnings.append("implementation_mismatch: values recomputed with current code")
    if store.plan["schema"] == "etps-offline-plan-v1":
        warnings.append("legacy_plan: positional boundaries/unit/policy may be unpinned")
    state = {"finish": "finished", "abort": "aborted"}.get(entries[-1]["kind"], "running")
    script_hash = store.slots[slot]["script_sha256"]
    responses = script_responses(store.artifacts[script_hash])
    response_index, evidence_issues = 0, []
    events, messages, pending = [], [], None
    for entry in entries[1:]:
        kind, payload = entry["kind"], entry["payload"]
        mapping(payload, "journal." + kind)
        if kind == "request":
            mapping(payload, "journal.request", ("messages", "node"))
            identity(payload["node"], "journal.request.node")
            require(pending is None and payload["messages"] == messages, "request history mismatch")
            pending = payload["node"]
        elif kind == "event":
            event = payload
            mapping(event, "journal.event", ("kind", "node"))
            identity(event["node"], "journal.event.node")
            if event["kind"] == "user":
                mapping(event, "journal.event.user", ("text",))
                require(pending is None, "user event before pending response")
                messages.append({"role": "user", "text": event["text"]})
            elif event["kind"] == "probe":
                mapping(event, "journal.event.probe", ("raw_base64", "answer", "status"))
                require(pending == event["node"], "probe lacks matching request intent")
                raw = raw_response(event["raw_base64"])
                projected = answer_from_raw(raw)
                if event["answer"] != projected:
                    # Old journals stored arbitrary JSON shapes before malformed
                    # classification. Accept only an exact, serializable decode.
                    legacy = decode(raw)
                    require(projected is None and encode(event["answer"]) == encode(legacy),
                            "raw answer projection mismatch")
                    warnings.append("legacy_answer_projection: malformed JSON shape retained")
                if response_index >= len(responses):
                    evidence_issues.append({"code": "script_exhausted", "response_index": response_index})
                else:
                    expected = responses[response_index]
                    changed = []
                    if event["status"] != expected["status"]:
                        changed.append("status")
                    if raw != raw_response(expected["raw_base64"]):
                        changed.append("raw_bytes")
                    if encode(event.get("generation")) != encode(expected.get("generation")):
                        changed.append("generation")
                    if changed:
                        evidence_issues.append({"code": "script_response_mismatch",
                                                "response_index": response_index, "fields": changed})
                response_index += 1
                messages.append({"role": "assistant", "raw_base64": event["raw_base64"]})
                pending = None
            else:
                raise InvalidRecord("unsupported persisted event")
            events.append(event)
    record = {"manifest_sha256": scorer.digest(manifest), "events": events, "wall_seconds": None,
              "purpose": "offline-verification"}
    result = score(manifest, record)
    recomputed = dict(result)
    if (state == "finished" or allow_running) and response_index < len(responses):
        evidence_issues.append({"code": "script_leftover", "consumed": response_index,
                                "script_responses": len(responses)})
    if result["legacy_unknown_probes"]:
        warnings.append("legacy_unknown_answers: historical implicit shapes used during replay")
    if state != "finished" and not allow_running:
        result.update(measurement_valid=False, reason="unfinished_slot", R=None, RR=None,
                      rr_unavailable_reason="unfinished_slot", accepted=None, experimental_eTPS=None)
    if state == "finished":
        finish = entries[-1]["payload"]
        if pending is not None:
            evidence_issues.append({"code": "unfinished_request"})
        if not result["measurement_valid"]:
            warnings.append("recomputed_measurement_invalid")
            evidence_issues.append({"code": "invalid_finished_trace"})
        if "terminal" not in finish or finish["terminal"] != result["terminal"]:
            evidence_issues.append({"code": "finish_terminal_mismatch",
                                    "reached_terminal": result["terminal"]})
        expected_reason = None if result["accepted"] else "system_terminal_failure"
        if "reason_code" not in finish and store.plan["schema"] == "etps-offline-plan-v1":
            warnings.append("legacy_finish_reason_missing: acceptance recomputed from events")
        elif "reason_code" not in finish or finish["reason_code"] != expected_reason:
            evidence_issues.append({"code": "finish_reason_mismatch", "expected_reason_code": expected_reason})
        stored_resolution = entries[-1]["payload"].get("resolved_obligations")
        if stored_resolution is not None and stored_resolution != result["resolved_obligations"]:
            warnings.append("resolved_obligations_differ_from_recorded")
    elif state == "aborted":
        policy = store.plan.get("invalidation_policy", LEGACY_INVALIDATION_POLICY)
        code = entries[-1]["payload"].get("reason_code")
        if not isinstance(code, str) or policy.get(code) != "invalidate":
            evidence_issues.append({"code": "abort_reason_invalid"})
    if evidence_issues:
        warnings.extend("unverified_evidence: " + code for code in
                        sorted({issue["code"] for issue in evidence_issues}))
        result.update(measurement_valid=False, reason="unverified_evidence", R=None, RR=None,
                      rr_unavailable_reason="unverified_evidence", accepted=None, TPS=None,
                      experimental_eTPS=None)
    return {"slot": slot, "arm": store.slots[slot]["arm"], "task": store.slots[slot]["task"],
            "state": state, "evidence": "synthetic-offline", "record": record,
            "reason": entries[-1]["payload"].get("reason"),
            "reason_code": entries[-1]["payload"].get("reason_code"),
            "warnings": warnings, "implementation_mismatch": bool(mismatches),
            "evidence_verified": not evidence_issues, "evidence_issues": evidence_issues,
            "recomputed_score": recomputed if evidence_issues else None,
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
            "evidence_unverified": sum(t.get("evidence_verified") is False for t in trials),
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
    mapping(bundle, "export", ("format", "plan_base64", "plan_sha256", "artifacts", "journal"))
    mapping(bundle["artifacts"], "export.artifacts")
    mapping(bundle["journal"], "export.journal")
    class ExportView:
        def entries(self, slot):
            previous = sha(encode([self.plan_hash, slot]))
            state = "unattempted"
            entries = bundle["journal"][slot]
            require(isinstance(entries, list), f"export.journal.{slot}: expected list")
            for i, entry in enumerate(entries):
                mapping(entry, f"export.journal.{slot}[{i}]", ("kind", "payload", "sha256"))
                kind = entry["kind"]
                identity(kind, f"export.journal.{slot}[{i}].kind")
                mapping(entry["payload"], f"export.journal.{slot}[{i}].payload")
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
    view.plan_raw = raw_response(bundle["plan_base64"], "export.plan_base64")
    view.plan_hash = sha(view.plan_raw)
    require(view.plan_hash == bundle["plan_sha256"], "export plan hash mismatch")
    view.artifacts = {k: raw_response(v, "export.artifacts." + k) for k, v in bundle["artifacts"].items()}
    view.plan = validate_bundle(view.plan_raw, view.artifacts, allow_legacy=True,
                                authoring=validate_authoring)
    view.slots = {s["id"]: s for s in view.plan["slots"]}
    require(set(bundle["journal"]) == set(view.slots), "export omitted planned slots")
    result = report(view)
    result["authoring_gate_reasserted"] = validate_authoring
    return result
