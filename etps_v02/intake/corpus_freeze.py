"""Hash exact corpus bundle bytes; require declared review, never prove semantics."""
import argparse
import json
from pathlib import Path, PurePosixPath

from ..scorer import InvalidRecord
from ..workload import decode, encode, sha
from .mapper import map_authoring, recover_source
from .state_records import IntakeError, read_bounded

VERSION = "corpus-freeze-v1"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_FILES = 4096
RECORD_FIELDS = {"version", "release_id", "dataset", "frozen_at", "brief_version", "authoring_format_version",
                 "brief_sha256", "source_sha256", "task_ids", "counts", "artifacts", "record_sha256"}
REQUIRED = {"source.json", "bundle.json", "authoring-brief.md", "review.json", "authorship.json", "settings.json"}


class FreezeError(IntakeError):
    pass


def need(condition, code, path, detail):
    if not condition:
        raise FreezeError(code, path, detail)


def closed(value, keys, path):
    need(type(value) is dict and value.keys() == set(keys), "record_fields", path, "closed required fields differ")


def nonempty(value, path):
    need(type(value) is str and bool(value), "record_type", path, "expected nonempty string")


def json_file(files, name):
    try:
        return decode(files[name])
    except (KeyError, InvalidRecord) as exc:
        raise FreezeError("record_json", name, "missing or invalid strict JSON") from exc


def validate_files(files):
    need(type(files) is dict and all(type(k) is str and type(v) is bytes for k, v in files.items()),
         "artifact_type", "bundle", "expected relative filename to exact bytes map")
    need(len(files) <= MAX_FILES and sum(len(v) for v in files.values()) <= MAX_BUNDLE_BYTES,
         "safety_limit", "bundle", "bundle admission ceiling")
    for name, raw in files.items():
        path = PurePosixPath(name)
        need(bool(name) and not path.is_absolute() and ".." not in path.parts and ":" not in name and "\\" not in name
             and str(path) == name and name != ".", "artifact_path", name, "canonical relative path required")
        need(len(raw) <= MAX_FILE_BYTES, "safety_limit", name, "artifact admission ceiling")


def role(name, index):
    fixed = {"bundle.json": "counts", "source.json": "source", "authoring-brief.md": "brief",
             "review.json": "review", "authorship.json": "authorship", "settings.json": "settings",
             "development-freeze.json": "development_freeze"}
    if name in fixed:
        return fixed[name]
    for item in index["tasks"]:
        for kind in ("manifest", "sidecar", "keys", "predictions", "field_map", "derivation", "intake"):
            if item[kind] == name:
                return kind
    return "additional_frozen_artifact"


def checked_record(raw):
    try:
        record = decode(raw)
        closed(record, RECORD_FIELDS, "freeze")
        need(record["version"] == VERSION, "freeze_record", "freeze.version", "unsupported record version")
        payload = {k: v for k, v in record.items() if k != "record_sha256"}
        need(sha(encode(payload)) == record["record_sha256"], "freeze_record", "freeze.record_sha256", "freeze record changed")
        need(record["dataset"] in ("development", "evaluation"), "freeze_record", "freeze.dataset", "unsupported dataset")
        for key in ("release_id", "frozen_at", "brief_version", "authoring_format_version", "source_sha256", "brief_sha256"):
            nonempty(record[key], "freeze." + key)
        need(type(record["task_ids"]) is list and all(type(v) is str for v in record["task_ids"]) and
             len(record["task_ids"]) == len(set(record["task_ids"])), "freeze_record", "freeze.task_ids", "invalid task identities")
        need(type(record["counts"]) is dict and type(record["artifacts"]) is list, "freeze_record", "freeze", "invalid inventory/counts")
        for item in record["artifacts"]:
            closed(item, ("path", "sha256", "bytes", "role"), "freeze.artifacts")
            need(type(item["bytes"]) is int and item["bytes"] >= 0, "freeze_record", "freeze.artifacts", "invalid byte length")
            for key in ("path", "sha256", "role"):
                nonempty(item[key], "freeze.artifacts." + key)
        return record
    except InvalidRecord as exc:
        raise FreezeError("freeze_record", "freeze", "invalid strict JSON freeze record") from exc


