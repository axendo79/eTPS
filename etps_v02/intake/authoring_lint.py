"""Advisory literal authoring-v1 checks. Findings never edit or refuse a task."""
import argparse
from collections import Counter
import re
import sys

from ..workload import encode, sha
from .authoring import MAX_BYTES
from .state_records import IntakeError, read_bounded
from ._review_support import document, field_sources, field_version, probe_context

VERSION = "authoring-lint-v1"
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


def lint_authoring(raw, *, window=2, status_phrases=None, question_phrases=None):
    if type(window) is not int or window < 0:
        raise IntakeError("lint_config", "window", "expected nonnegative integer")
    status_phrases = DEFAULT_STATUS_PHRASES if status_phrases is None else status_phrases
    question_phrases = DEFAULT_QUESTION_PHRASES if question_phrases is None else question_phrases
    for name, phrases in (("status_phrases", status_phrases), ("question_phrases", question_phrases)):
        if type(phrases) not in (list, tuple) or any(type(p) is not str or not p.strip() for p in phrases):
            raise IntakeError("lint_config", name, "expected nonempty literal phrases")
    doc, findings = document(raw), []

    def add(code, task, *, message=None, probe=None, evidence="", **facts):
        findings.append({"code": code, "level": "info" if code in ("evidence_position", "key_restatement_window_counts") else "advisory",
            "task_id": task["id"], "message_id": message, "probe_id": probe,
            "evidence": evidence, **facts})

    patterns = {}
    for task in doc["tasks"]:
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
        patterns[task["id"]] = sorted(set(styles + [prefix_pattern(task["id"])]))
        if len(styles) > 1:
            for kind, identity in identities:
                add("id_style_mixed", task, message=identity if kind == "message" else None,
                    probe=identity if kind == "probe" else None, record_id=identity if kind == "record" else None,
                    evidence=identity, scope="task", pattern=prefix_pattern(identity), patterns=styles)

        for probe in task["probes"]:
            context = probe_context(task, probe)
            messages = context[-window:] if window else []
            hits, exempt = 0, 0
            for field, query in sorted(probe["field_map"].items()):
                record, version = field_version(task, probe, query)
                if query["kind"] in ("status", "missing_information"):
                    allowed = set(record["status_labels"].values())
                    if query["kind"] == "missing_information":
                        allowed.add("missing_information")
                    missing = sorted(label for label in allowed if not word_match(probe["wording"], label))
                    if missing:
                        add("status_vocabulary_missing", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                            field=field, allowed_labels=sorted(allowed), missing_labels=missing)
                expected = probe["expected"][field]
                values = expected if field in probe["set_fields"] else [expected]
                for value in values:
                    # Exempt the selected version's establishing message and
                    # matching claim sources. Provenance IDs are always reported,
                    # including their public message prefixes, as requested.
                    sources = {version["message"]} if version else set()
                    if version:
                        sources.update(s["message"] for s in version["sources"] if normalized(s["value"]) == normalized(value))
                    for message in messages:
                        span = normalized_match(message["text"], value)
                        if not span:
                            continue
                        if query["kind"] != "provenance" and message["id"] in sources:
                            exempt += 1
                            continue
                        hits += 1
                        add("answer_restated_before_probe", task, message=message["id"], probe=probe["id"],
                            evidence=snippet(message["text"], span), field=field, expected_value=value,
                            kind=query["kind"], match_characters=list(span))
                if task["family"] == "F8" or task["coverage_tags"]["context_pressure"] == "over":
                    total = sum(len(m["text"]) for m in task["conversation"])
                    offsets, offset = {}, 0
                    for message in task["conversation"]:
                        offsets[message["id"]] = offset
                        offset += len(message["text"])
                    point = sum(len(m["text"]) for m in context) if context else None
                    sources = [{"message_id": m["id"], "start_character": offsets[m["id"]],
                        "end_character": offsets[m["id"]] + len(m["text"]),
                        "start_fraction": offsets[m["id"]] / total,
                        "characters_to_probe": point - offsets[m["id"]] if point is not None else None,
                        "evidence": snippet(m["text"])} for m in field_sources(task, probe, query)]
                    add("evidence_position", task, probe=probe["id"], evidence=snippet(probe["wording"]), field=field,
                        sources=sources, total_characters=total, probe_character=point,
                        position_basis="conversation_characters_plus_linked_corrections", kind=query["kind"])
            add("key_restatement_window_counts", task, probe=probe["id"], evidence=snippet(probe["wording"]),
                window_message_ids=[m["id"] for m in messages], window_messages=len(messages),
                restatement_hits=hits, establishing_source_hits_exempted=exempt)
    all_patterns = sorted({p for styles in patterns.values() for p in styles})
    if len(all_patterns) > 1:
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
    parser.add_argument("--window", type=int, default=2, help="preceding delivered messages, including the position message (default: 2)")
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
