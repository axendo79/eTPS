"""SYNTHETIC answerability controls; no real corpus content or execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.intake import state_records as v1
from etps_v02.intake import state_records_v11 as v11
from etps_v02.workload import encode, sha
from test_v02_state_records import chain, bind
from test_v02_scorer import user


def synthetic_missing_unit():
    manifest, sidecar = chain(("SYNTHETIC_quantity",))
    manifest["metadata"] = {"synthetic_label": "SYNTHETIC"}
    sidecar["version"] = "state-records-v1.1"
    item = copy.deepcopy(sidecar["records"][0])
    item.update(id="SYNTHETIC-unit", property="SYNTHETIC unit", versions=[])
    sidecar["records"].append(item)
    sidecar["fields"] = {name: {"record": "r", "kind": "missing_information",
        "missing_item": item["id"], "projection": projection}
        for name, projection in (("status", "status"), ("missing_item", "identifier"))}
    manifest["nodes"]["p0"].update(expected={"status": "missing_information",
        "missing_item": item["id"]}, set_fields=[])
    sidecar["probes"]["p0"] = ["missing_item", "status"]
    return manifest, sidecar


def bind_v11(manifest, sidecar):
    raw = encode(sidecar)
    manifest.setdefault("metadata", {})["state_records"] = {"version": "state-records-v1.1", "sha256": sha(raw)}
    return raw


def synthetic_item_version(event="e0"):
    _, sidecar = chain(("SYNTHETIC_unit_value",))
    version = sidecar["records"][0]["versions"][0]
    version.update(id="SYNTHETIC-item-v1", event=event, obligations=[])
    version["claims"][0]["source"] = event
    return version


class StateRecordsV11Tests(unittest.TestCase):
    def accept(self, manifest, sidecar):
        raw = bind_v11(manifest, sidecar)
        original = copy.deepcopy(manifest), raw
        result = v11.validate_state_records(manifest, raw)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["version"], "state-records-v1.1")
        self.assertFalse(result["semantics_verified"])
        self.assertIn("missing_information", result["checks"])
        self.assertEqual((manifest, raw), original)
        return result

    def reject(self, manifest, sidecar, code):
        with self.assertRaises(v1.IntakeError) as caught:
            v11.validate_state_records(manifest, bind_v11(manifest, sidecar))
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.path)

    def test_exact_status_with_and_without_identifier(self):
        self.accept(*synthetic_missing_unit())
        m, s = synthetic_missing_unit()
        del m["nodes"]["p0"]["expected"]["missing_item"]
        s["probes"]["p0"].remove("missing_item")
        result = self.accept(m, s)
        self.assertEqual(result["unavailable_fields"], [{"probe": "p0", "field": "missing_item"}])

    def test_later_establishment_is_absent_at_earlier_probe(self):
        m, s = synthetic_missing_unit()
        m["nodes"]["future"] = user("SYNTHETIC unit supplied later", "end")
        m["nodes"]["p0"]["next"] = {key: "future" for key in m["nodes"]["p0"]["next"]}
        s["records"][1]["versions"] = [synthetic_item_version("future")]
        self.accept(m, s)

    def test_prior_active_expired_and_unresolved_are_not_missing(self):
        for status in ("active", "expired", "unresolved"):
            with self.subTest(status=status):
                m, s = synthetic_missing_unit()
                m["start"] = "prior"
                m["nodes"]["prior"] = user("SYNTHETIC earlier unit", "e0")
                version = synthetic_item_version("prior")
                versions = [version]
                if status == "expired":
                    version["next"] = "SYNTHETIC-item-v2"
                    lapse = copy.deepcopy(version)
                    lapse.update(id="SYNTHETIC-item-v2", number=2, previous=version["id"], next=None,
                                 event="e0", transition="lapse", status="expired", value=None, claims=[])
                    versions.append(lapse)
                elif status == "unresolved":
                    version.update(event="e0", status="unresolved", value=None)
                    version["claims"].append({"source": "e0", "authority": "SYNTHETIC source",
                                               "value": "SYNTHETIC other unit"})
                s["records"][1]["versions"] = versions
                self.reject(m, s, "missing_item_established")

    def test_branch_dependent_establishment_is_refused(self):
        m, s = synthetic_missing_unit()
        m["nodes"]["p1"] = copy.deepcopy(m["nodes"]["p0"])
        m["nodes"]["p0"]["next"] = {key: "p1" for key in m["nodes"]["p0"]["next"]}
        m["nodes"]["p0"]["next"]["incorrect"] = "alternate"
        m["nodes"]["alternate"] = user("SYNTHETIC branch supplies unit", "p1")
        s["probes"]["p1"] = list(s["probes"]["p0"])
        s["records"][1]["versions"] = [synthetic_item_version("alternate")]
        self.reject(m, s, "branch_inconsistent")

    def test_status_and_identifier_are_exact_no_open_ended_answers(self):
        for field, value in (("status", "SYNTHETIC please clarify"), ("status", "unestablished"),
                             ("status", "Missing_Information"), ("missing_item", "SYNTHETIC-other"),
                             ("missing_item", None)):
            m, s = synthetic_missing_unit()
            m["nodes"]["p0"]["expected"][field] = value
            self.reject(m, s, "missing_information_answer")

    def test_identifier_requires_matching_literal_status_field(self):
        for change in ("no_status", "wrong_projection", "different_pair", "other_status_name"):
            m, s = synthetic_missing_unit()
            if change == "no_status":
                del m["nodes"]["p0"]["expected"]["status"]
                s["probes"]["p0"].remove("status")
            elif change == "wrong_projection":
                s["fields"]["status"]["projection"] = "identifier"
            elif change == "different_pair":
                s["fields"]["missing_item"]["record"] = "SYNTHETIC-unit"
            else:
                s["fields"]["answer_status"] = s["fields"].pop("status")
                m["nodes"]["p0"]["expected"]["answer_status"] = m["nodes"]["p0"]["expected"].pop("status")
                s["probes"]["p0"] = ["answer_status", "missing_item"]
            self.reject(m, s, "missing_information_answer")

    def test_closed_query_and_resolved_record_identifiers(self):
        for field, value, code in (("checkpoint", None, "closed_fields"),
                                   ("projection", "clarification", "field_type"),
                                   ("record", "SYNTHETIC-no-record", "answer_reference"),
                                   ("missing_item", "SYNTHETIC-typo", "answer_reference"),
                                   ("missing_item", [], "field_type")):
            m, s = synthetic_missing_unit()
            s["fields"]["status"][field] = value
            self.reject(m, s, code)

    def test_complete_probe_fields_and_normal_projections_still_checked(self):
        m, s = synthetic_missing_unit()
        s["probes"]["p0"].remove("missing_item")
        self.reject(m, s, "probe_fields")
        m, s = synthetic_missing_unit()
        s["fields"]["quantity"] = {"record": "r", "kind": "current", "checkpoint": None}
        s["probes"]["p0"].append("quantity")
        m["nodes"]["p0"]["expected"]["quantity"] = "SYNTHETIC_quantity"
        self.accept(m, s)
        m["nodes"]["p0"]["expected"]["quantity"] = "SYNTHETIC_wrong"
        self.reject(m, s, "answer_mismatch")

    def test_binding_raw_bytes_versions_and_json_refusals(self):
        m, s = synthetic_missing_unit()
        raw = bind_v11(m, s)
        for data, code in ((None, "sidecar_missing"), (raw + b" ", "hash_mismatch")):
            with self.assertRaises(v1.IntakeError) as caught:
                v11.validate_state_records(m, data)
            self.assertEqual(caught.exception.code, code)
        s["version"] = "state-records-v1"
        self.reject(m, s, "sidecar_version")
        m, s = synthetic_missing_unit()
        bind_v11(m, s)
        m["metadata"]["state_records"]["extra"] = "SYNTHETIC"
        with self.assertRaises(v1.IntakeError) as caught:
            v11.validate_state_records(m, encode(s))
        self.assertEqual(caught.exception.code, "closed_fields")
        m["metadata"]["state_records"].pop("extra")
        raw = b'{"SYNTHETIC":0,"SYNTHETIC":1}'
        m["metadata"]["state_records"]["sha256"] = sha(raw)
        with self.assertRaises(v1.IntakeError) as caught:
            v11.validate_state_records(m, raw)
        self.assertEqual(caught.exception.code, "invalid_json")

    def test_v1_dispatch_is_identical_and_old_validator_rejects_new_binding(self):
        m, s = chain(("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_A"))
        m["metadata"] = {"synthetic_label": "SYNTHETIC"}
        raw = bind(m, s)
        before = encode(m), raw
        self.assertEqual(encode(v11.validate_state_records(m, raw)), encode(v1.validate_state_records(m, raw)))
        self.assertEqual((encode(m), raw), before)
        self.assertEqual(v11.validate_state_records({}), v1.validate_state_records({}))
        m, s = synthetic_missing_unit()
        with self.assertRaises(v1.IntakeError) as caught:
            v1.validate_state_records(m, bind_v11(m, s))
        self.assertEqual(caught.exception.code, "binding_version")

    def test_software_bounds_and_invalid_manifest_still_apply(self):
        m, s = synthetic_missing_unit()
        raw = bind_v11(m, s)
        for ceiling in ("MAX_BYTES", "MAX_NODES"):
            with patch.object(v11, ceiling, 1), self.assertRaises(v1.IntakeError) as caught:
                v11.validate_state_records(m, raw)
            self.assertEqual(caught.exception.code, "safety_limit")
        m["nodes"]["p0"]["set_fields"] = ["SYNTHETIC-not-a-field"]
        self.reject(m, s, "manifest_invalid")

    def test_cli_dispatch_opt_out_and_hash_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for version in ("state-records-v1", "state-records-v1.1", None):
                m, s = chain(("SYNTHETIC_A",)) if version == "state-records-v1" else synthetic_missing_unit()
                raw = bind(m, s) if version == "state-records-v1" else bind_v11(m, s)
                if version is None:
                    m.pop("metadata")
                (root / "manifest.json").write_bytes(encode(m))
                (root / "sidecar.json").write_bytes(raw)
                cmd = [sys.executable, "-B", "-m", "etps_v02.intake.state_records_v11",
                       "--manifest", str(root / "manifest.json"), "--sidecar",
                       str(root / ("SYNTHETIC-no-file" if version is None else "sidecar.json"))]
                completed = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["status"], "not_opted_in" if version is None else "validated")
            m, s = synthetic_missing_unit()
            raw = bind_v11(m, s)
            (root / "manifest.json").write_bytes(encode(m))
            (root / "sidecar.json").write_bytes(raw + b" ")
            cmd[-1] = str(root / "sidecar.json")
            completed = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["code"], "hash_mismatch")
