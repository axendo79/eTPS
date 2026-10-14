"""Advisory literal authoring-v1 checks. Findings never edit or refuse a task."""
import argparse
from collections import Counter
import re
import sys

from ..workload import encode, sha
from .authoring import BRIEF_V2, MAX_BYTES, exact_answer
from .state_records import IntakeError, read_bounded
from ._review_support import document, field_sources, field_version, probe_context

VERSION = "authoring-lint-v2"
DEFAULT_STATUS_PHRASES = ("expires here", "new active version", "fresh version", "status label")
DEFAULT_QUESTION_PHRASES = ("the question that follows", "the next question", "the following question",
    "the upcoming question", "the subsequent question", "the question below", "the question to follow")


def normalized(value):
    text = "null" if value is None else str(value)
    return "".join(text.casefold().split())


def normalized_match(text, value):
    # Preserve an index for casefold expansions and whitespace removal, so the
    # evidence snippet always comes from the unchanged original message.
    compact, indices = [], []
    for i, char in enumerate(text):
        if not char.isspace():
            folded = char.casefold()
            compact.extend(folded)
            indices.extend([i] * len(folded))
    needle = normalized(value)
    start = "".join(compact).find(needle) if needle else -1
    return (indices[start], indices[start + len(needle) - 1] + 1) if start >= 0 else None


def word_match(text, phrase):
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"(?!\w)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.span() if match else None


def snippet(text, span=None):
    start = max(0, span[0] - 60) if span else 0
    return text[start:start + 240]


def prefix_pattern(identifier):
    # A prefix is the portion before the final separator-delimited ID component.
    # Digit runs in it are placeholders, so task1-m1 and task2-p2 share a style.
    match = re.match(r"^(.*[-_.])[^-_.]+$", identifier)
    return re.sub(r"\d+", "#", match[1]) + "<suffix>" if match else "<unprefixed>"


def field_clauses(wording, field, fields):
    """Literal field-scoped clauses, not a natural-language interpretation."""
    names = "|".join(re.escape(name) for name in sorted(fields, key=lambda n: (-len(n), n)))
    clauses = re.split(r"[.;!?\n]+|(?=\b(?:For|Return|Report|Provide|Give)\s+(?:field\s+)?(?:"
                       + names + r")(?!\w))", wording)
    return [clause for clause in clauses if word_match(clause, field)]


def missing_answer_forms(probe, field, query, record):
    expected = probe["expected"][field]
    is_set = field in probe["set_fields"]
    values = expected if is_set else [expected]
    status = query["kind"] == "status" or (query["kind"] == "missing_information" and query["projection"] == "status")
    identifier = query["kind"] == "provenance" or (query["kind"] == "missing_information" and query["projection"] == "identifier")
    forms = set()
    if is_set:
        forms.add("array")
        if not values:
            forms.add("empty_array_when_none")
    for value in values:
        forms.add("null_when_none" if value is None else "status_words" if status else
                  "bare_id" if identifier else "number" if type(value) is int else "exact_text")
    labels = set(record["status_labels"].values())
    if query["kind"] == "missing_information" and status:
        labels.add("missing_information")
    clauses = field_clauses(probe["wording"], field, probe["field_map"])

    def states(clause, form):
        if form == "number":
            return bool(re.search(r"\bbare\s+JSON\s+numbers?\b", clause, re.I))
        if form == "exact_text":
            return bool(re.search(r"\bexact(?:ly)?\b", clause, re.I) and
                        re.search(r"\b(?:text|written|conversation)\b", clause, re.I))
        if form == "bare_id":
            return bool(re.search(r"\bbare\s+(?:IDs?|identifiers?)\b", clause, re.I))
        if form == "status_words":
            return bool(re.search(r"\b(?:allowed|one\s+of)\b", clause, re.I)) and all(word_match(clause, label) for label in labels)
        none = bool(re.search(r"\b(?:nothing\s+applies|none|no\s+(?:values?|items?|sources?|information)\s+(?:appl(?:y|ies)|exists?)|never\s+set|cancelled|canceled)\b", clause, re.I))
        if form == "null_when_none":
            return bool(word_match(clause, "null")) and none
        if form == "array":
            return bool(word_match(clause, "array"))
        return bool(word_match(clause, "empty") and word_match(clause, "array")) and none

    return sorted(form for form in forms if not any(states(clause, form) for clause in clauses))


