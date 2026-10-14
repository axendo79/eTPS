# Brief v2 implementation handoff

The [2026-10-14 addendum](#maintainer-rulings-addendum-2026-10-14) supersedes
the historical S1, S3, S4 and S6 decisions recorded below.

Codex-authored implementation and SYNTHETIC software checks under the user's
local authorization, 2026-10-12. No real task/key/prediction, model execution,
human corpus review or empirical result was produced. The approved proposal's
A/B scope is implemented; its C/D experiment proposals are outside the six BUILD
items and require model/corpus work that was not performed here.

Worktree: `D:\eTPS-wt-brief-v2`, branch `v02-brief-v2`, based on
`origin/v02-review-tools` at `1c68ea2f91e9b0a6f767dc3e982b947ea077d9d8`.
The main checkout's branch/files were not changed. No fetch was needed because
the specified remote-tracking ref was available. TEMP/TMP and every temporary
artifact are under the ignored `scratch/tmp/` in this worktree. No push, PR or
merge is authorized or performed. Only the specifically authorized proposal
was read from the private workspace; no private corpus was accessed.

## Delivered behavior

1. `AUTHORING_BRIEF_V2.md` is self-contained, includes proposal A1–A9 and passes
   the extended existing denylist checks. V1 is byte-unchanged and indexed as
   historical. V2 omits v1's A–D condition descriptions under the prompt's
   explicit no-arm-design instruction; anonymous A–F prediction records and
   structural/null prediction rules remain. Every other v1 rule is preserved
   except where A1–A9 changes/adds it.
2. Authoring-v1 accepts both brief versions. V2 alone refuses five ID categories
   outside `<task>-m/q/p/v/r` plus three digits 001–999, using `id_style`.
   No continuity requirement or other new refusal was added. The mapper and
   existing freeze marker propagate the declared version; v1 artifact checks
   and every review gate remain intact.
3. Lint reports `authoring-lint-v2`, with field-scoped `answer_form_missing`.
   Status identifier projections use ID form, not status vocabulary. V2 defaults
   to three preceding delivered messages, includes source IDs, and has no
   establishment/source exemptions. V1 keeps two messages and old exemptions.
   Missing-item names, values-in-force, first-tenth source positions and token
   pressure requiring human verification are additional advisory observations.
4. Pure `normalized_score` reports paired strict/normalized object-level 0/1
   scores with declared ID/set fields. It folds only case/whitespace, balanced
   ID square-bracket/straight-quote wrappers and numeric strings with trailing
   alphabetic units. Existing complete-set semantics remain. Strict scorer,
   acceptance, runner, replay and stored evidence are unchanged.
5. Indices, format/lint/scorer usage and the human review runbook describe actual
   behavior and prospective declarations; new authoring uses brief v2/lint v2.

## Test-first evidence

Interpreter throughout:
`C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe`.
Baseline command: `-B -m unittest discover -s tests`.
Baseline: **449 tests ran, 448 passed, one pre-existing Windows FIFO skip**.

| Build item | Fail before | Pass after |
|---|---|---|
| 1: brief and denylist | Extended three-test existing suite: 2 missing-v2-file errors. V2 rule/neutrality regression also failed before the brief existed. | Both briefs pass all 3 existing denylist methods; v2 rules/neutrality regression passes. |
| 2: validator/schema/version propagation | Initial v2 focused run rejected v2 as unsupported, schema lacked the enum, and mapping could not begin. Pinned invalid-ID subcases returned brief_version instead of id_style. | V1/v2 admission, five ID categories, literal prefixes/noncontiguous numbering, mapper round-trip and v2 freeze/version mismatch regressions pass. |
| 3: advisory lint | Initial 13-method focused run: 27 failures and 19 errors across subcases. V2 was unsupported; new form checks/window were absent. Additional red run of 17 methods had 4 failures: historical-index label, pinned-prefix false positive, unreported source confirmation and unreported stale values. | All 17 focused methods pass; all 12 legacy lint methods pass. |
| 4: diagnostic score | New module import failed with ModuleNotFoundError; discover recorded 1 import error before implementation. | All 8 normalized-score methods pass; every authorized rule and non-rule is pinned, including M2 versus bin M2 and unchanged strict classification. |
| 5: docs/review | Index/runbook/diagnostic-document regression failed before files/links and lint-v2 instructions existed. | Documentation regression passes; local Markdown links are checked with the existing suite and final scope review. |
| 6: handoff | This evidence record did not exist before the implementation. | This record captures commands, outcomes, commits and pending choices; no artificial test of its own prose was added. |

The first focused follow-up also exposed two fixture/lint issues: one test
inadvertently examined later synthetic probes, and clause splitting separated
`null` from `for answer`. The fixture was narrowed to its intended probe and
clause splitting fixed; neither changes an admission/scoring rule. Source-ID
coverage later expanded the expected field observations to include status.
Eight scorer methods include two later defensive/mixed-set tests that passed
on first execution; they are not claimed as prior failures.

Exact local outputs are retained in ignored `scratch/tmp/`: `baseline-tests.txt`,
`brief-v2-red.txt`, `brief-denylist-red.txt`, `normalized-red.txt`,
`brief-v2-first-pass.txt`, `brief-v2-additional-red.txt`, `brief-v2-pass.txt`,
`normalized-pass.txt`, `brief-denylist-pass.txt` and `legacy-lint-pass.txt`.
They contain synthetic software output only. Full-suite and commit records
follow below.

## STUCK-DECISION

Flagged choices remain pending; no new authoring refusal or experimental
configuration resolves them. Human corpus/protocol defects still block freeze
under the existing review gate.

| ID | Unsettled detail | Options | Recommendation / current limit |
|---|---|---|---|
| S1 | A8 names no correction-ID category or numbers above 999. | Declare a sixth category; reuse a category with collision safeguards; retain existing correction rules. Extend width in a new version if needed. | Keep correction IDs under existing rules now; five named categories enforce the pinned spelling. Set a convention before real authoring needs it. No inferred new refusal. |
| S2 | A3 asks for past competition via at-checkpoint, but authoring-v1 permits set arrays only for kind=values; at-checkpoint is scalar. | Versioned historical-set extension; ask scalar historical fields/status; omit that representation. | Specify a historical-set extension separately. V2 states the intended semantics; human review must flag an unrepresentable request. No admission rule is relaxed. |
| S3 | A9 requires sizes/token verification but the closed source format has no budget/counter receipt fields, and 10% does not specify message versus character/token evidence boundaries. | Neutral parameter appendix plus frozen counter receipt/settings; new format fields. Message-start/character-start/token-span basis. | Use the existing neutral appendix/settings and freeze a counter receipt; settle its exact shape/basis before authoring. Lint reports both source-start bases and context_pressure_unverified; it estimates no tokens. |
| S4 | A6's question hygiene versus a linked correction intentionally repeating tested facts. | Explicit retry exception; separate correction/retry by three eligible messages; retain advisory flag and review the conflict. | Keep corrections visible and flagged; get a maintainer ruling before real retries are authored. Do not change recovery semantics or invent an exception. |
| S5 | No arm designs versus v1's concrete A–D descriptions. | Neutral anonymous prediction records; restore designs in an authorized separately supplied brief instance. | The prompt explicitly requires neutrality, so v2 keeps anonymous A–F records/null predictions and removes those descriptions. Provision of condition information remains pending; do not invent it. |
| S6 | Normalized-score metadata, exact folding grammar, fold-colliding sets and runner denominators/schema. | See NORMALIZED_SCORE.md's options table. | Use the pure paired report with explicit ID/set declarations; no answer-based ID inference or runner integration. Freeze prospective settings and settle any broader grammar/schema separately. |

Advisory wording matching cannot decide intent or whether conversation text
supports a key. Natural-language field naming, confirmations without literal
values/IDs, absence evidence and exact source-span placement remain human review
work; a software pass cannot establish semantic validity or independence.

## Full-suite verification

The same baseline command runs **474 tests in 60.585 seconds: 473 pass and one
pre-existing Windows FIFO test skips**. Output: `scratch/tmp/full-suite-first.txt`.
No new skip/failure is hidden. The 25 new methods are 17 brief-v2 and 8 diagnostic
scorer tests; extending the existing denylist adds subcases, not methods.
All original methods still run. No production model endpoint is used.

Final scope audit compares base-tree files using Git's checkout filters (Windows
CRLF), rather than incorrectly comparing checkout bytes with raw LF blobs:
**65 protected files** match byte-for-byte, including v1 brief, strict scorer,
runner/replay/persistence and legacy modules plus **53 unchanged baseline test/
fixture files**. Only `test_v02_authoring_brief.py` is intentionally extended.
V1 brief checkout SHA-256:
`b8b622782db44140b43a27eb444b8c9ec789651e154f889f1b9279b66cafecca`.
All **134 local Markdown links** across the affected maintainer docs resolve.
Scope audit output: `scratch/tmp/scope-verification.txt`. `git diff --check`
passes. Main still reports `94ff86720769bb001430e7739596972c231c2cf0` on `main`.

