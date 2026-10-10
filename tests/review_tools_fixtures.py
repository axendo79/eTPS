"""SYNTHETIC review documents only; no corpus, human approval or model run."""
import copy

from authoring_fixtures import synthetic_document
from etps_v02.workload import sha


def synthetic_review_document(*, giveaways=False):
    doc = synthetic_document(("SYNTHETIC_KEY",))
    task = doc["tasks"][0]
    task["coverage_tags"]["context_pressure"] = "over"
    task["conversation"][0]["text"] = "[SYNTHETIC-m0] SYNTHETIC entity's north property is SYNTHETIC_KEY."
    for i in range(1, 5):
        task["conversation"].append({"id": f"SYNTHETIC-m{i}",
            "text": f"[SYNTHETIC-m{i}] SYNTHETIC unrelated filler {i} café.", "recap": False})
    probe = task["probes"][0]
    probe["position"] = "SYNTHETIC-m4"
    probe["wording"] += " Allowed status labels: active, expired, unresolved, unestablished."
    if giveaways:
        task["conversation"][3]["text"] += " sYnThEtIc_ kEy; the next question uses a fresh version and status label."
    return doc


def synthetic_two_task_document():
    doc = synthetic_review_document()
    other = copy.deepcopy(doc["tasks"][0])
    other["id"] = "SYNTHETIC-task2"
    doc["tasks"].append(other)
    return doc


def synthetic_review_input(raw, document, checks):
    return {"version": "review-input-v1", "source_sha256": sha(raw),
        "reviewer": "SYNTHETIC simulated reviewer", "date": "SYNTHETIC simulated date",
        "tasks": [{"task_id": t["id"], "checks": {k: True for k in checks},
                   "notes": "SYNTHETIC simulated checklist; not human review"} for t in document["tasks"]],
        "defects": []}
