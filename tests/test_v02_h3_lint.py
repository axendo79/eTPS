"""Fail-before regressions for SYNTHETIC compressed H3 field wording."""
import unittest

from authoring_fixtures import synthetic_document
from authoring_rulings_fixtures import synthetic_missing_unit
from etps_v02.intake.authoring_lint import lint_authoring, missing_answer_forms
from etps_v02.workload import encode


class H3LintTests(unittest.TestCase):
    def forms(self, wording, value, *, kind="current", field="answer", is_set=False):
        query = {"kind": kind}
        probe = {"expected": {field: value}, "set_fields": [field] if is_set else [],
                 "wording": wording, "field_map": {field: query}}
        record = {"status_labels": {s: s for s in ("active", "expired", "unestablished", "unresolved")}}
        return missing_answer_forms(probe, field, query, record)

    def test_exact_json_string_and_json_integer(self):
        for value, wording in (("SYNTHETIC", "answer: one value in force now, as an exact JSON string"),
                               (7, "answer: one value in force now, as a JSON integer")):
            with self.subTest(value=value):
                self.assertEqual(self.forms(wording, value), [])

    def test_use_only_canonical_statuses(self):
        wording = ('For status about SYNTHETIC property now, use only "active" (one value in force), '
                   '"expired", "unestablished", or "unresolved". Settled value: "active", never "resolved".')
        self.assertEqual(self.forms(wording, "active", kind="status", field="status"), [])

    def test_adopted_null_and_bare_id_wording(self):
        for wording, value, kind, field in (
            ("answer: one value in force now, as an exact JSON string; JSON null if expired, unestablished, or unresolved (no unique value).", None, "current", "answer"),
            ("source: exact public source-claim message ID for the unique active value, as a JSON string, no brackets/descriptions. After precedence, identify the selected claim, not the later decision. JSON null without a unique active claim.", None, "provenance", "source"),
            ("source: exact public source-claim message ID for the unique active value, as a JSON string, no brackets/descriptions.", "SYNTHETIC-m0", "provenance", "source"),
            ("values: complete unordered JSON array of values in force now; singleton if active/settled, all distinct competing values if unresolved, [] if expired/unestablished. Members: an exact JSON string, preserving case, spelling, punctuation, and spacing. No duplicates or superseded alternatives.", [], "values", "values")):
            with self.subTest(field=field, value=value):
                self.assertEqual(self.forms(wording, value, kind=kind, field=field, is_set=kind == "values"), [])

    def test_designated_missing_information_does_not_need_ordinary_labels(self):
        doc = synthetic_missing_unit()
        doc["tasks"][0]["probes"][0]["wording"] = (
            '[SYNTHETIC-p0] For "status", use "missing_information" only when required item SYNTHETIC-unit '
            'was never supplied before this question, not for disagreement. Changed, disputed, withdrawn, '
            'forgotten, or context-omitted information previously supplied is ineligible. '
            'missing_item: exact declared item ID as a JSON string, no brackets/additions.')
        findings = lint_authoring(encode(doc))["findings"]
        self.assertEqual([r for r in findings if r["code"] in ("status_vocabulary_missing", "answer_form_missing")], [])

    def test_unstated_forms_still_report_and_other_field_cannot_supply_them(self):
        self.assertIn("number", self.forms("answer: give the value. other: a JSON integer.", 7))
        self.assertIn("null_when_none", self.forms("answer: use null. other: JSON null if expired.", None))
        self.assertIn("bare_id", self.forms("source: message ID as a JSON string.", "SYNTHETIC-m0", kind="provenance", field="source"))
        doc = synthetic_document(("SYNTHETIC_A",))
        doc["tasks"][0]["probes"][0]["wording"] = '[SYNTHETIC-p0] status: use only active expired unresolved.'
        rows = lint_authoring(encode(doc))["findings"]
        self.assertTrue(any(r["code"] == "status_vocabulary_missing" and "unestablished" in r["missing_labels"] for r in rows))


if __name__ == "__main__":
    unittest.main()
