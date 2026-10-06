"""Opt-in live controller/replay. Transport failures are measured outcomes."""
import base64
from datetime import datetime, timezone
import sqlite3
import time

from . import adapter_openai as adapter, scorer
from .live_plan import arm_endpoint, endpoint, validate_live
from .response_extraction import project_reply
from .scorer import classify, digest, finite, require, score, validate
from .workload import encode, raw_response, sha


def exposure(plan, slot):
    arm = plan["arms"][slot["arm"]]
    return {"endpoint_host": endpoint(arm_endpoint(plan, slot["arm"]))[1], "provider": arm["provider"],
            "model": arm["model"], "task_artifact_hashes": [plan["tasks"][slot["task"]]],
            "scope": "dispatch_intent; delivery may be uncertain"}


def _dispatch(store, slot, current, conversation, arm, base, manifest, elapsed, deadline, kind="probe"):
    require(conversation and conversation[-1]["role"] == "user",
            "live dispatch requires a public conversation ending with user")
    body = adapter.public_request(arm, conversation)
    intent = ({"node": current, "message_count": len(body["messages"]), "body_sha256": sha(encode(body)),
               "elapsed_seconds": elapsed, "deadline_seconds": deadline}
              if store.plan.get("request_journal") == "history-sha256-v1" else
              {"node": current, "body": body, "elapsed_seconds": elapsed, "deadline_seconds": deadline})
    if kind == "delivery":
        intent["kind"] = "delivery"
    store.append(slot, "request", intent)
    response = adapter.send(base, arm, body, deadline)
    if "memory_telemetry_field" in arm:
        from .memory_telemetry import project as project_memory
        response.update(project_memory(response, arm["memory_telemetry_field"]))
    if store.plan.get("timing_convention") == "decode-v1":
        from .timing import project
        response["timing"] = project(arm["provider"], response)
    raw = raw_response(response["raw_base64"])
    event = {"kind": kind, "node": current, **response}
    if kind == "probe":
        from .set_answers import projection_fields
        answer, extracted = project_reply(raw, manifest.get("answer_schema"), store.plan.get("response_extraction"),
            set_fields=projection_fields(manifest, manifest["nodes"][current]))
        event["answer"] = answer
        if "response_extraction" in store.plan:
            event["extracted"] = extracted
    store.append(slot, "event", event)
    if response["status"] == "ok":
        conversation.append({"role": "assistant", "content": raw.decode("utf-8")})
    return event


def run_live(store, slot, *, allow_live=False, allow_remote=False):
    from .runner import answer_from_raw, implementation
    require(allow_live, "live plan requires --allow-live")
    require(store.plan["schema"] == "etps-live-plan-v1", "not a live plan")
    validate_live(store.plan, allow_remote=allow_remote)
    base = arm_endpoint(store.plan, store.slots[slot]["arm"])
    remote = endpoint(base)[2]
    manifest = store.manifest(slot)
    validate(manifest)
    arm = store.plan["arms"][store.slots[slot]["arm"]]
    adapter.preflight(base, arm, store.plan["request_deadline_seconds"])
    began = time.monotonic()
    limit = store.plan["trial_wall_limit_seconds"]
    store.append(slot, "start", {"evidence": "live-exploratory", "controller_policy": "guard-v1",
                                **implementation()})
    current, conversation = manifest["start"], []
    dirty = False
    try:
        if remote:
            store.append(slot, "exposure", {**exposure(store.plan, store.slots[slot]),
                         "timestamp": datetime.now(timezone.utc).isoformat()})
        while manifest["nodes"][current]["kind"] != "terminal":
            if time.monotonic() - began >= limit:
                break
            node = manifest["nodes"][current]
            if node["kind"] == "session_boundary":
                if store.plan.get("boundary_delivery") == "deliver-v1" and dirty:
                    elapsed = time.monotonic() - began
                    if elapsed >= limit:
                        break
                    _dispatch(store, slot, current, conversation, arm, base, manifest, elapsed,
                              min(store.plan["request_deadline_seconds"], limit - elapsed), "delivery")
                    dirty = False
                store.append(slot, "event", {"kind": "session_boundary", "node": current})
                if arm.get("context_policy", "full") == "reset-v1":
                    conversation.clear()
                current = node["next"]
                continue
            if node["kind"] == "user":
                store.append(slot, "event", {"kind": "user", "node": current, "text": node["text"]})
                conversation.append({"role": "user", "content": node["text"]})
                dirty = True
                current = node["next"]
                continue
            elapsed = time.monotonic() - began
            if elapsed >= limit:
                break
            deadline = min(store.plan["request_deadline_seconds"], limit - elapsed)
            event = _dispatch(store, slot, current, conversation, arm, base, manifest, elapsed, deadline)
            dirty = False
            outcome = scorer.classify_probe(manifest, node, event)
            current, _ = scorer.route(manifest, node, event, outcome)
        wall = time.monotonic() - began
        stopped = wall >= limit
        store.append(slot, "finish", {"terminal": "$trial_wall_limit" if stopped else current,
                     "wall_seconds": wall, "reason_code": "trial_wall_limit" if stopped else
                     None if manifest["nodes"][current]["accepted"] else "system_terminal_failure"})
    except Exception as exc:
        # No exception text: network libraries or user data could contain secrets.
        code = "storage_error" if isinstance(exc, (OSError, sqlite3.Error)) else "execution_error"
        try:
            store.abort(slot, code, "live controller failed; durable prefix retained")
        except Exception:
            pass
        raise
    # Process crash/KeyboardInterrupt leaves a visible running prefix, never reissues.
    return replay_live_slot(store, slot)


