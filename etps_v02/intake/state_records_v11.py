"""Explicit v1/v1.1 intake dispatch; v1.1 adds exact missing-information queries only."""
import argparse
import copy
import json

from .. import scorer
from ..workload import decode, encode, sha
from . import state_records as v1

VERSION = "state-records-v1.1"
MAX_BYTES = v1.MAX_BYTES
MAX_MANIFEST_BYTES = v1.MAX_MANIFEST_BYTES
MAX_NODES = v1.MAX_NODES
IntakeError = v1.IntakeError


def version_of(manifest):
    metadata = manifest.get("metadata") if type(manifest) is dict else None
    item = metadata.get("state_records") if type(metadata) is dict else None
    return item.get("version") if type(item) is dict else None


def binding(manifest):
    if version_of(manifest) != VERSION:
        return v1.binding(manifest)
    item = manifest["metadata"]["state_records"]
    path = "manifest.metadata.state_records"
    v1.closed(item, ("version", "sha256"), path)
    key = item["sha256"]
    v1.check(type(key) is str and len(key) == 64 and all(c in "0123456789abcdef" for c in key),
             "binding_hash", path, "expected lowercase SHA-256")
    return key


def shape(sidecar):
    v1.closed(sidecar, ("version", "records", "fields", "probes"), "sidecar")
    v1.check(sidecar["version"] == VERSION, "sidecar_version", "sidecar.version", "unsupported version")
    v1.check(type(sidecar["fields"]) is dict, "field_type", "sidecar.fields", "expected object")
    standard = copy.deepcopy(sidecar)
    standard["version"] = v1.VERSION
    for field, query in sidecar["fields"].items():
        if type(query) is not dict or query.get("kind") != "missing_information":
            continue  # All old query shapes are validated by v1 unchanged.
        path = "sidecar.fields." + str(field)
        v1.closed(query, ("record", "kind", "missing_item", "projection"), path)
        v1.text_id(query["record"], path + ".record")
        v1.text_id(query["missing_item"], path + ".missing_item")
        v1.enum(query["projection"], ("status", "identifier"), path + ".projection")
        # Reuse the entire v1 record/chain format, without extending its states.
        standard["fields"][field] = {"record": query["record"], "kind": "status", "checkpoint": None}
    return v1.shape(standard)


def answers(sidecar, records, manifest, graph):
    missing = {field: query for field, query in sidecar["fields"].items()
               if query["kind"] == "missing_information"}
    for field, query in missing.items():
        path = "sidecar.fields." + field
        v1.check(query["record"] in records and query["missing_item"] in records,
                 "answer_reference", path, "record and missing item must reference declared records")
    probes = {key: node for key, node in manifest["nodes"].items() if node["kind"] == "probe"}
    v1.check(probes.keys() == sidecar["probes"].keys(), "probe_reference", "sidecar.probes",
             "probe declarations must cover exactly all executable probes")
    unavailable = []
    for key, node in probes.items():
        path = "sidecar.probes." + key
        graph.reference(key, path)
        fields = sidecar["probes"][key]
        v1.check(set(fields) == node["expected"].keys() and set(fields) <= sidecar["fields"].keys(),
                 "probe_fields", path, "probe fields must equal expected keys within the frozen logical field map")
        unavailable.extend({"probe": key, "field": field}
                           for field in sorted(sidecar["fields"].keys() - set(fields)))
        queries = {field: missing[field] for field in fields if field in missing}
        if not queries:
            continue
        status = queries.get("status")
        v1.check(status is not None and status["projection"] == "status" and
                 node["expected"]["status"] == "missing_information",
                 "missing_information_answer", path, "exact status field missing_information required")
        pair = (status["record"], status["missing_item"])
        for field, query in queries.items():
            v1.check((query["record"], query["missing_item"]) == pair and
                     (field == "status" if query["projection"] == "status" else
                      node["expected"][field] == query["missing_item"]),
                     "missing_information_answer", path + "." + field,
                     "identifier fields must exactly name the same declared missing item")
        current = graph.at(records[status["missing_item"]]["versions"], key, path + ".status")
        v1.check(current is None, "missing_item_established", path,
                 "missing item was previously established; lapse or disagreement is not insufficient information")

    # Validate regular projections with precisely the old answer checker. Only
    # this checker receives a filtered view; the full manifest is admitted below.
    standard = {**sidecar,
                "fields": {k: q for k, q in sidecar["fields"].items() if k not in missing},
                "probes": {k: [f for f in fields if f not in missing]
                           for k, fields in sidecar["probes"].items()}}
    view = {**manifest, "nodes": {key: ({**node, "expected": {
        f: value for f, value in node["expected"].items() if f not in missing}}
        if node["kind"] == "probe" else node) for key, node in manifest["nodes"].items()}}
    v1.answers(standard, records, view, graph)
    return unavailable


def validate_state_records(manifest, raw=None):
    """Dispatch v1 unchanged; explicitly admit only the narrow v1.1 extension."""
    if version_of(manifest) != VERSION:
        return v1.validate_state_records(manifest, raw)
    key = binding(manifest)
    v1.check(type(raw) is bytes, "sidecar_missing", "sidecar", "bound sidecar bytes required")
    v1.check(len(raw) <= MAX_BYTES, "safety_limit", "sidecar", "sidecar byte limit exceeded")
    v1.check(sha(raw) == key, "hash_mismatch", "manifest.metadata.state_records.sha256", "sidecar byte hash differs")
    try:
        sidecar = decode(raw)
        encode(sidecar)
    except scorer.InvalidRecord as exc:
        raise IntakeError("invalid_json", "sidecar", str(exc)) from exc
    records, versions = shape(sidecar)
    v1.check(type(manifest.get("nodes")) is dict, "manifest_invalid", "manifest.nodes", "expected nodes object")
    v1.check(len(manifest["nodes"]) <= MAX_NODES, "safety_limit", "manifest.nodes", "node limit exceeded")
    try:
        scorer.validate(manifest)
        scorer.digest(manifest)
    except scorer.InvalidRecord as exc:
        raise IntakeError("manifest_invalid", "manifest", str(exc)) from exc
    v1.chains(records, versions)
    graph = v1.EventGraph(manifest)
    v1.transitions(records, graph)
    v1.obligations(records, manifest, graph)
    unavailable = answers(sidecar, records, manifest, graph)
    return {"version": VERSION, "status": "validated", "checks": list(v1.CHECKS) + ["missing_information"],
            "records": len(records), "versions": len(versions), "probes": len(sidecar["probes"]),
            "unavailable_fields": unavailable, "semantics_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sidecar")
    args = parser.parse_args()
    try:
        try:
            manifest = decode(v1.read_bounded(args.manifest, MAX_MANIFEST_BYTES))
        except scorer.InvalidRecord as exc:
            raise IntakeError("manifest_invalid", args.manifest, str(exc)) from exc
        raw = v1.read_bounded(args.sidecar, MAX_BYTES) if binding(manifest) is not None and args.sidecar else None
        result = validate_state_records(manifest, raw)
    except IntakeError as exc:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": exc.code,
                          "path": exc.path, "detail": exc.detail}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
