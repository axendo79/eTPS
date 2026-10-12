"""Neutral brief checks; no corpus content is authored here."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = (("AUTHORING_BRIEF.md", "authoring-brief-v1"),
          ("AUTHORING_BRIEF_V2.md", "authoring-brief-v2"))


def forbidden(text, terms):
    return [term for term in terms if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)]


class BriefTests(unittest.TestCase):
    def test_no_maintainer_review_or_governance_material(self):
        for filename, _ in BRIEFS:
            with self.subTest(brief=filename):
                brief = (ROOT / "docs/v0.2" / filename).read_text(encoding="utf-8")
                self.assertEqual(forbidden(brief, ["reviewer", "governance", "canonical", "affiliation", "conflict", "attestation"]), [])

    def test_brief_is_self_contained_and_neutral(self):
        terms = [s.strip() for s in (ROOT / "tools/brief_denylist.txt").read_text(encoding="utf-8").splitlines()
                 if s.strip() and not s.startswith("#")]
        for filename, version in BRIEFS:
            with self.subTest(brief=filename):
                brief = (ROOT / "docs/v0.2" / filename).read_text(encoding="utf-8")
                self.assertEqual(forbidden(brief, terms), [])
                self.assertNotRegex(brief, r"\]\(|https?://")
                for family in range(1, 10):
                    self.assertIn("F" + str(family), brief)
                for term in ("authoring-v1", version, "field_map", "predictions", "development", "evaluation"):
                    self.assertIn(term, brief)

    def test_denylist_catches_required_terms_without_substring_false_positives(self):
        terms = (ROOT / "tools/brief_denylist.txt").read_text(encoding="utf-8").splitlines()
        required = ["projector", "candidate", "belief", "supersede", "live", "retained", "nyx", "bridge", "eTPS run"]
        self.assertTrue(set(required) <= set(terms))
        self.assertEqual(forbidden("SYNTHETIC: Projector, NYX, eTPS run", terms), [t for t in terms if t in {"projector", "nyx", "eTPS run", "eTPS"}])
        self.assertEqual(forbidden("delivery and lively conversation", ["live"]), [])
