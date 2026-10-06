"""Synthetic declaration/runtime agreement for d10 aliases of set fields."""
import unittest

from etps_v02.scorer import InvalidRecord, classify_probe, validate
from test_v02_set_answers import set_manifest
from test_v02_d10_tolerance import manifest as scalar_manifest


def aliases():
    m = set_manifest()
    m["answer_tolerance"] = "d10-v1"
    for node in m["nodes"].values():
        if node["kind"] == "probe":
            node["key_aliases"] = {"values": ["choices"]}
    return m


class SetUnknownTypingTests(unittest.TestCase):
    def test_scalar_alias_unknown_is_rejected_as_malformed_shape(self):
        m = aliases()
        m["nodes"]["p1"]["unknown_answers"] = [{"choices": "unknown"}]
        with self.assertRaises(InvalidRecord):
            validate(m)
        self.assertEqual(classify_probe(m, m["nodes"]["p1"],
            {"status": "ok", "answer": {"choices": "unknown"}}), "malformed")

    def test_array_alias_unknown_is_admitted_and_classified_unknown(self):
        m = aliases()
        m["nodes"]["p1"]["unknown_answers"] = [{"choices": ["unknown"]}]
        validate(m)
        self.assertEqual(classify_probe(m, m["nodes"]["p1"],
            {"status": "ok", "answer": {"choices": ["unknown"]}}), "unknown")

    def test_canonical_and_alias_elements_have_identical_type_rules(self):
        for key in ("values", "choices"):
            for value in ([True], [1.0], [{}], [[]], None):
                m = aliases()
                m["nodes"]["p1"]["unknown_answers"] = [{key: value}]
                with self.subTest(key=key, value=value), self.assertRaises(InvalidRecord):
                    validate(m)

    def test_non_set_d10_declarations_remain_scalar_only(self):
        m = scalar_manifest()
        p = m["nodes"]["p1"]
        p["unknown_answers"] = [{"value": "unknown"}]
        validate(m)
        self.assertEqual(classify_probe(m, p, {"status": "ok", "answer": {"value": "unknown"}}), "unknown")
        p["unknown_answers"] = [{"value": ["unknown"]}]
        with self.assertRaises(InvalidRecord):
            validate(m)
