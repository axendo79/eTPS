"""Trivial SYNTHETIC missing-information tooling fixtures only."""
import copy

from authoring_fixtures import synthetic_document, synthetic_recovery


def synthetic_missing_unit():
    doc = synthetic_document(("SYNTHETIC_quantity",))
    task = doc["tasks"][0]
    task["family"] = "F9"
    task["state_history"][0]["property"] = "SYNTHETIC quantity"
    missing = copy.deepcopy(task["state_history"][0])
    missing.update(id="SYNTHETIC-unit", property="SYNTHETIC unit", versions=[])
    task["state_history"].append(missing)
    task["field_map"] = {name: {"dimension": "control", "record": "SYNTHETIC-r",
        "kind": "missing_information", "missing_item": "SYNTHETIC-unit", "projection": projection}
        for name, projection in (("status", "status"), ("missing_item", "identifier"))}
    probe = task["probes"][0]
    probe.update(field_map=copy.deepcopy(task["field_map"]), set_fields=[],
        wording="[SYNTHETIC-p0] SYNTHETIC return status and missing_item as exact JSON.",
        expected={"status": "missing_information", "missing_item": "SYNTHETIC-unit"})
    return doc


def synthetic_disallowed_forms():
    doc = synthetic_document()
    doc["tasks"][0]["state_history"][0]["versions"][0]["requirements"][0]["begin_after"] = "SYNTHETIC-m1"
    yield doc, "delayed_obligation"
    doc = synthetic_recovery()
    task = doc["tasks"][0]
    task["recoveries"][0]["failure_probes"].append("SYNTHETIC-retry")
    task["probes"][1]["outcomes"]["incorrect"] = "SYNTHETIC-recovery"
    yield doc, "multi_failure_recovery"
    doc = synthetic_document()
    doc["tasks"][0]["probes"][0]["alternative_answers"] = [{"answer": "SYNTHETIC_other"}]
    yield doc, "alternative_answers"
