"""R1: SYNTHETIC admission failures and exact answerability forms."""
from pathlib import Path
import unittest

from authoring_rulings_fixtures import synthetic_disallowed_forms, synthetic_missing_unit
from etps_v02.intake.authoring import AuthoringError, validate_authoring
from etps_v02.workload import encode


class AuthoringRulingsTests(unittest.TestCase):
    def test_rules_1_to_3_refuse_at_authoring_stage(self):
        for doc, code in synthetic_disallowed_forms():
            with self.subTest(code=code):
                with self.assertRaises(AuthoringError) as caught:
                    validate_authoring(encode(doc))
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(caught.exception.path.startswith("source.tasks"))

    def test_exact_missing_unit_status_and_optional_identifier(self):
        doc = synthetic_missing_unit()
        self.assertEqual(validate_authoring(encode(doc)), doc)
        del doc["tasks"][0]["probes"][0]["field_map"]["missing_item"]
        del doc["tasks"][0]["probes"][0]["expected"]["missing_item"]
        self.assertEqual(validate_authoring(encode(doc)), doc)

    def test_open_ended_wrong_status_identifier_or_unpaired_identifier_refuse(self):
        cases = [(lambda p: p["expected"].update(status="SYNTHETIC please clarify")),
                 (lambda p: p["expected"].update(missing_item="SYNTHETIC-other")),
                 (lambda p: (p["field_map"].pop("status"), p["expected"].pop("status")))]
        for change in cases:
            doc = synthetic_missing_unit()
            change(doc["tasks"][0]["probes"][0])
            with self.assertRaises(AuthoringError) as caught:
                validate_authoring(encode(doc))
            self.assertEqual(caught.exception.code, "missing_information_answer")

    def test_new_query_is_closed_and_missing_item_must_be_declared(self):
        for change, code in ((lambda q: q.update(checkpoint=None), "closed_fields"),
                             (lambda q: q.update(missing_item="SYNTHETIC-absent-record"), "reference")):
            doc = synthetic_missing_unit()
            change(doc["tasks"][0]["field_map"]["status"])
            with self.assertRaises(AuthoringError) as caught:
                validate_authoring(encode(doc))
            self.assertEqual(caught.exception.code, code)

    def test_brief_states_rules_neutrally(self):
        text = (Path(__file__).resolve().parents[1] / "docs/v0.2/AUTHORING_BRIEF.md").read_text(encoding="utf-8")
        for phrase in ("begins at its establishing message", "exactly one failed question",
                       "one fixed answer object", "missing_information", "no open-ended clarification"):
            self.assertIn(phrase, text)
