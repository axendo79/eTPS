"""Per-arm cost diagnostics from synthetic delivery and answer responses."""
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report
from etps_v02.workload import encode
from test_v02_boundary_delivery import plan
from test_v02_live_adapter import FakeServer


ARM = "private-arm-label"


class ProcessingTotalsTests(unittest.TestCase):
    def run_case(self, *, memory=True, missing_completion=False, missing_memory=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        extra = {}

        def callback():
            extra.clear()
            extra["usage"] = {"prompt_tokens": 100, "completion_tokens": 7}
            extra["x_memory"] = {"extraction_prompt_tokens": 40,
                                 "extraction_completion_tokens": 9,
                                 "extraction_seconds": 0.25, "facts_rejected": 1}
            if len(server.seen) == 2:
                if missing_completion:
                    del extra["usage"]["completion_tokens"]
                if missing_memory:
                    del extra["x_memory"]

        with FakeServer(extra=extra, callback=callback) as server:
            p, artifacts = plan(server.url)
            if not memory:
                del p["arms"][ARM]["memory_telemetry_field"]
            store = Store.create(Path(temp.name) / "processing.db", encode(p), artifacts)
            self.addCleanup(store.close)
            trial = run_live(store, "slot", allow_live=True)
            self.assertIs(trial["score"]["accepted"], True)
            self.assertEqual(len(server.seen), 2)
        return store, report(store)

    def test_complete_memory_cost_example(self):
        _, result = self.run_case()
        costs = result["processing_totals"][ARM]
        self.assertEqual(costs["answer_and_delivery_prompt_tokens"],
                         {"numerator": 200, "coverage_count": 2, "request_count": 2, "total": 200})
        self.assertEqual(costs["answer_and_delivery_completion_tokens"],
                         {"numerator": 14, "coverage_count": 2, "request_count": 2, "total": 14})
        for key, value in (("extraction_prompt_tokens", 80), ("extraction_completion_tokens", 18),
                           ("extraction_seconds", Fraction(1, 2)), ("facts_rejected", 2)):
            self.assertEqual(costs[key], {"sum": value, "coverage_count": 2, "request_count": 2})
        self.assertEqual(costs["all_prompt_tokens"], 280)
        self.assertEqual(costs["all_completion_tokens"], 32)
        self.assertIn("self-reported", costs["definition"])

    def test_non_memory_arm_has_no_extraction_cost(self):
        _, result = self.run_case(memory=False)
        costs = result["processing_totals"][ARM]
        for key in ("extraction_prompt_tokens", "extraction_completion_tokens",
                    "extraction_seconds", "facts_rejected"):
            self.assertEqual(costs[key], "not_applicable")
        self.assertEqual(costs["all_prompt_tokens"], 200)
        self.assertEqual(costs["all_completion_tokens"], 14)
        self.assertEqual(costs["all_prompt_tokens"], costs["answer_and_delivery_prompt_tokens"]["total"])
        self.assertEqual(costs["all_completion_tokens"], costs["answer_and_delivery_completion_tokens"]["total"])

    def test_missing_completion_keeps_partial_coverage(self):
        _, result = self.run_case(missing_completion=True)
        costs = result["processing_totals"][ARM]
        self.assertIsNone(costs["all_completion_tokens"])
        self.assertEqual(costs["answer_and_delivery_completion_tokens"],
                         {"numerator": 7, "coverage_count": 1, "request_count": 2, "total": None})
        self.assertEqual(costs["all_prompt_tokens"], 280)

    def test_missing_memory_keeps_extraction_incomplete(self):
        _, result = self.run_case(missing_memory=True)
        costs = result["processing_totals"][ARM]
        self.assertEqual(costs["extraction_prompt_tokens"],
                         {"sum": 40, "coverage_count": 1, "request_count": 2})
        self.assertEqual(costs["extraction_completion_tokens"],
                         {"sum": 9, "coverage_count": 1, "request_count": 2})
        self.assertIsNone(costs["all_prompt_tokens"])
        self.assertIsNone(costs["all_completion_tokens"])

    def test_export_replay_reproduces_processing_totals(self):
        store, result = self.run_case()
        self.assertEqual(replay_export(export_bundle(store))["processing_totals"],
                         result["processing_totals"])

    def test_facts_rejected_is_in_memory_metrics(self):
        _, result = self.run_case()
        self.assertEqual(result["memory_telemetry"][ARM]["metrics"]["facts_rejected"],
                         {"sum": 2, "coverage_count": 2, "request_count": 2})


if __name__ == "__main__":
    unittest.main()
