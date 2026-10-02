"""Review regressions: synthetic fixtures and ephemeral loopback endpoints only."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from etps_v02 import adapter_openai as adapter
from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, json_default, replay_export, replay_slot
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode, sha
from test_v02_field_routing import fields_manifest
from test_v02_live_adapter import FakeServer, bundle, manifest


class LiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def create(self, plan, artifacts, task=None):
        if task is not None:
            raw = encode(task)
            plan["tasks"] = {"synthetic-task": sha(raw)}
            artifacts = {sha(raw): raw}
        self.count += 1
        store = Store.create(Path(self.temp.name) / (str(self.count) + ".db"), encode(plan), artifacts)
        self.addCleanup(store.close)
        return store

    def cli(self, store, env=None):
        return subprocess.run([sys.executable, "-B", "-m", "etps_v02", "run", str(store.path),
                               "--slot", "slot", "--allow-live"], capture_output=True, env=env)

    def assert_replay(self, store):
        result = replay_slot(store, "slot")
        self.assertTrue(result["evidence_verified"])
        for fmt in ("v1", "v2"):
            self.assertEqual(replay_export(export_bundle(store, format=fmt))["trials"][0], result)
        return result

    def test_partial_field_failure_routes_and_replays_both_providers(self):
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider, content='{"a":8,"b":"nine"}') as server:
                store = self.create(*bundle(server.url, provider), task=fields_manifest())
                result = run_live(store, "slot", allow_live=True)
                self.assertEqual([e["node"] for e in result["record"]["events"]],
                                 ["intro", "p", "r-a", "retry"])
                self.assertEqual(result["score"]["first_attempt"], {"left": False, "right": True, "both": False})
                self.assertTrue(result["score"]["measurement_valid"])
                self.assertEqual(self.assert_replay(store), result)
                self.assertEqual(len(server.seen), 2)

    def test_tcp_preflight_sends_no_application_bytes_or_journal(self):
        received = []
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(3)
            def accept():
                with listener.accept()[0] as peer:
                    peer.settimeout(3)
                    received.append(peer.recv(1))
            worker = threading.Thread(target=accept, daemon=True)
            worker.start()
            p, a = bundle("http://127.0.0.1:" + str(listener.getsockname()[1]))
            store = self.create(p, a)
            adapter.preflight(p["endpoint"], p["arms"]["private-arm-label"], 1)
            worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertEqual(received, [b""])
            self.assertEqual(store.entries("slot"), [])

    def test_preflight_refusal_cli_exit_two_and_no_journal(self):
        with socket.socket() as refused:
            refused.bind(("127.0.0.1", 0))
            store = self.create(*bundle("http://127.0.0.1:" + str(refused.getsockname()[1]),
                                       request_deadline_seconds=5))
            child = self.cli(store)
            self.assertEqual(child.returncode, 2)
            self.assertEqual(child.stderr.strip(), b"error: endpoint TCP preflight failed")
            self.assertEqual(store.entries("slot"), [])
            self.assertEqual(replay_slot(store, "slot")["state"], "unattempted")

    def test_credential_preflight_missing_or_malformed_cli_writes_nothing(self):
        for provider in ("openai-compatible", "anthropic"):
            with FakeServer(provider) as server:
                for value in (None, "", "bad key", "bad\nkey", "bad\x7fkey", "nonascii-\u00e9"):
                    with self.subTest(provider=provider, value=value):
                        p, a = bundle(server.url, provider)
                        p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_REVIEW_KEY"
                        store = self.create(p, a)
                        env = dict(os.environ)
                        env.pop("ETPS_REVIEW_KEY", None)
                        if value is not None:
                            env["ETPS_REVIEW_KEY"] = value
                        child = self.cli(store, env)
                        self.assertEqual(child.returncode, 2)
                        self.assertEqual(child.stderr.strip(), b"error: configured credential missing or malformed")
                        self.assertEqual(store.entries("slot"), [])
                self.assertEqual(server.seen, [])

    def test_credential_loss_after_intent_aborts_as_execution_error(self):
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider) as server:
                p, a = bundle(server.url, provider)
                p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_REVIEW_KEY"
                store = self.create(p, a)
                append = store.append
                def remove_after_intent(slot, kind, payload):
                    result = append(slot, kind, payload)
                    if kind == "request":
                        os.environ.pop("ETPS_REVIEW_KEY", None)
                    return result
                with patch.dict(os.environ, {"ETPS_REVIEW_KEY": "review-sentinel-secret"}), \
                        patch.object(store, "append", side_effect=remove_after_intent):
                    with self.assertRaisesRegex(InvalidRecord, "credential"):
                        run_live(store, "slot", allow_live=True)
                result = self.assert_replay(store)
                self.assertEqual(result["state"], "aborted")
                self.assertEqual(result["reason_code"], "execution_error")
                self.assertFalse(result["score"]["measurement_valid"])
                self.assertEqual([r["kind"] for r in store.entries("slot")], ["start", "event", "request", "abort"])
                self.assertEqual(server.seen, [])
                self.assertNotIn("review-sentinel-secret", json.dumps(export_bundle(store), default=json_default))

    def test_legacy_credential_timeout_readable_but_new_policy_rejects_it(self):
        with FakeServer(status=500) as server:
            store = self.create(*bundle(server.url))
            run_live(store, "slot", allow_live=True)
            original = export_bundle(store)
        for legacy in (True, False):
            exported = copy.deepcopy(original)
            rows = exported["journal"]["slot"]
            if legacy:
                rows[0]["payload"].pop("controller_policy")
            event = next(r["payload"] for r in rows if r["kind"] == "event" and r["payload"]["kind"] == "probe")
            event.update(transport_detail="credential_unavailable", http_status=None,
                         http_body_base64=None, http_body_sha256=None)
            previous = sha(encode([exported["plan_sha256"], "slot"]))
            for i, row in enumerate(rows):
                previous = sha(encode(["slot", i, row["kind"], previous]) + encode(row["payload"]))
                row["sha256"] = previous
            if legacy:
                result = replay_export(exported)["trials"][0]
                self.assertTrue(result["evidence_verified"])
                self.assertIn("legacy_credential_outcome: harness fault recorded as timeout", result["warnings"])
            else:
                with self.assertRaisesRegex(InvalidRecord, "transport failure evidence"):
                    replay_export(exported)

    def test_empty_public_history_guard_both_providers(self):
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider) as server:
                task = manifest()
                task["start"] = "p"
                del task["nodes"]["intro"]
                store = self.create(*bundle(server.url, provider), task=task)
                with self.assertRaisesRegex(InvalidRecord, "conversation"):
                    run_live(store, "slot", allow_live=True)
                result = self.assert_replay(store)
                self.assertEqual(result["reason_code"], "execution_error")
                self.assertEqual([r["kind"] for r in store.entries("slot")], ["start", "abort"])
                self.assertEqual(server.seen, [])

    def test_assistant_prefill_guard_both_providers(self):
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider) as server:
                task = manifest()
                task["nodes"]["p2"] = copy.deepcopy(task["nodes"]["p"])
                task["nodes"]["p"]["next"]["correct"] = "p2"
                with self.assertRaisesRegex(InvalidRecord, "live probe successor"):
                    self.create(*bundle(server.url, provider), task=task)
                with patch("etps_v02.live_plan.check_live_successors"):
                    store = self.create(*bundle(server.url, provider), task=task)
                    with self.assertRaisesRegex(InvalidRecord, "conversation"):
                        run_live(store, "slot", allow_live=True)
                    result = self.assert_replay(store)
                    self.assertEqual(result["reason_code"], "execution_error")
                    self.assertEqual(result["state"], "aborted")
                    self.assertEqual(len(server.seen), 1)
                    self.assertEqual(sum(r["kind"] == "request" for r in store.entries("slot")), 1)
