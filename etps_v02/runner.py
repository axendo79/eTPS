"""Offline finite-branch runner. Executes supplied response fixtures, never models."""
import base64
import platform
import sqlite3
from fractions import Fraction
from pathlib import Path

from . import scorer
from .scorer import InvalidRecord, classify, identity, mapping, require, score, summarize, validate
from .workload import LEGACY_INVALIDATION_POLICY, decode, encode, raw_response, script_responses, sha, validate_bundle
from .workload import safety_warnings


def implementation():
    # Normalize source CRLF to LF, so identical source has the same identity on
    # Windows and Unix. Evidence/artifact bytes are never normalized.
    files = {path.name: sha(path.read_bytes().replace(b"\r\n", b"\n"))
             for path in sorted(Path(__file__).parent.glob("*.py"), key=lambda p: p.name)}
    return {"files_sha256": files, "python_version": platform.python_version(),
            "sqlite_version": sqlite3.sqlite_version,
            # Retain the old keys for partial start records and existing clients.
            "scorer_sha256": files["scorer.py"], "runner_sha256": files["runner.py"]}


def answer_from_raw(raw, answer_schema=None):
    try:
        answer = decode(raw)
        # Default: string fields; typed-v1 also admits exact int/null values.
        # Do not let
        # arbitrary decoded JSON (infinities, surrogates, deep containers) reach
        # journal serialization. Raw bytes remain on the response event.
        if not scorer.answer_object(answer, answer_schema):
            return None
        for key, value in answer.items():
            key.encode("utf-8")
            if isinstance(value, str):
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
    policy = store.plan.get("arms", {}).get(store.slots[slot]["arm"], {}).get("context_policy", "full")
    try:
        while manifest["nodes"][current]["kind"] != "terminal":
            node = manifest["nodes"][current]
            if node["kind"] == "user":
                event = {"node": current, "kind": "user", "text": node["text"]}
                store.append(slot, "event", event)
                messages.append({"role": "user", "text": node["text"]})
                current = node["next"]
            elif node["kind"] == "session_boundary":
                store.append(slot, "event", {"node": current, "kind": "session_boundary"})
                if policy == "reset-v1":
                    messages.clear()
                current = node["next"]
            else:
                # Intent is durable before the adapter is called. A crash never
                # silently resumes or reissues this request.
                store.append(slot, "request", {"node": current, "messages": messages})
                response = _next_response(responses, index, decode(encode(messages)))
                index += 1
                raw = raw_response(response["raw_base64"])
                event = {"node": current, "kind": "probe", **response,
                         "answer": answer_from_raw(raw, manifest.get("answer_schema"))}
                store.append(slot, "event", event)
                messages.append({"role": "assistant", "raw_base64": response["raw_base64"]})
                outcome = scorer.classify_probe(manifest, node, event)
                current, _ = scorer.route(manifest, node, event, outcome)
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
    if store.plan["schema"] == "etps-manual-plan-v1":
        from .manual_runner import replay_manual_slot
        return replay_manual_slot(store, slot)
    if store.plan["schema"] == "etps-live-plan-v1":
        from .live_runner import replay_live_slot
        return replay_live_slot(store, slot, allow_running=allow_running)
    entries = store.entries(slot)
    manifest = store.manifest(slot)
    findings = validate(manifest, authoring=False)
    warnings = ["authoring_findings: " + code for code in sorted({f["code"] for f in findings})]
    if not entries:
        return {"slot": slot, "state": "unattempted", "score": None, "reason": "unattempted",
                "warnings": warnings, "authoring_findings": findings, "evidence_verified": None}
    mapping(entries[0]["payload"], "journal.start")
    current_implementation = implementation()
    start = entries[0]["payload"]
    recorded = {k: start[k] for k in current_implementation if k in start}
    mismatches = set()
    partial = set(recorded) != set(current_implementation)
    for key, value in recorded.items():
        if key == "files_sha256":
            mapping(value, "journal.start.files_sha256")
            current_files = current_implementation[key]
            partial |= bool(current_files.keys() - value.keys())
            mismatches.update(name for name, digest in value.items() if current_files.get(name) != digest)
        elif value != current_implementation[key]:
            mismatches.add({"scorer_sha256": "scorer.py", "runner_sha256": "runner.py"}.get(key, key))
    mismatches = sorted(mismatches)
    if partial:
        warnings.append("legacy_implementation_identity: partial")
    if mismatches:
        warnings.append("implementation_mismatch: " + ", ".join(mismatches) +
                        "; values recomputed with current code")
    if store.plan["schema"] == "etps-offline-plan-v1":
        warnings.append("legacy_plan: positional boundaries/unit/policy may be unpinned")
    state = {"finish": "finished", "abort": "aborted"}.get(entries[-1]["kind"], "running")
    script_hash = store.slots[slot]["script_sha256"]
    responses = script_responses(store.artifacts[script_hash], admission=False)
    response_index, evidence_issues = 0, []
    events, messages, pending = [], [], None
    policy = store.plan.get("arms", {}).get(store.slots[slot]["arm"], {}).get("context_policy", "full")
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
            elif event["kind"] == "session_boundary":
                require(pending is None and set(event) == {"node", "kind"}, "invalid session boundary event")
                if policy == "reset-v1":
                    messages.clear()
            elif event["kind"] == "probe":
                mapping(event, "journal.event.probe", ("raw_base64", "answer", "status"))
                require(pending == event["node"], "probe lacks matching request intent")
                raw = raw_response(event["raw_base64"], admission=False)
                # The immutable manifest artifact binds projection schema; no
                # journal layout change or implicit upgrade of old answers.
                projected = answer_from_raw(raw, manifest.get("answer_schema"))
                same = (encode(event["answer"]) == encode(projected)
                        if "answer_schema" in manifest else event["answer"] == projected)
                if not same:
                    # Old journals stored arbitrary JSON shapes before malformed
                    # classification. Accept only an exact, serializable decode.
                    legacy = decode(raw, admission=False)
                    require("answer_schema" not in manifest and projected is None
                            and encode(event["answer"]) == encode(legacy),
                            "raw answer projection mismatch")
                    warnings.append("legacy_answer_projection: malformed JSON shape retained")
                if response_index >= len(responses):
                    evidence_issues.append({"code": "script_exhausted", "response_index": response_index})
                else:
                    expected = responses[response_index]
                    changed = []
                    if event["status"] != expected["status"]:
                        changed.append("status")
                    if raw != raw_response(expected["raw_base64"], admission=False):
                        changed.append("raw_bytes")
                    if encode(event.get("generation")) != encode(expected.get("generation")):
                        changed.append("generation")
                    if encode(event.get("usage")) != encode(expected.get("usage")):
                        changed.append("usage")
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
    if "result_state" in result and result["accepted"] is not True:
        result["result_state"] = "failed"
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
    result = _report(store)
    if "cache_policy" in store.plan:
        result["cache_policy"] = store.plan["cache_policy"]
    tolerance_tasks = {task for task, key in store.plan["tasks"].items()
                       if decode(store.artifacts[key], admission=False).get("answer_tolerance") == "d10-v1"}
    if tolerance_tasks:
        from .answer_tolerance import summary
        result["answer_tolerance"] = {}
        for arm in sorted({s["arm"] for s in store.plan["slots"]}):
            slots = [s for s in store.plan["slots"] if s["arm"] == arm and s["task"] in tolerance_tasks]
            ids = {s["id"] for s in slots}
            scores = [t["score"] for t in result["trials"] if t["slot"] in ids and t.get("score") is not None]
            result["answer_tolerance"][arm] = {"tasks": sorted({s["task"] for s in slots}),
                                              **summary(scores, len(slots))}
    from .session_profile import add_diagnostics
    add_diagnostics(store, result)
    if store.plan.get("response_extraction") == "fence-v1":
        rates = {arm: {"numerator": 0, "denominator": 0} for arm in store.plan["arms"]}
        for slot, trial in zip(store.plan["slots"], result["trials"]):
            schema = store.manifest(slot["id"]).get("answer_schema")
            rate = rates[slot["arm"]]
            for event in trial.get("record", {}).get("events", []):
                if event["kind"] == "probe" and event["status"] == "ok":
                    rate["denominator"] += 1
                    rate["numerator"] += answer_from_raw(raw_response(event["raw_base64"], admission=False), schema) is not None
        for rate in rates.values():
            rate["value"] = Fraction(rate["numerator"], rate["denominator"]) if rate["denominator"] else None
        result["strict_json_rate"] = rates
    if store.plan["purpose"] == "dev-manual":
        from .manual_runner import EVIDENCE
        result.update(evidence=EVIDENCE, publish_excluded=True, coding_correctness_verified=False,
                      wall_time_kind="operator-paced")
        return {"purpose": "dev-manual", "evidence": EVIDENCE, "publish_excluded": True,
                "coding_correctness_verified": False, "wall_time_kind": "operator-paced",
                "plan_sha256": store.plan_hash, "summaries": [], "trials": [],
                "dev_manual": result}
    return result


