"""Opt-in public question descriptors and compressed H3 rendering.

This diagnostic support module is not wired into runner, mapper or replay.
Rendering accepts public descriptors only; it never reads expected answers.
"""
import hashlib
import json
from pathlib import Path
import stat

VERSION = "h3-compressed-v1"
LEGACY_VERSION = "legacy-v1"
SCHEMA = "etps-question-contract-v1"
FILENAME = "question-contract.json"
TEMPLATES = json.loads(Path(__file__).with_name("h3_wording.json").read_bytes())
KINDS = {"status", "missing_status", "scalar", "set", "source", "item", "other"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def read_named(root, name, ceiling=16 * 1024 * 1024):
    """Read one bounded regular file directly inside the declared directory."""
    if (type(name) is not str or not name or name in (".", "..") or
            any(char in name for char in ("/", "\\", ":")) or Path(name).name != name):
        raise ValueError("file boundary")
    root = Path(root)
    path = root / name
    if (path.is_symlink() or path.is_junction() or
            not path.resolve().is_relative_to(root.resolve()) or
            not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > ceiling):
        raise ValueError("file boundary")
    with path.open("rb") as stream:
        raw = stream.read(ceiling + 1)
    if len(raw) > ceiling:
        raise ValueError("file size")
    return raw


def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("closed question contract schema differs")


def text(value):
    if type(value) is not str or not value.strip() or "<" in value or ">" in value:
        raise ValueError("public text required")
    value.encode("utf-8")
    return value


def read_release(root, bundle_sha256):
    path = Path(root) / FILENAME
    if not path.exists() and not path.is_symlink():
        return None
    raw = read_named(root, FILENAME, 8 * 1024 * 1024)
    declaration = unique_json(raw)
    closed(declaration, ("schema", "question_contract_version", "release_id", "bundle_sha256", "tasks"))
    if declaration["schema"] != SCHEMA or declaration["question_contract_version"] not in (VERSION, LEGACY_VERSION):
        raise ValueError("unsupported question contract")
    if declaration["bundle_sha256"] != bundle_sha256:
        raise ValueError("question contract bundle binding differs")
    text(declaration["release_id"])
    if declaration["question_contract_version"] == LEGACY_VERSION:
        if declaration["tasks"] != {}:
            raise ValueError("legacy contract has no descriptors")
        return None
    if type(declaration["tasks"]) is not dict or not declaration["tasks"]:
        raise ValueError("question contract tasks required")
    for tid, task in declaration["tasks"].items():
        text(tid)
        closed(task, ("questions",))
        if type(task["questions"]) is not dict or not task["questions"]:
            raise ValueError("question descriptors required")
        for pid, spec in task["questions"].items():
            text(pid)
            render(spec)
    return {"declaration": declaration, "sha256": digest(raw)}


def render(spec):
    closed(spec, ("core", "fields"))
    core = text(spec["core"])
    fields = spec["fields"]
    if type(fields) is not dict or not fields:
        raise ValueError("public fields required")
    required = {
        "status": ("kind", "scope", "point"), "missing_status": ("kind", "item_id"),
        "scalar": ("kind", "value_type", "point"), "set": ("kind", "value_type"),
        "source": ("kind",), "item": ("kind", "item_id"), "other": ("kind", "id_kind", "null_rule"),
    }
    for field, desc in fields.items():
        text(field)
        if type(desc) is not dict or desc.get("kind") not in KINDS:
            raise ValueError("unsupported public field kind")
        closed(desc, required[desc["kind"]])
        for value in desc.values():
            text(value)
        if desc["kind"] in ("scalar", "set") and desc["value_type"] not in ("integer", "string"):
            raise ValueError("explicit integer/string type required")
    missing = [f for f, d in fields.items() if d["kind"] == "missing_status"]
    items = [f for f, d in fields.items() if d["kind"] == "item"]
    if missing and (missing != ["status"] or any(d["kind"] == "status" for d in fields.values())):
        raise ValueError("designated missing status must be separate")
    if items and not missing:
        raise ValueError("item projection requires missing designation")
    blocks = [TEMPLATES["general"].replace("<field names>", ", ".join(fields))]
    for field, desc in fields.items():
        kind = desc["kind"]
        if kind == "status":
            slot = "ordinary"
            params = {"<status field>": field, "<entity, property, scope>": desc["scope"],
                      "<current point or named checkpoint>": desc["point"]}
        elif kind == "missing_status":
            slot = "missing"
            if any(fields[f]["item_id"] != desc["item_id"] for f in items):
                raise ValueError("missing item identity differs")
            params = {"<declared item ID>": desc["item_id"], "<identifier field, if requested>": ", ".join(items)}
        elif kind == "item":
            continue
        elif kind == "scalar":
            slot = "scalar"
            params = {"<scalar current/checkpoint field>": field, "<at the specified point>": desc["point"],
                      "<JSON integer or exact JSON string>": "a JSON integer" if desc["value_type"] == "integer" else "an exact JSON string"}
        elif kind == "set":
            slot = "set"
            params = {"<set field>": field, "<explicit member type and exact-text/number form>":
                      "a JSON integer, without quotes, decimals, or units" if desc["value_type"] == "integer" else
                      "an exact JSON string, preserving case, spelling, punctuation, and spacing"}
        elif kind == "source":
            slot, params = "source", {"<source field>": field}
        else:
            slot = "other"
            params = {"<other ID field>": field, "<message/item>": desc["id_kind"],
                      "<State this field's null condition explicitly, or state that null is not permitted.>": desc["null_rule"]}
        block = TEMPLATES[slot]
        if kind == "missing_status" and not items:
            block = block.split(" <identifier field, if requested>:")[0]
        for old, value in params.items():
            block = block.replace(old, value)
        if "<" in block or ">" in block:
            raise ValueError("unexpanded question slot")
        blocks.append(block)
    return core + "\n\n" + "\n\n".join(blocks)


def apply(loaded, item, manifest):
    """Validate descriptor coverage and render into an explicitly supplied copy.

    This helper performs no file writes or automatic execution integration.
    Expected objects and all non-question nodes remain unchanged.
    """
    release = loaded.get("question_contract")
    if release is None:
        return []
    declaration = release["declaration"]
    if set(declaration["tasks"]) != {t["id"] for t in loaded["tasks"]}:
        raise ValueError("question contract task coverage differs")
    questions = declaration["tasks"][item["id"]]["questions"]
    probes = {pid for pid, node in manifest["nodes"].items() if node["kind"] == "probe"}
    sidecar = unique_json(loaded["files"][item["sidecar"]])
    if set(questions) != probes:
        raise ValueError("question/retry coverage differs")
    prompts = []
    for pid, spec in questions.items():
        if set(spec["fields"]) != set(sidecar["probes"][pid]):
            raise ValueError("public field coverage differs")
        for field, desc in spec["fields"].items():
            query = sidecar["fields"][field]
            expected_kind = {"current": "scalar", "at-checkpoint": "scalar", "status": "status",
                             "values": "set", "provenance": "source"}.get(query["kind"])
            if query["kind"] == "missing_information":
                expected_kind = "missing_status" if query["projection"] == "status" else "item"
                if desc.get("item_id") != query["missing_item"]:
                    raise ValueError("declared missing item differs")
            if desc["kind"] != expected_kind:
                raise ValueError("field projection differs")
            if query["kind"] == "at-checkpoint" and desc["point"] != "just after public message " + query["checkpoint"]:
                raise ValueError("checkpoint differs")
        node = manifest["nodes"]["question:" + pid]
        value = render(spec)
        node.update(text=value, sha256=digest(value.encode("utf-8")))
        prompts.append({"task_id": item["id"], "question_id": pid, "sha256": node["sha256"]})
    return prompts
