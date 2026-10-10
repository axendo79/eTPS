"""Shared factual views for maintainer review; never a scorer or admission gate."""
from .authoring import validate_authoring

CHECKS = {
    "conversation_supports_answers": "Conversation supports every answer",
    "history_matches": "State history matches the conversation",
    "keys_exact": "Answer keys, fields, requirements and correction spans are exact",
    "no_giveaway": "No unintended answer giveaway",
    "tags_plausible": "Coverage tags are plausible",
}


def document(raw):
    return validate_authoring(raw)


def probe_context(task, probe):
    """Conversation prefix, followed by corrections on this probe's linked branch.

    Return no context for a cyclic/unanchored declaration; lint does not invent a
    position or perform the mapper's graph admission.
    """
    messages = task["conversation"]
    positions = {m["id"]: i for i, m in enumerate(messages)}
    probes = {p["id"]: p for p in task["probes"]}
    recoveries = {r["id"]: r for r in task["recoveries"]}
    corrections, seen = [], set()
    point = probe["position"]
    while point not in positions:
        if point in seen or point not in recoveries:
            return []
        seen.add(point)
        correction = recoveries[point]
        corrections.append({"id": point, "text": correction["text"]})
        parents = correction["failure_probes"]
        if len(parents) != 1 or parents[0] not in probes:
            return []
        point = probes[parents[0]]["position"]
    return messages[:positions[point] + 1] + list(reversed(corrections))


def field_version(task, probe, query):
    record = next(r for r in task["state_history"] if r["id"] == query["record"])
    context = probe_context(task, probe)
    positions = {m["id"]: i for i, m in enumerate(context)}
    point = positions.get(query.get("checkpoint")) if query["kind"] == "at-checkpoint" else len(context) - 1
    if point is None:
        return record, None
    versions = [v for v in record["versions"] if v["message"] in positions and positions[v["message"]] <= point]
    return record, versions[-1] if versions else None


def field_sources(task, probe, query):
    """Declared selected version's transition and claim messages, in source order.

    Absence has no source message to position. For missing_information, include
    the question's target record and explicitly declared missing-item history.
    These are annotation references, not mechanically proven semantic evidence.
    """
    _, version = field_version(task, probe, query)
    versions = [version] if version else []
    if query["kind"] == "missing_information":
        _, missing = field_version(task, probe, {"record": query["missing_item"], "kind": "current"})
        if missing:
            versions.append(missing)
    refs = {v["message"] for v in versions}
    refs.update(s["message"] for v in versions for s in v["sources"])
    return [m for m in task["conversation"] if m["id"] in refs]
