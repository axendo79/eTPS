"""Synthetic replay cases, not model benchmark trials or independent review."""
import copy
from fractions import Fraction
import hashlib
import unittest

from etps_v02.scorer import UNIT, OUTCOMES, InvalidRecord, digest, score, summarize


def user(text, next_node, spans=None, failure=None):
    result = {"kind": "user", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
              "spans": spans or [], "next": next_node}
    if failure:
        result["failure"] = failure
    return result


def probe(expected, correct, failure, obligations=("db",)):
    return {"kind": "probe", "expected": expected,
            "unknown_answers": [{"status": "unknown"}, {"status": "refusal"}], "obligations": list(obligations),
            "next": {outcome: correct if outcome == "correct" else failure for outcome in OUTCOMES}}


def fixture():
    manifest = {"unit": UNIT, "start": "intro", "obligations": {
        "db": {"source": "intro", "begin_after": "intro", "end_before": "$trial_end"}}, "nodes": {
        "intro": user("database=SQLite", "p1"),
        "p1": probe({"database": "SQLite"}, "pass", "recover"),
        "recover": user("database=SQLite; new task", "p2", [[0, 15, "db"]], "p1"),
        "p2": probe({"database": "SQLite"}, "pass", "fail"),
        "pass": {"kind": "terminal", "accepted": True},
        "fail": {"kind": "terminal", "accepted": False}}}
    return manifest


def replay(manifest, answers=None, wall=2):
    answers = answers or {"p1": {"database": "Postgres"}, "p2": {"database": "SQLite"}}
    from etps_v02.scorer import classify
    key, events = manifest["start"], []
    while manifest["nodes"][key]["kind"] != "terminal":
        node = manifest["nodes"][key]
        event = {"node": key, "kind": node["kind"]}
        if node["kind"] == "user":
            event["text"] = node["text"]
        if node["kind"] == "probe":
            event.update(status="ok", answer=answers.get(key, node["expected"]),
                         generation={"tokens": 50, "seconds": 1})
            key = node["next"][classify(event, node["expected"], node["unknown_answers"])]
        else:
            key = node["next"]
        events.append(event)
    return {"manifest_sha256": digest(manifest), "events": events, "wall_seconds": wall}


