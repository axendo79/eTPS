"""Non-streaming urllib transport for explicit OpenAI-compatible/Anthropic plans.

No model/task/arm data beyond a prebuilt public request enters this module.
"""
import base64
import os
import queue
import socket
import threading
import time
from urllib import error, request
from urllib.parse import urlsplit

from .limits import MAX_RESPONSE_BYTES
from .live_plan import endpoint
from .scorer import InvalidRecord, finite, integer, require
from .workload import decode, encode, sha


def public_request(arm, conversation):
    messages = [{"role": m["role"], "content": m["content"]} for m in conversation]
    body = {"model": arm["model"], "temperature": arm["temperature"],
            "max_tokens": arm["max_tokens"], "stream": False, "messages": messages}
    if arm["provider"] == "anthropic":
        if "system_prompt" in arm:
            body["system"] = arm["system_prompt"]
    else:
        if "system_prompt" in arm:
            messages.insert(0, {"role": "system", "content": arm["system_prompt"]})
        if arm["seed"] is not None:
            body["seed"] = arm["seed"]
    return body


def envelope(provider, status, body):
    """Pure decoding for transport and evidence replay; malformed content is OK."""
    result = {"status": "timeout", "raw_base64": "", "usage": None,
              "generation": None, "generation_source": None, "backend_stats": {},
              "transport_detail": "http_status"}
    if not 200 <= status < 300:
        return result
    try:
        data = decode(body)
        require(isinstance(data, dict), "envelope")
        if provider == "anthropic":
            require(data.get("type") == "message" and data.get("role") == "assistant"
                    and isinstance(data.get("content"), list), "envelope")
            require(all(isinstance(b, dict) and b.get("type") == "text"
                        and isinstance(b.get("text"), str) for b in data["content"]), "envelope")
            content = "".join(b["text"] for b in data["content"])
        else:
            choices = data.get("choices")
            require(isinstance(choices, list) and len(choices) == 1, "envelope")
            message = choices[0]["message"]
            require(message.get("role") == "assistant", "envelope")
            content = message["content"]
        require(isinstance(content, str), "envelope")
        raw = content.encode("utf-8")
        result.update(status="ok", raw_base64=base64.b64encode(raw).decode("ascii"),
                      usage=data.get("usage"), transport_detail=None,
                      backend_stats={k: data[k] for k in ("stats", "timings") if k in data})
        # Only this explicitly named generation count/time pair is interpreted.
        # tokens_per_second or client latency alone never supplies a duration.
        timings = data.get("timings")
        if isinstance(timings, dict) and integer(timings.get("predicted_n")) and finite(
                timings.get("predicted_ms"), positive=True):
            result["generation"] = {"tokens": timings["predicted_n"], "seconds": timings["predicted_ms"] / 1000}
            result["generation_source"] = ["timings.predicted_n", "timings.predicted_ms"]
        encode(result)  # Reject nonserializable Unicode/number telemetry too.
        return result
    except (InvalidRecord, KeyError, TypeError, AttributeError, UnicodeError, OverflowError):
        return {**result, "status": "timeout", "raw_base64": "", "usage": None,
                "generation": None, "generation_source": None, "backend_stats": {},
                "transport_detail": "invalid_envelope"}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_once(url, body, headers, deadline):
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    req = request.Request(url, data=encode(body), headers=headers, method="POST")
    try:
        response = opener.open(req, timeout=deadline)
    except error.HTTPError as exc:
        response = exc  # Preserve non-2xx body hash; never follow a redirect.
    with response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return None, None, "response_size_limit"
        return response.code, raw, None


def credential(arm):
    """Read at dispatch; never include environment values in diagnostics."""
    name = arm["api_key_env"]
    key = os.environ.get(name) if name else None
    require(not name or (bool(key) and all(33 <= ord(c) <= 126 for c in key)),
            "configured credential missing or malformed")
    return key


def preflight(base, arm, deadline):
    """Validate credentials and TCP reachability without sending application data."""
    credential(arm)
    url = urlsplit(endpoint(base)[0])
    port = url.port if url.port is not None else (443 if url.scheme == "https" else 80)
    try:
        with socket.create_connection((url.hostname, port), timeout=deadline):
            pass
    except OSError:
        raise InvalidRecord("endpoint TCP preflight failed") from None


def send(base, arm, body, deadline):
    """One dispatch, bounded controller wait, sanitized errors; no automatic retry.

    The daemon worker may outlive a deadline; cancellation of backend generation
    is not claimed. It cannot journal or issue another request.
    """
    url, _, _ = endpoint(base)
    url += "/v1/messages" if arm["provider"] == "anthropic" else "/chat/completions"
    began = time.monotonic()
    key = credential(arm)
    headers = {"Content-Type": "application/json"}
    result = {"status": "timeout", "raw_base64": "", "usage": None, "generation": None,
              "generation_source": None, "backend_stats": {}, "transport_detail": None,
              "http_status": None, "http_body_base64": None, "http_body_sha256": None}
    if arm["provider"] == "anthropic":
        headers["anthropic-version"] = arm["anthropic_version"]
    if key:
        headers["x-api-key" if arm["provider"] == "anthropic" else "Authorization"] = (
            key if arm["provider"] == "anthropic" else "Bearer " + key)
    replies = queue.Queue(maxsize=1)
    def worker():
        try:
            replies.put(_http_once(url, body, headers, deadline))
        except Exception as exc:
            cause = exc.reason if isinstance(exc, error.URLError) else exc
            code = ("deadline_exceeded" if isinstance(cause, (TimeoutError, socket.timeout)) else
                    "connection_refused" if isinstance(cause, ConnectionRefusedError) else "transport_error")
            replies.put((None, None, code))  # Never retain exception text/URL/headers.
    threading.Thread(target=worker, daemon=True).start()
    try:
        status, raw, detail = replies.get(timeout=max(0, deadline - (time.monotonic() - began)))
    except queue.Empty:
        status, raw, detail = None, None, "deadline_exceeded"
    if raw is not None:
        result["http_status"] = status
        result["http_body_sha256"] = sha(raw)
        # Never persist an accidentally echoed credential, even in an error body.
        if key and key.encode("ascii") in raw:
            detail = "credential_echo"
        else:
            result["http_body_base64"] = base64.b64encode(raw).decode("ascii")
            result.update(envelope(arm["provider"], status, raw))
    if detail:
        result["transport_detail"] = detail
    result["client_latency_seconds"] = time.monotonic() - began
    return result
