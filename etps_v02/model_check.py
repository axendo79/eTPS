"""Model metadata lookup only; never transmits tasks or dispatches generation."""
from urllib import error, request
from urllib.parse import quote

from .adapter_openai import NoRedirect, credential
from .limits import MAX_RESPONSE_BYTES
from .live_plan import arm_endpoint, endpoint, validate_live
from .scorer import InvalidRecord, require
from .workload import decode


def check_models(plan, *, allow_remote=False):
    require(plan.get("schema") == "etps-live-plan-v1", "model check requires a live plan")
    validate_live(plan, allow_remote=allow_remote)
    results = []
    for name, arm in plan["arms"].items():
        status = "unavailable"
        try:
            key = credential(arm)
        except InvalidRecord:
            results.append({"arm": name, "status": "auth-error"})
            continue
        base = endpoint(arm_endpoint(plan, name))[0]
        path = {"anthropic": "/v1/models/", "lmstudio-native": "/api/v0/models/"}.get(
            arm["provider"], "/models/")
        headers = {}
        if arm["provider"] == "anthropic":
            headers["anthropic-version"] = arm["anthropic_version"]
        if key:
            headers["x-api-key" if arm["provider"] == "anthropic" else "Authorization"] = (
                key if arm["provider"] == "anthropic" else "Bearer " + key)
        try:
            opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
            req = request.Request(base + path + quote(arm["model"], safe=""), headers=headers, method="GET")
            try:
                response = opener.open(req, timeout=plan["request_deadline_seconds"])
            except error.HTTPError as exc:
                response = exc
            with response:
                if response.code in (401, 403):
                    status = "auth-error"
                elif response.code == 404:
                    status = "not-found"
                elif response.code == 200:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) <= MAX_RESPONSE_BYTES and not (key and key.encode("ascii") in raw):
                        data = decode(raw)
                        if isinstance(data, dict) and data.get("id") == arm["model"]:
                            status = "ok"
        except Exception:
            pass  # Never print response bodies, credentials or exception text.
        results.append({"arm": name, "status": status})
    return results
