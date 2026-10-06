"""Bounded state-records-v1 intake validation; never a scoring/replay hook."""
import argparse
from collections import deque
import json
from pathlib import Path

from .. import scorer
from ..set_answers import field_equal, scalar
from ..workload import decode, encode, sha

VERSION = "state-records-v1"
MAX_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_NODES = 4096
MAX_RECORDS = 128
MAX_VERSIONS = 1024
MAX_FIELDS = 256
MAX_PROBE_FIELDS = 16384
CHECKS = ("hash_binding", "closed_shape", "version_chains", "event_order",
          "obligation_boundaries", "reinstatement", "disagreement", "answer_keys")
STATUSES = ("active", "expired", "unresolved", "unestablished")
KINDS = ("current", "at-checkpoint", "status", "values", "provenance")


class IntakeError(ValueError):
    def __init__(self, code, path, detail):
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code}: {path}: {detail}")


def check(condition, code, path, detail):
    if not condition:
        raise IntakeError(code, path, detail)


def closed(value, fields, path):
    check(type(value) is dict and all(type(k) is str for k in value), "field_type", path, "expected object")
    check(set(fields) <= value.keys(), "required_fields", path, "required fields missing")
    check(value.keys() <= set(fields), "closed_fields", path, "unknown fields")


def text_id(value, path, nullable=False):
    check(nullable and value is None or type(value) is str and bool(value),
          "field_type", path, "expected nonempty string" + (" or null" if nullable else ""))


def listed(value, path):
    check(type(value) is list, "field_type", path, "expected array")


def enum(value, choices, path):
    check(type(value) is str and value in choices, "field_type", path, "unsupported value")


def binding(manifest):
    metadata = manifest.get("metadata") if type(manifest) is dict else None
    if type(metadata) is not dict or "state_records" not in metadata:
        return None
    item = metadata["state_records"]
    path = "manifest.metadata.state_records"
    closed(item, ("version", "sha256"), path)
    check(item["version"] == VERSION, "binding_version", path, "unsupported intake version")
    key = item["sha256"]
    check(type(key) is str and len(key) == 64 and all(c in "0123456789abcdef" for c in key),
          "binding_hash", path, "expected lowercase SHA-256")
    return key


class EventGraph:
    """Bounded DAG ancestry/dominance, without enumerating branch paths."""
    def __init__(self, manifest):
        self.nodes = manifest["nodes"]
        self.bits = {key: 1 << i for i, key in enumerate(self.nodes)}
        edges, incoming = {}, {key: [] for key in self.nodes}
        for key, node in self.nodes.items():
            if node["kind"] == "terminal":
                targets = []
            elif node["kind"] == "probe":
                targets = list(node["next"].values())
                if manifest.get("routing") == "field-v1":
                    targets += [entry["next"] for entry in node.get("field_routes", [])]
            else:
                targets = [node["next"]]
            edges[key] = sorted(set(targets))
            for target in edges[key]:
                incoming[target].append(key)
        indegree = {key: len(parents) for key, parents in incoming.items()}
        pending = deque(key for key in self.nodes if not indegree[key])
        self.ancestors, self.dominators, self.reachable = {}, {}, set()
        while pending:
            key = pending.popleft()
            parents = [p for p in incoming[key] if p in self.reachable]
            ancestors = 0
            for parent in parents:
                ancestors |= self.ancestors[parent] | self.bits[parent]
            self.ancestors[key] = ancestors
            if key == manifest["start"]:
                self.reachable.add(key)
                self.dominators[key] = self.bits[key]
            elif parents:
                self.reachable.add(key)
                common = self.dominators[parents[0]]
                for parent in parents[1:]:
                    common &= self.dominators[parent]
                self.dominators[key] = common | self.bits[key]
            else:
                self.dominators[key] = 0
            for target in edges[key]:
                indegree[target] -= 1
                if not indegree[target]:
                    pending.append(target)

    def reference(self, event, path, user=False):
        check(event in self.nodes and event in self.reachable, "event_reference", path,
              "event must reference a reachable manifest node")
        check(not user or self.nodes[event]["kind"] == "user", "event_reference", path,
              "state/source event must be a delivered user node")

    def before(self, left, right, path, equal=False):
        if equal and left == right:
            return
        check(left != right and bool(self.ancestors[right] & self.bits[left]),
              "event_order", path, "event does not precede target")
        check(bool(self.dominators[right] & self.bits[left]), "branch_inconsistent", path,
              "event is absent on another path to target")

    def at(self, versions, point, path):
        selected = None
        for version in versions:
            event = version["event"]
            if event == point:
                selected = version
            elif self.ancestors[point] & self.bits[event]:
                check(bool(self.dominators[point] & self.bits[event]), "branch_inconsistent", path,
                      "probe/checkpoint has branch-dependent state")
                selected = version
        return selected