def _report(store):
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
    arms = sorted({slot["arm"] for slot in store.plan["slots"]})
    arm_pairing = {}
    for task in store.plan["tasks"]:
        by_arm = {}
        for arm in arms:
            grouped = groups.get((task, arm), [])
            by_arm[arm] = {
                "planned": len(grouped),
                "finished": sum(t["state"] == "finished" for t in grouped),
                "rr_available": sum(t["state"] == "finished" and t["score"]["measurement_valid"]
                                    and t["score"]["RR"] is not None for t in grouped),
            }
        arm_pairing[task] = {"arms": by_arm,
                             "equal_planned_counts": len({v["planned"] for v in by_arm.values()}) == 1}
    return {"purpose": store.plan["purpose"], "plan_sha256": store.plan_hash,
            "summaries": summaries,
            "planned": len(trials), "attempted": attempted, **counts,
            "accepted": accepted, "failed": sum(r["accepted"] is False for r in finished),
            "measurement_valid": sum(r["measurement_valid"] for r in finished), "rr_available": rr_available,
            "implementation_mismatch": any(t.get("implementation_mismatch") for t in trials),
            "evidence_unverified": sum(t.get("evidence_verified") is False for t in trials),
            "warnings": sorted({w for t in trials for w in t.get("warnings", [])} |
                               set(safety_warnings(store.plan_raw, store.artifacts))),
            "rr_unavailable_attempted": attempted - rr_available,
            "comparison_incomplete": rr_available != len(trials),
            # This describes accounting availability, not experimental comparability.
            "slot_accounting_complete": rr_available == len(trials),
            "arm_pairing": arm_pairing,
            "unverified_dimensions": ["schedule exposure equality across arms",
                                      "mandatory assertions beyond terminal Boolean",
                                      "budgets", "action constraints"],
            "trials": trials}