After the final status/provenance/brief wording edits, **24 affected documentation
and brief methods pass** (3 denylist, 2 index/provenance, 2 runbook and 17 v2).
Output: `scratch/tmp/final-doc-checks.txt`. The only later code edit was a comment
clarifying the already-tested source exemptions; no functional change followed
the passing full suite, so the suite was not repeated without a new reason.

## Local commits and delivery

| Commit | Content |
|---|---|
| `fd0fa6d0b415fcd650dd78c8cc5f80dd8f7e19d2` | Build items 1–5: brief, version admission/schema/propagation, advisory lint, diagnostic scorer, tests/docs and initial evidence record. |
| Documentation commit containing this final record, subject `Record brief v2 verification and local delivery` | Build item 6: final test/scope/commit evidence. Resolve its exact ID with `git log -1 --format=%H` on the delivered branch. |

The worktree and `v02-brief-v2` branch are left in place, locally committed and
unpushed. The main checkout remains pinned. The temporary logs remain ignored;
no private proposal bytes, corpus artifact or answer key is committed. The
pending choices above require specification/review decisions before relevant
real authoring/execution, not further guessing by this implementation.

## Maintainer rulings addendum, 2026-10-14

The maintainer approved evaluation-prep recommendations in **Addendum 7**:
S1 pins the sixth ID category, `<task>-c001`, for corrections (v2 only).
S3 makes the first 10% a message-position rule, rounded up; the maintainer
verifies sizes with the token counter at freeze and records them in settings.json.
S4 exempts correction messages from rule 6, including retry correction positions;
ordinary messages remain checked within the original three-message window.
S6 keeps the normalized diagnostic as built: a pure paired report, explicit
provenance/missing-item ID fields and element-by-element set normalization.
Rule 9's beyond-budget minimum is now **1.5x**, replacing 2x.