def shape(sidecar):
    closed(sidecar, ("version", "records", "fields", "probes"), "sidecar")
    check(sidecar["version"] == VERSION, "sidecar_version", "sidecar.version", "unsupported version")
    listed(sidecar["records"], "sidecar.records")
    check(len(sidecar["records"]) <= MAX_RECORDS, "safety_limit", "sidecar.records", "record limit exceeded")
    check(type(sidecar["fields"]) is dict and type(sidecar["probes"]) is dict,
          "field_type", "sidecar", "fields/probes must be objects")
    check(len(sidecar["fields"]) <= MAX_FIELDS, "safety_limit", "sidecar.fields", "field limit exceeded")
    records, versions, ids = {}, {}, set()
    for i, record in enumerate(sidecar["records"]):
        path = f"sidecar.records[{i}]"
        closed(record, ("id", "entity", "property", "scope", "status_values", "versions"), path)
        for name in ("id", "entity", "property", "scope"):
            text_id(record[name], path + "." + name)
        check(record["id"] not in ids, "duplicate_id", path + ".id", "duplicate record/version ID")
        ids.add(record["id"])
        records[record["id"]] = record
        closed(record["status_values"], STATUSES, path + ".status_values")
        for value in record["status_values"].values():
            text_id(value, path + ".status_values")
        listed(record["versions"], path + ".versions")
        for j, version in enumerate(record["versions"]):
            vp = f"{path}.versions[{j}]"
            closed(version, ("id", "number", "previous", "next", "event", "transition", "status",
                             "value", "claims", "valid_time", "applicability", "obligations"), vp)
            for name in ("id", "event", "applicability"):
                text_id(version[name], vp + "." + name)
            for name in ("previous", "next"):
                text_id(version[name], vp + "." + name, nullable=True)
            check(type(version["number"]) is int and version["number"] > 0,
                  "field_type", vp + ".number", "expected positive integer")
            check(version["id"] not in ids, "duplicate_id", vp + ".id", "duplicate record/version ID")
            ids.add(version["id"])
            versions[version["id"]] = version
            check(len(versions) <= MAX_VERSIONS, "safety_limit", vp, "version limit exceeded")
            enum(version["transition"], ("establish", "change", "lapse", "reinstate", "precedence"), vp + ".transition")
            enum(version["status"], STATUSES[:3], vp + ".status")
            check(scalar(version["value"]), "field_type", vp + ".value", "expected typed-v1 scalar")
            closed(version["valid_time"], ("begin", "end"), vp + ".valid_time")
            for value in version["valid_time"].values():
                text_id(value, vp + ".valid_time", nullable=True)
            listed(version["claims"], vp + ".claims")
            for claim in version["claims"]:
                closed(claim, ("source", "authority", "value"), vp + ".claims")
                text_id(claim["source"], vp + ".claims.source")
                text_id(claim["authority"], vp + ".claims.authority")
                check(scalar(claim["value"]), "field_type", vp + ".claims.value", "expected typed-v1 scalar")
            listed(version["obligations"], vp + ".obligations")
            for obligation in version["obligations"]:
                closed(obligation, ("id", "kind", "begin_after", "end_before"), vp + ".obligations")
                for name in ("id", "begin_after", "end_before"):
                    text_id(obligation[name], vp + ".obligations." + name)
                enum(obligation["kind"], ("current", "historical"), vp + ".obligations.kind")
    for key, query in sidecar["fields"].items():
        path = "sidecar.fields." + str(key)
        text_id(key, path)
        closed(query, ("record", "kind", "checkpoint"), path)
        text_id(query["record"], path + ".record")
        enum(query["kind"], KINDS, path + ".kind")
        text_id(query["checkpoint"], path + ".checkpoint", nullable=query["kind"] != "at-checkpoint")
        check(query["kind"] == "at-checkpoint" or query["checkpoint"] is None,
              "field_type", path + ".checkpoint", "nonhistorical query must have null checkpoint")
    total = 0
    for key, fields in sidecar["probes"].items():
        text_id(key, "sidecar.probes")
        listed(fields, "sidecar.probes." + key)
        check(all(type(f) is str for f in fields) and len(fields) == len(set(fields)),
              "probe_fields", "sidecar.probes." + key, "expected unique field names")
        total += len(fields)
    check(total <= MAX_PROBE_FIELDS, "safety_limit", "sidecar.probes", "probe-field limit exceeded")
    return records, versions


