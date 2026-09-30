"""Explicit live settings and authorization, separate from offline plans."""
import re
from urllib.parse import urlsplit, urlunsplit
from .scorer import finite, identity, integer, mapping, require

SCHEMA = "etps-live-plan-v1"


def endpoint(value):
    identity(value, "endpoint")
    require(not any(ord(c) <= 32 for c in value), "invalid endpoint")
    try:
        u = urlsplit(value)
        port = u.port
        host = u.hostname
    except ValueError:
        require(False, "invalid endpoint")
    require(u.scheme in {"http", "https"} and bool(host) and u.username is None
            and u.password is None and not u.query and not u.fragment, "invalid endpoint")
    local = host in {"localhost", "127.0.0.1", "::1"}
    require(local or u.scheme == "https", "remote endpoints require HTTPS")
    # Avoid DNS resolution for localhost and prohibit proxy/redirect transport.
    authority = ("127.0.0.1" if host == "localhost" else u.netloc)
    if host == "localhost" and port is not None:
        authority += ":" + str(port)
    return urlunsplit((u.scheme, authority, u.path.rstrip("/"), "", "")), host, not local


def arm_endpoint(plan, arm):
    return plan["arms"][arm].get("endpoint", plan["endpoint"])


def validate_live(plan, *, allow_remote=False, execution=True):
    if "response_extraction" in plan:
        require(plan["response_extraction"] == "fence-v1", "unsupported response_extraction")
    endpoint(plan["endpoint"])
    arms = mapping(plan["arms"], "arms")
    require(bool(arms), "missing live arms")
    for arm in arms.values():
        mapping(arm, "arm")
    remote = any(endpoint(arm_endpoint(plan, name))[2] for name in arms)
    exposure = mapping(plan["exposure"], "exposure", ("non_loopback", "remote_endpoint_authorized"))
    require(set(exposure) == {"non_loopback", "remote_endpoint_authorized"}
            and type(exposure["non_loopback"]) is bool
            and exposure["non_loopback"] == remote
            and type(exposure["remote_endpoint_authorized"]) is bool, "invalid exposure declaration")
    if remote:
        require(exposure["remote_endpoint_authorized"] and (allow_remote or not execution),
                "remote endpoint requires plan authorization and --allow-remote")
    for key in ("request_deadline_seconds", "trial_wall_limit_seconds"):
        require(finite(plan[key], positive=True), key + " must be explicit and positive")
    arms = mapping(plan["arms"], "arms")
    require(bool(arms), "missing live arms")
    for name, arm in arms.items():
        identity(name, "arm name")
        required = {"provider", "model", "temperature", "seed", "max_tokens", "api_key_env"}
        mapping(arm, "arm", required)
        require(arm["provider"] in ("openai-compatible", "anthropic", "lmstudio-native"), "unsupported provider")
        if arm["provider"] == "lmstudio-native":
            require(not endpoint(arm_endpoint(plan, name))[2], "lmstudio-native requires loopback")
            require(arm["api_key_env"] is None, "lmstudio-native does not support keys")
        if arm["provider"] == "anthropic":
            required.add("anthropic_version")
            require(arm["seed"] is None, "anthropic seed must be explicit null (unsupported)")
            identity(arm.get("anthropic_version"), "anthropic_version")
            require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", arm["anthropic_version"]), "invalid anthropic_version")
        require(required <= arm.keys() and arm.keys() <= required | {"system_prompt", "endpoint"}, "invalid arm fields")
        identity(arm["model"], "model")
        require(finite(arm["temperature"]) and arm["temperature"] >= 0, "invalid temperature")
        require(arm["seed"] is None or type(arm["seed"]) is int, "invalid seed")
        require(integer(arm["max_tokens"]) and arm["max_tokens"] > 0, "invalid max_tokens")
        require(arm["api_key_env"] is None or isinstance(arm["api_key_env"], str)
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", arm["api_key_env"]), "invalid API key environment reference")
        require("system_prompt" not in arm or isinstance(arm["system_prompt"], str), "invalid system_prompt")
    return remote