def replay_live_slot(store, slot, allow_running=False):
    from .runner import answer_from_raw, implementation
    rows = store.entries(slot)
    manifest = store.manifest(slot)
    findings = validate(manifest, authoring=False)
    warnings = ["authoring_findings: " + code for code in sorted({f["code"] for f in findings})]
    if not rows:
        return {"slot": slot, "state": "unattempted", "score": None, "reason": "unattempted",
                "warnings": warnings, "authoring_findings": findings, "evidence_verified": None}
    arm = store.plan["arms"][store.slots[slot]["arm"]]
    validate_live(store.plan, execution=False)
    remote = endpoint(arm_endpoint(store.plan, store.slots[slot]["arm"]))[2]
    now = implementation()
    recorded = {k: rows[0]["payload"][k] for k in now if k in rows[0]["payload"]}
    changed = sorted(k for k in now if k in recorded and recorded[k] != now[k])
    if recorded.keys() != now.keys():
        warnings.append("legacy_implementation_identity: partial")
    if changed:
        warnings.append("implementation_mismatch: " + ", ".join(changed) + "; values recomputed with current code")
    state = {"finish": "finished", "abort": "aborted"}.get(rows[-1]["kind"], "running")
    events, conversation, exposures, issues = [], [], [], []
    pending, elapsed_end = None, 0
    guarded = rows[0]["payload"].get("controller_policy") == "guard-v1"
    delivery_path = None
    if store.plan.get("boundary_delivery") == "deliver-v1":
        from .boundary_delivery import Path
        delivery_path = Path(manifest)
    for row in rows[1:]:
        kind, p = row["kind"], row["payload"]
        if kind == "exposure":
            require(remote and not exposures and pending is None and not events, "invalid exposure ordering")
            require(set(p) == set(exposure(store.plan, store.slots[slot])) | {"timestamp"}, "invalid exposure fields")
            require(all(p[k] == v for k, v in exposure(store.plan, store.slots[slot]).items()), "exposure mismatch")
            try:
                require(datetime.fromisoformat(p["timestamp"]).utcoffset() is not None, "exposure timestamp lacks zone")
            except (ValueError, TypeError):
                require(False, "invalid exposure timestamp")
            exposures.append(p)
        elif kind == "request":
            hashed = store.plan.get("request_journal") == "history-sha256-v1"
            scorer.mapping(p, "journal.request", ("node", "elapsed_seconds", "deadline_seconds") +
                           (("message_count", "body_sha256") if hashed else ("body",)))
            if delivery_path is not None:
                delivery_path.request(p)
            else:
                require(p.get("kind", "probe") == "probe", "delivery requires deliver-v1")
            if guarded:
                require(conversation and conversation[-1]["role"] == "user",
                        "live request violates public conversation guard")
            require(pending is None and (not remote or len(exposures) == 1), "missing intent/exposure boundary")
            expected_body = adapter.public_request(arm, conversation)
            require(p["message_count"] == len(expected_body["messages"]) and p["body_sha256"] == sha(encode(expected_body))
                    if hashed else encode(p["body"]) == encode(expected_body), "request public history/settings mismatch")
            elapsed, deadline = p["elapsed_seconds"], p["deadline_seconds"]
            require(finite(elapsed) and elapsed >= elapsed_end and finite(deadline, positive=True), "invalid dispatch timing")
            require(deadline == min(store.plan["request_deadline_seconds"],
                                    store.plan["trial_wall_limit_seconds"] - elapsed), "request deadline mismatch")
            pending = p
        elif kind == "event":
            scorer.mapping(p, "journal.event", ("kind",))
            if p["kind"] == "session_boundary":
                require(pending is None and set(p) == {"node", "kind"}, "invalid session boundary event")
                if arm.get("context_policy", "full") == "reset-v1":
                    conversation.clear()
            elif p["kind"] == "user":
                scorer.mapping(p, "journal.event.user", ("node", "text"))
                require(pending is None, "user before pending response")
                conversation.append({"role": "user", "content": p["text"]})
            else:
                scorer.mapping(p, "journal.event.response", ("node", "raw_base64", "client_latency_seconds", "http_body_base64"))
                require(p["kind"] in {"probe", "delivery"} and pending is not None
                        and p["node"] == pending["node"] and p["kind"] == pending.get("kind", "probe"), "response lacks matching intent")
                raw = raw_response(p["raw_base64"], admission=False)
                if p["kind"] == "probe":
                    scorer.mapping(p, "journal.event.probe", ("answer",))
                    from .set_answers import projection_fields
                    answer, extracted = project_reply(raw, manifest.get("answer_schema"), store.plan.get("response_extraction"),
                        set_fields=projection_fields(manifest, manifest["nodes"].get(p["node"], {})))
                    require(encode(p["answer"]) == encode(answer), "raw answer projection mismatch")
                    if "response_extraction" in store.plan:
                        require(type(p.get("extracted")) is bool and p["extracted"] is extracted,
                                "response extraction flag mismatch")
                require(finite(p["client_latency_seconds"]), "invalid response latency")
                elapsed_end = pending["elapsed_seconds"] + p["client_latency_seconds"]
                if p["http_body_base64"] is not None:
                    scorer.mapping(p, "journal.event.response", ("http_body_sha256", "http_status", "status", "usage",
                                   "generation", "generation_source", "backend_stats", "transport_detail"))
                    body = raw_response(p["http_body_base64"], admission=False)
                    require(sha(body) == p["http_body_sha256"], "HTTP body hash mismatch")
                    expected = adapter.envelope(arm["provider"], p["http_status"], body)
                    require(all(encode(p[k]) == encode(v) for k, v in expected.items()), "HTTP envelope projection mismatch")
                else:
                    scorer.mapping(p, "journal.event.response", ("status", "usage", "generation", "generation_source",
                                   "backend_stats", "transport_detail"))
                    legacy_credential = not guarded and p["transport_detail"] == "credential_unavailable"
                    if legacy_credential:
                        warnings.append("legacy_credential_outcome: harness fault recorded as timeout")
                    require(p["status"] == "timeout" and raw == b"" and p["usage"] is None
                            and p["generation"] is None and p["generation_source"] is None
                            and p["backend_stats"] == {} and (legacy_credential or p["transport_detail"] in {
                                "deadline_exceeded", "connection_refused", "transport_error",
                                "credential_echo", "response_size_limit"}), "invalid transport failure evidence")
                if p["status"] == "ok":
                    conversation.append({"role": "assistant", "content": raw.decode("utf-8")})
                if "memory_telemetry_field" in arm:
                    from .memory_telemetry import project as project_memory
                    expected_memory = project_memory(p, arm["memory_telemetry_field"])
                    require(all(k in p and encode(p[k]) == encode(v) for k, v in expected_memory.items()),
                            "memory telemetry projection mismatch")
                if store.plan.get("timing_convention") == "decode-v1":
                    from .timing import project
                    require(encode(p.get("timing")) == encode(project(arm["provider"], p)),
                            "decode timing projection mismatch")
                pending = None
            if delivery_path is not None:
                delivery_path.event(p)
            events.append(p)
    if remote and len(exposures) != 1:
        issues.append({"code": "missing_exposure_record"})
    finish = rows[-1]["payload"] if state == "finished" else {}
    wall = finish.get("wall_seconds")
    if state == "finished":
        require(finite(wall) and wall >= elapsed_end, "invalid trial wall time")
    stopped = state == "finished" and finish.get("reason_code") == "trial_wall_limit"
    record = {"manifest_sha256": digest(manifest), "purpose": "live-exploratory", "events": events,
              "wall_seconds": wall, "trial_wall_limit_seconds": store.plan["trial_wall_limit_seconds"],
              "stop_reason": "trial_wall_limit" if stopped else None}
    if "timing_convention" in store.plan:
        record["timing_convention"] = store.plan["timing_convention"]
    if delivery_path is not None:
        record["boundary_delivery"] = "deliver-v1"
    result = score(manifest, record)
    if state == "finished":
        if pending is not None or not result["measurement_valid"]:
            issues.append({"code": "invalid_finished_trace"})
        expected_reason = "trial_wall_limit" if stopped else None if result["accepted"] else "system_terminal_failure"
        if finish.get("terminal") != result["terminal"] or finish.get("reason_code") != expected_reason:
            issues.append({"code": "finish_mismatch"})
        if wall >= store.plan["trial_wall_limit_seconds"] and not stopped:
            issues.append({"code": "wall_limit_not_enforced"})
    elif state == "aborted" and store.plan["invalidation_policy"].get(rows[-1]["payload"].get("reason_code")) != "invalidate":
        issues.append({"code": "abort_reason_invalid"})
    recomputed = dict(result)
    if state != "finished" or issues:
        reason = "unverified_evidence" if issues else "unfinished_slot"
        result.update(measurement_valid=False, reason=reason, R=None, RR=None, rr_unavailable_reason=reason,
                      accepted=None, TPS=None, experimental_eTPS=None)
        if "result_state" in result:
            result["result_state"] = "failed"
    if issues:
        warnings.extend("unverified_evidence: " + i["code"] for i in issues)
    return {"slot": slot, "arm": store.slots[slot]["arm"], "task": store.slots[slot]["task"],
            "state": state, "evidence": "live-exploratory", "record": record, "exposure": exposures,
            "reason": rows[-1]["payload"].get("reason"), "reason_code": rows[-1]["payload"].get("reason_code"),
            "warnings": warnings, "implementation_mismatch": bool(changed), "evidence_verified": not issues,
            "evidence_issues": issues, "recomputed_score": recomputed if issues else None,
            "implementation": {"recorded": recorded, "current": now, "changed": changed},
            "score": result}
