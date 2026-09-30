"""Frozen d10-v1 answer rules. Never transforms delivered input bytes."""
import re

from .scorer import LEGACY_UNKNOWN_ANSWERS, answer_equal, classify, mapping, require

RULES = ("key_aliases", "digit_string_to_int", "fixed_value_fields")
ASCII_WHITESPACE = " \t\n\r\v\f"


def validate_probe(node):
    expected = node["expected"]
    aliases = mapping(node.get("key_aliases", {}), "key_aliases")
    require(aliases.keys() <= expected.keys(), "alias canonical field is absent")
    occupied = set(expected)
    for names in aliases.values():
        require(isinstance(names, list) and all(isinstance(n, str) and n for n in names),
                "aliases must be nonempty strings")
        for name in names:
            require(name not in occupied, "alias sets must be disjoint from aliases and canonical keys")
            occupied.add(name)
    fixed = node.get("fixed_value_fields", [])
    require(isinstance(fixed, list) and all(isinstance(k, str) for k in fixed)
            and len(fixed) == len(set(fixed)) and set(fixed) <= expected.keys(),
            "fixed_value_fields must be unique expected fields")
    require(all(type(expected[k]) is str for k in fixed), "fixed values must be strings")


def normalize(node, answer):
    """Return comparable copies and applied rules, or None on key collision."""
    expected = dict(node["expected"])
    result = dict(answer)
    applied = set()
    for canonical, aliases in node.get("key_aliases", {}).items():
        present = [key for key in [canonical, *aliases] if key in answer]
        if len(present) > 1:
            return None
        if present and present[0] != canonical:
            result[canonical] = result.pop(present[0])
            applied.add("key_aliases")
    for key, value in list(result.items()):
        target = expected.get(key)
        if type(target) is int and type(value) is str and re.fullmatch(r"[0-9]+", value):
            # Compare decimal spellings first to avoid Python's integer digit cap.
            if value.lstrip("0") == str(target) or (not value.lstrip("0") and target == 0):
                result[key] = target
                applied.add("digit_string_to_int")
        if key in node.get("fixed_value_fields", []) and type(value) is str and value != target:
            left = value.strip(ASCII_WHITESPACE).casefold()
            right = target.strip(ASCII_WHITESPACE).casefold()
            if left != value or right != target:
                applied.add("fixed_value_fields")
            result[key], expected[key] = left, right
    return result, expected, [rule for rule in RULES if rule in applied]


def evaluate(manifest, node, event):
    outcome = classify(event, node["expected"], node.get("unknown_answers", LEGACY_UNKNOWN_ANSWERS),
                       manifest.get("answer_schema"))
    if outcome == "correct":
        return outcome, "exact", []
    if outcome in {"timeout", "malformed"}:
        return outcome, None, []
    normalized = normalize(node, event["answer"])
    if normalized is None:
        return "incorrect", None, []
    answer, expected, rules = normalized
    if answer_equal(answer, expected):
        return "correct", "format_deviation", rules
    return outcome, None, []


def summary(results, planned):
    accepted = sum(r["accepted"] is True for r in results)
    exact = sum(r["accepted"] is True and r.get("result_state") == "accepted_exact" for r in results)
    return {"planned": planned, "attempted": len(results), "accepted": accepted,
            "acceptance_rate": {"numerator": accepted, "denominator": len(results)},
            "failed": sum(r["accepted"] is False for r in results),
            "unavailable": sum(r["accepted"] is None for r in results),
            "accepted_exact": exact, "accepted_with_format_deviation": accepted - exact,
            "format_compliance_rate": {"numerator": exact, "denominator": accepted},
            "rule_counts": {rule: sum(rule in label.get("rules_applied", [])
                                       for r in results for label in r["classifications"])
                            for rule in RULES}}
