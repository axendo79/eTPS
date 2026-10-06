"""Invalid measurement diagnostics using synthetic traces and mocked adapters."""
import base64
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.adapter_openai import envelope
from etps_v02.live_runner import run_live
from etps_v02.manual_runner import run_manual
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export
from etps_v02.scorer import score
from etps_v02.workload import encode, sha
from test_v02_dimension_accuracy import dimensions
from test_v02_live_adapter import bundle as live_bundle
from test_v02_manual_dev import manual_bundle, paste
from test_v02_session_profile import rechain
from test_v02_set_ambiguity import trace
from test_v02_set_answers import set_manifest


def rechain_fixture(exported):
    """Bind the edited synthetic journal, including the v2 envelope."""
    rechain(exported)
    if "envelope" in exported:
        envelope = exported["envelope"]
        for slot, rows in exported["journal"].items():
            state = {"finish": "finished", "abort": "aborted"}.get(rows[-1]["kind"], "running")
            envelope["heads"][slot] = {"count": len(rows), "hash": rows[-1]["sha256"], "state": state}
        envelope["envelope_sha256"] = sha(encode([
            exported["plan_sha256"], envelope["slot_order"], envelope["heads"]]))


class InvalidDimensionTests(unittest.TestCase):
    def assert_unavailable(self, diagnostic, reason):
        for phase, fields in (("first_attempt", "first_fields"), ("terminal", "terminal_fields")):
            self.assertEqual(diagnostic[fields], {"values": "unavailable", "code": "unavailable"})
            metric = diagnostic[phase]["ambiguity"]
            self.assertEqual((metric["correct"], metric["planned"], metric["accuracy"]), (0, 2, 0))
            self.assertEqual(metric["reason_counts"],
                             {"incorrect": 0, "unknown": 0, "malformed": 0,
                              "unattempted": 0, "unavailable": 2})
            self.assertEqual(metric["unavailable_reasons"], {reason: 2})

    def recovery_manifest(self):
        m = dimensions(set_manifest())
        m["nodes"]["p1"]["next"]["correct"] = "recover"
        m["nodes"]["recover"]["spans"] = []
        return m

    def test_correct_first_probe_in_invalid_finished_manual_trace(self):
        # Retained F2 counterexample: a valid first answer precedes bad recovery input.
        m = self.recovery_manifest()
        p, a = manual_bundle(m)
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "manual.db", encode(p), a)
            try:
                answer = encode(m["nodes"]["p1"]["expected"])
                valid = run_manual(store, "slot", allow_manual=True,
                                   stdin=io.BytesIO(paste(answer) * 2), stdout=io.StringIO())
                self.assertTrue(valid["score"]["measurement_valid"])
                self.assertEqual(valid["score"]["dimension_accuracy"]["first_attempt"]["ambiguity"]["correct"], 2)
                for fmt in ("v1", "v2"):
                    with self.subTest(fmt=fmt):
                        exported = export_bundle(store, fmt)
                        event = next(row["payload"] for row in exported["journal"]["slot"]
                                     if row["kind"] == "event" and row["payload"]["node"] == "recover")
                        event["text"] = "Changed synthetic recovery payload"
                        rechain_fixture(exported)
                        replayed = replay_export(exported)["dev_manual"]
                        scored = replayed["trials"][0]["score"]
                        self.assertFalse(scored["measurement_valid"])
                        self.assertEqual(scored["reason"], "unmatched_user_payload")
                        self.assert_unavailable(scored["dimension_accuracy"], "unmatched_user_payload")
                        self.assertEqual(replayed["dimension_accuracy"][0]["dimension_accuracy"],
                                         scored["dimension_accuracy"])
                        for key in ("accepted", "RR", "experimental_eTPS"):
                            self.assertIsNone(scored[key])
                        # Changing diagnostic invalidation cannot change any primary score.
                        with patch("etps_v02.dimension_accuracy.finalize"):
                            baseline = replay_export(exported)["dev_manual"]["trials"][0]["score"]
                        self.assertEqual({k: v for k, v in scored.items() if k != "dimension_accuracy"},
                                         {k: v for k, v in baseline.items() if k != "dimension_accuracy"})
            finally:
                store.close()

    def test_invalid_pure_traces_erase_correct_first_credit_without_primary_changes(self):
        m = self.recovery_manifest()
        record = trace(m, [m["nodes"]["p1"]["expected"], m["nodes"]["p2"]["expected"]])
        truncated = copy.deepcopy(record)
        truncated["events"] = truncated["events"][:2]
        changed = copy.deepcopy(record)
        changed["events"][2]["text"] = "Changed synthetic recovery payload"
        for invalid, reason in ((truncated, "truncated_trace"), (changed, "unmatched_user_payload")):
            with self.subTest(reason=reason):
                scored = score(m, invalid)
                self.assertFalse(scored["measurement_valid"])
                self.assertEqual(scored["reason"], reason)
                self.assert_unavailable(scored["dimension_accuracy"], reason)
                with patch("etps_v02.dimension_accuracy.finalize"):
                    baseline = score(m, invalid)
                self.assertEqual({k: v for k, v in scored.items() if k != "dimension_accuracy"},
                                 {k: v for k, v in baseline.items() if k != "dimension_accuracy"})

    def test_manual_abort_after_correct_first_probe_has_no_credit(self):
        m = self.recovery_manifest()
        p, a = manual_bundle(m)
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "manual-abort.db", encode(p), a)
            try:
                answer = encode(m["nodes"]["p1"]["expected"])
                trial = run_manual(store, "slot", allow_manual=True,
                    stdin=io.BytesIO(paste(answer) + paste(answer, confirm=b"no")), stdout=io.StringIO())
                self.assertEqual(trial["state"], "aborted")
                self.assertEqual(trial["score"]["reason"], "unfinished_slot")
                self.assert_unavailable(trial["score"]["dimension_accuracy"], "operator_abort")
                for fmt in ("v1", "v2"):
                    replayed = replay_export(export_bundle(store, fmt))["dev_manual"]
                    self.assertEqual(replayed["trials"][0], trial)
                    self.assertEqual(replayed["dimension_accuracy"][0]["dimension_accuracy"],
                                     trial["score"]["dimension_accuracy"])
            finally:
                store.close()

    def test_live_abort_and_running_prefix_after_correct_answer_have_no_credit(self):
        m = dimensions(set_manifest())
        p, _ = live_bundle("http://127.0.0.1:1")
        raw_manifest = encode(m)
        p["tasks"] = {"synthetic-task": sha(raw_manifest)}
        body = encode({"choices": [{"message": {"role": "assistant",
                                              "content": encode(m["nodes"]["p1"]["expected"]).decode()}}]})
        event = {**envelope("openai-compatible", 200, body), "http_status": 200,
                 "http_body_base64": base64.b64encode(body).decode(), "http_body_sha256": sha(body),
                 "client_latency_seconds": 0.001}
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "live.db", encode(p), {sha(raw_manifest): raw_manifest})
            try:
                with patch("etps_v02.adapter_openai.preflight"), patch("etps_v02.adapter_openai.send", return_value=event):
                    valid = run_live(store, "slot", allow_live=True)
                self.assertTrue(valid["score"]["measurement_valid"])
                for fmt in ("v1", "v2"):
                    for state, reason in (("aborted", "operator_abort"), ("running", "unfinished_slot")):
                        with self.subTest(fmt=fmt, state=state):
                            exported = export_bundle(store, fmt)
                            if state == "aborted":
                                exported["journal"]["slot"][-1].update(kind="abort", payload={
                                    "reason_code": "operator_abort", "reason": "Synthetic stop before finish"})
                            else:
                                exported["journal"]["slot"].pop()
                            rechain_fixture(exported)
                            replayed = replay_export(exported)
                            trial = replayed["trials"][0]
                            self.assertEqual(trial["state"], state)
                            self.assertEqual(trial["score"]["reason"], "unfinished_slot")
                            self.assert_unavailable(trial["score"]["dimension_accuracy"], reason)
                            self.assertEqual(replayed["dimension_accuracy"][0]["dimension_accuracy"],
                                             trial["score"]["dimension_accuracy"])
            finally:
                store.close()
