"""Synthetic status/value separation, including field-specific recovery."""
import unittest

from etps_v02.scorer import classify_probe, digest, route, score, validate
from test_v02_scorer import user
from test_v02_set_answers import set_manifest


def ambiguity_manifest():
    m = set_manifest({"status": "unresolved", "values": ["alpha", "beta"]})
    m["routing"] = "field-v1"
    m["obligations"] = {key: {"source": "intro", "begin_after": "intro", "end_before": "$trial_end"}
                        for key in ("status", "values")}
    p = m["nodes"]["p1"]
    p["obligations"] = ["status", "values"]
    p["field_obligations"] = {key: [key] for key in ("status", "values")}
    p["next"] = {outcome: "pass" if outcome == "correct" else "r-both" for outcome in p["next"]}
    p["field_routes"] = [{"failed_fields": fields, "next": name} for fields, name in
                         ((["status"], "r-status"), (["values"], "r-values"), (["status", "values"], "r-both"))]
    del m["nodes"]["recover"]
    for name, fields in (("r-status", ["status"]), ("r-values", ["values"]), ("r-both", ["status", "values"])):
        m["nodes"][name] = user("repair", "p2", [[0, 6, key] for key in fields], "p1")
    m["nodes"]["p2"]["obligations"] = ["status", "values"]
    return m


def trace(m, answers):
    events, current, index = [], m["start"], 0
    while m["nodes"][current]["kind"] != "terminal":
        node = m["nodes"][current]
        event = {"node": current, "kind": node["kind"]}
        if node["kind"] == "user":
            event["text"] = node["text"]
            target = node["next"]
        else:
            event.update(status="ok", answer=answers[index], generation={"tokens": 10, "seconds": 1})
            index += 1
            target, _ = route(m, node, event, classify_probe(m, node, event))
        events.append(event)
        current = target
    return {"manifest_sha256": digest(m), "events": events}


class AmbiguitySetTests(unittest.TestCase):
    def test_status_and_values_are_independent_failed_fields(self):
        m = ambiguity_manifest()
        validate(m)
        expected = m["nodes"]["p1"]["expected"]
        for answer, first in (({"status": "resolved", "values": ["beta", "alpha"]},
                               {"status": False, "values": True}),
                              ({"status": "unresolved", "values": ["alpha"]},
                               {"status": True, "values": False}),
                              ({"status": "resolved", "values": ["alpha"]},
                               {"status": False, "values": False})):
            with self.subTest(answer=answer):
                result = score(m, trace(m, [answer, expected]))
                self.assertEqual(result["first_attempt"], first)
                self.assertEqual(result["R"], 6)  # Overlapping spans count once.
                self.assertTrue(result["accepted"])

    def test_exact_status_and_order_insensitive_values(self):
        m = ambiguity_manifest()
        result = score(m, trace(m, [{"status": "unresolved", "values": ["beta", "alpha"]}]))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["first_attempt"], {"status": True, "values": True})
        self.assertEqual(result["R"], 0)
        for status in ("Unresolved", " unresolved "):
            event = {"status": "ok", "answer": {"status": status, "values": ["alpha", "beta"]}}
            self.assertEqual(route(m, m["nodes"]["p1"], event, classify_probe(m, m["nodes"]["p1"], event)),
                             ("r-status", ["status"]))

    def test_complete_value_set_required_at_terminal(self):
        m = ambiguity_manifest()
        for values in (["alpha"], ["alpha", "beta", "gamma"], ["alpha", "beta", "alpha"]):
            answer = {"status": "unresolved", "values": values}
            result = score(m, trace(m, [answer, answer]))
            self.assertFalse(result["accepted"])
            self.assertIsNone(result["experimental_eTPS"])
