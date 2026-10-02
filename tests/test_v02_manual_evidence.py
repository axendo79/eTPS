"""Manual evidence regressions using scripted synthetic input only."""
import io
from pathlib import Path
import tempfile
import unittest

from etps_v02.manual_runner import run_manual
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, replay_slot
from etps_v02.workload import encode
from test_v02_manual_dev import manual_bundle, paste
from test_v02_session_profile import rechain


class ManualEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        plan, artifacts = manual_bundle()
        self.store = Store.create(Path(temp.name) / "manual.db", encode(plan), artifacts)
        self.addCleanup(self.store.close)

    def run_script(self, script):
        return run_manual(self.store, "slot", allow_manual=True,
                          stdin=io.BytesIO(script), stdout=io.StringIO())

    def test_clean_finished_manual_evidence_is_verified(self):
        trial = self.run_script(paste())
        self.assertEqual(trial["state"], "finished")
        self.assertIs(trial["evidence_verified"], True)
        self.assertIs(trial["score"]["measurement_valid"], True)
        self.assertEqual(replay_export(export_bundle(self.store, "v1"))["dev_manual"]["trials"][0], trial)

    def test_rechained_user_text_invalidates_finished_evidence(self):
        self.run_script(paste())
        exported = export_bundle(self.store, "v1")
        event = next(row["payload"] for row in exported["journal"]["slot"]
                     if row["kind"] == "event" and row["payload"]["kind"] == "user")
        event["text"] = "Unplanned synthetic input"
        rechain(exported)
        trial = replay_export(exported)["dev_manual"]["trials"][0]
        self.assertEqual(trial["state"], "finished")
        self.assertIs(trial["evidence_verified"], False)
        self.assertIs(trial["score"]["measurement_valid"], False)
        self.assertEqual(trial["score"]["reason"], "unmatched_user_payload")
        self.assertIn("recomputed_measurement_invalid", trial["warnings"])
        self.assertIn("unverified_evidence: invalid_finished_trace", trial["warnings"])

    def test_unattempted_aborted_and_running_keep_verification_values(self):
        self.assertIsNone(replay_slot(self.store, "slot")["evidence_verified"])
        aborted = self.run_script(paste(confirm=b"no"))
        self.assertEqual(aborted["state"], "aborted")
        self.assertIs(aborted["evidence_verified"], True)
        exported = export_bundle(self.store, "v1")
        exported["journal"]["slot"].pop()
        rechain(exported)
        running = replay_export(exported)["dev_manual"]["trials"][0]
        self.assertEqual(running["state"], "running")
        self.assertIs(running["evidence_verified"], True)
        for trial in (aborted, running):
            self.assertIs(trial["score"]["measurement_valid"], False)
            self.assertNotIn("recomputed_measurement_invalid", trial["warnings"])
            self.assertNotIn("unverified_evidence: invalid_finished_trace", trial["warnings"])


if __name__ == "__main__":
    unittest.main()
