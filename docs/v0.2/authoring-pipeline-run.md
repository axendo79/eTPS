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

## A4 — within-plan corpus aggregation

Commit: `feat(v02): aggregate corpus diagnostics within one plan`.
Files: intake/corpus_aggregation.py, tests/test_v02_corpus_aggregation.py,
CORPUS_AGGREGATION.md, this handoff.
Fail-before: new test module failed import (aggregation tool absent).
Pass-after: 6/6 targeted tests; canonical per-arm/family/tag counts, separate
first/terminal sets, omitted fields, abort/unattempted slots, all outcome classes,
refusal to combine plans/repeats, v1/v2 replay CLI and exclusive output creation.
Cumulative test count: 366. A1–A3 full suite: 360/360 passed unchanged.
STUCK: earlier repeat/aggregation item is resolved by maintainer ruling 2.
No new corpus-semantic choice made; repeat identity is a frozen external
hash-bound declaration because existing plan fields are closed.

## A5 — corpus freeze and verification

Commit: `feat(v02): freeze reviewed corpus bundles`.
Files: intake/corpus_freeze.py, tests/test_v02_corpus_freeze.py,
CORPUS_FREEZE.md, this handoff.
Fail-before: new test module failed import (freeze tool absent).
Pass-after: 6/6 targeted tests; deterministic complete inventory and verification,
every file's byte change, additions/deletions, record tampering, review/defect
gates, dev/eval separation and parent binding, reused IDs, counts and review
hashes, unsafe paths, CLI exclusive receipt creation and later-change refusal.
Cumulative test count: 372. No actual corpus or real review was frozen.
STUCK: none for the hash/review tool. Numeric experiment settings remain
author/maintainer supplied, never guessed. A3's clarification blocker persists.

## A6 — isolated author-session runbook

Commit: `docs(v02): document isolated author-session procedure`.
Files: AUTHORING_RUNBOOK.md, tests/test_v02_authoring_runbook.py, this handoff.
Fail-before: 2 tests errored because the runbook did not exist.
Pass-after: 2/2 targeted procedure checks. Cumulative test count: 374.
Runbook covers fresh only-brief/no-repository sessions, S1–S16 and S2–S4
records, private placeholder custody (not created), separate dev tuning/freeze
then untouched eval, A2/A3/explicit sidecar intake, human cross-check ruling 4,
hash-bound review and the defect-blocks-release rule.
STUCK: no new procedure decision; A3's representation blockers are explicit
release gates. No actual author/model session or private corpus folder was created.

## Final task table

Pending completion of A2–A7 and full-suite verification.
