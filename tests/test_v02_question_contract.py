"""SYNTHETIC public-only rendering and opt-in declaration checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from question_contract_fixtures import write_contract_fixture
from etps_v02 import question_contract as contract
from etps_v02.scorer import classify_probe
from etps_v02.response_extraction import project_reply
from etps_v02.workload import encode, sha


class QuestionContractTests(unittest.TestCase):
    def fixture(self, case="active"):
        folder = tempfile.TemporaryDirectory(prefix="etps-SYNTHETIC-wording-")
        self.addCleanup(folder.cleanup)
        return write_contract_fixture(Path(folder.name), case)

    def test_absent_and_explicit_legacy_do_not_render(self):
        bundle, index, declaration = self.fixture()
        path = bundle.parent / contract.FILENAME
        path.unlink()
        self.assertIsNone(contract.read_release(bundle.parent, sha(bundle.read_bytes())))
        declaration.update(question_contract_version=contract.LEGACY_VERSION, tasks={})
        path.write_bytes(encode(declaration))
        self.assertIsNone(contract.read_release(bundle.parent, sha(bundle.read_bytes())))
        manifest = json.loads((bundle.parent / index["tasks"][0]["manifest"]).read_bytes())
        before = encode(manifest)
        self.assertEqual(contract.apply({"question_contract": None}, index["tasks"][0], manifest), [])
        self.assertEqual(encode(manifest), before)

    def test_unknown_version_binding_duplicate_keys_and_closed_schema_refuse(self):
        for mode in ("version", "binding", "extra", "duplicate"):
            bundle, _, declaration = self.fixture()
            if mode == "version":
                declaration["question_contract_version"] = "future-unknown"
            elif mode == "binding":
                declaration["bundle_sha256"] = "0" * 64
            elif mode == "extra":
                declaration["expected"] = "CANARY_ANSWER"
            raw = encode(declaration)
            if mode == "duplicate":
                raw = raw[:-1] + b',"tasks":{}}'
            (bundle.parent / contract.FILENAME).write_bytes(raw)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                contract.read_release(bundle.parent, sha(bundle.read_bytes()))

    def test_all_questions_and_retries_only_change_question_user_nodes(self):
        bundle, index, _ = self.fixture("retry")
        release = contract.read_release(bundle.parent, sha(bundle.read_bytes()))
        item = index["tasks"][0]
        raw_side = (bundle.parent / item["sidecar"]).read_bytes()
        manifest = json.loads((bundle.parent / item["manifest"]).read_bytes())
        before = copy.deepcopy(manifest)
        prompts = contract.apply({"question_contract": release, "tasks": index["tasks"],
                                  "files": {item["sidecar"]: raw_side}}, item, manifest)
        self.assertEqual(len(prompts), 2)
        for pid, spec in release["declaration"]["tasks"][item["id"]]["questions"].items():
            node = "question:" + pid
            self.assertEqual(manifest["nodes"][node]["text"], contract.render(spec))
            self.assertEqual(manifest["nodes"][node]["sha256"], sha(contract.render(spec).encode()))
            before["nodes"][node] = manifest["nodes"][node]
        self.assertEqual(manifest, before)

    def test_expected_values_and_unknown_types_cannot_enter_renderer(self):
        spec = {"core": "SYNTHETIC question", "fields": {"answer": {"kind": "scalar", "value_type": "string", "point": "now"}}}
        rendered = contract.render(spec)
        self.assertNotIn("CANARY_ANSWER", rendered)
        spec["expected"] = {"answer": "CANARY_ANSWER"}
        with self.assertRaises(ValueError):
            contract.render(spec)
        del spec["expected"]
        spec["fields"]["answer"]["value_type"] = "boolean"
        with self.assertRaises(ValueError):
            contract.render(spec)

    def test_missing_checkpoint_and_other_slots(self):
        _, _, declaration = self.fixture("missing")
        spec = next(iter(next(iter(declaration["tasks"].values()))["questions"].values()))
        text = contract.render(spec)
        self.assertIn('"missing_information" only', text)
        self.assertNotIn('use only "active"', text)
        del spec["fields"]["missing_item"]
        self.assertNotIn("<identifier", contract.render(spec))
        self.assertNotIn(": exact declared item ID", contract.render(spec))
        text = contract.render({"core": "SYNTHETIC question", "fields": {
            "old": {"kind": "scalar", "value_type": "string", "point": "just after public message SYNTHETIC-m0"},
            "ref": {"kind": "other", "id_kind": "message", "null_rule": "JSON null if no matching event exists."}}})
        self.assertIn("just after public message SYNTHETIC-m0", text)
        self.assertIn("JSON null if no matching event exists.", text)

    def test_descriptor_checkpoint_kind_and_coverage_mismatch_refuse(self):
        for mode in ("point", "kind", "field", "probe", "task"):
            bundle, index, declaration = self.fixture()
            questions = next(iter(declaration["tasks"].values()))["questions"]
            spec = next(iter(questions.values()))
            if mode == "point":
                spec["fields"]["old"]["point"] = "now"
            elif mode == "kind":
                spec["fields"]["source"] = {"kind": "set", "value_type": "string"}
            elif mode == "field":
                spec["fields"]["extra"] = spec["fields"].pop("answer")
            elif mode == "probe":
                questions["SYNTHETIC-extra"] = copy.deepcopy(spec)
            else:
                declaration["tasks"]["SYNTHETIC-extra"] = copy.deepcopy(next(iter(declaration["tasks"].values())))
            (bundle.parent / contract.FILENAME).write_bytes(encode(declaration))
            item = index["tasks"][0]
            release = contract.read_release(bundle.parent, sha(bundle.read_bytes()))
            manifest = json.loads((bundle.parent / item["manifest"]).read_bytes())
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                contract.apply({"question_contract": release, "tasks": index["tasks"],
                    "files": {item["sidecar"]: (bundle.parent / item["sidecar"]).read_bytes()}}, item, manifest)

    def test_existing_digit_string_tolerance_and_fences_are_unchanged(self):
        text = contract.render({"core": "SYNTHETIC count question", "fields": {
            "count": {"kind": "scalar", "value_type": "integer", "point": "now"}}})
        self.assertIn("JSON integer", text)
        manifest = {"answer_schema": "typed-v1", "answer_tolerance": "d10-v1"}
        probe = {"expected": {"count": 7}, "unknown_answers": []}
        self.assertEqual(classify_probe(manifest, probe, {"status": "ok", "answer": {"count": "7"}}), "correct")
        self.assertEqual(project_reply(b'```json\n{"count":"7"}\n```', "typed-v1", "fence-v1")[0], {"count": "7"})

    def test_documented_slots_are_exact_and_brief_has_the_same_status_rules(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/v0.2/ANSWER_CONTRACT.md").read_text(encoding="utf-8")
        for slot in contract.TEMPLATES.values():
            self.assertIn("> " + slot, text)
        brief = (root / "docs/v0.2/AUTHORING_BRIEF_V2.md").read_text(encoding="utf-8")
        for term in ("h3-compressed-v1", "`active`", "`expired`", "`unestablished`", "`unresolved`", "list only `missing_information`"):
            self.assertIn(term, brief)


if __name__ == "__main__":
    unittest.main()