def chains(records, versions):
    for record in records.values():
        chain = record["versions"]
        for i, version in enumerate(chain):
            path = "versions." + version["id"]
            for link in (version["previous"], version["next"]):
                check(link is None or link in versions, "chain_link_unresolved", path, "missing predecessor/successor")
            check(version["number"] == i + 1 and
                  version["previous"] == (chain[i - 1]["id"] if i else None) and
                  version["next"] == (chain[i + 1]["id"] if i + 1 < len(chain) else None),
                  "version_chain", path, "chain must be contiguous, reciprocal and acyclic")


def transitions(records, graph):
    for record in records.values():
        previous, obligation_ids = None, set()
        for version in record["versions"]:
            path = "versions." + version["id"]
            graph.reference(version["event"], path + ".event", user=True)
            if previous:
                graph.before(previous["event"], version["event"], path + ".event")
            if version["status"] == "unresolved":
                sources = [claim["source"] for claim in version["claims"]]
                check(len(sources) >= 2 and len(sources) == len(set(sources)) and version["value"] is None,
                      "disagreement_claims", path, "unresolved requires distinct source claims and null scalar value")
            elif version["status"] == "active":
                check(len(version["claims"]) == 1 and scorer.answer_equal(
                    {"value": version["claims"][0]["value"]}, {"value": version["value"]}),
                    "state_claims", path, "active version requires one matching source claim")
            else:
                check(version["value"] is None and not version["claims"], "state_claims", path,
                      "expired version has no current value/claims")
            for claim in version["claims"]:
                graph.reference(claim["source"], path + ".claims.source", user=True)
                graph.before(claim["source"], version["event"], path + ".claims.source", equal=True)
            transition = version["transition"]
            if previous and previous["status"] == "unresolved":
                check(transition == "precedence" or transition == "change" and version["status"] == "unresolved",
                      "unresolved_without_precedence", path,
                      "disagreement cannot resolve without recorded precedence")
            if transition == "reinstate":
                current = [o["id"] for o in version["obligations"] if o["kind"] == "current"]
                check(previous is not None and previous["status"] == "expired" and version["status"] == "active"
                      and bool(current) and not obligation_ids.intersection(o["id"] for o in version["obligations"]),
                      "reinstatement_not_fresh", path, "reinstatement requires lapse, new version and fresh current obligation")
            elif previous is None:
                check(transition == "establish" and version["status"] != "expired", "state_transition", path,
                      "first version must establish state")
            elif transition == "precedence":
                check(previous["status"] == "unresolved" and version["status"] == "active" and
                      version["claims"][0] in previous["claims"], "precedence_claim", path,
                      "precedence must select a previously recorded claim")
            elif transition == "lapse":
                check(previous["status"] == "active" and version["status"] == "expired", "state_transition", path,
                      "lapse must end active state")
            else:
                check(transition == "change" and version["status"] != "expired" and
                      (previous["status"] == "active" or previous["status"] == version["status"] == "unresolved"),
                      "state_transition", path, "unsupported transition for recorded status")
            obligation_ids.update(o["id"] for o in version["obligations"])
            previous = version


def obligations(records, manifest, graph):
    used = set()
    for record in records.values():
        versions = record["versions"]
        for i, version in enumerate(versions):
            path = "versions." + version["id"] + ".obligations"
            for item in version["obligations"]:
                oid = item["id"]
                check(oid in manifest["obligations"], "obligation_reference", path, "missing executable obligation")
                check(oid not in used, "obligation_reused", path, "obligation is attributed to several versions")
                used.add(oid)
                expected_end = versions[i + 1]["event"] if i + 1 < len(versions) else "$trial_end"
                actual = manifest["obligations"][oid]
                check(actual == {"source": version["event"], "begin_after": item["begin_after"],
                                 "end_before": item["end_before"]} and item["begin_after"] == version["event"]
                      and (item["kind"] != "current" or item["end_before"] == expected_end),
                      "obligation_boundary", path, "executable and recorded boundaries differ")
                if item["end_before"] != "$trial_end":
                    graph.reference(item["end_before"], path + ".end_before")
                    graph.before(version["event"], item["end_before"], path + ".end_before")


def projected(record, version, kind):
    status = version["status"] if version else "unestablished"
    if kind == "status":
        return record["status_values"][status]
    if kind == "values":
        if status == "unresolved":
            values, seen = [], set()
            for claim in version["claims"]:
                identity = (type(claim["value"]), claim["value"])
                if identity not in seen:
                    values.append(claim["value"])
                    seen.add(identity)
            return values
        return [version["value"]] if status == "active" else []
    if kind == "provenance":
        return version["claims"][0]["source"] if status == "active" else None
    return version["value"] if status == "active" else None


