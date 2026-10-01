"""Planned versus attempted acceptance denominators."""
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.persistence import Store
from etps_v02.runner import report, run_offline
from etps_v02.scorer import summarize
from test_v02_runner import bundle


class AcceptanceRateTests(unittest.TestCase):
    def test_complete_incomplete_and_empty(self):
        accepted = {"manifest_sha256": "synthetic", "accepted": True, "measurement_valid": True,
                    "I": 1, "R": 0, "RR": Fraction(0), "wall_seconds": None}
        failed = dict(accepted, accepted=False)
        for results, planned, rate, reason, attempted in (
                ([accepted, failed], 2, Fraction(1, 2), None, Fraction(1, 2)),
                ([accepted], 4, None, "unattempted_slots", Fraction(1)),
                ([], 0, None, "no_trials", None),
                ([], 4, None, "unattempted_slots", None)):
            with self.subTest(planned=planned, attempted=len(results)):
                actual = summarize(results, planned=planned)
                self.assertEqual(actual["acceptance_rate"], rate)
                self.assertEqual(actual["acceptance_rate_unavailable_reason"], reason)
                self.assertEqual(actual["acceptance_rate_attempted"], attempted)

    def test_eight_slot_report_one_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store.create(Path(temp) / "plan.db", *bundle(slots=8))
            try:
                run_offline(store, "slot-0")
                result = report(store)
                self.assertEqual((result["planned"], result["attempted"]), (8, 1))
                group = next(g for g in result["summaries"] if g["arm"] == "baseline")
                self.assertEqual(group["planned"], 4)
                self.assertIsNone(group["acceptance_rate"])
                self.assertEqual(group["acceptance_rate_unavailable_reason"], "unattempted_slots")
                self.assertEqual(group["acceptance_rate_attempted"], 1)
            finally:
                store.close()
