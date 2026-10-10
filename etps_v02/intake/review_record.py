"""Assemble a declared human review, checking freeze admission in a temporary copy."""
import argparse
from pathlib import Path
import sys
import tempfile

from ..scorer import InvalidRecord
from ..workload import decode, encode, sha
from . import corpus_freeze
from .state_records import IntakeError, read_bounded
from ._review_support import CHECKS, document

VERSION = "review-record-v1"
INPUT_VERSION = "review-input-v1"
INPUT_FIELDS = {"version", "source_sha256", "reviewer", "date", "tasks", "defects"}


class ReviewError(IntakeError):
    pass


def need(condition, code, path, detail):
    if not condition:
        raise ReviewError(code, path, detail)


def closed(value, fields, path):
    need(type(value) is dict and value.keys() == set(fields), "review_input_fields", path, "closed required fields differ")


def declared_text(value, path):
    need(type(value) is str and bool(value.strip()), "review_input_type", path, "nonblank declaration required")


def checked_input(raw, files):
    try:
        review = decode(raw)
    except InvalidRecord as exc:
        raise ReviewError("review_input_json", "review-input", "invalid strict UTF-8 JSON") from exc
    closed(review, INPUT_FIELDS, "review-input")
    need(review["version"] == INPUT_VERSION, "review_input_version", "review-input.version", "unsupported review input")
    need("source.json" in files, "missing_artifact", "source.json", "source required")
    need(review["source_sha256"] == sha(files["source.json"]), "source_binding", "review-input.source_sha256", "review source bytes differ from bundle source.json")
    doc = document(files["source.json"])
    declared_text(review["reviewer"], "review-input.reviewer")
    declared_text(review["date"], "review-input.date")
    need(type(review["defects"]) is list, "review_input_type", "review-input.defects", "explicit defects array required")
    need(not review["defects"], "review_defect", "review-input.defects", "every listed defect blocks assembly; no defects are dropped")
    # An older bundle declaration must not be used to silently erase a defect.
    if "review.json" in files:
        try:
            previous = decode(files["review.json"])
        except InvalidRecord as exc:
            raise ReviewError("review_input_json", "review.json", "existing review is invalid") from exc
        need(type(previous) is dict and type(previous.get("defects")) is list,
             "review_input_type", "review.json.defects", "existing review must have explicit defects")
        need(not previous["defects"], "review_defect", "review.json.defects", "existing review defects must be resolved through separately retained evidence")
    need(type(review["tasks"]) is list, "review_input_type", "review-input.tasks", "per-task array required")
    task_ids = []
    for i, task in enumerate(review["tasks"]):
        path = f"review-input.tasks[{i}]"
        closed(task, ("task_id", "checks", "notes"), path)
        declared_text(task["task_id"], path + ".task_id")
        closed(task["checks"], CHECKS, path + ".checks")
        need(all(value is True for value in task["checks"].values()), "review_unchecked", path + ".checks", "every item must be the JSON boolean true")
        need(type(task["notes"]) is str, "review_input_type", path + ".notes", "notes must be a string (empty permitted)")
        task_ids.append(task["task_id"])
    expected_ids = {task["id"] for task in doc["tasks"]}
    need(len(task_ids) == len(set(task_ids)) and set(task_ids) == expected_ids,
         "review_tasks", "review-input.tasks", "every source task exactly once; no extra or missing task")
    return review, doc


def validate_in_copy(files, record, dataset, temporary_root):
    """Run the unchanged freeze gate over actual copied files, without a receipt.

    No freeze time or release ID is invented. The existing admission function is
    the complete gate used by create_freeze; it re-derives the mapper/sidecars.
    """
    candidate = dict(files, **{"review.json": record})
    corpus_freeze.validate_files(candidate)
    with tempfile.TemporaryDirectory(prefix="etps-review-record-", dir=temporary_root) as temp:
        root = Path(temp)
        for name, raw in candidate.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
        copied = corpus_freeze.read_directory(root)
        need(copied == candidate, "bundle_changed", "temporary-copy", "temporary copy differs")
        corpus_freeze.admission(copied, dataset)


def assemble_review(input_raw, bundle, output):
    """Create one new review record outside the unmodified source bundle."""
    root, target = Path(bundle), Path(output)
    need(not target.resolve().is_relative_to(root.resolve()), "output_path", str(target), "output must be outside the bundle")
    need(not target.exists() and not target.is_symlink(), "output_exists", str(target), "refuse an existing output")
    temporary_root = Path(tempfile.gettempdir()).resolve()
    need(not temporary_root.is_relative_to(root.resolve()), "temporary_path", str(temporary_root), "temporary copy must stay outside the bundle")
    files = corpus_freeze.read_directory(root)
    review, doc = checked_input(input_raw, files)
    record = encode({"version": "corpus-review-v1", "reviewer": review["reviewer"], "date": review["date"],
        "obligations_answer_keys_cross_checked": True, "defects": review["defects"],
        "artifacts": {name: sha(raw) for name, raw in files.items() if name != "review.json"}})
    validate_in_copy(files, record, doc["dataset"], temporary_root)
    need(corpus_freeze.read_directory(root) == files, "bundle_changed", str(root), "bundle changed during review assembly")
    try:
        with target.open("xb") as stream:
            stream.write(record)
    except FileExistsError as exc:
        raise ReviewError("output_exists", str(target), "refuse an existing output") from exc
    # A late mutation or interrupted write must never receive a success receipt.
    need(corpus_freeze.read_directory(root) == files, "bundle_changed", str(root), "bundle changed during output creation")
    need(read_bounded(target, corpus_freeze.MAX_FILE_BYTES) == record, "output_changed", str(target), "written review bytes differ")
    return {"version": VERSION, "status": "assembled", "source_sha256": review["source_sha256"],
        "artifacts": len(files) - int("review.json" in files), "freeze_validation": "accepted", "semantics_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_input")
    parser.add_argument("bundle")
    parser.add_argument("output", help="new review.json path outside the bundle; exclusive creation")
    args = parser.parse_args()
    try:
        result = assemble_review(read_bounded(args.review_input, corpus_freeze.MAX_FILE_BYTES), args.bundle, args.output)
    except IntakeError as exc:
        result = {"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}
    except OSError:
        result = {"version": VERSION, "status": "rejected", "code": "file_unavailable"}
    sys.stdout.buffer.write(encode(result) + b"\n")
    return 0 if result["status"] == "assembled" else 2


if __name__ == "__main__":
    raise SystemExit(main())
