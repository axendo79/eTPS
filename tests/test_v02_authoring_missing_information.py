"""SYNTHETIC F9 mapping, exact answers and frozen-bundle round trips."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from authoring_fixtures import synthetic_document, synthetic_recovery
from authoring_rulings_fixtures import synthetic_disallowed_forms, synthetic_missing_unit
from etps_v02.intake.authoring import AuthoringError, validate_authoring
from etps_v02.intake.corpus_freeze import FreezeError, create_freeze, verify_freeze
from etps_v02.intake.mapper import MappingError, map_authoring, recover_source
from etps_v02.intake.state_records_v11 import validate_state_records
from etps_v02.runner import answer_from_raw
from etps_v02.scorer import digest, score
from etps_v02.workload import decode, encode, sha
from test_v02_authoring_mapper import pointer, source_paths
from test_v02_corpus_freeze import synthetic_freezable, synthetic_review


class MissingInformationMapperTests(unittest.TestCase):
    def test_missing_unit_round_trip_binding_and_every_source_field(self):
        doc = synthetic_missing_unit()
        raw = json.dumps(doc, indent=2).encode()
        files = map_authoring(raw)
        self.assertEqual(files, map_authoring(raw))
        self.assertEqual(recover_source(files), raw)
        task = decode(files["bundle.json"])["tasks"][0]
        manifest = decode(files[task["manifest"]])
        sidecar = decode(files[task["sidecar"]])
        self.assertEqual(sidecar["version"], "state-records-v1.1")
        self.assertEqual(manifest["metadata"]["state_records"], {
            "version": sidecar["version"], "sha256": sha(files[task["sidecar"]])})
        self.assertEqual(task["manifest_sha256"], sha(files[task["manifest"]]))
        self.assertEqual(encode(validate_state_records(manifest, files[task["sidecar"]])), files[task["intake"]])
        self.assertEqual(decode(files[task["keys"]])["SYNTHETIC-p0"],
                         {"status": "missing_information", "missing_item": "SYNTHETIC-unit"})
        entries = decode(files[task["derivation"]])["entries"]
        self.assertEqual(set(source_paths(doc)), {e["source"] for e in entries})
        for entry in entries:
            for target in entry["targets"]:
                pointer(decode(files[target["artifact"]]), target["pointer"])
        for source in ("/tasks/0/field_map/status/missing_item",
                       "/tasks/0/probes/0/field_map/missing_item/projection"):
            targets = next(e["targets"] for e in entries if e["source"] == source)
            self.assertTrue(any(t["artifact"] == task["sidecar"] and t["pointer"].startswith("/fields/") for t in targets))

    def test_exact_status_only_and_existing_typed_scorer(self):
        doc = synthetic_missing_unit()
        probe = doc["tasks"][0]["probes"][0]
        probe["field_map"].pop("missing_item")
        probe["expected"].pop("missing_item")
        files = map_authoring(encode(doc))
        task = decode(files["bundle.json"])["tasks"][0]
        manifest = decode(files[task["manifest"]])
        events, node = [], manifest["start"]
        while manifest["nodes"][node]["kind"] != "terminal":
            value = manifest["nodes"][node]
            event = {"node": node, "kind": value["kind"]}
            if value["kind"] == "user":
                event["text"] = value["text"]
                node = value["next"]
            else:
                event.update(status="ok", answer=answer_from_raw(encode(value["expected"]), "typed-v1", set_fields=[]))
                node = value["next"]["correct"]
            events.append(event)
        record = {"manifest_sha256": digest(manifest), "events": events}
        result = score(manifest, record)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["measurement_valid"])
        events[-1]["answer"] = {"status": "SYNTHETIC please clarify"}
        result = score(manifest, record)
        self.assertTrue(result["measurement_valid"])
        self.assertFalse(result["accepted"])

    def test_disallowed_forms_refuse_at_authoring_and_mapping(self):
        for doc, code in synthetic_disallowed_forms():
            for validator, error in ((validate_authoring, AuthoringError), (map_authoring, MappingError)):
                with self.subTest(code=code, validator=validator.__name__), self.assertRaises(error) as caught:
                    validator(encode(doc))
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(caught.exception.path.startswith("source.tasks"))

    def test_general_clarification_and_established_item_remain_refused(self):
        doc = synthetic_document()
        doc["tasks"][0]["field_map"]["answer"]["kind"] = "clarification"
        for probe in doc["tasks"][0]["probes"]:
            probe["field_map"]["answer"]["kind"] = "clarification"
        with self.assertRaises(MappingError) as caught:
            map_authoring(encode(doc))
        self.assertEqual(caught.exception.code, "clarification_unrepresentable")
        doc = synthetic_missing_unit()
        item = doc["tasks"][0]["state_history"][1]
        version = copy.deepcopy(doc["tasks"][0]["state_history"][0]["versions"][0])
        version.update(id="SYNTHETIC-item-version", requirements=[])
        item["versions"] = [version]
        with self.assertRaises(MappingError) as caught:
            map_authoring(encode(doc))
        self.assertEqual(caught.exception.code, "missing_item_established")

    def test_plain_v1_all_artifact_bytes_match_pre_extension_fingerprints(self):
        # Captured before R3; every artifact's exact SHA is included, not just keys.
        for doc, expected in ((synthetic_document(), "0cf3f0c00a8b5b058525ac6ffc1ab331b16199c79615c404c7231f5db5c77949"),
                              (synthetic_recovery(), "792bf72c98e2c093eadc0c17cff8fd220ba7208f5547c8e2f18726ce5a77f19d")):
            files = map_authoring(encode(doc))
            self.assertEqual(sha(encode({name: sha(raw) for name, raw in files.items()})), expected)

    def test_mixed_bundle_selects_version_per_task(self):
        doc = synthetic_missing_unit()
        other = synthetic_document()["tasks"][0]
        other["id"] = "SYNTHETIC-other-task"
        doc["tasks"].append(other)
        files = map_authoring(encode(doc))
        tasks = decode(files["bundle.json"])["tasks"]
        self.assertEqual([decode(files[t["sidecar"]])["version"] for t in tasks],
                         ["state-records-v1.1", "state-records-v1"])
        self.assertEqual(recover_source(files), encode(doc))

    def test_freeze_verifies_extension_and_refuses_later_identifier_change(self):
        files = synthetic_freezable()
        files.update(map_authoring(encode(synthetic_missing_unit())))
        settings = decode(files["settings.json"])
        settings["counts"] = decode(files["bundle.json"])["counts"]
        files["settings.json"] = encode(settings)
        synthetic_review(files)
        frozen = create_freeze(files, "SYNTHETIC-F9-dev", "development", "SYNTHETIC instant")
        self.assertEqual(verify_freeze(files, frozen)["status"], "verified")
        task = decode(files["bundle.json"])["tasks"][0]
        files[task["sidecar"]] += b" "
        with self.assertRaises(FreezeError) as caught:
            verify_freeze(files, frozen)
        self.assertEqual(caught.exception.code, "bundle_changed")

    def test_cli_missing_unit_and_authoring_refusal_no_partial_output(self):
        with tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-") as temp:
            source, output = Path(temp) / "SYNTHETIC.json", Path(temp) / "bundle"
            source.write_bytes(encode(synthetic_missing_unit()))
            cmd = [sys.executable, "-B", "-m", "etps_v02.intake.mapper", str(source), str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = decode((output / "task-0001.manifest.json").read_bytes())
            self.assertEqual(manifest["metadata"]["state_records"]["version"], "state-records-v1.1")
            for index, (doc, code) in enumerate(synthetic_disallowed_forms()):
                source.write_bytes(encode(doc))
                refused = Path(temp) / ("refused-" + str(index))
                cmd[-1] = str(refused)
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["code"], code)
                self.assertFalse(refused.exists())
