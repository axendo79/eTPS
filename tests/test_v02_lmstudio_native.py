"""Native REST fixtures only; never contacts an installed LM Studio instance."""
import copy
from pathlib import Path
import tempfile
import unittest

from etps_v02.adapter_openai import envelope, send
from etps_v02.live_plan import validate_live
from etps_v02.live_runner import run_live
from etps_v02.model_check import check_models
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode
from test_v02_live_adapter import FakeServer, bundle
from test_v02_external_kit import MetadataServer


class NativeTests(unittest.TestCase):
    def test_native_path_no_credentials_generation_pair_and_replay(self):
        with FakeServer(extra={"usage": {"completion_tokens": 12},
                               "stats": {"generation_time": .6, "tokens_per_second": 999}}) as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle(server.url, "lmstudio-native")
            store = Store.create(Path(temp) / "test.db", encode(p), a)
            try:
                r = run_live(store, "slot", allow_live=True)
                self.assertTrue(r["score"]["accepted"])
                self.assertEqual(r["score"]["TPS"], 20)
                event = r["record"]["events"][-1]
                self.assertEqual(event["generation_source"], ["usage.completion_tokens", "stats.generation_time"])
                self.assertEqual(event["generation"], {"tokens": 12, "seconds": .6})
                path, _, headers = server.seen[0]
                self.assertEqual(path, "/api/v0/chat/completions")
                self.assertNotIn("authorization", {k.lower() for k in headers})
                self.assertNotIn("x-api-key", {k.lower() for k in headers})
                self.assertEqual(replay_export(export_bundle(store, "v2"))["trials"][0], r)
            finally:
                store.close()

    def test_missing_native_generation_fields_keep_tps_unavailable(self):
        for extra in ({}, {"stats": {}}, {"usage": {"completion_tokens": 12}},
                      {"stats": {"generation_time": .6}},
                      {"usage": {"completion_tokens": 12}, "stats": {"tokens_per_second": 20}},
                      {"usage": {"completion_tokens": True}, "stats": {"generation_time": .6}},
                      {"usage": {"completion_tokens": 12}, "stats": {"generation_time": 0}},
                      {"timings": {"predicted_n": 12, "predicted_ms": 600}}):
            with self.subTest(extra=extra), FakeServer(extra=extra) as server, tempfile.TemporaryDirectory() as temp:
                p, a = bundle(server.url, "lmstudio-native")
                store = Store.create(Path(temp) / "test.db", encode(p), a)
                try:
                    r = run_live(store, "slot", allow_live=True)
                    self.assertIsNone(r["score"]["TPS"])
                    self.assertIsNone(r["score"]["experimental_eTPS"])
                    self.assertIsNone(r["record"]["events"][-1]["generation_source"])
                    self.assertEqual(replay_export(export_bundle(store))["trials"][0], r)
                finally:
                    store.close()

    def test_native_rejects_remote_and_key_before_transport(self):
        p, _ = bundle("https://example.invalid", "lmstudio-native")
        p["exposure"] = {"non_loopback": True, "remote_endpoint_authorized": True}
        with self.assertRaisesRegex(InvalidRecord, "loopback"):
            validate_live(p, allow_remote=True)
        arm = p["arms"]["private-arm-label"]
        with self.assertRaisesRegex(InvalidRecord, "loopback"):
            send(p["endpoint"], arm, {}, 10)
        p["endpoint"] = "http://127.0.0.1:1"
        p["exposure"]["non_loopback"] = False
        arm["api_key_env"] = "NOT_READ"
        with self.assertRaisesRegex(InvalidRecord, "keys"):
            validate_live(p)

    def test_native_model_metadata_path(self):
        with MetadataServer() as server:
            p, _ = bundle(server.url, "lmstudio-native")
            self.assertEqual(check_models(p)[0]["status"], "ok")
            self.assertEqual(server.seen[0][0], "/api/v0/models/synthetic-model")

    def test_native_stats_do_not_change_compatible_provider_interpretation(self):
        raw = encode({"choices": [{"message": {"role": "assistant", "content": "{}"}}],
                      "usage": {"completion_tokens": 10}, "stats": {"generation_time": 1}})
        self.assertIsNone(envelope("openai-compatible", 200, raw)["generation"])
        self.assertEqual(envelope("lmstudio-native", 200, raw)["generation"], {"tokens": 10, "seconds": 1})
