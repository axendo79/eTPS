"""Opt-in request hashes: synthetic offline fixtures and loopback fake servers."""
from pathlib import Path
import tempfile
import unittest

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, run_offline
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import decode, encode, sha, validate_bundle
from test_v02_boundary_delivery import plan as delivery_plan
from test_v02_live_adapter import FakeServer, bundle as live_bundle
from test_v02_manual_dev import manual_bundle
from test_v02_runner import bundle as offline_bundle
from test_v02_session_profile import offline, rechain
from tools.bench_v02_scaling import chain_task, plan as chain_plan


MODE = "history-sha256-v1"
OFFLINE_FIELDS = {"node", "message_count", "messages_sha256"}
LIVE_FIELDS = {"node", "message_count", "body_sha256", "elapsed_seconds", "deadline_seconds"}


class RequestJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def create(self, plan, artifacts):
        self.count += 1
        store = Store.create(Path(self.temp.name) / f"{self.count}.db", encode(plan), artifacts)
        self.addCleanup(store.close)
        return store

    def requests(self, store, slot):
        return [r["payload"] for r in store.entries(slot) if r["kind"] == "request"]

    def test_offline_equivalence_and_exact_request_fields(self):
        raw, artifacts = offline_bundle(slots=1)
        plan = decode(raw)
        full = self.create(plan, artifacts)
        plan["request_journal"] = MODE
        hashed = self.create(plan, artifacts)
        before = run_offline(full, "slot-0")
        after = run_offline(hashed, "slot-0")
        self.assertEqual(before["score"], after["score"])
        self.assertEqual(before["record"]["events"], after["record"]["events"])
        self.assertEqual(len(self.requests(full, "slot-0")), len(self.requests(hashed, "slot-0")))
        for original, compact in zip(self.requests(full, "slot-0"), self.requests(hashed, "slot-0")):
            self.assertEqual(set(compact), OFFLINE_FIELDS)
            self.assertEqual(compact["node"], original["node"])
            self.assertEqual(compact["message_count"], len(original["messages"]))
            self.assertEqual(compact["messages_sha256"], sha(encode(original["messages"])))
        self.assertEqual(replay_export(export_bundle(hashed, format="v2"))["trials"][0], after)

    def test_fifty_turn_request_size(self):
        task, script, _ = chain_task(50, 2000)
        raw, artifacts = chain_plan(task, script, 1)
        plan = decode(raw)
        sizes = []
        for hashed in (False, True):
            if hashed:
                plan["request_journal"] = MODE
            store = self.create(plan, artifacts)
            run_offline(store, "s0")
            requests = self.requests(store, "s0")
            self.assertEqual(len(requests), 50)
            sizes.append(sum(len(encode(p)) for p in requests))
        self.assertLessEqual(sizes[1], 50 * 150)
        self.assertGreater(sizes[0], 10 * sizes[1])

    def test_offline_rechained_tampering(self):
        raw, artifacts = offline_bundle(slots=1)
        plan = decode(raw)
        plan["request_journal"] = MODE
        store = self.create(plan, artifacts)
        run_offline(store, "slot-0")
        for mutation in ("messages_sha256", "message_count", "text", "extra"):
            with self.subTest(mutation=mutation):
                exported = export_bundle(store, format="v1")
                rows = exported["journal"]["slot-0"]
                request = next(r["payload"] for r in rows if r["kind"] == "request")
                if mutation == "text":
                    user = next(r["payload"] for r in rows
                                if r["kind"] == "event" and r["payload"]["kind"] == "user")
                    user["text"] += " forged"
                elif mutation == "message_count":
                    request[mutation] += 1
                else:
                    request[mutation] = "0" * 64
                rechain(exported)
                error = "invalid request fields" if mutation == "extra" else "request history mismatch"
                with self.assertRaisesRegex(InvalidRecord, error):
                    replay_export(exported)

    def test_reset_hash_contains_only_post_boundary_users(self):
        plan, artifacts = offline()
        plan["request_journal"] = MODE
        store = self.create(plan, artifacts)
        run_offline(store, "slot-0")
        trial = run_offline(store, "slot-1")
        rows = store.entries("slot-1")
        boundary = next(i for i, r in enumerate(rows)
                        if r["kind"] == "event" and r["payload"]["kind"] == "session_boundary")
        request_index = next(i for i in range(boundary + 1, len(rows)) if rows[i]["kind"] == "request")
        messages = [{"role": "user", "text": r["payload"]["text"]}
                    for r in rows[boundary + 1:request_index]
                    if r["kind"] == "event" and r["payload"]["kind"] == "user"]
        self.assertEqual(messages, [{"role": "user", "text": "Which database?"}])
        request = rows[request_index]["payload"]
        self.assertEqual(request["message_count"], len(messages))
        self.assertEqual(request["messages_sha256"], sha(encode(messages)))
        self.assertEqual(replay_export(export_bundle(store, format="v2"))["trials"][1], trial)
        exported = export_bundle(store, format="v1")
        exported["journal"]["slot-1"][request_index]["payload"]["messages_sha256"] = "0" * 64
        rechain(exported)
        with self.assertRaisesRegex(InvalidRecord, "request history mismatch"):
            replay_export(exported)

    def test_live_providers_exact_fields_roundtrip_and_tampering(self):
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider) as server:
                plan, artifacts = live_bundle(server.url, provider, request_journal=MODE)
                store = self.create(plan, artifacts)
                trial = run_live(store, "slot", allow_live=True)
                self.assertTrue(trial["score"]["measurement_valid"])
                self.assertTrue(trial["evidence_verified"])
                requests = self.requests(store, "slot")
                self.assertEqual(len(requests), len(server.seen))
                for request, (_, body, _) in zip(requests, server.seen):
                    self.assertEqual(set(request), LIVE_FIELDS)
                    self.assertEqual(request["message_count"], len(body["messages"]))
                    self.assertEqual(request["body_sha256"], sha(encode(body)))
                self.assertEqual(replay_export(export_bundle(store, format="v2"))["trials"][0], trial)
                for mutation in ("body_sha256", "message_count", "text"):
                    with self.subTest(mutation=mutation):
                        exported = export_bundle(store, format="v1")
                        rows = exported["journal"]["slot"]
                        request = next(r["payload"] for r in rows if r["kind"] == "request")
                        if mutation == "text":
                            user = next(r["payload"] for r in rows
                                        if r["kind"] == "event" and r["payload"]["kind"] == "user")
                            user["text"] += " forged"
                        elif mutation == "message_count":
                            request[mutation] += 1
                        else:
                            request[mutation] = "0" * 64
                        rechain(exported)
                        with self.assertRaisesRegex(InvalidRecord, "request public history/settings mismatch"):
                            replay_export(exported)

    def test_delivery_both_policies_roundtrip_and_relocated_or_retyped_intent(self):
        for policy in ("reset-v1", "full"):
            with self.subTest(policy=policy), FakeServer() as server:
                plan, artifacts = delivery_plan(server.url, policy)
                plan["request_journal"] = MODE
                store = self.create(plan, artifacts)
                trial = run_live(store, "slot", allow_live=True)
                self.assertEqual(trial["state"], "finished")
                self.assertTrue(trial["score"]["measurement_valid"])
                self.assertTrue(trial["evidence_verified"])
                requests = self.requests(store, "slot")
                self.assertEqual(len(requests), 2)
                self.assertEqual(set(requests[0]), LIVE_FIELDS | {"kind"})
                self.assertEqual(requests[0]["kind"], "delivery")
                self.assertEqual(set(requests[1]), LIVE_FIELDS)
                self.assertEqual(replay_export(export_bundle(store, format="v2"))["trials"][0], trial)
                for mutation in ("move", "retype"):
                    with self.subTest(mutation=mutation):
                        exported = export_bundle(store, format="v1")
                        rows = exported["journal"]["slot"]
                        index = next(i for i, r in enumerate(rows) if r["kind"] == "request")
                        if mutation == "retype":
                            rows[index]["payload"]["kind"] = "probe"
                        else:
                            delivery = rows[index:index + 2]
                            del rows[index:index + 2]
                            boundary = next(i for i, r in enumerate(rows)
                                            if r["kind"] == "event" and r["payload"]["kind"] == "session_boundary")
                            rows[boundary + 1:boundary + 1] = delivery
                        rechain(exported)
                        with self.assertRaises(InvalidRecord):
                            replay_export(exported)

    def test_unknown_request_journal_rejected(self):
        raw, artifacts = offline_bundle()
        for plan, sources in ((decode(raw), artifacts), live_bundle("http://127.0.0.1:1")):
            with self.subTest(schema=plan["schema"]):
                for value in ("nope", [], {}, None, True):
                    with self.subTest(value=value):
                        plan["request_journal"] = value
                        with self.assertRaisesRegex(InvalidRecord, "unsupported request_journal"):
                            validate_bundle(encode(plan), sources)

    def test_manual_request_journal_rejected(self):
        plan, artifacts = manual_bundle()
        validate_bundle(encode(plan), artifacts)
        plan["request_journal"] = MODE
        with self.assertRaisesRegex(InvalidRecord, "invalid plan fields"):
            validate_bundle(encode(plan), artifacts)

    def test_legacy_request_journal_rejected(self):
        raw, artifacts = offline_bundle()
        plan = decode(raw)
        plan["schema"] = "etps-offline-plan-v1"
        del plan["unit"], plan["invalidation_policy"]
        validate_bundle(encode(plan), artifacts, allow_legacy=True)
        plan["request_journal"] = MODE
        with self.assertRaisesRegex(InvalidRecord, "invalid plan fields"):
            validate_bundle(encode(plan), artifacts, allow_legacy=True)

    def test_list_schema_raises_invalid_record(self):
        raw, artifacts = offline_bundle()
        complete = decode(raw)
        complete.update(schema=[], request_journal=MODE)
        for plan in ({"schema": [], "request_journal": MODE}, complete):
            with self.subTest(plan=plan), self.assertRaises(InvalidRecord):
                validate_bundle(encode(plan), artifacts)


if __name__ == "__main__":
    unittest.main()
