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
        elif row["kind"] == "event" and payload["kind"] in {"probe", "delivery"} and pending is not None:
            usage = payload.get("usage")
            # Retain the exact reported value, including unusual provider values.
            pending["prompt_tokens"] = usage.get("prompt_tokens") if isinstance(usage, dict) else None
            pending = None
    return requests


def completion_requests(rows):
    """Completion-token reports per dispatched intent; unanswered intents stay in the denominator."""
    requests, pending = [], None
    for row in rows:
        payload = row["payload"]
        if row["kind"] == "request":
            pending = {"completion_tokens": None}
            requests.append(pending)
        elif row["kind"] == "event" and payload["kind"] in {"probe", "delivery"} and pending is not None:
            usage = payload.get("usage")
            pending["completion_tokens"] = usage.get("completion_tokens") if isinstance(usage, dict) else None
            pending = None
    return requests


def processing_totals(prompts, completions, memory):
    """Descriptive per-arm cost sums; a total exists only when every part is fully reported."""
    answer_completion = total(completions, "completion_tokens")
    if memory is None:
        extraction = {key: "not_applicable" for key in ("extraction_prompt_tokens", "extraction_completion_tokens",
                                                       "extraction_seconds", "facts_rejected")}
        extra_prompt = extra_completion = 0
    else:
        metrics = memory["metrics"]
        extraction = {key: metrics[key] for key in ("extraction_prompt_tokens", "extraction_completion_tokens",
                                                    "extraction_seconds", "facts_rejected")}
        def complete(key):
            m = metrics[key]
            return m["sum"] if m["request_count"] and m["coverage_count"] == m["request_count"] else None
        extra_prompt, extra_completion = complete("extraction_prompt_tokens"), complete("extraction_completion_tokens")
    prompt = total(prompts)
    return {"answer_and_delivery_prompt_tokens": prompt, "answer_and_delivery_completion_tokens": answer_completion,
            **extraction,
            "all_prompt_tokens": None if prompt["total"] is None or extra_prompt is None else prompt["total"] + extra_prompt,
            "all_completion_tokens": None if answer_completion["total"] is None or extra_completion is None
                else answer_completion["total"] + extra_completion,
            "definition": "backend usage for every answer and delivery request plus self-reported memory "
                          "extraction telemetry; null unless every part is reported for every request"}


def total(requests, key="prompt_tokens"):
    values = [r[key] for r in requests if integer(r[key])]
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
    add_arm_comparison(store, result, arms)


def add_arm_comparison(store, result, arms):
    """Preserve arm identities and repetitions without pooling trial scores."""
    from .memory_telemetry import requests as memory_requests, summarize as memory_summary

    names = sorted(set(arms) | {s["arm"] for s in store.plan["slots"]})
    comparisons, memory_by_arm = {}, {name: [] for name in names if "memory_telemetry_field" in arms.get(name, {})}
    prompts_by_arm, completions_by_arm = {name: [] for name in names}, {name: [] for name in names}
    grouped = {}
    for slot, trial in zip(store.plan["slots"], result["trials"]):
        grouped.setdefault((slot["task"], slot["arm"]), []).append((slot, trial))
    for task, artifact in store.plan["tasks"].items():
        entries = {}
        for name in names:
            arm = arms.get(name, {})
            trials, prompts, observations = [], [], []
            memory_enabled = name in memory_by_arm
            for slot, trial in grouped.get((task, name), []):
                rows = store.entries(slot["id"])
                prompt = processing_requests(rows)
                prompts.extend(prompt)
                prompts_by_arm[name].extend(prompt)
                completions_by_arm[name].extend(completion_requests(rows))
                memory = memory_requests(rows) if memory_enabled else []
                observations.extend(memory)
                score = trial.get("score") or {}
                trials.append({"slot": slot["id"], "state": trial["state"],
                    **{key: score.get(key) for key in ("result_state", "accepted", "first_attempt", "I", "R", "RR", "TPS")},
                    "eTPS": score.get("experimental_eTPS"),
                    "processed_prompt_tokens": total(prompt),
                    "memory_telemetry": memory_summary(memory) if memory_enabled else None})
            entries[name] = {"arm": name, "context_policy": arm.get("context_policy", "full"),
                             "provider": arm.get("provider"), "trials": trials,
                             "processed_prompt_tokens": total(prompts),
                             "memory_telemetry": memory_summary(observations) if memory_enabled else None}
            if memory_enabled:
                memory_by_arm[name].extend(observations)
        comparisons[task] = {"task_artifact_sha256": artifact, "arms": entries}
    result["arm_comparison"] = comparisons
    if memory_by_arm:
        result["memory_telemetry"] = {name: memory_summary(observations) for name, observations in memory_by_arm.items()}
    result["processing_totals"] = {name: processing_totals(prompts_by_arm[name], completions_by_arm[name],
                                                           result.get("memory_telemetry", {}).get(name))
                                   for name in names}
    if store.plan.get("boundary_delivery") == "deliver-v1":
        from .boundary_delivery import observations as delivery_observations
        result["boundary_delivery"] = "deliver-v1"
        result["delivery_processing"] = {name: [] for name in names}
        for slot in store.plan["slots"]:
            name = slot["arm"]
            result["delivery_processing"][name].append({"slot": slot["id"], "task": slot["task"],
                "requests": delivery_observations(store.entries(slot["id"]), arms[name]["provider"])})
