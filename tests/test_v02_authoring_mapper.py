"""SYNTHETIC mapping and lossless-source round trips only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document, synthetic_recovery
from etps_v02.intake.mapper import MappingError, map_authoring, recover_source
from etps_v02.intake.state_records import validate_state_records
from etps_v02.workload import decode, encode, sha
from etps_v02.scorer import digest, score
from etps_v02.runner import answer_from_raw


def source_paths(value, prefix=""):
    yield prefix
    if isinstance(value, dict):
        for key, child in value.items():
            yield from source_paths(child, prefix + "/" + key.replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from source_paths(child, prefix + "/" + str(index))


def pointer(value, path):
    for part in path.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


class MapperTests(unittest.TestCase):
    def check_bundle(self, doc):
        raw = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
        files = map_authoring(raw)
        self.assertEqual(files, map_authoring(raw))
        self.assertEqual(recover_source(files), raw)
        index = decode(files["bundle.json"])
        self.assertEqual(index["source_sha256"], sha(raw))
        for item in index["tasks"]:
            manifest = decode(files[item["manifest"]])
            intake = validate_state_records(manifest, files[item["sidecar"]])
            self.assertEqual(intake["status"], "validated")
            self.assertFalse(intake["semantics_verified"])
            self.assertEqual(item["manifest_sha256"], sha(files[item["manifest"]]))
            log = decode(files[item["derivation"]])
            self.assertEqual(set(source_paths(doc)), {e["source"] for e in log["entries"]})
            for entry in log["entries"]:
                self.assertTrue(entry["targets"])
                for target in entry["targets"]:
                    pointer(decode(files[target["artifact"]]), target["pointer"])
            self.assertTrue(any(t["kind"] == "obligation" for e in log["entries"] for t in e["targets"]))
            events, node = [], manifest["start"]
            while manifest["nodes"][node]["kind"] != "terminal":
                value = manifest["nodes"][node]
                event = {"node": node, "kind": value["kind"]}
                if value["kind"] == "user":
                    event["text"] = value["text"]
                    node = value["next"]
                else:
                    event.update(status="ok", answer=answer_from_raw(encode(value["expected"]), "typed-v1", set_fields=value["set_fields"]))
                    node = value["next"]["correct"]
                events.append(event)
            result = score(manifest, {"manifest_sha256": digest(manifest), "events": events})
            self.assertTrue(result["measurement_valid"])
            self.assertTrue(result["accepted"])
        return files

    def test_a_b_c_a_b_a_lapse_and_reinstatement(self):
        cases = [("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C"),
                 ("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_A"),
                 ("SYNTHETIC_A", ("expired", None, [], "lapse")),
                 ("SYNTHETIC_A", ("expired", None, [], "lapse"),
                  ("active", "SYNTHETIC_A", [("SYNTHETIC-m2", "SYNTHETIC_A")], "reinstate"))]
        for values in cases:
            with self.subTest(values=values):
                self.check_bundle(synthetic_document(values))

    def test_unresolved_then_late_precedence_and_provenance(self):
        self.check_bundle(synthetic_document(("SYNTHETIC_A",
            ("unresolved", None, [("SYNTHETIC-m0", "SYNTHETIC_A"), ("SYNTHETIC-m1", "SYNTHETIC_B")], "change"),
            ("active", "SYNTHETIC_A", [("SYNTHETIC-m0", "SYNTHETIC_A")], "precedence"))))

    def test_partial_and_scoped_changes_preserve_other_record(self):
        doc = synthetic_document()
        t = doc["tasks"][0]
        t["coverage_tags"]["subcases"] = ["partial", "scoped"]
        r = copy.deepcopy(t["state_history"][0])
        r.update(id="SYNTHETIC-other", property="SYNTHETIC unchanged property", scope="SYNTHETIC south")
        r["versions"] = r["versions"][:1]
        r["versions"][0]["id"] = "SYNTHETIC-other-v"
        for req in r["versions"][0]["requirements"]:
            req.update(id="SYNTHETIC-other-" + req["kind"], end_before="$trial_end")
        t["state_history"].append(r)
        self.check_bundle(doc)

    def test_recovery_spans_recap_markers_and_missing_fields(self):
        doc = synthetic_recovery()
        doc["tasks"][0]["conversation"][0]["recap"] = True
        self.check_bundle(doc)
        doc = synthetic_document()
        del doc["tasks"][0]["probes"][0]["field_map"]["source"]
        del doc["tasks"][0]["probes"][0]["expected"]["source"]
        self.check_bundle(doc)

    def test_explicit_unsupported_features_refuse(self):
        doc = synthetic_document()
        doc["tasks"][0]["state_history"][0]["versions"][0]["requirements"][0]["begin_after"] = "SYNTHETIC-m1"
        cases = [(doc, "delayed_obligation")]
        doc = synthetic_recovery()
        t = doc["tasks"][0]
        t["recoveries"][0]["failure_probes"].append("SYNTHETIC-retry")
        t["probes"][1]["outcomes"]["incorrect"] = "SYNTHETIC-recovery"
        cases.append((doc, "multi_failure_recovery"))
        doc = synthetic_document()
        doc["tasks"][0]["probes"][0]["alternative_answers"] = [{"answer": "SYNTHETIC-other"}]
        cases.append((doc, "alternative_answers"))
        doc = synthetic_document()
        doc["tasks"][0]["field_map"]["answer"]["kind"] = "clarification"
        for p in doc["tasks"][0]["probes"]:
            p["field_map"]["answer"]["kind"] = "clarification"
        cases.append((doc, "clarification_unrepresentable"))
        for doc, code in cases:
            with self.subTest(code=code), self.assertRaises(MappingError) as caught:
                map_authoring(encode(doc))
            self.assertEqual(caught.exception.code, code)

    def test_intake_key_defect_blocks_mapping_and_source_tampering(self):
        doc = synthetic_document()
        doc["tasks"][0]["probes"][0]["expected"]["answer"] = "SYNTHETIC-wrong"
        with self.assertRaises(MappingError) as caught:
            map_authoring(encode(doc))
        self.assertEqual(caught.exception.code, "answer_mismatch")
        files = self.check_bundle(synthetic_document())
        files["source.json"] += b" "
        with self.assertRaises(MappingError) as caught:
            recover_source(files)
        self.assertEqual(caught.exception.code, "bundle_changed")

    def test_cli_refuses_overwrite_and_failed_mapping_leaves_no_output(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as folder:
            source, out = Path(folder) / "SYNTHETIC.json", Path(folder) / "derived"
            source.write_bytes(encode(synthetic_document()))
            args = [sys.executable, "-B", "-m", "etps_v02.intake.mapper", str(source), str(out)]
            first = subprocess.run(args, cwd=root, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = subprocess.run(args, cwd=root, capture_output=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(json.loads(second.stdout)["code"], "output_exists")
            source.write_bytes(b"{}")
            args[-1] = str(Path(folder) / "failed")
            failure = subprocess.run(args, cwd=root, capture_output=True)
            self.assertEqual(failure.returncode, 2)
            self.assertFalse(Path(args[-1]).exists())
