"""Synthetic provider metadata and per-arm endpoints; loopback only."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from etps_v02 import adapter_openai as adapter
from etps_v02.live_plan import validate_live
from etps_v02.live_runner import run_live
from etps_v02.model_check import check_models
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode
from test_v02_live_adapter import FakeServer, bundle


class MetadataServer:
    def __init__(self, status=200, body=None):
        self.seen = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                outer.seen.append((self.path, dict(self.headers), self.headers.get("Content-Length")))
                raw = body if body is not None else b'{"id":"synthetic-model"}'
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
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


class ExternalKitTests(unittest.TestCase):
    def test_two_endpoints_one_plan_pairing_and_replay(self):
        with FakeServer() as first, FakeServer("anthropic") as second, tempfile.TemporaryDirectory() as temp:
            p, artifacts = bundle(first.url)
            other, _ = bundle(second.url, "anthropic")
            p["arms"]["second"] = {**other["arms"]["private-arm-label"], "endpoint": second.url}
            p["slots"].append({"id": "second-slot", "arm": "second", "task": "synthetic-task"})
            store = Store.create(Path(temp) / "test.db", encode(p), artifacts)
            try:
                for slot in p["slots"]:
                    self.assertTrue(run_live(store, slot["id"], allow_live=True)["score"]["accepted"])
                r = report(store)
                self.assertEqual(len(r["summaries"]), 2)
                self.assertTrue(r["arm_pairing"]["synthetic-task"]["equal_planned_counts"])
                self.assertEqual(r["accepted"], 2)
                self.assertEqual(len(first.seen), 1)
                self.assertEqual(len(second.seen), 1)
                replayed = replay_export(export_bundle(store, "v2"))
                self.assertEqual({k: replayed[k] for k in r}, r)
            finally:
                store.close()

    def test_any_remote_arm_requires_both_authorizations(self):
        p, _ = bundle("http://127.0.0.1:1")
        p["arms"]["private-arm-label"]["endpoint"] = "https://example.invalid"
        with self.assertRaisesRegex(InvalidRecord, "exposure"):
            validate_live(p)
        p["exposure"]["non_loopback"] = True
        for flag, declared in ((False, False), (True, False), (False, True)):
            p["exposure"]["remote_endpoint_authorized"] = declared
            with self.assertRaisesRegex(InvalidRecord, "authorization"):
                validate_live(p, allow_remote=flag)
        self.assertTrue(validate_live(p, allow_remote=True))
        p["arms"]["private-arm-label"]["endpoint"] = "http://example.invalid"
        with self.assertRaisesRegex(InvalidRecord, "HTTPS"):
            validate_live(p, allow_remote=True)

    def test_selected_remote_endpoint_binds_exposure(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle("http://127.0.0.1:1")
            p["arms"]["private-arm-label"]["endpoint"] = "https://example.invalid/v1"
            p["exposure"] = {"non_loopback": True, "remote_endpoint_authorized": True}
            store = Store.create(Path(temp) / "test.db", encode(p), a, allow_remote=True)
            original = adapter._http_once
            urls = []
            def local(url, body, headers, deadline):
                urls.append(url)
                return original(server.url + "/chat/completions", body, headers, deadline)
            try:
                with patch.object(adapter, "preflight") as preflight, patch.object(adapter, "_http_once", side_effect=local):
                    r = run_live(store, "slot", allow_live=True, allow_remote=True)
                self.assertEqual(preflight.call_args.args[0], "https://example.invalid/v1")
                self.assertEqual(urls, ["https://example.invalid/v1/chat/completions"])
                self.assertEqual(r["exposure"][0]["endpoint_host"], "example.invalid")
                self.assertEqual(replay_export(export_bundle(store))["trials"][0], r)
            finally:
                store.close()

    def test_model_metadata_both_providers_status_and_no_task_data(self):
        for provider in ("anthropic", "openai-compatible"):
            for code, expected in ((200, "ok"), (404, "not-found"), (401, "auth-error"), (403, "auth-error"), (500, "unavailable")):
                with self.subTest(provider=provider, code=code), MetadataServer(code) as server:
                    p, _ = bundle(server.url, provider)
                    p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_METADATA_KEY"
                    with patch.dict(os.environ, {"ETPS_METADATA_KEY": "metadata-sentinel-secret"}):
                        r = check_models(p)
                    self.assertEqual(r, [{"arm": "private-arm-label", "status": expected}])
                    path, headers, length = server.seen[0]
                    self.assertEqual(path, ("/v1/models/" if provider == "anthropic" else "/models/") + "synthetic-model")
                    self.assertIsNone(length)
                    self.assertNotIn("expected-private-marker", json.dumps(server.seen))
                    self.assertNotIn("metadata-sentinel-secret", json.dumps(r))
                    headers = {k.lower(): v for k, v in headers.items()}
                    self.assertIn("x-api-key" if provider == "anthropic" else "authorization", headers)

    def test_model_check_missing_key_and_remote_gate_send_nothing(self):
        with MetadataServer() as server:
            p, _ = bundle(server.url)
            p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_METADATA_KEY"
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(check_models(p)[0]["status"], "auth-error")
            self.assertEqual(server.seen, [])
        p["arms"]["private-arm-label"]["endpoint"] = "https://example.invalid"
        p["exposure"] = {"non_loopback": True, "remote_endpoint_authorized": True}
        with self.assertRaisesRegex(InvalidRecord, "authorization"):
            check_models(p)

    def test_model_cli_and_secret_echo_never_printed(self):
        for body, expected in ((b'{"id":"synthetic-model"}', 0), (b'metadata-sentinel-secret', 2)):
            with MetadataServer(body=body) as server, tempfile.TemporaryDirectory() as temp:
                p, _ = bundle(server.url)
                p["arms"]["private-arm-label"]["api_key_env"] = "ETPS_METADATA_KEY"
                path = Path(temp) / "plan.json"
                path.write_bytes(encode(p))
                child = subprocess.run([sys.executable, "-B", "-m", "etps_v02", "check-models", str(path)],
                                       env={**os.environ, "ETPS_METADATA_KEY": "metadata-sentinel-secret"}, capture_output=True)
                self.assertEqual(child.returncode, expected)
                self.assertNotIn(b"metadata-sentinel-secret", child.stdout + child.stderr)
                self.assertEqual(len(server.seen), 1)
