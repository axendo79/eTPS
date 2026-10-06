"""Opt-in human-coded development evidence. No networking or publishable scores."""
import base64
from datetime import datetime
from pathlib import Path
import sqlite3
import sys
import time

from . import scorer
from .scorer import InvalidRecord, identity, mapping, require
from .set_answers import projection_fields
from .workload import INVALIDATION_POLICY, encode, raw_response, sha

EVIDENCE = "dev-manual-human-coded"


def validate_manual(plan, artifacts):
    require(plan["purpose"] == "dev-manual" and plan["invalidation_policy"] == INVALIDATION_POLICY,
            "manual plan requires dev-manual purpose and complete invalidation policy")
    arms = mapping(plan["arms"], "arms")
    require(bool(arms), "missing manual arms")
    rubrics = set()
    for name, arm in arms.items():
        identity(name, "arm")
        mapping(arm, "manual arm")
        require(set(arm) == {"provider", "service", "coder", "coding_rubric_sha256"}
                and arm["provider"] == "manual", "invalid manual arm fields")
        identity(arm["service"], "service")
        identity(arm["coder"], "coder")
        key = identity(arm["coding_rubric_sha256"], "coding_rubric_sha256")
        require(key in artifacts and isinstance(artifacts[key], bytes) and sha(artifacts[key]) == key,
                "missing or corrupt coding rubric")
        try:
            require(bool(artifacts[key].decode("utf-8").strip()), "empty coding rubric")
        except UnicodeError:
            raise InvalidRecord("coding rubric must be UTF-8") from None
        rubrics.add(key)
    return rubrics


def timestamp():
    return datetime.now().astimezone().isoformat()


def check_timestamp(value):
    try:
        require(datetime.fromisoformat(value).utcoffset() is not None, "manual timestamp requires zone")
    except (TypeError, ValueError):
        raise InvalidRecord("invalid manual timestamp") from None


def line(stream):
    value = stream.readline(scorer.limits.MAX_RESPONSE_BYTES + 1)
    scorer.limits.check(len(value), "MAX_RESPONSE_BYTES")
    require(value != b"", "manual input ended before confirmation")
    require(isinstance(value, bytes), "manual input requires a binary stream")
    return value


def run_manual(store, slot, *, allow_manual=False, stdin=None, stdout=None,
               sentinel="<<<END_ETPS_REPLY>>>"):
    from .runner import answer_from_raw, implementation
    require(allow_manual, "manual plan requires --allow-manual")
    require(store.plan["schema"] == "etps-manual-plan-v1", "not a manual plan")
    require(isinstance(sentinel, str) and sentinel and "\n" not in sentinel and "\r" not in sentinel,
            "invalid reply sentinel")
    try:
        end = sentinel.encode("utf-8")
    except UnicodeError:
        raise InvalidRecord("invalid reply sentinel") from None
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout
    manifest = store.manifest(slot)
    scorer.validate(manifest)
    arm = store.plan["arms"][store.slots[slot]["arm"]]
    validate_manual(store.plan, store.artifacts)
    began = time.monotonic()
    store.append(slot, "start", {"evidence": EVIDENCE, "coder": arm["coder"],
                                "timestamp": timestamp(), **implementation()})
    current, count = manifest["start"], 0
    try:
        folder = store.path.parent / (store.path.stem + "-messages") / sha(slot.encode())
        folder.mkdir(parents=True, exist_ok=True)
        while manifest["nodes"][current]["kind"] != "terminal":
            node = manifest["nodes"][current]
            if node["kind"] == "user":
                path = folder / (str(count) + ".txt")
                with path.open("xb") as output:
                    output.write(node["text"].encode("utf-8"))
                stdout.write("\nUSER MESSAGE (exact UTF-8 copy in " + str(path) + "):\n")
                stdout.write(node["text"])
                stdout.write("\n[END USER MESSAGE]\n")
                stdout.flush()
                store.append(slot, "event", {"kind": "user", "node": current, "text": node["text"],
                                            "timestamp": timestamp(), "coder": arm["coder"]})
                current = node["next"]
                count += 1
                continue
            store.append(slot, "request", {"node": current, "coder": arm["coder"], "timestamp": timestamp()})
            stdout.write("Paste full raw reply; terminate with a line containing " + sentinel + ":\n")
            stdout.flush()
            chunks, size = [], 0
            while True:
                value = line(stdin)
                if value.rstrip(b"\r\n") == end:
                    break
                size += len(value)
                scorer.limits.check(size, "MAX_RESPONSE_BYTES")
                chunks.append(value)
            raw = b"".join(chunks)
            stdout.write("Coded answer JSON on one line, or timeout:\n")
            stdout.flush()
            coded = line(stdin)
            scorer.limits.check(len(coded), "MAX_RESPONSE_BYTES")
            timeout = coded.strip() == b"timeout"
            event = {"kind": "probe", "node": current, "status": "timeout" if timeout else "ok",
                     "raw_base64": base64.b64encode(raw).decode("ascii"),
                     "coded_raw_base64": base64.b64encode(coded).decode("ascii"),
                     "answer": None if timeout else answer_from_raw(coded, manifest.get("answer_schema"),
                         set_fields=projection_fields(manifest, node)),
                     "coder": arm["coder"]}
            outcome = scorer.classify_probe(manifest, node, event)
            target, _ = scorer.route(manifest, node, event, outcome)
            stdout.write("Class: " + outcome + "; next: " + target + ". Confirm with yes:\n")
            stdout.flush()
            if line(stdin).strip().lower() != b"yes":
                store.abort(slot, "operator_abort", "manual coding not confirmed")
                from .runner import replay_slot
                return replay_slot(store, slot)
            event.update(timestamp=timestamp(), confirmed=True, outcome=outcome, next=target)
            store.append(slot, "event", event)
            current = target
        store.append(slot, "finish", {"terminal": current, "operator_wall_seconds": time.monotonic() - began,
                                     "timestamp": timestamp(), "reason_code": None if manifest["nodes"][current]["accepted"]
                                     else "system_terminal_failure"})
    except BaseException as exc:
        code = ("interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else
                "storage_error" if isinstance(exc, (OSError, sqlite3.Error)) else "execution_error")
        try:
            store.abort(slot, code, "manual harness failed; durable prefix retained")
        except Exception:
            pass
        raise
    return replay_manual_slot(store, slot)


