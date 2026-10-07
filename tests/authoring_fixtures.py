"""Trivial SYNTHETIC tooling data only; no real task, key or prediction."""
import copy


def synthetic_document(values=("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C")):
    record = {"id": "SYNTHETIC-r", "entity": "SYNTHETIC entity", "property": "SYNTHETIC property",
              "scope": "SYNTHETIC north", "status_labels": {s: s for s in
                  ("active", "expired", "unresolved", "unestablished")}, "versions": []}
    fields = {name: {"dimension": dimension, "record": record["id"], "kind": kind,
                    "checkpoint": "SYNTHETIC-m0" if kind == "at-checkpoint" else None}
              for name, kind, dimension in (("answer", "current", "current"),
                  ("old", "at-checkpoint", "historical"), ("status", "status", "ambiguity"),
                  ("values", "values", "ambiguity"), ("source", "provenance", "provenance"))}
    task = {"id": "SYNTHETIC-task", "family": "F1", "coverage_tags": {
        "chain_depth": len(values) - 1, "distance": 0, "entity_similarity": "distinct",
        "ambiguity_status": "active", "provenance_need": "needed", "context_pressure": "within",
        "verbatim_possible": True, "subcases": []}, "conversation": [], "field_map": fields,
        "probes": [], "state_history": [record], "recoveries": [], "predictions": [
            {"arm": arm, "failing": None, "reason": "SYNTHETIC no behavior assumed"} for arm in "ABCDEF"]}
    for i, entry in enumerate(values):
        mid, pid, vid = f"SYNTHETIC-m{i}", f"SYNTHETIC-p{i}", f"SYNTHETIC-v{i}"
        if isinstance(entry, str):
            status, value, sources, change = "active", entry, [(mid, entry)], "establish" if not i else "change"
        else:
            status, value, sources, change = entry
        reqs = [{"id": vid + "-" + kind, "kind": kind, "begin_after": mid, "end_before": end}
                for kind, end in (("current", f"SYNTHETIC-m{i+1}" if i+1 < len(values) else "$trial_end"),
                                  ("historical", "$trial_end"))]
        record["versions"].append({"id": vid, "message": mid, "change": change, "status": status,
            "value": value, "sources": [{"message": source, "authority": "SYNTHETIC equal source", "value": val}
                                         for source, val in sources],
            "time": {"begin": "SYNTHETIC checkpoint", "end": None},
            "applicability": "SYNTHETIC north property", "requirements": reqs})
        task["conversation"].append({"id": mid, "text": f"[{mid}] SYNTHETIC event {i}; answer strict JSON.", "recap": False})
        task["probes"].append({"id": pid, "position": mid, "wording": f"[{pid}] SYNTHETIC return answer, old, status, values, source as JSON.",
            "field_map": copy.deepcopy(fields), "expected": {"answer": value if status == "active" else None,
                "old": values[0] if isinstance(values[0], str) else values[0][1], "status": status,
                "values": [val for _, val in sources] if status == "unresolved" else [value] if status == "active" else [],
                "source": sources[0][0] if status == "active" else None}, "set_fields": ["values"],
            "unknown_answers": [], "alternative_answers": [], "requirements": [r["id"] for r in reqs],
            "outcomes": {o: "$continue" if o == "correct" else "$reject" for o in
                         ("correct", "incorrect", "unknown", "malformed", "timeout")}})
    return {"version": "authoring-v1", "brief_version": "authoring-brief-v1", "dataset": "development", "tasks": [task]}


def synthetic_recovery():
    doc = synthetic_document(("SYNTHETIC_A",))
    task = doc["tasks"][0]
    probe = task["probes"][0]
    retry = copy.deepcopy(probe)
    rid = "SYNTHETIC-recovery"
    retry.update(id="SYNTHETIC-retry", position=rid, wording="[SYNTHETIC-retry] SYNTHETIC return the same JSON fields.")
    text = f"[{rid}] SYNTHETIC_A"
    begin = len(f"[{rid}] ".encode("utf-8"))
    task["recoveries"] = [{"id": rid, "failure_probes": [probe["id"]], "text": text,
        "spans": [[begin, len(text.encode("utf-8")), probe["requirements"][0]]], "new_spans": [], "retry": retry["id"]}]
    probe["outcomes"]["incorrect"] = rid
    task["probes"].append(retry)
    return doc
