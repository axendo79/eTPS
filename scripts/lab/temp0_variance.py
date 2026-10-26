"""Synthetic temperature-zero repeat calibration, separate from eTPS scoring.

Standard library only. Each invocation requires a NEW output directory; no resume,
retry, cache operation, model load or configuration change is performed. Example:
python -B scripts/lab/temp0_variance.py --prompts prompts.json --conditions
'[{"id":"A","concurrency":1},{"id":"B","concurrency":4}]' --repeats 10
--output ABSOLUTE_NEW_DIRECTORY

Request serialization matches etps_v02.adapter_openai.public_request and
workload.encode (with the explicitly requested top_p field added). Output equality
is exact Unicode text equality without normalization. Character positions are
zero-based Unicode code points; backend token positions are unavailable because
chat responses do not expose output token IDs. No answer correctness is scored.
"""
import argparse
import base64
import hashlib
import json
import os
import statistics
import subprocess
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit


def utc():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def request_body(prompt, condition, model):
    body = {"model": model, "temperature": 0, "top_p": 1, "max_tokens": 256,
            "stream": False, "messages": prompt["messages"]}
    if condition.get("seed") is not None:
        body["seed"] = condition["seed"]
    return body


def first_difference(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right)) if left != right else None


def spread(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return {"n": len(values), "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["condition"], row["prompt_id"]].append(row)
    result = []
    for (condition, prompt_id), group in sorted(groups.items()):
        valid = sorted((r for r in group if r["success"]),
                       key=lambda r: r.get("repeat_index", 0))
        counts = Counter(r["output_text"] for r in valid)
        # Ties follow earliest repeat, never response completion order.
        modal = counts.most_common(1)[0][0] if counts else None
        variants = [{"output_sha256": digest(text.encode("utf-8")), "count": count,
                     "first_differing_character_index_vs_modal": first_difference(modal, text)}
                    for text, count in counts.items()]
        positions = [v["first_differing_character_index_vs_modal"] for v in variants
                     if v["first_differing_character_index_vs_modal"] is not None]
        result.append({"condition": condition, "prompt_id": prompt_id,
            "attempted": len(group), "succeeded": len(valid), "failed": len(group) - len(valid),
            "distinct_outputs": len(counts), "modal_output_sha256":
            digest(modal.encode("utf-8")) if modal is not None else None,
            "modal_exact_match_rate": counts[modal] / len(valid) if valid else None,
            "first_differing_character_index": min(positions) if positions else None,
            "first_differing_model_token_index": None,
            "model_token_position_unavailable_reason": "response has no output token IDs",
            "variants": variants,
            "completion_tokens": spread((r.get("usage") or {}).get("completion_tokens") for r in group),
            "prompt_tokens": spread((r.get("usage") or {}).get("prompt_tokens") for r in group),
            "latency_seconds": spread(r["wall_latency_seconds"] for r in group)})
    return result


class Journal:
    def __init__(self, path):
        self.file = Path(path).open("xb")
        self.lock = threading.Lock()

    def write(self, value):
        with self.lock:
            self.file.write(encoded(value) + b"\n")
            self.file.flush()
            os.fsync(self.file.fileno())

    def close(self):
        self.file.close()


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def one_request(endpoint, body, prompt_id, condition, repeat_index, timeout):
    raw_request = encoded(body)
    row = {"prompt_id": prompt_id, "condition": condition, "repeat_index": repeat_index,
           "timestamp_utc": utc(), "request_json": body,
           "request_json_sha256": digest(raw_request), "http_status": None,
           "response_json": None, "response_body_base64": None,
           "response_body_utf8": None, "response_body_sha256": None,
           "output_text": None, "output_sha256": None, "usage": None,
           "returned_model": None, "finish_reason": None, "success": False, "error": None}
    began = time.monotonic()
    try:
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        req = request.Request(endpoint, data=raw_request,
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            response = opener.open(req, timeout=timeout)
        except error.HTTPError as exc:
            response = exc
        with response:
            row["http_status"] = response.code
            raw = response.read()
        row.update(response_body_base64=base64.b64encode(raw).decode("ascii"),
                   response_body_sha256=digest(raw), response_body_utf8=raw.decode("utf-8", errors="replace"))
        data = json.loads(raw)
        row["response_json"] = data
        if isinstance(data, dict):
            row["returned_model"] = data.get("model")
            row["usage"] = data.get("usage") if isinstance(data.get("usage"), dict) else None
        if not 200 <= row["http_status"] < 300:
            row["error"] = "http_error"
        elif row["returned_model"] != body["model"]:
            row["error"] = "missing_or_different_model_id"
        else:
            choices = data["choices"]
            if len(choices) != 1:
                raise ValueError("expected one choice")
            text = choices[0]["message"]["content"]
            if not isinstance(text, str):
                raise ValueError("expected string content")
            row.update(output_text=text, output_sha256=digest(text.encode("utf-8")),
                       finish_reason=choices[0].get("finish_reason"), success=True)
    except Exception as exc:
        row["error"] = type(exc).__name__ + ": " + str(exc)
    row["wall_latency_seconds"] = time.monotonic() - began
    row["completed_timestamp_utc"] = utc()
    return row


def gpu_temperatures():
    result = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                            check=True, capture_output=True, text=True, timeout=10,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def validate(prompts, conditions, repeats, base):
    if (not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1
            or not prompts or not conditions or len(prompts) * len(conditions) * repeats > 450):
        raise ValueError("invalid repeat/request budget (maximum 450)")
    url = urlsplit(base)
    if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path.rstrip("/") != "/v1"):
        raise ValueError("requires a loopback OpenAI-compatible /v1 base")
    if len({p["id"] for p in prompts}) != len(prompts):
        raise ValueError("duplicate prompt IDs")
    for prompt in prompts:
        messages = prompt["messages"]
        if not messages or messages[-1]["role"] != "user":
            raise ValueError("prompt must end with user message")
        for message in messages:
            if (set(message) != {"role", "content"} or message["role"] not in {"system", "user", "assistant"}
                    or not isinstance(message["content"], str)):
                raise ValueError("invalid message")
    if len({c["id"] for c in conditions}) != len(conditions):
        raise ValueError("duplicate condition IDs")
    for condition in conditions:
        if (set(condition) - {"id", "concurrency", "seed"}
                or type(condition["concurrency"]) is not int or not 1 <= condition["concurrency"] <= 4):
            raise ValueError("invalid condition (concurrency 1 to 4)")


def run_measurement(prompts, conditions, repeats, output, *, base="http://localhost:1234/v1",
                    model="google/gemma-4-e4b", timeout=300, temperature_reader=gpu_temperatures):
    validate(prompts, conditions, repeats, base)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    endpoint = base.rstrip("/") + "/chat/completions"
    schedule = [{"condition": c["id"], "prompt_id": p["id"], "repeat_index": r}
                for c in conditions for r in range(repeats) for p in prompts]
    plan = {"started_utc": utc(), "model": model, "endpoint": endpoint,
            "conditions": conditions, "repeats": repeats, "timeout_seconds": timeout,
            "prompts": prompts, "schedule": schedule, "request_count": len(schedule),
            "request_parameters": {"temperature": 0, "top_p": 1, "max_tokens": 256, "stream": False},
            "thinking_parameter": "omitted; no repository instruction found", "automatic_retries": 0,
            "stop_policy": {"cumulative_completed_failure_rate_gt": 0.05,
                            "different_model_id": True, "gpu_temperature_gt_c": 90},
            "cache_policy": "server cache left unchanged; A precedes B; no warming or flushing"}
    with (output / "plan.json").open("xb") as file:
        file.write(encoded(plan) + b"\n")
        file.flush()
        os.fsync(file.fileno())
    journal = Journal(output / "requests.jsonl")
    dispatches = Journal(output / "dispatches.jsonl")
    gpu = Journal(output / "gpu.jsonl")
    stop = threading.Event()
    monitor_done = threading.Event()
    reason_lock = threading.Lock()
    reason = [None]
    rows = []
    counts = {c["id"]: {"sent": 0, "succeeded": 0, "failed": 0} for c in conditions}

    def halt(value):
        with reason_lock:
            if reason[0] is None:
                reason[0] = value
        stop.set()

    def sample_gpu():
        try:
            temperatures = temperature_reader()
            if not temperatures:
                raise ValueError("no GPU temperatures returned")
            gpu.write({"timestamp_utc": utc(), "temperatures_c": temperatures})
            if max(temperatures) > 90:
                halt("gpu_temperature_exceeds_90_c")
        except Exception as exc:
            gpu.write({"timestamp_utc": utc(), "error": type(exc).__name__})
            halt("gpu_monitor_unavailable")

    def monitor():
        while not monitor_done.wait(1):
            sample_gpu()

    def execute(prompt, condition, repeat):
        row = one_request(endpoint, request_body(prompt, condition, model),
                          prompt["id"], condition["id"], repeat, timeout)
        journal.write(row)  # Durable as soon as this request finishes, even during drain.
        if row["returned_model"] is not None and row["returned_model"] != model:
            halt("different_model_id")
        return row

    sample_gpu()
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        for condition in conditions:
            cid = condition["id"]
            jobs = iter((p, r) for r in range(repeats) for p in prompts)
            exhausted = False
            with ThreadPoolExecutor(max_workers=condition["concurrency"]) as pool:
                pending = set()
                while pending or (not exhausted and not stop.is_set()):
                    while not exhausted and not stop.is_set() and len(pending) < condition["concurrency"]:
                        try:
                            prompt, repeat = next(jobs)
                        except StopIteration:
                            exhausted = True
                            break
                        body = request_body(prompt, condition, model)
                        dispatches.write({"timestamp_utc": utc(), "prompt_id": prompt["id"],
                            "condition": cid, "repeat_index": repeat, "request_json_sha256": digest(encoded(body))})
                        counts[cid]["sent"] += 1
                        pending.add(pool.submit(execute, prompt, condition, repeat))
                    if not pending:
                        break
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        row = future.result()
                        rows.append(row)
                        counts[cid]["succeeded" if row["success"] else "failed"] += 1
                        totals = {key: sum(c[key] for c in counts.values()) for key in ("succeeded", "failed")}
                        if totals["failed"] / (totals["succeeded"] + totals["failed"]) > 0.05:
                            halt("failure_rate_exceeds_5_percent")
                        print(f"PROGRESS {cid} sent={counts[cid]['sent']} succeeded={counts[cid]['succeeded']} "
                              f"failed={counts[cid]['failed']} prompt={row['prompt_id']} repeat={row['repeat_index']}", flush=True)
            print("CONDITION " + cid + " " + json.dumps(counts[cid]), flush=True)
            if stop.is_set():
                break
    except KeyboardInterrupt:
        halt("operator_interrupt")
        raise
    finally:
        monitor_done.set()
        thread.join(timeout=15)
        journal.close()
        dispatches.close()
        gpu.close()
    result = {"completed_utc": utc(), "counts": counts, "planned": len(schedule),
              "unattempted": len(schedule) - sum(c["sent"] for c in counts.values()),
              "stop_reason": reason[0], "groups": summarize(rows)}
    with (output / "summary.json").open("xb") as file:
        file.write(encoded(result) + b"\n")
        file.flush()
        os.fsync(file.fileno())
    print("TOTAL " + json.dumps({k: v for k, v in result.items() if k != "groups"}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--conditions", required=True, help="JSON array, in execution order")
    parser.add_argument("--repeats", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base", default="http://localhost:1234/v1")
    parser.add_argument("--model", default="google/gemma-4-e4b")
    parser.add_argument("--timeout", default=300, type=float)
    args = parser.parse_args()
    document = json.loads(args.prompts.read_text(encoding="utf-8"))
    result = run_measurement(document["prompts"], json.loads(args.conditions), args.repeats,
                             args.output, base=args.base, model=args.model, timeout=args.timeout)
    return 2 if result["stop_reason"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
