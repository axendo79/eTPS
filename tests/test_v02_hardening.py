"""Focused hardening regressions; synthetic fixtures, never model evidence."""
import base64
import copy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import limits
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report, run_offline
from etps_v02.runner import implementation, replay_slot
from etps_v02.scorer import InvalidRecord, union_length, validate
from etps_v02.workload import decode, encode, raw_response, script_responses, validate_bundle
from test_v02_runner import bundle, response
from test_v02_scorer import fixture, user, probe


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.serial = 0

    def create(self, **kwargs):
        self.serial += 1
        plan, artifacts = bundle(**kwargs)
        store = Store.create(Path(self.temp.name) / f"case-{self.serial}.db", plan, artifacts)
        self.addCleanup(store.close)
        return store

    def test_v07_nonbyte_inputs_still_raise_invalid_record(self):
        for raw in (None, 1, "{}", [], {}):
            for call in (lambda: validate_bundle(raw, {}), lambda: script_responses(raw)):
                with self.subTest(raw=raw), self.assertRaises(InvalidRecord):
                    call()

    def test_v07_interval_union_matches_old_byte_sets(self):
        rng = random.Random(729)
        for _ in range(500):
            spans = []
            for _ in range(rng.randrange(40)):
                a = rng.randrange(100)
                spans.append((a, rng.randrange(a + 1, 150)))
            expected = len({p for a, b in spans for p in range(a, b)})
            self.assertEqual(union_length(spans), expected)
        self.assertEqual(union_length([(0, 10**12), (3, 10**12 + 1)]), 10**12 + 1)

    def test_v07_file_limits_check_before_open_and_include_boundary(self):
        path = Path(self.temp.name) / "input.json"
        path.write_bytes(b'{}')
        for name in ("MAX_PLAN_BYTES", "MAX_ARTIFACT_BYTES", "MAX_EXPORT_BYTES"):
            with self.subTest(name=name), patch.object(limits, name, 2):
                self.assertEqual(limits.read_file(path, name), b'{}')
            with patch.object(limits, name, 1), patch.object(Path, "open") as opened:
                with self.assertRaisesRegex(InvalidRecord, name):
                    limits.read_file(path, name)
                opened.assert_not_called()

    def test_v07_in_memory_admission_limits(self):
        plan, artifacts = bundle()
        for name, value in (("MAX_PLAN_BYTES", len(plan) - 1),
                            ("MAX_ARTIFACT_BYTES", max(map(len, artifacts.values())) - 1),
                            ("MAX_PLAN_SLOTS", 1), ("MAX_SCRIPT_RESPONSES", 1)):
            with self.subTest(name=name), patch.object(limits, name, value):
                with self.assertRaisesRegex(InvalidRecord, name):
                    validate_bundle(plan, artifacts)
        m = fixture()
        with patch.object(limits, "MAX_MANIFEST_NODES", len(m["nodes"]) - 1):
            with self.assertRaisesRegex(InvalidRecord, "MAX_MANIFEST_NODES"):
                validate(m)
            self.assertEqual(validate(m, authoring=False)[0]["limit"], "MAX_MANIFEST_NODES")
        raw = base64.b64encode(b'abcd').decode()
        with patch.object(limits, "MAX_RESPONSE_BYTES", 3):
            with self.assertRaisesRegex(InvalidRecord, "MAX_RESPONSE_BYTES"):
                raw_response(raw)
        with patch.object(limits, "MAX_RESPONSE_BYTES", 4):
            self.assertEqual(raw_response(raw), b'abcd')

    def test_v07_depth_checked_before_json_parser(self):
        with patch.object(limits, "MAX_JSON_NESTING_DEPTH", 3):
            self.assertEqual(decode(b'[[[0]]]'), [[[0]]])
            self.assertEqual(decode(b'{"x":"[\\\"{{{{"}'), {"x": '["{{{{'})
            with patch("etps_v02.workload.json.loads") as loads:
                with self.assertRaisesRegex(InvalidRecord, "MAX_JSON_NESTING_DEPTH"):
                    decode(b'[[[[0]]]]')
                loads.assert_not_called()
            with self.assertRaisesRegex(InvalidRecord, "MAX_JSON_NESTING_DEPTH"):
                validate(fixture())

    def test_v07_old_evidence_over_admission_limits_warns_and_replays(self):
        store = self.create(slots=1)
        run_offline(store, "slot-0")
        exported = export_bundle(store)
        with patch.object(limits, "MAX_PLAN_SLOTS", 0), patch.object(limits, "MAX_RESPONSE_BYTES", 1):
            checked = replay_export(exported)
            self.assertEqual(checked["accepted"], 1)
            self.assertIn("legacy_safety_limit: MAX_PLAN_SLOTS", checked["warnings"])
            self.assertIn("legacy_safety_limit: MAX_RESPONSE_BYTES", checked["warnings"])

    def test_v07_append_does_not_scan_prefix_and_reopen_detects_middle_corruption(self):
        store = self.create(slots=1)
        store.append("slot-0", "start", {})
        with patch.object(store, "entries", side_effect=AssertionError("prefix reread")):
            for i in range(8):
                store.append("slot-0", "event", {"index": i})
        store.db.execute("DROP TRIGGER immutable_journal_UPDATE")
        store.db.execute("UPDATE journal SET payload=? WHERE slot='slot-0' AND seq=4", (b'{}',))
        store.db.commit()
        with self.assertRaisesRegex(InvalidRecord, "integrity"):
            Store(store.path)
        with self.assertRaisesRegex(InvalidRecord, "integrity"):
            export_bundle(store)

    def test_v07_append_detects_tail_head_mismatch_and_rolls_back(self):
        store = self.create(slots=1)
        store.append("slot-0", "start", {})
        store.db.execute("UPDATE heads SET hash='damaged'")
        store.db.commit()
        with self.assertRaisesRegex(InvalidRecord, "head"):
            store.append("slot-0", "event", {})
        self.assertEqual(store.db.execute("SELECT count(*) FROM journal").fetchone()[0], 1)

    def test_v07_bounded_scaling_chain_and_journal(self):
        m = {"unit": "utf8_bytes", "start": "n0", "obligations": {}, "nodes": {}}
        for i in range(4999):
            m["nodes"][f"n{i}"] = user("", f"n{i + 1}")
        m["nodes"]["n4999"] = {"kind": "terminal", "accepted": True}
        self.assertEqual(validate(m), [])
        m["nodes"]["n4999"] = user("", "n0")
        with self.assertRaisesRegex(InvalidRecord, "cyclic"):
            validate(m)
        store = self.create(slots=1)
        store.append("slot-0", "start", {})
        with patch.object(store, "entries", side_effect=AssertionError("prefix reread")):
            for i in range(2000):
                store.append("slot-0", "event", {"index": i})
        self.assertEqual(len(store.entries("slot-0")), 2001)
        reopened = Store(store.path)
        try:
            self.assertEqual(len(reopened.entries("slot-0")), 2001)
        finally:
            reopened.close()

    def test_v09_identity_covers_all_modules_and_normalizes_lf(self):
        actual = implementation()
        expected = sorted(p.name for p in Path("etps_v02").glob("*.py"))
        self.assertEqual(list(actual["files_sha256"]), expected)
        self.assertTrue(actual["python_version"])
        self.assertTrue(actual["sqlite_version"])
        original = Path.read_bytes
        def crlf(path):
            return original(path).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        with patch.object(Path, "read_bytes", crlf):
            self.assertEqual(implementation(), actual)

    def test_v09_partial_identity_compares_only_present_keys(self):
        store = self.create(slots=1)
        old = {"scorer_sha256": implementation()["scorer_sha256"]}
        with patch("etps_v02.runner.implementation", return_value=old):
            run_offline(store, "slot-0")
        result = replay_slot(store, "slot-0")
        self.assertFalse(result["implementation_mismatch"])
        self.assertEqual(result["implementation"]["recorded"], old)
        self.assertIn("legacy_implementation_identity: partial", result["warnings"])
        self.assertTrue(result["score"]["measurement_valid"])

    def test_v09_changed_modules_and_runtime_are_named(self):
        store = self.create(slots=1)
        old = implementation()
        old["files_sha256"]["workload.py"] = "changed"
        old["files_sha256"]["persistence.py"] = "changed"
        old["python_version"] = "old"
        with patch("etps_v02.runner.implementation", return_value=old):
            run_offline(store, "slot-0")
        result = replay_slot(store, "slot-0")
        self.assertEqual(result["implementation"]["changed"],
                         ["persistence.py", "python_version", "workload.py"])
        self.assertTrue(result["score"]["measurement_valid"])
        self.assertTrue(any("workload.py" in w and "persistence.py" in w for w in result["warnings"]))

    def test_v10_single_arm_slot_accounting_is_not_comparability(self):
        store = self.create(slots=1, responses=[response()])
        before = report(store)
        self.assertFalse(before["slot_accounting_complete"])
        run_offline(store, "slot-0")
        checked = report(store)
        self.assertTrue(checked["slot_accounting_complete"])
        self.assertFalse(checked["comparison_incomplete"])
        self.assertEqual(checked["arm_pairing"]["synthetic"], {
            "arms": {"baseline": {"planned": 1, "finished": 1, "rr_available": 1}},
            "equal_planned_counts": True})
        self.assertEqual(checked["unverified_dimensions"], [
            "schedule exposure equality across arms", "mandatory assertions beyond terminal Boolean",
            "budgets", "action constraints"])

    def test_v10_unbalanced_arms_and_failed_unavailable_trials_remain(self):
        store = self.create(slots=3, responses=[response(b'{}'), response(b'{}')])
        run_offline(store, "slot-0")
        store.append("slot-1", "start", implementation())
        store.abort("slot-1", "operator_abort")
        checked = report(store)
        self.assertEqual(checked["failed"], 1)
        self.assertEqual(checked["aborted"], 1)
        self.assertEqual(checked["unattempted"], 1)
        self.assertEqual(len(checked["trials"]), 3)
        self.assertFalse(checked["slot_accounting_complete"])
        self.assertEqual(checked["arm_pairing"]["synthetic"], {
            "arms": {"baseline": {"planned": 2, "finished": 1, "rr_available": 1},
                     "memory": {"planned": 1, "finished": 0, "rr_available": 0}},
            "equal_planned_counts": False})

    def test_v10_missing_arm_for_task_is_explicit_zero(self):
        plan_raw, artifacts = bundle(slots=2)
        plan = decode(plan_raw)
        plan["tasks"]["other"] = plan["tasks"]["synthetic"]
        plan["slots"][1]["task"] = "other"
        store = Store.create(Path(self.temp.name) / "pairing.db", encode(plan), artifacts)
        self.addCleanup(store.close)
        checked = report(store)
        for task, missing in (("synthetic", "memory"), ("other", "baseline")):
            pairing = checked["arm_pairing"][task]
            self.assertFalse(pairing["equal_planned_counts"])
            self.assertEqual(pairing["arms"][missing], {"planned": 0, "finished": 0, "rr_available": 0})

    def test_v06_bypass_is_a_finding_not_an_admission_rejection(self):
        m = fixture()
        m["nodes"]["intro"]["next"] = "choice"
        m["nodes"]["choice"] = probe({"choice": "normal"}, "p1", "recover")
        findings = validate(m)
        self.assertEqual(findings, [{"code": "recovery_failure_not_dominating",
                                    "node": "recover", "failure": "p1"}])
        store = self.create(manifest=m, slots=1,
                            responses=[response(b'{"choice":"normal"}'), response(b'{}'), response()])
        trial = run_offline(store, "slot-0")
        self.assertTrue(trial["score"]["measurement_valid"])
        self.assertEqual(trial["score"]["R"], 15)
        self.assertIn("authoring_findings: recovery_failure_not_dominating", trial["warnings"])

    def test_v06_dominating_probe_and_unreachable_bypass_have_no_finding(self):
        m = fixture()
        self.assertEqual(validate(m), [])
        m["nodes"]["unused"] = user("", "recover")
        self.assertEqual(validate(m), [])