def json_default(value):
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    raise TypeError(type(value).__name__)


def export_bundle(store, format="v1", *, audience="evidence"):
    """Lossless input/journal export plus derived observations, not a public release."""
    require(format in ("v1", "v2"), "unsupported export format")
    require(audience in {"evidence", "leaderboard", "website"}, "unsupported export audience")
    require(audience == "evidence" or store.plan["purpose"] != "dev-manual",
            "dev-manual evidence is excluded from leaderboard/website publication")
    if format == "v2":
        # One read snapshot binds heads, journals and report even if another
        # connection appends. A savepoint preserves any caller-owned transaction.
        store.db.execute("SAVEPOINT export_v2")
        try:
            heads = {row["slot"]: {"count": row["count"], "hash": row["hash"], "state": row["state"]}
                     for row in store.db.execute("SELECT slot,count,hash,state FROM heads")}
            slot_order = [slot["id"] for slot in store.plan["slots"]]
            require(set(heads) == set(slot_order), "export head slot integrity failure")
            exported = export_bundle(store)  # Keep the v1 body and its report unchanged.
            exported["format"] = "etps-offline-export-v2"
            exported["envelope"] = {
                "slot_order": slot_order, "heads": heads,
                "envelope_sha256": sha(encode([store.plan_hash, slot_order, heads])),
            }
            return exported
        finally:
            store.db.execute("RELEASE SAVEPOINT export_v2")
    exported = {"format": "etps-offline-export-v1", "plan_sha256": store.plan_hash,
            "plan_base64": base64.b64encode(store.plan_raw).decode("ascii"),
            "artifacts": {key: base64.b64encode(raw).decode("ascii") for key, raw in store.artifacts.items()},
            "journal": {slot: store.entries(slot) for slot in store.slots}, "report": report(store)}
    if store.plan["purpose"] == "dev-manual":
        from .manual_runner import EVIDENCE
        exported.update(evidence=EVIDENCE, publish_excluded=True, coding_correctness_verified=False,
                        wall_time_kind="operator-paced")
    return exported


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
            if bound:
                require(len(entries) == heads[slot]["count"], "export journal head count integrity failure")
            for i, entry in enumerate(entries):
                mapping(entry, f"export.journal.{slot}[{i}]", ("kind", "payload", "sha256"))
                kind = entry["kind"]
                identity(kind, f"export.journal.{slot}[{i}].kind")
                mapping(entry["payload"], f"export.journal.{slot}[{i}].payload")
                expected = sha(encode([slot, i, kind, previous]) + encode(entry["payload"]))
                require(entry["sha256"] == expected, "export journal integrity failure")
                require((i == 0 and kind == "start") or
                        (state == "running" and kind in ({"event", "request", "finish", "abort"} |
                         ({"exposure"} if self.plan["schema"] == "etps-live-plan-v1" else set()))),
                        "invalid export lifecycle")
                state = {"start": "running", "finish": "finished", "abort": "aborted"}.get(kind, state)
                previous = expected
            if bound:
                require(previous == heads[slot]["hash"], "export journal head hash integrity failure")
                require(state == heads[slot]["state"], "export journal head state integrity failure")
            return entries

        def manifest(self, slot):
            return decode(self.artifacts[self.plan["tasks"][self.slots[slot]["task"]]], admission=False)

    require(bundle["format"] in ("etps-offline-export-v1", "etps-offline-export-v2"),
            "unsupported export format")
    bound = bundle["format"] == "etps-offline-export-v2"
    view = ExportView()
    view.plan_raw = raw_response(bundle["plan_base64"], "export.plan_base64", admission=False)
    view.plan_hash = sha(view.plan_raw)
    require(view.plan_hash == bundle["plan_sha256"], "export plan hash mismatch")
    view.artifacts = {k: raw_response(v, "export.artifacts." + k, admission=False)
                      for k, v in bundle["artifacts"].items()}
    view.plan = validate_bundle(view.plan_raw, view.artifacts, allow_legacy=True,
                                authoring=validate_authoring, allow_remote=True)  # Read-only replay, never dispatch.
    view.slots = {s["id"]: s for s in view.plan["slots"]}
    require(set(bundle["journal"]) == set(view.slots), "export omitted planned slots")
    if bound:
        envelope = mapping(bundle.get("envelope"), "export.envelope",
                           ("slot_order", "heads", "envelope_sha256"))
        require(set(envelope) == {"slot_order", "heads", "envelope_sha256"},
                "export envelope fields integrity failure")
        slot_order = envelope["slot_order"]
        require(isinstance(slot_order, list) and slot_order == list(view.slots),
                "export slot order integrity failure")
        heads = mapping(envelope["heads"], "export.envelope.heads")
        require(set(heads) == set(slot_order), "export head slot integrity failure")
        for slot, head in heads.items():
            mapping(head, "export.envelope.heads." + slot, ("count", "hash", "state"))
            require(set(head) == {"count", "hash", "state"} and
                    type(head["count"]) is int and head["count"] >= 0 and
                    isinstance(head["hash"], str) and len(head["hash"]) == 64 and
                    all(c in "0123456789abcdef" for c in head["hash"]) and
                    head["state"] in ("unattempted", "running", "finished", "aborted"),
                    "export head shape integrity failure")
        require(envelope["envelope_sha256"] == sha(encode([view.plan_hash, slot_order, heads])),
                "export envelope hash integrity failure")
    result = report(view)
    result["authoring_gate_reasserted"] = validate_authoring
    result["export_completeness_bound"] = bound
    return result