Codex applied these rulings test-first using SYNTHETIC data only. The focused
run first had 16 failures across 21 tests, then all 21 passed. Four new methods
cover correction-ID/span/mapper preservation, exemption-window boundaries,
rounded message-position cutoffs and character-distance independence. Historical
v1 admission/brief and strict scoring/runner/replay/normalized scorer are unchanged.
No private corpus or launch folder was read, and no model run or push occurred.

Full suite with the requested Windows Python 3.14 interpreter and worktree
scratch/tmp TEMP/TMP: **478 tests in 72.635 seconds, 477 pass and the existing
Windows FIFO test skips**. Output: `scratch/tmp/brief-v2-amend-full-suite.txt`;
focused logs: `brief-v2-amend-red.txt` and `brief-v2-amend-green.txt` in the same
directory. Scope checks confirm 93 protected files match baseline bytes under
their LF/CRLF checkout conventions, three SYNTHETIC v1 lint reports are
byte-identical to baseline, and 59 local Markdown links resolve. After the final
evidence/status edits, all nine affected documentation/brief checks pass; output:
`scratch/tmp/brief-v2-amend-final-docs.txt`. `git diff --check` passes. This amendment
is locally committed on `v02-brief-v2` and left unpushed.

## P3 repair and integration addendum, 2026-10-14

The user authorized all three audit repairs and their local commits. Review-tool
fix `680679b86eb95d32d97b0d46f2e97b0aa399abbc` was committed on
`v02-review-tools` after its full suite ran **452 tests: 451 pass, one existing
FIFO skip**. Merge `1b87d1ac090471bb530acf1505abc01b20c80475` integrates it
into `v02-brief-v2` without conflicts, preserving maintainer amendment `ebdc014`.
See the [review-tool repair evidence](review-tools-run.md#pr-28-p3-repairs-2026-10-14).

The normalized diagnostic now requires an alphabetic unit token via
`str.isalpha()` while retaining the existing ASCII decimal/fraction/exponent
grammar. Superscripts, fractions, Roman numerals and non-ASCII decimal digits
cannot yield a diagnostic integer match. Both scalar and set-member paths are
tested; documented number spellings and alphabetic units still pass. A string
containing a numeric symbol still matches the same expected string exactly.

Before the fix, the ten-method diagnostic suite recorded 12 subtest failures;
afterward all ten passed. The requested full-path Windows Python 3.14 command,
with TEMP/TMP in `D:\eTPS-wt-brief-v2\scratch\tmp`, runs **483 tests in 50.181
seconds: 482 pass, one existing Windows FIFO skip**. Logs are ignored:
`scratch/tmp/p3-normalized-before.txt`, `p3-normalized-after.txt` and
`p3-brief-full-suite.txt`. No production changes followed this passing suite.
Four affected documentation checks pass after the final evidence updates;
output is `scratch/tmp/p3-final-docs.txt`. `git diff --check` passes.

Production changes relative to `ebdc014` are limited to review_record.py,
review_sheet.py and normalized_score.py. Strict scoring, authoring/mapper/freeze
admission, runner/replay and v1 brief remain unchanged. This is Codex-authored
SYNTHETIC software evidence; no private workspace or real corpus was accessed,
no model run occurred, and the pinned main checkout was not edited. Both local
branches remain unpushed. The diagnostic-fix commit subject is
`Require alphabetic units in normalized numeric diagnostics`.