class ReplayTests(unittest.TestCase):
    def test_retained_fact(self):
        m = fixture()
        r = score(m, replay(m, {"p1": {"database": "SQLite"}}))
        self.assertEqual((r["I"], r["R"], r["RR"], r["retention"]), (15, 0, 0, 1))

    def test_keyword_trap_and_successful_recovery(self):
        m = fixture()
        r = score(m, replay(m, {"p1": {"database": "Postgres", "mention": "SQLite"}}))
        self.assertEqual((r["I"], r["R"], r["RR"]), (40, 15, Fraction(3, 8)))
        self.assertTrue(r["accepted"])
        self.assertEqual(r["retention"], 0)
        self.assertEqual(r["experimental_eTPS"], Fraction(125, 4))

    def test_wrong_no_recovery(self):
        m = fixture()
        m["nodes"]["p1"]["next"] = {k: "pass" if k == "correct" else "fail" for k in OUTCOMES}
        r = score(m, replay(m))
        self.assertEqual(r["RR"], 0)
        self.assertFalse(r["accepted"])
        self.assertIsNone(r["experimental_eTPS"])

    def test_update_current_and_historical(self):
        m = fixture()
        m["nodes"]["intro"]["next"] = "update"
        m["nodes"]["update"] = user("database=Postgres", "p1")
        m["nodes"]["p1"] = probe({"database": "Postgres"}, "history", "fail", ("current",))
        m["nodes"]["history"] = probe({"database": "SQLite"}, "pass", "fail")
        m["obligations"]["current"] = {"source": "update", "begin_after": "update", "end_before": "$trial_end"}
        r = score(m, replay(m))
        self.assertEqual((r["I"], r["R"], r["retention"]), (32, 0, 1))
        r = score(m, replay(m, {"p1": {"database": "SQLite"}}))
        self.assertFalse(r["accepted"])

    def test_unresolved_contradiction_and_legitimate_clarification(self):
        for expected in ({"state": "unresolved", "alternatives": "Monday|Tuesday"},
                         {"clarify": "unit"}):
            with self.subTest(expected=expected):
                m = fixture()
                m["nodes"]["p1"]["expected"] = expected
                r = score(m, replay(m, {"p1": expected}))
                self.assertTrue(r["accepted"])
                self.assertEqual(r["R"], 0)

    def test_known_unit_request_is_failure(self):
        m = fixture()
        r = score(m, replay(m, {"p1": {"clarify": "unit"}}))
        self.assertEqual((r["R"], r["retention"]), (15, 0))

    def test_new_evidence_and_scheduled_recap(self):
        for text in ("Actually new evidence", "database=SQLite"):
            m = fixture()
            m["nodes"]["intro"]["next"] = "extra"
            m["nodes"]["extra"] = user(text, "p1")
            r = score(m, replay(m, {"p1": {"database": "SQLite"}}))
            self.assertEqual((r["I"], r["R"]), (15 + len(text.encode()), 0))

    def test_context_eviction_does_not_end_obligation(self):
        m = fixture()
        m["nodes"]["intro"]["next"] = "evict"
        m["nodes"]["evict"] = {"kind": "internal", "next": "p1"}
        r = score(m, replay(m))
        self.assertEqual(r["R"], 15)

    def test_expiration_boundary_and_out_of_contract(self):
        m = fixture()
        m["obligations"]["db"]["end_before"] = "recover"
        self.assertEqual(score(m, replay(m))["R"], 0)
        m["obligations"]["db"]["end_before"] = "p1"
        r = score(m, replay(m))
        self.assertEqual(r["R"], 0)
        self.assertIsNone(r["retention"])

    def test_overlap_union(self):
        m = fixture()
        m["obligations"]["alias"] = copy.deepcopy(m["obligations"]["db"])
        m["nodes"]["p1"]["obligations"].append("alias")
        m["nodes"]["recover"]["spans"] += [[0, 15, "alias"], [3, 10, "db"]]
        self.assertEqual(score(m, replay(m))["R"], 15)

    def test_internal_summary_and_transport_replay_excluded(self):
        for kind in ("internal", "replay"):
            m = fixture()
            m["nodes"]["intro"]["next"] = "extra"
            m["nodes"]["extra"] = {"kind": kind, "next": "p1"}
            record = replay(m)
            record["events"][1]["text"] = "x" * 9000
            self.assertEqual(score(m, record)["I"], 40)

    def test_unmatched_payload_is_not_wrong_answer(self):
        m = fixture()
        record = replay(m)
        record["events"][2]["text"] += " invented help"
        r = score(m, record)
        self.assertFalse(r["measurement_valid"])
        self.assertIsNone(r["RR"])
        self.assertEqual(r["reason"], "unmatched_user_payload")

    def test_wrong_branch_and_omitted_recovery(self):
        m = fixture()
        record = replay(m)
        del record["events"][2]
        self.assertEqual(score(m, record)["reason"], "off_script_event")

    def test_manifest_mutation_rejected(self):
        m = fixture()
        record = replay(m)
        m["obligations"]["db"]["end_before"] = "recover"
        with self.assertRaisesRegex(InvalidRecord, "identity"):
            score(m, record)

    def test_all_answer_failure_categories(self):
        for answer, label in ((None, "malformed"), ({"status": "unknown"}, "unknown"),
                              ({"status": "refusal"}, "unknown"), ({"new": "value"}, "incorrect")):
            m = fixture()
            r = score(m, replay(m, {"p1": answer}))
            self.assertEqual(r["classifications"][1]["class"], label)
            self.assertTrue(r["measurement_valid"])

    def test_timeout_and_exhausted_recovery(self):
        m = fixture()
        record = replay(m, {"p1": {}, "p2": {}})
        record["events"][1]["status"] = "timeout"
        r = score(m, record)
        self.assertEqual(r["classifications"][1]["class"], "timeout")
        self.assertFalse(r["accepted"])
        self.assertTrue(r["measurement_valid"])

    def test_missing_usage_and_invalid_timing(self):
        m = fixture()
        record = replay(m)
        del record["events"][1]["generation"]
        self.assertIsNone(score(m, record)["TPS"])
        for value in (float("nan"), float("inf"), -1, True, 0):
            record = replay(m)
            record["events"][1]["generation"]["seconds"] = value
            with self.assertRaises(InvalidRecord):
                score(m, record)

    def test_zero_input_no_probes(self):
        m = {"unit": UNIT, "start": "pass", "obligations": {}, "nodes": {
            "pass": {"kind": "terminal", "accepted": True}}}
        r = score(m, replay(m))
        self.assertEqual((r["I"], r["R"]), (0, 0))
        self.assertIsNone(r["RR"])
        self.assertIsNone(r["TPS"])
        self.assertIsNone(r["retention"])

    def test_empty_turn_keeps_trial_denominator(self):
        m = fixture()
        m["nodes"]["intro"]["next"] = "empty"
        m["nodes"]["empty"] = user("", "p1")
        self.assertEqual(score(m, replay(m))["I"], 40)

    def test_utf8_boundaries_and_identity(self):
        m = fixture()
        m["nodes"]["recover"] = user("é猫 new", "p2", [[0, 5, "db"]], "p1")
        r = score(m, replay(m))
        self.assertEqual((r["I"], r["R"]), (24, 5))
        m["nodes"]["recover"]["spans"] = [[1, 5, "db"]]
        with self.assertRaisesRegex(InvalidRecord, "boundaries"):
            score(m, replay(m))

    def test_missing_annotation_and_invalid_spans(self):
        for spans in ([[-1, 5, "db"]], [[0, 100, "db"]], [[10, 3, "db"]]):
            m = fixture()
            m["nodes"]["recover"]["spans"] = spans
            with self.assertRaises(InvalidRecord):
                score(m, replay(m))
        m = fixture()
        del m["nodes"]["recover"]["spans"]
        with self.assertRaises(InvalidRecord):
            score(m, replay(m))

    def test_unrelated_failure_cannot_authorize_recovery(self):
        m = fixture()
        m["obligations"]["other"] = copy.deepcopy(m["obligations"]["db"])
        m["nodes"]["recover"]["spans"] = [[0, 15, "other"]]
        self.assertEqual(score(m, replay(m))["reason"], "unlinked_recovery")

    def test_incomplete_policy_rejected(self):
        m = fixture()
        del m["nodes"]["p1"]["next"]["unknown"]
        with self.assertRaises(InvalidRecord):
            score(m, replay(m))

    def test_cycle_rejected_without_execution(self):
        m = fixture()
        record = replay(m)
        m["nodes"]["p2"]["next"]["incorrect"] = "recover"
        record["manifest_sha256"] = digest(m)
        with self.assertRaisesRegex(InvalidRecord, "cyclic"):
            score(m, record)

    def test_recovery_cannot_establish_its_own_source(self):
        m = fixture()
        m["obligations"]["db"]["source"] = "recover"
        m["obligations"]["db"]["begin_after"] = "recover"
        self.assertEqual(score(m, replay(m))["reason"], "unestablished_recovery")

    def test_unicode_normalization_is_not_implicit(self):
        m = fixture()
        m["nodes"]["recover"] = user("é", "p2", [[0, 2, "db"]], "p1")
        record = replay(m)
        record["events"][2]["text"] = "e\u0301"
        self.assertEqual(score(m, record)["reason"], "unmatched_user_payload")

    def test_truncated_and_extra_events(self):
        m = fixture()
        record = replay(m)
        record["events"].pop()
        self.assertEqual(score(m, record)["reason"], "truncated_trace")
        record = replay(m)
        record["events"].append(record["events"][0])
        self.assertEqual(score(m, record)["reason"], "off_script_event")

    def test_arm_identity_does_not_affect_replay_and_exact_results(self):
        m = fixture()
        a, b = replay(m), replay(m)
        a["arm"], b["arm"] = "baseline", "memory"
        before = copy.deepcopy((m, a))
        self.assertEqual(score(m, a), score(m, b))
        self.assertEqual((m, a), before)
        self.assertEqual(score(m, a)["RR"], Fraction(3, 8))

    def test_all_attempt_costs_include_failures(self):
        m = fixture()
        good = score(m, replay(m))
        bad = score(m, replay(m, {"p1": {}, "p2": {}}, wall=5))
        s = summarize([good, bad])
        self.assertEqual((s["attempted"], s["accepted"], s["acceptance_rate"]), (2, 1, Fraction(1, 2)))
        self.assertEqual(s["input_bytes_per_accepted"], 80)
        self.assertEqual(s["wall_seconds_per_accepted"], 7)
        self.assertIsNone(summarize([bad])["input_bytes_per_accepted"])

    def test_input_based_not_output_based(self):
        m = fixture()
        m["nodes"]["intro"] = user("a" * 100, "p1")
        m["nodes"]["recover"] = user("a" * 100, "p2", [[0, 100, "db"]], "p1")
        record = replay(m)
        record["events"][-1]["generation"]["tokens"] = 5
        r = score(m, record)
        self.assertEqual((r["R"], r["I"], r["RR"]), (100, 200, Fraction(1, 2)))

    def test_mixed_message_document_offsets(self):
        text = "The code is amber. Also sort the list."
        self.assertEqual(text.encode()[0:18], b"The code is amber.")
        self.assertEqual(text.encode()[19:38], b"Also sort the list.")


