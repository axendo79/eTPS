"""Codex-authored audit regressions. Synthetic evidence only; no model calls."""
import base64
import copy
from fractions import Fraction
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.persistence import Store
from etps_v02.runner import answer_from_raw, export_bundle, replay_export, replay_slot, run_offline
from etps_v02.scorer import InvalidRecord, digest, finite, score, validate
from etps_v02.workload import decode, encode, script_responses, sha, validate_bundle
from test_v02_runner import bundle, response
from test_v02_scorer import fixture, replay, user


class RepairTests(unittest.TestCase):
    def test_v07_long_graph_and_cycle_use_iterative_validation(self):
        m = {"unit": "utf8_bytes", "start": "n0", "obligations": {}, "nodes": {}}
        for i in range(1100):
            m["nodes"][f"n{i}"] = user("", f"n{i + 1}")
        m["nodes"]["n1100"] = {"kind": "terminal", "accepted": True}
        self.assertEqual(validate(m), [])
        m["nodes"]["n1100"] = user("", "n0")
        with self.assertRaisesRegex(InvalidRecord, "cyclic policy"):
            validate(m)

    def test_v01_legacy_malformed_json_projection_remains_replayable(self):
        exported = self.exported(responses=[response(b'{"x":1}'), response()])
        event = next(e["payload"] for e in exported["journal"]["slot-0"]
                     if e["kind"] == "event" and e["payload"]["kind"] == "probe")
        event["answer"] = {"x": 1}
        self.rehash(exported)
        trial = replay_export(exported)["trials"][0]
        self.assertTrue(trial["evidence_verified"])
        self.assertTrue(trial["score"]["measurement_valid"])
        self.assertTrue(any(w.startswith("legacy_answer_projection:") for w in trial["warnings"]))
        event["answer"] = {"x": 2}
        self.rehash(exported)
        with self.assertRaisesRegex(InvalidRecord, "raw answer projection mismatch"):
            replay_export(exported)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.serial = 0

    def create(self, **kwargs):
        plan, artifacts = bundle(slots=1, **kwargs)
        self.serial += 1
        path = Path(self.temp.name) / f"case-{self.serial}.db"
        store = Store.create(path, plan, artifacts)
        self.addCleanup(store.close)
        return store

    def exported(self, **kwargs):
        store = self.create(**kwargs)
        run_offline(store, "slot-0")
        return export_bundle(store)

    def rehash(self, exported):
        # Deliberately preserve a coherent hash chain so semantic checks, rather
        # than an incidental checksum failure, detect the audit counterexample.
        messages = []
        previous = sha(encode([exported["plan_sha256"], "slot-0"]))
        for i, entry in enumerate(exported["journal"]["slot-0"]):
            kind, payload = entry["kind"], entry["payload"]
            if kind == "request":
                payload["messages"] = copy.deepcopy(messages)
            elif kind == "event":
                if payload["kind"] == "user":
                    messages.append({"role": "user", "text": payload["text"]})
                else:
                    messages.append({"role": "assistant", "raw_base64": payload["raw_base64"]})
            previous = sha(encode(["slot-0", i, kind, previous]) + encode(payload))
            entry["sha256"] = previous

    def replace_script(self, exported, responses):
        plan = decode(base64.b64decode(exported["plan_base64"]))
        old = plan["slots"][0]["script_sha256"]
        del exported["artifacts"][old]
        raw = encode({"responses": responses})
        exported["artifacts"][sha(raw)] = base64.b64encode(raw).decode()
        plan["slots"][0]["script_sha256"] = sha(raw)
        raw = encode(plan)
        exported["plan_base64"] = base64.b64encode(raw).decode()
        exported["plan_sha256"] = sha(raw)
        self.rehash(exported)

    def assert_unverified(self, exported, code):
        result = replay_export(exported)
        trial = result["trials"][0]
        self.assertFalse(trial["evidence_verified"])
        self.assertIn(code, {issue["code"] for issue in trial["evidence_issues"]})
        self.assertTrue(any(code in w for w in result["warnings"]))
        self.assertEqual(result["evidence_unverified"], 1)
        self.assertTrue(result["comparison_incomplete"])
        self.assertFalse(trial["score"]["measurement_valid"])
        self.assertIsNone(trial["score"]["RR"])
        self.assertIsNone(trial["score"]["accepted"])
        self.assertEqual(result["planned"], 1)
        self.assertEqual(result["attempted"], 1)
        return trial

    def test_v01_invalid_numbers_and_surrogates_are_journaled_malformed(self):
        for raw in (b'{"x":1e999}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":-Infinity}', b'{"x":"\\ud800"}', b'{"\\udfff":"x"}'):
            for final in (response(), response(b'{}')):
                with self.subTest(raw=raw, final=final):
                    store = self.create(responses=[response(raw), final])
                    result = run_offline(store, "slot-0")
                    observed = result["record"]["events"][1]
                    self.assertEqual(base64.b64decode(observed["raw_base64"]), raw)
                    self.assertIsNone(observed["answer"])
                    self.assertEqual(result["score"]["classifications"][1]["class"], "malformed")
                    self.assertEqual(result["state"], "finished")
                    self.assertTrue(result["score"]["measurement_valid"])
                    self.assertEqual(result["score"]["RR"], Fraction(3, 8))
                    self.assertEqual(result["score"]["accepted"], final == response())
                    self.assertEqual(replay_slot(store, "slot-0")["score"], result["score"])

    def test_v01_arbitrary_bytes_project_without_parser_errors(self):
        for raw in (b'', bytes(range(256)), b'null', b'42', b'[]',
                    b'{"x":[1]}', b'[' * 2000 + b'0' + b']' * 2000):
            with self.subTest(raw=raw[:20]):
                self.assertIsNone(answer_from_raw(raw))
        with patch("etps_v02.runner.decode", side_effect=RecursionError):
            self.assertIsNone(answer_from_raw(b'{}'))
        self.assertEqual(answer_from_raw(b'{"database":"wrong"}'), {"database": "wrong"})
        self.assertEqual(answer_from_raw(b'{"status":"unknown"}'), {"status": "unknown"})

    def test_v01_storage_and_harness_errors_remain_distinct(self):
        for exc, code in ((sqlite3.OperationalError("write failed"), "storage_error"),
                          (RuntimeError("controller failed"), "execution_error")):
            with self.subTest(code=code):
                store = self.create()
                original = store.append
                failed = False

                def append(slot, kind, payload):
                    nonlocal failed
                    if kind == "event" and not failed:
                        failed = True
                        raise exc
                    return original(slot, kind, payload)

                with patch.object(store, "append", side_effect=append):
                    with self.assertRaises(type(exc)):
                        run_offline(store, "slot-0")
                result = replay_slot(store, "slot-0")
                self.assertEqual(result["reason_code"], code)
                self.assertEqual(result["state"], "aborted")
                self.assertIsNone(result["score"]["RR"])

    def test_v04_manifest_shapes_fail_closed(self):
        for value in (None, 1, "scalar", [], {}, {"unit": "utf8_bytes"}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(InvalidRecord, "manifest"):
                    validate(value)
        changes = [((), "unit", []), ((), "nodes", []), ((), "obligations", None),
                   ((), "start", []), (("nodes",), "p1", None),
                   (("nodes", "p1"), "next", []), (("nodes", "p1"), "obligations", [[]]),
                   (("nodes", "p1", "next"), "correct", []),
                   (("nodes", "recover"), "failure", ["p1"]),
                   (("nodes", "recover"), "spans", None),
                   (("nodes", "recover"), "spans", [[0, 15]]),
                   (("nodes", "recover"), "spans", [[0, 15, []]]),
                   (("obligations",), "db", []),
                   (("obligations", "db"), "source", []),
                   (("obligations", "db"), "end_before", [])]
        for path, key, value in changes:
            with self.subTest(path=path, key=key):
                m = fixture()
                target = m
                for part in path:
                    target = target[part]
                target[key] = value
                with self.assertRaises(InvalidRecord):
                    validate(m)
        m = fixture()
        m["nodes"]["recover"]["failure"] = []
        with self.assertRaisesRegex(InvalidRecord, r"manifest.nodes.recover.failure"):
            validate(m)

    def test_v04_plan_and_script_shapes_fail_before_database_creation(self):
        plan_raw, artifacts = bundle(slots=1)
        for value in (None, 4, "scalar", [], {}, {"schema": []}):
            with self.subTest(value=value):
                path = Path(self.temp.name) / "invalid.db"
                with self.assertRaises(InvalidRecord):
                    Store.create(path, encode(value), artifacts)
                self.assertFalse(path.exists())
        for field, value in (("tasks", {"synthetic": []}), ("slots", [None]),
                             ("slots", [[]]), ("slots", [{"id": []}])):
            plan = decode(plan_raw)
            plan[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidRecord):
                validate_bundle(encode(plan), artifacts)
        for value in (None, [], {"status": []}, {"status": "ok", "raw_base64": []},
                      {**response(), "generation": []},
                      {**response(), "generation": {"tokens": [], "seconds": 1}}):
            with self.subTest(response=value), self.assertRaises(InvalidRecord):
                script_responses(encode({"responses": [value]}))

    def test_v04_finite_large_integers_do_not_overflow(self):
        self.assertTrue(finite(10 ** 400))
        self.assertFalse(finite(-(10 ** 400)))
        for value in (None, [], {}, True, float("inf"), float("nan")):
            self.assertFalse(finite(value))
        self.assertFalse(finite(0, positive=True))

    def test_v04_record_and_export_shapes_fail_closed(self):
        for value in (None, [], 1, {}, {"events": []}):
            with self.subTest(value=value):
                with self.assertRaises(InvalidRecord):
                    score(fixture(), value)
                with self.assertRaises(InvalidRecord):
                    replay_export(value)
        for value in (None, [], {}, {"node": [], "kind": "probe"}):
            record = replay(fixture())
            record["events"] = [value]
            with self.assertRaises(InvalidRecord):
                score(fixture(), record)

    def test_v04_cli_validation_errors_are_concise_and_create_no_database(self):
        plan_raw, artifacts = bundle(slots=1)
        root = Path(self.temp.name)
        for index, invalid in enumerate((b'null', b'[]', b'4')):
            plan_path = root / f"plan-{index}.json"
            plan_path.write_bytes(invalid)
            paths = []
            for key, raw in artifacts.items():
                artifact_path = root / key
                artifact_path.write_bytes(raw)
                paths += ["--artifact", str(artifact_path)]
            db = root / f"cli-{index}.db"
            result = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "import", str(db),
                                     "--plan", str(plan_path), *paths], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error: plan:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(db.exists())

    def test_v05_unknown_manifest_and_node_fields_rejected_for_authoring(self):
        for node in (None, "intro", "p1", "pass"):
            m = fixture()
            target = m if node is None else m["nodes"][node]
            target["budget_seconds"] = 0
            with self.subTest(node=node):
                with self.assertRaisesRegex(InvalidRecord, "unrecognized fields budget_seconds"):
                    validate(m)
                findings = validate(m, authoring=False)
                self.assertEqual(findings[0]["code"], "legacy_unrecognized_fields")
                self.assertIn("budget_seconds", findings[0]["fields"])
                self.assertTrue(score(m, replay(m))["measurement_valid"])

    def test_v05_metadata_is_hashed_but_has_no_executable_effect(self):
        m = fixture()
        baseline = score(m, replay(m))
        original_hash = digest(m)
        m["metadata"] = {"budget_seconds": 0, "accepted": False}
        for node in m["nodes"].values():
            node["metadata"] = {"next": "missing", "budget_seconds": 0}
        self.assertFalse(validate(m))
        self.assertNotEqual(digest(m), original_hash)
        result = score(m, replay(m))
        for key in ("RR", "I", "R", "accepted", "classifications"):
            self.assertEqual(result[key], baseline[key])
        for target in (m, m["nodes"]["intro"]):
            target["metadata"] = []
            with self.assertRaisesRegex(InvalidRecord, "metadata: expected object"):
                validate(m)
            target["metadata"] = {}

    def test_v05_old_export_unknown_fields_remain_visible_even_unattempted(self):
        m = fixture()
        m["nodes"]["intro"]["budget_seconds"] = 0
        plan, artifacts = bundle(manifest=m, slots=1)
        exported = {"format": "etps-offline-export-v1", "plan_sha256": sha(plan),
                    "plan_base64": base64.b64encode(plan).decode(),
                    "artifacts": {k: base64.b64encode(v).decode() for k, v in artifacts.items()},
                    "journal": {"slot-0": []}}
        result = replay_export(exported)
        self.assertTrue(any("legacy_unrecognized_fields" in w for w in result["warnings"]))
        with self.assertRaisesRegex(InvalidRecord, "unrecognized fields"):
            replay_export(exported, validate_authoring=True)

    def test_v06_future_failure_is_rejected_before_import(self):
        m = fixture()
        m["nodes"]["recover"]["failure"] = "p2"
        with self.assertRaisesRegex(InvalidRecord, "failure: probe is not a path-ancestor"):
            validate(m)
        plan, artifacts = bundle(manifest=m, slots=1)
        path = Path(self.temp.name) / "future.db"
        with self.assertRaises(InvalidRecord):
            Store.create(path, plan, artifacts)
        self.assertFalse(path.exists())
        findings = validate(m, authoring=False)
        self.assertEqual(findings[0]["code"], "recovery_failure_not_ancestor")
        self.assertEqual(score(m, replay(m))["reason"], "unlinked_recovery")

    def test_v06_linked_probe_must_test_recovery_obligation(self):
        m = fixture()
        m["nodes"]["p1"]["obligations"] = []
        with self.assertRaisesRegex(InvalidRecord, "failure probe does not test db"):
            validate(m)
        self.assertEqual(validate(m, authoring=False)[0]["code"], "recovery_obligation_not_tested")

    def test_v06_mutually_exclusive_legitimate_recoveries_still_pass(self):
        m = fixture()
        m["nodes"]["alternate"] = user("database=SQLite", "p2", [[0, 15, "db"]], "p1")
        m["nodes"]["p1"]["next"]["unknown"] = "alternate"
        self.assertFalse(validate(m))
        for first in (response(b'{}'), response(b'{"status":"unknown"}')):
            store = self.create(manifest=m, responses=[first, response()])
            result = run_offline(store, "slot-0")
            self.assertTrue(result["score"]["measurement_valid"])
            self.assertEqual(result["score"]["R"], 15)

    def test_v02_replay_compares_status_bytes_and_generation(self):
        original = self.exported()
        for field, value in (("status", "timeout"), ("raw_base64", response(b'{}')["raw_base64"]),
                             ("generation", {"tokens": 51, "seconds": 1})):
            with self.subTest(field=field):
                exported = copy.deepcopy(original)
                event = next(e["payload"] for e in exported["journal"]["slot-0"]
                             if e["kind"] == "event" and e["payload"]["kind"] == "probe")
                event[field] = value
                if field == "raw_base64":
                    event["answer"] = {}
                self.rehash(exported)
                trial = self.assert_unverified(exported, "script_response_mismatch")
                self.assertIsNotNone(trial["recomputed_score"])

    def test_v02_finished_evidence_requires_exact_script_consumption(self):
        for script, code in (([], "script_exhausted"), ([response(), response()], "script_leftover")):
            exported = self.exported(responses=[response()])
            self.replace_script(exported, script)
            self.assert_unverified(exported, code)

    def test_v02_interrupted_journal_must_be_script_prefix(self):
        exported = self.exported()
        entries = exported["journal"]["slot-0"]
        first_probe = next(i for i, e in enumerate(entries)
                           if e["kind"] == "event" and e["payload"]["kind"] == "probe")
        exported["journal"]["slot-0"] = entries[:first_probe + 1]
        self.rehash(exported)
        trial = replay_export(exported)["trials"][0]
        self.assertTrue(trial["evidence_verified"])
        self.assertEqual(trial["state"], "running")
        self.assertIsNone(trial["score"]["RR"])
        exported["journal"]["slot-0"][-1]["payload"]["status"] = "timeout"
        self.rehash(exported)
        self.assert_unverified(exported, "script_response_mismatch")

    def test_v02_adapter_substitution_cannot_finish_as_verified(self):
        store = self.create(responses=[response(b'{}')])
        with patch("etps_v02.runner._next_response", return_value=response()):
            with self.assertRaisesRegex(InvalidRecord, "invalid scoring provenance"):
                run_offline(store, "slot-0")
        trial = replay_slot(store, "slot-0")
        self.assertEqual(trial["state"], "aborted")
        self.assertFalse(trial["evidence_verified"])
        self.assertIsNone(trial["score"]["RR"])

    def test_v03_finish_terminal_must_match_reached_terminal(self):
        exported = self.exported()
        exported["journal"]["slot-0"][-1]["payload"]["terminal"] = "fail"
        self.rehash(exported)
        trial = self.assert_unverified(exported, "finish_terminal_mismatch")
        self.assertTrue(trial["recomputed_score"]["accepted"])
        self.assertEqual(trial["recomputed_score"]["terminal"], "pass")

    def test_v03_finish_reason_must_agree_with_acceptance(self):
        for responses, reason in (([response()], "system_terminal_failure"),
                                  ([response(b'{}'), response(b'{}')], None),
                                  ([response()], "invented")):
            exported = self.exported(responses=responses)
            exported["journal"]["slot-0"][-1]["payload"]["reason_code"] = reason
            self.rehash(exported)
            trial = self.assert_unverified(exported, "finish_reason_mismatch")
            self.assertIsInstance(trial["recomputed_score"]["accepted"], bool)

    def test_v03_missing_v2_finish_fields_are_invalid_evidence(self):
        for field, code in (("terminal", "finish_terminal_mismatch"),
                            ("reason_code", "finish_reason_mismatch")):
            exported = self.exported()
            del exported["journal"]["slot-0"][-1]["payload"][field]
            self.rehash(exported)
            self.assert_unverified(exported, code)

    def test_v03_abort_codes_are_checked_during_export_and_database_replay(self):
        store = self.create()
        from etps_v02.runner import implementation
        store.append("slot-0", "start", implementation())
        store.abort("slot-0", "operator_abort", "synthetic test")
        exported = export_bundle(store)
        self.assertTrue(replay_export(exported)["trials"][0]["evidence_verified"])
        for code in ("invented", "system_terminal_failure", [], None):
            changed = copy.deepcopy(exported)
            changed["journal"]["slot-0"][-1]["payload"]["reason_code"] = code
            self.rehash(changed)
            self.assert_unverified(changed, "abort_reason_invalid")
        changed = copy.deepcopy(exported)
        changed["journal"]["slot-0"][-1]["payload"]["reason_code"] = "invented"
        self.rehash(changed)
        # A coherent stored chain must face the same semantic checks as export.
        store.db.execute("DROP TRIGGER immutable_journal_UPDATE")
        entry = changed["journal"]["slot-0"][-1]
        store.db.execute("UPDATE journal SET payload=?,hash=? WHERE slot=? AND kind='abort'",
                         (encode(entry["payload"]), entry["sha256"], "slot-0"))
        store.db.execute("UPDATE heads SET hash=? WHERE slot=?", (entry["sha256"], "slot-0"))
        store.db.commit()
        trial = replay_slot(store, "slot-0")
        self.assertFalse(trial["evidence_verified"])
        self.assertEqual(trial["evidence_issues"], [{"code": "abort_reason_invalid"}])
