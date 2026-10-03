"""Opt-in memory diagnostics, isolated from answer and throughput scoring."""
from fractions import Fraction
import math

from .scorer import InvalidRecord
from .workload import decode, encode, raw_response

KEYS = ("extraction_calls", "extraction_prompt_tokens", "extraction_completion_tokens",
        "extraction_seconds", "beliefs_injected", "injected_chars", "facts_rejected")


def numeric(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def project(response, field):
    """Copy a flat object exactly; retain invalid originals only in raw HTTP bytes."""
    result = {"memory_telemetry": None, "memory_telemetry_status": "unavailable"}
    if response.get("http_body_base64") is None:
        return result
    try:
        body = decode(raw_response(response["http_body_base64"], admission=False), admission=False)
        if not isinstance(body, dict):
            raise InvalidRecord("expected response object")
        if field not in body:
            return {**result, "memory_telemetry_status": "missing"}
        value = body[field]
        if not isinstance(value, dict) or not all(v is None or type(v) is str or numeric(v) for v in value.values()):
            raise InvalidRecord("invalid memory object")
        encode(value)  # Reject invalid Unicode as well as nonfinite numbers.
        return {"memory_telemetry": value, "memory_telemetry_status": "valid"}
    except InvalidRecord:
        return {**result, "memory_telemetry_status": "invalid"}


def requests(rows):
    """Unanswered intents remain in coverage denominators."""
    result = []
    pending = None
    for row in rows:
        p = row["payload"]
        if row["kind"] == "request":
            pending = {"status": "unavailable", "value": None}
            result.append(pending)
        elif row["kind"] == "event" and p["kind"] in {"probe", "delivery"} and pending is not None:
            pending.update(status=p.get("memory_telemetry_status", "unavailable"),
                           value=p.get("memory_telemetry"))
            pending = None
    return result


def summarize(observations):
    result = {"request_count": len(observations),
              **{status + "_count": sum(o["status"] == status for o in observations)
                 for status in ("valid", "invalid", "missing", "unavailable")}, "metrics": {}}
    for key in KEYS:
        values = [o["value"][key] for o in observations if o["status"] == "valid"
                  and key in o["value"] and numeric(o["value"][key])]
        summed = sum((Fraction(str(v)) for v in values), Fraction(0))
        if summed.denominator == 1:
            summed = summed.numerator
        result["metrics"][key] = {"sum": summed, "coverage_count": len(values),
                                   "request_count": len(observations)}
    return result
