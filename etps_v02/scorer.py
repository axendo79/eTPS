"""Pure finite replay scorer. No network, tokenizer, model judge, or persistence.

Manifest authors own semantic truth. This module verifies declared transitions,
exact payloads, UTF-8 spans and recovery provenance, not corpus impartiality.
"""
from fractions import Fraction
import hashlib
import json
import math

from . import limits

UNIT = "utf8_bytes"
LEGACY_UNIT = "utf8-bytes-v1"
OUTCOMES = {"correct", "incorrect", "unknown", "malformed", "timeout"}
# Compatibility only for old records without an explicit per-probe declaration.
LEGACY_UNKNOWN_ANSWERS = ({"status": "unknown"}, {"status": "refusal"})


class InvalidRecord(ValueError):
    """Malformed manifest, trace, or telemetry: never convert to a good score."""


def digest(manifest):
    """Identity for this prototype's canonical JSON manifest representation."""
    try:
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise InvalidRecord("manifest: invalid JSON value") from exc
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise InvalidRecord(reason)


def mapping(value, path, required=()):
    require(isinstance(value, dict), f"{path}: expected object")
    require(all(isinstance(k, str) for k in value), f"{path}: keys must be strings")
    missing = set(required) - value.keys()
    require(not missing, f"{path}: missing fields {', '.join(sorted(missing))}")
    return value


def identity(value, path):
    require(isinstance(value, str) and bool(value), f"{path}: expected nonempty string")
    return value


def telemetry(value, path):
    mapping(value, path, ("tokens", "seconds"))
    require(set(value) == {"tokens", "seconds"} and integer(value["tokens"])
            and finite(value["seconds"], positive=True), f"{path}: invalid generation telemetry")


def integer(value):
    return type(value) is int and value >= 0


