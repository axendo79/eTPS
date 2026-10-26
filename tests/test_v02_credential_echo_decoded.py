"""SYNTHETIC credentials and mocked HTTP only; diagnostics never include keys."""
import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import adapter_openai as adapter
from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, json_default, replay_export, replay_slot, report
from etps_v02.workload import encode, sha
from test_v02_live_adapter import bundle


SYNTHETIC_KEY = "SYNTHETIC-TEST-ONLY-" + "Z" * 24


class DecodedCredentialEchoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def response(self, provider):
        content = '{"answer":"expected-private-marker"}'
        if provider == "anthropic":
            return {"type": "message", "role": "assistant",
                    "content": [{"type": "text", "text": content}]}
        return {"choices": [{"message": {"role": "assistant", "content": content}}]}

    def escaped(self, value, fully=False):
        raw = encode(value)
        literal = SYNTHETIC_KEY.encode("ascii")
        replacement = ("".join("\\u%04x" % ord(c) for c in SYNTHETIC_KEY).encode("ascii")
                       if fully else b"\\u%04x" % literal[0] + literal[1:])
        self.assertTrue(literal in raw, "synthetic fixture must contain the marker")
        raw = raw.replace(literal, replacement)
        self.assertTrue(literal not in raw, "synthetic fixture must bypass the literal check")
        return raw

    def run_response(self, raw, provider, status=200):
        plan, artifacts = bundle("http://127.0.0.1:1", provider)
        plan["arms"]["private-arm-label"]["api_key_env"] = "ETPS_SYNTHETIC_DECODED_KEY"
        self.count += 1
        store = Store.create(Path(self.temp.name) / (str(self.count) + ".db"), encode(plan), artifacts)
        self.addCleanup(store.close)
        with patch.dict(os.environ, {"ETPS_SYNTHETIC_DECODED_KEY": SYNTHETIC_KEY}), \
                patch.object(adapter, "preflight"), \
                patch.object(adapter, "_http_once", return_value=(status, raw, None)):
            result = run_live(store, "slot", allow_live=True)
        return store, result

    def assert_withheld(self, raw, provider, status=200):
        store, result = self.run_response(raw, provider, status)
        event = result["record"]["events"][-1]
        # Fail before inspecting/exporting any body if detection is absent.
        self.assertEqual(event["transport_detail"], "credential_echo")
        self.assertEqual(event["status"], "timeout")
        self.assertEqual(event["http_status"], status)
        self.assertEqual(event["http_body_sha256"], sha(raw))
        self.assertIsNone(event["http_body_base64"])
        self.assertEqual(event["raw_base64"], "")
        self.assertIsNone(event["answer"])
        self.assertIsNone(event["usage"])
        self.assertIsNone(event["generation"])
        self.assertIsNone(event["generation_source"])
        self.assertEqual(event["backend_stats"], {})
        self.assertEqual(result["state"], "finished")
        self.assertEqual(result["reason_code"], "system_terminal_failure")
        self.assertFalse(result["score"]["accepted"])
        self.assertTrue(result["score"]["measurement_valid"])
        self.assertTrue(result["evidence_verified"])
        self.assertEqual(replay_slot(store, "slot"), result)
        for fmt in ("v1", "v2"):
            exported = export_bundle(store, format=fmt)
            replayed = replay_export(exported)
            self.assertEqual(replayed["trials"][0], result)
            output = json.dumps([store.entries("slot"), report(store), exported, replayed],
                                default=json_default)
            self.assertTrue(SYNTHETIC_KEY not in output, "synthetic marker must not persist")
            self.assertTrue(base64.b64encode(raw).decode("ascii") not in output,
                            "withheld HTTP body must not persist")
        stored = store.path.read_bytes()
        self.assertTrue(SYNTHETIC_KEY.encode("ascii") not in stored,
                        "synthetic marker must not reach SQLite")
        self.assertTrue(raw not in stored, "withheld HTTP body must not reach SQLite")

    def test_escaped_single_character_string_value_is_detected(self):
        for provider in ("openai-compatible", "anthropic"):
            value = self.response(provider)
            content = "prefix " + SYNTHETIC_KEY + " suffix"
            if provider == "anthropic":
                value["content"][0]["text"] = content
            else:
                value["choices"][0]["message"]["content"] = content
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(self.escaped(value), provider, status)

    def test_fully_escaped_credential_is_detected(self):
        for provider in ("openai-compatible", "anthropic"):
            value = self.response(provider)
            value["metadata"] = SYNTHETIC_KEY
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(self.escaped(value, fully=True), provider, status)

    def test_nested_object_array_string_is_detected(self):
        for provider in ("openai-compatible", "anthropic"):
            value = self.response(provider)
            value["metadata"] = [None, {"nested": [False, 17, {"value": SYNTHETIC_KEY}]}]
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(self.escaped(value), provider, status)

    def test_credential_in_object_key_is_detected(self):
        for provider in ("openai-compatible", "anthropic"):
            value = self.response(provider)
            value["metadata"] = [{"prefix " + SYNTHETIC_KEY + " suffix": None}]
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(self.escaped(value, fully=True), provider, status)

    def test_top_level_json_string_and_array_are_detected(self):
        for provider in ("openai-compatible", "anthropic"):
            for form, value in (("string", SYNTHETIC_KEY), ("array", [None, SYNTHETIC_KEY])):
                for status in (200, 500):
                    with self.subTest(provider=provider, form=form, status=status):
                        self.assert_withheld(self.escaped(value, fully=True), provider, status)

    def test_duplicate_object_members_are_all_checked(self):
        fragment = self.escaped(SYNTHETIC_KEY, fully=True)
        raw = b'{"metadata":' + fragment + b',"metadata":"ordinary"}'
        for provider in ("openai-compatible", "anthropic"):
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(raw, provider, status)

    def test_decode_recursion_error_fails_closed(self):
        # Platform-independent: any RecursionError from decoding withholds, echo or not.
        for raw in (self.escaped(SYNTHETIC_KEY, fully=True), encode({"ordinary": 17})):
            with self.subTest(raw=raw), \
                    patch.object(adapter.json, "loads", side_effect=RecursionError):
                self.assertTrue(adapter._decoded_credential_echo(raw, SYNTHETIC_KEY))

    def test_deep_json_decode_recursion_is_withheld(self):
        # Whether real nesting exceeds the decoder's limit depends on the platform
        # (Windows 3.14 raises at this depth; Linux 3.14 may not).
        depth = 100_000
        nested = b"[" * depth + self.escaped(SYNTHETIC_KEY, fully=True) + b"]" * depth
        for provider in ("openai-compatible", "anthropic"):
            raw = encode(self.response(provider))[:-1] + b',"metadata":' + nested + b"}"
            try:
                json.loads(raw)
            except RecursionError:
                pass
            else:
                self.skipTest("JSON decoder handles this depth without RecursionError here")
            for status in (200, 500):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(raw, provider, status)

    def test_shallow_json_decoded_check_is_unchanged(self):
        for value, expected in (({"ordinary": [None, False, 17, "public text"]}, False),
                                ({"metadata": SYNTHETIC_KEY}, True),
                                ({SYNTHETIC_KEY: "ordinary"}, True)):
            raw = self.escaped(value, fully=True) if expected else encode(value)
            with self.subTest(echo=expected, raw=raw):
                self.assertEqual(adapter._decoded_credential_echo(raw, SYNTHETIC_KEY), expected)

    def test_ordinary_response_is_unchanged(self):
        for provider in ("openai-compatible", "anthropic"):
            value = self.response(provider)
            value["metadata"] = [None, False, 17, {"ordinary": "public synthetic text"}]
            raw = encode(value)
            with self.subTest(provider=provider):
                store, result = self.run_response(raw, provider)
                event = result["record"]["events"][-1]
                self.assertTrue(result["score"]["accepted"])
                self.assertEqual(event["http_body_base64"], base64.b64encode(raw).decode("ascii"))
                for name, expected in adapter.envelope(provider, 200, raw).items():
                    self.assertEqual(event[name], expected)
                for fmt in ("v1", "v2"):
                    self.assertEqual(replay_export(export_bundle(store, format=fmt))["trials"][0], result)

    def test_non_json_raw_check_and_outcomes_are_unchanged(self):
        for provider in ("openai-compatible", "anthropic"):
            for status, detail in ((200, "invalid_envelope"), (500, "http_status")):
                with self.subTest(provider=provider, status=status):
                    self.assert_withheld(SYNTHETIC_KEY.encode("ascii"), provider, status)
                    raw = b"ordinary non-JSON response"
                    store, result = self.run_response(raw, provider, status)
                    event = result["record"]["events"][-1]
                    self.assertEqual(event["status"], "timeout")
                    self.assertEqual(event["transport_detail"], detail)
                    self.assertEqual(event["http_body_base64"], base64.b64encode(raw).decode("ascii"))
                    self.assertEqual(replay_export(export_bundle(store))["trials"][0], result)

    def test_malformed_json_handling_is_unchanged(self):
        # An escaped fragment is not a decoded JSON string in an incomplete body.
        raw = self.escaped({"unfinished": SYNTHETIC_KEY}, fully=True)[:-1]
        for provider in ("openai-compatible", "anthropic"):
            for status, detail in ((200, "invalid_envelope"), (500, "http_status")):
                with self.subTest(provider=provider, status=status):
                    _, result = self.run_response(raw, provider, status)
                    event = result["record"]["events"][-1]
                    self.assertEqual(event["status"], "timeout")
                    self.assertEqual(event["transport_detail"], detail)
                    self.assertTrue(event["http_body_base64"] == base64.b64encode(raw).decode("ascii"),
                                    "malformed body handling must remain unchanged")
