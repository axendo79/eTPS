"""SYNTHETIC within-plan reporting, never pooled experiment evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document, synthetic_recovery
from etps_v02.intake.mapper import map_authoring
from etps_v02.intake.corpus_aggregation import AggregationError, aggregate_report
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, json_default, report, run_offline
from etps_v02.workload import decode, encode, sha, INVALIDATION_POLICY
from test_v02_runner import response


def synthetic_plan(doc, responses=None, slots=1):
    files = map_authoring(encode(doc))
    item = decode(files["bundle.json"])["tasks"][0]
    mraw = files[item["manifest"]]
    if responses is None:
        responses = [response(encode(p["expected"])) for p in doc["tasks"][0]["probes"] if p["position"] in
                     {m["id"] for m in doc["tasks"][0]["conversation"]}]
    script = encode({"responses": responses})
    artifacts = {sha(mraw): mraw, sha(script): script}
    plan = {"schema": "etps-offline-plan-v2", "purpose": "offline-verification", "unit": "utf8_bytes",
            "invalidation_policy": dict(INVALIDATION_POLICY), "tasks": {"SYNTHETIC-task": sha(mraw)},
            "slots": [{"id": f"SYNTHETIC-slot-{i}", "task": "SYNTHETIC-task", "arm": "A" if i % 2 == 0 else "B",
                       "script_sha256": sha(script)} for i in range(slots)]}
    raw = encode(plan)
    grouping = {"version": "corpus-grouping-v1", "repeat_id": "SYNTHETIC-repeat", "plan_sha256": sha(raw)}
    return raw, artifacts, grouping


class CorpusAggregationTests(unittest.TestCase):
    def test_cli_replays_v1_v2_and_refuses_output_overwrite(self):
        plan, artifacts, grouping = synthetic_plan(synthetic_document())
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            folder = Path(temp)
            store = Store.create(folder / "SYNTHETIC.db", plan, artifacts)
            try:
                run_offline(store, "SYNTHETIC-slot-0")
                (folder / "grouping.json").write_bytes(encode(grouping))
                for fmt in ("v1", "v2"):
                    exported = export_bundle(store, fmt)
                    exported["report"] = {"SYNTHETIC-forged": True}
                    (folder / "export.json").write_bytes(json.dumps(exported, default=json_default).encode())
                    out = folder / (fmt + ".json")
                    args = [sys.executable, "-B", "-m", "etps_v02.intake.corpus_aggregation", "--export", str(folder / "export.json"),
                            "--grouping", str(folder / "grouping.json"), "--output", str(out)]
                    result = subprocess.run(args, capture_output=True, cwd=Path(__file__).resolve().parents[1])
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(decode(out.read_bytes())["arms"]["A"]["overall"]["acceptance"]["accepted"], 1)
                    result = subprocess.run(args, capture_output=True, cwd=Path(__file__).resolve().parents[1])
                    self.assertEqual(result.returncode, 2)
            finally:
                store.close()

    def test_completed_recovery_separates_first_terminal_and_complete_set_units(self):
        doc = synthetic_recovery()
        correct = doc["tasks"][0]["probes"][0]["expected"]
        wrong = dict(correct, values=["SYNTHETIC-wrong"])
        plan, artifacts, grouping = synthetic_plan(doc, [response(encode(wrong)), response(encode(correct))])
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                run_offline(store, "SYNTHETIC-slot-0")
                original = report(store)
                result = aggregate_report(plan, artifacts, original, grouping)
                arm = result["arms"]["A"]["overall"]
                self.assertEqual(arm["acceptance"]["accepted"], 1)
                self.assertEqual(arm["first_attempt"]["ambiguity"]["correct"], 1)
                self.assertEqual(arm["terminal"]["ambiguity"]["correct"], 2)
                self.assertEqual(arm["first_attempt"]["ambiguity"]["planned"], 2)
                self.assertEqual(result["arms"]["A"]["families"]["F1"], arm)
                self.assertIn("provenance_need=\"needed\"", result["arms"]["A"]["coverage_tags"])
                self.assertEqual(result, aggregate_report(plan, artifacts, original, grouping))
            finally:
                store.close()

    def test_planned_attempted_unavailable_and_unattempted_preserved(self):
        plan, artifacts, grouping = synthetic_plan(synthetic_document(), slots=4)
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                run_offline(store, "SYNTHETIC-slot-0")
                store.append("SYNTHETIC-slot-1", "start", {})
                store.abort("SYNTHETIC-slot-1", "operator_abort", "SYNTHETIC")
                result = aggregate_report(plan, artifacts, report(store), grouping)
                a, b = (result["arms"][arm]["overall"] for arm in ("A", "B"))
                self.assertEqual((a["acceptance"]["planned"], a["acceptance"]["attempted"], a["acceptance"]["accepted"]), (2, 1, 1))
                self.assertEqual(a["terminal"]["current"]["accuracy"], {"numerator": 1, "denominator": 2})
                self.assertEqual(a["terminal"]["current"]["reason_counts"], {"unattempted": 1})
                self.assertEqual(b["first_attempt"]["current"]["unavailable_reasons"], {"operator_abort": 1})
                self.assertEqual(b["terminal"]["current"]["planned"], 2)
            finally:
                store.close()

    def test_missing_frozen_field_is_unavailable_not_remapped(self):
        doc = synthetic_document()
        p = doc["tasks"][0]["probes"][0]
        del p["field_map"]["source"]
        del p["expected"]["source"]
        plan, artifacts, grouping = synthetic_plan(doc)
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                run_offline(store, "SYNTHETIC-slot-0")
                original = report(store)
                self.assertEqual(original["dimension_accuracy"][0]["dimension_accuracy"]["unavailable_reason"], "heterogeneous_field_plan")
                result = aggregate_report(plan, artifacts, original, grouping)
                a = result["arms"]["A"]["overall"]
                self.assertEqual(a["first_attempt"]["provenance"]["unavailable_reasons"], {"field_not_supplied": 1})
                self.assertEqual(a["first_attempt"]["provenance"]["attempted"], 0)
                self.assertEqual(a["terminal"]["provenance"]["correct"], 1)
                self.assertTrue(original["trials"][0]["score"]["accepted"])
            finally:
                store.close()

    def test_refuse_multiple_plans_repeats_slot_loss_and_wrong_identity(self):
        plan, artifacts, grouping = synthetic_plan(synthetic_document())
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                r = report(store)
                cases = [([plan, plan], r, grouping, "multiple_plans"),
                         (plan, [r, r], grouping, "multiple_reports"),
                         (plan, r, dict(grouping, repeat_id=["SYNTHETIC-one", "SYNTHETIC-two"]), "repeat_identity"),
                         (plan, dict(r, plan_sha256="0" * 64), grouping, "plan_mismatch"),
                         (plan, dict(r, trials=[]), grouping, "slot_accounting"),
                         (plan, r, dict(grouping, extra="SYNTHETIC"), "grouping_fields")]
                for raw, rep, group, code in cases:
                    with self.subTest(code=code), self.assertRaises(AggregationError) as caught:
                        aggregate_report(raw, artifacts, rep, group)
                    self.assertEqual(caught.exception.code, code)
            finally:
                store.close()

    def test_timeout_unknown_malformed_incorrect_are_reason_coded(self):
        for outcome, raw in (("timeout", b""), ("malformed", b"SYNTHETIC"), ("incorrect", b'{}'),
                             ("unknown", b'{"status":"SYNTHETIC-unknown"}')):
            doc = synthetic_document(("SYNTHETIC_A",))
            doc["tasks"][0]["probes"][0]["unknown_answers"] = [{"status": "SYNTHETIC-unknown"}]
            plan, artifacts, grouping = synthetic_plan(doc, [response(raw, status="timeout" if outcome == "timeout" else "ok")])
            with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
                store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
                try:
                    run_offline(store, "SYNTHETIC-slot-0")
                    result = aggregate_report(plan, artifacts, report(store), grouping)
                    metric = result["arms"]["A"]["overall"]["first_attempt"]["current"]
                    self.assertEqual(metric["correct"], 0)
                    self.assertEqual(metric["attempted"], 1)
                    self.assertEqual(metric["unavailable_reasons"] if outcome == "timeout" else metric["reason_counts"], {outcome: 1})
                finally:
                    store.close()
