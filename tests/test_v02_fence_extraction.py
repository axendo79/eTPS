"""Frozen extraction rules and loopback-only live/replay regressions."""
import base64
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.response_extraction import fence_v1, project_reply
from etps_v02.runner import answer_from_raw, export_bundle, replay_export, report
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode, sha, validate_bundle
from test_v02_live_adapter import FakeServer, bundle


class FenceExtractionTests(unittest.TestCase):
    def test_exact_fences_and_ascii_whitespace(self):
        for raw in (b'```json\n{"v":5}\n```', b'```\n{"v":5}\n```',
                    b' \t\r\n\v\f```json   \r\n {"v":5}\r\n```\r\n \t',
                    b'```   \n{"v":5}\n```', b'```\n```'):
            with self.subTest(raw=raw):
                body, applied = fence_v1(raw)
                self.assertTrue(applied)
                self.assertEqual(project_reply(raw, 'typed-v1', 'fence-v1'),
                                 (answer_from_raw(body, 'typed-v1'), True))
        self.assertEqual(project_reply(b'```json\n{"v":5}\n```', 'typed-v1', 'fence-v1'), ({'v':5}, True))

    def test_no_partial_embedded_multiple_or_tag_normalization(self):
        block = b'```json\n{"v":5}\n```'
        for raw in (b'prose\n'+block, block+b'\nprose', block+b'\n'+block,
                    b'```python\n{"v":5}\n```', b'```JSON\n{"v":5}\n```',
                    b'```json\t\n{"v":5}\n```', b'```json\n{"v":5}',
                    b'```json {"v":5}```', b'````\n{"v":5}\n````',
                    b'```\n{"v":5}\n ```', b'\xc2\xa0'+block,
                    b'```\n{"v":5}\n```json\n{}\n```', b' {"v":5} '):
            with self.subTest(raw=raw):
                self.assertEqual(fence_v1(raw), (raw, False))
                self.assertEqual(project_reply(raw, 'typed-v1', 'fence-v1'),
                                 (answer_from_raw(raw, 'typed-v1'), False))

    def test_body_projection_is_existing_schema_not_repaired(self):
        for body in (b'bad JSON', b'{"v":true}', b'{"v":[5]}', b'{"v":5.0}'):
            self.assertEqual(project_reply(b'```json\n'+body+b'\n```', 'typed-v1', 'fence-v1'), (None, True))
        self.assertEqual(project_reply(b'```\n{"v":5}\n```', None, 'fence-v1'), (None, True))
        self.assertEqual(project_reply(b'```\n{"v":"```"}\n```', None, 'fence-v1'), ({'v':'```'}, True))

    def test_rule_is_live_only_and_version_checked(self):
        p, a = bundle('http://127.0.0.1:1')
        for value in ('fence-v2', None, False, {}):
            p['response_extraction'] = value
            with self.assertRaisesRegex(InvalidRecord, 'response_extraction'):
                validate_bundle(encode(p), a)
        from test_v02_manual_dev import manual_bundle
        p, a = manual_bundle()
        p['response_extraction'] = 'fence-v1'
        with self.assertRaisesRegex(InvalidRecord, 'plan fields'):
            validate_bundle(encode(p), a)
        from test_v02_runner import bundle as offline_bundle
        from etps_v02.workload import decode
        raw, a = offline_bundle()
        p = decode(raw)
        p['response_extraction'] = 'fence-v1'
        with self.assertRaisesRegex(InvalidRecord, 'plan fields'):
            validate_bundle(encode(p), a)

    def test_live_round_trip_raw_bytes_and_all_providers(self):
        content = ' \t```json  \r\n{"answer":"expected-private-marker"}\r\n```\r\n'
        for provider in ('openai-compatible', 'anthropic', 'lmstudio-native'):
            with self.subTest(provider=provider), FakeServer(provider, content=content) as server, tempfile.TemporaryDirectory() as temp:
                p, a = bundle(server.url, provider, response_extraction='fence-v1')
                store = Store.create(Path(temp)/'test.db', encode(p), a)
                try:
                    r = run_live(store, 'slot', allow_live=True)
                    self.assertTrue(r['score']['accepted'])
                    event = r['record']['events'][-1]
                    self.assertTrue(event['extracted'])
                    self.assertEqual(base64.b64decode(event['raw_base64']), content.encode())
                    for fmt in ('v1','v2'):
                        self.assertEqual(replay_export(export_bundle(store, fmt))['trials'][0], r)
                finally:
                    store.close()

    def test_absent_rule_keeps_strict_records_and_report_shape(self):
        content = '```json\n{"answer":"expected-private-marker"}\n```'
        with FakeServer(content=content) as server, tempfile.TemporaryDirectory() as temp:
            p, a = bundle(server.url)
            store = Store.create(Path(temp)/'test.db', encode(p), a)
            try:
                r = run_live(store, 'slot', allow_live=True)
                self.assertEqual(r['score']['classifications'][-1]['class'], 'malformed')
                self.assertNotIn('extracted', r['record']['events'][-1])
                self.assertNotIn('strict_json_rate', report(store))
                self.assertEqual(replay_export(export_bundle(store))['trials'][0], r)
            finally:
                store.close()

    def test_extraction_routes_without_changing_public_assistant_history(self):
        from test_v02_field_routing import fields_manifest
        content = '```json\n{"a":8,"b":"nine"}\n```'
        with FakeServer(content=content) as server, tempfile.TemporaryDirectory() as temp:
            p, _ = bundle(server.url, response_extraction='fence-v1')
            raw = encode(fields_manifest())
            p['tasks'] = {'synthetic-task':sha(raw)}
            store = Store.create(Path(temp)/'test.db', encode(p), {sha(raw):raw})
            try:
                r = run_live(store,'slot',allow_live=True)
                self.assertTrue(r['score']['measurement_valid'])
                self.assertEqual([e['node'] for e in r['record']['events']], ['intro','p','r-a','retry'])
                assistants = [m['content'] for m in server.seen[1][1]['messages'] if m['role']=='assistant']
                self.assertEqual(assistants, [content])
                self.assertEqual(replay_export(export_bundle(store,'v2'))['trials'][0], r)
            finally:
                store.close()

    def test_strict_json_rate_counts_ok_only_per_arm(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as temp:
            servers = [stack.enter_context(FakeServer(content='{"answer":"wrong"}')),
                       stack.enter_context(FakeServer(content='```\n{"answer":"expected-private-marker"}\n```')),
                       stack.enter_context(FakeServer(content='not JSON')),
                       stack.enter_context(FakeServer(status=500))]
            p, a = bundle(servers[0].url, response_extraction='fence-v1')
            arm = p['arms']['private-arm-label']
            p['arms'] = {str(i): {**arm, 'endpoint': s.url} for i,s in enumerate(servers)}
            p['arms']['unused'] = dict(arm)
            p['slots'] = [{'id':str(i), 'arm':str(j), 'task':'synthetic-task'} for i,j in enumerate((0,0,1,2,3))]
            store = Store.create(Path(temp)/'test.db', encode(p), a)
            try:
                for slot in p['slots']:
                    run_live(store, slot['id'], allow_live=True)
                r = report(store)
                self.assertEqual(r['strict_json_rate'], {
                    '0': {'numerator':2,'denominator':2,'value':Fraction(1)},
                    '1': {'numerator':0,'denominator':1,'value':Fraction(0)},
                    '2': {'numerator':0,'denominator':1,'value':Fraction(0)},
                    '3': {'numerator':0,'denominator':0,'value':None},
                    'unused': {'numerator':0,'denominator':0,'value':None}})
                self.assertEqual(r['accepted'], 1)  # Strictly valid wrong answers still count diagnostically.
                self.assertFalse(r['trials'][-1]['record']['events'][-1]['extracted'])
                self.assertEqual(replay_export(export_bundle(store,'v2'))['strict_json_rate'], r['strict_json_rate'])
            finally:
                store.close()

    def test_rehashed_extracted_flag_tampering_detected(self):
        with FakeServer(content='```\n{"answer":"expected-private-marker"}\n```') as server, tempfile.TemporaryDirectory() as temp:
            p,a = bundle(server.url, response_extraction='fence-v1')
            store = Store.create(Path(temp)/'test.db', encode(p), a)
            try:
                run_live(store,'slot',allow_live=True)
                original = export_bundle(store)
            finally:
                store.close()
        for value in (False, 1, None, 'missing'):
            exported = copy.deepcopy(original)
            rows = exported['journal']['slot']
            event = next(r['payload'] for r in rows if r['payload'].get('kind')=='probe')
            if value == 'missing':
                del event['extracted']
            else:
                event['extracted'] = value
            previous = sha(encode([exported['plan_sha256'],'slot']))
            for i,row in enumerate(rows):
                previous = sha(encode(['slot',i,row['kind'],previous])+encode(row['payload']))
                row['sha256'] = previous
            with self.assertRaisesRegex(InvalidRecord,'extraction flag'):
                replay_export(exported)
