"""Strict, neutral authoring-v1 admission. Separate from scoring and replay."""
import argparse
import json

from ..scorer import InvalidRecord, OUTCOMES, boundaries
from ..set_answers import scalar
from ..dimension_accuracy import DIMENSIONS
from ..workload import decode, encode, sha
from .state_records import IntakeError, read_bounded

VERSION = "authoring-v1"
BRIEF_VERSION = "authoring-brief-v1"
MAX_BYTES = 8 * 1024 * 1024
MAX_TASKS = 256
MAX_ITEMS = 4096
FIELDS = {
    "root": ("version", "brief_version", "dataset", "tasks"),
    "task": ("id", "family", "coverage_tags", "conversation", "field_map", "probes", "state_history", "recoveries", "predictions"),
    "coverage": ("chain_depth", "distance", "entity_similarity", "ambiguity_status", "provenance_need", "context_pressure", "verbatim_possible", "subcases"),
    "message": ("id", "text", "recap"),
    "field": ("dimension", "record", "kind", "checkpoint"),
    "field_missing": ("dimension", "record", "kind", "missing_item", "projection"),
    "probe": ("id", "position", "wording", "field_map", "expected", "set_fields", "unknown_answers", "alternative_answers", "requirements", "outcomes"),
    "record": ("id", "entity", "property", "scope", "status_labels", "versions"),
    "version": ("id", "message", "change", "status", "value", "sources", "time", "applicability", "requirements"),
    "source": ("message", "authority", "value"),
    "requirement": ("id", "kind", "begin_after", "end_before"),
    "recovery": ("id", "failure_probes", "text", "spans", "new_spans", "retry"),
    "prediction": ("arm", "failing", "reason"),
}
STATUSES = ("active", "expired", "unresolved", "unestablished")
KINDS = ("current", "at-checkpoint", "status", "values", "provenance", "clarification", "missing_information")
CHANGES = ("establish", "change", "lapse", "reinstate", "precedence")
SUBCASES = ("partial", "scoped", "negation", "retraction", "reinstatement", "revisit")


class AuthoringError(IntakeError):
    pass


def need(condition, code, path, detail):
    if not condition:
        raise AuthoringError(code, path, detail)


def closed(value, keys, path):
    need(type(value) is dict, "field_type", path, "expected object")
    need(set(keys) <= value.keys(), "required_fields", path, "required fields missing")
    need(value.keys() <= set(keys), "closed_fields", path, "unknown fields")


def string(value, path, *, identifier=False, nullable=False):
    need(nullable and value is None or type(value) is str and bool(value), "field_type", path, "expected nonempty string")
    if identifier and value is not None:
        need(not value.startswith("$") and ":" not in value, "field_type", path, "reserved ID")


def enum(value, choices, path, code="field_type"):
    need(type(value) is str and value in choices, code, path, "unsupported value")


def array(value, path, *, nonempty=False):
    need(type(value) is list and (not nonempty or bool(value)), "field_type", path, "expected array")
    need(len(value) <= MAX_ITEMS, "safety_limit", path, "array admission ceiling")


def unique_strings(value, path):
    array(value, path)
    for item in value:
        string(item, path)
    need(len(value) == len(set(value)), "duplicate_id", path, "duplicate member")


def scalar_value(value, path):
    need(scalar(value), "field_type", path, "expected string, integer or null")


def answer(value, sets, path):
    need(type(value) is dict and all(type(k) is str and k for k in value), "answer_shape", path, "expected answer object")
    for key, val in value.items():
        if key in sets:
            need(type(val) is list, "answer_shape", path, "expected scalar set array")
            need(len(val) <= MAX_ITEMS, "safety_limit", path, "array admission ceiling")
            need(all(scalar(v) for v in val), "answer_shape", path, "expected scalar set array")
            need(len(val) == len({(type(v).__name__, v) for v in val}), "answer_shape", path, "duplicate set element")
        else:
            need(scalar(val), "answer_shape", path, "expected scalar field")


def exact_answer(left, right, sets):
    if left.keys() != right.keys():
        return False
    for key in left:
        if key in sets:
            if {(type(v).__name__, v) for v in left[key]} != {(type(v).__name__, v) for v in right[key]}:
                return False
        elif type(left[key]) is not type(right[key]) or left[key] != right[key]:
            return False
    return True


