"""SYNTHETIC version admission, answer-form lint and compatibility tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document, synthetic_recovery
from authoring_rulings_fixtures import synthetic_missing_unit
from brief_v2_fixtures import synthetic_rename, synthetic_v2
from review_tools_fixtures import synthetic_review_document
from test_v02_corpus_freeze import synthetic_freezable, synthetic_review
from etps_v02.intake.authoring import AuthoringError, validate_authoring
from etps_v02.intake.authoring_lint import lint_authoring
from etps_v02.intake.corpus_freeze import FreezeError, create_freeze, verify_freeze
from etps_v02.intake.mapper import map_authoring, recover_source
from etps_v02.workload import decode, encode

ROOT = Path(__file__).resolve().parents[1]


class BriefV2AdmissionTests(unittest.TestCase):
    def test_v1_and_v2_admit_without_mutating_exact_source(self):
        for doc in (synthetic_document(), synthetic_v2(synthetic_document()),
                    synthetic_v2(synthetic_missing_unit()), synthetic_v2(synthetic_recovery())):
            with self.subTest(brief=doc["brief_version"]):
                raw = encode(doc)
                self.assertEqual(validate_authoring(raw), doc)
                self.assertEqual(raw, encode(doc))

    def test_v2_pins_each_of_five_id_categories_v1_stays_compatible(self):
        doc = synthetic_v2(synthetic_document())
        task = doc["tasks"][0]
        for old in (task["conversation"][0]["id"], task["probes"][0]["id"],
                    task["state_history"][0]["id"], task["state_history"][0]["versions"][0]["id"],
                    task["state_history"][0]["versions"][0]["requirements"][0]["id"]):
            for new in (old[:-3] + "1", old[:-3] + "000", old[:-3] + "1000", old.upper(), "OTHER-m001"):
                with self.subTest(old=old, new=new):
                    bad = synthetic_rename(doc, old, new)
                    with self.assertRaises(AuthoringError) as caught:
                        validate_authoring(encode(bad))
                    self.assertEqual(caught.exception.code, "id_style")
                    self.assertIn("source.tasks[0]", caught.exception.path)
                    bad["brief_version"] = "authoring-brief-v1"
                    validate_authoring(encode(bad))

    def test_v2_does_not_add_hygiene_or_pressure_refusals(self):
        doc = synthetic_v2(synthetic_review_document(giveaways=True))
        doc["tasks"][0]["probes"][0]["wording"] = "[SYNTHETIC-task-q001] SYNTHETIC vague question."
        self.assertEqual(validate_authoring(encode(doc)), doc)

    def test_literal_task_prefix_metacharacters_and_noncontiguous_numbers(self):
        doc = synthetic_v2(synthetic_document())
        doc = synthetic_rename(doc, "SYNTHETIC-task", "SYNTHETIC.task+unit")
        doc = synthetic_rename(doc, "SYNTHETIC.task+unit-m001", "SYNTHETIC.task+unit-m017")
        self.assertEqual(validate_authoring(encode(doc)), doc)

    def test_schema_lists_both_briefs(self):
        schema = json.loads((ROOT / "docs/v0.2/authoring-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["brief_version"]["enum"],
                         ["authoring-brief-v1", "authoring-brief-v2"])

    def test_mapper_and_freeze_propagate_v2_preserve_review_gates(self):
        files = synthetic_freezable()
        source = encode(synthetic_v2(decode(files["source.json"])))
        derived = map_authoring(source)
        self.assertEqual(recover_source(derived), source)
        manifest = decode(derived["task-0001.manifest.json"])
        self.assertEqual(manifest["metadata"]["authoring"]["brief_version"], "authoring-brief-v2")
        files.update(derived)
        # Synthetic marker is sufficient for the existing freeze rule; this is
        # neither an actual authoring brief nor a simulated human review claim.
        files["authoring-brief.md"] = b"SYNTHETIC authoring-brief-v2"
        synthetic_review(files)
        receipt = create_freeze(files, "SYNTHETIC-v2", "development", "SYNTHETIC time")
        self.assertEqual(decode(receipt)["brief_version"], "authoring-brief-v2")
        self.assertEqual(verify_freeze(files, receipt)["status"], "verified")
        files["authoring-brief.md"] = b"SYNTHETIC authoring-brief-v1"
        synthetic_review(files)
        with self.assertRaises(FreezeError) as caught:
            create_freeze(files, "SYNTHETIC-v2", "development", "SYNTHETIC time")
        self.assertEqual(caught.exception.code, "brief_version")


class BriefV2LintTests(unittest.TestCase):
    def rows(self, doc, code="answer_form_missing", **options):
        return [f for f in lint_authoring(encode(doc), **options)["findings"] if f["code"] == code]

    def probe_only(self, value, kind="current"):
        doc = synthetic_v2(synthetic_document())
        task = doc["tasks"][0]
        probe = task["probes"][0]
        query = copy.deepcopy(task["field_map"]["answer"])
        query.update(kind=kind, checkpoint=task["conversation"][0]["id"] if kind == "at-checkpoint" else None)
        task["field_map"] = {"answer": query}
        task["probes"] = [probe]
        probe.update(field_map=copy.deepcopy(task["field_map"]), expected={"answer": value},
                     set_fields=["answer"] if kind == "values" else [])
        return doc, probe

    def test_number_text_id_null_status_and_set_forms_are_field_specific(self):
        cases = [(7, "current", "Return answer as a bare JSON number.", "number"),
                 ("SYNTHETIC_A", "at-checkpoint", "Return answer as exact text as written in the conversation.", "exact_text"),
                 ("SYNTHETIC-task-m001", "provenance", "Return answer as the bare ID, with no brackets or extra text.", "bare_id"),
                 (None, "current", "Return null for answer when nothing applies (cancelled, none, or never set).", "null_when_none"),
                 ("active", "status", "For answer, allowed status words: active, expired, unresolved, unestablished.", "status_words"),
                 ([7, 9], "values", "Return answer as a JSON array of bare JSON numbers.", "number"),
                 (["SYNTHETIC_A"], "values", "Return answer as a JSON array of exact text as written in the conversation.", "exact_text"),
                 ([], "values", "Return answer as an empty JSON array when no values apply.", "empty_array_when_none")]
        for value, kind, wording, form in cases:
            with self.subTest(kind=kind, value=value):
                doc, probe = self.probe_only(value, kind)
                probe["wording"] = f"[{probe['id']}] SYNTHETIC return answer as JSON."
                rows = self.rows(doc)
                self.assertEqual(rows[0]["field"], "answer")
                self.assertIn(form, rows[0]["missing_forms"])
                probe["wording"] += " " + wording
                self.assertEqual(self.rows(doc), [])

    def test_generic_json_wrong_form_or_another_fields_form_does_not_suffice(self):
        doc = synthetic_v2(synthetic_document())
        probe = doc["tasks"][0]["probes"][0]
        doc["tasks"][0]["probes"] = [probe]
        probe["wording"] = f"[{probe['id']}] SYNTHETIC return JSON. For answer, use exact text as written in the conversation."
        rows = self.rows(doc)
        self.assertNotIn("answer", {r["field"] for r in rows})
        self.assertIn("old", {r["field"] for r in rows})
        self.assertIn("source", {r["field"] for r in rows})
        doc, probe = self.probe_only(7)
        probe["wording"] += " Return answer as exact text as written in the conversation."
        self.assertIn("number", self.rows(doc)[0]["missing_forms"])

    def test_status_identifier_projection_and_declared_missing_item_name(self):
        doc = synthetic_v2(synthetic_missing_unit())
        probe = doc["tasks"][0]["probes"][0]
        probe["wording"] += " For status, allowed status words: active expired unresolved unestablished missing_information. For missing_item, return the bare ID, with no brackets or extra text."
        self.assertEqual(self.rows(doc), [])
        self.assertEqual(self.rows(doc, "status_vocabulary_missing"), [])
        self.assertTrue(self.rows(doc, "missing_item_not_named"))
        probe["wording"] += " The required item is SYNTHETIC-task-p002."
        self.assertEqual(self.rows(doc, "missing_item_not_named"), [])

    def test_v2_three_message_window_includes_sources_v1_defaults_two(self):
        doc = synthetic_review_document()
        task = doc["tasks"][0]
        task["conversation"][2]["text"] += " SYNTHETIC_KEY SYNTHETIC-m0"
        self.assertEqual(self.rows(doc, "answer_restated_before_probe"), [])
        v2 = synthetic_v2(doc)
        # ID inside filler is ordinary public text and does not become a reference.
        v2["tasks"][0]["conversation"][2]["text"] += " SYNTHETIC-task-m001"
        report = lint_authoring(encode(v2))
        self.assertEqual(report["version"], "authoring-lint-v2")
        self.assertEqual(report["config"]["window"], 3)
        self.assertTrue(self.rows(v2, "answer_restated_before_probe"))
        self.assertEqual(self.rows(v2, "answer_restated_before_probe", window=2), [])
        task["probes"][0]["position"] = "SYNTHETIC-m0"
        self.assertEqual({r["field"] for r in self.rows(doc, "answer_restated_before_probe")}, {"source"})
        v2 = synthetic_v2(doc)
        self.assertEqual({r["field"] for r in self.rows(v2, "answer_restated_before_probe")},
                         {"answer", "old", "status", "values", "source"})

    def test_v2_retry_wording_has_own_forms_and_correction_window(self):
        doc = synthetic_v2(synthetic_recovery())
        rows = self.rows(doc)
        self.assertEqual({r["probe_id"] for r in rows}, {p["id"] for p in doc["tasks"][0]["probes"]})
        self.assertTrue(any(r["message_id"] == "SYNTHETIC-recovery" for r in
                            self.rows(doc, "answer_restated_before_probe")))

    def test_cli_defaults_to_three_for_v2_and_report_is_advisory(self):
        with tempfile.TemporaryDirectory(prefix="SYNTHETIC-v2-") as temp:
            path = Path(temp) / "SYNTHETIC.json"
            raw = encode(synthetic_v2(synthetic_review_document()))
            path.write_bytes(raw)
            result = subprocess.run([sys.executable, "-B", "-m", "etps_v02.intake.authoring_lint", str(path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["config"]["window"], 3)
            self.assertTrue(report["advisory"])
            self.assertFalse(report["semantics_verified"])
            self.assertEqual(path.read_bytes(), raw)

    def test_v2_pinned_task_prefix_is_not_a_mixed_style(self):
        doc = synthetic_v2(synthetic_review_document())
        self.assertEqual(self.rows(doc, "id_style_mixed"), [])

    def test_v2_source_confirmation_is_checked_without_provenance_answer_field(self):
        doc = synthetic_v2(synthetic_review_document())
        task = doc["tasks"][0]
        probe = task["probes"][0]
        task["field_map"] = {"answer": task["field_map"]["answer"]}
        probe.update(field_map=copy.deepcopy(task["field_map"]), expected={"answer": "SYNTHETIC_KEY"}, set_fields=[])
        task["conversation"][2]["text"] += " The source remains SYNTHETIC-task-m001."
        hits = self.rows(doc, "answer_restated_before_probe")
        self.assertTrue(any(r.get("restatement") == "source_id" and r["message_id"] == task["conversation"][2]["id"] for r in hits))

    def test_values_meaning_and_pressure_remain_advisory_without_budget_inference(self):
        doc = synthetic_v2(synthetic_review_document())
        task = doc["tasks"][0]
        # Move the established evidence beyond the first tenth in both bases.
        task["conversation"][0], task["conversation"][2] = task["conversation"][2], task["conversation"][0]
        self.assertTrue(self.rows(doc, "evidence_outside_first_tenth"))
        pressure = self.rows(doc, "context_pressure_unverified")[0]
        self.assertEqual(pressure["messages"], 5)
        self.assertEqual(pressure["characters"], sum(len(m["text"]) for m in task["conversation"]))
        self.assertEqual(pressure["required_budget_fraction"], ">=2")
        task["coverage_tags"]["context_pressure"] = "within"
        self.assertEqual(self.rows(doc, "evidence_outside_first_tenth"), [])
        self.assertEqual(self.rows(doc, "context_pressure_unverified")[0]["required_budget_fraction"], "<0.5")
        task["probes"][0]["expected"]["values"] = ["SYNTHETIC_PAST"]
        self.assertTrue(self.rows(doc, "values_not_in_force"))
        self.assertEqual(validate_authoring(encode(doc)), doc)


class BriefV2DocsTests(unittest.TestCase):
    def test_v2_has_all_nine_rules_without_condition_designs(self):
        brief = (ROOT / "docs/v0.2/AUTHORING_BRIEF_V2.md").read_text(encoding="utf-8")
        for term in ("bare JSON numbers", "exactly as written", "bare ID", "allowed status words",
                     "values in force", "declared item ID", "Describe events", "3 messages",
                     "upcoming question", "<task>-m001", "<task>-q001", "<task>-p001",
                     "<task>-v001", "<task>-r001", "first 10%", "at least 2x", "under 50%",
                     "messages and characters", "token counter"):
            self.assertIn(term, brief)
        self.assertNotIn("A receives", brief)
        self.assertNotIn("B receives", brief)

    def test_indices_runbook_and_diagnostic_documentation(self):
        for name in ("docs/INDEX.md", "docs/v0.2/README.md", "docs/v0.2/AUTHORING_RUNBOOK.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("AUTHORING_BRIEF_V2.md", text)
            self.assertIn("historical", text)
        runbook = (ROOT / "docs/v0.2/AUTHORING_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("authoring-lint-v2", runbook)
        normalized = (ROOT / "docs/v0.2/NORMALIZED_SCORE.md").read_text(encoding="utf-8")
        for term in ("diagnostic", "strict", "acceptance", "STUCK-DECISION", "before"):
            self.assertIn(term, normalized)
