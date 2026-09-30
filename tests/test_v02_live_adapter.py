"""Fake-server tests only. Never contact a real model or fixed model port."""
import base64
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from etps_v02 import adapter_openai as adapter
from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, json_default, replay_export, replay_slot, report, run_offline
from etps_v02.scorer import InvalidRecord, OUTCOMES
from etps_v02.workload import encode, sha, validate_bundle, INVALIDATION_POLICY


def manifest():
    return {"unit": "utf8_bytes", "start": "intro", "obligations": {}, "nodes": {
        "intro": {"kind": "user", "text": "Public synthetic request", "sha256": sha(b"Public synthetic request"),
                  "spans": [], "next": "p"},
        "p": {"kind": "probe", "expected": {"answer": "expected-private-marker"}, "unknown_answers": [],
              "obligations": [], "next": {o: "pass" if o == "correct" else "fail" for o in OUTCOMES}},
        "pass": {"kind": "terminal", "accepted": True}, "fail": {"kind": "terminal", "accepted": False}}}


def bundle(endpoint, provider="openai-compatible", **updates):
    raw = encode(manifest())
    arm = {"provider": provider, "model": "synthetic-model", "temperature": 0,
           "seed": None, "max_tokens": 17, "api_key_env": None, "system_prompt": "Synthetic system instruction"}
    if provider == "anthropic":
        arm["anthropic_version"] = "2023-06-01"
    p = {"schema": "etps-live-plan-v1", "purpose": "live-exploratory", "unit": "utf8_bytes",
         "endpoint": endpoint, "arms": {"private-arm-label": arm}, "request_deadline_seconds": 1,
         "trial_wall_limit_seconds": 5, "exposure": {"non_loopback": False, "remote_endpoint_authorized": False},
         "invalidation_policy": INVALIDATION_POLICY, "tasks": {"synthetic-task": sha(raw)},
         "slots": [{"id": "slot", "arm": "private-arm-label", "task": "synthetic-task"}]}
    p.update(updates)
    return p, {sha(raw): raw}


