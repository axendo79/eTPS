"""Session policy regressions using synthetic data and ephemeral fake servers."""
import base64
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report, run_offline
from etps_v02.scorer import InvalidRecord, OUTCOMES, validate
from etps_v02.session_profile import processing_requests, total
from etps_v02.workload import decode, encode, sha, validate_bundle
from test_v02_live_adapter import FakeServer, bundle as live_bundle
from test_v02_runner import bundle as offline_bundle, response
from test_v02_scorer import fixture, user


def task():
    m = fixture()
    m["nodes"]["intro"]["next"] = "warmup"
    m["nodes"]["warmup"] = {"kind": "probe", "expected": {"ack": "ok"},
        "unknown_answers": [], "obligations": [], "next": {o: "boundary" for o in OUTCOMES}}
    m["nodes"]["boundary"] = {"kind": "session_boundary", "next": "question"}
    m["nodes"]["question"] = user("Which database?", "p1")
    return m


def offline(m=None, policies=True):
    responses = [response(b'{"ack":"ok"}'), response(b'{"database":"wrong"}'), response()]
    responses[0]["usage"] = {"prompt_tokens": 12}
    responses[2]["usage"] = {"prompt_tokens": 0}
    raw, artifacts = offline_bundle(manifest=m or task(), responses=responses)
    plan = decode(raw)
    if policies:
        plan["arms"] = {"baseline": {"context_policy": "full"}, "memory": {"context_policy": "reset-v1"}}
    return plan, artifacts


def rechain(bundle):
    for slot, rows in bundle["journal"].items():
        previous = sha(encode([bundle["plan_sha256"], slot]))
        for i, row in enumerate(rows):
            previous = sha(encode([slot, i, row["kind"], previous]) + encode(row["payload"]))
            row["sha256"] = previous


class SessionProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stores = []

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.temp.cleanup()

    def create(self, plan, artifacts):
        store = Store.create(Path(self.temp.name) / f"{len(self.stores)}.db", encode(plan), artifacts)
        self.stores.append(store)
        return store

    def test_offline_reset_exact_history_obligations_and_costs(self):
        store = self.create(*offline())
        scores = []
        for slot in store.slots:
            scores.append(run_offline(store, slot)["score"])
        self.assertEqual(scores[0], scores[1])
        s = scores[0]
        self.assertEqual((s["I"], s["R"], s["RR"]), (55, 15, Fraction(3, 11)))
        self.assertTrue(s["accepted"])
        self.assertEqual(s["first_attempt"], {"db": False})
        self.assertIn({"node": "boundary", "class": "excluded_session_boundary"}, s["classifications"])
        histories = [[r["payload"]["messages"] for r in store.entries(slot) if r["kind"] == "request"]
                     for slot in store.slots]
        question = {"role": "user", "text": "Which database?"}
        self.assertEqual(histories[0][1], [{"role": "user", "text": "database=SQLite"},
            {"role": "assistant", "raw_base64": base64.b64encode(b'{"ack":"ok"}').decode()}, question])
        self.assertEqual(histories[1][1], [question])
        self.assertEqual(histories[1][2], [question,
            {"role": "assistant", "raw_base64": base64.b64encode(b'{"database":"wrong"}').decode()},
            {"role": "user", "text": "database=SQLite; new task"}])
        result = report(store)
        self.assertEqual(result["processed_prompt_tokens"]["memory"],
                         {"numerator": 12, "coverage_count": 2, "request_count": 3, "total": None})
        pair = result["context_policy_pairing"]["synthetic"]
        self.assertEqual(pair["full"][0]["I"], pair["reset-v1"][0]["I"])
        self.assertEqual(pair["reset-v1"][0]["requests"][1]["prompt_tokens"], None)
        self.assertEqual(replay_export(export_bundle(store, format="v2"))["context_policy_pairing"],
                         result["context_policy_pairing"])

    def test_authoring_rejects_missing_user_and_text_on_boundary(self):
        m = task()
        m["nodes"]["boundary"]["next"] = "p1"
        with self.assertRaisesRegex(InvalidRecord, "requires a user message after the boundary"):
            validate(m)
        m = task()
        m["nodes"]["boundary"]["text"] = "not allowed"
        with self.assertRaises(InvalidRecord):
            validate(m)

    def test_full_ignores_boundary_and_absent_policy_is_identical(self):
        plan, artifacts = offline(policies=False)
        implicit = self.create(plan, artifacts)
        plan["arms"] = {"baseline": {"context_policy": "full"}, "memory": {}}
        explicit = self.create(plan, artifacts)
        for store in (implicit, explicit):
            run_offline(store, "slot-0")
        left = [r["payload"] for r in implicit.entries("slot-0")]
        right = [r["payload"] for r in explicit.entries("slot-0")]
        self.assertEqual(encode(left), encode(right))

    def test_offline_replay_rejects_rehashed_history_and_usage(self):
        store = self.create(*offline())
        run_offline(store, "slot-0")
        run_offline(store, "slot-1")
        exported = export_bundle(store)
        requests = [r for r in exported["journal"]["slot-1"] if r["kind"] == "request"]
        requests[1]["payload"]["messages"].insert(0, {"role": "user", "text": "database=SQLite"})
        rechain(exported)
        with self.assertRaisesRegex(InvalidRecord, "request history mismatch"):
            replay_export(exported)
        exported = export_bundle(store)
        events = [r for r in exported["journal"]["slot-1"] if r["kind"] == "event" and r["payload"]["kind"] == "probe"]
        events[0]["payload"]["usage"]["prompt_tokens"] = 99
        rechain(exported)
        self.assertFalse(replay_export(exported)["trials"][1]["evidence_verified"])

    def test_invalid_policy_rejected(self):
        p, artifacts = offline()
        p["arms"]["baseline"]["context_policy"] = "reset"
        with self.assertRaisesRegex(InvalidRecord, "context_policy"):
            validate_bundle(encode(p), artifacts)
        p, artifacts = live_bundle("http://127.0.0.1:1")
        p["arms"]["private-arm-label"]["context_policy"] = None
        with self.assertRaisesRegex(InvalidRecord, "context_policy"):
            validate_bundle(encode(p), artifacts)

    def test_live_policies_exact_bodies_system_persistence_and_replay(self):
        for provider in ("openai-compatible", "anthropic", "lmstudio-native"):
            for policy in (None, "full", "reset-v1"):
                with self.subTest(provider=provider, policy=policy), FakeServer(
                        provider, content='{"database":"SQLite"}', extra={"usage": {"prompt_tokens": 19}}) as server:
                    p, _ = live_bundle(server.url, provider)
                    arm = p["arms"]["private-arm-label"]
                    if policy is not None:
                        arm["context_policy"] = policy
                    m = task()
                    raw = encode(m)
                    p["tasks"] = {"synthetic-task": sha(raw)}
                    store = self.create(p, {sha(raw): raw})
                    trial = run_live(store, "slot", allow_live=True)
                    self.assertTrue(trial["score"]["accepted"])
                    self.assertEqual(trial["score"]["first_attempt"], {"db": True})
                    expected = {"model": "synthetic-model", "temperature": 0,
                                "max_tokens": 17, "stream": False, "messages": []}
                    if provider == "anthropic":
                        expected["system"] = "Synthetic system instruction"
                    else:
                        expected["messages"].append({"role": "system", "content": "Synthetic system instruction"})
                    if policy != "reset-v1":
                        expected["messages"] += [{"role": "user", "content": "database=SQLite"},
                            {"role": "assistant", "content": '{"database":"SQLite"}'}]
                    expected["messages"].append({"role": "user", "content": "Which database?"})
                    self.assertEqual(encode(server.seen[1][1]), encode(expected))
                    result = report(store)
                    self.assertEqual(result["processed_prompt_tokens"]["private-arm-label"],
                        {"numerator": 38, "coverage_count": 2, "request_count": 2, "total": 38})
                    self.assertEqual(replay_export(export_bundle(store))["context_policy_pairing"],
                                     result["context_policy_pairing"])
                    exported = export_bundle(store)
                    requests = [r for r in exported["journal"]["slot"] if r["kind"] == "request"]
                    requests[1]["payload"]["body"]["messages"].append({"role": "user", "content": "tampered"})
                    rechain(exported)
                    with self.assertRaisesRegex(InvalidRecord, "public history/settings mismatch"):
                        replay_export(exported)

    def test_live_missing_usage_and_pending_request_coverage(self):
        with FakeServer() as server:
            p, artifacts = live_bundle(server.url)
            store = self.create(p, artifacts)
            run_live(store, "slot", allow_live=True)
            self.assertEqual(report(store)["processed_prompt_tokens"]["private-arm-label"],
                {"numerator": 0, "coverage_count": 0, "request_count": 1, "total": None})
        rows = [{"kind": "request", "payload": {"node": "p"}}]
        self.assertEqual(total(processing_requests(rows))["coverage_count"], 0)
        rows.append({"kind": "event", "payload": {"kind": "probe", "usage": {"prompt_tokens": "19"}}})
        self.assertEqual(processing_requests(rows)[0]["prompt_tokens"], "19")
        self.assertEqual(total(processing_requests(rows))["coverage_count"], 0)

    def test_repeated_boundaries_clear_again_without_expiring_obligation(self):
        m = task()
        m["nodes"]["p1"]["next"]["incorrect"] = "second-boundary"
        m["nodes"]["second-boundary"] = {"kind": "session_boundary", "next": "recover"}
        store = self.create(*offline(m))
        run_offline(store, "slot-0")
        trial = run_offline(store, "slot-1")
        self.assertTrue(trial["score"]["accepted"])
        self.assertEqual(trial["score"]["R"], 15)
        requests = [r["payload"] for r in store.entries("slot-1") if r["kind"] == "request"]
        self.assertEqual(requests[-1]["messages"], [{"role": "user", "text": "database=SQLite; new task"}])


if __name__ == "__main__":
    unittest.main()
