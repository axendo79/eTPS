"""Public SYNTHETIC kit checks; never discover or read a corpus directory."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.conformance import check_bundle
from etps_v02.intake.authoring import validate_authoring
from etps_v02.intake.authoring_lint import lint_authoring
from etps_v02.intake.corpus_freeze import create_freeze, verify_freeze
from etps_v02.intake.mapper import map_authoring
from etps_v02.intake.state_records_v11 import validate_state_records
from etps_v02.question_contract import render
from etps_v02.workload import decode, encode, sha

REPO = Path(__file__).resolve().parents[1]
KIT = REPO / 'docs/v0.2/authoring-kit'
spec = importlib.util.spec_from_file_location('authoring_kit_check', KIT / 'check_batch.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class AuthoringKitTests(unittest.TestCase):
    def inputs(self, family=None):
        doc = decode((KIT / 'examples/source.json').read_bytes())
        contract = decode((KIT / 'examples/question-contract-input.json').read_bytes())
        if family:
            doc['tasks'] = [t for t in doc['tasks'] if t['family'] == family]
            contract['tasks'] = {t['id']: contract['tasks'][t['id']] for t in doc['tasks']}
        return doc, contract

    def write_inputs(self, root, doc, contract):
        root.mkdir()
        (root / 'source.json').write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        (root / 'question-contract-input.json').write_text(json.dumps(contract, ensure_ascii=False), encoding='utf-8')
        return root

    def family_passes(self, family):
        doc, contract = self.inputs(family)
        raw = encode(doc)
        self.assertEqual(validate_authoring(raw)['brief_version'], 'authoring-brief-v2')
        lint = lint_authoring(raw)
        self.assertEqual(lint['config']['window'], 3)
        self.assertEqual(set(lint['counts']) - kit.OBSERVATIONS, set())
        files = map_authoring(raw)
        index = decode(files['bundle.json'])
        for item in index['tasks']:
            receipt = validate_state_records(decode(files[item['manifest']]), files[item['sidecar']])
            self.assertEqual(receipt['status'], 'validated')
            self.assertFalse(receipt['semantics_verified'])
        for task in doc['tasks']:
            for probe in task['probes']:
                self.assertEqual(probe['wording'], render(contract['tasks'][task['id']]['questions'][probe['id']]))
        contract['bundle_sha256'] = sha(files['bundle.json'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in dict(files, **{'question-contract.json': encode(contract)}).items():
                (root / name).write_bytes(data)
            report = check_bundle(root / 'bundle.json')
        self.assertEqual(report['tasks_checked'], 1)
        self.assertEqual(report['violation_count'], 0, report)

    def test_f1_chain(self): self.family_passes('F1')
    def test_f2_checkpoint_after_lapse(self): self.family_passes('F2')
    def test_f3_change_then_lapse(self): self.family_passes('F3')
    def test_f4_conflict_and_precedence(self): self.family_passes('F4')
    def test_f5_similar_entities(self): self.family_passes('F5')
    def test_f6_early_evidence_distance(self): self.family_passes('F6')
    def test_f7_mixed_and_retry(self): self.family_passes('F7')
    def test_f8_source(self): self.family_passes('F8')
    def test_f9_all_controls(self): self.family_passes('F9')

    def test_batch_cli_counts_and_unchanged_source(self):
        before = {p.name: p.read_bytes() for p in (KIT / 'examples').iterdir()}
        proc = subprocess.run([sys.executable, '-B', str(KIT / 'check_batch.py'), str(KIT / 'examples')],
                              capture_output=True, text=True, cwd=REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stderr, '')
        self.assertEqual(len(proc.stdout.splitlines()), 1)
        result = json.loads(proc.stdout)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['counts'], dict(tasks=9, intakes=9, fields_checked=58,
            lint_findings=23, lint_warnings=0, violations=0))
        self.assertFalse(result['semantics_verified'])
        self.assertFalse(result['token_sizes_verified'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in (KIT / 'examples').iterdir()})

    def test_missing_malformed_and_duplicate_key_are_content_free(self):
        canary = 'SYNTHETIC_PRIVATE_CANARY'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / canary
            doc, contract = self.inputs('F1')
            self.write_inputs(root, doc, contract)
            for raw in (b'{"'+canary.encode()+b'":', b'{"version":1,"version":"'+canary.encode()+b'"}'):
                with self.subTest(raw=raw):
                    (root / 'source.json').write_bytes(raw)
                    out, err = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        code = kit.main([str(root)])
                    self.assertEqual(code, 2)
                    self.assertEqual(err.getvalue(), '')
                    self.assertNotIn(canary, out.getvalue())
                    self.assertEqual(json.loads(out.getvalue())['refusal']['phase'], 'authoring')
            (root / 'source.json').unlink()
            self.assertEqual(kit.check_batch(root)['refusal']['phase'], 'read')

    def test_wording_must_already_equal_public_rendering(self):
        doc, contract = self.inputs('F7')
        doc['tasks'][0]['probes'][1]['wording'] += ' Omitted form on retry.'
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_inputs(Path(directory) / 'input', doc, contract)
            result = kit.check_batch(root, Path(directory) / 'export')
            self.assertEqual(result['refusal']['phase'], 'question_wording')
            self.assertFalse((Path(directory) / 'export').exists())

    def test_descriptor_types_are_checked_by_real_conformance(self):
        doc, contract = self.inputs('F1')
        task = doc['tasks'][0]; probe = task['probes'][0]
        descriptor = contract['tasks'][task['id']]['questions'][probe['id']]
        descriptor['fields']['code']['value_type'] = 'integer'
        probe['wording'] = render(descriptor)
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_inputs(Path(directory) / 'input', doc, contract)
            result = kit.check_batch(root)
        self.assertEqual(result['refusal']['phase'], 'conformance')
        self.assertGreater(result['counts']['violations'], 0)

    def test_intake_rejects_wrong_key_without_echoing_it(self):
        doc, contract = self.inputs('F1')
        doc['tasks'][0]['probes'][0]['expected']['code'] = 'SYNTHETIC_SECRET_WRONG'
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_inputs(Path(directory) / 'input', doc, contract)
            result = kit.check_batch(root)
        self.assertEqual(result['refusal']['phase'], 'mapping')
        self.assertNotIn('SYNTHETIC_SECRET_WRONG', json.dumps(result))

    def test_advisory_lint_findings_are_visible_without_prose(self):
        doc, contract = self.inputs('F1')
        doc['tasks'][0]['conversation'][-1]['text'] += ' tovri-8'
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_inputs(Path(directory) / 'input', doc, contract)
            result = kit.check_batch(root)
        self.assertEqual(result['status'], 'PASS')  # Mirrors advisory lint exit 0.
        self.assertGreater(result['lint_counts']['answer_restated_before_probe'], 0)
        self.assertGreater(result['counts']['lint_warnings'], 0)
        self.assertNotIn('tovri-8', json.dumps(result))

    def test_untrusted_ids_fields_and_prose_never_reach_summary(self):
        doc, contract = self.inputs('F1')
        # Replace task prefixes, field names and fictional values consistently.
        for old, new in [('SYNTHETIC-K01', 'SYNTHETIC_CANARY_ID'),
                         ('"code"', '"SYNTHETIC_CANARY_FIELD"'), ('tovri-8', 'SYNTHETIC_CANARY_VALUE')]:
            doc = decode(encode(doc).replace(old.encode(), new.encode()))
            contract = decode(encode(contract).replace(old.encode(), new.encode()))
        task=doc['tasks'][0]
        for probe in task['probes']:
            probe['wording'] = render(contract['tasks'][task['id']]['questions'][probe['id']])
        with tempfile.TemporaryDirectory() as directory:
            root=self.write_inputs(Path(directory) / 'SYNTHETIC_CANARY_PATH', doc, contract)
            result=kit.check_batch(root)
        self.assertEqual(result['status'], 'PASS')
        self.assertNotIn('SYNTHETIC_CANARY', json.dumps(result))

    def test_dependency_output_exceptions_and_future_codes_are_sanitized(self):
        canary='SYNTHETIC_DEPENDENCY_CANARY'
        def fail(*args, **kwargs):
            print(canary)
            print(canary, file=sys.stderr)
            raise ValueError(canary)
        for target in ('etps_v02.intake.authoring.validate_authoring',
                       'etps_v02.intake.mapper.map_authoring',
                       'etps_v02.intake.state_records_v11.validate_state_records',
                       'etps_v02.intake.authoring_lint.lint_authoring',
                       'etps_v02.conformance.check_bundle'):
            with self.subTest(target=target), patch(target, fail):
                out,err=io.StringIO(),io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code=kit.main([str(KIT / 'examples')])
                self.assertEqual(code, 2)
                self.assertEqual(err.getvalue(), '')
                self.assertNotIn(canary,out.getvalue())
        lint=lint_authoring((KIT / 'examples/source.json').read_bytes())
        lint['findings'].append({'code':canary,'evidence':canary})
        with patch('etps_v02.intake.authoring_lint.lint_authoring',return_value=lint):
            result=kit.check_batch(KIT / 'examples')
        self.assertEqual(result['lint_counts']['unrecognized_lint'],1)
        self.assertNotIn(canary,json.dumps(result))

    def test_export_is_exact_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'new-export'
            result=kit.check_batch(KIT / 'examples',target)
            self.assertEqual(result['status'],'PASS')
            original=(KIT / 'examples/source.json').read_bytes()
            for name,raw in map_authoring(original).items():
                self.assertEqual((target/name).read_bytes(),raw)
            self.assertEqual(check_bundle(target/'bundle.json')['violation_count'],0)
            bound=decode((target/'question-contract.json').read_bytes())
            index=decode((target/'bundle.json').read_bytes())
            for item in index['tasks']:
                manifest=decode((target/item['manifest']).read_bytes())
                for pid,spec in bound['tasks'][item['id']]['questions'].items():
                    self.assertEqual(manifest['nodes']['question:'+pid]['text'],render(spec))
            before={p.name:p.read_bytes() for p in target.iterdir()}
            self.assertEqual(kit.check_batch(KIT/'examples',target)['refusal']['phase'],'export')
            self.assertEqual(before,{p.name:p.read_bytes() for p in target.iterdir()})

    def test_export_remains_rederivable_by_freeze(self):
        # Simulated declarations only; no human review or token receipt is claimed.
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'export'
            self.assertEqual(kit.check_batch(KIT/'examples',target)['status'],'PASS')
            files={p.name:p.read_bytes() for p in target.iterdir()}
            index=decode(files['bundle.json'])
            files['authoring-brief.md']=(REPO/'docs/v0.2/AUTHORING_BRIEF_V2.md').read_bytes()
            files['authorship.json']=encode(dict(version='author-session-v1',author='SYNTHETIC author',model='SYNTHETIC model',
                session='SYNTHETIC session',date='SYNTHETIC date',affiliations=['SYNTHETIC test'],prior_exposure=dict(
                declarant='SYNTHETIC declarant',date='SYNTHETIC date',corpus_version='SYNTHETIC release',prior_runs='unknown',
                known_runs=[],inspection='SYNTHETIC software fixture; implementation exposed',revisions=[])))
            files['settings.json']=encode(dict(version='corpus-settings-v1',dataset='development',counts=index['counts'],
                parameters={'synthetic_only':True,'token_sizes_verified':False},development_freeze_sha256=None))
            files['review.json']=encode(dict(version='corpus-review-v1',reviewer='SYNTHETIC simulated declaration',date='SYNTHETIC date',
                obligations_answer_keys_cross_checked=True,defects=[],artifacts={n:sha(r) for n,r in files.items()}))
            receipt=create_freeze(files,'SYNTHETIC release','development','SYNTHETIC time')
            self.assertEqual(verify_freeze(files,receipt)['status'],'verified')

    def test_cli_usage_is_content_free(self):
        for args in ([], ['--SYNTHETIC_CANARY'], ['input','--bad','SYNTHETIC_CANARY']):
            out,err=io.StringIO(),io.StringIO()
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                code=kit.main(args)
            self.assertEqual(code,2)
            self.assertEqual(err.getvalue(),'')
            self.assertNotIn('SYNTHETIC_CANARY',out.getvalue())

    def test_placeholder_template_is_not_admitted_as_a_task(self):
        result=kit.check_batch(KIT/'template')
        self.assertEqual(result['status'],'REFUSED')
        # Templates contain only fill-in strings, never substitute corpus defaults.
        source=(KIT/'template/source.json').read_text(encoding='utf-8')
        self.assertIn('<task>-m001',source)
        self.assertIn('<exact string in force>',source)


if __name__=='__main__':
    unittest.main()
