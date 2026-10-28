"""Pure source-extracted counterexample; no package imports, stores or transport.

Reads only four hash-pinned Python sources. Executes explicitly selected AST
definitions with stdlib dependencies; all response bytes and rows are synthetic.
The workload helpers are called with admission=False exactly as project does.
This proves projection behavior, not HTTP dispatch or durable journal behavior.
"""
import argparse
import ast
import base64
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

PINS = {
    'scorer.py': '299e74d020fb5b894b19781fd8c05ada5409d3c3cda884dd7ae02e1a8396f07a',
    'workload.py': '893c542b475e85576d5dba226891e99f721654eec606f19d31537d1489c1ac06',
    'memory_telemetry.py': 'b6fe8cd739c0d921b1ec5fba6d1a2b7a42f63dede2dfe6ab071cb73925316870',
    'session_profile.py': '6436fb75ea64ddee7ca2191e0275fdd4f9eb72cd90ca60bdf3dd3af440c89864',
}


def definitions(source, filename, names, namespace):
    raw = (source / filename).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[filename]:
        raise ValueError('source_pin_changed:' + filename)
    tree = ast.parse(raw, filename=str(source / filename))
    selected = []
    found = set()
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else (
            node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) else None)
        if name in names:
            selected.append(node)
            found.add(name)
    if found != set(names):
        raise ValueError('missing_definition:' + filename)
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(source / filename), 'exec'), namespace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True,
                        help='eTPS repository root containing hash-pinned etps_v02 source')
    parser.add_argument('--output', type=Path, required=True,
                        help='new JSON output path; existing files are never overwritten')
    args = parser.parse_args()
    source = args.repo_root.resolve() / 'etps_v02'
    target = args.output.resolve()
    if target.exists():
        raise ValueError('output_must_be_absent')
    scope = {'base64': base64, 'json': json, 'math': math, 'Fraction': Fraction}
    definitions(source, 'scorer.py', {'InvalidRecord', 'require', 'integer'}, scope)
    definitions(source, 'workload.py', {'encode', 'decode', 'raw_response'}, scope)
    definitions(source, 'memory_telemetry.py', {'KEYS', 'numeric', 'project', 'requests', 'summarize'}, scope)
    definitions(source, 'session_profile.py', {'processing_requests', 'completion_requests', 'processing_totals', 'total'}, scope)
    project, requests, summarize = (scope[k] for k in ('project', 'requests', 'summarize'))
    encode, decode = scope['encode'], scope['decode']
    known = {'extraction_calls': 1, 'extraction_prompt_tokens': 8,
             'extraction_completion_tokens': 4, 'extraction_seconds': 0.25,
             'beliefs_injected': 1, 'injected_chars': 10, 'facts_rejected': 0}

    def response(metrics, status=502):
        raw = encode({'error': {'code': 'synthetic_invalid_reply'}, 'x_nyx_bridge': metrics})
        r = {'http_status': status, 'http_body_base64': base64.b64encode(raw).decode('ascii'),
             'http_body_sha256': hashlib.sha256(raw).hexdigest(), 'status': 'timeout' if status == 502 else 'ok',
             'raw_base64': '', 'usage': None}
        before = dict(r)
        projected = project(r, 'x_nyx_bridge')
        assert r == before, 'projection mutated raw evidence'
        assert hashlib.sha256(base64.b64decode(r['http_body_base64'])).hexdigest() == r['http_body_sha256']
        assert decode(base64.b64decode(r['http_body_base64']), admission=False)['x_nyx_bridge'] == metrics
        return {**r, **projected}

    results = []
    flat = response(known)
    assert flat['memory_telemetry_status'] == 'valid' and flat['memory_telemetry'] == known
    results.append({'case': 'flat_scalar_control', 'projection': 'valid', 'raw_cost_retained': True})
    for case, addition in (
            ('nested_receipts', {'ingestions': [{'status': 'accepted', 'cached': False}]}),
            ('boolean_status', {'memory_complete': True}),
            ('composite_v2_shape', {'ingestions': [{'status': 'accepted', 'cached': False}], 'memory_complete': True})):
        r = response({**known, **addition})
        assert r['memory_telemetry_status'] == 'invalid' and r['memory_telemetry'] is None
        summary = summarize([{'status': 'invalid', 'value': None}])
        assert summary['invalid_count'] == 1 and summary['request_count'] == 1
        assert summary['metrics']['extraction_calls'] == {'sum': 0, 'coverage_count': 0, 'request_count': 1}
        results.append({'case': case, 'projection': 'invalid', 'raw_cost_retained': True,
                        'extraction_calls': summary['metrics']['extraction_calls']})

    failed = response({**known, 'ingestions': [{'cached': False}], 'memory_complete': True})
    retried = response({**{k: 0 for k in known}, 'ingestions': [{'cached': True}], 'memory_complete': True}, status=200)
    rows = []
    for index, event in enumerate((failed, retried), 1):
        rows.extend([{'kind': 'request', 'payload': {'node': 'synthetic-' + str(index)}},
                     {'kind': 'event', 'payload': {'kind': 'probe', 'node': 'synthetic-' + str(index), **event}}])
    observations = requests(rows)
    summary = summarize(observations)
    assert len(rows) == 4 and len(observations) == 2
    assert summary['invalid_count'] == 2
    assert summary['metrics']['extraction_prompt_tokens'] == {'sum': 0, 'coverage_count': 0, 'request_count': 2}
    raw_metrics = [decode(base64.b64decode(r['payload']['http_body_base64']), admission=False)['x_nyx_bridge']
                   for r in rows if r['kind'] == 'event']
    assert [r['extraction_calls'] for r in raw_metrics] == [1, 0]
    assert sum(r['extraction_prompt_tokens'] for r in raw_metrics) == 8
    totals = scope['processing_totals'](scope['processing_requests'](rows), scope['completion_requests'](rows), summary)
    assert totals['all_prompt_tokens'] is None and totals['all_completion_tokens'] is None
    results.append({'case': 'failed_request_then_cached_retry', 'events': 2, 'raw_extraction_calls': [1, 0],
                    'raw_extraction_prompt_tokens_total': 8, 'summary': summary,
                    'all_prompt_tokens': totals['all_prompt_tokens'], 'all_completion_tokens': totals['all_completion_tokens']})

    unknown = response({**known, 'extraction_prompt_tokens': None, 'extraction_completion_tokens': None})
    assert unknown['memory_telemetry_status'] == 'valid'
    unknown_summary = summarize([{'status': 'valid', 'value': unknown['memory_telemetry']}])
    assert unknown_summary['metrics']['extraction_calls']['coverage_count'] == 1
    assert unknown_summary['metrics']['extraction_prompt_tokens']['coverage_count'] == 0
    results.append({'case': 'unknown_usage_control', 'projection': 'valid', 'usage_stays_unknown': True})
    report = {'status': 'SYNTHETIC_SOURCE_EXTRACTED_PROOF', 'cases_passed': len(results), 'source_sha256': PINS,
              'package_imports': 0, 'network_model_native_store_calls': 0,
              'limits': 'No adapter dispatch, durable persistence, scoring or accepted-schema change is exercised.',
              'results': results}
    with target.open('xb') as f:
        f.write((json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    print(json.dumps({'cases_passed': len(results), 'result_path': str(target)}))


if __name__ == '__main__':
    main()
