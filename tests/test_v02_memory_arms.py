"""Generic memory-arm diagnostics; synthetic HTTP servers, no model calls."""
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.memory_telemetry import requests, summarize
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import decode, encode, sha, validate_bundle
from test_v02_live_adapter import FakeServer, bundle
from test_v02_session_profile import rechain


class MemoryArmsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stores = []

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.temp.cleanup()

    def create(self, plan, artifacts):
        self.assertGreaterEqual(plan["request_deadline_seconds"], 10)
        self.assertGreaterEqual(plan["trial_wall_limit_seconds"], 10)
        store = Store.create(Path(self.temp.name) / f"{len(self.stores)}.db", encode(plan), artifacts)
        self.stores.append(store)
        return store

    def test_three_arms_same_policy_separate_repetitions_and_unattempted(self):
        telemetry = {"extraction_calls": 2, "extraction_prompt_tokens": 25,
                     "extraction_completion_tokens": 4, "extraction_seconds": .1,
                     "beliefs_injected": 1, "injected_chars": 18, "version": "synthetic"}
        with FakeServer(extra={"x_memory": telemetry, "usage": {"prompt_tokens": 30},
                               "timings": {"predicted_n": 12, "predicted_ms": 600}}) as server:
            p, a = bundle(server.url, cache_policy="warm-declared")
            base = p["arms"]["private-arm-label"]
            p["arms"] = {"full": {**base, "context_policy": "full"},
                         "reset": {**base, "context_policy": "reset-v1"},
                         "memory": {**base, "context_policy": "reset-v1", "memory_telemetry_field": "x_memory"}}
            p["slots"] = [{"id": str(i), "arm": arm, "task": "synthetic-task"}
                          for i, arm in enumerate(("full", "reset", "memory", "memory", "memory"))]
            m = decode(next(iter(a.values())))
            m["answer_tolerance"] = "d10-v1"
            raw = encode(m)
            p["tasks"] = {"synthetic-task": sha(raw)}
            store = self.create(p, {sha(raw): raw})
            for slot in p["slots"][:-1]:
                run_live(store, slot["id"], allow_live=True)
            r = report(store)
            self.assertEqual(r["cache_policy"], "warm-declared")
            arms = r["arm_comparison"]["synthetic-task"]["arms"]
            self.assertEqual(set(arms), {"full", "reset", "memory"})
            self.assertEqual([t["slot"] for t in arms["reset"]["trials"]], ["1"])
            self.assertEqual([t["slot"] for t in arms["memory"]["trials"]], ["2", "3", "4"])
            self.assertEqual(arms["memory"]["context_policy"], "reset-v1")
            self.assertEqual(arms["memory"]["provider"], "openai-compatible")
            self.assertEqual(arms["memory"]["trials"][0]["result_state"], "accepted_exact")
            self.assertIsNone(arms["memory"]["trials"][-1]["accepted"])
            self.assertEqual(arms["memory"]["processed_prompt_tokens"]["total"], 60)
            memory = r["memory_telemetry"]["memory"]
            self.assertEqual(memory["request_count"], 2)  # Unattempted is not a request.
            self.assertEqual(memory["metrics"]["extraction_calls"], {"sum": 4, "coverage_count": 2, "request_count": 2})
            self.assertEqual(memory["metrics"]["extraction_seconds"]["sum"], Fraction(1, 5))
            self.assertEqual(len(r["context_policy_pairing"]["synthetic-task"]["reset-v1"]), 4)
            # Existing policy entries keep their exact schema, without memory fields.
            old = r["context_policy_pairing"]["synthetic-task"]["reset-v1"][0]
            self.assertEqual(set(old), {"slot", "arm", "state", "accepted", "first_attempt", "retention",
                "I", "R", "RR", "TPS", "experimental_eTPS", "processed_prompt_tokens", "requests"})
            for key in ("I", "R", "RR", "TPS", "eTPS"):
                self.assertEqual(arms["full"]["trials"][0][key], arms["memory"]["trials"][0][key])
            for _, body, _ in server.seen:
                self.assertNotIn("memory_telemetry_field", body)
                self.assertNotIn("cache_policy", body)
            for version in ("v1", "v2"):
                replayed = replay_export(export_bundle(store, version))
                self.assertEqual(replayed["arm_comparison"], r["arm_comparison"])
                self.assertEqual(replayed["memory_telemetry"], r["memory_telemetry"])
                self.assertEqual(replayed["cache_policy"], "warm-declared")

    def test_object_copied_exactly_and_missing_numeric_coverage(self):
        value = {"extraction_calls": "2", "beliefs_injected": 0, "extraction_seconds": -.25, "note": " exact "}
        with FakeServer(extra={"x_memory": value}) as server:
            p, a = bundle(server.url)
            p["arms"]["private-arm-label"]["memory_telemetry_field"] = "x_memory"
            store = self.create(p, a)
            trial = run_live(store, "slot", allow_live=True)
            event = trial["record"]["events"][-1]
            self.assertEqual(encode(event["memory_telemetry"]), encode(value))
            self.assertEqual(event["memory_telemetry_status"], "valid")
            metrics = report(store)["memory_telemetry"]["private-arm-label"]["metrics"]
            self.assertEqual(metrics["extraction_calls"]["coverage_count"], 0)
            self.assertEqual(metrics["beliefs_injected"]["coverage_count"], 1)
            self.assertEqual(metrics["extraction_seconds"]["sum"], Fraction(-1, 4))
            self.assertTrue(trial["score"]["accepted"])
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_malformed_objects_record_invalid_without_scoring_change(self):
        for value in ([], "bad", 3, None, {"a": True}, {"a": None}, {"a": []}, {"a": {}}, {"a": "\ud800"}):
            # Raw JSON permits a surrogate escape to exercise invalid Unicode safely.
            import json
            raw = json.dumps({"choices": [{"message": {"role": "assistant", "content": '{"answer":"expected-private-marker"}'}}],
                              "x_memory": value}).encode()
            with self.subTest(value=value), FakeServer(raw=raw) as server:
                p, a = bundle(server.url)
                p["arms"]["private-arm-label"]["memory_telemetry_field"] = "x_memory"
                store = self.create(p, a)
                trial = run_live(store, "slot", allow_live=True)
                event = trial["record"]["events"][-1]
                self.assertIsNone(event["memory_telemetry"])
                self.assertEqual(event["memory_telemetry_status"], "invalid")
                self.assertTrue(trial["score"]["accepted"])
                self.assertEqual(report(store)["memory_telemetry"]["private-arm-label"]["invalid_count"], 1)
                self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_nonfinite_numbers_missing_field_and_absent_opt_in(self):
        raw = b'{"choices":[{"message":{"role":"assistant","content":"{\\"answer\\":\\"expected-private-marker\\"}"}}],"x_memory":{"extraction_seconds":1e999}}'
        with FakeServer(raw=raw) as server:
            p, a = bundle(server.url)
            p["arms"]["private-arm-label"]["memory_telemetry_field"] = "x_memory"
            trial = run_live(self.create(p, a), "slot", allow_live=True)
            self.assertEqual(trial["record"]["events"][-1]["memory_telemetry_status"], "invalid")
            self.assertTrue(trial["score"]["accepted"])
        with FakeServer() as server:
            p, a = bundle(server.url)
            legacy = self.create(p, a)
            r = run_live(legacy, "slot", allow_live=True)
            self.assertNotIn("memory_telemetry", r["record"]["events"][-1])
            self.assertNotIn("memory_telemetry", report(legacy))
            self.assertNotIn("cache_policy", report(legacy))
            p["arms"]["private-arm-label"]["memory_telemetry_field"] = "absent"
            store = self.create(p, a)
            r = run_live(store, "slot", allow_live=True)
            self.assertEqual(r["record"]["events"][-1]["memory_telemetry_status"], "missing")
            self.assertEqual(report(store)["memory_telemetry"]["private-arm-label"]["missing_count"], 1)

    def test_rehashed_projection_tampering_rejected(self):
        with FakeServer(extra={"x_memory": {"extraction_calls": 1}}) as server:
            p, a = bundle(server.url)
            p["arms"]["private-arm-label"]["memory_telemetry_field"] = "x_memory"
            store = self.create(p, a)
            run_live(store, "slot", allow_live=True)
            for mode in ("value", "status", "missing"):
                exported = export_bundle(store)
                event = next(r["payload"] for r in exported["journal"]["slot"]
                             if r["kind"] == "event" and r["payload"]["kind"] == "probe")
                if mode == "value": event["memory_telemetry"]["extraction_calls"] = 999
                elif mode == "status": event["memory_telemetry_status"] = "invalid"
                else: del event["memory_telemetry"]
                rechain(exported)
                with self.subTest(mode=mode), self.assertRaisesRegex(InvalidRecord, "memory telemetry projection"):
                    replay_export(exported)

    def test_schema_validation(self):
        for field, values in (("cache_policy", (None, "cold", {}, True)),
                              ("memory_telemetry_field", (None, "", [], 5))):
            for value in values:
                p, a = bundle("http://127.0.0.1:1")
                target = p if field == "cache_policy" else p["arms"]["private-arm-label"]
                target[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(InvalidRecord):
                    validate_bundle(encode(p), a)

    def test_pending_and_failed_requests_remain_in_denominator(self):
        rows = [{"kind": "request", "payload": {}},
                {"kind": "event", "payload": {"kind": "probe", "status": "timeout",
                 "memory_telemetry_status": "valid", "memory_telemetry": {"extraction_calls": 3}}},
                {"kind": "request", "payload": {}}]
        summary = summarize(requests(rows))
        self.assertEqual(summary["request_count"], 2)
        self.assertEqual(summary["unavailable_count"], 1)
        self.assertEqual(summary["metrics"]["extraction_calls"], {"sum": 3, "coverage_count": 1, "request_count": 2})

    def test_error_response_costs_are_retained_and_replayed(self):
        with FakeServer(status=500, extra={"x_memory": {"extraction_calls": 2}}) as server:
            p, a = bundle(server.url)
            p["arms"]["private-arm-label"]["memory_telemetry_field"] = "x_memory"
            store = self.create(p, a)
            trial = run_live(store, "slot", allow_live=True)
            self.assertFalse(trial["score"]["accepted"])
            self.assertIsNone(trial["score"]["TPS"])
            summary = report(store)["memory_telemetry"]["private-arm-label"]
            self.assertEqual(summary["metrics"]["extraction_calls"],
                             {"sum": 2, "coverage_count": 1, "request_count": 1})
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)
