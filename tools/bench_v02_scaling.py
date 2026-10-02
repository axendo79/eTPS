"""Synthetic scaling benchmark for the v0.2 harness. Not a model benchmark.

Run from the repository root: python -B tools/bench_v02_scaling.py
Deterministic rows (vm_steps, bytes, calls) are the acceptance evidence; *_seconds rows
are informational and hardware dependent. Writes only to a temporary directory.
"""
import base64
import hashlib
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etps_v02 import runner, scorer  # noqa: E402
from etps_v02.persistence import Store  # noqa: E402
from etps_v02.scorer import InvalidRecord  # noqa: E402
from etps_v02.workload import INVALIDATION_POLICY, encode, sha  # noqa: E402

RESPONSE = {"status": "ok", "raw_base64": base64.b64encode(b'{"database":"SQLite"}').decode()}


def two_probe_task():
    text = "database=SQLite"
    manifest = {"unit": "utf8_bytes", "start": "u", "obligations": {
        "db": {"source": "u", "begin_after": "u", "end_before": "$trial_end"}}, "nodes": {
        "u": {"kind": "user", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
              "spans": [], "next": "p"},
        "p": {"kind": "probe", "expected": {"database": "SQLite"}, "unknown_answers": [],
              "obligations": ["db"], "next": {o: ("ok" if o == "correct" else "no") for o in scorer.OUTCOMES}},
        "ok": {"kind": "terminal", "accepted": True}, "no": {"kind": "terminal", "accepted": False}}}
    return encode(manifest), encode({"responses": [RESPONSE]})


def chain_task(turns, reply_bytes):
    nodes = {}
    for i in range(turns):
        text = f"turn {i} " + "x" * 200
        nodes[f"u{i}"] = {"kind": "user", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                          "spans": [], "next": f"p{i}"}
        target = f"u{i + 1}" if i + 1 < turns else "done"
        nodes[f"p{i}"] = {"kind": "probe", "expected": {"a": "b"}, "unknown_answers": [], "obligations": [],
                          "next": {o: target for o in scorer.OUTCOMES}}
    nodes["done"] = {"kind": "terminal", "accepted": True}
    reply = json.dumps({"a": "b", "pad": "y" * reply_bytes}).encode()
    response = {"status": "ok", "raw_base64": base64.b64encode(reply).decode()}
    return (encode({"unit": "utf8_bytes", "start": "u0", "obligations": {}, "nodes": nodes}),
            encode({"responses": [response] * turns}), turns * len(reply))


def plan(task, script, slots, **extra):
    return encode({"schema": "etps-offline-plan-v2", "purpose": "offline-verification", "unit": "utf8_bytes",
                   "invalidation_policy": dict(INVALIDATION_POLICY), "tasks": {"t": sha(task)},
                   "slots": [{"id": f"s{i}", "arm": "a", "task": "t", "script_sha256": sha(script)}
                             for i in range(slots)], **extra}), {sha(task): task, sha(script): script}


def emit(name, value):
    print(f"{name}\t{value}")


def create_scaling(temp):
    task, script = two_probe_task()
    for slots in (1000, 4000):
        plan_raw, artifacts = plan(task, script, slots)
        began = time.perf_counter()
        Store.create(temp / f"create{slots}.db", plan_raw, artifacts).close()
        emit(f"create_seconds.slots_{slots}", f"{time.perf_counter() - began:.2f}")


def start_vm_steps(temp, predecessors):
    task, script = two_probe_task()
    plan_raw, artifacts = plan(task, script, predecessors + 1)
    store = Store.create(temp / f"order{predecessors}.db", plan_raw, artifacts)
    try:
        for i in range(predecessors):
            store.append(f"s{i}", "start", {})
            store.abort(f"s{i}", "operator_abort")
        steps = [0]

        def count():
            steps[0] += 1
        store.db.set_progress_handler(count, 1)
        store.append(f"s{predecessors}", "start", {})
        store.db.set_progress_handler(None, 1)
        return steps[0]
    finally:
        store.close()


def journal_bytes(temp, extra, label):
    task, script, reply_total = chain_task(100, 2000)
    plan_raw, artifacts = plan(task, script, 1, **extra)
    try:
        store = Store.create(temp / f"journal_{label}.db", plan_raw, artifacts)
    except InvalidRecord as exc:
        emit(f"journal_bytes.{label}", f"unsupported ({exc})")
        return
    try:
        runner.run_offline(store, "s0")
        total, requests = store.db.execute(
            "SELECT sum(length(payload)), sum(CASE WHEN kind='request' THEN length(payload) END) FROM journal"
        ).fetchone()
        emit(f"journal_bytes.{label}.total", total)
        emit(f"journal_bytes.{label}.requests", requests)
        emit(f"journal_bytes.{label}.reply_bytes", reply_total)
    finally:
        store.close()


def report_scaling(temp):
    task, script = two_probe_task()
    plan_raw, artifacts = plan(task, script, 200)
    store = Store.create(temp / "report.db", plan_raw, artifacts)
    try:
        for i in range(200):
            runner.run_offline(store, f"s{i}")
        calls = {"validate": 0, "implementation": 0}
        originals = scorer.validate, runner.implementation

        def validate(*args, **kwargs):
            calls["validate"] += 1
            return originals[0](*args, **kwargs)

        def implementation():
            calls["implementation"] += 1
            return originals[1]()
        scorer.validate = runner.validate = validate
        runner.implementation = implementation
        try:
            began = time.perf_counter()
            runner.report(store)
            emit("report_seconds.slots_200", f"{time.perf_counter() - began:.2f}")
        finally:
            scorer.validate = runner.validate = originals[0]
            runner.implementation = originals[1]
        emit("report_calls.validate", calls["validate"])
        emit("report_calls.implementation", calls["implementation"])
    finally:
        store.close()


def main():
    emit("python", sys.version.split()[0])
    emit("sqlite", sqlite3.sqlite_version)
    with tempfile.TemporaryDirectory() as name:
        temp = Path(name)
        create_scaling(temp)
        small, large = start_vm_steps(temp, 100), start_vm_steps(temp, 400)
        emit("start_vm_steps.predecessors_100", small)
        emit("start_vm_steps.predecessors_400", large)
        emit("start_vm_steps.ratio_400_over_100", f"{large / small:.2f}")
        journal_bytes(temp, {}, "full_history")
        journal_bytes(temp, {"request_journal": "history-sha256-v1"}, "history_sha256")
        report_scaling(temp)


if __name__ == "__main__":
    main()
