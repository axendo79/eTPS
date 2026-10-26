"""Synthetic fake-server coverage for optional lab fields and a counted probe."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_temp0_variance import fake_server, lab


def reply(body, index, *, reasoning="", tokens=0, status=200):
    usage = {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}
    if tokens is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": tokens}
    return status, {"model": "synthetic-model", "choices": [{"message": {
        "role": "assistant", "content": "synthetic answer", "reasoning_content": reasoning},
        "finish_reason": "stop"}], "usage": usage}


class Temp0ExtraBodyTests(unittest.TestCase):
    def prompts(self):
        return [{"id": f"p{i}", "messages": [{"role": "user", "content": f"invented {i}"}]}
                for i in range(2)]

    def run_fake(self, base, output, *, concurrency=1, verify=True):
        return lab.run_measurement(self.prompts(), [{"id": "A", "concurrency": concurrency}],
            3, output, base=base, model="synthetic-model", temperature_reader=lambda: [45],
            extra_body={"reasoning_effort": "none"}, verify_no_reasoning=verify)

    def test_extra_fields_are_sent_hashed_and_planned_with_counted_probe(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(reply) as (base, seen, _):
            output = Path(temp) / "new"
            result = self.run_fake(base, output)
            plan = json.loads((output / "plan.json").read_bytes())
            rows = [json.loads(line) for line in (output / "requests.jsonl").read_bytes().splitlines()]
            self.assertEqual(result["counts"]["A"], {"sent": 6, "succeeded": 6, "failed": 0})
            self.assertEqual(len(seen), 6)  # Probe replaces the first slot, never adds a call.
            self.assertEqual(plan["extra_body"], {"reasoning_effort": "none"})
            self.assertTrue(plan["preflight_probe"]["counts_toward_plan"])
            self.assertTrue(result["preflight_probe"]["verified"])
            self.assertTrue(rows[0]["is_preflight_probe"])
            self.assertFalse(any(row["is_preflight_probe"] for row in rows[1:]))
            self.assertEqual([(r["prompt_id"], r["repeat_index"]) for r in rows],
                             [(f"p{i}", repeat) for repeat in range(3) for i in range(2)])
            for row, (_, raw, body) in zip(rows, seen):
                self.assertEqual(body["reasoning_effort"], "none")
                self.assertNotIn("seed", body)
                self.assertEqual(row["request_json_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(row["reasoning_content"], "")
                self.assertEqual(row["reasoning_tokens"], 0)
                self.assertTrue(row["thinking_off_verified"])

    def test_extra_body_cannot_override_frozen_core_or_seed(self):
        for name in ("model", "messages", "temperature", "top_p", "max_tokens", "stream", "seed"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    lab.request_body(self.prompts()[0], {"id": "A"}, "m", extra_body={name: "changed"})
        for value in ([], "text", True, {"x": float("nan")}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    lab.request_body(self.prompts()[0], {"id": "A"}, "m", extra_body=value)

    def test_extra_fields_do_not_implicitly_enable_reasoning_gate(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(
                lambda b, i: reply(b, i, reasoning="synthetic thought", tokens=1)) as (base, seen, _):
            result = self.run_fake(base, Path(temp) / "new", verify=False)
            self.assertEqual(len(seen), 6)
            self.assertIsNone(result["stop_reason"])

    def test_probe_with_reasoning_stops_before_any_parallel_dispatch(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(
                lambda b, i: reply(b, i, reasoning="synthetic thought", tokens=1)) as (base, seen, active):
            result = self.run_fake(base, Path(temp) / "new", concurrency=4)
            self.assertEqual(len(seen), 1)
            self.assertEqual(active[1], 1)
            self.assertEqual(result["stop_reason"], "nonempty_reasoning_content")
            self.assertFalse(result["preflight_probe"]["verified"])
            self.assertEqual(result["unattempted"], 5)

    def test_probe_requires_explicit_integer_zero_reasoning_usage(self):
        for tokens in (1, None, False):
            with self.subTest(tokens=tokens), tempfile.TemporaryDirectory() as temp, fake_server(
                    lambda b, i: reply(b, i, tokens=tokens)) as (base, seen, _):
                result = self.run_fake(base, Path(temp) / "new")
                self.assertEqual(len(seen), 1)
                self.assertEqual(result["stop_reason"], "probe_reasoning_usage_not_zero")
                self.assertFalse(result["preflight_probe"]["verified"])

    def test_later_reasoning_stops_without_retry_and_retains_response(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(
                lambda b, i: reply(b, i, reasoning="later thought" if i == 2 else "")) as (base, seen, _):
            output = Path(temp) / "new"
            result = self.run_fake(base, output)
            self.assertEqual(len(seen), 2)
            self.assertTrue(result["preflight_probe"]["verified"])
            self.assertEqual(result["stop_reason"], "nonempty_reasoning_content")
            rows = [json.loads(line) for line in (output / "requests.jsonl").read_bytes().splitlines()]
            self.assertEqual(rows[1]["reasoning_content"], "later thought")
            self.assertFalse(rows[1]["thinking_off_verified"])
            self.assertTrue(rows[1]["success"])  # Transport success is separate from the gate.

    def test_reasoning_in_http_error_also_stops(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(
                lambda b, i: reply(b, i, reasoning="error thought" if i == 2 else "",
                                   status=400 if i == 2 else 200)) as (base, seen, _):
            result = self.run_fake(base, Path(temp) / "new")
            self.assertEqual(len(seen), 2)
            self.assertEqual(result["stop_reason"], "nonempty_reasoning_content")
            self.assertEqual(result["counts"]["A"]["failed"], 1)

    def test_failed_probe_never_allows_following_slots(self):
        with tempfile.TemporaryDirectory() as temp, fake_server(
                lambda b, i: reply(b, i, status=503)) as (base, seen, _):
            result = self.run_fake(base, Path(temp) / "new", concurrency=4)
            self.assertEqual(len(seen), 1)
            self.assertEqual(result["stop_reason"], "probe_request_failed")
            self.assertFalse(result["preflight_probe"]["verified"])


if __name__ == "__main__":
    unittest.main()
