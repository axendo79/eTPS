"""SYNTHETIC review assembly and freeze gates; simulated checks are not review."""
import copy
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_tools_fixtures import synthetic_review_document, synthetic_review_input
from test_v02_corpus_freeze import synthetic_freezable
from etps_v02.intake import corpus_freeze, review_record
from etps_v02.intake._review_support import CHECKS
from etps_v02.intake.authoring_lint import lint_authoring
from etps_v02.intake.mapper import map_authoring
from etps_v02.intake.review_sheet import render_sheet
from etps_v02.workload import decode, encode, sha


def write_bundle(directory, files):
    directory.mkdir()
    for name, raw in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


class ReviewRecordTests(unittest.TestCase):
    def fixture(self):
        files = synthetic_freezable()
        files.pop("review.json")
        raw = files["source.json"]
        return files, synthetic_review_input(raw, decode(raw), CHECKS)

    def test_author_map_lint_sheet_export_assemble_then_freeze_accepts(self):
        doc = synthetic_review_document(giveaways=True)
        raw = encode(doc)
        files, _ = self.fixture()
        files = {k: v for k, v in files.items() if k in ("authorship.json", "settings.json", "authoring-brief.md")}
        files.update(map_authoring(raw))
        settings = decode(files["settings.json"])
        settings["counts"] = decode(files["bundle.json"])["counts"]
        files["settings.json"] = encode(settings)
        report = lint_authoring(raw)
        self.assertTrue(any(f["code"] == "answer_restated_before_probe" for f in report["findings"]))
        files["review-evidence/SYNTHETIC-lint.json"] = encode(report)
        files["review-evidence/SYNTHETIC-sheet.html"] = render_sheet(raw).encode("utf-8")
        review = synthetic_review_input(raw, doc, CHECKS)
        files["review-evidence/SYNTHETIC-input.json"] = encode(review)
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-e2e-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            before = corpus_freeze.read_directory(bundle)
            result = review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(result["freeze_validation"], "accepted")
            self.assertFalse(result["semantics_verified"])
            self.assertEqual(corpus_freeze.read_directory(bundle), before)
            record = decode(output.read_bytes())
            self.assertEqual(record["artifacts"], {k: sha(v) for k, v in files.items()})
            self.assertEqual(record["reviewer"], review["reviewer"])
            self.assertEqual(record["date"], review["date"])
            self.assertEqual(record["defects"], [])
            self.assertTrue(record["obligations_answer_keys_cross_checked"])
            files["review.json"] = output.read_bytes()
            freeze = corpus_freeze.create_freeze(files, "SYNTHETIC-review-tools", "development", "SYNTHETIC freeze time")
            self.assertEqual(corpus_freeze.verify_freeze(files, freeze)["status"], "verified")

    def test_single_defect_blocks_output_and_is_never_dropped(self):
        files, review = self.fixture()
        review["defects"] = ["SYNTHETIC one unresolved mismatch"]
        original = copy.deepcopy(review)
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-defect-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            with self.assertRaises(review_record.ReviewError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "review_defect")
            self.assertFalse(output.exists())
            self.assertEqual(review, original)
            self.assertEqual(corpus_freeze.read_directory(bundle), files)

    def test_source_hash_binds_exact_bytes_even_json_whitespace_change(self):
        for change in ("hash", "source"):
            files, review = self.fixture()
            if change == "hash":
                review["source_sha256"] = "0" * 64
            else:
                files["source.json"] += b" "
            with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-hash-") as temp:
                bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
                write_bundle(bundle, files)
                with self.assertRaises(review_record.ReviewError) as caught:
                    review_record.assemble_review(encode(review), bundle, output)
                self.assertEqual(caught.exception.code, "source_binding")
                self.assertFalse(output.exists())

    def test_missing_extra_duplicate_tasks_and_unchecked_or_missing_checks_refuse(self):
        changes = [
            lambda r: r["tasks"].clear(),
            lambda r: r["tasks"].append(dict(r["tasks"][0], task_id="SYNTHETIC-extra")),
            lambda r: r["tasks"].append(copy.deepcopy(r["tasks"][0])),
            lambda r: r["tasks"][0]["checks"].__setitem__("history_matches", False),
            lambda r: r["tasks"][0]["checks"].pop("keys_exact"),
            lambda r: r["tasks"][0]["checks"].__setitem__("keys_exact", 1),
        ]
        for mutate in changes:
            files, review = self.fixture()
            mutate(review)
            with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-checks-") as temp:
                bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
                write_bundle(bundle, files)
                with self.assertRaises(review_record.ReviewError):
                    review_record.assemble_review(encode(review), bundle, output)
                self.assertFalse(output.exists())

    def test_closed_input_strict_json_types_and_blank_declarations_refuse(self):
        changes = [
            lambda r: r.__setitem__("version", "SYNTHETIC-wrong-version"),
            lambda r: r.__setitem__("defects", {}),
            lambda r: r.__setitem__("reviewer", " "),
            lambda r: r.__setitem__("date", ""),
            lambda r: r.__setitem__("SYNTHETIC_extra", True),
            lambda r: r["tasks"][0].__setitem__("notes", None),
        ]
        for mutate in changes:
            files, review = self.fixture()
            mutate(review)
            with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-shape-") as temp:
                bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
                write_bundle(bundle, files)
                with self.assertRaises(review_record.ReviewError):
                    review_record.assemble_review(encode(review), bundle, output)
                self.assertFalse(output.exists())
        files, review = self.fixture()
        raw = encode(review)
        duplicate = raw[:-1] + b',"defects":[]}'
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-json-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            with self.assertRaises(review_record.ReviewError):
                review_record.assemble_review(duplicate, bundle, output)

    def test_existing_bundle_review_defects_also_block(self):
        files, review = self.fixture()
        files["review.json"] = encode({"defects": ["SYNTHETIC earlier defect"]})
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-old-defect-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            with self.assertRaises(review_record.ReviewError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "review_defect")
            self.assertFalse(output.exists())

    def test_freeze_validator_runs_on_temporary_copy_and_rejects_changed_derived_bytes(self):
        files, review = self.fixture()
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-copy-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            original_read = corpus_freeze.read_directory
            snapshots = []
            def tracked(path):
                snapshots.append(Path(path))
                return original_read(path)
            with patch.object(corpus_freeze, "admission", wraps=corpus_freeze.admission) as admission, \
                 patch.object(corpus_freeze, "read_directory", side_effect=tracked):
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(admission.call_count, 1)
            self.assertTrue(any(p != bundle for p in snapshots))
        files["task-0001.manifest.json"] += b" "
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-derived-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            with self.assertRaises(corpus_freeze.FreezeError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "derived_bundle")
            self.assertFalse(output.exists())

    def test_output_inside_bundle_existing_output_and_snapshot_changes_refuse(self):
        files, review = self.fixture()
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-exclusive-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            for target in (bundle / "review.json", bundle / "new" / "SYNTHETIC-review.json"):
                with self.assertRaises(review_record.ReviewError) as caught:
                    review_record.assemble_review(encode(review), bundle, target)
                self.assertEqual(caught.exception.code, "output_path")
            output.write_bytes(b"SYNTHETIC preserved")
            with self.assertRaises(review_record.ReviewError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "output_exists")
            self.assertEqual(output.read_bytes(), b"SYNTHETIC preserved")
            output.unlink()
            real_admission = corpus_freeze.admission
            def changes_bundle(snapshot, dataset):
                result = real_admission(snapshot, dataset)
                (bundle / "SYNTHETIC-new.txt").write_bytes(b"SYNTHETIC changed")
                return result
            with patch.object(corpus_freeze, "admission", side_effect=changes_bundle), \
                 self.assertRaises(review_record.ReviewError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "bundle_changed")
            self.assertFalse(output.exists())

    def test_cli_assembly_and_defect_refusal(self):
        files, review = self.fixture()
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-record-cli-") as temp:
            bundle, output, input_path = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json", Path(temp) / "SYNTHETIC-input.json"
            write_bundle(bundle, files)
            input_path.write_bytes(encode(review))
            args = [sys.executable, "-B", "-m", "etps_v02.intake.review_record", str(input_path), str(bundle), str(output)]
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["freeze_validation"], "accepted")
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
            output.unlink()
            review["defects"] = ["SYNTHETIC defect"]
            input_path.write_bytes(encode(review))
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["code"], "review_defect")
            self.assertFalse(output.exists())

    def test_temporary_directory_inside_bundle_is_refused_before_copy(self):
        files, review = self.fixture()
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-temp-custody-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            with patch.object(tempfile, "gettempdir", return_value=str(bundle)), \
                 self.assertRaises(review_record.ReviewError) as caught:
                review_record.assemble_review(encode(review), bundle, output)
            self.assertEqual(caught.exception.code, "temporary_path")
            self.assertEqual(corpus_freeze.read_directory(bundle), files)
            self.assertFalse(output.exists())

    def test_evaluation_parent_and_additional_artifacts_are_bound(self):
        dev = synthetic_freezable()
        parent = corpus_freeze.create_freeze(dev, "SYNTHETIC-development", "development", "SYNTHETIC time")
        files = synthetic_freezable("evaluation", parent)
        files.pop("review.json")
        files["SYNTHETIC-extra.txt"] = b"SYNTHETIC additional evidence"
        review = synthetic_review_input(files["source.json"], decode(files["source.json"]), CHECKS)
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-eval-review-") as temp:
            bundle, output = Path(temp) / "bundle", Path(temp) / "SYNTHETIC-review.json"
            write_bundle(bundle, files)
            review_record.assemble_review(encode(review), bundle, output)
            record = decode(output.read_bytes())
            self.assertEqual(record["artifacts"]["development-freeze.json"], sha(parent))
            self.assertEqual(record["artifacts"]["SYNTHETIC-extra.txt"], sha(files["SYNTHETIC-extra.txt"]))
            files["review.json"] = output.read_bytes()
            freeze = corpus_freeze.create_freeze(files, "SYNTHETIC-evaluation", "evaluation", "SYNTHETIC time")
            self.assertEqual(corpus_freeze.verify_freeze(files, freeze)["dataset"], "evaluation")


if __name__ == "__main__":
    unittest.main()
