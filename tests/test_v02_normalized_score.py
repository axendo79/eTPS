"""SYNTHETIC deterministic diagnostic rules and forbidden broad tolerances."""
import copy
import unittest

from etps_v02.normalized_score import normalized_score
from etps_v02.scorer import classify


class NormalizedScoreTests(unittest.TestCase):
    def score(self, answer, expected, strict, normalized, **fields):
        report = normalized_score(answer, expected, **fields)
        self.assertEqual(report["strict"], strict)
        self.assertEqual(report["normalized"], normalized)
        self.assertTrue(report["diagnostic"])
        self.assertEqual(report["version"], "normalized-score-v1")
        return report

    def test_exact_case_and_whitespace_folding_preserves_word_separation(self):
        self.score({"text": "SYNTHETIC blue"}, {"text": "SYNTHETIC blue"}, 1, 1)
        self.score({"text": "  synthetic\t BLUE\n"}, {"text": "SYNTHETIC blue"}, 0, 1)
        self.score({"text": "SYNTHETICblue"}, {"text": "SYNTHETIC blue"}, 0, 0)
        self.score({"text": "Straße"}, {"text": "STRASSE"}, 0, 1)

    def test_only_declared_id_fields_strip_balanced_brackets_and_quotes(self):
        for value in ("[M2]", '"M2"', "'m2'", '["M2"]', ' " [m2] " '):
            with self.subTest(value=value):
                self.score({"source": value}, {"source": "M2"}, 0, 1, id_fields=("source",))
        self.score({"text": '"SYNTHETIC blue"'}, {"text": "SYNTHETIC blue"}, 0, 0)
        for value in ("bin M2", "M2 extra", "[M2", "M2]", "(M2)", "`M2`"):
            self.score({"source": value}, {"source": "M2"}, 0, 0, id_fields=("source",))
        self.score({"source": "M2"}, {"source": "bin M2"}, 0, 0, id_fields=("source",))

    def test_numeric_strings_with_trailing_unit_without_unit_conversion(self):
        for value in ("7kg", "7 kg", " 7 KG ", "7.0 kg", "7e0 kg", "+7 kg"):
            self.score({"quantity": value}, {"quantity": 7}, 0, 1)
        self.score({"quantity": "-7 kg"}, {"quantity": -7}, 0, 1)
        self.score({"quantity": "0 kg"}, {"quantity": 0}, 0, 1)
        for value in ("7", "seven kg", "about 7 kg", "7 kg extra", "7.1 kg", "kg 7", "8 kg", "NaN kg", "Infinity kg", "７ kg", True, 7.0):
            self.score({"quantity": value}, {"quantity": 7}, 0, 0)
        self.score({"quantity": "7000 g"}, {"quantity": 7}, 0, 0)
        self.score({"quantity": "7 kg"}, {"quantity": "7"}, 0, 0)

    def test_no_key_aliases_extra_missing_keys_null_coercion_or_fuzzy_matching(self):
        for answer, expected in (({"Text": "SYNTHETIC"}, {"text": "SYNTHETIC"}),
                                 ({"alias": "SYNTHETIC"}, {"text": "SYNTHETIC"}),
                                 ({"text": "SYNTHETIC", "extra": "wrong"}, {"text": "SYNTHETIC"}),
                                 ({}, {"text": None}), ({"text": "null"}, {"text": None}),
                                 ({"text": "SYNTHETC"}, {"text": "SYNTHETIC"}),
                                 ({"text": "cafe"}, {"text": "café"}),
                                 ({"text": "cafe\u0301"}, {"text": "café"}),
                                 ({"text": "SYNTHETIC."}, {"text": "SYNTHETIC"}),
                                 ({"text": {"nested": "SYNTHETIC"}}, {"text": "SYNTHETIC"})):
            self.score(answer, expected, 0, 0)
        self.score({"text": None}, {"text": None}, 1, 1)
        self.score(None, {"text": "SYNTHETIC"}, 0, 0)

    def test_complete_sets_keep_types_duplicates_and_membership_strict(self):
        self.score({"values": ["SYNTHETIC_B", "SYNTHETIC_A"]},
                   {"values": ["SYNTHETIC_A", "SYNTHETIC_B"]}, 1, 1, set_fields=("values",))
        self.score({"values": [" synthetic_b ", "synthetic_a"]},
                   {"values": ["SYNTHETIC_A", "SYNTHETIC_B"]}, 0, 1, set_fields=("values",))
        for values in (["SYNTHETIC_A"], ["SYNTHETIC_A", "SYNTHETIC_A"], ["SYNTHETIC_A", "SYNTHETIC_C"],
                       ["SYNTHETIC_A", "synthetic_a"], "SYNTHETIC_A"):
            self.score({"values": values}, {"values": ["SYNTHETIC_A", "SYNTHETIC_B"]}, 0, 0, set_fields=("values",))
        self.score({"values": ["7 kg", "synthetic"]}, {"values": [7, "SYNTHETIC"]}, 0, 1, set_fields=("values",))

    def test_invalid_expected_and_field_declarations_are_explicit_errors(self):
        for expected, fields in (({"x": True}, {}), ({"x": [7, 7]}, {"set_fields": ("x",)}),
                                 ({"x": 7}, {"id_fields": ("x",)}), ({"x": 7}, {"set_fields": ("absent",)}),
                                 ({"x": "M2"}, {"id_fields": ("x", "x")}), ({"x": "M2"}, {"id_fields": "x"})):
            with self.subTest(expected=expected, fields=fields), self.assertRaises(ValueError):
                normalized_score({}, expected, **fields)

    def test_exact_fold_colliding_set_and_context_sensitive_typed_members(self):
        self.score({"values": ["SYNTHETIC", "synthetic"]}, {"values": ["SYNTHETIC", "synthetic"]},
                   1, 1, set_fields=("values",))
        self.score({"values": ["7kg", "7 kg"]}, {"values": [7, "7 kg"]}, 0, 1, set_fields=("values",))
        self.score({"values": ["7kg", "7 g"]}, {"values": [7, "7 kg"]}, 0, 0, set_fields=("values",))

    def test_pure_deterministic_report_never_changes_strict_classification(self):
        answer, expected = {"source": "[m2]", "text": " synthetic "}, {"source": "M2", "text": "SYNTHETIC"}
        before = copy.deepcopy((answer, expected))
        report = self.score(answer, expected, 0, 1, id_fields=("source",))
        self.assertEqual(report, normalized_score(answer, expected, id_fields=("source",)))
        self.assertEqual((answer, expected), before)
        self.assertEqual(classify({"status": "ok", "answer": answer}, expected, answer_schema="typed-v1"), "incorrect")
