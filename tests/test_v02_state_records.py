"""Public synthetic state-record intake fixtures, never corpus tasks or model runs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.intake.state_records import IntakeError, validate_state_records
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, json_default, replay_export, run_offline
from etps_v02.scorer import OUTCOMES, digest, score
from etps_v02.workload import encode, sha
from test_v02_runner import bundle, response
from test_v02_scorer import user


def bind(manifest, sidecar):
    raw = encode(sidecar)
    manifest.setdefault("metadata", {})["state_records"] = {"version": "state-records-v1", "sha256": sha(raw)}
    return raw


def chain(values=("A", "B", "C")):
    """Each tuple entry is active, or a (status, value, claims, transition) row."""
    m = {"unit": "utf8_bytes", "answer_schema": "typed-v1", "answer_predicate": "set-v1",
         "start": "e0", "nodes": {"end": {"kind": "terminal", "accepted": True}}, "obligations": {}}
    record = {"id": "r", "entity": "synthetic entity", "property": "code", "scope": "north",
              "status_values": {"active": "active", "expired": "expired", "unresolved": "unresolved",
                                "unestablished": "unestablished"}, "versions": []}
    s = {"version": "state-records-v1", "records": [record], "fields": {
        name: {"record": "r", "kind": kind, "checkpoint": "e0" if kind == "at-checkpoint" else None}
        for name, kind in (("answer", "current"), ("status", "status"), ("values", "values"),
                           ("source", "provenance"), ("old", "at-checkpoint"))}, "probes": {}}
    original = values[0] if isinstance(values[0], str) else values[0][1]
    for i, entry in enumerate(values):
        event, probe = f"e{i}", f"p{i}"
        if isinstance(entry, str):
            status, value, claims, transition = "active", entry, [(event, entry)], "establish" if i == 0 else "change"
        else:
            status, value, claims, transition = entry
        next_event = f"e{i + 1}" if i + 1 < len(values) else "$trial_end"
        v = {"id": f"r{i + 1}", "number": i + 1, "previous": f"r{i}" if i else None,
             "next": f"r{i + 2}" if i + 1 < len(values) else None, "event": event,
             "transition": transition, "status": status, "value": value,
             "claims": [{"source": source, "authority": "synthetic equal authority", "value": claim}
                        for source, claim in claims], "valid_time": {"begin": "conversation checkpoint", "end": None},
             "applicability": "north site code", "obligations": []}
        for kind, end in (("current", next_event), ("historical", "$trial_end")):
            oid = f"r{i + 1}-{kind}"
            v["obligations"].append({"id": oid, "kind": kind, "begin_after": event, "end_before": end})
            m["obligations"][oid] = {"source": event, "begin_after": event, "end_before": end}
        record["versions"].append(v)
        m["nodes"][event] = user("Synthetic event " + event, probe)
        expected = {"answer": value if status == "active" else None, "status": status,
                    "values": [claim for _, claim in claims] if status == "unresolved" else
                              [value] if status == "active" else [],
                    "source": claims[0][0] if status == "active" else None, "old": original}
        m["nodes"][probe] = {"kind": "probe", "expected": expected, "unknown_answers": [], "set_fields": ["values"],
            "obligations": [ob["id"] for ob in v["obligations"]],
            "next": {outcome: next_event if next_event != "$trial_end" else "end" for outcome in OUTCOMES}}
        s["probes"][probe] = sorted(expected)
    return m, s


def reinstatement():
    return chain(("A", ("expired", None, [], "lapse"),
                  ("active", "A", [("e2", "A")], "reinstate")))


def disagreement():
    return chain(("A", ("unresolved", None, [("e0", "A"), ("e1", "B")], "change"),
                  ("active", "A", [("e0", "A")], "precedence")))


def scored_record(m):
    events = []
    node = m["start"]
    while m["nodes"][node]["kind"] != "terminal":
        value = m["nodes"][node]
        event = {"node": node, "kind": value["kind"]}
        if value["kind"] == "user":
            event["text"] = value["text"]
            target = value["next"]
        else:
            event.update(status="ok", answer=copy.deepcopy(value["expected"]))
            target = value["next"]["correct"]
        events.append(event)
        node = target
    return {"manifest_sha256": digest(m), "events": events}


class StateRecordTests(unittest.TestCase):
    def accept(self, m, s):
        result = validate_state_records(m, bind(m, s))
        self.assertEqual(result["status"], "validated")
        self.assertFalse(result["semantics_verified"])
        return result

    def reject(self, m, s, code):
        with self.assertRaises(IntakeError) as caught:
            validate_state_records(m, bind(m, s))
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.path)

    def test_valid_a_b_c_and_revisited_a(self):
        for values in (("A", "B", "C"), ("A", "B", "A")):
            self.accept(*chain(values))

    def test_lapse_and_new_version_reinstatement(self):
        self.accept(*chain(("A", ("expired", None, [], "lapse"))))
        self.accept(*reinstatement())

    def test_unresolved_then_precedence_and_set_order(self):
        m, s = disagreement()
        m["nodes"]["p1"]["expected"]["values"] = ["B", "A"]
        self.accept(m, s)

    def test_disagreement_can_accumulate_claims_without_resolving(self):
        m, s = chain(("A", ("unresolved", None, [("e0", "A"), ("e1", "B")], "change"),
                      ("unresolved", None, [("e0", "A"), ("e1", "B"), ("e2", "C")], "change")))
        self.accept(m, s)

    def test_future_checkpoint_and_cross_branch_sources_fail(self):
        m, s = chain()
        s["fields"]["old"]["checkpoint"] = "e2"
        self.reject(m, s, "event_order")
        m, s = chain()
        m["nodes"]["alternate"] = user("Synthetic alternate source", "e1")
        m["nodes"]["p0"]["next"]["incorrect"] = "alternate"
        s["records"][0]["versions"][1]["claims"][0]["source"] = "alternate"
        self.reject(m, s, "branch_inconsistent")

    def test_json_types_never_use_bool_integer_coercion(self):
        for field, value in (("number", True), ("value", True), ("value", 1.0)):
            m, s = chain()
            s["records"][0]["versions"][0][field] = value
            self.reject(m, s, "field_type")

    def test_escaped_surrogate_in_authority_is_not_portable_json(self):
        m, s = chain()
        s["records"][0]["versions"][0]["claims"][0]["authority"] = chr(0xD800)
        raw = json.dumps(s, ensure_ascii=True).encode("ascii")
        m["metadata"] = {"state_records": {"version": "state-records-v1", "sha256": sha(raw)}}
        with self.assertRaises(IntakeError) as error:
            validate_state_records(m, raw)
        self.assertEqual(error.exception.code, "invalid_json")

    def test_validator_does_not_mutate_frozen_inputs(self):
        m, s = chain()
        raw = bind(m, s)
        before = encode(m)
        validate_state_records(m, raw)
        self.assertEqual(encode(m), before)
        self.assertEqual(encode(s), raw)

    def test_scoped_partial_change_keeps_other_property(self):
        m, s = chain(("A", "B"))
        other = copy.deepcopy(s["records"][0])
        other.update(id="south-colour", property="colour", scope="south")
        other["versions"] = [other["versions"][0]]
        v = other["versions"][0]
        v.update(id="s1", previous=None, next=None, value="kept", applicability="south site colour")
        v["claims"][0]["value"] = "kept"
        v["obligations"] = []
        s["records"].append(other)
        s["fields"]["other"] = {"record": "south-colour", "kind": "current", "checkpoint": None}
        for probe, names in s["probes"].items():
            names.append("other")
            m["nodes"][probe]["expected"]["other"] = "kept"
        self.accept(m, s)

    def test_a_hash_binding_and_opt_out(self):
        m, s = chain()
        raw = bind(m, s)
        with self.assertRaises(IntakeError) as error:
            validate_state_records(m, raw + b" ")
        self.assertEqual(error.exception.code, "hash_mismatch")
        m.pop("metadata")
        self.assertEqual(validate_state_records(m, None)["status"], "not_opted_in")

    def test_b_unique_closed_required_and_strict_json(self):
        m, s = chain()
        s["records"][0]["versions"][1]["id"] = "r1"
        self.reject(m, s, "duplicate_id")
        m, s = chain()
        s["records"][0]["extra"] = True
        self.reject(m, s, "closed_fields")
        m, s = chain()
        s["records"][0].pop("scope")
        self.reject(m, s, "required_fields")
        m, _ = chain()
        raw = b'{"version":"state-records-v1","version":"state-records-v1"}'
        m["metadata"] = {"state_records": {"version": "state-records-v1", "sha256": sha(raw)}}
        with self.assertRaises(IntakeError) as error:
            validate_state_records(m, raw)
        self.assertEqual(error.exception.code, "invalid_json")

    def test_c_contiguous_resolving_acyclic_links(self):
        for update, code in (({"number": 4}, "version_chain"),
                             ({"previous": "absent"}, "chain_link_unresolved"),
                             ({"next": "r2"}, "version_chain")):
            m, s = chain()
            s["records"][0]["versions"][1].update(update)
            self.reject(m, s, code)

    def test_d_event_references_order_and_consistent_branches(self):
        for event, code in (("absent", "event_reference"), ("e0", "event_order")):
            m, s = chain()
            s["records"][0]["versions"][1]["event"] = event
            self.reject(m, s, code)
        m, s = chain()
        m["nodes"]["bypass"] = user("Synthetic alternate branch", "p1")
        m["nodes"]["p0"]["next"]["incorrect"] = "bypass"
        self.reject(m, s, "branch_inconsistent")

    def test_e_current_and_historical_boundary_correspondence(self):
        m, s = chain()
        m["obligations"]["r1-current"]["end_before"] = "$trial_end"
        self.reject(m, s, "obligation_boundary")
        m, s = chain()
        s["records"][0]["versions"][0]["obligations"][0]["id"] = "absent"
        self.reject(m, s, "obligation_reference")
        m, s = chain()
        hist = s["records"][0]["versions"][0]["obligations"][1]
        hist["end_before"] = "e2"
        m["obligations"][hist["id"]]["end_before"] = "e2"
        self.accept(m, s)  # Explicit historical expiration is allowed.

    def test_f_reinstatement_cannot_reuse_obligation(self):
        m, s = reinstatement()
        s["records"][0]["versions"][2]["obligations"][0]["id"] = "r1-current"
        self.reject(m, s, "reinstatement_not_fresh")

    def test_g_distinct_claim_sources_and_precedence_required(self):
        m, s = disagreement()
        s["records"][0]["versions"][1]["claims"][1]["source"] = "e0"
        self.reject(m, s, "disagreement_claims")
        m, s = disagreement()
        s["records"][0]["versions"][2]["transition"] = "change"
        self.reject(m, s, "unresolved_without_precedence")

    def test_h_expected_value_and_complete_set_correspondence(self):
        m, s = chain()
        m["nodes"]["p1"]["expected"]["answer"] = "A"
        self.reject(m, s, "answer_mismatch")
        m, s = disagreement()
        m["nodes"]["p1"]["expected"]["values"] = ["A"]
        self.reject(m, s, "answer_mismatch")
        m, s = chain()
        s["probes"]["p1"].remove("status")
        self.reject(m, s, "probe_fields")

    def test_missing_logical_field_is_declared_unavailable(self):
        m, s = chain()
        m["nodes"]["p1"]["expected"].pop("source")
        s["probes"]["p1"].remove("source")
        result = self.accept(m, s)
        self.assertEqual(result["unavailable_fields"], [{"probe": "p1", "field": "source"}])

    def test_intake_never_changes_scoring_or_replay_with_or_without_binding(self):
        for bound in (False, True):
            m, s = chain()
            raw = bind(m, s)
            if not bound:
                m.pop("metadata")
            record = scored_record(m)
            before = encode(json.loads(json.dumps(score(m, record), default=json_default)))
            validate_state_records(m, raw)
            after = encode(json.loads(json.dumps(score(m, record), default=json_default)))
            self.assertEqual(before, after)
            with tempfile.TemporaryDirectory() as temp:
                p, a = bundle(m, [response(encode(m["nodes"][probe]["expected"]))
                                  for probe in s["probes"]], slots=1)
                store = Store.create(Path(temp) / "replay.db", p, a)
                try:
                    run_offline(store, "slot-0")
                    for fmt in ("v1", "v2"):
                        exported = export_bundle(store, fmt)
                        with patch("etps_v02.intake.state_records.validate_state_records", side_effect=AssertionError("intake during replay")):
                            replayed = replay_export(exported)
                        replayed.pop("authoring_gate_reasserted")
                        replayed.pop("export_completeness_bound")
                        canonical = lambda v: json.dumps(v, sort_keys=True, default=json_default).encode()
                        self.assertEqual(canonical(replayed), canonical(exported["report"]))
                finally:
                    store.close()

    def test_software_bounds_and_cli_reason_code(self):
        m, s = chain()
        raw = bind(m, s)
        with patch("etps_v02.intake.state_records.MAX_NODES", 3), self.assertRaises(IntakeError) as error:
            validate_state_records(m, raw)
        self.assertEqual(error.exception.code, "safety_limit")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "manifest.json").write_bytes(encode(m))
            (root / "sidecar.json").write_bytes(raw + b" ")
            completed = subprocess.run([sys.executable, "-B", "-m", "etps_v02.intake.state_records",
                "--manifest", str(root / "manifest.json"), "--sidecar", str(root / "sidecar.json")],
                capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["code"], "hash_mismatch")
