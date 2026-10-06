"""Diagnostic field counts only, with synthetic planned-slot and replay evidence."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, report, run_offline
from etps_v02.scorer import InvalidRecord, digest, score, validate
from etps_v02.workload import encode
from test_v02_runner import bundle, response
from test_v02_set_ambiguity import ambiguity_manifest, trace
from test_v02_set_answers import set_manifest


def dimensions(m=None):
    m = ambiguity_manifest() if m is None else m
    for node in m["nodes"].values():
        if node["kind"] == "probe":
            node["field_dimensions"] = {key: "ambiguity" for key in node["expected"]}
    return m


class DimensionAccuracyTests(unittest.TestCase):
    def check(self, result, phase, correct, planned=2, **reasons):
        metric = result["dimension_accuracy"][phase]["ambiguity"]
        self.assertEqual(metric["correct"], correct)
        self.assertEqual(metric["planned"], planned)
        self.assertEqual(metric["accuracy"], Fraction(correct, planned))
        self.assertEqual(metric["reason_counts"], {key: reasons.get(key, 0) for key in
                         ("incorrect", "unknown", "malformed", "unattempted", "unavailable")})

    def test_first_and_terminal_separate_complete_set_units(self):
        m = dimensions()
        result = score(m, trace(m, [{"status": "unresolved", "values": ["alpha"]},
                                   {"status": "unresolved", "values": ["beta", "alpha"]}]))
        self.check(result, "first_attempt", 1, incorrect=1)
        self.check(result, "terminal", 2)
        self.assertEqual(result["dimension_accuracy"]["first_fields"], {"status": "correct", "values": "incorrect"})

    def test_all_tags_exact_scalar_and_set_counts(self):
        tags = ("current", "historical", "expired", "ambiguity", "provenance", "control")
        expected = {tag: "value" for tag in tags}
        expected["values"] = [7, "7"]
        m = set_manifest(expected)
        for node in m["nodes"].values():
            if node["kind"] == "probe":
                node["field_dimensions"] = {tag: tag for tag in tags} | {"values": "ambiguity"}
        validate(m)
        answer = dict(expected, current="wrong", values=["7", 7])
        r = score(m, trace(m, [answer, expected]))
        for tag in tags:
            first = r["dimension_accuracy"]["first_attempt"][tag]
            self.assertEqual((first["correct"], first["planned"]),
                             (0, 1) if tag == "current" else (2, 2) if tag == "ambiguity" else (1, 1))

    def test_malformed_timeout_unknown_and_missing_fields(self):
        for answer, transport, reasons in ((None, "ok", {"malformed": 2}),
                                            (None, "timeout", {"unavailable": 2}),
                                            ({"status": "unresolved"}, "ok", {"incorrect": 1}),
                                            ({"unknown": "yes"}, "ok", {"unknown": 2})):
            m = dimensions()
            if answer == {"unknown": "yes"}:
                m["nodes"]["p1"]["unknown_answers"] = [answer]
            record = trace(m, [None, m["nodes"]["p2"]["expected"]])
            record["events"][1].update(answer=answer, status=transport)
            r = score(m, record)
            self.check(r, "first_attempt", 1 if reasons == {"incorrect": 1} else 0, **reasons)
            self.check(r, "terminal", 2)

    def test_unattempted_prefix_and_truncated_terminal(self):
        m = dimensions()
        r = score(m, {"manifest_sha256": digest(m), "events": []})
        self.check(r, "first_attempt", 0, unattempted=2)
        self.check(r, "terminal", 0, unavailable=2)
        record = trace(m, [{"status": "unresolved", "values": []}, m["nodes"]["p2"]["expected"]])
        record["events"] = record["events"][:2]
        r = score(m, record)
        self.check(r, "first_attempt", 1, incorrect=1)
        self.check(r, "terminal", 0, unavailable=2)

    def test_tags_never_change_primary_scores(self):
        untagged = ambiguity_manifest()
        tagged = dimensions(copy.deepcopy(untagged))
        answers = [{"status": "resolved", "values": ["beta", "alpha"]}, untagged["nodes"]["p2"]["expected"]]
        a, b = score(untagged, trace(untagged, answers)), score(tagged, trace(tagged, answers))
        b.pop("dimension_accuracy")
        b["manifest_sha256"] = a["manifest_sha256"]
        self.assertEqual(a, b)

    def test_d10_scalar_tolerance_with_exact_sets(self):
        m = dimensions(set_manifest())
        m["answer_tolerance"] = "d10-v1"
        r = score(m, trace(m, [{"values": [None, 7, "alpha"], "code": "42"}]))
        self.check(r, "first_attempt", 2)
        self.check(r, "terminal", 2)

    def test_extra_claim_can_fail_acceptance_with_correct_planned_fields(self):
        m = dimensions()
        answer = {**m["nodes"]["p1"]["expected"], "extra": "claim"}
        r = score(m, trace(m, [answer, answer]))
        self.assertFalse(r["accepted"])
        self.check(r, "first_attempt", 2)
        self.check(r, "terminal", 2)
        self.assertIsNone(r["dimension_accuracy"]["terminal"]["provenance"]["accuracy"])

    def test_completed_answer_in_aborted_slot_has_no_terminal_credit(self):
        m = dimensions(set_manifest())
        with tempfile.TemporaryDirectory() as temp:
            p, a = bundle(m, [response(encode(m["nodes"]["p1"]["expected"]))], slots=2)
            store = Store.create(Path(temp) / "abort.db", p, a)
            try:
                run_offline(store, "slot-0")
                for entry in store.entries("slot-0")[:-1]:
                    store.append("slot-1", entry["kind"], entry["payload"])
                store.abort("slot-1", "operator_abort", "synthetic stop before finish")
                r = report(store)
                self.check(r["trials"][1]["score"], "first_attempt", 2)
                self.check(r["trials"][1]["score"], "terminal", 0, unavailable=2)
                self.check(r["dimension_accuracy"][1], "terminal", 0, unavailable=2)
            finally:
                store.close()

    def test_invalid_tags_and_opt_in(self):
        for updates in ({"status": "other", "values": "ambiguity"}, {"status": "ambiguity"},
                        {"status": "ambiguity", "values": "ambiguity", "extra": "current"},
                        {"status": [], "values": "ambiguity"}, []):
            m = dimensions()
            m["nodes"]["p1"]["field_dimensions"] = updates
            with self.subTest(updates=updates), self.assertRaises(InvalidRecord):
                validate(m)
        m = dimensions(set_manifest({"values": []}))
        del m["answer_predicate"]
        m["nodes"]["p1"]["expected"] = {"values": "x"}
        m["nodes"]["p2"]["expected"] = {"values": "x"}
        for name in ("p1", "p2"):
            m["nodes"][name].pop("set_fields")
        with self.assertRaises(InvalidRecord):
            validate(m)

    def test_heterogeneous_plan_is_unavailable_without_changing_acceptance(self):
        m = dimensions()
        m["nodes"]["p2"]["field_dimensions"]["status"] = "current"
        validate(m)
        r = score(m, trace(m, [m["nodes"]["p1"]["expected"]]))
        self.assertTrue(r["accepted"])
        self.assertEqual(r["dimension_accuracy"]["unavailable_reason"], "heterogeneous_field_plan")

    def test_report_retains_every_slot_and_replays_diagnostics(self):
        m = dimensions(set_manifest())
        answers = [{"values": [None, 7, "alpha"], "code": 42}]
        with tempfile.TemporaryDirectory() as temp:
            p, a = bundle(m, [response(encode(v)) for v in answers], slots=4)
            store = Store.create(Path(temp) / "dimensions.db", p, a)
            try:
                run_offline(store, "slot-0")
                store.append("slot-1", "start", {})
                store.abort("slot-1", "operator_abort", "synthetic")
                result = report(store)
                rows = result["dimension_accuracy"]
                self.assertEqual(len(rows), 4)
                self.assertEqual([row["slot"] for row in rows], [f"slot-{i}" for i in range(4)])
                self.check(rows[0], "terminal", 2)
                self.check(rows[1], "terminal", 0, unavailable=2)
                self.check(rows[2], "first_attempt", 0, unattempted=2)
                self.check(rows[2], "terminal", 0, unattempted=2)
                for fmt in ("v1", "v2"):
                    exported = export_bundle(store, fmt)
                    exported["report"] = {"forged_dimensions": True}
                    replayed = replay_export(exported)
                    self.assertEqual(replayed["dimension_accuracy"], result["dimension_accuracy"])
                    self.assertEqual(replayed["trials"], result["trials"])
            finally:
                store.close()
