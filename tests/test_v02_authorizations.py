"""Regression cases supplied by reviewer; traces are synthetic, not model runs."""
from fractions import Fraction
import unittest

from etps_v02.scorer import InvalidRecord, classify, score, summarize, validate
from test_v02_scorer import fixture, probe, replay, user


def reused_grant(correct_between=False):
    m = fixture()
    text = "The code is amber."  # 18 bytes, repeated exactly three times.
    m["nodes"]["intro"] = user(text, "p1")
    m["nodes"]["recover"] = user(text, "p2" if correct_between else "repeat", [[0, 18, "db"]], "p1")
    m["nodes"]["repeat"] = user(text, "last", [[0, 18, "db"]], "p1")
    m["nodes"]["p2"]["next"]["correct"] = "repeat"
    m["nodes"]["last"] = probe({"database": "SQLite"}, "pass", "fail")
    return m


class AuthorizationTests(unittest.TestCase):
    def test_one_failure_cannot_count_two_resupplies(self):
        m = reused_grant()
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            validate(m)
        r = score(m, replay(m))
        self.assertEqual((r["R"], r["I"], r["RR"]), (18, 54, Fraction(1, 3)))
        self.assertTrue(r["measurement_valid"])
        self.assertEqual(r["authoring_findings"][0]["code"], "duplicate_recovery_authorization")
        repeated = [x for x in r["classifications"] if x["node"] == "repeat"][0]
        self.assertEqual((repeated["class"], repeated["R"]), ("scheduled", 0))

    def test_recovery_correct_probe_then_recap_is_not_recovery(self):
        m = reused_grant(correct_between=True)
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            validate(m)
        r = score(m, replay(m))
        self.assertEqual((r["R"], r["I"]), (18, 54))
        self.assertTrue(r["accepted"])
        self.assertEqual([c for c in r["classifications"] if c["node"] == "repeat"][0]["R"], 0)

    def test_correct_probe_clears_unconsumed_grant(self):
        m = fixture()
        m["nodes"]["p1"]["next"] = {k: "p2" for k in m["nodes"]["p1"]["next"]}
        m["nodes"]["p2"]["next"]["correct"] = "recover"
        m["nodes"]["recover"]["next"] = "last"
        m["nodes"]["last"] = probe({"database": "SQLite"}, "pass", "fail")
        validate(m)
        r = score(m, replay(m))
        self.assertEqual(r["R"], 0)
        self.assertEqual(r["I"], 40)
        self.assertTrue(r["accepted"])

    def test_new_failure_can_authorize_new_recovery(self):
        m = reused_grant(correct_between=True)
        m["nodes"]["p2"]["next"] = {k: "pass" if k == "correct" else "repeat"
                                           for k in m["nodes"]["p2"]["next"]}
        m["nodes"]["repeat"]["failure"] = "p2"
        validate(m)
        r = score(m, replay(m, {"p1": {}, "p2": {}}))
        self.assertEqual((r["R"], r["I"]), (36, 54))
        self.assertFalse(r["authoring_findings"])

    def test_new_uncorrected_failure_does_not_revive_consumed_older_citation(self):
        """Runtime prevents overcredit; authoring blocks stale-link undercounting."""
        m = reused_grant(correct_between=True)
        m["nodes"]["p2"]["next"] = {k: "pass" if k == "correct" else "repeat"
                                           for k in m["nodes"]["p2"]["next"]}
        # The second real failure is p2, but the authored second re-supply cites p1.
        self.assertEqual(m["nodes"]["repeat"]["failure"], "p1")
        with self.assertRaisesRegex(InvalidRecord, "duplicate recovery"):
            validate(m)
        r = score(m, replay(m, {"p1": {}, "p2": {}}))
        repeat = next(c for c in r["classifications"] if c["node"] == "repeat")
        self.assertEqual((repeat["class"], repeat["R"], repeat["stale_failure_obligations"]),
                         ("scheduled", 0, ["db"]))
        self.assertEqual((r["R"], r["I"], r["RR"]), (18, 54, Fraction(1, 3)))
        self.assertTrue(r["measurement_valid"])
        self.assertTrue(r["authoring_findings"])
        # No implicit retargeting to p2: only an explicitly corrected manifest earns R.
        m["nodes"]["repeat"]["failure"] = "p2"
        validate(m)
        corrected = score(m, replay(m, {"p1": {}, "p2": {}}))
        self.assertEqual((corrected["R"], corrected["I"]), (36, 54))

    def test_mutually_exclusive_recovery_variants_are_allowed(self):
        m = fixture()
        m["nodes"]["alternate"] = user("database=SQLite", "p2", [[0, 15, "db"]], "p1")
        m["nodes"]["p1"]["next"]["unknown"] = "alternate"
        validate(m)
        for answer in ({"status": "unknown"}, {"database": "wrong"}):
            r = score(m, replay(m, {"p1": answer}))
            self.assertEqual(r["R"], 15)

    def test_multiple_spans_consume_only_after_whole_event(self):
        m = fixture()
        m["nodes"]["recover"]["spans"] = [[0, 5, "db"], [5, 15, "db"], [2, 8, "db"]]
        validate(m)
        r = score(m, replay(m))
        self.assertEqual(r["R"], 15)
        c = [x for x in r["classifications"] if x["node"] == "recover"][0]
        self.assertEqual(c["consumed_obligations"], ["db"])

    def test_unknown_answer_shapes_are_declared_per_probe(self):
        m = fixture()
        m["nodes"]["p1"]["unknown_answers"] = [{"availability": "not_known"}]
        for answer, outcome in (({"availability": "not_known"}, "unknown"),
                                ({"status": "unknown"}, "incorrect"),
                                ({"status": "refusal"}, "incorrect")):
            r = score(m, replay(m, {"p1": answer}))
            self.assertEqual(r["classifications"][1]["class"], outcome)
        event = {"status": "ok", "answer": {"status": "unknown"}}
        self.assertEqual(classify(event, {"database": "SQLite"}), "incorrect")

    def test_missing_unknown_schema_is_replay_only(self):
        m = fixture()
        record = replay(m, {"p1": {"status": "unknown"}})
        del m["nodes"]["p1"]["unknown_answers"]
        from etps_v02.scorer import digest
        record["manifest_sha256"] = digest(m)
        with self.assertRaisesRegex(InvalidRecord, "declare unknown_answers"):
            validate(m)
        r = score(m, record)
        self.assertEqual(r["legacy_unknown_probes"], ["p1"])
        self.assertEqual(r["classifications"][1]["class"], "unknown")

    def test_invalid_or_overlapping_unknown_declarations_rejected(self):
        for answers in ([{"database": "SQLite"}], ["unknown"], [{"status": "x"}, {"status": "x"}]):
            m = fixture()
            m["nodes"]["p1"]["unknown_answers"] = answers
            with self.assertRaises(InvalidRecord):
                validate(m)

    def test_checkpoint_delayed_start_is_explicitly_pilot_unsupported(self):
        m = fixture()
        m["obligations"]["db"]["begin_after"] = "p1"
        with self.assertRaisesRegex(InvalidRecord, "pilot begin"):
            validate(m)

    def test_pooled_rr_weights_inputs_and_keeps_failed_costs(self):
        m = fixture()
        a = score(m, replay(m, {"p1": {"database": "SQLite"}}, wall=2))
        b = score(m, replay(m, {"p1": {}, "p2": {}}, wall=5))
        s = summarize([a, b])
        self.assertEqual(s["pooled_RR"], Fraction(15, 55))
        self.assertNotEqual(s["pooled_RR"], (a["RR"] + b["RR"]) / 2)
        self.assertEqual(s["input_bytes_per_accepted"], 55)
        self.assertEqual(s["wall_seconds_per_accepted"], 7)
        self.assertEqual(s["acceptance_rate"], Fraction(1, 2))
        incomplete = summarize([a, b], planned=3)
        self.assertIsNone(incomplete["pooled_RR"])
        self.assertIsNone(incomplete["input_bytes_per_accepted"])
        self.assertEqual(incomplete["pooled_RR_unavailable_reason"], "unattempted_slots")