class FormulaTests(unittest.TestCase):
    def test_executable_formula_attacks(self):
        from etps_v02.examples import results
        result = results()
        a = result["A_recovery"]
        b = result["B_no_recovery_with_30s_extra_cost"]
        diluted = result["diluted_different_profile_noncomparable"]
        self.assertEqual((a["R"], a["I"], a["experimental_eTPS"]), (100, 1000, None))
        self.assertEqual((diluted["R"], diluted["I"], diluted["experimental_eTPS"]),
                         (100, 10000, None))
        self.assertEqual(a["manifest_sha256"], b["manifest_sha256"])
        self.assertIsNone(b["experimental_eTPS"])
        self.assertIsNone(a["TPS"])
        self.assertGreater(b["wall_seconds"], a["wall_seconds"])
        with self.assertRaisesRegex(InvalidRecord, "pool"):
            summarize([a, diluted])

    def test_denominator_dilution(self):
        self.assertEqual(50 * (1 - Fraction(100, 1000)), 45)
        self.assertEqual(50 * (1 - Fraction(100, 10000)), Fraction(99, 2))

    def test_retrieval_cost_reversal(self):
        a, b = 50 * (1 - Fraction(1, 10)), 50
        self.assertLess(a, b)
        self.assertLess(2, 32)

    def test_aggregation_mismatch(self):
        paired = (10 * (1 - Fraction(0)), 100 * (1 - Fraction(9, 10)))
        self.assertEqual(sum(paired) / 2, 10)
        self.assertEqual(Fraction(55) * (1 - Fraction(9, 20)), Fraction(121, 4))

    def test_retry_cost_blindness(self):
        self.assertEqual(Fraction(50, 1), Fraction(150, 3))


if __name__ == "__main__":
    unittest.main()
