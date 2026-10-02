"""Automated synthetic manual-plan inputs; no human session or service."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import scorer
from etps_v02.manual_runner import run_manual
from etps_v02.persistence import Store
from etps_v02.runner import answer_from_raw, export_bundle, replay_export
from etps_v02.workload import encode
from test_v02_d10_tolerance import manifest
from test_v02_field_routing import fields_manifest
from test_v02_manual_dev import manual_bundle, paste


class ManualD10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def create(self, task):
        self.count += 1
        plan, artifacts = manual_bundle(task)
        store = Store.create(Path(self.temp.name) / f"{self.count}.db", encode(plan), artifacts)
        self.addCleanup(store.close)
        return store

    def run_script(self, store, coded):
        output = io.StringIO()
        with patch("etps_v02.adapter_openai.send", side_effect=AssertionError("manual network")):
            result = run_manual(store, "slot", allow_manual=True,
                                stdin=io.BytesIO(paste(coded) * 2), stdout=output)
        return result, output.getvalue()

    def test_alias_reproduction(self):
        store = self.create(manifest())
        result, output = self.run_script(store, b'{"value":42,"label":"Ready"}')
        self.assertIn("Class: correct", output)
        self.assertTrue(result["score"]["measurement_valid"])
        self.assertTrue(result["score"]["accepted"])
        self.assertEqual(result["score"]["result_state"], "accepted_with_format_deviation")
        self.assertEqual(replay_export(export_bundle(store))["dev_manual"]["trials"][0], result)

    def test_all_d10_answer_cases_agree(self):
        answers = [{"v": 42, "label": "Ready"}, {"value": 42, "label": "Ready"},
                   {"v": "0042", "label": "Ready"}, {"v": 42, "label": "\tREADY\r\n"},
                   {"value": "42", "label": " ready "},
                   {"v": 42, "value": 42, "label": "Ready"},
                   {"value": 42, "number": 42, "label": "Ready"}, {"value": 42},
                   {"value": 42, "label": "Ready", "extra": "x"}, {"status": "unknown"},
                   {"v": "42", "label": "Ready"}, {"v": 42, "label": "\u00a0READY\u00a0"},
                   {"v": 0}, {"value": "42", "label": " READY "}]
        answers += [{"v": v, "label": "Ready"} for v in
                    ("+42", " 42", "42 ", "4.0", "-1", "\u0664\u0662", "42\n",
                     True, 42.0, [], {}, "0" * 5000 + "42")]
        cases = [(manifest(), encode(answer), "p1") for answer in answers]
        cases.append((manifest(), b"timeout", "p1"))
        undeclared = manifest()
        undeclared["nodes"]["p1"]["fixed_value_fields"] = []
        cases.append((undeclared, encode({"v": 42, "label": "ready"}), "p1"))
        string_expected = manifest()
        string_expected["nodes"]["p1"].update(expected={"v": "42"}, fixed_value_fields=[])
        cases.append((string_expected, encode({"v": 42}), "p1"))
        fields = fields_manifest()
        fields["answer_tolerance"] = "d10-v1"
        fields["nodes"]["p"].update(key_aliases={"a": ["alpha"]}, fixed_value_fields=["b"])
        cases.append((fields, encode({"alpha": "7", "b": "wrong"}), "p"))
        for task, coded, probe in cases:
            if probe == "p1":
                task["nodes"][probe]["unknown_answers"] = [{"status": "unknown"}, {"v": "42", "label": "Ready"}]
            event = {"status": "timeout" if coded == b"timeout" else "ok",
                     "answer": None if coded == b"timeout" else answer_from_raw(coded, task.get("answer_schema"))}
            expected = scorer.classify_probe(task, task["nodes"][probe], event)
            with self.subTest(coded=coded[:100], probe=probe):
                result, output = self.run_script(self.create(task), coded)
                first = next(e for e in result["record"]["events"] if e["kind"] == "probe")
                self.assertEqual(first["outcome"], expected)
                self.assertIn("Class: " + expected, output)
                classification = next(c for c in result["score"]["classifications"] if c["node"] == probe)
                self.assertEqual(classification["class"], expected)

    def test_historical_strict_manual_journal_rejected(self):
        store = self.create(manifest())
        def strict(task, node, event):
            return scorer.classify(event, node["expected"], node["unknown_answers"], task.get("answer_schema"))
        with patch("etps_v02.manual_runner.scorer.classify_probe", side_effect=strict):
            self.run_script(store, b'{"value":42,"label":"Ready"}')
            exported = export_bundle(store)
        with self.assertRaisesRegex(scorer.InvalidRecord, "manual branch mismatch"):
            replay_export(exported)
