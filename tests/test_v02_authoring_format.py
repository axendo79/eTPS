"""SYNTHETIC authoring-v1 refusal and closed-format tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from authoring_fixtures import synthetic_document, synthetic_recovery
from etps_v02.intake.authoring import AuthoringError, validate_authoring
from etps_v02.workload import encode


class AuthoringFormatTests(unittest.TestCase):
    def reject(self, doc, code):
        with self.assertRaises(AuthoringError) as caught:
            validate_authoring(encode(doc))
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.path)

    def test_valid_and_no_mutation(self):
        for doc in (synthetic_document(), synthetic_recovery()):
            raw = encode(doc)
            self.assertEqual(validate_authoring(raw), doc)
            self.assertEqual(encode(doc), raw)

    def test_strict_json_and_portable_strings(self):
        for raw in (b'{"version":1,"version":2}', b'\xff', b'{"x":NaN}', b'[]', b'{"x":"\\ud800"}'):
            with self.assertRaises(AuthoringError) as caught:
                validate_authoring(raw)
            self.assertIn(caught.exception.code, ("invalid_json", "field_type"))

    def test_versions_and_size(self):
        for key, code in (("version", "format_version"), ("brief_version", "brief_version")):
            doc = synthetic_document()
            doc[key] = "SYNTHETIC-unsupported"
            self.reject(doc, code)
        with patch("etps_v02.intake.authoring.MAX_BYTES", 2):
            self.reject(synthetic_document(), "safety_limit")

    def test_all_structural_objects_are_closed_and_required(self):
        doc = synthetic_recovery()
        t = doc["tasks"][0]
        v = t["state_history"][0]["versions"][0]
        objects = [doc, t, t["coverage_tags"], t["conversation"][0], t["field_map"]["answer"],
                   t["probes"][0], t["probes"][0]["outcomes"], t["state_history"][0],
                   t["state_history"][0]["status_labels"], v, v["sources"][0], v["time"],
                   v["requirements"][0], t["recoveries"][0], t["predictions"][0]]
        for obj in objects:
            obj["SYNTHETIC-extra"] = None
            self.reject(doc, "closed_fields")
            del obj["SYNTHETIC-extra"]
            key = next(iter(obj))
            value = obj.pop(key)
            self.reject(doc, "required_fields")
            obj[key] = value

    def test_every_other_refusal_code(self):
        cases = [
            ("field_type", lambda t: t["conversation"][0].update(recap=1)),
            ("duplicate_id", lambda t: t["conversation"].append(copy.deepcopy(t["conversation"][0]))),
            ("coverage_tag", lambda t: t["coverage_tags"].update(entity_similarity="SYNTHETIC-other")),
            ("reference", lambda t: t["field_map"]["answer"].update(record="SYNTHETIC-missing")),
            ("position", lambda t: t["probes"][0].update(position="SYNTHETIC-missing")),
            ("field_map", lambda t: t["probes"][0]["field_map"]["answer"].update(dimension="control")),
            ("answer_shape", lambda t: t["probes"][0]["expected"].update(answer=True)),
            ("unknown_overlap", lambda t: t["probes"][0]["unknown_answers"].append(copy.deepcopy(t["probes"][0]["expected"]))),
            ("route", lambda t: t["probes"][0]["outcomes"].update(incorrect="$continue")),
            ("span", lambda t: t["recoveries"][0]["spans"][0].__setitem__(1, 99999)),
            ("prediction", lambda t: t["predictions"].pop()),
            ("public_identifier", lambda t: t["conversation"][0].update(text="SYNTHETIC no public ID")),
            ("history_order", lambda t: t["state_history"][0]["versions"].append(copy.deepcopy(t["state_history"][0]["versions"][0]))),
        ]
        for code, mutate in cases:
            with self.subTest(code=code):
                doc = synthetic_recovery()
                if code == "history_order":
                    mutate(doc["tasks"][0])
                    doc["tasks"][0]["state_history"][0]["versions"][-1]["id"] = "SYNTHETIC-other-version"
                    doc["tasks"][0]["state_history"][0]["versions"][-1]["requirements"] = []
                else:
                    mutate(doc["tasks"][0])
                self.reject(doc, code)

    def test_set_types_duplicate_values_and_wrong_field_sets(self):
        for value in ([1, True], ["SYNTHETIC_A", "SYNTHETIC_A"], [["SYNTHETIC_A"]], "SYNTHETIC_A"):
            doc = synthetic_document()
            doc["tasks"][0]["probes"][0]["expected"]["values"] = value
            self.reject(doc, "answer_shape")

    def test_cli_and_schema(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "docs/v0.2/authoring-v1.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as folder:
            path = Path(folder) / "SYNTHETIC.json"
            path.write_bytes(encode(synthetic_document()))
            result = subprocess.run([sys.executable, "-B", "-m", "etps_v02.intake.authoring", str(path)],
                                    cwd=root, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)["semantics_verified"])
            path.write_bytes(b'{}')
            result = subprocess.run([sys.executable, "-B", "-m", "etps_v02.intake.authoring", str(path)],
                                    cwd=root, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["code"], "required_fields")