def field_map(value, path):
    need(type(value) is dict and bool(value), "field_type", path, "expected nonempty field map")
    for name, item in value.items():
        string(name, path)
        need(type(item) is dict, "field_type", path + "." + name, "expected field object")
        missing = item.get("kind") == "missing_information"
        closed(item, FIELDS["field_missing" if missing else "field"], path + "." + name)
        enum(item["dimension"], DIMENSIONS, path)
        string(item["record"], path)
        enum(item["kind"], KINDS, path)
        if missing:
            string(item["missing_item"], path)
            enum(item["projection"], ("status", "identifier"), path)
        else:
            string(item["checkpoint"], path, nullable=item["kind"] != "at-checkpoint")
            need(item["kind"] == "at-checkpoint" or item["checkpoint"] is None, "field_map", path, "unexpected checkpoint")


def validate_task(task, path):
    closed(task, FIELDS["task"], path)
    string(task["id"], path + ".id", identifier=True)
    enum(task["family"], tuple("F" + str(i) for i in range(1, 10)), path + ".family")
    coverage = task["coverage_tags"]
    closed(coverage, FIELDS["coverage"], path + ".coverage_tags")
    for key in ("chain_depth", "distance"):
        need(type(coverage[key]) is int and coverage[key] >= 0, "coverage_tag", path, "expected nonnegative count")
    for key, choices in (("entity_similarity", ("distinct", "similar")), ("ambiguity_status", STATUSES + ("resolved",)),
                         ("provenance_need", ("needed", "none")), ("context_pressure", ("within", "over"))):
        enum(coverage[key], choices, path + ".coverage_tags." + key, "coverage_tag")
    need(type(coverage["verbatim_possible"]) is bool, "coverage_tag", path, "expected boolean")
    unique_strings(coverage["subcases"], path)
    for subcase in coverage["subcases"]:
        enum(subcase, SUBCASES, path, "coverage_tag")
    for key in ("conversation", "probes", "state_history", "recoveries", "predictions"):
        array(task[key], path + "." + key, nonempty=key in ("conversation", "probes", "state_history"))
    events, messages, probes, recoveries = {}, {}, {}, {}
    for key, shape, target in (("conversation", "message", messages), ("probes", "probe", probes), ("recoveries", "recovery", recoveries)):
        for i, item in enumerate(task[key]):
            ip = f"{path}.{key}[{i}]"
            closed(item, FIELDS[shape], ip)
            string(item["id"], ip, identifier=True)
            need(item["id"] not in events, "duplicate_id", ip, "duplicate event ID")
            events[item["id"]] = item
            target[item["id"]] = item
            text_key = "wording" if key == "probes" else "text"
            string(item[text_key], ip)
            need(item[text_key].startswith("[" + item["id"] + "] "), "public_identifier", ip, "public text must start with its ID")
            if key == "conversation":
                need(type(item["recap"]) is bool, "field_type", ip, "recap must be boolean")
    order = {mid: i for i, mid in enumerate(messages)}
    record_ids, state_ids, requirement_ids = set(), set(), set()
    for i, record in enumerate(task["state_history"]):
        rp = f"{path}.state_history[{i}]"
        closed(record, FIELDS["record"], rp)
        for key in ("id", "entity", "property", "scope"):
            string(record[key], rp, identifier=key == "id")
        need(record["id"] not in state_ids, "duplicate_id", rp, "duplicate proposition ID")
        state_ids.add(record["id"])
        record_ids.add(record["id"])
        closed(record["status_labels"], STATUSES, rp)
        for value in record["status_labels"].values():
            string(value, rp)
        array(record["versions"], rp)
        prior_order = -1
        for j, version in enumerate(record["versions"]):
            vp = f"{rp}.versions[{j}]"
            closed(version, FIELDS["version"], vp)
            for key in ("id", "message", "applicability"):
                string(version[key], vp, identifier=key == "id")
            need(version["id"] not in state_ids, "duplicate_id", vp, "duplicate version ID")
            state_ids.add(version["id"])
            need(version["message"] in messages, "reference", vp, "version message absent")
            need(order[version["message"]] > prior_order, "history_order", vp, "versions must advance in conversation order")
            prior_order = order[version["message"]]
            enum(version["change"], CHANGES, vp)
            enum(version["status"], STATUSES[:3], vp)
            scalar_value(version["value"], vp)
            closed(version["time"], ("begin", "end"), vp)
            for value in version["time"].values():
                string(value, vp, nullable=True)
            array(version["sources"], vp)
            for source in version["sources"]:
                closed(source, FIELDS["source"], vp)
                string(source["message"], vp)
                string(source["authority"], vp)
                scalar_value(source["value"], vp)
                need(source["message"] in messages and order[source["message"]] <= prior_order,
                     "reference", vp, "source must precede establishment")
            array(version["requirements"], vp)
            for req in version["requirements"]:
                closed(req, FIELDS["requirement"], vp)
                string(req["id"], vp, identifier=True)
                need(req["id"] not in requirement_ids, "duplicate_id", vp, "duplicate requirement ID")
                requirement_ids.add(req["id"])
                enum(req["kind"], ("current", "historical"), vp)
                for key in ("begin_after", "end_before"):
                    string(req[key], vp)
                    need(req[key] in messages or key == "end_before" and req[key] == "$trial_end",
                         "reference", vp, "requirement boundary absent")
                need(req["begin_after"] == version["message"], "delayed_obligation", vp + ".requirements",
                     "maintainer ruling 1: every requirement begins at its establishing message")
    field_map(task["field_map"], path + ".field_map")
    for query in task["field_map"].values():
        need(query["record"] in record_ids, "reference", path, "field proposition absent")
        if query["kind"] == "missing_information":
            need(query["missing_item"] in record_ids, "reference", path, "missing item must reference a declared proposition")
        else:
            need(query["checkpoint"] is None or query["checkpoint"] in messages, "reference", path, "checkpoint absent")
    for pid, probe in probes.items():
        pp = path + ".probes." + pid
        string(probe["position"], pp)
        need(probe["position"] in messages or probe["position"] in recoveries, "position", pp, "question position absent")
        field_map(probe["field_map"], pp)
        need(all(name in task["field_map"] and query == task["field_map"][name] for name, query in probe["field_map"].items()),
             "field_map", pp, "question redefines frozen fields")
        unique_strings(probe["set_fields"], pp)
        need(set(probe["set_fields"]) <= probe["field_map"].keys(), "answer_shape", pp, "set field absent")
        need(all((name in probe["set_fields"]) == (query["kind"] == "values") for name, query in probe["field_map"].items()),
             "answer_shape", pp, "values queries require set designation; scalar queries cannot be sets")
        answer(probe["expected"], probe["set_fields"], pp)
        need(probe["expected"].keys() == probe["field_map"].keys(), "field_map", pp, "expected keys differ from map")
        for key in ("unknown_answers", "alternative_answers"):
            array(probe[key], pp)
            if key == "alternative_answers":
                need(not probe[key], "alternative_answers", pp + ".alternative_answers",
                     "maintainer ruling 3: one canonical answer object per question")
            for item in probe[key]:
                answer(item, probe["set_fields"], pp)
        missing = {name: q for name, q in probe["field_map"].items() if q["kind"] == "missing_information"}
        if missing:
            status = missing.get("status")
            need(status is not None and status["projection"] == "status" and probe["expected"]["status"] == "missing_information",
                 "missing_information_answer", pp, "exact status field missing_information required")
            pair = (status["record"], status["missing_item"])
            for name, query in missing.items():
                need((query["record"], query["missing_item"]) == pair and
                     (name == "status" if query["projection"] == "status" else
                      probe["expected"][name] == query["missing_item"]), "missing_information_answer", pp,
                     "identifier fields must exactly name the same declared missing item")
        for item in probe["unknown_answers"]:
            need(not any(exact_answer(item, expected, probe["set_fields"]) for expected in [probe["expected"]] + probe["alternative_answers"]),
                 "unknown_overlap", pp, "unknown overlaps correct answer")
        unique_strings(probe["requirements"], pp)
        need(set(probe["requirements"]) <= requirement_ids, "reference", pp, "tested requirement absent")
        closed(probe["outcomes"], OUTCOMES, pp)
        for outcome, target in probe["outcomes"].items():
            string(target, pp)
            need(target == "$continue" if outcome == "correct" else target == "$reject" or target in recoveries,
                 "route", pp, "unsupported outcome route")
    for rid, recovery in recoveries.items():
        rp = path + ".recoveries." + rid
        unique_strings(recovery["failure_probes"], rp)
        need(len(recovery["failure_probes"]) == 1, "multi_failure_recovery", rp + ".failure_probes",
             "maintainer ruling 2: one correction maps to exactly one failed question")
        need(bool(recovery["failure_probes"]) and set(recovery["failure_probes"]) <= probes.keys(), "reference", rp, "failure question absent")
        string(recovery["retry"], rp)
        need(recovery["retry"] in probes and probes[recovery["retry"]]["position"] == rid, "position", rp, "retry must follow correction")
        need([p for p in probes if probes[p]["position"] == rid] == [recovery["retry"]], "position", rp, "correction must have exactly one retry")
        routed = {pid for pid, p in probes.items() if rid in p["outcomes"].values()}
        need(routed == set(recovery["failure_probes"]), "route", rp, "failure links differ from outcome routes")
        raw, aligned = boundaries(recovery["text"])
        for key, width in (("spans", 3), ("new_spans", 2)):
            array(recovery[key], rp)
            for span in recovery[key]:
                need(type(span) is list and len(span) == width and all(type(v) is int for v in span[:2]), "span", rp, "invalid byte span shape")
                begin, end = span[:2]
                need(0 <= begin < end <= len(raw) and begin in aligned and end in aligned, "span", rp, "span must align with UTF-8 bytes")
                if width == 3:
                    need(type(span[2]) is str and span[2] in requirement_ids, "reference", rp, "span requirement absent")
        need(bool(recovery["spans"]), "span", rp, "correction requires a designated repeated-fact span")
        need(not any(max(a, c) < min(b, d) for a, b, _ in recovery["spans"] for c, d in recovery["new_spans"]),
             "span", rp, "new content overlaps repeated facts")
    for probe in probes.values():
        if probe["position"] in recoveries:
            need(recoveries[probe["position"]]["retry"] == probe["id"], "position", path, "unattached retry")
    arms = []
    for prediction in task["predictions"]:
        closed(prediction, FIELDS["prediction"], path)
        enum(prediction["arm"], tuple("ABCDEF"), path, "prediction")
        need(prediction["failing"] is None or type(prediction["failing"]) is bool, "prediction", path, "expected boolean or null prediction")
        string(prediction["reason"], path)
        arms.append(prediction["arm"])
    need(sorted(arms) == list("ABCDEF"), "prediction", path, "exactly one prediction per anonymous condition required")


