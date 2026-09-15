"""Offline integration/crash tests. All outputs are authored fixtures, not models."""
import base64
import copy
from fractions import Fraction
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.persistence import Store
from etps_v02.runner import implementation, replay_slot, report, run_offline, export_bundle, replay_export
from etps_v02.scorer import InvalidRecord, score
from etps_v02.workload import INVALIDATION_POLICY, decode, encode, sha
from test_v02_scorer import fixture, user


def response(raw=b'{"database":"SQLite"}', status="ok", generation=None):
    return {"status": status, "raw_base64": base64.b64encode(raw).decode(), "generation": generation}


def bundle(manifest=None, responses=None, slots=2):
    manifest = manifest or fixture()
    # Deliberately noncanonical file spelling; persistence must preserve it exactly.
    raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\r\n").encode()
    script = encode({"responses": responses if responses is not None else [
        response(b'{"database":"Postgres"}', generation={"tokens": 50, "seconds": 1}),
        response(generation={"tokens": 50, "seconds": 1})]})
    artifacts = {sha(raw): raw, sha(script): script}
    plan = {"schema": "etps-offline-plan-v2", "purpose": "offline-verification",
            "unit": "utf8_bytes", "invalidation_policy": dict(INVALIDATION_POLICY),
            "tasks": {"synthetic": sha(raw)}, "slots": [
                {"id": f"slot-{i}", "arm": "baseline" if i % 2 == 0 else "memory",
                 "task": "synthetic", "script_sha256": sha(script)} for i in range(slots)]}
    return encode(plan), artifacts


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "offline.db"
        self.store = None

    def tearDown(self):
        if self.store:
            self.store.close()
        self.temp.cleanup()

    def create(self, **kwargs):
        plan, artifacts = bundle(**kwargs)
        self.store = Store.create(self.path, plan, artifacts)
        return self.store

    def test_recovery_exact_roundtrip_and_reopen(self):
        store = self.create()
        before = run_offline(store, "slot-0")
        self.assertEqual((before["score"]["R"], before["score"]["I"], before["score"]["RR"]),
                         (15, 40, Fraction(3, 8)))
        self.assertIsNone(before["score"]["experimental_eTPS"])
        self.assertIsNone(before["score"]["TPS"])
        self.assertIsNone(before["score"]["wall_seconds"])
        original = copy.deepcopy(store.artifacts)
        store.close()
        self.store = Store(self.path)
        self.assertEqual(before, replay_slot(self.store, "slot-0"))
        self.assertEqual(original, self.store.artifacts)
        self.assertEqual(before["score"], score(self.store.manifest("slot-0"), before["record"]))

    def test_adapter_sees_only_public_history(self):
        from etps_v02.runner import _next_response
        store = self.create()
        seen = []
        def capture(responses, index, messages):
            seen.append(copy.deepcopy(messages))
            return _next_response(responses, index, messages)
        with patch("etps_v02.runner._next_response", capture):
            run_offline(store, "slot-0")
            run_offline(store, "slot-1")
        self.assertEqual(seen[:2], seen[2:])
        self.assertEqual(seen[0], [{"role": "user", "text": "database=SQLite"}])
        for messages in seen:
            for message in messages:
                self.assertLessEqual(set(message), {"role", "text", "raw_base64"})

    def test_wrong_answers_are_finished_failures(self):
        store = self.create(responses=[response(b'{"database":"Postgres"}'), response(b'{}')])
        result = run_offline(store, "slot-0")
        self.assertEqual(result["state"], "finished")
        self.assertFalse(result["score"]["accepted"])
        self.assertTrue(result["score"]["measurement_valid"])
        self.assertIsNone(result["score"]["experimental_eTPS"])
        summary = report(store)
        self.assertEqual((summary["planned"], summary["attempted"], summary["failed"], summary["unattempted"]),
                         (2, 1, 1, 1))
        self.assertTrue(summary["comparison_incomplete"])

    def test_raw_malformed_unicode_duplicate_keys_and_timeout(self):
        for raw, status, label in ((b'\xff', "ok", "malformed"),
                                   (b'{"database":"bad","database":"SQLite"}', "ok", "malformed"),
                                   (b'{"database":"SQLite"}', "timeout", "timeout")):
            with self.subTest(raw=raw):
                plan, artifacts = bundle(responses=[response(raw, status), response()], slots=1)
                path = Path(self.temp.name) / f"case-{label}-{len(raw)}.db"
                store = Store.create(path, plan, artifacts)
                try:
                    result = run_offline(store, "slot-0")
                    self.assertEqual(result["score"]["classifications"][1]["class"], label)
                    self.assertEqual(base64.b64decode(result["record"]["events"][1]["raw_base64"]), raw)
                finally:
                    store.close()

    def test_unknown_and_exhausted_scripts_abort_without_replacement(self):
        store = self.create(responses=[response(b'{"status":"unknown"}')])
        with self.assertRaisesRegex(InvalidRecord, "exhausted"):
            run_offline(store, "slot-0")
        result = replay_slot(store, "slot-0")
        self.assertEqual(result["state"], "aborted")
        self.assertIsNone(result["score"]["RR"])
        self.assertEqual(len(result["record"]["events"]), 3)
        with self.assertRaisesRegex(InvalidRecord, "already attempted"):
            run_offline(store, "slot-0")
        self.assertEqual(report(store)["unattempted"], 1)

    def test_unused_script_is_visible_abort(self):
        store = self.create(responses=[response(), response()])
        with self.assertRaisesRegex(InvalidRecord, "unused"):
            run_offline(store, "slot-0")
        self.assertEqual(report(store)["aborted"], 1)
        self.assertIsNone(replay_slot(store, "slot-0")["score"]["accepted"])

    def test_interrupted_request_requires_explicit_abort(self):
        store = self.create()
        store.append("slot-0", "start", {"evidence": "synthetic-offline", **implementation()})
        store.append("slot-0", "request", {"node": "p1", "messages": []})
        store.close()
        self.store = Store(self.path)
        self.assertEqual(report(self.store)["running"], 1)
        with self.assertRaisesRegex(InvalidRecord, "already attempted"):
            run_offline(self.store, "slot-0")
        with self.assertRaisesRegex(InvalidRecord, "order"):
            run_offline(self.store, "slot-1")
        self.store.abort("slot-0", "interrupted", "operator confirmed interrupted offline request")
        run_offline(self.store, "slot-1")
        self.assertEqual(report(self.store)["aborted"], 1)

    def test_immutable_rows_and_no_duplicate_claim(self):
        store = self.create()
        run_offline(store, "slot-0")
        with self.assertRaises(sqlite3.IntegrityError):
            store.db.execute("DELETE FROM journal")
        store.db.rollback()
        second = Store(self.path)
        try:
            with self.assertRaises(InvalidRecord):
                run_offline(second, "slot-0")
        finally:
            second.close()

    def test_head_detects_tail_loss(self):
        store = self.create()
        run_offline(store, "slot-0")
        store.db.execute("DROP TRIGGER immutable_journal_DELETE")
        store.db.execute("DELETE FROM journal WHERE slot='slot-0' AND seq=(SELECT MAX(seq) FROM journal WHERE slot='slot-0')")
        store.db.commit()
        with self.assertRaisesRegex(InvalidRecord, "head"):
            store.entries("slot-0")

    def test_raw_event_tampering_detected(self):
        store = self.create()
        run_offline(store, "slot-0")
        store.db.execute("DROP TRIGGER immutable_journal_UPDATE")
        store.db.execute("UPDATE journal SET payload=? WHERE seq=1 AND slot='slot-0'", (b'{}',))
        store.db.commit()
        with self.assertRaisesRegex(InvalidRecord, "integrity"):
            store.entries("slot-0")

    def test_preflight_rejects_changed_artifact_and_live_mode_without_creating_db(self):
        plan, artifacts = bundle()
        key = next(iter(artifacts))
        artifacts[key] += b' '
        with self.assertRaisesRegex(InvalidRecord, "hash"):
            Store.create(self.path, plan, artifacts)
        self.assertFalse(self.path.exists())
        plan, artifacts = bundle()
        p = decode(plan)
        p["purpose"] = "calibration"
        with self.assertRaisesRegex(InvalidRecord, "only offline"):
            Store.create(self.path, encode(p), artifacts)
        self.assertFalse(self.path.exists())

    def test_unsupported_internal_action_is_not_silently_skipped(self):
        m = fixture()
        m["nodes"]["internal"] = {"kind": "internal", "next": "pass"}
        with self.assertRaisesRegex(InvalidRecord, "only user/probe/terminal"):
            self.create(manifest=m)
        self.assertFalse(self.path.exists())

    def test_rejects_duplicate_json_and_nonfinite_script_before_write(self):
        plan, artifacts = bundle()
        with self.assertRaises(InvalidRecord):
            Store.create(self.path, b'{"purpose":1,"purpose":2}', artifacts)
        with self.assertRaises(InvalidRecord):
            decode(b'{"x":NaN}')
        self.assertFalse(self.path.exists())

    def test_existing_legacy_and_unknown_schema_are_not_initialized(self):
        self.path.write_bytes(b'')
        with self.assertRaises(InvalidRecord):
            Store(self.path)
        self.assertEqual(self.path.read_bytes(), b'')
        plan, artifacts = bundle()
        with self.assertRaises(FileExistsError):
            Store.create(self.path, plan, artifacts)

    def test_export_is_lossless_and_cross_process_replay(self):
        store = self.create()
        run_offline(store, "slot-0")
        exported = export_bundle(store)
        self.assertEqual(base64.b64decode(exported["plan_base64"]), store.plan_raw)
        for key, raw in exported["artifacts"].items():
            self.assertEqual(base64.b64decode(raw), store.artifacts[key])
        completed = subprocess.run([sys.executable, "-m", "etps_v02", "report", str(self.path)],
                                   check=True, capture_output=True, text=True)
        data = json.loads(completed.stdout)
        self.assertEqual(data["trials"][0]["score"]["RR"], {"numerator": 3, "denominator": 8})
        self.assertEqual(data["unattempted"], 1)

    def test_all_planned_slots_visible_when_complete(self):
        store = self.create()
        run_offline(store, "slot-0")
        run_offline(store, "slot-1")
        s = report(store)
        self.assertEqual((s["planned"], s["attempted"], s["accepted"], s["rr_available"]), (2, 2, 2, 2))
        self.assertFalse(s["comparison_incomplete"])

    def test_report_exposes_all_attempt_costs_and_pooled_rr(self):
        plan_raw, artifacts = bundle(responses=[response()], slots=2)
        plan = decode(plan_raw)
        failing = encode({"responses": [response(b'{}'), response(b'{}')]})
        artifacts[sha(failing)] = failing
        plan["slots"][1]["script_sha256"] = sha(failing)
        plan["slots"][1]["arm"] = "baseline"
        self.store = Store.create(self.path, encode(plan), artifacts)
        run_offline(self.store, "slot-0")
        incomplete = report(self.store)["summaries"][0]
        self.assertIsNone(incomplete["pooled_RR"])
        self.assertEqual(incomplete["input_cost_unavailable_reason"], "unattempted_slots")
        run_offline(self.store, "slot-1")
        summary = report(self.store)["summaries"][0]
        self.assertEqual((summary["planned"], summary["attempted"], summary["accepted"]), (2, 2, 1))
        self.assertEqual(summary["input_bytes_per_accepted"], 55)
        self.assertEqual(summary["pooled_RR"], Fraction(3, 11))
        self.assertIsNone(summary["wall_seconds_per_accepted"])
        self.assertEqual(summary["wall_cost_unavailable_reason"], "wall_time_unavailable")
        self.assertEqual(replay_export(export_bundle(self.store))["summaries"][0], summary)

    def test_report_keeps_arms_and_tasks_separate(self):
        store = self.create(responses=[response()])
        run_offline(store, "slot-0")
        run_offline(store, "slot-1")
        summaries = report(store)["summaries"]
        self.assertEqual({s["arm"] for s in summaries}, {"baseline", "memory"})
        self.assertTrue(all(s["planned"] == 1 for s in summaries))
        # Same arm with different task files still produces separate summaries.
        plan_raw, artifacts = bundle(responses=[response()], slots=2)
        plan = decode(plan_raw)
        m = fixture()
        m["nodes"]["intro"] = user("database=SQLite; another task", "p1")
        raw = encode(m)
        artifacts[sha(raw)] = raw
        plan["tasks"]["other"] = sha(raw)
        plan["slots"][1].update(task="other", arm="baseline")
        other = Store.create(Path(self.temp.name) / "other.db", encode(plan), artifacts)
        try:
            run_offline(other, "slot-0")
            run_offline(other, "slot-1")
            summaries = report(other)["summaries"]
            self.assertEqual({s["task"] for s in summaries}, {"synthetic", "other"})
            self.assertTrue(all(s["planned"] == 1 for s in summaries))
        finally:
            other.close()

    def test_import_rejects_duplicate_grants_before_creating_store(self):
        from test_v02_authorizations import reused_grant
        plan, artifacts = bundle(manifest=reused_grant(), slots=1)
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            Store.create(self.path, plan, artifacts)
        self.assertFalse(self.path.exists())

    def test_legacy_schema_flag_does_not_disable_v2_authoring_gate(self):
        from etps_v02.workload import validate_bundle
        from test_v02_authorizations import reused_grant
        plan, artifacts = bundle(manifest=reused_grant(), slots=1)
        for allow_legacy in (False, True):
            with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
                validate_bundle(plan, artifacts, allow_legacy=allow_legacy)
        # Replay is an explicit, separate choice, not implied by schema compatibility.
        self.assertEqual(validate_bundle(plan, artifacts, allow_legacy=True, authoring=False)["schema"],
                         "etps-offline-plan-v2")

    def test_v2_export_can_reassert_authoring_gate(self):
        from test_v02_authorizations import reused_grant
        plan, artifacts = bundle(manifest=reused_grant(), slots=1)
        exported = {"format": "etps-offline-export-v1", "plan_sha256": sha(plan),
                    "plan_base64": base64.b64encode(plan).decode(),
                    "artifacts": {k: base64.b64encode(v).decode() for k, v in artifacts.items()},
                    "journal": {"slot-0": []}}
        self.assertFalse(replay_export(exported)["authoring_gate_reasserted"])
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            replay_export(exported, validate_authoring=True)
        store = self.create(slots=1)
        run_offline(store, "slot-0")
        result = replay_export(export_bundle(store), validate_authoring=True)
        self.assertTrue(result["authoring_gate_reasserted"])
        self.assertEqual(result["trials"][0]["score"]["RR"], Fraction(3, 8))

    def test_asymmetric_recovery_keeps_event_boundaries(self):
        from test_v02_scorer import probe
        m = fixture()
        m["obligations"]["db"]["end_before"] = "expire"
        m["nodes"]["p1"]["next"]["correct"] = "later"
        m["nodes"]["p2"]["next"]["correct"] = "later"
        m["nodes"]["later"] = probe({"database": "SQLite"}, "expire", "later_rec")
        m["nodes"]["later_rec"] = user("database=SQLite", "last", [[0, 15, "db"]], "later")
        m["nodes"]["last"] = probe({"database": "SQLite"}, "expire", "fail")
        m["nodes"]["expire"] = user("Obligation ended.", "pass")
        good, wrong = response(), response(b'{}')
        results = []
        for i, script in enumerate(([good, wrong, good], [wrong, good, wrong, good])):
            plan, artifacts = bundle(manifest=m, responses=script, slots=1)
            store = Store.create(Path(self.temp.name) / f"arm-{i}.db", plan, artifacts)
            try:
                result = run_offline(store, "slot-0")
                results.append(result)
                recovery = [c for c in result["score"]["classifications"] if c["node"] == "later_rec"][0]
                self.assertEqual(recovery["R"], 15)
                self.assertEqual(store.entries("slot-0")[-1]["payload"]["resolved_obligations"],
                                 result["score"]["resolved_obligations"])
            finally:
                store.close()
        a, b = [r["score"]["resolved_obligations"]["db"] for r in results]
        self.assertEqual((a["begin_after"], a["end_before"]), ("intro", "expire"))
        self.assertEqual(a["end_before"], b["end_before"])
        self.assertEqual(b["end_index"] - a["end_index"], 2)

    def test_synthetic_throughput_interlock_all_output_paths(self):
        store = self.create(slots=1)
        result = run_offline(store, "slot-0")
        for r in (result, replay_slot(store, "slot-0"), report(store)["trials"][0],
                  export_bundle(store)["report"]["trials"][0]):
            self.assertIsNone(r["score"]["TPS"])
            self.assertIsNone(r["score"]["experimental_eTPS"])
            self.assertEqual(r["score"]["throughput_unavailable_reason"], "offline_verification")
            self.assertEqual(r["record"]["events"][1]["generation"]["tokens"], 50)

    def test_code_hash_mismatch_warns_and_recomputes(self):
        store = self.create(slots=1)
        with patch("etps_v02.runner.implementation", return_value={"scorer_sha256": "old", "runner_sha256": "old"}):
            run_offline(store, "slot-0")
        result = replay_slot(store, "slot-0")
        self.assertTrue(result["implementation_mismatch"])
        self.assertEqual(result["score"]["RR"], Fraction(3, 8))
        self.assertEqual(result["implementation"]["recorded"]["scorer_sha256"], "old")
        self.assertTrue(export_bundle(store)["report"]["implementation_mismatch"])
        exported = export_bundle(store)
        exported["report"] = {"forged": "old summary must not be trusted"}
        recomputed = replay_export(exported)
        self.assertEqual(recomputed["trials"][0]["score"]["RR"], Fraction(3, 8))
        self.assertTrue(recomputed["implementation_mismatch"])

    def test_predeclared_reason_codes_distinguish_failures(self):
        for i, (script, code, state) in enumerate((
                ([response(b'{}')], "script_exhausted", "aborted"),
                ([response(), response()], "script_leftover", "aborted"),
                ([response(b'{}'), response(b'{}')], "system_terminal_failure", "finished"))):
            plan, artifacts = bundle(responses=script, slots=1)
            store = Store.create(Path(self.temp.name) / f"reason-{i}.db", plan, artifacts)
            try:
                if state == "aborted":
                    with self.assertRaises(InvalidRecord):
                        run_offline(store, "slot-0")
                else:
                    run_offline(store, "slot-0")
                result = replay_slot(store, "slot-0")
                self.assertEqual((result["state"], result["reason_code"]), (state, code))
                self.assertEqual(result["score"]["measurement_valid"], state == "finished")
            finally:
                store.close()

    def test_new_plan_requires_unit_policy_and_event_ids(self):
        plan, artifacts = bundle()
        for field in ("unit", "invalidation_policy"):
            changed = decode(plan)
            del changed[field]
            with self.assertRaises(InvalidRecord):
                Store.create(self.path, encode(changed), artifacts)
        changed = decode(plan)
        changed["unit"] = "codepoints"
        with self.assertRaisesRegex(InvalidRecord, "unit"):
            Store.create(self.path, encode(changed), artifacts)
        m = fixture()
        m["unit"] = "utf8-bytes-v1"
        with self.assertRaisesRegex(InvalidRecord, "unit mismatch"):
            self.create(manifest=m)
        m = fixture()
        m["obligations"]["db"] = {"source": "intro", "begin": 1, "end": 20}
        with self.assertRaisesRegex(InvalidRecord, "event-ID"):
            self.create(manifest=m)
        self.assertFalse(self.path.exists())

    def test_abort_rejects_undeclared_code(self):
        store = self.create()
        store.append("slot-0", "start", {"evidence": "synthetic-offline", **implementation()})
        with self.assertRaisesRegex(InvalidRecord, "predeclared"):
            store.abort("slot-0", "some free text")
        self.assertEqual(report(store)["running"], 1)

    def test_legacy_export_remains_replayable(self):
        m = fixture()
        m["unit"] = "utf8-bytes-v1"
        m["obligations"]["db"] = {"source": "intro", "begin": 1, "end": 20}
        plan_raw, artifacts = bundle(manifest=m, responses=[response()], slots=1)
        plan = decode(plan_raw)
        plan["schema"] = "etps-offline-plan-v1"
        del plan["unit"]
        del plan["invalidation_policy"]
        raw = encode(plan)
        rows = [("start", {"scorer_sha256": "old", "runner_sha256": "old"}),
                ("event", {"node": "intro", "kind": "user", "text": "database=SQLite"}),
                ("request", {"node": "p1", "messages": [{"role": "user", "text": "database=SQLite"}]}),
                ("event", {"node": "p1", "kind": "probe", **response(), "answer": {"database": "SQLite"}}),
                ("finish", {"terminal": "pass", "wall_seconds": None})]
        previous = sha(encode([sha(raw), "slot-0"]))
        entries = []
        for i, (kind, payload) in enumerate(rows):
            previous = sha(encode(["slot-0", i, kind, previous]) + encode(payload))
            entries.append({"kind": kind, "payload": payload, "sha256": previous})
        exported = {"format": "etps-offline-export-v1", "plan_sha256": sha(raw),
                    "plan_base64": base64.b64encode(raw).decode(),
                    "artifacts": {key: base64.b64encode(value).decode() for key, value in artifacts.items()},
                    "journal": {"slot-0": entries}}
        r = replay_export(exported)
        self.assertTrue(r["implementation_mismatch"])
        self.assertEqual(r["trials"][0]["score"]["RR"], 0)
        self.assertIsNone(r["trials"][0]["score"]["TPS"])
        self.assertTrue(any("legacy_plan" in w for w in r["warnings"]))

    def test_cli_import_run_export_without_models(self):
        plan, artifacts = bundle(slots=1)
        plan_path = Path(self.temp.name) / "plan.json"
        plan_path.write_bytes(plan)
        args = [sys.executable, "-m", "etps_v02", "import", str(self.path), "--plan", str(plan_path)]
        for i, raw in enumerate(artifacts.values()):
            path = Path(self.temp.name) / f"artifact-{i}.json"
            path.write_bytes(raw)
            args += ["--artifact", str(path)]
        imported = subprocess.run(args, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(imported.stdout)["unattempted"], 1)
        subprocess.run([sys.executable, "-m", "etps_v02", "run", str(self.path), "--slot", "slot-0"],
                       check=True, capture_output=True, text=True)
        output = Path(self.temp.name) / "export.json"
        subprocess.run([sys.executable, "-m", "etps_v02", "export", str(self.path), "--output", str(output)],
                       check=True, capture_output=True, text=True)
        exported = json.loads(output.read_text())
        self.assertEqual(exported["report"]["accepted"], 1)
        self.assertEqual(base64.b64decode(exported["plan_base64"]), plan)
        checked = subprocess.run([sys.executable, "-m", "etps_v02", "replay-export", str(output),
                                  "--validate-authoring"], check=True, capture_output=True, text=True)
        self.assertTrue(json.loads(checked.stdout)["authoring_gate_reasserted"])


if __name__ == "__main__":
    unittest.main()
