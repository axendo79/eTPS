"""SYNTHETIC factual advisory lint regressions; no quality/difficulty judge."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document, synthetic_recovery
from authoring_rulings_fixtures import synthetic_missing_unit
from review_tools_fixtures import synthetic_review_document, synthetic_two_task_document
from etps_v02.intake import authoring_lint
from etps_v02.workload import encode, sha


class AuthoringLintTests(unittest.TestCase):
    def findings(self, doc, code, **options):
        return [f for f in authoring_lint.lint_authoring(encode(doc), **options)["findings"] if f["code"] == code]

    def test_status_vocabulary_uses_record_labels_and_missing_information(self):
        doc = synthetic_review_document()
        self.assertEqual(self.findings(doc, "status_vocabulary_missing"), [])
        record = doc["tasks"][0]["state_history"][0]
        record["status_labels"]["active"] = "SYNTHETIC usable"
        rows = self.findings(doc, "status_vocabulary_missing")
        self.assertEqual(rows[0]["missing_labels"], ["SYNTHETIC usable"])
        self.assertEqual(rows[0]["probe_id"], "SYNTHETIC-p0")
        missing = synthetic_missing_unit()
        self.assertIn("missing_information", self.findings(missing, "status_vocabulary_missing")[0]["missing_labels"])
        missing["tasks"][0]["probes"][0]["wording"] += " active expired unresolved unestablished missing_information"
        self.assertEqual(self.findings(missing, "status_vocabulary_missing"), [])

    def test_normalized_restated_scalar_and_window_counts_with_source_exemption(self):
        doc = synthetic_review_document(giveaways=True)
        original = copy.deepcopy(doc)
        rows = self.findings(doc, "answer_restated_before_probe")
        self.assertEqual({f["field"] for f in rows}, {"answer", "old", "values"})
        self.assertTrue(all(f["message_id"] == "SYNTHETIC-m3" for f in rows))
        self.assertIn("sYnThEtIc_ kEy", rows[0]["evidence"])
        self.assertEqual(self.findings(doc, "answer_restated_before_probe", window=1), [])
        self.assertEqual(self.findings(doc, "answer_restated_before_probe", window=0), [])
        counts = self.findings(doc, "key_restatement_window_counts")[0]
        self.assertEqual(counts["restatement_hits"], 3)
        self.assertEqual(counts["window_message_ids"], ["SYNTHETIC-m3", "SYNTHETIC-m4"])
        task = doc["tasks"][0]
        task["probes"][0]["position"] = "SYNTHETIC-m0"
        hits = self.findings(doc, "answer_restated_before_probe")
        self.assertEqual({f["field"] for f in hits}, {"source"})
        self.assertEqual(original["tasks"][0]["conversation"], doc["tasks"][0]["conversation"])

    def test_set_members_and_provenance_ids_are_individually_reported(self):
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        task["probes"][0]["expected"]["values"] = ["SYNTHETIC_RED", "SYNTHETIC_BLUE"]
        task["conversation"][4]["text"] += " SYNTHETIC_RED SYNTHETIC_BLUE SYNTHETIC-m0"
        rows = self.findings(doc, "answer_restated_before_probe")
        self.assertEqual({f["expected_value"] for f in rows}, {"SYNTHETIC_RED", "SYNTHETIC_BLUE", "SYNTHETIC-m0"})

    def test_annotation_words_have_boundaries_and_configurable_phrases(self):
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        task["conversation"][1]["text"] += " inactive actively unresolvedness"
        self.assertEqual(self.findings(doc, "status_word_leak"), [])
        task["conversation"][1]["text"] += " ACTIVE; expires here; new active version; fresh version; status label"
        rows = self.findings(doc, "status_word_leak")
        self.assertEqual({r["matched"] for r in rows}, {"active", "expires here", "new active version", "fresh version", "status label"})
        task["conversation"][2]["text"] += " SYNTHETIC bespoke cue"
        rows = self.findings(doc, "status_word_leak", status_phrases=["SYNTHETIC bespoke cue"])
        self.assertIn("SYNTHETIC bespoke cue", {r["matched"] for r in rows})
        self.assertNotIn("fresh version", {r["matched"] for r in rows})

    def test_question_references_are_factual_including_key_messages(self):
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        for i, phrase in enumerate(("the question that follows", "the next question", "the following question")):
            task["conversation"][i]["text"] += " " + phrase
        rows = self.findings(doc, "question_reference_in_filler")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["evidence"] for r in rows))

    def test_prefix_patterns_within_tasks_and_across_document(self):
        doc = synthetic_two_task_document()
        self.assertEqual(self.findings(doc, "id_style_mixed"), [])
        doc["tasks"][1]["id"] = "DIFFERENT-task"
        rows = self.findings(doc, "id_style_mixed")
        self.assertTrue(any(r["scope"] == "document" for r in rows))
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        task["state_history"][0]["id"] = "DIFFERENT-record"
        for query in task["field_map"].values():
            query["record"] = "DIFFERENT-record"
        task["probes"][0]["field_map"] = copy.deepcopy(task["field_map"])
        rows = self.findings(doc, "id_style_mixed")
        self.assertTrue(any(r["record_id"] == "DIFFERENT-record" for r in rows))

    def test_evidence_positions_count_characters_and_sources_not_utf8_bytes(self):
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        total = sum(len(m["text"]) for m in task["conversation"])
        rows = self.findings(doc, "evidence_position")
        self.assertEqual({r["field"] for r in rows}, set(task["field_map"]))
        answer = next(r for r in rows if r["field"] == "answer")
        self.assertEqual(answer["total_characters"], total)
        self.assertEqual(answer["sources"][0]["start_fraction"], 0)
        self.assertEqual(answer["sources"][0]["characters_to_probe"], total)
        self.assertEqual(answer["sources"][0]["message_id"], "SYNTHETIC-m0")
        task["coverage_tags"]["context_pressure"] = "within"
        self.assertEqual(self.findings(doc, "evidence_position"), [])
        task["family"] = "F8"
        self.assertEqual(len(self.findings(doc, "evidence_position")), len(task["field_map"]))

    def test_multiple_claim_sources_and_checkpoint_versions_remain_distinct(self):
        doc = synthetic_document(("SYNTHETIC_FIRST", ("unresolved", None,
            [("SYNTHETIC-m0", "SYNTHETIC_FIRST"), ("SYNTHETIC-m1", "SYNTHETIC_SECOND")], "change")))
        doc["tasks"][0]["coverage_tags"]["context_pressure"] = "over"
        rows = self.findings(doc, "evidence_position")
        current = next(r for r in rows if r["probe_id"] == "SYNTHETIC-p1" and r["field"] == "values")
        historical = next(r for r in rows if r["probe_id"] == "SYNTHETIC-p1" and r["field"] == "old")
        self.assertEqual({s["message_id"] for s in current["sources"]}, {"SYNTHETIC-m0", "SYNTHETIC-m1"})
        self.assertEqual({s["message_id"] for s in historical["sources"]}, {"SYNTHETIC-m0"})

    def test_recovery_retry_window_follows_linked_branch(self):
        doc = synthetic_recovery()
        rows = self.findings(doc, "answer_restated_before_probe")
        self.assertTrue(any(r["probe_id"] == "SYNTHETIC-retry" and r["message_id"] == "SYNTHETIC-recovery" for r in rows))

    def test_canonical_deterministic_report_and_input_unchanged(self):
        raw = encode(synthetic_review_document(giveaways=True))
        result = authoring_lint.lint_authoring(raw)
        self.assertEqual(result, authoring_lint.lint_authoring(raw))
        self.assertEqual(result["source_sha256"], sha(raw))
        self.assertTrue(result["advisory"])
        self.assertFalse(result["semantics_verified"])
        self.assertEqual(encode(result), authoring_lint.report_bytes(raw))

    def test_cli_findings_exit_zero_canonical_stdout_summary_stderr_invalid_exit_two(self):
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-lint-") as temp:
            path = Path(temp) / "SYNTHETIC.json"
            raw = encode(synthetic_review_document(giveaways=True))
            path.write_bytes(raw)
            args = [sys.executable, "-B", "-m", "etps_v02.intake.authoring_lint", str(path)]
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.rstrip(), encode(json.loads(result.stdout)))
            self.assertIn(b"advisory", result.stderr)
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(b'{"SYNTHETIC invalid":')
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "rejected")
            path.unlink()
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
