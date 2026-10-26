"""Synthetic lab transport tests; never contact a model endpoint."""
import hashlib
import importlib.util
import json
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "temp0_variance", Path(__file__).resolve().parents[1] / "scripts/lab/temp0_variance.py")
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


@contextmanager
def fake_server(reply=None):
    seen = []
    active = [0, 0]
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            body = json.loads(raw)
            with lock:
                seen.append((self.path, raw, body))
                active[0] += 1
                active[1] = max(active)
                index = len(seen)
            time.sleep(0.025)
            status, response = reply(body, index) if reply else (200, {
                "model": "synthetic-model", "choices": [{"message": {
                    "role": "assistant", "content": "café"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}})
            data = response if isinstance(response, bytes) else json.dumps(response).encode()
            self.send_response(status)
            self.end_headers()
            self.wfile.write(data)
            with lock:
                active[0] -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", seen, active
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class Temp0VarianceTests(unittest.TestCase):
    def prompts(self, count=2):
        return [{"id": f"p{i}", "category": "synthetic", "messages": [
            {"role": "user", "content": f"invented-{i}"}]} for i in range(count)]

    def run_fake(self, base, out, **kwargs):
        return lab.run_measurement(self.prompts(), [{"id": "A", "concurrency": 1}],
                                   3, out, base=base, model="synthetic-model",
                                   temperature_reader=lambda: [45], **kwargs)

    def test_payload_hash_and_durable_round_robin(self):
        with tempfile.TemporaryDirectory() as temp, fake_server() as (base, seen, _):
            out = Path(temp) / "new"
            with mock.patch.object(lab.os, "fsync", wraps=lab.os.fsync) as sync:
                result = self.run_fake(base, out)
            rows = [json.loads(line) for line in (out / "requests.jsonl").read_text().splitlines()]
            self.assertEqual(result["counts"]["A"], {"sent": 6, "succeeded": 6, "failed": 0})
            self.assertEqual([(r["prompt_id"], r["repeat_index"]) for r in rows],
                             [(f"p{i}", r) for r in range(3) for i in range(2)])
            self.assertGreaterEqual(sync.call_count, 12)
            for row, (url, raw, body) in zip(rows, seen):
                self.assertEqual(url, "/v1/chat/completions")
                self.assertEqual(body, {"model": "synthetic-model", "temperature": 0,
                    "top_p": 1, "max_tokens": 256, "stream": False,
                    "messages": self.prompts()[int(row["prompt_id"][-1])]["messages"]})
                self.assertEqual(row["request_json_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(row["output_sha256"], hashlib.sha256("café".encode()).hexdigest())
                self.assertEqual(row["response_json"]["usage"], row["usage"])
                self.assertEqual(row["http_status"], 200)
                self.assertGreater(row["wall_latency_seconds"], 0)
                self.assertTrue(row["timestamp_utc"].endswith("+00:00"))

    def test_parallelism_and_condition_order(self):
        with tempfile.TemporaryDirectory() as temp, fake_server() as (base, seen, active):
            result = lab.run_measurement(self.prompts(4), [
                {"id": "A", "concurrency": 1}, {"id": "B", "concurrency": 4}],
                2, Path(temp) / "new", base=base, model="synthetic-model",
                temperature_reader=lambda: [45])
            self.assertEqual(len(seen), 16)
            self.assertGreater(active[1], 1)
            self.assertLessEqual(active[1], 4)
            dispatch = [json.loads(line) for line in
                        (Path(temp) / "new/dispatches.jsonl").read_text().splitlines()]
            self.assertEqual([r["condition"] for r in dispatch], ["A"] * 8 + ["B"] * 8)
            self.assertEqual([r["prompt_id"] for r in dispatch[8:]], ["p0", "p1", "p2", "p3"] * 2)
            self.assertIsNone(result["stop_reason"])

    def test_summary_modal_unicode_prefix_and_spreads(self):
        rows = [{"condition": "A", "prompt_id": "p", "success": True,
                 "output_text": text, "usage": {"completion_tokens": tokens},
                 "wall_latency_seconds": latency} for text, tokens, latency in
                [("café", 2, 1), ("café", 4, 3), ("cafe", 6, 9), ("café!", 8, 5)]]
        group = lab.summarize(rows)[0]
        self.assertEqual(group["distinct_outputs"], 3)
        self.assertEqual(group["modal_exact_match_rate"], 0.5)
        self.assertEqual(group["first_differing_character_index"], 3)
        self.assertEqual(group["completion_tokens"], {"n": 4, "min": 2, "median": 5.0, "max": 8})
        self.assertEqual(group["latency_seconds"]["median"], 4.0)
        self.assertEqual(lab.first_difference("abc", "abcd"), 3)
        self.assertIsNone(lab.first_difference("abc", "abc"))
        self.assertIsNone(group["first_differing_model_token_index"])

    def test_failure_retained_and_stops_without_retry(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(lambda *_: (503, {"error": "synthetic"})) as (base, seen, _):
            result = self.run_fake(base, Path(temp) / "new")
            self.assertEqual(len(seen), 1)
            self.assertEqual(result["stop_reason"], "failure_rate_exceeds_5_percent")
            self.assertEqual(result["counts"]["A"]["failed"], 1)
            row = json.loads((Path(temp) / "new/requests.jsonl").read_text())
            self.assertEqual(row["response_json"], {"error": "synthetic"})
            self.assertEqual(row["http_status"], 503)
            self.assertEqual(result["unattempted"], 5)

    def test_malformed_response_preserved(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(lambda *_: (200, b"not-json")) as (base, _, _):
            self.run_fake(base, Path(temp) / "new")
            row = json.loads((Path(temp) / "new/requests.jsonl").read_text())
            self.assertFalse(row["success"])
            self.assertEqual(row["response_body_utf8"], "not-json")
            self.assertIsNone(row["response_json"])

    def test_wrong_model_stops_immediately(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(lambda *_: (200, {
                "model": "wrong", "choices": [{"message": {"content": "x"}}]})) as (base, seen, _):
            result = self.run_fake(base, Path(temp) / "new")
            self.assertEqual(len(seen), 1)
            self.assertEqual(result["stop_reason"], "different_model_id")

    def test_hot_gpu_stops_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temp, fake_server() as (base, seen, _):
            result = lab.run_measurement(self.prompts(), [{"id": "A", "concurrency": 1}],
                3, Path(temp) / "new", base=base, model="synthetic-model",
                temperature_reader=lambda: [91])
            self.assertEqual(seen, [])
            self.assertEqual(result["stop_reason"], "gpu_temperature_exceeds_90_c")

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaises(FileExistsError):
                self.run_fake("http://127.0.0.1:1/v1", out)
            self.assertEqual(list(out.iterdir()), [])

    def test_seed_only_when_explicit_and_budget_guard(self):
        body = lab.request_body(self.prompts()[0], {"id": "A", "concurrency": 1}, "m")
        self.assertNotIn("seed", body)
        self.assertEqual(lab.request_body(self.prompts()[0], {"seed": 42}, "m")["seed"], 42)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                lab.run_measurement(self.prompts(), [{"id": "A", "concurrency": 1}],
                    226, Path(temp) / "new", temperature_reader=lambda: [45])
            self.assertFalse((Path(temp) / "new").exists())


if __name__ == "__main__":
    unittest.main()
