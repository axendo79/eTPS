"""Scripted human coding of synthetic fixtures; no services or browsers."""
import base64
import copy
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import adapter_openai
from etps_v02.manual_runner import EVIDENCE, run_manual
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export, replay_slot, report
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import INVALIDATION_POLICY, encode, sha, validate_bundle
from test_v02_live_adapter import manifest
from test_v02_field_routing import fields_manifest


def manual_bundle(task=None):
    raw = encode(task or manifest())
    rubric = b'Model-authored synthetic rubric: code the stated answer; do not repair it.\n'
    p = {"schema": "etps-manual-plan-v1", "purpose": "dev-manual", "unit": "utf8_bytes",
         "invalidation_policy": INVALIDATION_POLICY, "tasks": {"task": sha(raw)},
         "arms": {"manual": {"provider": "manual", "service": "synthetic service", "coder": "operator-test",
                             "coding_rubric_sha256": sha(rubric)}},
         "slots": [{"id": "slot", "arm": "manual", "task": "task"}]}
    return p, {sha(raw): raw, sha(rubric): rubric}


def paste(coded=b'{"answer":"expected-private-marker"}', raw=b'Unstructured reply\r\nsecond line\n', confirm=b'yes'):
    return raw + b'<<<END_ETPS_REPLY>>>\n' + coded + b'\n' + confirm + b'\n'


class ManualDevTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def create(self, task=None):
        self.count += 1
        p, a = manual_bundle(task)
        store = Store.create(Path(self.temp.name) / (str(self.count) + '.db'), encode(p), a)
        self.addCleanup(store.close)
        return store

    def run_script(self, store, script):
        output = io.StringIO()
        with patch.object(adapter_openai, 'send', side_effect=AssertionError('manual network')):
            result = run_manual(store, 'slot', allow_manual=True, stdin=io.BytesIO(script), stdout=output)
        return result, output.getvalue()

    def test_opt_in_and_schema_rubric_binding(self):
        store = self.create()
        with self.assertRaisesRegex(InvalidRecord, '--allow-manual'):
            run_manual(store, 'slot')
        self.assertEqual(store.entries('slot'), [])
        p, a = manual_bundle()
        for extra in ({'endpoint': 'http://127.0.0.1'}, {'temperature': 0}, {'provider': 'anthropic'}):
            q = copy.deepcopy(p)
            q['arms']['manual'].update(extra)
            with self.assertRaises(InvalidRecord):
                validate_bundle(encode(q), a)
        del a[p['arms']['manual']['coding_rubric_sha256']]
        with self.assertRaisesRegex(InvalidRecord, 'rubric'):
            validate_bundle(encode(p), a)

    def test_verbatim_reply_exact_message_file_and_human_coding(self):
        store = self.create()
        raw = b'Not JSON; independently coded.\r\nUnicode: \xc3\xa9\n'
        result, output = self.run_script(store, paste(raw=raw))
        self.assertTrue(result['score']['accepted'])
        self.assertIsNone(result['score']['TPS'])
        self.assertIsNone(result['score']['experimental_eTPS'])
        event = result['record']['events'][-1]
        self.assertEqual(base64.b64decode(event['raw_base64']), raw)
        self.assertEqual(event['coder'], 'operator-test')
        self.assertTrue(event['confirmed'])
        self.assertIn('next: pass', output)
        message = next(store.path.parent.glob(store.path.stem + '-messages/*/*.txt'))
        self.assertEqual(message.read_bytes(), manifest()['nodes']['intro']['text'].encode())
        self.assertEqual(result['wall_time_kind'], 'operator-paced')
        self.assertFalse(result['coding_correctness_verified'])
        self.assertGreaterEqual(result['operator_wall_seconds'], 0)

    def test_all_coded_outcomes_and_retained_failures(self):
        task = manifest()
        task['nodes']['p']['unknown_answers'] = [{'status': 'unknown'}]
        for coded, outcome in ((b'{"answer":"wrong"}', 'incorrect'), (b'not-json', 'malformed'),
                                (b'{"status":"unknown"}', 'unknown'), (b'timeout', 'timeout')):
            with self.subTest(outcome=outcome):
                store = self.create(task)
                result, _ = self.run_script(store, paste(coded))
                self.assertEqual(result['score']['classifications'][-1]['class'], outcome)
                self.assertEqual(result['state'], 'finished')
                self.assertFalse(result['score']['accepted'])
                self.assertTrue(result['score']['measurement_valid'])
                self.assertEqual(report(store)['dev_manual']['failed'], 1)

    def test_confirmation_refusal_and_input_failure_are_harness_faults(self):
        store = self.create()
        result, _ = self.run_script(store, paste(confirm=b'no'))
        self.assertEqual(result['reason_code'], 'operator_abort')
        self.assertFalse(result['score']['measurement_valid'])
        self.assertEqual([r['kind'] for r in store.entries('slot')], ['start', 'event', 'request', 'abort'])
        store = self.create()
        with self.assertRaises(InvalidRecord):
            self.run_script(store, b'partial reply\n')
        self.assertEqual(replay_slot(store, 'slot')['reason_code'], 'execution_error')
        self.assertEqual(report(store)['dev_manual']['failed'], 0)
        self.assertEqual(report(store)['dev_manual']['rr_unavailable_attempted'], 1)

    def test_field_routing_and_replay_exports_fenced(self):
        store = self.create(fields_manifest())
        result, _ = self.run_script(store, paste(b'{"a":8,"b":"nine"}') + paste(b'{"a":7,"b":"nine"}'))
        self.assertTrue(result['score']['accepted'])
        self.assertEqual([e['node'] for e in result['record']['events']], ['intro', 'p', 'r-a', 'retry'])
        for fmt in ('v1', 'v2'):
            exported = export_bundle(store, fmt)
            self.assertEqual(exported['evidence'], EVIDENCE)
            self.assertTrue(exported['publish_excluded'])
            r = replay_export(exported)
            self.assertEqual(r['dev_manual']['trials'][0], result)
            self.assertEqual(r['summaries'], [])
            self.assertEqual(r['trials'], [])
            self.assertEqual(r['dev_manual']['evidence'], EVIDENCE)
            self.assertFalse(r['coding_correctness_verified'])
            for audience in ('leaderboard', 'website'):
                with self.assertRaisesRegex(InvalidRecord, 'excluded'):
                    export_bundle(store, fmt, audience=audience)

    def test_unattempted_and_aborted_trials_stay_labeled(self):
        store = self.create()
        self.assertEqual(report(store)['dev_manual']['trials'][0]['evidence'], EVIDENCE)
        self.run_script(store, paste(confirm=b'no'))
        self.assertTrue(replay_export(export_bundle(store, 'v2'))['publish_excluded'])

    def test_rehashed_coded_answer_tampering_rejected(self):
        store = self.create()
        self.run_script(store, paste())
        exported = export_bundle(store)
        rows = exported['journal']['slot']
        for row in rows:
            if row['payload'].get('kind') == 'probe':
                row['payload']['answer'] = {'answer': 'tampered'}
        previous = sha(encode([exported['plan_sha256'], 'slot']))
        for i, row in enumerate(rows):
            previous = sha(encode(['slot', i, row['kind'], previous]) + encode(row['payload']))
            row['sha256'] = previous
        with self.assertRaisesRegex(InvalidRecord, 'projection'):
            replay_export(exported)

    def test_cli_manual_gate_scripted_stdin_and_publication_refusal(self):
        store = self.create()
        args = [sys.executable, '-B', '-m', 'etps_v02']
        denied = subprocess.run(args + ['run', str(store.path), '--slot', 'slot'], capture_output=True)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(store.entries('slot'), [])
        run = subprocess.run(args + ['run', str(store.path), '--slot', 'slot', '--allow-manual'],
                             input=paste(), capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        self.assertIn(EVIDENCE.encode(), run.stdout)
        for audience in ('leaderboard', 'website'):
            out = Path(self.temp.name) / (audience + '.json')
            child = subprocess.run(args + ['export', str(store.path), '--output', str(out), '--audience', audience], capture_output=True)
            self.assertEqual(child.returncode, 2)
            self.assertFalse(out.exists())

    def test_unknown_user_payload_is_protocol_deviation_not_wrong_answer(self):
        store = self.create()
        self.run_script(store, paste())
        exported = export_bundle(store)
        rows = exported['journal']['slot']
        for row in rows:
            if row['payload'].get('kind') == 'user':
                row['payload']['text'] = 'Unplanned synthetic input'
        previous = sha(encode([exported['plan_sha256'], 'slot']))
        for i, row in enumerate(rows):
            previous = sha(encode(['slot', i, row['kind'], previous]) + encode(row['payload']))
            row['sha256'] = previous
        result = replay_export(exported)['dev_manual']['trials'][0]
        self.assertFalse(result['score']['measurement_valid'])
        self.assertEqual(result['score']['reason'], 'unmatched_user_payload')

    def test_message_file_fault_invalidates_instead_of_charging_model(self):
        store = self.create()
        with patch.object(Path, 'mkdir', side_effect=OSError('synthetic file fault')):
            with self.assertRaises(OSError):
                self.run_script(store, paste())
        result = replay_slot(store, 'slot')
        self.assertEqual(result['reason_code'], 'storage_error')
        self.assertFalse(result['score']['measurement_valid'])
        self.assertEqual(report(store)['dev_manual']['failed'], 0)
