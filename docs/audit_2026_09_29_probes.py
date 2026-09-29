"""Bounded local audit reproductions; synthetic only, no network or model calls.

Run from the repository root with python -B docs/audit_2026_09_29_probes.py.
These characterize current defects; they are not a passing regression contract.
"""
import ast
import base64
import copy
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from test_v02_runner import bundle, response
from test_v02_scorer import fixture, replay, user
from etps_v02.persistence import Store
from etps_v02.runner import run_offline, export_bundle, replay_export
from etps_v02.scorer import validate, score, finite
from etps_v02.workload import decode, encode, sha, validate_bundle
import scorer as legacy
import logger
import user_profile as profiles
import leaderboard
import seit


def emit(name, **values):
    print(json.dumps({"probe": name, **values}, default=str, sort_keys=True))


def error(fn):
    try:
        fn()
        return "accepted"
    except Exception as exc:
        return type(exc).__name__


def rehash(export, slot):
    previous = sha(encode([export["plan_sha256"], slot]))
    for i, entry in enumerate(export["journal"][slot]):
        previous = sha(encode([slot, i, entry["kind"], previous]) + encode(entry["payload"]))
        entry["sha256"] = previous


def main():
    files = sorted(p for p in ROOT.rglob("*.py") if ".git" not in p.parts)
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    emit("syntax", files=len(files), result="all parsed")
    emit("strict_decode", overflow_is_infinite=math.isinf(decode(b'{"x":1e999}')["x"]),
         huge_integer_finite_check=error(lambda: finite(10 ** 400)))
    emit("schema_errors", null_plan=error(lambda: validate_bundle(b"null", {})),
         missing_nodes=error(lambda: validate({"unit": "utf8_bytes"})))
    emit("deep_response", exception=error(lambda: decode(("[" * 1100 + "0" + "]" * 1100).encode())))
    m = fixture()
    m["nodes"]["intro"]["budget_seconds"] = 0
    emit("ignored_manifest_policy", validation=error(lambda: validate(m)))
    m = fixture()
    m["nodes"]["recover"]["failure"] = "p2"
    emit("future_failure_reference", validation=error(lambda: validate(m)),
         replay_reason=score(m, replay(m))["reason"])
    chain = {"unit": "utf8_bytes", "start": "n0", "obligations": {}, "nodes": {}}
    for i in range(1100):
        chain["nodes"][f"n{i}"] = user("", f"n{i+1}")
    chain["nodes"]["n1100"] = {"kind": "terminal", "accepted": True}
    emit("finite_long_graph", validation=error(lambda: validate(chain)))
    with tempfile.TemporaryDirectory(prefix="etps-audit-") as temp:
        root = Path(temp)
        plan, artifacts = bundle(responses=[response(b'{}')], slots=1)
        store = Store.create(root / "mismatch.db", plan, artifacts)
        try:
            with patch("etps_v02.runner._next_response", return_value=response()):
                execution = error(lambda: run_offline(store, "slot-0"))
            exported = export_bundle(store)
            checked = replay_export(exported, validate_authoring=True)
            emit("script_mismatch", accepted=checked["accepted"], warnings=checked["warnings"],
                 comparison_incomplete=checked["comparison_incomplete"], execution=execution,
                 evidence_verified=checked["trials"][0].get("evidence_verified"))
            # A rejected adapter substitution now aborts. Test finish metadata on
            # separate, valid completed evidence so the original probe continues.
            clean_plan, clean_artifacts = bundle(responses=[response()], slots=1)
            clean = Store.create(root / "finish.db", clean_plan, clean_artifacts)
            try:
                run_offline(clean, "slot-0")
                exported = export_bundle(clean)
            finally:
                clean.close()
            changed = copy.deepcopy(exported)
            changed["journal"]["slot-0"][-1]["payload"].update(terminal="fail", reason_code="invented")
            rehash(changed, "slot-0")
            checked = replay_export(changed, validate_authoring=True)
            emit("finish_mismatch", accepted=checked["accepted"], warnings=checked["warnings"],
                 reason_code=checked["trials"][0]["reason_code"])
            stripped = copy.deepcopy(exported)
            stripped["journal"]["slot-0"] = []
            checked = replay_export(stripped)
            emit("export_erased_attempt", attempted=checked["attempted"], warnings=checked["warnings"])
        finally:
            store.close()
        for label, raw in (("exponent_overflow", b'{"x":1e999}'),
                           ("escaped_surrogate", b'{"x":"\\ud800"}')):
            plan, artifacts = bundle(responses=[response(raw), response()], slots=1)
            store = Store.create(root / (label + ".db"), plan, artifacts)
            try:
                result = error(lambda: run_offline(store, "slot-0"))
                entries = store.entries("slot-0")
                emit(label + "_runner", exception=result, final_kind=entries[-1]["kind"],
                     reason_code=entries[-1]["payload"].get("reason_code"),
                     probe_events=sum(e["kind"] == "event" and e["payload"]["kind"] == "probe" for e in entries))
            finally:
                store.close()
        plan, artifacts = bundle(responses=[response(("[" * 1100 + "0" + "]" * 1100).encode()), response()], slots=1)
        store = Store.create(root / "deep.db", plan, artifacts)
        try:
            result = error(lambda: run_offline(store, "slot-0"))
            entries = store.entries("slot-0")
            emit("deep_response_runner", exception=result, final_kind=entries[-1]["kind"],
                 reason_code=entries[-1]["payload"].get("reason_code"),
                 probe_events=sum(e["kind"] == "event" and e["payload"]["kind"] == "probe" for e in entries))
        finally:
            store.close()
        db = root / "profiles.db"
        logs = root / "logger.db"
        profiles.initialize_schema(db)
        logger.initialize_schema(logs)
        a = profiles.create_user(db_path=db)
        b = profiles.create_user(db_path=db)
        hw = profiles.register_hardware_profile(b["user_id"], {"cpu": "other user's CPU", "gpu": "GPU"}, "private", db_path=db)
        profiles.update_consent(a["user_id"], True, True, True, ["researchers"], db_path=db)
        for _ in range(2):
            profiles.link_run(a["user_id"], "nonexistent-run", "v0.1", hardware_profile_id=hw,
                              is_public=True, aggregate_cache={"etps_sustained": 999}, db_path=db)
        exported = profiles.export_for_partners("researchers", db_path=db)
        emit("legacy_links", duplicate_links=len(profiles.get_user_history(a["user_id"], db_path=db)),
             other_user_hardware=exported["data"][0]["hw_cpu"], fabricated_score=exported["data"][0]["etps_avg"])
        run = logger.start_run({}, {}, db_path=logs)
        result = legacy.calculate_etps(50, legacy.TokenCounts(total=100), legacy.PenaltyRecord(),
                                      legacy.ContinuityRecord(expected_context_items=2, retained_context_items=1, is_single_turn=False))
        logger.record_task_result(run, "test", "B", result, 2, db_path=logs)
        logger.finalize_run(run, logs)
        profiles.link_run(a["user_id"], run, "v0.1", is_public=False, db_path=db)
        profiles.update_consent(a["user_id"], False, False, False, db_path=db)
        board = leaderboard.build_leaderboard(logger_db=logs, profile_db=db)
        conn = logger.get_connection(logs)
        try:
            row = dict(conn.execute("SELECT is_single_turn, expected_context_items, retained_context_items, continuity_factor FROM task_results").fetchone())
        finally:
            conn.close()
        emit("private_run_on_leaderboard", exposed=any(r["run_id"] == run for r in board))
        emit("legacy_continuity_storage", **row)
    result = legacy.calculate_etps(50, legacy.TokenCounts(total=100, correction=-100), legacy.PenaltyRecord(), legacy.ContinuityRecord())
    emit("legacy_negative_waste", raw=result.tps_raw, etps=result.etps, efficiency=result.efficiency_ratio)
    samples = [seit.SEITSample(x, 1, timestamp=0) for x in (0, 0, 100)]
    result = seit.calculate_seit(samples, seit.PowerProfile(10), window_seconds=-1)
    emit("seit_invalid_window_and_variance", window=result.window_seconds, cv=result.coefficient_of_variation, stable=result.thermal_stable)