def replay_manual_slot(store, slot):
    from .runner import answer_from_raw, implementation
    rows = store.entries(slot)
    manifest = store.manifest(slot)
    findings = scorer.validate(manifest, authoring=False)
    common = {"slot": slot, "arm": store.slots[slot]["arm"], "task": store.slots[slot]["task"],
              "evidence": EVIDENCE, "publish_excluded": True, "coding_correctness_verified": False,
              "wall_time_kind": "operator-paced"}
    warnings = ["human_coding: coding correctness cannot be verified"]
    warnings += ["authoring_findings: " + code for code in sorted({f["code"] for f in findings})]
    if not rows:
        return {**common, "state": "unattempted", "score": None, "evidence_verified": None,
                "reason": "unattempted", "warnings": warnings}
    arm = store.plan["arms"][store.slots[slot]["arm"]]
    start = rows[0]["payload"]
    require(start.get("evidence") == EVIDENCE and start.get("coder") == arm["coder"], "manual start mismatch")
    check_timestamp(start.get("timestamp"))
    changed = [k for k, v in implementation().items() if k in start and encode(start[k]) != encode(v)]
    if changed:
        warnings.append("implementation_mismatch: " + ", ".join(sorted(changed)))
    events, pending, current = [], None, manifest["start"]
    for row in rows[1:]:
        p = row["payload"]
        if row["kind"] in {"request", "event"}:
            require(p.get("coder") == arm["coder"], "manual coder mismatch")
            check_timestamp(p.get("timestamp"))
        if row["kind"] == "request":
            require(pending is None and p.get("node") == current and manifest["nodes"][current]["kind"] == "probe",
                    "manual request order mismatch")
            pending = current
        elif row["kind"] == "event":
            require(p.get("node") == current, "manual node order mismatch")
            node = manifest["nodes"][current]
            if p.get("kind") == "user":
                require(pending is None and node["kind"] == "user", "manual user order mismatch")
                current = node["next"]  # scorer preserves unknown-payload protocol deviations.
            else:
                require(p.get("kind") == "probe" and pending == current and p.get("confirmed") is True,
                        "manual probe lacks confirmation/intent")
                mapping(p, "journal.event.probe", ("raw_base64", "coded_raw_base64", "status", "answer"))
                raw_response(p["raw_base64"], admission=False)
                coded = raw_response(p["coded_raw_base64"], admission=False)
                timeout = coded.strip() == b"timeout"
                require(p["status"] == ("timeout" if timeout else "ok"), "manual status mismatch")
                answer = None if timeout else answer_from_raw(coded, manifest.get("answer_schema"),
                    set_fields=projection_fields(manifest, node))
                require(encode(p["answer"]) == encode(answer), "manual coded answer projection mismatch")
                require(p.get("generation") is None, "manual generation telemetry prohibited")
                outcome = scorer.classify_probe(manifest, node, p)
                target, _ = scorer.route(manifest, node, p, outcome)
                require(p.get("outcome") == outcome and p.get("next") == target, "manual branch mismatch")
                current, pending = target, None
            events.append(p)
    state = {"finish": "finished", "abort": "aborted"}.get(rows[-1]["kind"], "running")
    finish = rows[-1]["payload"]
    wall = finish.get("operator_wall_seconds") if state == "finished" else None
    if state == "finished":
        require(scorer.finite(wall) and pending is None and manifest["nodes"][current]["kind"] == "terminal",
                "invalid manual finish")
        check_timestamp(finish.get("timestamp"))
        require(finish.get("terminal") == current, "manual finish terminal mismatch")
        require(finish.get("reason_code") == (None if manifest["nodes"][current]["accepted"] else "system_terminal_failure"),
                "manual finish reason mismatch")
    elif state == "aborted":
        require(store.plan["invalidation_policy"].get(finish.get("reason_code")) == "invalidate", "manual abort reason")
    record = {"manifest_sha256": scorer.digest(manifest), "purpose": "dev-manual", "events": events,
              "wall_seconds": None, "operator_wall_seconds": wall, "wall_time_kind": "operator-paced"}
    result = scorer.score(manifest, record)
    result.update(TPS=None, experimental_eTPS=None)
    if state != "finished":
        result.update(measurement_valid=False, reason="unfinished_slot", R=None, RR=None,
                      rr_unavailable_reason="unfinished_slot", accepted=None)
    verified = state != "finished" or result["measurement_valid"]
    if not verified:
        warnings += ["recomputed_measurement_invalid", "unverified_evidence: invalid_finished_trace"]
    return {**common, "state": state, "score": result, "record": record, "warnings": warnings,
            "operator_wall_seconds": wall, "reason_code": finish.get("reason_code"),
            "implementation_mismatch": bool(changed), "evidence_verified": verified}