class FakeServer:
    def __init__(self, provider="openai-compatible", content='{"answer":"expected-private-marker"}',
                 status=200, raw=None, delay=0, extra=None, callback=None, headers=None):
        self.seen = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                outer.seen.append((self.path, json.loads(data), dict(self.headers)))
                if callback:
                    callback()
                time.sleep(delay)
                value = ({"type": "message", "role": "assistant", "content": [{"type": "text", "text": content}]}
                         if provider == "anthropic" else
                         {"choices": [{"message": {"role": "assistant", "content": content}}]})
                value.update(extra or {})
                body = raw if raw is not None else encode(value)
                try:
                    self.send_response(status)
                    self.send_header("Content-Length", str(len(body)))
                    for key, value in (headers or {}).items():
                        self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class LiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stores = []
    def tearDown(self):
        for store in self.stores:
            store.close()
        self.temp.cleanup()
    def create(self, p, artifacts, allow_remote=False):
        path = Path(self.temp.name) / (str(len(self.stores)) + ".db")
        store = Store.create(path, encode(p), artifacts, allow_remote=allow_remote)
        self.stores.append(store)
        return store

    def test_both_providers_outcomes_and_replay(self):
        for provider in ("openai-compatible", "anthropic"):
            for content, outcome in (('{"answer":"expected-private-marker"}', "correct"),
                                     ('{"answer":"wrong"}', "incorrect"), ("not-json", "malformed"), ("", "malformed")):
                with self.subTest(provider=provider, outcome=outcome), FakeServer(provider, content) as server:
                    p, artifacts = bundle(server.url, provider)
                    store = self.create(p, artifacts)
                    r = run_live(store, "slot", allow_live=True)
                    self.assertEqual(r["score"]["classifications"][-1]["class"], outcome)
                    self.assertTrue(r["score"]["measurement_valid"])
                    self.assertTrue(r["evidence_verified"])
                    self.assertEqual(r["score"]["accepted"], outcome == "correct")
                    self.assertIsNone(r["score"]["TPS"])
                    self.assertIsNone(r["score"]["experimental_eTPS"])
                    self.assertGreater(r["score"]["wall_seconds"], 0)
                    for fmt in ("v1", "v2"):
                        replayed = replay_export(export_bundle(store, format=fmt), validate_authoring=True)
                        self.assertEqual(replayed["trials"][0], r)
                    body = server.seen[0][1]
                    self.assertNotIn("expected-private-marker", json.dumps(body))
                    self.assertNotIn("private-arm-label", json.dumps(body))
                    self.assertNotIn("obligations", json.dumps(body))
                    self.assertEqual(body["max_tokens"], 17)
                    self.assertFalse(body["stream"])
                    if provider == "anthropic":
                        self.assertEqual(server.seen[0][0], "/v1/messages")
                        self.assertIn("system", body)
                        self.assertNotIn("seed", body)
                    else:
                        self.assertEqual(server.seen[0][0], "/chat/completions")
                        self.assertEqual(body["messages"][0]["role"], "system")

    def test_transport_failures_are_finished_measured_failures(self):
        for provider in ("openai-compatible", "anthropic"):
            for options, detail in (({"status": 500}, "http_status"),
                                    ({"raw": b"garbage"}, "invalid_envelope"),
                                    ({"raw": b'{}'}, "invalid_envelope"),
                                    ({"delay": 2.0}, "deadline_exceeded")):
                with self.subTest(provider=provider, detail=detail), FakeServer(provider, **options) as server:
                    p, artifacts = bundle(server.url, provider,
                                          request_deadline_seconds=.5 if "delay" in options else 5,
                                          trial_wall_limit_seconds=10)
                    store = self.create(p, artifacts)
                    r = run_live(store, "slot", allow_live=True)
                    event = r["record"]["events"][-1]
                    self.assertEqual(event["status"], "timeout")
                    self.assertEqual(event["transport_detail"], detail)
                    self.assertEqual(r["state"], "finished")
                    self.assertEqual(r["reason_code"], "system_terminal_failure")
                    self.assertTrue(r["score"]["measurement_valid"])
                    self.assertIsNotNone(r["score"]["RR"])
                    self.assertLessEqual(len(server.seen), 1)

    def test_connection_refused(self):
        original = adapter.preflight
        with FakeServer() as server:
            def close_after_preflight(*args):
                original(*args)
                server.server.shutdown()
                server.server.server_close()
            p, a = bundle(server.url, request_deadline_seconds=5,
                          trial_wall_limit_seconds=10)
            with patch.object(adapter, "preflight", side_effect=close_after_preflight):
                r = run_live(self.create(p, a), "slot", allow_live=True)
            self.assertEqual(r["record"]["events"][-1]["transport_detail"], "connection_refused")
            self.assertEqual(r["record"]["events"][-1]["status"], "timeout")
            self.assertEqual(r["state"], "finished")
            self.assertTrue(r["score"]["measurement_valid"])
            self.assertTrue(r["evidence_verified"])

    def test_intent_persisted_before_http_and_crash_retains_prefix(self):
        path = Path(self.temp.name) / "0.db"
        checked = []
        def check():
            other = Store(path)
            try:
                checked.append(other.entries("slot")[-1]["kind"])
            finally:
                other.close()
        with FakeServer(callback=check) as server:
            p, a = bundle(server.url)
            run_live(self.create(p, a), "slot", allow_live=True)
        self.assertEqual(checked, ["request"])
        store = self.create(p, a)
        with patch.object(adapter, "preflight"), patch.object(adapter, "send", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            run_live(store, "slot", allow_live=True)
        self.assertEqual(store.entries("slot")[-1]["kind"], "request")
        self.assertEqual(replay_slot(store, "slot")["state"], "running")
        self.assertEqual(report(store)["rr_unavailable_attempted"], 1)

    def test_wall_limit_is_bounded_failure(self):
        with FakeServer(delay=2.0) as server:
            p, a = bundle(server.url, request_deadline_seconds=1, trial_wall_limit_seconds=.5)
            store = self.create(p, a)
            r = run_live(store, "slot", allow_live=True)
            self.assertEqual(r["reason_code"], "trial_wall_limit")
            self.assertEqual(r["score"]["terminal"], "$trial_wall_limit")
            self.assertTrue(r["score"]["measurement_valid"])
            self.assertFalse(r["score"]["accepted"])
            self.assertEqual(report(store)["failed"], 1)
            self.assertEqual(replay_export(export_bundle(store))["trials"][0], r)

    def test_usage_and_client_latency_do_not_make_generation_tps(self):
        usage = {"prompt_tokens": 12, "completion_tokens": 4, "vendor_extra": {"cached": 2}}
        with FakeServer(extra={"usage": usage, "stats": {"tokens_per_second": 900}}) as server:
            p, a = bundle(server.url)
            store = self.create(p, a)
            r = run_live(store, "slot", allow_live=True)
            self.assertEqual(r["record"]["events"][-1]["usage"], usage)
            self.assertIsNone(r["score"]["TPS"])
            self.assertIsNotNone(report(store)["summaries"][0]["wall_seconds_per_accepted"])

    def test_explicit_backend_generation_pair_has_named_sources(self):
        with FakeServer(extra={"timings": {"predicted_n": 4, "predicted_ms": 200}}) as server:
            p, a = bundle(server.url)
            r = run_live(self.create(p, a), "slot", allow_live=True)
            self.assertEqual(r["score"]["TPS"], 20)
            self.assertEqual(r["record"]["events"][-1]["generation_source"],
                             ["timings.predicted_n", "timings.predicted_ms"])

    def test_remote_dual_authorization_and_https_required(self):
        p, a = bundle("https://example.invalid")
        p["exposure"]["non_loopback"] = True
        for plan_auth, flag in ((False, False), (False, True), (True, False)):
            p["exposure"]["remote_endpoint_authorized"] = plan_auth
            with self.assertRaisesRegex(InvalidRecord, "authorization"):
                validate_bundle(encode(p), a, allow_remote=flag)
        p["exposure"]["remote_endpoint_authorized"] = True
        validate_bundle(encode(p), a, allow_remote=True)
        store = self.create(p, a, allow_remote=True)
        with patch.object(adapter, "send") as send, self.assertRaisesRegex(InvalidRecord, "authorization"):
            run_live(store, "slot", allow_live=True)
        send.assert_not_called()
        self.assertEqual(store.entries("slot"), [])
        p["endpoint"] = "http://example.invalid"
        with self.assertRaisesRegex(InvalidRecord, "HTTPS"):
            validate_bundle(encode(p), a, allow_remote=True)

    def test_remote_exposure_and_api_key_nonleak_both_providers(self):
        sentinel = "test-only-credential-sentinel-DO-NOT-PERSIST"
        original = adapter._http_once
        for provider in ("openai-compatible", "anthropic"):
            with self.subTest(provider=provider), FakeServer(provider) as server:
                p, a = bundle("https://example.invalid", provider)
                p["exposure"] = {"non_loopback": True, "remote_endpoint_authorized": True}
                p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_TEST_KEY"
                store = self.create(p, a, allow_remote=True)
                def local_only(url, body, headers, deadline):
                    suffix = "/v1/messages" if provider == "anthropic" else "/chat/completions"
                    return original(server.url + suffix, body, headers, deadline)
                with patch.object(adapter, "preflight"), patch.dict(os.environ, {"ETPS_TEST_KEY": sentinel}), patch.object(adapter, "_http_once", side_effect=local_only):
                    r = run_live(store, "slot", allow_live=True, allow_remote=True)
                self.assertEqual(len(r["exposure"]), 1)
                self.assertEqual(r["exposure"][0]["endpoint_host"], "example.invalid")
                self.assertEqual(r["exposure"][0]["provider"], provider)
                self.assertEqual(r["exposure"][0]["task_artifact_hashes"], list(p["tasks"].values()))
                headers = {k.lower(): v for k, v in server.seen[0][2].items()}
                self.assertEqual(headers["x-api-key" if provider == "anthropic" else "authorization"],
                                 sentinel if provider == "anthropic" else "Bearer " + sentinel)
                exported = export_bundle(store, format="v2")
                all_output = json.dumps([exported, report(store), replay_export(exported)], default=json_default)
                self.assertNotIn(sentinel, all_output)
                self.assertNotIn(sentinel.encode(), store.path.read_bytes())
                self.assertEqual(replay_export(exported)["trials"][0], r)

    def test_secret_echo_and_exception_details_never_persist(self):
        key = "synthetic-secret-sentinel"
        with FakeServer(raw=key.encode(), status=500) as server:
            p, a = bundle(server.url)
            p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_TEST_KEY"
            store = self.create(p, a)
            with patch.dict(os.environ, {"ETPS_TEST_KEY": key}):
                r = run_live(store, "slot", allow_live=True)
            self.assertEqual(r["record"]["events"][-1]["transport_detail"], "credential_echo")
            self.assertNotIn(key, json.dumps(export_bundle(store), default=json_default))
        store = self.create(p, a)
        with patch.object(adapter, "preflight"), patch.dict(os.environ, {"ETPS_TEST_KEY": key}), patch.object(adapter, "_http_once", side_effect=RuntimeError(key)):
            run_live(store, "slot", allow_live=True)
        self.assertNotIn(key, json.dumps(export_bundle(store), default=json_default))

    def test_required_settings_and_credentials_in_url_rejected(self):
        p, a = bundle("http://127.0.0.1:1")
        for key in ("endpoint", "arms", "exposure", "request_deadline_seconds", "trial_wall_limit_seconds"):
            q = copy.deepcopy(p)
            del q[key]
            with self.assertRaises(InvalidRecord):
                validate_bundle(encode(q), a)
        for key in ("provider", "model", "temperature", "seed", "max_tokens", "api_key_env"):
            q = copy.deepcopy(p)
            del q["arms"]["private-arm-label"][key]
            with self.assertRaises(InvalidRecord):
                validate_bundle(encode(q), a)
        for url in ("http://user:secret@localhost", "http://localhost?api_key=secret", "ftp://localhost", "http://127.0.0.2"):
            q = copy.deepcopy(p)
            q["endpoint"] = url
            with self.assertRaises(InvalidRecord):
                validate_bundle(encode(q), a)

    def test_cli_requires_live_flag_and_offline_never_dispatches(self):
        p, a = bundle("http://127.0.0.1:1")
        store = self.create(p, a)
        child = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "run", str(store.path), "--slot", "slot"], capture_output=True)
        self.assertEqual(child.returncode, 2)
        self.assertIn(b"--allow-live", child.stderr)
        self.assertEqual(store.entries("slot"), [])
        from test_v02_runner import bundle as offline_bundle, response
        raw, artifacts = offline_bundle(responses=[response()], slots=1)
        from etps_v02.workload import decode
        offline = self.create(decode(raw), artifacts)
        with patch.object(adapter, "send", side_effect=AssertionError("offline network")):
            self.assertTrue(run_offline(offline, "slot-0")["score"]["accepted"])

    def test_typed_projection_and_assistant_public_history(self):
        arm = bundle("http://127.0.0.1:1")[0]["arms"]["private-arm-label"]
        body = adapter.public_request(arm, [{"role": "user", "content": "public"},
                                           {"role": "assistant", "content": "prior answer"}])
        self.assertEqual(body["messages"][-1], {"role": "assistant", "content": "prior answer"})
        with FakeServer(content='{"v":null}') as server:
            p, _ = bundle(server.url)
            m = manifest()
            m["answer_schema"] = "typed-v1"
            m["nodes"]["p"]["expected"] = {"v": None}
            raw = encode(m)
            p["tasks"] = {"synthetic-task": sha(raw)}
            r = run_live(self.create(p, {sha(raw): raw}), "slot", allow_live=True)
            self.assertTrue(r["score"]["accepted"])

    def test_redirects_and_proxy_environment_are_not_followed(self):
        with FakeServer() as target, FakeServer(status=302, headers={"Location": target.url}) as origin:
            p, a = bundle(origin.url)
            with patch.dict(os.environ, {"HTTP_PROXY": target.url, "http_proxy": target.url, "NO_PROXY": ""}):
                r = run_live(self.create(p, a), "slot", allow_live=True)
            self.assertEqual(len(origin.seen), 1)
            self.assertEqual(target.seen, [])
            self.assertEqual(r["record"]["events"][-1]["transport_detail"], "http_status")

    def test_live_replay_rejects_rehashed_usage_or_request_tampering(self):
        with FakeServer() as server:
            p, a = bundle(server.url)
            store = self.create(p, a)
            run_live(store, "slot", allow_live=True)
            original = export_bundle(store)
        for kind in ("request", "event"):
            exported = copy.deepcopy(original)
            rows = exported["journal"]["slot"]
            for row in rows:
                if row["kind"] == kind:
                    if kind == "request":
                        row["payload"]["body"]["temperature"] = 99
                    elif row["payload"].get("kind") == "probe":
                        row["payload"]["usage"] = {"completion_tokens": 999}
            previous = sha(encode([exported["plan_sha256"], "slot"]))
            for i, row in enumerate(rows):
                previous = sha(encode(["slot", i, row["kind"], previous]) + encode(row["payload"]))
                row["sha256"] = previous
            with self.assertRaisesRegex(InvalidRecord, "mismatch"):
                replay_export(exported)