def admission(files, dataset):
    validate_files(files)
    need(REQUIRED <= files.keys(), "missing_artifact", "bundle", "missing required artifact: " + ", ".join(sorted(REQUIRED - files.keys())))
    try:
        derived = map_authoring(files["source.json"])
        recover_source({name: files[name] for name in derived})
    except (IntakeError, KeyError) as exc:
        raise FreezeError("derived_bundle", "bundle", "source/derived mapping or sidecar intake failed: " + str(exc)) from exc
    index = json_file(files, "bundle.json")
    need(dataset in ("development", "evaluation") and index["dataset"] == dataset,
         "dataset_separation", "bundle.dataset", "freeze only one matching dataset")
    author = json_file(files, "authorship.json")
    closed(author, ("version", "author", "model", "session", "date", "affiliations", "prior_exposure"), "authorship")
    need(author["version"] == "author-session-v1", "record_type", "authorship.version", "unsupported author-session record")
    for key in ("author", "model", "session", "date"):
        nonempty(author[key], "authorship." + key)
    need(type(author["affiliations"]) is list and all(type(v) is str and v for v in author["affiliations"]),
         "record_type", "authorship.affiliations", "explicit affiliation list required")
    exposure = author["prior_exposure"]
    closed(exposure, ("declarant", "date", "corpus_version", "prior_runs", "known_runs", "inspection", "revisions"), "prior_exposure")
    for key in ("declarant", "date", "corpus_version", "inspection"):
        nonempty(exposure[key], "prior_exposure." + key)
    need(exposure["prior_runs"] in ("yes", "no", "unknown") and type(exposure["known_runs"]) is list and type(exposure["revisions"]) is list,
         "record_type", "prior_exposure", "explicit yes/no/unknown and run/revision lists required")
    settings = json_file(files, "settings.json")
    closed(settings, ("version", "dataset", "counts", "parameters", "development_freeze_sha256"), "settings")
    need(settings["version"] == "corpus-settings-v1" and settings["dataset"] == dataset,
         "dataset_separation", "settings.dataset", "settings must identify the same dataset")
    need(type(settings["parameters"]) is dict and bool(settings["parameters"]), "record_type", "settings.parameters", "explicit frozen parameters required")
    need(encode(settings["counts"]) == encode(index["counts"]), "counts_mismatch", "settings.counts", "declared counts differ from mapped corpus")
    if dataset == "development":
        need(settings["development_freeze_sha256"] is None and "development-freeze.json" not in files,
             "dataset_separation", "settings", "development cannot contain an evaluation/development parent freeze")
    else:
        need("development-freeze.json" in files and settings["development_freeze_sha256"] == sha(files["development-freeze.json"]),
             "dataset_separation", "settings", "evaluation requires a hash-bound development freeze")
        dev = checked_record(files["development-freeze.json"])
        need(dev["dataset"] == "development" and dev["source_sha256"] != index["source_sha256"] and
             not set(dev["task_ids"]).intersection(item["id"] for item in index["tasks"]),
             "dataset_separation", "development-freeze", "development/evaluation source and task IDs must be distinct")
    review = json_file(files, "review.json")
    closed(review, ("version", "reviewer", "date", "obligations_answer_keys_cross_checked", "defects", "artifacts"), "review")
    need(review["version"] == "corpus-review-v1" and review["obligations_answer_keys_cross_checked"] is True,
         "review_required", "review", "declared cross-check against obligations and keys required")
    nonempty(review["reviewer"], "review.reviewer")
    nonempty(review["date"], "review.date")
    need(type(review["defects"]) is list and not review["defects"], "review_defect", "review.defects", "any unresolved defect blocks freeze/release")
    need(review["artifacts"] == {name: sha(raw) for name, raw in files.items() if name != "review.json"},
         "review_binding", "review.artifacts", "review must bind every other exact artifact")
    need(b"authoring-brief-v1" in files["authoring-brief.md"], "brief_version", "authoring-brief.md", "declared brief version missing")
    return index


