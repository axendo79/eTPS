"""SYNTHETIC: precedence selects a recorded claim by source and value (maintainer ruling 2026-10-07)."""
import unittest

from etps_v02.intake.state_records import IntakeError, validate_state_records
from test_v02_state_records import bind, disagreement


class PrecedenceSelectionTests(unittest.TestCase):
    def selected(self, s):
        return s["records"][0]["versions"][-1]["claims"][0]

    def test_reworded_authority_still_selects_the_recorded_claim(self):
        # Authority text is descriptive; the claim is identified by its source and value.
        m, s = disagreement()
        self.selected(s)["authority"] = "synthetic claim selected by an explicit precedence decision"
        result = validate_state_records(m, bind(m, s))
        self.assertEqual(result["status"], "validated")

    def test_unrecorded_source_or_value_is_still_refused(self):
        for change in ({"source": "e2"}, {"value": "Z"}, {"value": 7}):
            with self.subTest(change=change):
                m, s = disagreement()
                self.selected(s).update(change)
                with self.assertRaises(IntakeError) as caught:
                    validate_state_records(m, bind(m, s))
                self.assertIn(caught.exception.code, {"precedence_claim", "state_claims", "claim_source"})


if __name__ == "__main__":
    unittest.main()
