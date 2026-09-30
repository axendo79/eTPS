"""Descriptive context-policy and processing-cost diagnostics; never scoring."""
from .scorer import integer


def processing_requests(rows):
    """Include unanswered intents in the denominator; never infer token counts."""
    requests = []
    pending = None
    for row in rows:
        payload = row["payload"]
        if row["kind"] == "request":
            pending = {"node": payload["node"], "prompt_tokens": None}
            requests.append(pending)
        elif row["kind"] == "event" and payload["kind"] == "probe" and pending is not None:
            usage = payload.get("usage")
            # Retain the exact reported value, including unusual provider values.
            pending["prompt_tokens"] = usage.get("prompt_tokens") if isinstance(usage, dict) else None
            pending = None
    return requests


def total(requests):
    values = [r["prompt_tokens"] for r in requests if integer(r["prompt_tokens"])]
    return {"numerator": sum(values), "coverage_count": len(values),
            "request_count": len(requests),
            "total": sum(values) if values and len(values) == len(requests) else None}


def add_diagnostics(store, result):
    arms = store.plan.get("arms", {})
    enabled = (store.plan["schema"] == "etps-live-plan-v1" or
               any("context_policy" in arm for arm in arms.values()) or
               any(n["kind"] == "session_boundary" for slot in store.plan["slots"]
                   for n in store.manifest(slot["id"])["nodes"].values()))
    if not enabled or store.plan["purpose"] == "dev-manual":
        return
    by_arm, pairs = {}, {}
    fields = ("accepted", "first_attempt", "retention", "I", "R", "RR", "TPS", "experimental_eTPS")
    for slot, trial in zip(store.plan["slots"], result["trials"]):
        requests = processing_requests(store.entries(slot["id"]))
        by_arm.setdefault(slot["arm"], []).extend(requests)
        policy = arms.get(slot["arm"], {}).get("context_policy", "full")
        score = trial.get("score") or {}
        entry = {"slot": slot["id"], "arm": slot["arm"], "state": trial["state"],
                 **{key: score.get(key) for key in fields},
                 "processed_prompt_tokens": total(requests), "requests": requests}
        pair = pairs.setdefault(slot["task"], {"task_artifact_sha256": store.plan["tasks"][slot["task"]],
                                               "full": [], "reset-v1": []})
        pair[policy].append(entry)
    result["processed_prompt_tokens"] = {arm: total(requests) for arm, requests in by_arm.items()}
    result["context_policy_pairing"] = pairs
