"""Maintainer procedure checks; examples remain explicitly SYNTHETIC."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

DOCS = Path(__file__).resolve().parents[1] / "docs/v0.2"


class AuthoringRulingsDocumentationTests(unittest.TestCase):
    def test_documented_extension_shape_and_runbook_dispatch_agree(self):
        text = (DOCS / "STATE_RECORDS_V1.md").read_text(encoding="utf-8")
        extension = text.split("## state-records-v1.1", 1)[1]
        fields = json.loads(re.findall(r"```json\s*(.*?)\s*```", extension, re.S)[0])
        self.assertEqual(set(fields), {"status", "missing_item"})
        for query in fields.values():
            self.assertEqual(set(query), {"record", "kind", "missing_item", "projection"})
            self.assertEqual(query["kind"], "missing_information")
            self.assertIn("SYNTHETIC", query["record"])
            self.assertIn("SYNTHETIC", query["missing_item"])
        self.assertEqual(fields["status"]["projection"], "status")
        self.assertEqual(fields["missing_item"]["projection"], "identifier")
        self.assertIn("missing_item_established", extension)
        self.assertIn("missing_information_answer", extension)
        runbook = (DOCS / "AUTHORING_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("-m etps_v02.intake.state_records_v11 --manifest", runbook)
        self.assertIsNotNone(importlib.util.find_spec("etps_v02.intake.state_records_v11"))
        self.assertIn("missing item's earlier source history", runbook)
        self.assertIn("defect blocks release", runbook)

    def test_attributed_rulings_refusals_and_completed_handoff(self):
        provenance = (DOCS / "PROVENANCE.md").read_text(encoding="utf-8")
        self.assertIn("## Maintainer authoring rulings (2026-10-06)", provenance)
        self.assertIn("answerability only", provenance)
        self.assertIn("no corpus content", provenance)
        for name in ("AUTHORING_FORMAT_V1.md", "AUTHORING_MAPPER.md"):
            text = (DOCS / name).read_text(encoding="utf-8")
            for code in ("delayed_obligation", "multi_failure_recovery", "alternative_answers", "missing_information"):
                self.assertIn(code, text)
        handoff = (DOCS / "authoring-pipeline-run.md").read_text(encoding="utf-8").split("## Authoring rulings", 1)[1]
        for task in ("R1", "R2", "R3", "R4"):
            self.assertIn("| " + task + " | done |", handoff)
        self.assertIn("STUCK: none", handoff)
        self.assertIn("Skipped: none", handoff)
