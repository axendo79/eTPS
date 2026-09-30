"""Synthetic field routing, with no private corpus content."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from etps_v02.scorer import InvalidRecord, classify, digest, route, score, validate
from etps_v02.runner import run_offline, export_bundle, replay_export
from etps_v02.persistence import Store
from etps_v02.workload import encode
from test_v02_scorer import fixture, user, probe, replay
from test_v02_runner import bundle, response


def fields_manifest():
    m = fixture()
    m.update(routing="field-v1", answer_schema="typed-v1")
    m["obligations"] = {o: {"source": "intro", "begin_after": "intro", "end_before": "$trial_end"}
                        for o in ("left", "right", "both")}
    m["nodes"] = {"intro": user("Synthetic fixture input", "p"),
                  "pass": {"kind": "terminal", "accepted": True},
                  "fail": {"kind": "terminal", "accepted": False}}
    p = probe({"a": 7, "b": "nine"}, "pass", "r-ab", ("left", "right", "both"))
    p["unknown_answers"] = []
    p["field_obligations"] = {"a": ["left", "both"], "b": ["right", "both"]}
    p["field_routes"] = [{"failed_fields": fs, "next": "r-" + "".join(fs)}
                         for fs in (["a"], ["b"], ["a", "b"])]
    m["nodes"]["p"] = p
    for fields in (["a"], ["b"], ["a", "b"]):
        obs = sorted({o for f in fields for o in p["field_obligations"][f]})
        m["nodes"]["r-" + "".join(fields)] = user("repair", "retry", [[0, 6, o] for o in obs], "p")
    m["nodes"]["retry"] = probe(p["expected"], "pass", "fail", p["obligations"])
    m["nodes"]["retry"]["unknown_answers"] = []
    return m


def trace(m, answer):
    events = [{"node": "intro", "kind": "user", "text": m["nodes"]["intro"]["text"]}]
    p = m["nodes"]["p"]
    event = {"node": "p", "kind": "probe", "status": "ok", "answer": answer}
    outcome = classify(event, p["expected"], [], m.get("answer_schema"))
    target, _ = route(m, p, event, outcome)
    events += [event, {"node": target, "kind": "user", "text": "repair"},
               {"node": "retry", "kind": "probe", "status": "ok", "answer": p["expected"]}]
    return {"manifest_sha256": digest(m), "events": events}


class FieldRoutingTests(unittest.TestCase):
    def test_every_subset_and_partial_retention(self):
        m = fields_manifest()
        self.assertEqual(validate(m), [])
        for answer, failed in (({"a": "7", "b": "nine"}, {"left", "both"}),
                               ({"a": 7, "b": "wrong"}, {"right", "both"}),
                               ({"a": 8, "b": "wrong"}, {"left", "right", "both"})):
            r = score(m, trace(m, answer))
            self.assertTrue(r["measurement_valid"])
            self.assertEqual(r["first_attempt"], {o: o not in failed for o in m["obligations"]})
            self.assertEqual(r["retention"], Fraction(3 - len(failed), 3))
            self.assertEqual(r["R"], 6)

    def test_missing_extra_keys_fallback_and_other_outcomes(self):
        m = fields_manifest()
        for answer in ({}, {"a": 7}, {"a": 7, "b": "nine", "extra": None}):
            r = score(m, trace(m, answer))
            self.assertTrue(r["measurement_valid"])
            self.assertFalse(any(r["first_attempt"].values()))
        for outcome in ("correct", "unknown", "malformed", "timeout"):
            self.assertEqual(route(m, m["nodes"]["p"], {}, outcome),
                             (m["nodes"]["p"]["next"][outcome], None))

    def test_nonfailed_obligation_recovery_is_unlinked(self):
        m = fields_manifest()
        m["nodes"]["r-a"]["spans"].append([0, 6, "right"])
        validate(m)
        r = score(m, trace(m, {"a": 8, "b": "nine"}))
        self.assertEqual(r["reason"], "unlinked_recovery")
        self.assertIsNone(r["RR"])

    def test_bad_routing_declarations(self):
        mutations = [lambda p: p["field_routes"].pop(),
                     lambda p: p["field_routes"].append(copy.deepcopy(p["field_routes"][0])),
                     lambda p: p["field_routes"][0].update(failed_fields=[]),
                     lambda p: p["field_routes"][2].update(failed_fields=["b", "a"]),
                     lambda p: p["field_routes"][0].update(next="absent"),
                     lambda p: p["field_obligations"].pop("a"),
                     lambda p: p["field_obligations"].update(a=["absent"]),
                     lambda p: p.pop("field_obligations")]
        for mutate in mutations:
            m = fields_manifest()
            mutate(m["nodes"]["p"])
            with self.assertRaises(InvalidRecord):
                validate(m)

    def test_route_edges_participate_in_cycle_and_v06_checks(self):
        m = fields_manifest()
        m["nodes"]["p"]["field_routes"][0]["next"] = "intro"
        with self.assertRaisesRegex(InvalidRecord, "cyclic"):
            validate(m)
        m = fields_manifest()
        m["nodes"]["r-a"]["failure"] = "retry"
        with self.assertRaisesRegex(InvalidRecord, "ancestor"):
            validate(m)
        m = fields_manifest()
        m["nodes"]["r-a"]["next"] = "r-ab"
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            validate(m)

    def test_opt_in_required_and_string_default_works(self):
        m = fields_manifest()
        del m["routing"]
        with self.assertRaisesRegex(InvalidRecord, "unrecognized"):
            validate(m)
        m = fields_manifest()
        del m["answer_schema"]
        m["nodes"]["p"]["expected"]["a"] = "seven"
        validate(m)
        self.assertTrue(score(m, trace(m, {"a": "wrong", "b": "nine"}))["accepted"])

    def test_legacy_score_unchanged(self):
        m = fixture()
        original = score(m, replay(m))
        m["routing"] = "field-v1"  # No probe opts into field routes.
        r = score(m, replay(m))
        r["manifest_sha256"] = original["manifest_sha256"]
        self.assertEqual(r, original)

    def test_runner_and_replay_routes_and_legacy_exports(self):
        for m, answers in ((fields_manifest(), [b'{"a":8,"b":"nine"}', b'{"a":7,"b":"nine"}']),
                           (fixture(), [b'{"database":"SQLite"}'])):
            with tempfile.TemporaryDirectory() as temp:
                plan, artifacts = bundle(manifest=m, responses=[response(a) for a in answers], slots=1)
                store = Store.create(Path(temp) / "test.db", plan, artifacts)
                try:
                    result = run_offline(store, "slot-0")
                    self.assertTrue(result["score"]["accepted"])
                    for fmt in ("v1", "v2"):
                        replayed = replay_export(export_bundle(store, format=fmt), validate_authoring=True)
                        self.assertEqual(replayed["trials"][0], result)
                finally:
                    store.close()
