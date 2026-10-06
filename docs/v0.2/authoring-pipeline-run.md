# Authoring pipeline run — 2026-10-06

Authorized local tooling only, in D:\eTPS, on `v02-authoring-pipeline` created
from `v02-set-answers` at `937b514`. No real task, development task, key or
prediction is authored. Every executable fixture added here is labeled SYNTHETIC.
Existing tests are preserved. No network, model run, private workspace access,
push, or edit to another project is authorized or performed.

## A1 — neutral authoring brief

Commit: `feat(v02): add neutral authoring brief` (resolved in final table).
Files: AUTHORING_BRIEF.md, tools/brief_denylist.txt,
tests/test_v02_authoring_brief.py, this handoff.
Fail-before: 2 tests errored because both requested artifacts were absent.
Pass-after: 2/2 targeted tests. Unchanged baseline: 344/344 full-suite tests.
STUCK: none. Anonymous E/F predictions explicitly admit unknown because the
neutral brief cannot disclose implementation behavior. No winner is prescribed.

## A2 — authoring-v1 schema and strict validator

Commit: `feat(v02): validate neutral authoring-v1` (resolved in final table).
Files: intake/authoring.py, authoring-v1.schema.json, AUTHORING_FORMAT_V1.md,
tests/authoring_fixtures.py, tests/test_v02_authoring_format.py, this handoff.
Fail-before: new test module failed import (validator absent).
Pass-after: 7/7 targeted tests, including every format refusal code and closed
objects, strict JSON, CLI, and portable strings. Cumulative test count: 353.
STUCK: none for format admission; representability is tested separately in A3.

## A3 — mapper and bounded sidecar intake

Commit: `feat(v02): derive manifests from authoring-v1` (resolved in final table).
Files: intake/mapper.py, tests/test_v02_authoring_mapper.py,
AUTHORING_MAPPER.md, this handoff.
Fail-before: new test module failed import (mapper absent).
Pass-after: 7/7 targeted tests with lossless-source round trips and canonical
byte comparisons; synthetic A→B→C, A→B→A, lapse/reinstatement, unresolved then
precedence, scoped/partial change, provenance, recovery, recap, and omitted fields.
Cumulative test count: 360. Every result passes the existing intake validator.

STUCK (implemented refusals, no approximation):
- Delayed obligations: CORPUS_INTAKE §3 decision 3 and executable
  `begin_after == source`; code `delayed_obligation`.
- Multi-probe recovery: CORPUS_INTAKE §3 decision 4, one `user.failure` ID;
  code `multi_failure_recovery`.
- Additional correct forms: SET_ANSWERS supports one expected object; code
  `alternative_answers`.
- F9 legitimate clarification: STATE_RECORDS_V1 query table has only current,
  at-checkpoint, status, values and provenance projections. A clarification-only
  expected answer is supported by the scorer (CORPUS_INTAKE §2), but cannot be
  projected by the mandatory sidecar. Code `clarification_unrepresentable`;
  release of complete F9 coverage needs a representation ruling/extension.

## Final task table

Pending completion of A2–A7 and full-suite verification.
