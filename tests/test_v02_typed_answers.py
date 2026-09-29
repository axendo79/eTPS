"""Public synthetic typed-language tests; no private workload material."""
import copy
from pathlib import Path
import tempfile
import unittest

from etps_v02.persistence import Store
from etps_v02.runner import answer_from_raw, run_offline, replay_slot, export_bundle, replay_export
from etps_v02.scorer import InvalidRecord, answer_equal, classify, validate
from etps_v02.workload import encode, sha
from test_v02_runner import bundle, response
from test_v02_scorer import fixture


def typed(expected=None):
    m = fixture()
    m["answer_schema"] = "typed-v1"
    for name in ("p1", "p2"):
        m["nodes"][name]["expected"] = {"v": 5} if expected is None else expected
        m["nodes"][name]["unknown_answers"] = []
    return m


class TypedAnswerTests(unittest.TestCase):
    def test_legacy_projection_and_classification(self):
        self.assertIsNone(answer_from_raw(b'{"v":1}'))
        self.assertEqual(classify({"status": "ok", "answer": {"v": 1}}, {"v": "1"}), "malformed")
        self.assertEqual(answer_from_raw(b'{"v":"1"}'), {"v": "1"})
        validate(fixture())

    def test_type_strict_correct_and_incorrect(self):
        for expected, answer, outcome in (
                ({"v": 5}, {"v": 5}, "correct"),
                ({"v": 5}, {"v": "5"}, "incorrect"),
                ({"v": None}, {"v": None}, "correct"),
                ({"v": None}, {"v": "null"}, "incorrect"),
                ({"v": 5}, {}, "incorrect"),
                ({"v": 5}, {"v": 5, "extra": None}, "incorrect")):
            with self.subTest(answer=answer):
                projected = answer_from_raw(encode(answer), "typed-v1")
                self.assertEqual(classify({"status": "ok", "answer": projected}, expected,
                                          [], "typed-v1"), outcome)

    def test_bool_never_equals_int_and_is_malformed(self):
        self.assertFalse(answer_equal({"v": 1}, {"v": True}))
        self.assertFalse(answer_equal({"v": 1}, {"v": 1.0}))
        self.assertEqual(classify({"status": "ok", "answer": {"v": True}},
                                  {"v": 1}, [], "typed-v1"), "malformed")

    def test_out_of_schema_and_invalid_bytes_are_malformed(self):
        for raw in (b'{"v":true}', b'{"v":false}', b'{"v":5.0}', b'{"v":{}}',
                    b'{"v":[]}', b'[]', b'null', b'5', b'NaN', b'\xff',
                    b'{"v":1,"v":2}', b'{"v":"\\ud800"}', b'{"\\ud800":1}'):
            with self.subTest(raw=raw):
                projected = answer_from_raw(raw, "typed-v1")
                self.assertIsNone(projected)
                self.assertEqual(classify({"status": "ok", "answer": projected},
                                          {"v": 5}, [], "typed-v1"), "malformed")

    def test_typed_unknowns_use_strict_types_and_timeout_precedence(self):
        self.assertEqual(classify({"status": "ok", "answer": {"v": None}},
                                  {"v": 5}, [{"v": None}], "typed-v1"), "unknown")
        self.assertEqual(classify({"status": "ok", "answer": {"v": "5"}},
                                  {"v": None}, [{"v": 5}], "typed-v1"), "incorrect")
        self.assertEqual(classify({"status": "timeout", "answer": {"v": 5}},
                                  {"v": 5}, [], "typed-v1"), "timeout")
        self.assertEqual(classify({"status": "ok", "answer": {"status": "unknown"}},
                                  {"v": 5}, [], "typed-v1"), "incorrect")

    def test_bad_declarations_rejected(self):
        for value in (True, False, 1.0, [], {}, [1]):
            for field in ("expected", "unknown_answers"):
                m = typed()
                m["nodes"]["p1"][field] = {"v": value} if field == "expected" else [{"v": value}]
                with self.subTest(value=value, field=field), self.assertRaises(InvalidRecord):
                    validate(m)
        for schema in (None, "typed-v2", {}, 1):
            m = typed()
            m["answer_schema"] = schema
            with self.assertRaises(InvalidRecord):
                validate(m)

    def test_typed_unknown_overlap_duplicates_and_distinct_string(self):
        for answers in ([{"v": 5}], [{"v": None}, {"v": None}]):
            m = typed()
            m["nodes"]["p1"]["unknown_answers"] = answers
            with self.assertRaises(InvalidRecord):
                validate(m)
        m = typed()
        m["nodes"]["p1"]["unknown_answers"] = [{"v": "5"}]
        validate(m)

    def test_typed_run_reopen_and_both_export_formats(self):
        for expected in ({"v": 5}, {"v": None}):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                plan, artifacts = bundle(manifest=typed(expected), slots=1,
                                         responses=[response(b'{}'), response(encode(expected))])
                path = Path(temp) / "typed.db"
                store = Store.create(path, plan, artifacts)
                try:
                    before = run_offline(store, "slot-0")
                    self.assertTrue(before["score"]["accepted"])
                    self.assertTrue(before["evidence_verified"])
                    self.assertEqual(before["record"]["events"][-1]["answer"], expected)
                finally:
                    store.close()
                store = Store(path)
                try:
                    self.assertEqual(replay_slot(store, "slot-0"), before)
                    for fmt in ("v1", "v2"):
                        r = replay_export(export_bundle(store, format=fmt), validate_authoring=True)
                        self.assertEqual(r["trials"][0], before)
                finally:
                    store.close()

    def test_typed_projection_tamper_cannot_exploit_bool_int_equality(self):
        with tempfile.TemporaryDirectory() as temp:
            plan, artifacts = bundle(manifest=typed({"v": 1}), slots=1,
                                     responses=[response(b'{"v":1}')])
            store = Store.create(Path(temp) / "typed.db", plan, artifacts)
            try:
                run_offline(store, "slot-0")
                exported = export_bundle(store)
            finally:
                store.close()
            rows = exported["journal"]["slot-0"]
            for row in rows:
                if row["kind"] == "event" and row["payload"].get("kind") == "probe":
                    row["payload"]["answer"] = {"v": True}
            previous = sha(encode([exported["plan_sha256"], "slot-0"]))
            for i, row in enumerate(rows):
                previous = sha(encode(["slot-0", i, row["kind"], previous]) + encode(row["payload"]))
                row["sha256"] = previous
            with self.assertRaisesRegex(InvalidRecord, "projection mismatch"):
                replay_export(exported)

    def test_old_journal_layout_projection_and_replay_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            plan, artifacts = bundle(slots=1, responses=[response(b'{"v":1}'), response()])
            store = Store.create(Path(temp) / "legacy.db", plan, artifacts)
            try:
                result = run_offline(store, "slot-0")
                self.assertIsNone(result["record"]["events"][1]["answer"])
                self.assertNotIn("answer_schema", result["record"]["events"][1])
                exported = export_bundle(store)
                original = copy.deepcopy(exported)
                self.assertEqual(replay_export(exported)["trials"][0], result)
                self.assertEqual(exported, original)
                # Pre-projection-repair journals retained arbitrary JSON.
                rows = exported["journal"]["slot-0"]
                for row in rows:
                    if row["kind"] == "event" and row["payload"].get("node") == "p1":
                        row["payload"]["answer"] = {"v": 1}
                previous = sha(encode([exported["plan_sha256"], "slot-0"]))
                for i, row in enumerate(rows):
                    previous = sha(encode(["slot-0", i, row["kind"], previous]) + encode(row["payload"]))
                    row["sha256"] = previous
                old = replay_export(exported)["trials"][0]
                self.assertEqual(old["score"], result["score"])
                self.assertIn("legacy_answer_projection: malformed JSON shape retained", old["warnings"])
            finally:
                store.close()