def validate_authoring(raw):
    need(type(raw) is bytes, "invalid_json", "source", "expected exact UTF-8 bytes")
    need(len(raw) <= MAX_BYTES, "safety_limit", "source", "source byte admission ceiling")
    try:
        document = decode(raw)
        encode(document)
    except InvalidRecord as exc:
        raise AuthoringError("invalid_json", "source", str(exc)) from exc
    closed(document, FIELDS["root"], "source")
    need(document["version"] == VERSION, "format_version", "source.version", "unsupported authoring format")
    need(document["brief_version"] == BRIEF_VERSION, "brief_version", "source.brief_version", "unsupported brief")
    enum(document["dataset"], ("development", "evaluation"), "source.dataset")
    array(document["tasks"], "source.tasks", nonempty=True)
    need(len(document["tasks"]) <= MAX_TASKS, "safety_limit", "source.tasks", "task admission ceiling")
    ids = set()
    for i, task in enumerate(document["tasks"]):
        validate_task(task, f"source.tasks[{i}]")
        need(task["id"] not in ids, "duplicate_id", "source.tasks", "duplicate task ID")
        ids.add(task["id"])
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    try:
        raw = read_bounded(args.source, MAX_BYTES)
        document = validate_authoring(raw)
        result = {"version": VERSION, "status": "validated", "sha256": sha(raw),
                  "tasks": len(document["tasks"]), "dataset": document["dataset"], "semantics_verified": False}
    except IntakeError as exc:
        result = {"version": VERSION, "status": "rejected", "code": exc.code, "path": exc.path, "detail": exc.detail}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
