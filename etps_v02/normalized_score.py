"""Pure normalized-score-v1 diagnostics. Never imported by strict scoring.

Callers declare ID and set fields from frozen metadata, not answer heuristics.
Only case/whitespace, surrounding ID wrappers and numeric-unit spelling fold.
"""
from decimal import Decimal, InvalidOperation
import re

from .set_answers import answer_object, equal

VERSION = "normalized-score-v1"
NUMBER_UNIT = re.compile(r"([+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s*([^\W\d_]+)")
WRAPPERS = {"[": "]", '"': '"', "'": "'"}


def fold(value):
    return " ".join(value.casefold().split())


def unwrap_id(value):
    value = value.strip()
    while len(value) >= 2 and value[0] in WRAPPERS and value[-1] == WRAPPERS[value[0]]:
        value = value[1:-1].strip()
    return value


def comparable(value, target, *, identifier=False):
    if type(value) is str:
        if type(target) is int:
            match = NUMBER_UNIT.fullmatch(value.strip())
            # Unicode word characters also include superscripts and fractions.
            if match and match[2].isalpha():
                try:
                    if Decimal(match[1]) == target:
                        return target
                except InvalidOperation:
                    pass
        if type(target) is str:
            return fold(unwrap_id(value) if identifier else value)
    return value


def set_equal(left, right, *, identifier=False):
    if len(left) != len(right):
        return False
    # Normalized duplicates cannot satisfy multiple different expected members.
    # Every pair is compared with the expected member's type; never coerce text
    # that happens to look numeric when the expected member is itself text.
    edges = [[i for i, target in enumerate(right)
              if type(comparable(value, target, identifier=identifier)) is type(target)
              and comparable(value, target, identifier=identifier) == target] for value in left]
    # Bipartite matching preserves complete-set semantics for mixed typed sets.
    matched = {}

    def assign(index, seen):
        for target in edges[index]:
            if target in seen:
                continue
            seen.add(target)
            if target not in matched or assign(matched[target], seen):
                matched[target] = index
                return True
        return False

    return all(assign(i, set()) for i in range(len(left)))


def normalized_score(answer, expected, *, id_fields=(), set_fields=()):
    """Return paired 0/1 exact-object scores, with no mutation or acceptance.

    expected uses typed-v1 scalars and explicitly designated complete-set arrays.
    Malformed answers score zero in both columns. Invalid declarations raise
    ValueError instead of inventing ID/set identity from values or key names.
    """
    for name, fields in (("id_fields", id_fields), ("set_fields", set_fields)):
        if (type(fields) not in (tuple, list) or not all(type(k) is str for k in fields)
                or len(set(fields)) != len(fields) or type(expected) is not dict
                or not set(fields) <= expected.keys()):
            raise ValueError(f"{name} must be unique expected field names")
    node = {"set_fields": set_fields}
    if not answer_object(expected, set_fields) or not all(type(k) is str and k for k in expected):
        raise ValueError("expected must be a typed-v1 object with declared set fields")
    for key in id_fields:
        values = expected[key] if key in set_fields else [expected[key]]
        if not all(value is None or type(value) is str for value in values):
            raise ValueError("ID fields must expect strings or null")
    if not equal(node, expected, expected):
        raise ValueError("expected sets must have unique typed members")
    report = {"version": VERSION, "diagnostic": True, "strict": 0, "normalized": 0,
              "id_fields": sorted(id_fields), "set_fields": sorted(set_fields)}
    if not answer_object(answer, set_fields) or answer.keys() != expected.keys():
        return report
    report["strict"] = int(equal(node, answer, expected))
    if report["strict"]:
        report["normalized"] = 1
        return report
    for key, target in expected.items():
        value, identifier = answer[key], key in id_fields
        if key in set_fields:
            # Even exact duplicates remain errors; normalization is not deduping.
            if len({(type(v), v) for v in value}) != len(value):
                return report
            targets = [fold(unwrap_id(v) if identifier else v) if type(v) is str else v for v in target]
            if len({(type(v), v) for v in targets}) != len(targets):
                return report
            if not set_equal(value, targets, identifier=identifier):
                return report
        else:
            target = fold(unwrap_id(target) if identifier else target) if type(target) is str else target
            value = comparable(value, target, identifier=identifier)
            if type(value) is not type(target) or value != target:
                return report
    report["normalized"] = 1
    return report
