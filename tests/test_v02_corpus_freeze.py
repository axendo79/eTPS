"""SYNTHETIC corpus-freeze records; no actual corpus or review attestation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document
from etps_v02.intake.mapper import map_authoring
from etps_v02.intake.corpus_freeze import FreezeError, create_freeze, verify_freeze
from etps_v02.workload import decode, encode, sha


def synthetic_freezable(dataset="development", development=None):
    doc = synthetic_document()
    doc["dataset"] = dataset
    if dataset == "evaluation":
        doc["tasks"][0]["id"] = "SYNTHETIC-eval-task"
    files = map_authoring(encode(doc))
    files["authoring-brief.md"] = (Path(__file__).resolve().parents[1] / "docs/v0.2/AUTHORING_BRIEF.md").read_bytes()
    files["authorship.json"] = encode({"version": "author-session-v1", "author": "SYNTHETIC author", "model": "SYNTHETIC model",
        "session": "SYNTHETIC fresh session", "date": "SYNTHETIC date", "affiliations": ["SYNTHETIC only"],
        "prior_exposure": {"declarant": "SYNTHETIC author", "date": "SYNTHETIC date", "corpus_version": "SYNTHETIC-version",
            "prior_runs": "unknown", "known_runs": [], "inspection": "SYNTHETIC none", "revisions": []}})
    index = decode(files["bundle.json"])
    if development is not None:
        files["development-freeze.json"] = development
    files["settings.json"] = encode({"version": "corpus-settings-v1", "dataset": dataset,
        "counts": index["counts"], "parameters": {"SYNTHETIC": "not experiment budgets"},
        "development_freeze_sha256": sha(development) if development else None})
    synthetic_review(files)
    return files


def synthetic_review(files):
    files["review.json"] = encode({"version": "corpus-review-v1", "reviewer": "SYNTHETIC reviewer", "date": "SYNTHETIC date",
        "obligations_answer_keys_cross_checked": True, "defects": [],
        "artifacts": {name: sha(raw) for name, raw in files.items() if name != "review.json"}})


class CorpusFreezeTests(unittest.TestCase):
    def test_freeze_verify_deterministic_and_complete_inventory(self):
        files = synthetic_freezable()
        original = copy.deepcopy(files)
        raw = create_freeze(files, "SYNTHETIC-dev-v1", "development", "SYNTHETIC freeze instant")
        self.assertEqual(files, original)
        self.assertEqual(raw, create_freeze(files, "SYNTHETIC-dev-v1", "development", "SYNTHETIC freeze instant"))
        result = verify_freeze(files, raw)
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["semantics_verified"])
        record = decode(raw)
        self.assertEqual({a["path"] for a in record["artifacts"]}, set(files))
        for role in ("manifest", "sidecar", "keys", "predictions", "field_map", "derivation", "brief", "counts", "review", "authorship", "settings"):
            self.assertIn(role, {a["role"] for a in record["artifacts"]})

    def test_every_later_byte_change_addition_deletion_and_record_change_refuses(self):
        files = synthetic_freezable()
        raw = create_freeze(files, "SYNTHETIC-dev", "development", "SYNTHETIC time")
        for name in files:
            changed = dict(files)
            changed[name] += b" "
            with self.subTest(name=name), self.assertRaises(FreezeError) as caught:
                verify_freeze(changed, raw)
            self.assertEqual(caught.exception.code, "bundle_changed")
        for changed in (dict(files, **{"SYNTHETIC-extra.json": b'{}'}), {k: v for k, v in files.items() if k != "source.json"}):
            with self.assertRaises(FreezeError) as caught:
                verify_freeze(changed, raw)
            self.assertEqual(caught.exception.code, "bundle_changed")
        record = decode(raw)
        record["release_id"] = "SYNTHETIC-tampered"
        with self.assertRaises(FreezeError) as caught:
            verify_freeze(files, encode(record))
        self.assertEqual(caught.exception.code, "freeze_record")

    def test_review_and_defects_gate_release(self):
        for mutate, code in ((lambda f: f.pop("review.json"), "missing_artifact"),
            (lambda f: f.__setitem__("review.json", encode(dict(decode(f["review.json"]), defects=["SYNTHETIC mismatch"]))), "review_defect"),
            (lambda f: f.__setitem__("review.json", encode(dict(decode(f["review.json"]), obligations_answer_keys_cross_checked=False))), "review_required"),
            (lambda f: f.__setitem__("source.json", f["source.json"] + b" "), "derived_bundle")):
            files = synthetic_freezable()
            mutate(files)
            with self.subTest(code=code), self.assertRaises(FreezeError) as caught:
                create_freeze(files, "SYNTHETIC", "development", "SYNTHETIC time")
            self.assertEqual(caught.exception.code, code)

    def test_separate_dev_eval_and_required_development_binding(self):
        dev = synthetic_freezable()
        dev_record = create_freeze(dev, "SYNTHETIC-dev", "development", "SYNTHETIC time")
        evaluation = synthetic_freezable("evaluation", dev_record)
        eval_record = create_freeze(evaluation, "SYNTHETIC-eval", "evaluation", "SYNTHETIC later")
        self.assertEqual(verify_freeze(evaluation, eval_record)["dataset"], "evaluation")
        for files, dataset in ((dev, "evaluation"), (evaluation, "development"), (synthetic_freezable("evaluation"), "evaluation")):
            with self.assertRaises(FreezeError) as caught:
                create_freeze(files, "SYNTHETIC", dataset, "SYNTHETIC time")
            self.assertEqual(caught.exception.code, "dataset_separation")
        reused = synthetic_freezable("evaluation", dev_record)
        doc = decode(reused["source.json"])
        doc["tasks"][0]["id"] = "SYNTHETIC-task"
        mapped = map_authoring(encode(doc))
        reused.update(mapped)
        reused["settings.json"] = encode(dict(decode(reused["settings.json"]), counts=decode(mapped["bundle.json"])["counts"]))
        synthetic_review(reused)
        with self.assertRaises(FreezeError) as caught:
            create_freeze(reused, "SYNTHETIC", "evaluation", "SYNTHETIC time")
        self.assertEqual(caught.exception.code, "dataset_separation")

    def test_counts_review_hashes_author_record_and_unsafe_paths_refuse(self):
        cases = []
        f = synthetic_freezable()
        s = decode(f["settings.json"])
        s["counts"]["tasks"] = 999
        f["settings.json"] = encode(s)
        synthetic_review(f)
        cases.append((f, "counts_mismatch"))
        f = synthetic_freezable()
        f["authorship.json"] += b" "
        cases.append((f, "review_binding"))
        f = synthetic_freezable()
        del f["authorship.json"]
        cases.append((f, "missing_artifact"))
        f = synthetic_freezable()
        f["../SYNTHETIC.json"] = b'{}'
        cases.append((f, "artifact_path"))
        for files, code in cases:
            with self.subTest(code=code), self.assertRaises(FreezeError) as caught:
                create_freeze(files, "SYNTHETIC", "development", "SYNTHETIC time")
            self.assertEqual(caught.exception.code, code)

    def test_cli_exclusive_record_and_detected_changes(self):
        files = synthetic_freezable()
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            folder = Path(temp)
            bundle, record = folder / "bundle", folder / "SYNTHETIC-freeze.json"
            bundle.mkdir()
            for name, raw in files.items():
                (bundle / name).write_bytes(raw)
            args = [sys.executable, "-B", "-m", "etps_v02.intake.corpus_freeze", "create", str(bundle), str(record),
                    "--release", "SYNTHETIC", "--dataset", "development", "--frozen-at", "SYNTHETIC time"]
            created = subprocess.run(args, cwd=root, capture_output=True)
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            again = subprocess.run(args, cwd=root, capture_output=True)
            self.assertEqual(again.returncode, 2)
            self.assertEqual(json.loads(again.stdout)["code"], "freeze_exists")
            check = [sys.executable, "-B", "-m", "etps_v02.intake.corpus_freeze", "verify", str(bundle), str(record)]
            self.assertEqual(subprocess.run(check, cwd=root, capture_output=True).returncode, 0)
            (bundle / "source.json").write_bytes(b"SYNTHETIC changed")
            checked = subprocess.run(check, cwd=root, capture_output=True)
            self.assertEqual(checked.returncode, 2)
            self.assertEqual(json.loads(checked.stdout)["code"], "bundle_changed")
