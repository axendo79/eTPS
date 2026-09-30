"""Review regressions for field coverage; existing test files are unchanged."""
import unittest
from etps_v02.scorer import InvalidRecord, validate
from test_v02_field_routing import fields_manifest


class FieldCoverageReviewTests(unittest.TestCase):
    def test_every_tested_obligation_requires_a_field_link(self):
        m = fields_manifest()
        for links in m["nodes"]["p"]["field_obligations"].values():
            links.remove("both")
        with self.assertRaisesRegex(InvalidRecord, "cover all tested obligations"):
            validate(m)
        self.assertIn({"code": "field_obligations_incomplete", "node": "p"},
                      validate(m, authoring=False))

    def test_shared_obligation_is_covered_by_the_union(self):
        m = fields_manifest()
        m["nodes"]["p"]["field_obligations"]["a"].remove("both")
        self.assertEqual(validate(m), [])