def finite(value, positive=False):
    # Python integers are finite without a conversion to bounded C doubles.
    return (type(value) in (int, float) and (type(value) is int or math.isfinite(value))
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


def declared_fields(value, allowed, path, authoring, findings):
    unknown = sorted(value.keys() - allowed - {"metadata"})
    if unknown:
        require(not authoring, f"{path}: unrecognized fields {', '.join(unknown)}")
        findings.append({"code": "legacy_unrecognized_fields", "path": path, "fields": unknown})
    if "metadata" in value and not isinstance(value["metadata"], dict):
        require(not authoring, path + ".metadata: expected object")
        findings.append({"code": "legacy_metadata_shape", "path": path + ".metadata"})


def validate(manifest, *, authoring=True):
    mapping(manifest, "manifest", ("unit", "nodes", "obligations", "start"))
    findings = []
    if authoring:
        limits.check_value_depth(manifest)
    declared_fields(manifest, {"unit", "nodes", "obligations", "start", "answer_schema", "routing", "answer_tolerance", "answer_predicate"},
                    "manifest", authoring, findings)
    if "answer_predicate" in manifest:
        require(manifest["answer_predicate"] == "set-v1", "unsupported answer_predicate")
        require(manifest.get("answer_schema") == "typed-v1", "set-v1 requires typed-v1")
    set_answers = manifest.get("answer_predicate") == "set-v1"
    if "answer_tolerance" in manifest:
        require(manifest["answer_tolerance"] == "d10-v1", "unsupported answer_tolerance")
    if "routing" in manifest:
        require(manifest["routing"] == "field-v1", "unsupported routing")
    field_routing = manifest.get("routing") == "field-v1"
    if "answer_schema" in manifest:
        require(manifest["answer_schema"] == "typed-v1", "unsupported answer_schema")
    answer_schema = manifest.get("answer_schema")
    require(isinstance(manifest["unit"], str) and manifest["unit"] in {UNIT, LEGACY_UNIT},
            "manifest.unit: unsupported accounting unit")
    nodes = mapping(manifest["nodes"], "manifest.nodes")
    if authoring:
        limits.check(len(nodes), "MAX_MANIFEST_NODES")
    elif len(nodes) > limits.MAX_MANIFEST_NODES:
        findings.append({"code": "legacy_safety_limit", "limit": "MAX_MANIFEST_NODES"})
    obligations = mapping(manifest["obligations"], "manifest.obligations")
    identity(manifest["start"], "manifest.start")
    require(manifest["start"] in nodes, "missing start")
    for key, node in nodes.items():
        identity(key, "manifest.nodes key")
        mapping(node, f"manifest.nodes.{key}", ("kind",))
        require(isinstance(node["kind"], str) and
                node["kind"] in {"user", "probe", "internal", "replay", "session_boundary", "terminal"},
                f"manifest.nodes.{key}.kind: unknown node kind")
    for oid, obligation in obligations.items():
        identity(oid, "manifest.obligations key")
        path = f"manifest.obligations.{oid}"
        mapping(obligation, path, ("source",))
        identity(obligation["source"], path + ".source")
        if "begin_after" in obligation:
            require(set(obligation) == {"source", "begin_after", "end_before"}, "invalid event interval fields")
            identity(obligation["begin_after"], path + ".begin_after")
            identity(obligation["end_before"], path + ".end_before")
            # Pilot restriction, not the general contract: checkpoint-delayed
            # starts need a separately reviewed applicability/controller model.
            require(obligation["begin_after"] == obligation["source"], "pilot begin must follow establishment")
            require(obligation["end_before"] == "$trial_end" or obligation["end_before"] in nodes,
                    "unknown expiration event")
            require(obligation["end_before"] != obligation["source"], "expiration equals establishment")
        else:
            # Compatibility for old exports only; new offline plans reject positions.
            mapping(obligation, path, ("begin", "end"))
            require(integer(obligation["begin"]) and integer(obligation["end"])
                    and obligation["begin"] < obligation["end"], "invalid obligation interval")
        require(obligation["source"] in nodes and
                nodes[obligation["source"]]["kind"] == "user", "invalid source")
    for key, node in nodes.items():
        path = f"manifest.nodes.{key}"
        kind = node["kind"]
        allowed = {
            "user": {"kind", "text", "sha256", "spans", "failure", "next"},
            "probe": {"kind", "expected", "unknown_answers", "obligations", "next"},
            "terminal": {"kind", "accepted"},
            "internal": {"kind", "next"}, "replay": {"kind", "next"},
            "session_boundary": {"kind", "next"},
        }[kind]
        if field_routing and kind == "probe":
            allowed |= {"field_obligations", "field_routes"}
        if manifest.get("answer_tolerance") == "d10-v1" and kind == "probe":
            allowed |= {"key_aliases", "fixed_value_fields"}
        if set_answers and kind == "probe":
            allowed |= {"set_fields", "field_dimensions"}
        declared_fields(node, allowed, path, authoring, findings)
        if kind == "terminal":
            mapping(node, path, ("accepted",))
            require(type(node["accepted"]) is bool, "terminal acceptance must be Boolean")
            continue
        mapping(node, path, ("next",))
        if kind == "probe":
            mapping(node, path, ("expected",))
            if authoring:
                require("unknown_answers" in node, "probe must declare unknown_answers (possibly empty)")
            mapping(node["next"], path + ".next")
            require(set(node["next"]) == OUTCOMES, "incomplete outcome policy")
            if set_answers:
                from .set_answers import (answer_object as set_object, equal as set_equal,
                                          projection_fields, validate_probe as validate_sets)
                mapping(node["expected"], path + ".expected")
                if manifest.get("answer_tolerance") == "d10-v1":
                    from .answer_tolerance import validate_probe
                    validate_probe(node)
                validate_sets(manifest, node)
                from .dimension_accuracy import validate_probe as validate_dimensions
                validate_dimensions(node)
            else:
                require(answer_object(node["expected"], answer_schema),
                        "answers require typed-v1 fields" if answer_schema else "answers require string fields")
            if not set_answers and manifest.get("answer_tolerance") == "d10-v1":
                from .answer_tolerance import validate_probe
                validate_probe(node)
            if "unknown_answers" in node:
                answers = node["unknown_answers"]
                require(isinstance(answers, list) and all((set_object(a, projection_fields(manifest, node))
                        if set_answers else answer_object(a, answer_schema))
                        for a in answers), "unknown_answers must declare exact typed-v1 objects"
                        if answer_schema else "unknown_answers must declare exact string-field objects")
                require(not any((set_equal(node, node["expected"], a) if set_answers else
                                 answer_equal(node["expected"], a)) for a in answers),
                        "correct/unknown declarations overlap")
                require(len({digest(a) for a in answers}) == len(answers), "duplicate unknown answer")
            tested = node.get("obligations", [])
            require(isinstance(tested, list) and all(isinstance(o, str) for o in tested),
                    path + ".obligations: expected string list")
            require(set(tested) <= obligations.keys(), "unknown probe obligation")
            targets = list(node["next"].values())
            if field_routing and ("field_routes" in node or "field_obligations" in node):
                links = mapping(node.get("field_obligations"), path + ".field_obligations")
                require(links.keys() == node["expected"].keys(), "field_obligations must cover expected keys")
                for linked in links.values():
                    require(isinstance(linked, list) and all(isinstance(o, str) for o in linked)
                            and len(linked) == len(set(linked)) and set(linked) <= set(tested),
                            "field_obligations must reference tested obligations")
                if {o for linked in links.values() for o in linked} != set(tested):
                    require(not authoring, "field_obligations must cover all tested obligations")
                    findings.append({"code": "field_obligations_incomplete", "node": key})
                routes = node.get("field_routes")
                require(isinstance(routes, list), "field_routes must be a list")
                subsets = set()
                for route in routes:
                    mapping(route, path + ".field_routes entry", ("failed_fields", "next"))
                    require(set(route) == {"failed_fields", "next"}, "invalid field route fields")
                    fields = route["failed_fields"]
                    require(isinstance(fields, list) and bool(fields)
                            and all(isinstance(f, str) for f in fields)
                            and fields == sorted(set(fields)) and set(fields) <= links.keys(),
                            "failed_fields must be a sorted nonempty subset")
                    require(tuple(fields) not in subsets, "duplicate field route")
                    subsets.add(tuple(fields))
                    targets.append(route["next"])
                # Count plus unique, valid subsets proves coverage without
                # constructing an exponential powerset of expected keys.
                require(len(subsets) == (1 << len(links)) - 1, "incomplete field route coverage")
        else:
            targets = [node["next"]]
        require(all(isinstance(target, str) and target in nodes for target in targets),
                path + ".next: missing transition")
        if kind == "user":
            mapping(node, path, ("text", "sha256"))
            raw, offsets = boundaries(node["text"])
            require(node["sha256"] == hashlib.sha256(raw).hexdigest(), "payload hash mismatch")
            require("spans" in node, "missing span annotation")
            require(isinstance(node["spans"], list), path + ".spans: expected list")
            for span in node["spans"]:
                require(isinstance(span, list) and len(span) == 3,
                        path + ".spans: expected [begin, end, obligation]")
                a, b, oid = span
                require(integer(a) and integer(b) and a < b and a in offsets and b in offsets,
                        "span must use UTF-8 character boundaries")
                require(isinstance(oid, str) and oid in obligations, "unknown span obligation")
            if "failure" in node:
                identity(node["failure"], path + ".failure")
            if node["spans"]:
                require(node.get("failure") in nodes and
                        nodes[node["failure"]]["kind"] == "probe", "missing recovery failure")
    # Finite unrolled branches bound retries. Reject cycles even in unused branches.
    done, visiting = set(), set()
    edges = {key: (() if node["kind"] == "terminal" else
                   tuple(set(node["next"].values()) |
                         ({r["next"] for r in node.get("field_routes", [])} if field_routing else set()))
                   if node["kind"] == "probe" else (node["next"],))
             for key, node in nodes.items()}
    for key in nodes:
        stack = [(key, False)]
        while stack:
            current, expanded = stack.pop()
            if current in done:
                continue
            targets = edges[current]
            if expanded:
                visiting.remove(current)
                done.add(current)
            else:
                require(current not in visiting, "cyclic policy; unroll bounded retries")
                visiting.add(current)
                stack.append((current, True))
                stack.extend((target, False) for target in targets)
    # Compute only reachability that recovery checks actually need. Do not keep
    # an all-pairs descendant matrix (quadratic even for a recovery-free chain).
    def reachable(source, targets, *, blocked=None, include_source=False):
        found, seen = set(), set()
        pending = [source] if include_source else list(edges[source])
        while pending and found != targets:
            current = pending.pop()
            if current in seen or current == blocked:
                continue
            seen.add(current)
            if current in targets:
                found.add(current)
            pending.extend(edges[current])
        return found

    # A boundary opts into the session profile. Every path from it to a probe
    # must deliver a user message first, even when a full-history arm ignores it.
    # Walk the union once; stop at users so branching stays linear in the graph.
    pending = [key for key, node in nodes.items() if node["kind"] == "session_boundary"]
    checked = set()
    while pending:
        key = pending.pop()
        if key in checked:
            continue
        checked.add(key)
        kind = nodes[key]["kind"]
        if kind == "probe":
            require(not authoring, f"manifest.nodes.{key}: probe after session_boundary requires a user message after the boundary")
            findings.append({"code": "session_boundary_missing_user", "node": key})
        elif kind != "user":
            pending.extend(edges[key])

    grants = {}
    recovery_targets = {}
    for key, node in nodes.items():
        if node["kind"] == "user" and node["spans"]:
            recovery_targets.setdefault(node["failure"], set()).add(key)
    reachable_recoveries = {failure: reachable(failure, targets)
                            for failure, targets in recovery_targets.items()}
    for key, node in nodes.items():
        if node["kind"] == "user":
            for oid in {span[2] for span in node["spans"]}:
                failure = node["failure"]
                if key not in reachable_recoveries[failure]:
                    require(not authoring, f"manifest.nodes.{key}.failure: probe is not a path-ancestor")
                    findings.append({"code": "recovery_failure_not_ancestor", "node": key,
                                     "failure": failure, "obligation": oid})
                if oid not in nodes[failure].get("obligations", []):
                    require(not authoring, f"manifest.nodes.{key}.spans: failure probe does not test {oid}")
                    findings.append({"code": "recovery_obligation_not_tested", "node": key,
                                     "failure": failure, "obligation": oid})
                grants.setdefault((failure, oid), []).append(key)
    # Diagnostic only: removing the failure probe reveals any route from start
    # that bypasses it. Runtime still requires an observed eligible failure.
    for failure, targets in recovery_targets.items():
        for key in sorted(reachable(manifest["start"], targets, blocked=failure, include_source=True)):
            findings.append({"code": "recovery_failure_not_dominating", "node": key, "failure": failure})
    for (failure, oid), users in grants.items():
        linked = {left: reachable(left, set(users) - {left}) for left in users}
        for i, left in enumerate(users):
            for right in users[i + 1:]:
                if right in linked[left] or left in linked[right]:
                    findings.append({"code": "duplicate_recovery_authorization", "failure": failure,
                                     "obligation": oid, "nodes": [left, right]})
    if authoring:
        require(not any(f["code"] == "duplicate_recovery_authorization" for f in findings),
                "duplicate recovery authorization on a common path")
    digest(manifest)  # Reject unserializable/nonfinite/invalid-Unicode declarations.
    return findings


def union_length(spans):
    """Count a union of half-open byte intervals without expanding positions."""
    total, end = 0, 0
    for a, b in sorted(spans):
        total += max(0, b - max(a, end))
        end = max(end, b)
    return total


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


def answer_object(answer, answer_schema=None):
    """Typed values exclude bool explicitly; bool is a Python int subclass."""
    return isinstance(answer, dict) and all(
        isinstance(k, str) and (type(v) in (str, int, type(None))
                               if answer_schema == "typed-v1" else isinstance(v, str))
        for k, v in answer.items())


def answer_equal(left, right):
    """Flat equality without Python's bool/int or int/float coercions."""
    return (isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys()
            and all(type(left[k]) is type(right[k]) and left[k] == right[k] for k in left))


def classify(event, expected, unknown_answers=(), answer_schema=None):
    mapping(event, "event", ("status",))
    require(isinstance(event["status"], str) and event["status"] in {"ok", "timeout"},
            "event.status: unknown transport status")
    if event["status"] == "timeout":
        return "timeout"
    answer = event.get("answer")
    if not answer_object(answer, answer_schema):
        return "malformed"
    if answer_equal(answer, expected):
        return "correct"
    if any(answer_equal(answer, unknown) for unknown in unknown_answers):
        return "unknown"
    return "incorrect"


def classify_probe(manifest, node, event):
    if manifest.get("answer_predicate") == "set-v1":
        from .set_answers import evaluate
        return evaluate(manifest, node, event)[0]
    if manifest.get("answer_tolerance") == "d10-v1":
        from .answer_tolerance import evaluate
        return evaluate(manifest, node, event)[0]
    return classify(event, node["expected"], node.get("unknown_answers", LEGACY_UNKNOWN_ANSWERS),
                    manifest.get("answer_schema"))


def route(manifest, node, event, outcome):
    """Return successor and optional exact-key failed fields; no reclassification."""
    answer, expected = event.get("answer"), node["expected"]
    if manifest.get("answer_tolerance") == "d10-v1" and outcome == "incorrect":
        from .answer_tolerance import normalize
        normalized = normalize(node, answer)
        if normalized is None:
            return node["next"][outcome], None
        answer, expected, _ = normalized
    if (manifest.get("routing") == "field-v1" and "field_routes" in node
            and outcome == "incorrect" and answer.keys() == expected.keys()):
        if manifest.get("answer_predicate") == "set-v1":
            from .set_answers import field_equal
            fields = sorted(k for k in expected if not field_equal(node, k, answer[k], expected[k]))
        else:
            fields = sorted(k for k in expected
                            if not answer_equal({k: answer[k]}, {k: expected[k]}))
        for entry in node["field_routes"]:
            if entry["failed_fields"] == fields:
                return entry["next"], fields
        raise InvalidRecord("missing field route")
    return node["next"][outcome], None


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
    mapping(record, "record", ("manifest_sha256", "events"))
    require(record.get("manifest_sha256") == digest(manifest), "manifest identity mismatch")
    events = record["events"]
    require(isinstance(events, list), "events must be a list")
    for index, event in enumerate(events):
        path = f"record.events[{index}]"
        mapping(event, path, ("node", "kind"))
        identity(event["node"], path + ".node")
        identity(event["kind"], path + ".kind")
        if event["kind"] == "user":
            mapping(event, path, ("text",))
        if event.get("generation") is not None:
            telemetry(event["generation"], path + ".generation")
    if record.get("boundary_delivery") == "deliver-v1":
        require(record.get("purpose") == "live-exploratory", "delivery requires live record")
        from .boundary_delivery import scoring_events
        events = scoring_events(manifest, events)
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
            covered, consumed, stale = [], set(), set()
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
                covered.append((a, b))
                consumed.add(oid)
            if reason:
                break
            recovered = union_length(covered)
            r += recovered
            # Consume after the whole event, so multiple spans for one obligation
            # all count once as a union. Re-supply discharges older grants too.
            for standing in failures.values():
                standing.difference_update(consumed)
            labels.append({"node": current, "class": "recovery" if covered else "scheduled",
                           "I": len(event["text"].encode()), "R": recovered,
                           "consumed_obligations": sorted(consumed), "stale_failure_obligations": sorted(stale)})
            current = node["next"]
        elif kind == "probe":
            attempts += 1
            outcome = classify_probe(manifest, node, event)
            target, failed_fields = route(manifest, node, event, outcome)
            field_failures = (None if failed_fields is None else
                              {o for f in failed_fields for o in node["field_obligations"][f]})
            active = set()
            for oid in node.get("obligations", []):
                obligation = manifest["obligations"][oid]
                source = seen.get(obligation["source"])
                if (source is not None and source < index
                        and is_active(obligation, seen, index)):
                    active.add(oid)
                    first.setdefault(oid, outcome == "correct" if field_failures is None
                                     else oid not in field_failures)
            if outcome != "correct":
                failed = active if field_failures is None else active & field_failures
                failures[current] = set(failed)
                observed_failures[current] = set(failed)
                if field_failures is not None:
                    for standing in failures.values():
                        standing.difference_update(active - failed)
            else:
                for standing in failures.values():
                    standing.difference_update(node.get("obligations", []))
            labels.append({"node": current, "class": outcome})
            if manifest.get("answer_tolerance") == "d10-v1":
                from .answer_tolerance import evaluate
                _, mode, rules = evaluate(manifest, node, event)
                labels[-1].update(mode=mode, rules_applied=rules)
            usage = event.get("generation")
            if record.get("timing_convention") == "decode-v1":
                usage = event.get("timing", {}).get("decode_generation")
            if usage is None:
                generation_available = False
            else:
                telemetry(usage, f"record.events[{index}].generation")
                generation_tokens += usage["tokens"]
                generation_seconds += Fraction(str(usage["seconds"]))
            current = target
        else:
            labels.append({"node": current, "class": "excluded_" + kind})
            current = node["next"]
    terminal = manifest["nodes"][current]
    if record.get("purpose") == "live-exploratory" and record.get("stop_reason") == "trial_wall_limit":
        limit = record.get("trial_wall_limit_seconds")
        require(finite(limit, positive=True) and wall is not None and wall >= limit,
                "invalid trial wall limit stop")
        if reason is None:
            terminal = {"kind": "terminal", "accepted": False}
            current = "$trial_wall_limit"
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
    result = {"unit": manifest["unit"], "manifest_sha256": record["manifest_sha256"],
            "authoring_findings": findings,
            "legacy_unknown_probes": [key for key, node in manifest["nodes"].items()
                                      if node["kind"] == "probe" and "unknown_answers" not in node],
            "resolved_obligations": resolved,
            "throughput_unavailable_reason": "offline_verification" if offline else None,
            "measurement_valid": valid, "reason": reason,
            "terminal": current if valid else None,
            "I": raw_i, "R": r if valid else None, "RR": rr,
            "rr_unavailable_reason": reason or ("zero_input" if not raw_i else None),
            "accepted": accepted, "first_attempt": first,
            "retention": Fraction(sum(first.values()), len(first)) if first else None,
            "attempts": attempts, "TPS": tps,
            "experimental_eTPS": tps * (1 - rr) if accepted and rr is not None and tps is not None else None,
            "wall_seconds": wall, "classifications": labels}
    if manifest.get("answer_tolerance") == "d10-v1":
        result["result_state"] = ("accepted_with_format_deviation" if
            any(label.get("mode") == "format_deviation" for label in labels) else "accepted_exact") if accepted else "failed"
    if record.get("timing_convention") == "decode-v1":
        result["timing_convention"] = "decode-v1"
        if not offline and tps is None:
            result["throughput_unavailable_reason"] = "decode_timing_unavailable"
    if manifest.get("answer_predicate") == "set-v1":
        from .dimension_accuracy import diagnostics, finalize
        diagnostic = diagnostics(manifest, events, labels,
            terminal_available=valid and current in manifest["nodes"] and terminal["kind"] == "terminal",
            reason=reason or record.get("stop_reason"))
        if diagnostic is not None:
            result["dimension_accuracy"] = diagnostic
            finalize(manifest, result)
    return result


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
            "acceptance_rate": Fraction(accepted, len(results)) if complete else None,
            "acceptance_rate_unavailable_reason": "unattempted_slots" if planned > len(results) else
                "no_trials" if not results else None,
            "acceptance_rate_attempted": Fraction(accepted, len(results)) if results else None,
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
