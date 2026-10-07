"""Procedure completeness checks; no author session is launched."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AuthoringRunbookTests(unittest.TestCase):
    def test_isolated_launch_and_records(self):
        text = (ROOT / "docs/v0.2/AUTHORING_RUNBOOK.md").read_text(encoding="utf-8")
        for term in ("fresh model session", "only AUTHORING_BRIEF.md", "no repository access", "S2", "S3", "S4",
                     "author", "model", "session", "date", "prior_runs", "unknown", "non-canonical"):
            self.assertIn(term, text)
        self.assertIn("<PRIVATE_CORPUS_ROOT_OUTSIDE_PUBLIC_REPOSITORIES>", text)
        self.assertIn("Do not create this placeholder path", text)

    def test_dev_freeze_eval_and_review_gates(self):
        text = (ROOT / "docs/v0.2/AUTHORING_RUNBOOK.md").read_text(encoding="utf-8")
        for term in ("development", "evaluation", "freeze", "etps_v02.intake.authoring", "etps_v02.intake.mapper",
                     "etps_v02.intake.state_records", "etps_v02.intake.corpus_freeze", "human cross-check",
                     "ruling 4", "defect blocks release", "S1", "S16", "clarification_unrepresentable"):
            self.assertIn(term, text)
        self.assertLess(text.index("1. Development set"), text.index("2. Evaluation set"))
        self.assertIn("never used to drop or adjust tasks", text)
