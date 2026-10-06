"""set-v1 field diagnostics; no changes to acceptance or efficiency measures."""
from fractions import Fraction

from .scorer import OUTCOMES, mapping, require
from .set_answers import comparable, field_equal

DIMENSIONS = ("current", "historical", "expired", "ambiguity", "provenance", "control")
REASONS = ("incorrect", "unknown", "malformed", "unattempted", "unavailable")


def validate_probe(node):
    if "field_dimensions" not in node:
        return
    tags = mapping(node["field_dimensions"], "field_dimensions")
    require(tags.keys() == node["expected"].keys(), "field_dimensions must cover expected fields")
    require(all(isinstance(tag, str) and tag in DIMENSIONS for tag in tags.values()),
            "unsupported field dimension")


def plan(manifest):
    probes = [node for node in manifest["nodes"].values() if node["kind"] == "probe"]
    tagged = [node for node in probes if "field_dimensions" in node]
    if manifest.get("answer_predicate") != "set-v1" or not tagged:
        return None, None
    tags = tagged[0]["field_dimensions"]
    if any(node.get("field_dimensions") != tags for node in probes):
        return None, "heterogeneous_field_plan"
    return tags, None


def aggregate(tags, fields, unavailable_reason=None):
    result = {}
    for dimension in DIMENSIONS:
        statuses = [fields[key] for key, tag in tags.items() if tag == dimension]
        correct, planned = statuses.count("correct"), len(statuses)
        result[dimension] = {"correct": correct, "planned": planned,
                             "accuracy": Fraction(correct, planned) if planned else None,
                             "reason_counts": {reason: statuses.count(reason) for reason in REASONS},
                             "unavailable_reasons": ({unavailable_reason: statuses.count("unavailable")}
                                 if unavailable_reason and "unavailable" in statuses else {})}
    return result


def fields_for(manifest, node, event, outcome, tags):
    if outcome in {"timeout", "malformed", "unknown"}:
        return {key: "unavailable" if outcome == "timeout" else outcome for key in tags}
    normalized = comparable(manifest, node, event["answer"])
    if normalized is None:
        # Alias collisions cannot be attributed to an unambiguous field value.
        return {key: "incorrect" for key in tags}
    answer, expected, _ = normalized
    return {key: "correct" if key in answer and field_equal(node, key, answer[key], expected[key])
            else "incorrect" for key in tags}


def diagnostics(manifest, events, labels, *, terminal_available, reason=None, unattempted=False):
    tags, problem = plan(manifest)
    if problem:
        return {"unavailable_reason": problem, "first_attempt": None, "terminal": None}
    if tags is None:
        return None
    observations = [(event, label["class"]) for event, label in zip(events, labels)
                    if event["kind"] == "probe" and label["class"] in OUTCOMES]
    first_reason = terminal_reason = None
    if observations:
        event, outcome = observations[0]
        first = fields_for(manifest, manifest["nodes"][event["node"]], event, outcome, tags)
        first_reason = "timeout" if outcome == "timeout" else None
    else:
        first = {key: "unattempted" for key in tags}
    if terminal_available and observations:
        event, outcome = observations[-1]
        terminal = fields_for(manifest, manifest["nodes"][event["node"]], event, outcome, tags)
        terminal_reason = "timeout" if outcome == "timeout" else None
    else:
        terminal = {key: "unattempted" if unattempted else "unavailable" for key in tags}
        terminal_reason = None if unattempted else reason or "no_terminal_answer"
    return {"first_attempt": aggregate(tags, first, first_reason),
            "terminal": aggregate(tags, terminal, terminal_reason),
            "first_fields": first, "terminal_fields": terminal, "unavailable_reason": None}


def finalize(manifest, result):
    """Apply evidence/slot invalidation after pure event scoring, if necessary."""
    diagnostic = result.get("dimension_accuracy")
    tags, _ = plan(manifest)
    if diagnostic is None or tags is None or result["measurement_valid"]:
        return
    terminal = {key: "unavailable" for key in tags}
    diagnostic = dict(diagnostic, terminal_fields=terminal,
                      terminal=aggregate(tags, terminal, result["reason"]))
    if result["reason"] == "unverified_evidence":
        diagnostic.update(first_fields=dict(terminal),
                          first_attempt=aggregate(tags, terminal, result["reason"]))
    result["dimension_accuracy"] = diagnostic


def add_report(store, result):
    """One row per tagged planned slot; never infer or pool repeat identities."""
    rows = []
    for slot, trial in zip(store.plan["slots"], result["trials"]):
        manifest = store.manifest(slot["id"])
        tags, problem = plan(manifest)
        if tags is None and problem is None:
            continue
        scored = trial.get("score")
        diagnostic = scored.get("dimension_accuracy") if scored else None
        if diagnostic is None:
            diagnostic = diagnostics(manifest, [], [], terminal_available=False,
                                     reason=trial.get("reason"), unattempted=trial["state"] == "unattempted")
        elif tags is not None and (trial["state"] != "finished" or not scored["measurement_valid"]):
            diagnostic = dict(diagnostic)
            terminal = {key: "unavailable" for key in tags}
            diagnostic.update(terminal_fields=terminal,
                terminal=aggregate(tags, terminal, scored.get("reason") or trial["state"]))
        rows.append({"slot": slot["id"], "task": slot["task"], "arm": slot["arm"],
                     "state": trial["state"], "dimension_accuracy": diagnostic})
    if rows:
        result["dimension_accuracy"] = rows
