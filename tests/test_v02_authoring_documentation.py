"""Authoring pipeline discoverability and provenance; no corpus content."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/v0.2"


class AuthoringDocumentationTests(unittest.TestCase):
    def test_pipeline_index_links_to_all_artifacts_and_links_resolve(self):
        index = (DOCS / "README.md").read_text(encoding="utf-8")
        for name in ("AUTHORING_BRIEF.md", "AUTHORING_FORMAT_V1.md", "AUTHORING_MAPPER.md", "CORPUS_AGGREGATION.md",
                     "CORPUS_FREEZE.md", "AUTHORING_RUNBOOK.md", "STATE_RECORDS_V1.md", "authoring-pipeline-run.md"):
            self.assertIn("](" + name + ")", index)
        for path in [DOCS / n for n in ("README.md", "AUTHORING_FORMAT_V1.md", "AUTHORING_MAPPER.md", "CORPUS_AGGREGATION.md", "CORPUS_FREEZE.md", "AUTHORING_RUNBOOK.md")]:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if not target.startswith(("https:", "http:")):
                    self.assertTrue((path.parent / target.split("#")[0]).is_file(), (path, target))

    def test_provenance_and_main_index(self):
        provenance = (DOCS / "PROVENANCE.md").read_text(encoding="utf-8")
        self.assertIn("Codex-authored tooling under user authorization", provenance)
        self.assertIn("no corpus content", provenance)
        self.assertIn("v02-authoring-pipeline", provenance)
        self.assertIn("v0.2/README.md", (ROOT / "docs/INDEX.md").read_text(encoding="utf-8"))
