"""Opt-in set-v1 predicate: complete sets of exact typed-v1 scalars."""
from .scorer import LEGACY_UNKNOWN_ANSWERS, answer_equal, mapping, require


def scalar(value):
    return type(value) in (str, int, type(None))


def answer_object(answer, fields):
    return isinstance(answer, dict) and all(
        isinstance(key, str) and
        (type(value) is list and all(scalar(v) for v in value)
         if key in fields else scalar(value))
        for key, value in answer.items())


def element_keys(values):
    # Types are part of identity; 7, "7" and null remain distinct.
    return {(type(value), value) for value in values}


def field_equal(node, key, left, right):
    if key not in node.get("set_fields", []):
        return answer_equal({key: left}, {key: right})
    if (type(left) is not list or type(right) is not list
            or not all(scalar(v) for v in left + right)):
        return False
    a, b = element_keys(left), element_keys(right)
    return len(a) == len(left) and len(b) == len(right) and a == b


def equal(node, left, right):
    return left.keys() == right.keys() and all(field_equal(node, k, left[k], right[k]) for k in left)


def projection_fields(manifest, node):
    """Canonical set names and declared d10 key aliases; no element tolerance."""
    if manifest.get("answer_predicate") != "set-v1":
        return ()
    fields = list(node.get("set_fields", []))
    if manifest.get("answer_tolerance") == "d10-v1":
        fields += [alias for key in node.get("set_fields", [])
                   for alias in node.get("key_aliases", {}).get(key, [])]
    return fields


def validate_probe(manifest, node):
    fields = node.get("set_fields", [])
    require(isinstance(fields, list) and all(isinstance(k, str) for k in fields)
            and len(fields) == len(set(fields)) and set(fields) <= node["expected"].keys(),
            "set_fields must be unique expected fields")
    require(answer_object(node["expected"], projection_fields(manifest, node)),
            "set-v1 requires arrays of typed-v1 scalars")
    require(all(len(element_keys(node["expected"][k])) == len(node["expected"][k]) for k in fields),
            "duplicate expected set element")


def comparable(manifest, node, answer):
    if manifest.get("answer_tolerance") == "d10-v1":
        from .answer_tolerance import normalize
        return normalize(node, answer)
    return answer, node["expected"], []


def evaluate(manifest, node, event):
    mapping(event, "event", ("status",))
    require(isinstance(event["status"], str) and event["status"] in {"ok", "timeout"},
            "event.status: unknown transport status")
    if event["status"] == "timeout":
        return "timeout", None, []
    answer = event.get("answer")
    if not answer_object(answer, projection_fields(manifest, node)):
        return "malformed", None, []
    if equal(node, answer, node["expected"]):
        return "correct", "exact", []
    unknown = any(answer_equal(answer, a) for a in node.get("unknown_answers", LEGACY_UNKNOWN_ANSWERS))
    normalized = comparable(manifest, node, answer)
    if normalized is None:
        return "incorrect", None, []
    result, expected, rules = normalized
    if equal(node, result, expected):
        return "correct", "format_deviation", rules
    return "unknown" if unknown else "incorrect", None, []
