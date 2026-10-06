# Authoring pipeline run — 2026-10-06

Authorized local tooling only, in D:\eTPS, on `v02-authoring-pipeline` created
from `v02-set-answers` at `937b514`. No real task, development task, key or
prediction is authored. Every executable fixture added here is labeled SYNTHETIC.
Existing tests are preserved. No external network, real model run, private
workspace access, push, or edit to another project is performed. The unchanged
suite uses ephemeral loopback fake servers; new tooling tests invoke no endpoints.

## A1 — neutral authoring brief

Commit: `77e7467` — `feat(v02): add neutral authoring brief`.
Files: AUTHORING_BRIEF.md, tools/brief_denylist.txt,
tests/test_v02_authoring_brief.py, this handoff.
Fail-before: 2 tests errored because both requested artifacts were absent.
Pass-after: 2/2 targeted tests. Unchanged baseline: 344/344 full-suite tests.
STUCK: none. Anonymous E/F predictions explicitly admit unknown because the
neutral brief cannot disclose implementation behavior. No winner is prescribed.

## A2 — authoring-v1 schema and strict validator

Commit: `55ee10e` — `feat(v02): validate neutral authoring-v1`.
Files: intake/authoring.py, authoring-v1.schema.json, AUTHORING_FORMAT_V1.md,
tests/authoring_fixtures.py, tests/test_v02_authoring_format.py, this handoff.
Fail-before: new test module failed import (validator absent).
Pass-after: 7/7 targeted tests, including every format refusal code and closed
objects, strict JSON, CLI, and portable strings. Cumulative test count: 353.
STUCK: none for format admission; representability is tested separately in A3.

## A3 — mapper and bounded sidecar intake

Commit: `c863230` — `feat(v02): derive manifests from authoring-v1`.
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

Commit: `94a6521` — `feat(v02): aggregate corpus diagnostics within one plan`.
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

Commit: `3834a5c` — `feat(v02): freeze reviewed corpus bundles`.
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

Commit: `2816c2f` — `docs(v02): document isolated author-session procedure`.
Files: AUTHORING_RUNBOOK.md, tests/test_v02_authoring_runbook.py, this handoff.
Fail-before: 2 tests errored because the runbook did not exist.
Pass-after: 2/2 targeted procedure checks. Cumulative test count: 374.
Runbook covers fresh only-brief/no-repository sessions, S1–S16 and S2–S4
records, private placeholder custody (not created), separate dev tuning/freeze
then untouched eval, A2/A3/explicit sidecar intake, human cross-check ruling 4,
hash-bound review and the defect-blocks-release rule.
STUCK: no new procedure decision; A3's representation blockers are explicit
release gates. No actual author/model session or private corpus folder was created.

## A7 — documentation, provenance and final consistency verification

Commit: `v02-authoring-pipeline` (final branch tip) —
`docs(v02): link authoring pipeline and record final verification`.
The tip reference avoids embedding a self-referential commit hash in its own
committed handoff; A1–A6 hashes above are immutable local commit IDs.
Files: docs/INDEX.md, docs/v0.2/README.md, PROVENANCE.md, SET_ANSWERS.md,
STATE_RECORDS_V1.md, this handoff, and final consistency fixes/tests to the new
brief/denylist, mapper, aggregation and freeze tools. No pre-existing test or
scorer/runner/replay source file is edited.

Fail-before: 2 new documentation checks failed (index absent and provenance
entry absent). Final QA regressions also demonstrated brief review-language
leakage, a corrupt report's uncaught KeyError, a missing derived per-family
prediction summary, and acceptance of whitespace-edited freeze receipts.
Pass-after: documentation 2/2, brief 3/3, format 7/7, mapper 10/10,
aggregation 7/7, freeze 6/6, runbook 2/2. The per-family summary only groups
author-supplied predictions, with no authored prediction of its own. Every new
fixture remains SYNTHETIC. Added mapper checks cover inactive requirement refusal,
recovery-cycle refusal and multiple-task derivations. Format CLI also checks
missing-file refusal. STUCK: A3's explicit representation limitations only.

## Final verification

Full command:
`C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe -B -m unittest discover -s tests -q`.
Unchanged baseline: 344/344. Intermediate full suites: 360/360 and 380/380.
Final full suite: **381/381 passed**, exit 0, 48.830 seconds (344 unchanged
baseline tests plus 37 new tests). Final staged `git diff --cached --check`:
exit 0. All targeted pass-after checks above are included in that full run.
All existing test paths are unchanged in `git diff v02-set-answers -- tests`;
only new files are present. Scorer, runner, replay, existing intake and all
other pre-existing Python modules are unchanged. `v02-set-answers` remains
`937b51452980212d8e24e3f5055ae826b66b82d9`. All seven commits are local on the new
branch. No goal/author session, model run, external network, public corpus,
private-workspace access or other-project edit occurred.
Closure: final branch `v02-authoring-pipeline`; seven local task commits;
clean worktree checked after the A7 commit. No push or PR is performed.

## Final task table

| Task | Status | Commit | Tests / STUCK |
|---|---|---|---|
| A1 brief | done | `77e7467` | Initially 2 tests; final 3. Separate denylist; no governance text in the brief. |
| A2 format/validator | done | `55ee10e` | 7 tests; all format refusal codes and closed structures. |
| A3 mapper | done | `c863230` | Initially 7 tests; final 10. STUCK forms are explicitly refused: delayed obligations, multi-failure recovery, alternatives, clarification sidecar projection. |
| A4 aggregation | done | `94a6521` | Initially 6 tests; final 7. Earlier aggregation STUCK resolved by ruling 2. |
| A5 freeze | done | `3834a5c` | 6 tests; exact inventory, review, dev/eval separation and later-change refusal. |
| A6 runbook | done | `2816c2f` | 2 tests; isolated only-brief author, private custody, human review and defect gates. |
| A7 docs/provenance | done | `v02-authoring-pipeline` | 2 documentation tests plus final consistency regressions and full suite. |

Skipped: none. Tooling delivery is complete; real corpus authoring and execution
are outside this session. Full F9 release remains STUCK until the clarification
representation is settled; no subcase was deleted or replaced to conceal it.

## Authoring rulings — 2026-10-06

The maintainer has settled the earlier A3 representation choices: delayed
starts, combined-failure corrections and alternative correct objects are
disallowed. F9 is limited to exact missing-information answerability, with
`status = missing_information` and an optional exact missing-item identifier.
No open-ended clarification is admitted. These rulings supersede the historical
A3 STUCK entries above; implementation and verification follow below.

### R1 — authoring-stage refusals and neutral brief

Commit: R1 task commit, `feat(v02): enforce authoring rulings at admission`.
Files: etps_v02/intake/authoring.py, mapper.py (error-type compatibility adapter),
AUTHORING_BRIEF.md, authoring-v1.schema.json, new
tests/authoring_rulings_fixtures.py and tests/test_v02_authoring_rulings.py,
this handoff. All pre-existing tests are unchanged.
Fail-before: the five new tests exposed absent admission refusals, an unsupported
missing-information field shape, and missing brief rules. The existing neutrality
scan then refused the word "canonical"; the brief now states the equivalent
"one fixed answer object" without changing the denylist or prior tests.
Pass-after: 5/5 new tests; 29/29 authoring tests; full suite **386/386**, exit 0,
53.417 seconds. The mapper preserves its public MappingError type when reporting
the earlier authoring-stage reason codes. STUCK: none. R2/R3 will implement the
sidecar projection before this new source form is executable.
