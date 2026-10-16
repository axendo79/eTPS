"""Custodian-only batch diagnostic; no model execution or scoring changes.

Run from the repository root: python -B docs/v0.2/authoring-kit/check_batch.py BATCH
The two named inputs are source.json and question-contract-input.json.
"""
import contextlib
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile


class Discard:
    """Drop dependency diagnostics without retaining private text in a log."""
    encoding = "utf-8"
    errors = "replace"

    @property
    def buffer(self):
        return self

    def write(self, value):
        return len(value)

    def flush(self):
        pass


@contextlib.contextmanager
def quiet():
    sink = Discard()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


LINT_CODES = frozenset("""
answer_form_missing status_vocabulary_missing answer_restated_before_probe
status_word_leak question_reference_in_filler id_style_mixed evidence_position
key_restatement_window_counts missing_item_not_named values_not_in_force
evidence_outside_first_tenth context_pressure_unverified
""".split())
OBSERVATIONS = {"evidence_position", "key_restatement_window_counts", "context_pressure_unverified"}
STAGES = ("read", "authoring", "question_wording", "mapping", "intake", "lint", "conformance", "export")


def check_batch(batch, export=None):
    """Check one batch in temporary storage; export only on explicit request.

    Only fixed codes and numeric counts cross the output boundary. Neither task
    IDs nor author-chosen field names, paths, hashes or exception text are emitted.
    Lint remains advisory: PASS can include warnings, shown in lint_counts.
    """
    result = {"schema": "authoring-kit-check-v1", "status": "REFUSED", "checks": [],
              "counts": {"tasks": 0, "intakes": 0, "fields_checked": 0,
                         "lint_findings": 0, "lint_warnings": 0, "violations": 0},
              "lint_counts": {}, "semantics_verified": False, "token_sizes_verified": False}
    phase = "read"
    try:
        with quiet():
            # Anchor imports to this checkout, independent of the caller's cwd.
            repo = Path(__file__).resolve().parents[3]
            if str(repo) not in sys.path:
                sys.path.insert(0, str(repo))
            from etps_v02.conformance import check_bundle
            from etps_v02.intake.authoring import MAX_BYTES, validate_authoring
            from etps_v02.intake.authoring_lint import lint_authoring
            from etps_v02.intake.mapper import map_authoring
            from etps_v02.intake.state_records_v11 import validate_state_records
            from etps_v02.question_contract import (SCHEMA, VERSION, closed, digest,
                                                    is_junction, read_named, render, text)
            from etps_v02.workload import decode, encode

            root = Path(batch)
            if root.is_symlink() or is_junction(root) or not root.is_dir():
                raise ValueError()
            raw = read_named(root, "source.json", MAX_BYTES)
            contract_raw = read_named(root, "question-contract-input.json", MAX_BYTES)
            declaration = decode(contract_raw)
            closed(declaration, ("schema", "question_contract_version", "release_id", "tasks"))
            if declaration["schema"] != SCHEMA or declaration["question_contract_version"] != VERSION:
                raise ValueError()
            text(declaration["release_id"])
            result["checks"].append(phase)

            phase = "authoring"
            doc = validate_authoring(raw)
            if doc["brief_version"] != "authoring-brief-v2":
                raise ValueError()
            result["counts"]["tasks"] = len(doc["tasks"])
            result["checks"].append(phase)

            phase = "question_wording"
            tasks = declaration["tasks"]
            if type(tasks) is not dict or set(tasks) != {t["id"] for t in doc["tasks"]}:
                raise ValueError()
            for task in doc["tasks"]:
                entry = tasks[task["id"]]
                closed(entry, ("questions",))
                questions = entry["questions"]
                if type(questions) is not dict or set(questions) != {p["id"] for p in task["probes"]}:
                    raise ValueError()
                for probe in task["probes"]:
                    # No implicit prompt rewrite. Freeze can re-derive every byte.
                    if render(questions[probe["id"]]) != probe["wording"]:
                        raise ValueError()
            result["checks"].append(phase)

            phase = "mapping"
            files = map_authoring(raw)
            index = decode(files["bundle.json"])
            declaration["bundle_sha256"] = digest(files["bundle.json"])
            # Descriptor field order controls H3 paragraph order. Preserve it
            # when binding; canonical sorting here could render different text.
            files["question-contract.json"] = json.dumps(
                declaration, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            files["question-contract-input.json"] = contract_raw
            result["checks"].append(phase)

            phase = "intake"
            for item in index["tasks"]:
                receipt = validate_state_records(decode(files[item["manifest"]]), files[item["sidecar"]])
                if receipt["status"] != "validated":
                    raise ValueError()
                result["counts"]["intakes"] += 1
            result["checks"].append(phase)

            phase = "lint"
            lint = lint_authoring(raw)  # Keep the v2 three-message default.
            counts = Counter(f["code"] if f["code"] in LINT_CODES else "unrecognized_lint"
                             for f in lint["findings"])
            result["lint_counts"] = dict(sorted(counts.items()))
            result["counts"]["lint_findings"] = sum(counts.values())
            result["counts"]["lint_warnings"] = sum(n for code, n in counts.items() if code not in OBSERVATIONS)
            result["checks"].append(phase)

            phase = "conformance"
            # check_bundle reads only its bounded named files. This temporary
            # copy contains private material; the custodian sets TEMP/TMP.
            with tempfile.TemporaryDirectory(prefix="etps-authoring-kit-") as directory:
                temp = Path(directory)
                if temp.resolve().is_relative_to(root.resolve()):
                    raise ValueError()
                for name, data in files.items():
                    (temp / name).write_bytes(data)
                report = check_bundle(temp / "bundle.json")
            result["counts"]["fields_checked"] = report["fields_checked"]
            result["counts"]["violations"] = report["violation_count"]
            if report["violation_count"]:
                raise ValueError()
            result["checks"].append(phase)

            if export is not None:
                phase = "export"
                target = Path(export)
                if target.resolve().is_relative_to(root.resolve()):
                    raise ValueError()
                target.mkdir(exist_ok=False)  # New sibling/private destination only.
                for name, data in files.items():
                    with (target / name).open("xb") as stream:
                        stream.write(data)
                result["checks"].append(phase)
            result["status"] = "PASS"
    except (Exception, KeyboardInterrupt, SystemExit):
        result["refusal"] = {"code": "check_failed", "phase": phase if phase in STAGES else "read"}
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in (1, 3) or args[0].startswith("-") or len(args) == 3 and args[1] != "--export":
        result = {"schema": "authoring-kit-check-v1", "status": "REFUSED",
                  "refusal": {"code": "usage_error", "phase": "read"}}
    else:
        result = check_batch(args[0], args[2] if len(args) == 3 else None)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