def answers(sidecar, records, manifest, graph):
    probes = {key: node for key, node in manifest["nodes"].items() if node["kind"] == "probe"}
    check(probes.keys() == sidecar["probes"].keys(), "probe_reference", "sidecar.probes",
          "probe declarations must cover exactly all executable probes")
    for field, query in sidecar["fields"].items():
        check(query["record"] in records, "answer_reference", "sidecar.fields." + field, "missing state record")
        if query["kind"] == "at-checkpoint":
            graph.reference(query["checkpoint"], "sidecar.fields." + field + ".checkpoint")
    unavailable = []
    for key, node in probes.items():
        path = "sidecar.probes." + key
        graph.reference(key, path)
        fields = sidecar["probes"][key]
        check(set(fields) == node["expected"].keys() and set(fields) <= sidecar["fields"].keys(),
              "probe_fields", path, "probe fields must equal expected keys within the frozen logical field map")
        unavailable.extend({"probe": key, "field": field} for field in sorted(sidecar["fields"].keys() - set(fields)))
        for field in fields:
            query = sidecar["fields"][field]
            record = records[query["record"]]
            current = graph.at(record["versions"], key, path + "." + field)
            if query["kind"] == "at-checkpoint":
                graph.before(query["checkpoint"], key, path + "." + field)
                current = graph.at(record["versions"], query["checkpoint"], path + "." + field)
            expected = projected(record, current, query["kind"])
            equal = (field_equal(node, field, node["expected"][field], expected)
                     if manifest.get("answer_predicate") == "set-v1" else
                     scorer.answer_equal({field: node["expected"][field]}, {field: expected}))
            check(equal, "answer_mismatch", path + "." + field, "expected answer differs from recorded state projection")
    return unavailable


def validate_state_records(manifest, raw=None):
    """Return an intake result or raise reason-coded IntakeError. Never mutates inputs."""
    key = binding(manifest)
    if key is None:
        return {"version": VERSION, "status": "not_opted_in", "semantics_verified": False}
    check(type(raw) is bytes, "sidecar_missing", "sidecar", "bound sidecar bytes required")
    check(len(raw) <= MAX_BYTES, "safety_limit", "sidecar", "sidecar byte limit exceeded")
    check(sha(raw) == key, "hash_mismatch", "manifest.metadata.state_records.sha256", "sidecar byte hash differs")
    try:
        sidecar = decode(raw)
        encode(sidecar)  # Verify decoded strings are portable UTF-8; keep/hash original bytes.
    except scorer.InvalidRecord as exc:
        raise IntakeError("invalid_json", "sidecar", str(exc)) from exc
    records, versions = shape(sidecar)
    check(type(manifest.get("nodes")) is dict, "manifest_invalid", "manifest.nodes", "expected nodes object")
    check(len(manifest["nodes"]) <= MAX_NODES, "safety_limit", "manifest.nodes", "node limit exceeded")
    try:
        scorer.validate(manifest)
        scorer.digest(manifest)
    except scorer.InvalidRecord as exc:
        raise IntakeError("manifest_invalid", "manifest", str(exc)) from exc
    chains(records, versions)
    graph = EventGraph(manifest)
    transitions(records, graph)
    obligations(records, manifest, graph)
    unavailable = answers(sidecar, records, manifest, graph)
    return {"version": VERSION, "status": "validated", "checks": list(CHECKS),
            "records": len(records), "versions": len(versions), "probes": len(sidecar["probes"]),
            "unavailable_fields": unavailable, "semantics_verified": False}


def read_bounded(path, ceiling):
    path = Path(path)
    try:
        check(path.stat().st_size <= ceiling, "safety_limit", str(path), "file byte limit exceeded")
        with path.open("rb") as stream:
            raw = stream.read(ceiling + 1)
        check(len(raw) <= ceiling, "safety_limit", str(path), "file byte limit exceeded")
        return raw
    except OSError as exc:
        raise IntakeError("file_unavailable", str(path), "cannot read requested file") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sidecar")
    args = parser.parse_args()
    try:
        try:
            manifest = decode(read_bounded(args.manifest, MAX_MANIFEST_BYTES))
        except scorer.InvalidRecord as exc:
            raise IntakeError("manifest_invalid", args.manifest, str(exc)) from exc
        raw = read_bounded(args.sidecar, MAX_BYTES) if binding(manifest) is not None and args.sidecar else None
        result = validate_state_records(manifest, raw)
    except IntakeError as exc:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": exc.code,
                          "path": exc.path, "detail": exc.detail}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
