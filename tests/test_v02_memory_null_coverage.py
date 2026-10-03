"""Nullable memory fields retain independent coverage; synthetic evidence only."""
import base64
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.memory_telemetry import project, summarize
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode
from test_v02_boundary_delivery import plan
from test_v02_live_adapter import FakeServer
from test_v02_session_profile import rechain


ARM = "private-arm-label"


def projection(value):
    raw = json.dumps({"x_memory": value}).encode("utf-8")
    return project({"http_body_base64": base64.b64encode(raw).decode("ascii")}, "x_memory")


class MemoryNullCoverageTests(unittest.TestCase):
    def test_null_fields_are_preserved_with_independent_coverage(self):
        value = {"extraction_prompt_tokens": None, "extraction_seconds": .25,
                 "facts_rejected": 1, "optional_diagnostic": None}
        result = projection(value)
        self.assertEqual(result, {"memory_telemetry": value, "memory_telemetry_status": "valid"})
        summary = summarize([{"status": "valid", "value": value}])
        self.assertEqual(summary["valid_count"], 1)
        self.assertEqual(summary["metrics"]["extraction_prompt_tokens"],
                         {"sum": 0, "coverage_count": 0, "request_count": 1})
        self.assertEqual(summary["metrics"]["extraction_seconds"],
                         {"sum": Fraction(1, 4), "coverage_count": 1, "request_count": 1})
        self.assertEqual(summary["metrics"]["facts_rejected"],
                         {"sum": 1, "coverage_count": 1, "request_count": 1})

    def test_strings_remain_valid_but_do_not_supply_numeric_coverage(self):
        value = {"extraction_prompt_tokens": "40", "note": " exact ", "facts_rejected": 1}
        self.assertEqual(projection(value)["memory_telemetry"], value)
        self.assertEqual(projection(value)["memory_telemetry_status"], "valid")
        summary = summarize([{"status": "valid", "value": value}])
        self.assertEqual(summary["metrics"]["extraction_prompt_tokens"]["coverage_count"], 0)
        self.assertEqual(summary["metrics"]["facts_rejected"]["coverage_count"], 1)

    def test_other_invalid_shapes_stay_invalid_even_beside_null(self):
        for value in (None, "bad", [], 3, {"tokens": None, "other": {}},
                      {"tokens": None, "other": []}, {"tokens": None, "other": True},
                      {"tokens": None, "other": "\ud800"}):
            with self.subTest(value=value):
                self.assertEqual(projection(value),
                                 {"memory_telemetry": None, "memory_telemetry_status": "invalid"})

    def test_nonfinite_numbers_stay_invalid_even_beside_null(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                self.assertEqual(projection({"tokens": None, "extraction_seconds": value})[
                    "memory_telemetry_status"], "invalid")
        raw = b'{"x_memory":{"tokens":null,"extraction_seconds":1e999}}'
        self.assertEqual(project({"http_body_base64": base64.b64encode(raw).decode()},
                                 "x_memory")["memory_telemetry_status"], "invalid")

    def run_case(self, null_key):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        extra = {}

        def callback():
            extra.clear()
            extra.update(usage={"prompt_tokens": 100, "completion_tokens": 7},
                         x_memory={"extraction_prompt_tokens": 40,
                                   "extraction_completion_tokens": 9,
                                   "extraction_seconds": .25, "facts_rejected": 1})
            if len(server.seen) == 2:
                extra["x_memory"][null_key] = None

        with FakeServer(extra=extra, callback=callback) as server:
            p, artifacts = plan(server.url)
            store = Store.create(Path(temp.name) / "null-coverage.db", encode(p), artifacts)
            self.addCleanup(store.close)
            trial = run_live(store, "slot", allow_live=True)
            self.assertTrue(trial["score"]["accepted"])
            self.assertEqual(len(server.seen), 2)
        return store, report(store)

    def test_null_token_totals_keep_other_fields_complete_and_replay(self):
        for key, partial_sum, total_key, other_total, other_value in (
            ("extraction_prompt_tokens", 40, "all_prompt_tokens", "all_completion_tokens", 32),
            ("extraction_completion_tokens", 9, "all_completion_tokens", "all_prompt_tokens", 280),
        ):
            with self.subTest(key=key):
                store, result = self.run_case(key)
                telemetry = result["memory_telemetry"][ARM]
                self.assertEqual(telemetry["valid_count"], 2)
                self.assertEqual(telemetry["invalid_count"], 0)
                costs = result["processing_totals"][ARM]
                self.assertEqual(costs[key], {"sum": partial_sum, "coverage_count": 1, "request_count": 2})
                self.assertEqual(costs["extraction_seconds"],
                                 {"sum": Fraction(1, 2), "coverage_count": 2, "request_count": 2})
                self.assertEqual(costs["facts_rejected"],
                                 {"sum": 2, "coverage_count": 2, "request_count": 2})
                self.assertIsNone(costs[total_key])
                self.assertEqual(costs[other_total], other_value)
                event = result["trials"][0]["record"]["events"][-1]
                self.assertEqual(event["memory_telemetry_status"], "valid")
                self.assertIsNone(event["memory_telemetry"][key])
                for version in ("v1", "v2"):
                    replayed = replay_export(export_bundle(store, version))
                    self.assertEqual(replayed["processing_totals"], result["processing_totals"])
                    self.assertEqual(replayed["memory_telemetry"], result["memory_telemetry"])

    def test_rehashed_null_to_zero_projection_tampering_is_rejected(self):
        store, _ = self.run_case("extraction_prompt_tokens")
        exported = export_bundle(store)
        event = next(r["payload"] for r in exported["journal"]["slot"]
                     if r["kind"] == "event" and r["payload"]["kind"] == "probe")
        event["memory_telemetry"]["extraction_prompt_tokens"] = 0
        rechain(exported)
        with self.assertRaisesRegex(InvalidRecord, "memory telemetry projection"):
            replay_export(exported)

    def test_old_invalid_null_projection_requires_recorded_revision(self):
        store, _ = self.run_case("extraction_prompt_tokens")
        exported = export_bundle(store)
        event = next(r["payload"] for r in exported["journal"]["slot"]
                     if r["kind"] == "event" and r["payload"]["kind"] == "probe")
        event.update(memory_telemetry=None, memory_telemetry_status="invalid")
        rechain(exported)
        with self.assertRaisesRegex(InvalidRecord, "memory telemetry projection"):
            replay_export(exported)


if __name__ == "__main__":
    unittest.main()
