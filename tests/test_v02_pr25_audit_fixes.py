"""SYNTHETIC regressions for the Dot's PR #25 (e079bcd) audit findings."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from authoring_fixtures import synthetic_document
from etps_v02.intake.authoring import AuthoringError, validate_authoring
from etps_v02.intake.corpus_aggregation import aggregate_report
from etps_v02.intake.corpus_freeze import FreezeError, read_directory
from etps_v02.intake.mapper import MappingError, recover_source
from etps_v02.intake.state_records import IntakeError, validate_state_records
from etps_v02.persistence import Store
from etps_v02.runner import OfflineFailure, report, run_offline
from etps_v02.workload import decode, encode
from test_v02_corpus_aggregation import synthetic_plan
from test_v02_runner import response
from test_v02_state_records import bind, chain


class PR25AuditFixTests(unittest.TestCase):
    def test_scorer_invalid_aborted_prefix_is_unavailable_with_evidence_reason(self):
        # Finding 1: one scorer-invalid trial must not stop aggregation, and its
        # evidence reason outranks the abort code (SET_ANSWERS precedence).
        plan, artifacts, grouping = synthetic_plan(synthetic_document(), slots=2)
        manifest = decode(artifacts[decode(plan)["tasks"]["SYNTHETIC-task"]])
        start = manifest["start"]
        self.assertEqual(manifest["nodes"][start]["kind"], "user")
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                run_offline(store, "SYNTHETIC-slot-0")
                store.append("SYNTHETIC-slot-1", "start", {})
                store.append("SYNTHETIC-slot-1", "event",
                             {"node": start, "kind": "user", "text": "SYNTHETIC changed user text"})
                store.abort("SYNTHETIC-slot-1", "operator_abort", "SYNTHETIC")
                result = aggregate_report(plan, artifacts, report(store), grouping)
                a, b = (result["arms"][arm]["overall"] for arm in ("A", "B"))
                self.assertEqual(a["acceptance"]["accepted"], 1)
                for phase in ("first_attempt", "terminal"):
                    self.assertEqual(b[phase]["current"]["correct"], 0)
                    self.assertEqual(b[phase]["current"]["unavailable_reasons"], {"unmatched_user_payload": 1})
            finally:
                store.close()

    def test_invalid_measurement_keeps_attempted_fields_without_credit(self):
        # e1e1062 finding 1: a classified answer before an invalidating stop is
        # still attempted; credit stays unavailable (CORPUS_AGGREGATION).
        doc = synthetic_document()
        first = doc["tasks"][0]["probes"][0]["expected"]
        plan, artifacts, grouping = synthetic_plan(doc, [response(encode(first))])
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                with self.assertRaises(OfflineFailure):
                    run_offline(store, "SYNTHETIC-slot-0")
                original = report(store)
                self.assertFalse(original["trials"][0]["score"]["measurement_valid"])
                current = aggregate_report(plan, artifacts, original, grouping)["arms"]["A"]["overall"]["first_attempt"]["current"]
                self.assertEqual(current["attempted"], 1)
                self.assertEqual(current["correct"], 0)
                self.assertEqual(current["unavailable"], current["planned"])
            finally:
                store.close()

    def test_heterogeneous_plan_keeps_evidence_reason_over_abort(self):
        # e1e1062 finding 2: without per-dimension diagnostics (heterogeneous
        # field plan) the scorer's invalidation still outranks operator_abort.
        doc = synthetic_document()
        probe = doc["tasks"][0]["probes"][0]
        del probe["expected"]["source"], probe["field_map"]["source"]
        plan, artifacts, grouping = synthetic_plan(doc)
        manifest = decode(artifacts[decode(plan)["tasks"]["SYNTHETIC-task"]])
        start = manifest["start"]
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            store = Store.create(Path(temp) / "SYNTHETIC.db", plan, artifacts)
            try:
                store.append("SYNTHETIC-slot-0", "start", {})
                store.append("SYNTHETIC-slot-0", "event",
                             {"node": start, "kind": "user", "text": "SYNTHETIC changed user text"})
                store.abort("SYNTHETIC-slot-0", "operator_abort", "SYNTHETIC")
                original = report(store)
                self.assertIsNone(original["trials"][0]["score"]["dimension_accuracy"]["first_attempt"])
                arm = aggregate_report(plan, artifacts, original, grouping)["arms"]["A"]["overall"]
                for phase in ("first_attempt", "terminal"):
                    self.assertEqual(arm[phase]["current"]["unavailable_reasons"], {"unmatched_user_payload": 1})
            finally:
                store.close()

    def test_precedence_from_non_disagreement_is_a_typed_refusal(self):
        # e1e1062 finding 3: precedence on an expired version must not index
        # its empty claims; it is refused as precedence_claim.
        m, s = chain(("A", ("expired", None, [], "precedence")))
        with self.assertRaises(IntakeError) as caught:
            validate_state_records(m, bind(m, s))
        self.assertEqual(caught.exception.code, "precedence_claim")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO support required")
    def test_freeze_inventory_refuses_fifo(self):
        # Finding 2: nonregular entries are refused, never silently skipped.
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            root = Path(temp)
            (root / "SYNTHETIC.json").write_bytes(b"{}")
            os.mkfifo(root / "SYNTHETIC-extra")
            with self.assertRaises(FreezeError) as caught:
                read_directory(root)
            self.assertEqual(caught.exception.code, "artifact_path")

    def test_freeze_inventory_refuses_any_nonregular_entry(self):
        # Platform-independent form of finding 2: an entry that is neither a
        # directory nor a regular file is refused.
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            root = Path(temp)
            (root / "SYNTHETIC.json").write_bytes(b"{}")
            odd = root / "SYNTHETIC-extra"
            odd.write_bytes(b"")
            real_is_file = Path.is_file
            with patch.object(Path, "is_file", lambda self: False if self == odd else real_is_file(self)):
                with self.assertRaises(FreezeError) as caught:
                    read_directory(root)
            self.assertEqual(caught.exception.code, "artifact_path")

    def test_set_answer_arrays_obey_admission_ceiling(self):
        # Finding 3: set arrays inside answers obey the 4,096-member ceiling.
        doc = synthetic_document()
        probe = doc["tasks"][0]["probes"][0]
        probe["unknown_answers"] = [{**probe["expected"], "values": list(range(4097))}]
        with self.assertRaises(AuthoringError) as caught:
            validate_authoring(encode(doc))
        self.assertEqual(caught.exception.code, "safety_limit")

    def test_malformed_bundle_index_is_a_typed_refusal(self):
        # Finding 4: malformed bundle.json gives MappingError("bundle_changed").
        for index in (b"null", b"[]", b"7", b'{"source_sha256": 7}'):
            with self.subTest(index=index):
                with self.assertRaises(MappingError) as caught:
                    recover_source({"bundle.json": index, "source.json": b"{}"})
                self.assertEqual(caught.exception.code, "bundle_changed")


if __name__ == "__main__":
    unittest.main()