def create_freeze(files, release_id, dataset, frozen_at):
    nonempty(release_id, "release_id")
    nonempty(frozen_at, "frozen_at")
    index = admission(files, dataset)
    record = {"version": VERSION, "release_id": release_id, "dataset": dataset, "frozen_at": frozen_at,
              "brief_version": index["brief_version"], "authoring_format_version": index["authoring_format_version"],
              "brief_sha256": sha(files["authoring-brief.md"]), "source_sha256": index["source_sha256"],
              "task_ids": [item["id"] for item in index["tasks"]], "counts": index["counts"],
              "artifacts": [{"path": name, "sha256": sha(raw), "bytes": len(raw), "role": role(name, index)} for name, raw in sorted(files.items())]}
    record["record_sha256"] = sha(encode(record))
    return encode(record)


def verify_freeze(files, raw):
    validate_files(files)
    record = checked_record(raw)
    need({item["path"] for item in record["artifacts"]} == files.keys() and len(record["artifacts"]) == len(files),
         "bundle_changed", "bundle", "file added, missing or duplicate in freeze inventory")
    for item in record["artifacts"]:
        content = files[item["path"]]
        need(len(content) == item["bytes"] and sha(content) == item["sha256"], "bundle_changed", item["path"], "frozen artifact bytes changed")
    # Reassert gates as well as byte identity; neither pass establishes semantic truth.
    regenerated = create_freeze(files, record["release_id"], record["dataset"], record["frozen_at"])
    need(decode(regenerated) == record, "freeze_record", "freeze", "freeze metadata differs from admitted bundle")
    return {"version": VERSION, "status": "verified", "release_id": record["release_id"], "dataset": record["dataset"],
            "record_sha256": record["record_sha256"], "artifacts": len(files), "semantics_verified": False}


def read_directory(directory):
    root = Path(directory)
    need(root.is_dir() and not root.is_symlink() and not root.is_junction(), "artifact_path", str(root), "ordinary bundle directory required")
    files, size = {}, 0
    for path in sorted(root.rglob("*")):
        need(not path.is_symlink() and not path.is_junction(), "artifact_path", str(path), "linked bundle paths refused")
        if path.is_file():
            need(len(files) < MAX_FILES, "safety_limit", str(root), "file admission ceiling")
            raw = read_bounded(path, MAX_FILE_BYTES)
            size += len(raw)
            need(size <= MAX_BUNDLE_BYTES, "safety_limit", str(root), "bundle byte admission ceiling")
            files[path.relative_to(root).as_posix()] = raw
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("bundle")
    parser.add_argument("record")
    parser.add_argument("--release")
    parser.add_argument("--dataset", choices=("development", "evaluation"))
    parser.add_argument("--frozen-at")
    args = parser.parse_args()
    try:
        record_path = Path(args.record)
        if args.action == "create":
            need(not record_path.exists(), "freeze_exists", str(record_path), "refuse to replace an existing freeze record")
            need(not record_path.resolve().is_relative_to(Path(args.bundle).resolve()), "artifact_path", str(record_path), "freeze receipt must be outside inventoried bundle")
            need(all((args.release, args.dataset, args.frozen_at)), "record_type", "arguments", "create requires release, dataset and explicit freeze time")
            files = read_directory(args.bundle)
            raw = create_freeze(files, args.release, args.dataset, args.frozen_at)
            # A second snapshot catches changes during preparation; creation is exclusive.
            need(read_directory(args.bundle) == files, "bundle_changed", args.bundle, "bundle changed during freeze preparation")
            with record_path.open("xb") as stream:
                stream.write(raw)
            result = verify_freeze(read_directory(args.bundle), raw)
            result["status"] = "frozen"
        else:
            result = verify_freeze(read_directory(args.bundle), read_bounded(record_path, MAX_FILE_BYTES))
    except IntakeError as exc:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}, sort_keys=True))
        return 2
    except OSError:
        print(json.dumps({"version": VERSION, "status": "rejected", "code": "file_unavailable"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
