"""SYNTHETIC conformance regressions, including output secrecy canaries."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from question_contract_fixtures import write_contract_fixture
from etps_v02 import conformance
from etps_v02.workload import encode, sha


class ConformanceTests(unittest.TestCase):
    def fixture(self, case="active"):
        folder = tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-contract-")
        self.addCleanup(folder.cleanup)
        return write_contract_fixture(Path(folder.name), case)

    def mutate(self, bundle, item, member, change):
        path = bundle.parent / item[member]
        data = json.loads(path.read_bytes())
        change(data)
        path.write_bytes(encode(data))

    def rules(self, report):
        return {r["rule_id"] for r in report["violations"]}

    def assert_content_free(self, report, *canaries):
        self.assertEqual(set(report), {"schema", "tasks_checked", "fields_checked", "violation_count", "violations"})
        self.assertEqual(report["schema"], "etps-conformance-v1")
        for row in report["violations"]:
            self.assertEqual(set(row), {"task_id", "field_name", "rule_id", "count"})
        raw = json.dumps(report)
        for canary in canaries + ("SYNTHETIC_A", "SYNTHETIC-p0", "SYNTHETIC-m0"):
            self.assertNotIn(canary, raw)

    def test_valid_synthetic_states_and_retry_are_read_only(self):
        for case in ("active", "expired", "unresolved", "settled", "missing", "retry"):
            with self.subTest(case=case):
                bundle, _, _ = self.fixture(case)
                before = {p.name: p.read_bytes() for p in bundle.parent.iterdir()}
                report = conformance.check_bundle(bundle)
                self.assertEqual(report["violation_count"], 0, report)
                self.assertEqual(report["tasks_checked"], 1)
                self.assertGreater(report["fields_checked"], 0)
                self.assertEqual(before, {p.name: p.read_bytes() for p in bundle.parent.iterdir()})
                self.assert_content_free(report)

    def test_content_free_status_null_id_and_duplicate_set_failures(self):
        bundle, index, _ = self.fixture()
        def change(keys):
            next(iter(keys.values())).update(status="CANARY_BAD_LABEL", answer="null",
                source="[CANARY_ID]", values=["CANARY_SET", "CANARY_SET"])
        self.mutate(bundle, index["tasks"][0], "keys", change)
        report = conformance.check_bundle(bundle)
        self.assertTrue({"R1-STATUS", "R1-TYPED-NULL", "R1-BARE-ID", "R1-SET-DUPLICATE", "R1-KEY-BINDING"} <= self.rules(report))
        self.assert_content_free(report, "CANARY_BAD_LABEL", "CANARY_ID", "CANARY_SET")

    def test_labels_types_sets_and_active_null(self):
        bundle, index, _ = self.fixture()
        item = index["tasks"][0]
        def side(data):
            data["records"][0]["status_values"]["active"] = "CANARY_ALIAS"
            data["records"][0]["versions"][0]["value"] = None
        self.mutate(bundle, item, "sidecar", side)
        self.mutate(bundle, item, "keys", lambda d: next(iter(d.values())).update(status="missing_information", values=True, answer=2.5))
        report = conformance.check_bundle(bundle)
        self.assertTrue({"R1-LABEL", "R1-STATUS", "R1-SET-FORM", "R1-TYPE", "R1-ACTIVE-NULL"} <= self.rules(report))
        self.assert_content_free(report, "CANARY_ALIAS")

    def test_expired_null_set_and_source_projections(self):
        bundle, index, _ = self.fixture("expired")
        self.mutate(bundle, index["tasks"][0], "keys", lambda d: list(d.values())[-1].update(
            answer="", values=["CANARY_HISTORICAL"], source="null"))
        report = conformance.check_bundle(bundle)
        self.assertTrue({"R1-TYPED-NULL", "R1-SET-PROJECTION", "R1-ID-PROJECTION"} <= self.rules(report))
        self.assert_content_free(report, "CANARY_HISTORICAL")

    def test_missing_designation_rejects_previously_supplied_item(self):
        bundle, index, _ = self.fixture("missing")
        def change(side):
            side["records"][1]["versions"] = side["records"][0]["versions"]
        self.mutate(bundle, index["tasks"][0], "sidecar", change)
        self.assertIn("R1-MISSING-DESIGNATION", self.rules(conformance.check_bundle(bundle)))

    def test_bool_is_not_integer_and_set_type_is_strict(self):
        bundle, index, declaration = self.fixture()
        fields = next(iter(declaration["tasks"].values()))["questions"]["SYNTHETIC-p0"]["fields"]
        fields["answer"]["value_type"] = "integer"
        fields["values"]["value_type"] = "integer"
        (bundle.parent / "question-contract.json").write_bytes(encode(declaration))
        self.mutate(bundle, index["tasks"][0], "keys", lambda d: next(iter(d.values())).update(answer=True, values=[True, 1]))
        self.assertIn("R1-TYPE", self.rules(conformance.check_bundle(bundle)))

    def test_descriptor_coverage_set_declaration_and_key_fields(self):
        for mutation, rule in (("coverage", "R1-DESCRIPTOR"), ("set", "R1-SET-DECLARATION"), ("keys", "R1-KEY-FIELDS")):
            with self.subTest(mutation=mutation):
                bundle, index, declaration = self.fixture("retry")
                if mutation == "coverage":
                    del next(iter(declaration["tasks"].values()))["questions"]["SYNTHETIC-retry"]
                    (bundle.parent / "question-contract.json").write_bytes(encode(declaration))
                elif mutation == "set":
                    self.mutate(bundle, index["tasks"][0], "manifest", lambda d: d["nodes"]["SYNTHETIC-p0"].update(set_fields=[]))
                else:
                    self.mutate(bundle, index["tasks"][0], "keys", lambda d: d.pop("SYNTHETIC-p0"))
                self.assertIn(rule, self.rules(conformance.check_bundle(bundle)))

    def test_absent_legacy_unknown_or_unbound_contract_is_not_opted_in(self):
        for mode in ("absent", "legacy", "unknown", "binding"):
            with self.subTest(mode=mode):
                bundle, _, declaration = self.fixture()
                path = bundle.parent / "question-contract.json"
                if mode == "absent":
                    path.unlink()
                else:
                    if mode == "legacy":
                        declaration.update(question_contract_version="legacy-v1", tasks={})
                    elif mode == "unknown":
                        declaration["question_contract_version"] = "CANARY_VERSION"
                    else:
                        declaration["bundle_sha256"] = "0" * 64
                    path.write_bytes(encode(declaration))
                report = conformance.check_bundle(bundle)
                self.assertGreater(report["violation_count"], 0)
                self.assert_content_free(report, "CANARY_VERSION")

    def test_path_boundaries_and_malformed_files_never_echo_content(self):
        for member in ("manifest", "sidecar", "keys"):
            bundle, index, declaration = self.fixture()
            index["tasks"][0][member] = "../CANARY_PATH.json"
            bundle.write_bytes(encode(index))
            declaration["bundle_sha256"] = sha(bundle.read_bytes())
            (bundle.parent / "question-contract.json").write_bytes(encode(declaration))
            report = conformance.check_bundle(bundle)
            self.assertIn("R1-STRUCTURE", self.rules(report))
            self.assert_content_free(report, "CANARY_PATH")
        bundle, index, _ = self.fixture()
        (bundle.parent / index["tasks"][0]["manifest"]).write_bytes(b'{"CANARY_PARSE":')
        report = conformance.check_bundle(bundle)
        self.assertIn("R1-STRUCTURE", self.rules(report))
        self.assert_content_free(report, "CANARY_PARSE")

    def test_cli_success_and_canaries_in_invalid_input_arguments(self):
        bundle, index, _ = self.fixture()
        args = [sys.executable, "-B", "-m", "etps_v02.conformance"]
        result = subprocess.run(args + [str(bundle)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assert_content_free(json.loads(result.stdout))
        self.mutate(bundle, index["tasks"][0], "keys", lambda d: next(iter(d.values())).update(answer="CANARY_VALUE", source="[CANARY_SOURCE]"))
        for extra in ([str(bundle)], [], ["CANARY_MISSING_PATH"], ["--CANARY_FLAG"], ["CANARY_ARG", "CANARY_EXTRA"]):
            result = subprocess.run(args + extra, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, b"")
            self.assert_content_free(json.loads(result.stdout), "CANARY_VALUE", "CANARY_SOURCE", "CANARY_MISSING_PATH", "CANARY_FLAG", "CANARY_ARG", "CANARY_EXTRA")


if __name__ == "__main__":
    unittest.main()
