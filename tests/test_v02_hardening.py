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
from etps_v02.scorer import InvalidRecord, union_length, validate
from etps_v02.workload import decode, encode, raw_response, script_responses, validate_bundle
from test_v02_runner import bundle, response
from test_v02_scorer import fixture, user


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
