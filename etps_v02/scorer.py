"""Pure finite replay scorer. No network, tokenizer, model judge, or persistence.

Manifest authors own semantic truth. This module verifies declared transitions,
exact payloads, UTF-8 spans and recovery provenance, not corpus impartiality.
"""
from fractions import Fraction
import hashlib
import json
import math

UNIT = "utf8_bytes"
LEGACY_UNIT = "utf8-bytes-v1"
OUTCOMES = {"correct", "incorrect", "unknown", "malformed", "timeout"}
# Compatibility only for old records without an explicit per-probe declaration.
LEGACY_UNKNOWN_ANSWERS = ({"status": "unknown"}, {"status": "refusal"})


class InvalidRecord(ValueError):
    """Malformed manifest, trace, or telemetry: never convert to a good score."""


def digest(manifest):
    """Identity for this prototype's canonical JSON manifest representation."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, reason):
    if not condition:
        raise InvalidRecord(reason)


def integer(value):
    return type(value) is int and value >= 0


def finite(value, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def boundaries(text):
    require(isinstance(text, str), "payload must be text")
    try:
        raw = text.encode("utf-8")
    except UnicodeError as exc:
        raise InvalidRecord("invalid UTF-8 payload") from exc
    offsets = {0}
    position = 0
    for char in text:
        position += len(char.encode("utf-8"))
        offsets.add(position)
    return raw, offsets


def validate(manifest, *, authoring=True):
    require(manifest.get("unit") in {UNIT, LEGACY_UNIT}, "unsupported accounting unit")
    nodes = manifest["nodes"]
    obligations = manifest["obligations"]
    require(manifest["start"] in nodes, "missing start")
    for oid, obligation in obligations.items():
        if "begin_after" in obligation:
            require(set(obligation) == {"source", "begin_after", "end_before"}, "invalid event interval fields")
            # Pilot restriction, not the general contract: checkpoint-delayed
            # starts need a separately reviewed applicability/controller model.
            require(obligation["begin_after"] == obligation["source"], "pilot begin must follow establishment")
            require(obligation["end_before"] == "$trial_end" or obligation["end_before"] in nodes,
                    "unknown expiration event")
            require(obligation["end_before"] != obligation["source"], "expiration equals establishment")
        else:
            # Compatibility for old exports only; new offline plans reject positions.
            require(integer(obligation["begin"]) and integer(obligation["end"])
                    and obligation["begin"] < obligation["end"], "invalid obligation interval")
        require(obligation["source"] in nodes and
                nodes[obligation["source"]]["kind"] == "user", "invalid source")
    for node in nodes.values():
        kind = node["kind"]
        require(kind in {"user", "probe", "internal", "replay", "terminal"}, "unknown node kind")
        if kind == "terminal":
            require(type(node["accepted"]) is bool, "terminal acceptance must be Boolean")
            continue
        if kind == "probe":
            if authoring:
                require("unknown_answers" in node, "probe must declare unknown_answers (possibly empty)")
            require(set(node["next"]) == OUTCOMES, "incomplete outcome policy")
            require(isinstance(node["expected"], dict) and
                    all(isinstance(k, str) and isinstance(v, str)
                        for k, v in node["expected"].items()), "answers require string fields")
            if "unknown_answers" in node:
                answers = node["unknown_answers"]
                require(isinstance(answers, list) and all(isinstance(a, dict) and
                        all(isinstance(k, str) and isinstance(v, str) for k, v in a.items())
                        for a in answers), "unknown_answers must declare exact string-field objects")
                require(node["expected"] not in answers, "correct/unknown declarations overlap")
                require(len({digest(a) for a in answers}) == len(answers), "duplicate unknown answer")
            require(set(node.get("obligations", [])) <= obligations.keys(), "unknown probe obligation")
            targets = node["next"].values()
        else:
            targets = [node["next"]]
        require(all(target in nodes for target in targets), "missing transition")
        if kind == "user":
            raw, offsets = boundaries(node["text"])
            require(node["sha256"] == hashlib.sha256(raw).hexdigest(), "payload hash mismatch")
            require("spans" in node, "missing span annotation")
            for span in node["spans"]:
                a, b, oid = span
                require(integer(a) and integer(b) and a < b and a in offsets and b in offsets,
                        "span must use UTF-8 character boundaries")
                require(oid in obligations, "unknown span obligation")
            if node["spans"]:
                require(node.get("failure") in nodes and
                        nodes[node["failure"]]["kind"] == "probe", "missing recovery failure")
    # Finite unrolled branches bound retries. Reject cycles even in unused branches.
    done, visiting, descendants = set(), set(), {}
    def visit(key):
        require(key not in visiting, "cyclic policy; unroll bounded retries")
        if key in done:
            return
        visiting.add(key)
        descendants[key] = set()
        node = nodes[key]
        if node["kind"] != "terminal":
            targets = node["next"].values() if node["kind"] == "probe" else [node["next"]]
            for target in targets:
                visit(target)
                descendants[key].update({target} | descendants[target])
        visiting.remove(key)
        done.add(key)
    for key in nodes:
        visit(key)
    grants, findings = {}, []
    for key, node in nodes.items():
        if node["kind"] == "user":
            for oid in {span[2] for span in node["spans"]}:
                grants.setdefault((node["failure"], oid), []).append(key)
    for (failure, oid), users in grants.items():
        for i, left in enumerate(users):
            for right in users[i + 1:]:
                if right in descendants[left] or left in descendants[right]:
                    findings.append({"code": "duplicate_recovery_authorization", "failure": failure,
                                     "obligation": oid, "nodes": [left, right]})
    if authoring:
        require(not findings, "duplicate recovery authorization on a common path")
    return findings


def interval(obligation, seen, length=None, terminal=None):
    if "begin_after" not in obligation:
        return {"begin_index": obligation["begin"], "end_index": obligation["end"],
                "basis": "legacy_executed_indices"}
    source = seen.get(obligation["begin_after"])
    end_id = obligation["end_before"]
    end = seen.get(end_id)
    if terminal is not None and end_id in {"$trial_end", terminal}:
        end = length
    return {"begin_after": obligation["begin_after"], "end_before": end_id,
            "begin_index": None if source is None else source + 1, "end_index": end,
            "basis": "event_ids", "end_reached": end is not None}


def is_active(obligation, seen, index):
    resolved = interval(obligation, seen)
    begin, end = resolved["begin_index"], resolved["end_index"]
    return begin is not None and begin <= index and (end is None or index < end)


def classify(event, expected, unknown_answers=()):
    require(event.get("status") in {"ok", "timeout"}, "unknown transport status")
    if event["status"] == "timeout":
        return "timeout"
    answer = event.get("answer")
    if not isinstance(answer, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                               for k, v in answer.items()):
        return "malformed"
    if answer == expected:
        return "correct"
    if answer in unknown_answers:
        return "unknown"
    return "incorrect"


def score(manifest, record):
    """Return exact fractions and observations, or raise InvalidRecord.

    A well-shaped off-script trace returns measurement_valid=False and RR=None.
    Raw input remains visible; invalid records never receive an experimental index.
    Manifest acceptance terminals declare all task/action budget obligations; this
    prototype cannot independently verify real-world actions or backend clocks.
    """
    # Replay old evidence even if its authoring pattern is now rejected. Runtime
    # consumption still prevents duplicate credit; findings remain visible.
    findings = validate(manifest, authoring=False)
    require(record.get("manifest_sha256") == digest(manifest), "manifest identity mismatch")
    events = record["events"]
    require(isinstance(events, list), "events must be a list")
    raw_i = sum(len(boundaries(e["text"])[0]) for e in events if e.get("kind") == "user")
    wall = record.get("wall_seconds")
    require(wall is None or finite(wall), "invalid task wall time")
    current = manifest["start"]
    seen, failures, observed_failures, first, labels = {}, {}, {}, {}, []
    r = 0
    generation_tokens, generation_seconds = 0, Fraction(0)
    generation_available = True
    attempts = 0
    reason = None
    for index, event in enumerate(events):
        node = manifest["nodes"][current]
        if node["kind"] == "terminal" or event.get("node") != current or event.get("kind") != node["kind"]:
            reason = "off_script_event"
            break
        seen[current] = index
        kind = node["kind"]
        if kind == "user":
            if event["text"] != node["text"]:
                reason = "unmatched_user_payload"
                break
            covered, consumed, stale = set(), set(), set()
            for a, b, oid in node["spans"]:
                obligation = manifest["obligations"][oid]
                source = seen.get(obligation["source"])
                if source is None or source >= index:
                    reason = "unestablished_recovery"
                    break
                if not is_active(obligation, seen, index):
                    continue
                if oid not in failures.get(node["failure"], set()):
                    if oid in observed_failures.get(node["failure"], set()):
                        stale.add(oid)
                        continue
                    else:
                        reason = "unlinked_recovery"
                        break
                covered.update(range(a, b))
                consumed.add(oid)
            if reason:
                break
            r += len(covered)
            # Consume after the whole event, so multiple spans for one obligation
            # all count once as a union. Re-supply discharges older grants too.
            for standing in failures.values():
                standing.difference_update(consumed)
            labels.append({"node": current, "class": "recovery" if covered else "scheduled",
                           "I": len(event["text"].encode()), "R": len(covered),
                           "consumed_obligations": sorted(consumed), "stale_failure_obligations": sorted(stale)})
            current = node["next"]
        elif kind == "probe":
            attempts += 1
            outcome = classify(event, node["expected"], node.get("unknown_answers", LEGACY_UNKNOWN_ANSWERS))
            active = set()
            for oid in node.get("obligations", []):
                obligation = manifest["obligations"][oid]
                source = seen.get(obligation["source"])
                if (source is not None and source < index
                        and is_active(obligation, seen, index)):
                    active.add(oid)
                    first.setdefault(oid, outcome == "correct")
            if outcome != "correct":
                failures[current] = set(active)
                observed_failures[current] = set(active)
            else:
                for standing in failures.values():
                    standing.difference_update(node.get("obligations", []))
            labels.append({"node": current, "class": outcome})
            usage = event.get("generation")
            if usage is None:
                generation_available = False
            else:
                require(integer(usage["tokens"]) and finite(usage["seconds"], positive=True),
                        "invalid backend generation telemetry")
                generation_tokens += usage["tokens"]
                generation_seconds += Fraction(str(usage["seconds"]))
            current = node["next"][outcome]
        else:
            labels.append({"node": current, "class": "excluded_" + kind})
            current = node["next"]
    terminal = manifest["nodes"][current]
    if reason is None and terminal["kind"] != "terminal":
        reason = "truncated_trace"
    valid = reason is None
    accepted = terminal["accepted"] if valid else None
    rr = Fraction(r, raw_i) if valid and raw_i else None
    tps = (Fraction(generation_tokens) / generation_seconds
           if valid and generation_available and generation_seconds else None)
    offline = record.get("purpose") == "offline-verification"
    if offline:
        tps = None
    resolved = {oid: interval(o, seen, len(events), current if valid else None)
                for oid, o in manifest["obligations"].items()}
    return {"unit": manifest["unit"], "manifest_sha256": record["manifest_sha256"],
            "authoring_findings": findings,
            "legacy_unknown_probes": [key for key, node in manifest["nodes"].items()
                                      if node["kind"] == "probe" and "unknown_answers" not in node],
            "resolved_obligations": resolved,
            "throughput_unavailable_reason": "offline_verification" if offline else None,
            "measurement_valid": valid, "reason": reason,
            "I": raw_i, "R": r if valid else None, "RR": rr,
            "rr_unavailable_reason": reason or ("zero_input" if not raw_i else None),
            "accepted": accepted, "first_attempt": first,
            "retention": Fraction(sum(first.values()), len(first)) if first else None,
            "attempts": attempts, "TPS": tps,
            "experimental_eTPS": tps * (1 - rr) if accepted and rr is not None and tps is not None else None,
            "wall_seconds": wall, "classifications": labels}


def summarize(results, *, planned=None):
    """All-attempt cost per accepted completion; no survivor-only cost numerator."""
    planned = len(results) if planned is None else planned
    require(integer(planned) and planned >= len(results), "invalid planned count")
    require(len({r["manifest_sha256"] for r in results}) <= 1, "cannot pool different manifests")
    accepted = sum(r["accepted"] is True for r in results)
    complete = bool(results) and planned == len(results)
    valid = complete and all(r["measurement_valid"] for r in results)
    total_i = sum(r["I"] for r in results)
    pooled_available = valid and all(r["RR"] is not None for r in results) and total_i > 0
    reason = ("unattempted_slots" if planned > len(results) else
              "no_trials" if not results else "invalid_or_unfinished_trials" if not valid else None)
    return {"planned": planned, "attempted": len(results), "accepted": accepted,
            "invalid": sum(not r["measurement_valid"] for r in results),
            "acceptance_rate": Fraction(accepted, len(results)) if results else None,
            "input_bytes_per_accepted": Fraction(total_i, accepted)
                if accepted and valid else None,
            "input_cost_unavailable_reason": reason or ("zero_accepted" if not accepted else None),
            "wall_seconds_per_accepted": sum(Fraction(str(r["wall_seconds"])) for r in results) / accepted
                if accepted and valid and all(r["wall_seconds"] is not None for r in results) else None,
            "wall_cost_unavailable_reason": reason or ("zero_accepted" if not accepted else
                "wall_time_unavailable" if any(r["wall_seconds"] is None for r in results) else None),
            "pooled_RR": Fraction(sum(r["R"] for r in results), total_i) if pooled_available else None,
            "pooled_RR_definition": "sum(R)/sum(I), all planned trials including measured failures",
            "pooled_RR_unavailable_reason": reason or (None if pooled_available else "RR_unavailable")}
