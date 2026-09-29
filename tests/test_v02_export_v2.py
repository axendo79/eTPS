"""Opt-in completeness binding; editable hashes are not execution attestation."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, implementation, json_default, replay_export, report, run_offline
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode, sha
from test_v02_runner import bundle


class ExportV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        plan, artifacts = bundle(slots=4)
        self.store = Store.create(Path(self.temp.name) / "offline.db", plan, artifacts)
        self.addCleanup(self.store.close)
        run_offline(self.store, "slot-0")

    def exported(self):
        return export_bundle(self.store, format="v2")

    def rehash_envelope(self, exported):
        envelope = exported["envelope"]
        envelope["envelope_sha256"] = sha(encode([
            exported["plan_sha256"], envelope["slot_order"], envelope["heads"]]))

    def test_default_v1_serialized_body_and_warnings_stay_unchanged(self):
        # The pre-v2 serialization contract, including insertion order and no envelope.
        expected = {"format": "etps-offline-export-v1", "plan_sha256": self.store.plan_hash,
                    "plan_base64": base64.b64encode(self.store.plan_raw).decode("ascii"),
                    "artifacts": {k: base64.b64encode(v).decode("ascii")
                                  for k, v in self.store.artifacts.items()},
                    "journal": {slot: self.store.entries(slot) for slot in self.store.slots},
                    "report": report(self.store)}
        for exported in (export_bundle(self.store), export_bundle(self.store, format="v1")):
            self.assertEqual(json.dumps(exported, default=json_default, ensure_ascii=False, indent=2),
                             json.dumps(expected, default=json_default, ensure_ascii=False, indent=2))
            checked = replay_export(exported)
            self.assertEqual(checked, {**expected["report"], "authoring_gate_reasserted": False,
                                       "export_completeness_bound": False})
            self.assertEqual(checked["warnings"], [])
        expected["journal"]["slot-0"] = []
        erased = replay_export(expected)
        self.assertEqual(erased["attempted"], 0)
        self.assertEqual(erased["warnings"], [])
        self.assertFalse(erased["export_completeness_bound"])

    def test_v2_round_trip_binds_database_heads_and_preserves_report(self):
        exported = self.exported()
        self.assertEqual(exported["format"], "etps-offline-export-v2")
        envelope = exported["envelope"]
        self.assertEqual(envelope["slot_order"], [s["id"] for s in self.store.plan["slots"]])
        actual = {r["slot"]: {k: r[k] for k in ("count", "hash", "state")}
                  for r in self.store.db.execute("SELECT * FROM heads")}
        self.assertEqual(envelope["heads"], actual)
        self.assertEqual(envelope["envelope_sha256"], sha(encode([
            exported["plan_sha256"], envelope["slot_order"], actual])))
        checked = replay_export(exported, validate_authoring=True)
        self.assertTrue(checked.pop("export_completeness_bound"))
        self.assertTrue(checked.pop("authoring_gate_reasserted"))
        self.assertEqual(checked, report(self.store))
        self.assertEqual(checked["trials"][0]["evidence_issues"], [])
        self.assertTrue(checked["trials"][0]["evidence_verified"])

    def test_v2_truncated_and_emptied_journals_are_integrity_failures(self):
        original = self.exported()
        for remaining in (0, 1, len(original["journal"]["slot-0"]) - 1):
            with self.subTest(remaining=remaining):
                changed = copy.deepcopy(original)
                changed["journal"]["slot-0"] = changed["journal"]["slot-0"][:remaining]
                with self.assertRaisesRegex(InvalidRecord, "head count integrity"):
                    replay_export(changed)

    def test_v2_missing_extra_or_reordered_slots_are_rejected(self):
        for mutation in ("remove_journal", "extra_journal", "reorder", "remove_head", "extra_head"):
            with self.subTest(mutation=mutation):
                changed = self.exported()
                if mutation == "remove_journal":
                    del changed["journal"]["slot-1"]
                elif mutation == "extra_journal":
                    changed["journal"]["extra"] = []
                elif mutation == "reorder":
                    changed["envelope"]["slot_order"].reverse()
                elif mutation == "remove_head":
                    del changed["envelope"]["heads"]["slot-1"]
                else:
                    changed["envelope"]["heads"]["extra"] = changed["envelope"]["heads"]["slot-1"]
                self.rehash_envelope(changed)
                with self.assertRaises(InvalidRecord):
                    replay_export(changed)

    def test_v2_edited_heads_without_envelope_rehash_are_rejected(self):
        for field, value in (("count", 0), ("hash", "0" * 64), ("state", "running")):
            with self.subTest(field=field):
                changed = self.exported()
                changed["envelope"]["heads"]["slot-0"][field] = value
                with self.assertRaisesRegex(InvalidRecord, "envelope hash integrity"):
                    replay_export(changed)

    def test_v2_edited_envelope_hash_is_rejected(self):
        changed = self.exported()
        changed["envelope"]["envelope_sha256"] = "0" * 64
        with self.assertRaisesRegex(InvalidRecord, "envelope hash integrity"):
            replay_export(changed)

    def test_v2_rehashed_envelope_does_not_hide_count_hash_or_state_mismatch(self):
        for field, value in (("count", 0), ("hash", "0" * 64), ("state", "running")):
            with self.subTest(field=field):
                changed = self.exported()
                changed["envelope"]["heads"]["slot-0"][field] = value
                self.rehash_envelope(changed)
                with self.assertRaisesRegex(InvalidRecord, "head " + field + " integrity"):
                    replay_export(changed)

    def test_v2_zero_count_requires_seed_hash_and_unattempted_state(self):
        for field, value in (("hash", "0" * 64), ("state", "finished")):
            with self.subTest(field=field):
                changed = self.exported()
                changed["envelope"]["heads"]["slot-1"][field] = value
                self.rehash_envelope(changed)
                with self.assertRaisesRegex(InvalidRecord, "head " + field + " integrity"):
                    replay_export(changed)

    def test_v2_all_lifecycle_states_round_trip(self):
        self.store.append("slot-1", "start", implementation())
        self.store.abort("slot-1", "operator_abort")
        self.store.append("slot-2", "start", implementation())
        exported = self.exported()
        self.assertEqual([h["state"] for h in exported["envelope"]["heads"].values()],
                         ["finished", "aborted", "running", "unattempted"])
        checked = replay_export(exported)
        self.assertTrue(checked["export_completeness_bound"])
        self.assertEqual([t["state"] for t in checked["trials"]],
                         ["finished", "aborted", "running", "unattempted"])

    def test_v2_malformed_envelopes_raise_invalid_record(self):
        for envelope in (None, [], {}, {"slot_order": [], "heads": {}, "envelope_sha256": "bad"}):
            with self.subTest(envelope=envelope):
                changed = self.exported()
                changed["envelope"] = envelope
                with self.assertRaises(InvalidRecord):
                    replay_export(changed)
        for field, value in (("count", True), ("count", -1), ("count", 1.0),
                             ("hash", []), ("state", [])):
            with self.subTest(field=field, value=value):
                changed = self.exported()
                changed["envelope"]["heads"]["slot-0"][field] = value
                self.rehash_envelope(changed)
                with self.assertRaises(InvalidRecord):
                    replay_export(changed)

    def test_coherent_full_rewrite_is_accepted_accident_detection_not_attestation(self):
        changed = self.exported()
        # Erase the attempt and coherently recompute every journal/head/envelope hash.
        changed["journal"]["slot-0"] = []
        for slot, entries in changed["journal"].items():
            previous = sha(encode([changed["plan_sha256"], slot]))
            state = "unattempted"
            for i, entry in enumerate(entries):
                previous = sha(encode([slot, i, entry["kind"], previous]) + encode(entry["payload"]))
                entry["sha256"] = previous
                state = {"start": "running", "finish": "finished", "abort": "aborted"}.get(entry["kind"], state)
            changed["envelope"]["heads"][slot] = {"count": len(entries), "hash": previous, "state": state}
        self.rehash_envelope(changed)
        checked = replay_export(changed)
        self.assertTrue(checked["export_completeness_bound"])
        self.assertEqual(checked["attempted"], 0)
        self.assertEqual(checked["warnings"], [])

    def test_v2_snapshot_is_consistent_during_concurrent_append(self):
        writer = Store(self.store.path)
        self.addCleanup(writer.close)
        original = self.store.entries
        written = False
        def append_during_read(slot):
            nonlocal written
            if not written:
                written = True
                writer.append("slot-1", "start", implementation())
                writer.abort("slot-1", "operator_abort")
            return original(slot)
        with patch.object(self.store, "entries", side_effect=append_during_read):
            exported = self.exported()
        self.assertTrue(replay_export(exported)["export_completeness_bound"])
        self.assertEqual(exported["envelope"]["heads"]["slot-1"]["state"], "unattempted")
        self.assertEqual(report(self.store)["aborted"], 1)
        self.assertFalse(self.store.db.in_transaction)

    def test_v2_preserves_caller_transaction_and_releases_snapshot_on_error(self):
        self.store.db.execute("BEGIN")
        self.exported()
        self.assertTrue(self.store.db.in_transaction)
        self.store.db.rollback()
        with patch.object(self.store, "entries", side_effect=InvalidRecord("synthetic corruption")):
            with self.assertRaisesRegex(InvalidRecord, "synthetic corruption"):
                self.exported()
        self.assertFalse(self.store.db.in_transaction)

    def test_invalid_api_export_format(self):
        for value in ("v3", "etps-offline-export-v2", None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(InvalidRecord, "unsupported export format"):
                export_bundle(self.store, format=value)

    def test_cli_v2_round_trip_default_v1_and_invalid_format(self):
        for choice in (None, "v1", "v2"):
            path = Path(self.temp.name) / f"export-{choice}.json"
            args = [sys.executable, "-B", "-m", "etps_v02", "export", str(self.store.path), "--output", str(path)]
            if choice is not None:
                args += ["--format", choice]
            completed = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            exported = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(exported["format"], "etps-offline-export-" + (choice or "v1"))
            checked = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "replay-export", str(path)],
                                     capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["export_completeness_bound"], choice == "v2")
        invalid = Path(self.temp.name) / "invalid.json"
        failed = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "export", str(self.store.path),
                                 "--output", str(invalid), "--format", "v3"], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("error:", failed.stderr)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertFalse(invalid.exists())

    def test_cli_v2_integrity_failure_is_concise_exit_two(self):
        changed = self.exported()
        changed["journal"]["slot-0"] = []
        path = Path(self.temp.name) / "erased.json"
        path.write_text(json.dumps(changed, default=json_default), encoding="utf-8")
        failed = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "replay-export", str(path)],
                                capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertTrue(failed.stderr.startswith("error:"))
        self.assertNotIn("Traceback", failed.stderr)
