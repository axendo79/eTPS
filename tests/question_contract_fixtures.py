"""SYNTHETIC public descriptors and mapper bundles; no corpus material."""
import json

from authoring_fixtures import synthetic_document, synthetic_recovery
from authoring_rulings_fixtures import synthetic_missing_unit
from etps_v02.intake.mapper import map_authoring
from etps_v02.workload import encode, sha


def write_contract_fixture(root, case="active"):
    if case == "missing":
        doc = synthetic_missing_unit()
    elif case == "retry":
        doc = synthetic_recovery()
    elif case == "expired":
        doc = synthetic_document(("SYNTHETIC_A", ("expired", None, [], "lapse")))
    elif case == "unresolved":
        doc = synthetic_document(("SYNTHETIC_A", ("unresolved", None,
            [("SYNTHETIC-m0", "SYNTHETIC_A"), ("SYNTHETIC-m1", "SYNTHETIC_B")], "change")))
    elif case == "settled":
        doc = synthetic_document(("SYNTHETIC_A", ("unresolved", None,
            [("SYNTHETIC-m0", "SYNTHETIC_A"), ("SYNTHETIC-m1", "SYNTHETIC_B")], "change"),
            ("active", "SYNTHETIC_A", [("SYNTHETIC-m0", "SYNTHETIC_A")], "precedence")))
    else:
        doc = synthetic_document(("SYNTHETIC_A",))
    files = map_authoring(encode(doc))
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    index = json.loads(files["bundle.json"])
    # Types and scope are public declarations, never inferred from answer keys.
    ordinary = {
        "answer": {"kind": "scalar", "value_type": "string", "point": "now"},
        "old": {"kind": "scalar", "value_type": "string", "point": "just after public message SYNTHETIC-m0"},
        "status": {"kind": "status", "scope": "SYNTHETIC entity, property, north", "point": "now"},
        "values": {"kind": "set", "value_type": "string"},
        "source": {"kind": "source"},
    }
    missing = {"status": {"kind": "missing_status", "item_id": "SYNTHETIC-unit"},
               "missing_item": {"kind": "item", "item_id": "SYNTHETIC-unit"}}
    questions = {p["id"]: {"core": p["wording"], "fields": missing if case == "missing" else ordinary}
                 for p in doc["tasks"][0]["probes"]}
    declaration = {"schema": "etps-question-contract-v1", "question_contract_version": "h3-compressed-v1",
                   "release_id": "SYNTHETIC-contract-v1", "bundle_sha256": sha(files["bundle.json"]),
                   "tasks": {index["tasks"][0]["id"]: {"questions": questions}}}
    (root / "question-contract.json").write_bytes(encode(declaration))
    return root / "bundle.json", index, declaration