def lint_authoring(raw, *, window=None, status_phrases=None, question_phrases=None):
    if window is not None and (type(window) is not int or window < 0):
        raise IntakeError("lint_config", "window", "expected nonnegative integer")
    doc, findings = document(raw), []
    v2 = doc["brief_version"] == BRIEF_V2
    window = (3 if v2 else 2) if window is None else window
    status_phrases = DEFAULT_STATUS_PHRASES + (("never established",) if v2 else ()) if status_phrases is None else status_phrases
    question_phrases = DEFAULT_QUESTION_PHRASES if question_phrases is None else question_phrases
    for name, phrases in (("status_phrases", status_phrases), ("question_phrases", question_phrases)):
        if type(phrases) not in (list, tuple) or any(type(p) is not str or not p.strip() for p in phrases):
            raise IntakeError("lint_config", name, "expected nonempty literal phrases")

    def add(code, task, *, message=None, probe=None, evidence="", **facts):
        findings.append({"code": code, "level": "info" if code in ("evidence_position", "key_restatement_window_counts") else "advisory",
            "task_id": task["id"], "message_id": message, "probe_id": probe,
            "evidence": evidence, **facts})

    patterns = {}
    for task in doc["tasks"]:
        correction_ids = {r["id"] for r in task["recoveries"]}
        labels = {v for r in task["state_history"] for v in r["status_labels"].values()}
        for message in task["conversation"]:
            for phrase in sorted(labels | set(status_phrases)):
                span = word_match(message["text"], phrase)
                if span:
                    add("status_word_leak", task, message=message["id"], evidence=snippet(message["text"], span), matched=phrase)
            for phrase in sorted(set(question_phrases)):
                span = word_match(message["text"], phrase)
                if span:
                    add("question_reference_in_filler", task, message=message["id"], evidence=snippet(message["text"], span), matched=phrase)
        identities = [("message", m["id"]) for m in task["conversation"]]
        identities += [("probe", p["id"]) for p in task["probes"]]
        identities += [("record", r["id"]) for r in task["state_history"]]
        styles = sorted({prefix_pattern(i) for _, i in identities})
        # A separatorless task ID (d1t01) has no prefix style of its own, so it
        # must not register as a competing "<unprefixed>" style.
        own = prefix_pattern(task["id"])
        patterns[task["id"]] = sorted(set(styles + ([own] if own != "<unprefixed>" else [])))
        if len(styles) > 1:
            for kind, identity in identities:
                add("id_style_mixed", task, message=identity if kind == "message" else None,
                    probe=identity if kind == "probe" else None, record_id=identity if kind == "record" else None,
                    evidence=identity, scope="task", pattern=prefix_pattern(identity), patterns=styles)

        for probe in task["probes"]:
            context = probe_context(task, probe)
            messages = context[-window:] if window else []
            # Corrections still occupy delivered-message positions, but rule 6
            # exempts their text. Do not extend the window to earlier messages.
            if v2:
                messages = [m for m in messages if m["id"] not in correction_ids]
            hits, exempt = 0, 0
            for field, query in sorted(probe["field_map"].items()):
                record, version = field_version(task, probe, query)
                is_status = query["kind"] == "status" or (query["kind"] == "missing_information" and query["projection"] == "status")
                if is_status:
                    allowed = set(record["status_labels"].values())
                    if query["kind"] == "missing_information":
                        allowed.add("missing_information")
                    missing = sorted(label for label in allowed if not word_match(probe["wording"], label))
                    if missing:
                        add("status_vocabulary_missing", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                            field=field, allowed_labels=sorted(allowed), missing_labels=missing)
                missing_forms = missing_answer_forms(probe, field, query, record)
                if missing_forms:
                    add("answer_form_missing", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                        field=field, kind=query["kind"], missing_forms=missing_forms)
                if v2 and query["kind"] == "missing_information" and not word_match(probe["wording"], query["missing_item"]):
                    add("missing_item_not_named", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                        field=field, missing_item=query["missing_item"])
                expected = probe["expected"][field]
                if v2 and query["kind"] == "values":
                    in_force = ([] if version is None or version["status"] == "expired" else
                                [version["value"]] if version["status"] == "active" else
                                [s["value"] for s in version["sources"]])
                    if not exact_answer({field: expected}, {field: in_force}, [field]):
                        add("values_not_in_force", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                            field=field, expected_values=expected, declared_values_in_force=in_force)
                values = expected if field in probe["set_fields"] else [expected]
                for value in values:
                    # V1 keeps establishment/matching-source exemptions. V2
                    # reports those hits too; provenance IDs are always reported.
                    sources = {version["message"]} if version else set()
                    if version:
                        sources.update(s["message"] for s in version["sources"] if normalized(s["value"]) == normalized(value))
                    for message in messages:
                        span = normalized_match(message["text"], value)
                        if not span:
                            continue
                        if not v2 and query["kind"] != "provenance" and message["id"] in sources:
                            exempt += 1
                            continue
                        hits += 1
                        add("answer_restated_before_probe", task, message=message["id"], probe=probe["id"],
                            evidence=snippet(message["text"], span), field=field, expected_value=value,
                            kind=query["kind"], match_characters=list(span))
                if v2 and query["kind"] != "provenance":
                    for source in field_sources(task, probe, query):
                        for message in messages:
                            span = normalized_match(message["text"], source["id"])
                            if span:
                                hits += 1
                                add("answer_restated_before_probe", task, message=message["id"], probe=probe["id"],
                                    evidence=snippet(message["text"], span), field=field, expected_value=source["id"],
                                    kind=query["kind"], restatement="source_id", match_characters=list(span))
                if task["family"] == "F8" or task["coverage_tags"]["context_pressure"] == "over":
                    total = sum(len(m["text"]) for m in task["conversation"])
                    positions = {m["id"]: i for i, m in enumerate(task["conversation"])}
                    first_tenth = (len(task["conversation"]) + 9) // 10
                    offsets, offset = {}, 0
                    for message in task["conversation"]:
                        offsets[message["id"]] = offset
                        offset += len(message["text"])
                    point = sum(len(m["text"]) for m in context) if context else None
                    sources = [{"message_id": m["id"], "start_character": offsets[m["id"]],
                        **({"message_index": positions[m["id"]], "message_position": positions[m["id"]] + 1} if v2 else {}),
                        "end_character": offsets[m["id"]] + len(m["text"]),
                        "start_fraction": offsets[m["id"]] / total,
                        "characters_to_probe": point - offsets[m["id"]] if point is not None else None,
                        "evidence": snippet(m["text"])} for m in field_sources(task, probe, query)]
                    add("evidence_position", task, probe=probe["id"], evidence=snippet(probe["wording"]), field=field,
                        sources=sources, total_characters=total, probe_character=point,
                        position_basis="conversation_message_position" if v2 else "conversation_characters_plus_linked_corrections",
                        **({"total_messages": len(task["conversation"]), "first_tenth_messages": first_tenth,
                            "character_position_basis": "conversation_characters_plus_linked_corrections"} if v2 else {}),
                        kind=query["kind"])
                    if v2 and task["coverage_tags"]["context_pressure"] == "over":
                        outside = [s["message_id"] for s in sources if s["message_position"] > first_tenth]
                        if outside:
                            add("evidence_outside_first_tenth", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                                field=field, source_message_ids=outside, basis="conversation_message_position")
            add("key_restatement_window_counts", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                window_message_ids=[m["id"] for m in messages], window_messages=len(messages),
                restatement_hits=hits, establishing_source_hits_exempted=exempt)
        if v2:
            add("context_pressure_unverified", task, evidence=task["coverage_tags"]["context_pressure"],
                messages=len(task["conversation"]), characters=sum(len(m["text"]) for m in task["conversation"]),
                required_budget_fraction="<0.5" if task["coverage_tags"]["context_pressure"] == "within" else ">=1.5",
                detail="Authoring format has no token budget/counter receipt; maintainer must verify sizes with the token counter at freeze and record them in settings.json.")
    all_patterns = sorted({p for styles in patterns.values() for p in styles})
    if not v2 and len(all_patterns) > 1:
        for task in doc["tasks"]:
            add("id_style_mixed", task, probe=task["probes"][0]["id"], evidence=task["id"], record_id=None,
                scope="document", patterns=all_patterns, task_patterns=patterns[task["id"]])
    findings.sort(key=lambda f: (f["task_id"], f["code"], f["probe_id"] or "", f["message_id"] or "", encode(f)))
    return {"version": VERSION, "source_sha256": sha(raw), "advisory": True, "semantics_verified": False,
        "tasks": len(doc["tasks"]), "config": {"window": window, "status_phrases": sorted(set(status_phrases)),
            "question_phrases": sorted(set(question_phrases))}, "findings": findings,
        "counts": dict(sorted(Counter(f["code"] for f in findings).items()))}


def report_bytes(raw, **options):
    return encode(lint_authoring(raw, **options))


def add_options(parser):
    parser.add_argument("--window", type=int, default=None, help="preceding delivered messages, including the position message (default: v1=2, v2=3)")
    parser.add_argument("--status-phrase", action="append", dest="status_phrases", help="replace default annotation phrases; repeat for each literal phrase")
    parser.add_argument("--question-phrase", action="append", dest="question_phrases", help="replace default question-reference phrases; repeat for each literal phrase")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    add_options(parser)
    args = parser.parse_args()
    try:
        result = lint_authoring(read_bounded(args.source, MAX_BYTES), window=args.window,
            status_phrases=args.status_phrases, question_phrases=args.question_phrases)
    except IntakeError as exc:
        sys.stdout.buffer.write(encode({"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}) + b"\n")
        return 2
    sys.stdout.buffer.write(encode(result) + b"\n")
    summary = ", ".join(f"{code}={count}" for code, count in result["counts"].items()) or "no findings"
    print(f"advisory: {result['tasks']} task(s); {summary}; semantics unverified", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
