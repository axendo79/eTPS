"""Synthetic complete-set answers; no corpus tasks or model calls."""
import copy
import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.persistence import Store
from etps_v02.runner import answer_from_raw, export_bundle, replay_export, report, run_offline
from etps_v02.scorer import InvalidRecord, classify_probe, route, validate
from etps_v02.workload import encode
from test_v02_runner import bundle, response
from test_v02_typed_answers import typed


def set_manifest(expected=None):
    m = typed({"values": ["alpha", 7, None], "code": 42} if expected is None else expected)
    m["answer_predicate"] = "set-v1"
    for name in ("p1", "p2"):
        m["nodes"][name]["set_fields"] = ["values"]
    return m


class CompleteSetTests(unittest.TestCase):
    def outcome(self, m, answer, status="ok"):
        return classify_probe(m, m["nodes"]["p1"], {"status": status, "answer": answer})

    def test_complete_set_order_and_strict_element_types(self):
        m = set_manifest()
        validate(m)
        self.assertEqual(self.outcome(m, {"values": [None, 7, "alpha"], "code": 42}), "correct")
        for values in (["alpha", "7", None], ["alpha", 7], ["alpha", 7, None, "extra"],
                       ["alpha", 7, None, 7], ["Alpha", 7, None]):
            with self.subTest(values=values):
                self.assertEqual(self.outcome(m, {"values": values, "code": 42}), "incorrect")

    def test_empty_set_and_typed_distinct_elements(self):
        for values in ([], [0, "0", None, "null"]):
            m = set_manifest({"values": values})
            validate(m)
            self.assertEqual(self.outcome(m, {"values": list(reversed(values))}), "correct")
            self.assertEqual(self.outcome(m, {"values": values + ["extra"]}), "incorrect")

    def test_array_schema_transport_and_extra_claims(self):
        m = set_manifest()
        for values in (None, 7, "alpha", {}, [True], [7.0], [[]], [{}]):
            with self.subTest(values=values):
                self.assertEqual(self.outcome(m, {"values": values, "code": 42}), "malformed")
        self.assertEqual(self.outcome(m, None, "timeout"), "timeout")
        self.assertEqual(self.outcome(m, {"code": 42}), "incorrect")
        self.assertEqual(self.outcome(m, {**m["nodes"]["p1"]["expected"], "extra": "x"}), "incorrect")
        self.assertEqual(self.outcome(m, {"values": [], "code": []}), "malformed")

    def test_projection_is_manifest_designated_and_preserves_bytes(self):
        raw = b'{"values":[null,7,"alpha"],"code":42}'
        self.assertIsNone(answer_from_raw(raw, "typed-v1"))
        self.assertEqual(answer_from_raw(raw, "typed-v1", set_fields=["values"]),
                         {"values": [None, 7, "alpha"], "code": 42})
        for raw in (b'{"values":[true]}', b'{"values":[1.0]}', b'{"values":[{}]}',
                    b'{"values":["\\ud800"]}', b'{"values":[],"values":[]}', b'{"extra":[]}'):
            with self.subTest(raw=raw):
                self.assertIsNone(answer_from_raw(raw, "typed-v1", set_fields=["values"]))

    def test_invalid_manifest_designations(self):
        for fields, values in ((["missing"], []), (["values"], "x"), (["values"], [7, 7]),
                               (["values"], [None, None]), (["values"], [True]),
                               (["values", "values"], []), ("values", []), ([[]], [])):
            m = set_manifest({"values": values})
            m["nodes"]["p1"]["set_fields"] = fields
            with self.subTest(fields=fields, values=values), self.assertRaises(InvalidRecord):
                validate(m)
        for mutation in (lambda m: m.pop("answer_predicate"),
                         lambda m: m.update(answer_predicate="set-v2"),
                         lambda m: m.pop("answer_schema")):
            m = set_manifest()
            mutation(m)
            with self.assertRaises(InvalidRecord):
                validate(m)

    def test_unknowns_and_order_insensitive_correct_overlap(self):
        m = set_manifest()
        m["nodes"]["p1"]["unknown_answers"] = [{"status": "unknown"}]
        validate(m)
        self.assertEqual(self.outcome(m, {"status": "unknown"}), "unknown")
        m["nodes"]["p1"]["unknown_answers"] = [{"values": [None, 7, "alpha"], "code": 42}]
        with self.assertRaisesRegex(InvalidRecord, "overlap"):
            validate(m)

    def test_d10_scalars_and_key_aliases_never_normalize_set_elements(self):
        m = set_manifest()
        m["answer_tolerance"] = "d10-v1"
        for name in ("p1", "p2"):
            m["nodes"][name]["key_aliases"] = {"code": ["number"], "values": ["choices"]}
        validate(m)
        self.assertEqual(self.outcome(m, {"choices": [7, None, "alpha"], "number": "0042"}), "correct")
        self.assertEqual(self.outcome(m, {"values": ["7", None, "alpha"], "code": "42"}), "incorrect")
        self.assertEqual(self.outcome(m, {"values": [7, None, "ALPHA"], "code": 42}), "incorrect")
        self.assertEqual(self.outcome(m, {"values": [], "choices": [], "code": 42}), "incorrect")
        m["nodes"]["p1"]["fixed_value_fields"] = ["values"]
        with self.assertRaises(InvalidRecord):
            validate(m)

    def test_field_routing_uses_complete_set_equality(self):
        m = set_manifest()
        m["routing"] = "field-v1"
        p = m["nodes"]["p1"]
        p["field_obligations"] = {"code": [], "values": ["db"]}
        p["field_routes"] = [{"failed_fields": fields, "next": "recover"}
                             for fields in (["code"], ["values"], ["code", "values"])]
        validate(m)
        for answer, fields in (({"values": [7, None, "alpha"], "code": 0}, ["code"]),
                               ({"values": [7, None], "code": 42}, ["values"]),
                               ({"values": [7, 7, None, "alpha"], "code": 0}, ["code", "values"])):
            event = {"status": "ok", "answer": answer}
            self.assertEqual(route(m, p, event, classify_probe(m, p, event)), ("recover", fields))

    def test_offline_roundtrip_recovery_and_d10_modes(self):
        m = set_manifest()
        m["answer_tolerance"] = "d10-v1"
        answers = [{"values": [7], "code": 42}, {"values": [7, None, "alpha"], "code": "42"}]
        with tempfile.TemporaryDirectory() as temp:
            plan, artifacts = bundle(m, [response(encode(a)) for a in answers], slots=1)
            before = copy.deepcopy(artifacts)
            store = Store.create(Path(temp) / "set.db", plan, artifacts)
            try:
                trial = run_offline(store, "slot-0")
                self.assertTrue(trial["score"]["accepted"])
                self.assertEqual(trial["score"]["retention"], 0)
                self.assertEqual(trial["score"]["result_state"], "accepted_with_format_deviation")
                self.assertEqual(trial["score"]["classifications"][-1]["rules_applied"], ["digit_string_to_int"])
                self.assertEqual(store.artifacts, before)
                for fmt in ("v1", "v2"):
                    exported = export_bundle(store, fmt)
                    exported["report"] = {"forged": True}
                    self.assertEqual(replay_export(exported)["trials"][0], trial)
                self.assertNotIn("dimension_accuracy", report(store))
            finally:
                store.close()

    def test_fence_projection_of_sets(self):
        from etps_v02.response_extraction import project_reply
        raw = b'```json\n{"values":[7,"alpha",null],"code":42}\n```'
        self.assertEqual(project_reply(raw, "typed-v1", "fence-v1", set_fields=["values"]),
                         ({"values": [7, "alpha", None], "code": 42}, True))
        self.assertEqual(project_reply(raw, "typed-v1", "fence-v1"), (None, True))

    def test_scripted_manual_projection_and_replay(self):
        from etps_v02.manual_runner import run_manual
        from test_v02_manual_dev import manual_bundle, paste
        m = set_manifest()
        plan, artifacts = manual_bundle(m)
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "manual.db", encode(plan), artifacts)
            try:
                with patch("etps_v02.adapter_openai.send", side_effect=AssertionError("network")):
                    trial = run_manual(store, "slot", allow_manual=True,
                        stdin=io.BytesIO(paste(b'{"values":[null,7,"alpha"],"code":42}')),
                        stdout=io.StringIO())
                self.assertTrue(trial["score"]["accepted"])
                replayed = replay_export(export_bundle(store))
                self.assertEqual(replayed["dev_manual"]["trials"][0], trial)
            finally:
                store.close()

    def test_mocked_live_projection_and_evidence_replay(self):
        from etps_v02.adapter_openai import envelope
        from etps_v02.live_runner import run_live
        from etps_v02.workload import sha
        from test_v02_live_adapter import bundle as live_bundle
        m = set_manifest()
        plan, _ = live_bundle("http://127.0.0.1:1")
        raw_manifest = encode(m)
        plan["tasks"] = {"synthetic-task": sha(raw_manifest)}
        body = encode({"choices": [{"message": {"role": "assistant",
                       "content": '{"values":[7,null,"alpha"],"code":42}'}}]})
        event = {**envelope("openai-compatible", 200, body), "http_status": 200,
                 "http_body_base64": base64.b64encode(body).decode(), "http_body_sha256": sha(body),
                 "client_latency_seconds": 0.001}
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "live.db", encode(plan), {sha(raw_manifest): raw_manifest})
            try:
                with patch("etps_v02.adapter_openai.preflight"), patch("etps_v02.adapter_openai.send", return_value=event):
                    trial = run_live(store, "slot", allow_live=True)
                self.assertTrue(trial["score"]["accepted"])
                self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)
            finally:
                store.close()
