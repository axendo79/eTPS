"""Strict offline bundle ingestion; preserves original bytes separately from JSON."""
import base64
import hashlib
import json

from . import limits
from .scorer import UNIT, InvalidRecord, mapping, require, telemetry, validate

LEGACY_INVALIDATION_POLICY = {
    "script_exhausted": "invalidate", "script_leftover": "invalidate",
    "execution_error": "invalidate", "interrupted": "invalidate",
    "operator_abort": "invalidate", "system_terminal_failure": "retain",
}
INVALIDATION_POLICY = {**LEGACY_INVALIDATION_POLICY, "storage_error": "invalidate"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise InvalidRecord("JSON: invalid value") from exc


def decode(raw, *, admission=True):
    require(isinstance(raw, bytes), "JSON: expected bytes")
    if admission:
        limits.check_json_depth(raw)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise InvalidRecord("nonfinite JSON constant")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        raise InvalidRecord("invalid strict UTF-8 JSON") from exc


def raw_response(value, path="response.raw_base64", *, admission=True, limit="MAX_RESPONSE_BYTES"):
    require(isinstance(value, str), path + ": expected base64 string")
    if admission:
        limits.check(max(0, (len(value) // 4) * 3 - 2), limit)
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise InvalidRecord(path + ": invalid raw response bytes") from exc
    if admission:
        limits.check(len(raw), limit)
    return raw


def script_responses(raw, *, admission=True):
    require(isinstance(raw, bytes), "JSON: expected bytes")
    if admission:
        limits.check(len(raw), "MAX_ARTIFACT_BYTES")
    script = decode(raw, admission=admission)
    require(isinstance(script, dict) and set(script) == {"responses"}, "invalid script")
    require(isinstance(script["responses"], list), "responses must be a list")
    if admission:
        limits.check(len(script["responses"]), "MAX_SCRIPT_RESPONSES")
    for index, response in enumerate(script["responses"]):
        path = f"script.responses[{index}]"
        require(isinstance(response, dict) and set(response) <= {"status", "raw_base64", "generation"},
                "unsupported response field")
        mapping(response, path, ("status", "raw_base64"))
        require(isinstance(response["status"], str) and response["status"] in {"ok", "timeout"},
                path + ".status: invalid script transport status")
        raw_response(response["raw_base64"], path + ".raw_base64", admission=admission)
        usage = response.get("generation")
        if usage is not None:
            telemetry(usage, path + ".generation")
    return script["responses"]


def validate_bundle(plan_raw, artifacts, allow_legacy=False, *, authoring=True):
    """Schema compatibility and authoring enforcement are independent choices.

    allow_legacy admits v1 field layouts only. Evidence replay explicitly selects
    authoring=False; import and callers reasserting the gate leave it True.
    """
    require(isinstance(plan_raw, bytes), "JSON: expected bytes")
    if authoring:
        limits.check(len(plan_raw), "MAX_PLAN_BYTES")
    plan = decode(plan_raw, admission=authoring)
    mapping(plan, "plan")
    mapping(artifacts, "artifacts")
    legacy = allow_legacy and plan.get("schema") == "etps-offline-plan-v1"
    fields = {"schema", "purpose", "tasks", "slots"}
    if not legacy:
        fields |= {"unit", "invalidation_policy"}
    require(set(plan) == fields, "invalid plan fields")
    require((legacy or plan["schema"] == "etps-offline-plan-v2") and
            plan["purpose"] == "offline-verification", "only offline verification supported")
    if not legacy:
        require(plan["unit"] == UNIT, "unsupported plan unit")
        require(plan["invalidation_policy"] in (INVALIDATION_POLICY, LEGACY_INVALIDATION_POLICY),
                "incomplete or unsupported invalidation policy")
    require(isinstance(plan["tasks"], dict) and bool(plan["tasks"]), "missing task manifests")
    require(isinstance(plan["slots"], list) and bool(plan["slots"]), "missing planned slots")
    if authoring:
        limits.check(len(plan["slots"]), "MAX_PLAN_SLOTS")
    for key, raw in artifacts.items():
        if authoring and isinstance(raw, bytes):
            limits.check(len(raw), "MAX_ARTIFACT_BYTES")
        require(isinstance(raw, bytes) and sha(raw) == key, "artifact byte hash mismatch")
    referenced, ids = set(), set()
    for task, key in plan["tasks"].items():
        require(isinstance(task, str) and bool(task) and isinstance(key, str) and key in artifacts,
                "plan.tasks: missing task artifact")
        manifest = decode(artifacts[key], admission=authoring)
        validate(manifest, authoring=authoring)
        if not legacy:
            require(manifest["unit"] == plan["unit"], "task/plan unit mismatch")
            require(all("begin_after" in o for o in manifest["obligations"].values()),
                    "new plans require event-ID obligation boundaries")
        # No silent no-op for memory/reset/replay actions not yet implemented.
        require(all(n["kind"] in {"user", "probe", "terminal"} for n in manifest["nodes"].values()),
                "offline runner supports only user/probe/terminal nodes")
        referenced.add(key)
    for index, slot in enumerate(plan["slots"]):
        mapping(slot, f"plan.slots[{index}]")
        require(set(slot) == {"id", "arm", "task", "script_sha256"}, "invalid slot fields")
        require(all(isinstance(slot[k], str) and slot[k] for k in slot), "invalid slot identity")
        require(slot["id"] not in ids and slot["task"] in plan["tasks"], "duplicate slot or missing task")
        require(slot["script_sha256"] in artifacts, "missing response script")
        script_responses(artifacts[slot["script_sha256"]], admission=authoring)
        ids.add(slot["id"])
        referenced.add(slot["script_sha256"])
    require(referenced == set(artifacts), "unreferenced artifacts")
    return plan


def safety_warnings(plan_raw, artifacts):
    """Label old, readable evidence outside today's admission envelope."""
    exceeded = set()

    def check_size(value, name):
        if value > getattr(limits, name):
            exceeded.add(name)

    plan = decode(plan_raw, admission=False)
    check_size(len(plan_raw), "MAX_PLAN_BYTES")
    check_size(len(plan["slots"]), "MAX_PLAN_SLOTS")
    for raw in [plan_raw, *artifacts.values()]:
        try:
            limits.check_json_depth(raw)
        except InvalidRecord:
            exceeded.add("MAX_JSON_NESTING_DEPTH")
    for raw in artifacts.values():
        check_size(len(raw), "MAX_ARTIFACT_BYTES")
    for key in set(s["script_sha256"] for s in plan["slots"]):
        responses = script_responses(artifacts[key], admission=False)
        check_size(len(responses), "MAX_SCRIPT_RESPONSES")
        for response in responses:
            check_size(len(raw_response(response["raw_base64"], admission=False)), "MAX_RESPONSE_BYTES")
    return ["legacy_safety_limit: " + name for name in sorted(exceeded)]
