"""Boundary delivery uses synthetic public facts and ephemeral fake servers."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report
from etps_v02.scorer import InvalidRecord, score
from etps_v02.workload import decode, encode, sha, validate_bundle
from test_v02_live_adapter import FakeServer, bundle
from test_v02_scorer import user
from test_v02_session_profile import rechain


def plan(url, policy="reset-v1", enabled=True, requested=False):
    p, a = bundle(url, "lmstudio-native", timing_convention="decode-v1")
    if enabled:
        p["boundary_delivery"] = "deliver-v1"
    arm = p["arms"]["private-arm-label"]
    arm.update(context_policy=policy, memory_telemetry_field="x_memory")
    m = decode(next(iter(a.values())))
    m["answer_tolerance"] = "d10-v1"
    m["nodes"]["intro"] = user("Synthetic fact: widget color is violet.", "boundary")
    m["nodes"]["boundary"] = {"kind": "session_boundary", "next": "question"}
    m["nodes"]["question"] = user("Report the synthetic answer.", "p")
    m["obligations"] = {"fact": {"source": "intro", "begin_after": "intro", "end_before": "$trial_end"}}
    m["nodes"]["p"]["obligations"] = ["fact"]
    if requested:
        m["nodes"]["intro"]["next"] = "earlier"
        m["nodes"]["earlier"] = copy.deepcopy(m["nodes"]["p"])
        m["nodes"]["earlier"]["next"] = {key: "boundary" for key in m["nodes"]["earlier"]["next"]}
    raw = encode(m)
    p["tasks"] = {"synthetic-task": sha(raw)}
    return p, {sha(raw): raw}


class BoundaryDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stores = []

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.temp.cleanup()

    def create(self, p, a):
        self.assertGreaterEqual(p["request_deadline_seconds"], 10)
        self.assertGreaterEqual(p["trial_wall_limit_seconds"], 10)
        store = Store.create(Path(self.temp.name) / f"{len(self.stores)}.db", encode(p), a)
        self.stores.append(store)
        return store

    def test_full_reset_and_memory_receive_delivery_scoring_excludes_reply(self):
        for policy in ("full", "reset-v1"):
            extra = {}
            def callback():
                delivery = len(server.seen) == 1
                extra.update(choices=[{"message": {"role": "assistant", "content":
                    "This is unclassified delivery prose." if delivery else '{"answer":"expected-private-marker"}'}}],
                    usage={"prompt_tokens": 3, "completion_tokens": 101 if delivery else 11},
                    stats={"generation_time": 1 if delivery else 2, "time_to_first_token": .5 if delivery else 1},
                    x_memory={"extraction_calls": 1})
            with self.subTest(policy=policy), FakeServer(extra=extra, callback=callback) as server:
                store = self.create(*plan(server.url, policy))
                trial = run_live(store, "slot", allow_live=True)
                self.assertEqual(len(server.seen), 2)
                first = server.seen[0][1]["messages"]
                self.assertEqual(first[-1], {"role": "user", "content": "Synthetic fact: widget color is violet."})
                second = server.seen[1][1]["messages"]
                if policy == "reset-v1":
                    self.assertEqual(second[1:], [{"role": "user", "content": "Report the synthetic answer."}])
                else:
                    self.assertEqual(second[:-1], first + [{"role": "assistant", "content": "This is unclassified delivery prose."}])
                self.assertTrue(trial["score"]["accepted"])
                self.assertEqual(trial["score"]["result_state"], "accepted_exact")
                self.assertEqual(trial["score"]["attempts"], 1)
                self.assertEqual(trial["score"]["first_attempt"], {"fact": True})
                self.assertEqual(trial["score"]["TPS"], 10)
                self.assertEqual(trial["score"]["experimental_eTPS"], 10)
                self.assertEqual(trial["score"]["I"], len(first[-1]["content"].encode()) + len(second[-1]["content"].encode()))
                self.assertEqual(trial["score"]["R"], 0)
                self.assertFalse(any(c["class"] == "malformed" for c in trial["score"]["classifications"]))
                self.assertEqual(score(store.manifest("slot"), trial["record"]), trial["score"])
                delivery = next(e for e in trial["record"]["events"] if e["kind"] == "delivery")
                self.assertNotIn("answer", delivery)
                self.assertEqual(delivery["memory_telemetry"], {"extraction_calls": 1})
                r = report(store)
                d = r["delivery_processing"]["private-arm-label"][0]["requests"][0]
                self.assertEqual(d["generation"], {"tokens": 101, "seconds": 1})
                self.assertEqual(d["timing"]["decode_tps"]["value"], 200)
                self.assertEqual(d["timing"]["prompt_tokens"]["value"], 3)
                self.assertEqual(r["processed_prompt_tokens"]["private-arm-label"]["total"], 6)
                self.assertEqual(r["memory_telemetry"]["private-arm-label"]["metrics"]["extraction_calls"]["sum"], 2)
                for version in ("v1", "v2"):
                    replayed = replay_export(export_bundle(store, version))
                    self.assertEqual(replayed["trials"][0], trial)
                    self.assertEqual(replayed["delivery_processing"], r["delivery_processing"])

    def test_no_delivery_when_already_requested_or_at_empty_boundary(self):
        for requested in (True, False):
            with FakeServer() as server:
                p, a = plan(server.url, requested=requested)
                if not requested:
                    m = decode(next(iter(a.values())))
                    m["start"] = "boundary"
                    raw = encode(m)
                    a, p["tasks"] = {sha(raw): raw}, {"synthetic-task": sha(raw)}
                store = self.create(p, a)
                trial = run_live(store, "slot", allow_live=True)
                self.assertFalse(any(e["kind"] == "delivery" for e in trial["record"]["events"]))
                self.assertEqual(len(server.seen), 2 if requested else 1)

    def test_failure_recorded_then_continues_without_assistant_append(self):
        from etps_v02 import adapter_openai
        original = adapter_openai.send
        calls = []
        with FakeServer(extra={"usage": {"completion_tokens": 11},
                               "stats": {"generation_time": 2, "time_to_first_token": 1}}) as server:
            def send(*args):
                response = original(*args)
                calls.append(response)
                return response
            # HTTP failure is a transport outcome; the next probe uses another fake endpoint response.
            with FakeServer(status=500) as failure:
                def dispatch(base, arm, body, deadline):
                    return send(failure.url if not calls else base, arm, body, deadline)
                store = self.create(*plan(server.url, "full"))
                with patch("etps_v02.live_runner.adapter.send", side_effect=dispatch):
                    trial = run_live(store, "slot", allow_live=True)
            self.assertTrue(trial["score"]["accepted"])
            self.assertEqual(trial["score"]["TPS"], 10)
            self.assertEqual(trial["record"]["events"][1]["status"], "timeout")
            self.assertFalse(any(m["role"] == "assistant" for m in server.seen[0][1]["messages"]))
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_rehashed_tampering_missing_duplicate_and_relocated_delivery(self):
        with FakeServer() as server:
            store = self.create(*plan(server.url))
            run_live(store, "slot", allow_live=True)
            for mutation in ("history", "raw", "omit", "duplicate", "node", "kind"):
                exported = export_bundle(store)
                rows = exported["journal"]["slot"]
                request_index = next(i for i, r in enumerate(rows) if r["kind"] == "request")
                event = rows[request_index + 1]["payload"]
                if mutation == "history": rows[request_index]["payload"]["body"]["messages"][-1]["content"] = "forged"
                elif mutation == "raw": event["raw_base64"] = "e30="
                elif mutation == "omit": del rows[request_index:request_index + 2]
                elif mutation == "duplicate": rows[request_index:request_index] = copy.deepcopy(rows[request_index:request_index + 2])
                elif mutation == "node": rows[request_index]["payload"]["node"] = "p"
                else: rows[request_index]["payload"]["kind"] = "probe"
                rechain(exported)
                with self.subTest(mutation=mutation), self.assertRaises(InvalidRecord):
                    replay_export(exported)

    def test_absent_field_preserves_request_and_report_behavior(self):
        with FakeServer() as server:
            store = self.create(*plan(server.url, enabled=False))
            trial = run_live(store, "slot", allow_live=True)
            self.assertEqual(len(server.seen), 1)
            self.assertEqual(server.seen[0][1]["messages"][1:],
                             [{"role": "user", "content": "Report the synthetic answer."}])
            self.assertNotIn("boundary_delivery", trial["record"])
            self.assertNotIn("delivery_processing", report(store))
            self.assertTrue(all("kind" not in r["payload"] for r in store.entries("slot") if r["kind"] == "request"))
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_delivery_without_primary_timing_opt_in_still_has_secondary_timing(self):
        with FakeServer(extra={"usage": {"completion_tokens": 6, "prompt_tokens": 7},
                               "stats": {"generation_time": 2, "time_to_first_token": 1}}) as server:
            p, a = plan(server.url)
            del p["timing_convention"]
            store = self.create(p, a)
            trial = run_live(store, "slot", allow_live=True)
            self.assertEqual(trial["score"]["TPS"], 3)
            delivery = next(e for e in trial["record"]["events"] if e["kind"] == "delivery")
            self.assertNotIn("timing", delivery)
            timing = report(store)["delivery_processing"]["private-arm-label"][0]["requests"][0]["timing"]
            self.assertEqual(timing["decode_tps"]["value"], 5)
            self.assertEqual(timing["full_generation_tps"]["value"], 3)
            self.assertEqual(timing["completion_tokens"]["value"], 6)
            self.assertEqual(timing["prompt_tokens"]["value"], 7)
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_invalid_version_and_offline_plan_rejected(self):
        p, a = plan("http://127.0.0.1:1")
        for value in (None, True, "deliver-v2", {}):
            p["boundary_delivery"] = value
            with self.assertRaisesRegex(InvalidRecord, "boundary_delivery"):
                validate_bundle(encode(p), a)
        from test_v02_runner import bundle as offline_bundle
        raw, a = offline_bundle()
        p = decode(raw)
        p["boundary_delivery"] = "deliver-v1"
        with self.assertRaisesRegex(InvalidRecord, "plan fields"):
            validate_bundle(encode(p), a)

    def test_delivery_wall_limit_stops_before_probe(self):
        from etps_v02 import adapter_openai
        original = adapter_openai.send
        clock = [0]
        with FakeServer() as server:
            store = self.create(*plan(server.url))
            def send(*args):
                result = original(*args)
                clock[0] = 31
                result["client_latency_seconds"] = 31
                return result
            with patch("etps_v02.live_runner.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("etps_v02.live_runner.adapter.send", side_effect=send):
                trial = run_live(store, "slot", allow_live=True)
            self.assertFalse(trial["score"]["accepted"])
            self.assertEqual(trial["reason_code"], "trial_wall_limit")
            self.assertEqual(trial["score"]["attempts"], 0)
            self.assertIsNone(trial["score"]["TPS"])
            self.assertEqual(len(server.seen), 1)
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)

    def test_multiple_pending_users_one_delivery_and_repeated_boundary(self):
        with FakeServer() as server:
            p, a = plan(server.url)
            m = decode(next(iter(a.values())))
            m["nodes"]["intro"]["next"] = "second-fact"
            m["nodes"]["second-fact"] = user("Another synthetic fact.", "boundary")
            m["nodes"]["boundary"]["next"] = "second-boundary"
            m["nodes"]["second-boundary"] = {"kind": "session_boundary", "next": "question"}
            raw = encode(m)
            p["tasks"] = {"synthetic-task": sha(raw)}
            store = self.create(p, {sha(raw): raw})
            trial = run_live(store, "slot", allow_live=True)
            self.assertEqual(len(server.seen), 2)
            self.assertEqual([message["content"] for message in server.seen[0][1]["messages"] if message["role"] == "user"],
                             ["Synthetic fact: widget color is violet.", "Another synthetic fact."])
            self.assertEqual(sum(e["kind"] == "delivery" for e in trial["record"]["events"]), 1)
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], trial)
