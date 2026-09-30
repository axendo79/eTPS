"""Decode-v1 HTTP fixtures; all servers are ephemeral synthetic servers."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import decode, encode, sha
from test_v02_live_adapter import FakeServer, bundle


class DecodeTimingTests(unittest.TestCase):
    def execute(self, extra, provider="lmstudio-native", convention="decode-v1", d10=False):
        with FakeServer(extra=extra) as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle(server.url, provider)
            if convention:
                p["timing_convention"] = convention
            if d10:
                m = decode(next(iter(a.values())))
                m["answer_tolerance"] = "d10-v1"
                m["nodes"]["p"]["expected"] = {"answer": "EXPECTED-PRIVATE-MARKER"}
                m["nodes"]["p"]["fixed_value_fields"] = ["answer"]
                raw = encode(m)
                p["tasks"] = {"synthetic-task": sha(raw)}
                a = {sha(raw): raw}
            store = Store.create(Path(temp) / "test.db", encode(p), a)
            try:
                r = run_live(store, "slot", allow_live=True)
                self.assertEqual(replay_export(export_bundle(store, "v2"))["trials"][0], r)
                return r
            finally:
                store.close()

    def test_native_context_pressure_arithmetic_sources_and_d10(self):
        extra = {"usage": {"completion_tokens": 70, "prompt_tokens": 400,
                           "completion_tokens_details": {"reasoning_tokens": 50}},
                 "stats": {"generation_time": 3.217, "time_to_first_token": 1.595, "prompt_eval_time": 1.2}}
        r = self.execute(extra, d10=True)
        self.assertEqual(r["score"]["TPS"], Fraction(34500, 811))
        self.assertEqual(round(float(r["score"]["TPS"]), 2), 42.54)
        self.assertEqual(r["score"]["experimental_eTPS"], r["score"]["TPS"])
        self.assertEqual(r["score"]["result_state"], "accepted_with_format_deviation")
        t = r["record"]["events"][-1]["timing"]
        self.assertAlmostEqual(t["full_generation_tps"]["value"], 70 / 3.217)
        self.assertEqual(t["decode_seconds"]["value"], 1.622)
        self.assertEqual(t["completion_tokens"]["value"], 70)
        self.assertEqual(t["prompt_tokens"]["value"], 400)
        self.assertEqual(t["ttft_seconds"]["value"], 1.595)
        self.assertEqual(t["decode_tps"]["source_fields"],
                         ["usage.completion_tokens", "stats.generation_time", "stats.time_to_first_token"])

    def test_missing_invalid_or_short_native_intervals(self):
        extras = [{}]
        for count, gen, first in ((0, 1, .5), (1, 1, .5), (True, 1, .5), (70, 1, 1),
                                  (70, 1, 2), (70, 1, None), (70, None, .5)):
            extras.append({"usage": {"completion_tokens": count},
                           "stats": {"generation_time": gen, "time_to_first_token": first}})
        for extra in extras:
            with self.subTest(extra=extra):
                r = self.execute(extra)
                self.assertTrue(r["score"]["accepted"])
                self.assertIsNone(r["score"]["TPS"])
                self.assertIsNone(r["score"]["experimental_eTPS"])

    def test_compatible_predicted_is_ambiguous_explicit_decode_only(self):
        r = self.execute({"timings": {"predicted_n": 70, "predicted_ms": 3217}}, "openai-compatible")
        self.assertIsNone(r["score"]["TPS"])
        r = self.execute({"timings": {"decode_n": 69, "decode_ms": 1622, "prompt_ms": 100,
                                      "full_generation_n": 70, "full_generation_ms": 3217}}, "openai-compatible")
        self.assertEqual(r["score"]["TPS"], Fraction(34500, 811))
        self.assertAlmostEqual(r["record"]["events"][-1]["timing"]["full_generation_tps"]["value"], 70 / 3.217)

    def test_legacy_and_unknown_convention(self):
        r = self.execute({"usage": {"completion_tokens": 70}, "stats": {"generation_time": 3.217}}, convention=None)
        self.assertEqual(r["score"]["TPS"], Fraction(70000, 3217))
        self.assertNotIn("timing", r["record"]["events"][-1])
        self.assertNotIn("timing_convention", r["score"])
        with self.assertRaisesRegex(InvalidRecord, "timing_convention"):
            self.execute({}, convention="decode-v2")

    def test_rehashed_timing_projection_tampering_is_rejected(self):
        with FakeServer(extra={"usage": {"completion_tokens": 8},
                               "stats": {"generation_time": 2, "time_to_first_token": 1}}) as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle(server.url, "lmstudio-native", timing_convention="decode-v1")
            store = Store.create(Path(temp) / "test.db", encode(p), a)
            try:
                run_live(store, "slot", allow_live=True)
                original = export_bundle(store)
                for field in ("decode_tps", "full_generation_tps", "ttft_seconds", "completion_tokens"):
                    exported = copy.deepcopy(original)
                    rows = exported["journal"]["slot"]
                    event = next(r["payload"] for r in rows if r["kind"] == "event" and r["payload"]["kind"] == "probe")
                    event["timing"][field]["value"] = 999
                    previous = sha(encode([exported["plan_sha256"], "slot"]))
                    for i, row in enumerate(rows):
                        row["sha256"] = sha(encode(["slot", i, row["kind"], previous]) + encode(row["payload"]))
                        previous = row["sha256"]
                    with self.subTest(field=field), self.assertRaisesRegex(InvalidRecord, "timing projection"):
                        replay_export(exported)
            finally:
                store.close()

    def test_timing_is_live_only_and_transport_failure_has_sources(self):
        from etps_v02.workload import validate_bundle
        from test_v02_runner import bundle as offline_bundle
        raw, artifacts = offline_bundle()
        plan = decode(raw)
        plan["timing_convention"] = "decode-v1"
        with self.assertRaisesRegex(InvalidRecord, "plan fields"):
            validate_bundle(encode(plan), artifacts)
        with FakeServer(status=500) as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle(server.url, "lmstudio-native", timing_convention="decode-v1")
            store = Store.create(Path(temp) / "test.db", encode(p), a)
            try:
                r = run_live(store, "slot", allow_live=True)
                self.assertFalse(r["score"]["accepted"])
                self.assertIsNone(r["score"]["TPS"])
                t = r["record"]["events"][-1]["timing"]
                self.assertEqual(t["client_elapsed_seconds"]["source_fields"], ["client_latency_seconds"])
                self.assertEqual(replay_export(export_bundle(store))["trials"][0], r)
            finally:
                store.close()
