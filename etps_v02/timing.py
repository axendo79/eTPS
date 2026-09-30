"""Frozen decode-v1 telemetry projection from verified backend response fields."""
from fractions import Fraction

from .scorer import finite, integer


def project(provider, response):
    usage = response.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    backend = response.get("backend_stats", {})
    stats = backend.get("stats", {})
    stats = stats if isinstance(stats, dict) else {}
    timings = backend.get("timings", {})
    timings = timings if isinstance(timings, dict) else {}
    result = {"convention": "decode-v1", "decode_generation": None,
              "completion_token_scope": "backend completion tokens, including reasoning tokens; no subtraction or estimate"}

    def observation(name, value, sources):
        result[name] = {"value": value, "source_fields": sources}

    def field(name, values, key, prefix, *, count=False, scale=1):
        value = values.get(key)
        good = integer(value) if count else finite(value)
        observation(name, value / scale if good and scale != 1 else value if good else None,
                    [prefix + key])

    field("client_elapsed_seconds", response, "client_latency_seconds", "")
    field("completion_tokens", usage, "completion_tokens", "usage.", count=True)
    field("prompt_tokens", usage, "prompt_tokens", "usage.", count=True)
    for name in ("full_generation_tps", "ttft_seconds", "prompt_prefill_seconds", "decode_seconds", "decode_tps"):
        observation(name, None, [])
    if response.get("status") != "ok":
        result["unavailable_reason"] = "transport_or_envelope_failure"
        return result

    tokens = seconds = None
    sources = []
    if provider == "lmstudio-native":
        field("ttft_seconds", stats, "time_to_first_token", "stats.")
        field("prompt_prefill_seconds", stats, "prompt_eval_time", "stats.")
        count, generation, first = usage.get("completion_tokens"), stats.get("generation_time"), stats.get("time_to_first_token")
        full_sources = ["usage.completion_tokens", "stats.generation_time"]
        if integer(count) and finite(generation, positive=True):
            observation("full_generation_tps", float(Fraction(count) / Fraction(str(generation))), full_sources)
        else:
            observation("full_generation_tps", None, full_sources)
        sources = ["usage.completion_tokens", "stats.generation_time", "stats.time_to_first_token"]
        if finite(generation) and finite(first):
            duration = Fraction(str(generation)) - Fraction(str(first))
            if duration > 0:
                observation("decode_seconds", float(duration), sources[1:])
                if integer(count) and count > 1:
                    tokens, seconds = count - 1, float(duration)
    elif provider == "openai-compatible":
        # predicted_n/predicted_ms do not establish first-token boundaries.
        # Only literal decode names qualify; do not infer from predicted rates.
        sources = ["timings.decode_n", "timings.decode_ms"]
        count, duration = timings.get("decode_n"), timings.get("decode_ms")
        if integer(count) and count > 0 and finite(duration, positive=True):
            tokens, seconds = count, float(Fraction(str(duration)) / 1000)
            observation("decode_seconds", seconds, ["timings.decode_ms"])
        field("prompt_prefill_seconds", timings, "prompt_ms", "timings.", scale=1000)
        field("ttft_seconds", timings, "time_to_first_token_ms", "timings.", scale=1000)
        if result["prompt_tokens"]["value"] is None:
            field("prompt_tokens", timings, "prompt_n", "timings.", count=True)
        full_n, full_ms = timings.get("full_generation_n"), timings.get("full_generation_ms")
        if integer(full_n) and finite(full_ms, positive=True):
            observation("full_generation_tps", float(Fraction(full_n) * 1000 / Fraction(str(full_ms))),
                        ["timings.full_generation_n", "timings.full_generation_ms"])
    if tokens is not None and seconds is not None and seconds > 0:
        result["decode_generation"] = {"tokens": tokens, "seconds": seconds}
        observation("decode_tps", float(Fraction(tokens) / Fraction(str(seconds))), sources)
        result["unavailable_reason"] = None
    else:
        observation("decode_tps", None, sources)
        result["unavailable_reason"] = "explicit_decode_count_and_positive_interval_unavailable"
    result["decode_generation_source_fields"] = sources
    return result
