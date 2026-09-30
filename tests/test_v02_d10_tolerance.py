"""Synthetic D10 rules and raw-byte replay; no private corpus text."""
from pathlib import Path
import tempfile
import unittest

from etps_v02.answer_tolerance import evaluate
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report, run_offline
from etps_v02.scorer import InvalidRecord, classify_probe, digest, route, score, validate
from etps_v02.workload import encode
from test_v02_field_routing import fields_manifest
from test_v02_runner import bundle, response
from test_v02_typed_answers import typed


def manifest():
    m = typed({"v": 42, "label": "Ready"})
    m["answer_tolerance"] = "d10-v1"
    for name in ("p1", "p2"):
        m["nodes"][name].update(key_aliases={"v": ["value", "number"]}, fixed_value_fields=["label"])
    return m


class D10Tests(unittest.TestCase):
    def check(self, answer, outcome="correct", mode="format_deviation", rules=None):
        m = manifest()
        actual = evaluate(m, m["nodes"]["p1"], {"status": "ok", "answer": answer})
        self.assertEqual(actual, (outcome, mode, rules or []))

    def test_each_rule_and_combination(self):
        self.check({"v": 42, "label": "Ready"}, mode="exact")
        self.check({"value": 42, "label": "Ready"}, rules=["key_aliases"])
        self.check({"v": "0042", "label": "Ready"}, rules=["digit_string_to_int"])
        self.check({"v": 42, "label": "\tREADY\r\n"}, rules=["fixed_value_fields"])
        self.check({"value": "42", "label": " ready "},
                   rules=["key_aliases", "digit_string_to_int", "fixed_value_fields"])

    def test_integer_spellings_and_type_boundaries(self):
        for value in ("+42", " 42", "42 ", "4.0", "-1", "٤٢", "42\n"):
            self.check({"v": value, "label": "Ready"}, "incorrect", None)
        for value in (True, 42.0, [], {}):
            self.check({"v": value, "label": "Ready"}, "malformed", None)
        self.check({"v": "0" * 5000 + "42", "label": "Ready"}, rules=["digit_string_to_int"])

    def test_collisions_extra_missing_and_unknown(self):
        for answer in ({"v": 42, "value": 42, "label": "Ready"},
                       {"value": 42, "number": 42, "label": "Ready"},
                       {"value": 42}, {"value": 42, "label": "Ready", "extra": "x"}):
            self.check(answer, "incorrect", None)
        m = manifest()
        p = m["nodes"]["p1"]
        p["unknown_answers"] = [{"status": "unknown"}, {"v": "42", "label": "Ready"}]
        self.assertEqual(evaluate(m, p, {"status": "ok", "answer": {"status": "unknown"}})[0], "unknown")
        self.assertEqual(evaluate(m, p, {"status": "ok", "answer": p["unknown_answers"][1]})[0], "correct")
        self.assertEqual(evaluate(m, p, {"status": "timeout", "answer": p["expected"]}), ("timeout", None, []))

    def test_only_declared_fields_and_ascii_whitespace(self):
        m = manifest()
        p = m["nodes"]["p1"]
        p["fixed_value_fields"] = []
        self.assertEqual(evaluate(m, p, {"status": "ok", "answer": {"v": 42, "label": "ready"}})[0], "incorrect")
        self.check({"v": 42, "label": "\u00a0READY\u00a0"}, "incorrect", None)
        p["expected"] = {"v": "42"}
        self.assertEqual(evaluate(m, p, {"status": "ok", "answer": {"v": 42}})[0], "incorrect")

    def test_invalid_declarations(self):
        for updates in ({"key_aliases": {"v": ["label"]}}, {"key_aliases": {"v": ["a"], "label": ["a"]}},
                        {"key_aliases": {"v": ["a", "a"]}}, {"key_aliases": {"missing": ["a"]}},
                        {"key_aliases": {"v": "a"}}, {"fixed_value_fields": ["v"]},
                        {"fixed_value_fields": ["label", "label"]}, {"fixed_value_fields": ["missing"]}):
            m = manifest()
            m["nodes"]["p1"].update(updates)
            with self.subTest(updates=updates), self.assertRaises(InvalidRecord):
                validate(m)
        m = manifest()
        del m["answer_tolerance"]
        with self.assertRaises(InvalidRecord):
            validate(m)
        m = manifest()
        m["answer_tolerance"] = "d10-v2"
        with self.assertRaises(InvalidRecord):
            validate(m)

    def test_field_routing_after_normalization(self):
        m = fields_manifest()
        m["answer_tolerance"] = "d10-v1"
        p = m["nodes"]["p"]
        p.update(key_aliases={"a": ["alpha"]}, fixed_value_fields=["b"])
        e = {"status": "ok", "answer": {"alpha": "7", "b": "wrong"}}
        self.assertEqual(route(m, p, e, classify_probe(m, p, e)), ("r-b", ["b"]))
        events = [{"node": "intro", "kind": "user", "text": m["nodes"]["intro"]["text"]},
                  {"node": "p", "kind": "probe", **e},
                  {"node": "r-b", "kind": "user", "text": "repair"},
                  {"node": "retry", "kind": "probe", "status": "ok", "answer": p["expected"]}]
        r = score(m, {"manifest_sha256": digest(m), "events": events})
        self.assertTrue(r["first_attempt"]["left"])
        self.assertFalse(r["first_attempt"]["right"])
        self.assertEqual(r["R"], 6)
        self.assertEqual(r["result_state"], "accepted_exact")  # Only correct probes set the state.

    def test_offline_states_retention_reports_and_replay(self):
        for answers, state in (([{"v": 42, "label": "Ready"}], "accepted_exact"),
                               ([{"value": "42", "label": " READY "}], "accepted_with_format_deviation"),
                               ([{"v": 0}, {"v": 0}], "failed")):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temp:
                p, a = bundle(manifest(), [response(encode(v)) for v in answers], slots=1)
                store = Store.create(Path(temp) / "test.db", p, a)
                try:
                    trial = run_offline(store, "slot-0")
                    self.assertEqual(trial["score"]["result_state"], state)
                    if state != "failed":
                        self.assertEqual(trial["score"]["retention"], 1)
                    r = report(store)["answer_tolerance"]["baseline"]
                    self.assertEqual(r["format_compliance_rate"], {"numerator": int(state == "accepted_exact"),
                                                                  "denominator": int(state != "failed")})
                    exported = export_bundle(store, "v2")
                    exported["report"] = {"forged_modes_and_rules": True}
                    self.assertEqual(replay_export(exported)["trials"][0], trial)
                finally:
                    store.close()

    def test_legacy_no_added_fields(self):
        m = typed({"v": 42})
        self.assertEqual(classify_probe(m, m["nodes"]["p1"], {"status": "ok", "answer": {"v": "42"}}), "incorrect")
        with tempfile.TemporaryDirectory() as temp:
            p, a = bundle(m, [response(b'{"v":42}')], slots=1)
            store = Store.create(Path(temp) / "test.db", p, a)
            try:
                r = run_offline(store, "slot-0")["score"]
                self.assertNotIn("result_state", r)
                self.assertFalse(any("mode" in c for c in r["classifications"]))
                self.assertNotIn("answer_tolerance", report(store))
            finally:
                store.close()