def inventory():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT)
    tracked = git("ls-files", "-z").decode().split("\0")
    files = [ROOT / p for p in tracked if p]
    files += list((ROOT / "_local_docs_draft0").rglob("*.md"))
    files += [ROOT / "docs/v0.2/CORPUS_INTAKE.md"]
    for p in files:
        raw = p.read_bytes()
        raw.decode("utf-8")
    emit("inventory", tracked_files=len([p for p in tracked if p]),
         reviewed_local_files=len(files), all_utf8=True)
    broken = []
    for p in files:
        if p.suffix != ".md":
            continue
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            destination = target.split("#")[0]
            if destination and not (p.parent / destination).exists():
                broken.append([str(p.relative_to(ROOT)), target])
    emit("local_markdown_links", broken=broken)
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"\bAKIA[0-9A-Z]{16}\b", rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
                rb"\bsk-[A-Za-z0-9_-]{32,}\b"]
    hits, blobs = [], 0
    for line in objects:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        oid, name = parts
        if git("cat-file", "-t", oid).strip() != b"blob":
            continue
        raw = git("cat-file", "blob", oid)
        blobs += 1
        if any(re.search(pattern, raw) for pattern in patterns):
            hits.append({"object": oid, "path": name})
    emit("limited_history_secret_signatures", blobs_scanned=blobs, locations=hits,
         limitation="Narrow signature scan, not proof of absence; values are never printed")
    for ref in ("origin/claude/civic-lens-assistant-y3zYa", "origin/claude/bear-lake-property-analysis-QQDAM"):
        names = git("diff", "--name-only", "main..." + ref).decode().splitlines()
        py_results = {}
        for name in names:
            raw = git("show", ref + ":" + name)
            if name.endswith(".py"):
                py_results[name] = error(lambda raw=raw: ast.parse(raw))
        emit("unmerged_branch_inventory", ref=ref, changed_files=names, syntax=py_results)


def smoke():
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    for module in ("scorer.py", "logger.py", "user_profile.py", "leaderboard.py", "seit.py"):
        result = subprocess.run([sys.executable, "-B", str(ROOT / module)], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", env=env)
        emit("legacy_smoke", module=module, exit_code=result.returncode,
             error=result.stderr if result.returncode else None)


if __name__ == "__main__":
    if "--inventory" in sys.argv:
        inventory()
    elif "--smoke" in sys.argv:
        smoke()
    else:
        main()
