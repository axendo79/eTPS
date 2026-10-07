# eTPS v0.2 status

## Current state

The experimental v0.2 byte scorer, offline/live/manual runners, SQLite journal,
replay/export, answer tolerance, reset/delivery policies and processing-cost
diagnostics are implemented and covered by synthetic standard-library tests.
Acceptance, first-attempt retention, RR and generation TPS remain separate;
eTPS is a labeled experimental index. Legacy v0.1 modules remain preserved.

The state-evolution authoring pipeline is merged in PR #25; see the
[isolated author-session runbook](v0.2/AUTHORING_RUNBOOK.md). No development
or evaluation corpus has been authored yet.

Local live work includes run 7 (three arms) and run 8 (five arms, three separate
repeats), using google/gemma-4-e4b only. These are exploratory calibration
observations, not benchmark results or evidence of general superiority.
There are no independent held-out tasks, no calibration manifest satisfying
the measurement contract, and no benchmark claims. Run 8's frozen exploratory
plans do not fill those gaps. Earlier entries below record historical states.

Run `python -m unittest discover -s tests -v` from the repository root.
Tests use synthetic inputs and ephemeral fake servers, not model endpoints.
The website and leaderboard remain on hold until validity work is done.

## Five-arm memory calibration, run 8 (2026-10-02)

Codex executed the user-authorized run on 2026-10-02 local time. **Results
describe Nyx-backed prototype memory, not Nyx proper. Calibration only.**
The model was local google/gemma-4-e4b; no other model or remote service was
evaluated. Eleven tasks per arm, one trial per task/arm/repeat, three separate
55-slot plans/stores. All 55 slots finished in each repeat, with no invalid,
aborted or unattempted slots. All three memory-mode checks passed and the saved
exports replayed identically at the recorded revision. No retry occurred.

| Arm | Configuration |
|---|---|
| A | gemma-full: full history |
| B | gemma-reset: reset-only |
| C | gemma-reset-nyx: reset plus Nyx-backed prototype memory |
| D | gemma-reset-naive: reset plus chronological extracted-fact memory |
| E | gemma-reset-recall: reset plus verbatim user-message recall |

The same task bytes and final-generation settings were used across arms:
temperature 0, max_tokens 2048, seed null, fence-v1, d10-v1, decode-v1,
warm-declared and deliver-v1. Arm order rotates by (task index + repeat index)
modulo five. C/D share extraction (same model, max_tokens 1024); E does not
extract. Each memory slot uses a fresh bridge process and store.

### Outcomes, separately by repeat

Accepted counts include exact and tolerated format deviations, shown in
parentheses. First-attempt retention uses eight fact-dependent tasks:
retained_fact, supersession_current, historical, contradiction, new_evidence,
context_pressure, scheduled_recap and mixed_recovery. The controls clarification,
expired and never_established remain in acceptance and cost denominators.
Scheduled_recap is retention under a scheduled recap, not unaided retention.
Mixed_recovery counts only designated old-fact spans as reconstruction.

Pooled RR below is descriptive **within one arm and repeat**: sum(R)/sum(I),
including measured failures. Each row includes all 11 measurement-valid tasks;
none is excluded or unavailable. Results and costs are never pooled across
repeats. Accepted after re-supply means accepted=true and R>0; R=0 alone does
not establish first-attempt retention.

#### Repeat 1

| Arm | Accepted /11 (exact, deviation) | First retained /8 | Accepted with R>0 /11 | Pooled RR |
|---|---|---|---|---|
| A | 9/11 (8, 1) | 6/8 | 0/11 | 41/15689 = 0.002613 |
| B | 8/11 (7, 1) | 0/8 | 6/11 | 281/15933 = 0.017636 |
| C | 10/11 (7, 3) | 7/8 | 0/11 | 25/15641 = 0.001598 |
| D | 9/11 (7, 2) | 6/8 | 0/11 | 91/15709 = 0.005793 |
| E | 10/11 (9, 1) | 7/8 | 0/11 | 66/15684 = 0.004208 |

#### Repeat 2

| Arm | Accepted /11 (exact, deviation) | First retained /8 | Accepted with R>0 /11 | Pooled RR |
|---|---|---|---|---|
| A | 9/11 (7, 2) | 6/8 | 0/11 | 41/15689 = 0.002613 |
| B | 8/11 (7, 1) | 0/8 | 6/11 | 281/15933 = 0.017636 |
| C | 9/11 (7, 2) | 5/8 | 1/11 | 73/15689 = 0.004653 |
| D | 9/11 (7, 2) | 6/8 | 0/11 | 48/15664 = 0.003064 |
| E | 10/11 (10, 0) | 7/8 | 0/11 | 66/15684 = 0.004208 |

#### Repeat 3

| Arm | Accepted /11 (exact, deviation) | First retained /8 | Accepted with R>0 /11 | Pooled RR |
|---|---|---|---|---|
| A | 9/11 (7, 2) | 6/8 | 0/11 | 41/15689 = 0.002613 |
| B | 8/11 (7, 1) | 0/8 | 6/11 | 281/15933 = 0.017636 |
| C | 10/11 (7, 3) | 7/8 | 0/11 | 23/15639 = 0.001471 |
| D | 9/11 (7, 2) | 6/8 | 0/11 | 48/15664 = 0.003064 |
| E | 10/11 (10, 0) | 7/8 | 0/11 | 66/15684 = 0.004208 |

### Processing costs beside accuracy

Prompt/completion columns include **all answer and boundary-delivery requests**,
including failed trials; they are not probe-only or accepted-only totals.
Coverage is reported requests / all requests for both usage fields and, for
C/D/E, every extraction metric. Extraction seconds are rounded to three decimals
and exclude storage and final generation; they are not end-to-end latency.
Extraction token counts, calls and rejected batches are self-reported telemetry.
A/B extraction is not_applicable; E's measured extraction values are zero.
No live memory objects were missing, invalid or unavailable in any repeat.

#### Repeat 1 costs

| Arm | Prompt tokens | Completion tokens | Extraction calls | Extraction prompt | Extraction completion | Extraction seconds | Facts rejected | Coverage |
|---|---|---|---|---|---|---|---|---|
| A | 10159 | 6654 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 24/24 |
| B | 4982 | 9970 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 30/30 |
| C | 5368 | 5814 | 28 | 7164 | 7464 | 141.520 | 1 | 23/23 |
| D | 5548 | 6725 | 29 | 7292 | 7924 | 147.318 | 1 | 24/24 |
| E | 12511 | 5320 | 0 | 0 | 0 | 0.000 | 0 | 23/23 |

#### Repeat 2 costs

| Arm | Prompt tokens | Completion tokens | Extraction calls | Extraction prompt | Extraction completion | Extraction seconds | Facts rejected | Coverage |
|---|---|---|---|---|---|---|---|---|
| A | 10150 | 6818 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 24/24 |
| B | 4970 | 9841 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 30/30 |
| C | 5602 | 6845 | 30 | 7406 | 7891 | 148.876 | 1 | 25/25 |
| D | 5485 | 6201 | 29 | 7282 | 7461 | 139.102 | 1 | 24/24 |
| E | 12511 | 5304 | 0 | 0 | 0 | 0.000 | 0 | 23/23 |

#### Repeat 3 costs

| Arm | Prompt tokens | Completion tokens | Extraction calls | Extraction prompt | Extraction completion | Extraction seconds | Facts rejected | Coverage |
|---|---|---|---|---|---|---|---|---|
| A | 10150 | 6821 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 24/24 |
| B | 4970 | 10010 | not_applicable | not_applicable | not_applicable | not_applicable | not_applicable | 30/30 |
| C | 5358 | 6725 | 29 | 7282 | 7924 | 150.353 | 1 | 23/23 |
| D | 5479 | 6408 | 29 | 7282 | 7476 | 138.095 | 1 | 24/24 |
| E | 12511 | 5312 | 0 | 0 | 0 | 0.000 | 0 | 23/23 |

### Interpretation, losses and disclosures

C versus D compares current-belief storage against chronological retention of
the same extracted facts. C versus E changes extraction and representation
together, so it is not an isolated test of storage. A/B are full-history and
reset-only controls. C lost context_pressure to A/B/E in repeats 1 and 2;
C and D both failed that task in those repeats. C accepted contradiction only
in repeat 1; all arms failed it in repeats 2 and 3. In repeat 2 C needed
re-supply on supersession_current and retained fewer tasks on first attempt
than D. These losses remain visible alongside C's successes. Full history
failed mixed_recovery in every repeat while the other arms accepted it.

There are only eight fact-dependent tasks. **Differences of one or two tasks
are noise, not persuasive evidence of superiority. This is calibration, not
proof.** Repeats reuse the same tasks and one model; they are not independent
held-out tasks. The tasks and harness are model-authored, with prior model
exposure and calibration-informed answer aliases. A fair general result needs
independently authored held-out tasks and more than this model/task set.
No broad architectural, causal or statistical-significance claim follows.

The user reports that a separate e4b chat may have overlapped the first one or
two repeat-1 slots. This is a possible **timing-only** confound; overlap was not
independently established, and no timing result was corrected or rerun.

The bridge uses ingestion-time identity/current-belief behavior rather than
general contradiction, expiry or historical reasoning. All memory modes use
the same "Facts remembered from earlier in this conversation:" prefix and
prepended system position. Recall includes instructions and nonfacts and avoids
extraction loss/errors/costs. Ingestion includes the current request, identical
user content is deduplicated, and there is no injection cap, relevance filter,
pruning or decay. C/D's extraction limit differs from recall's no-extraction
path; storage overhead and failure exposure differ. Longer memory can increase
cost or context failures. These are disclosed control differences, not isolated
tests of an architecture. eTPS discounts user reconstruction burden, not total
system compute; costs and coverage must stay beside accuracy.

**Conflict:** the eTPS author builds Nyx and owns these control arms. Nyx must
be allowed to lose. Model-authored tasks and model review are not independent
validation. The website and leaderboard stay on hold until validity work.

### Missing-usage coverage and provenance

Offline synthetic validation exposed a coverage asymmetry: missing extraction
usage in C/D produced null token counts, which the run-time eTPS revision
rejected as an entirely invalid memory object. Coverage fell from 22/22 to
21/22 even for available time/rejection fields, and combined token totals
became null. E cannot encounter this extraction-usage failure because it makes
no extraction calls. This was not observed in the live repeats above.

The wrap-up fix accepts null field values and lowers numeric coverage only for
the affected fields. Available extraction_seconds and facts_rejected retain
coverage; incomplete combined token totals remain null. Strings keep their
existing valid-but-nonnumeric behavior; nested objects, booleans and nonfinite
numbers remain invalid. This changes telemetry projection, not scoring. The
frozen run 8 artifacts and reports remain unchanged; the tables above come from
their recorded revision, not a rescore. Old journals containing null fields
marked invalid may fail projection verification under the new revision; use
their recorded code revision for faithful replay rather than rewriting evidence.

Run 8 used eTPS `02a01b4d21a225a095502e66d2e08c7306a330ac`,
nyx-bridge `32d880117b6613ffb563d5b6b0f2f079b9b0d203`, and
ProjectNyx `622c037770bbb96b41377d5775fcece4b7eeb9f6`.
The combined freeze SHA-256, verified before and after execution, was
`e104ee6520fa4400cc5148c1a9031d562cc8543330190bdf23490a0f2b29b0e9`.
The approved eTPS untracked ProjectNotes-only exception was recorded;
the other two trees were clean. Local hashes are not independent timestamp
proofs, and frozen exploratory plans are not a formal calibration manifest.

Evidence remains private in `local-5arm-controls-2026-10-02`: RUN_RECORD.md,
ANALYSIS_PLAN.md, FREEZE.json, per-repeat reports/exports and slot logs.
Only aggregate results and task names are reproduced here, with no private
task text, prompts or answers. This wrap-up uses synthetic tests only and
does not perform a model run or modify the private evidence.

Validation: the full suite passed 283 tests before the fix and 290 after it,
using `python -B -m unittest discover -s tests -v` on Windows Python 3.14.
Seven new synthetic tests cover null-field coverage, incomplete token totals,
unchanged string/invalid-value handling and replay integrity/compatibility.
The user authorized removing the single contradictory null case from the old
invalid-values test; byte checks verified all other existing test content
unchanged across 28 files. Aggregate outcome/cost tables, coverage, freeze and
revision identifiers were checked against the saved reports without rescoring.

## D10 answer tolerance and decode-v1 timing (2026-09-30)

User decisions: freeze three answer tolerance rules and three result states;
report format compliance separately, never as a multiplier. Report both timing
conventions, with decode-only TPS/eTPS primary and full-generation TPS secondary
under an explicitly frozen decode-v1 live plan. Absence of either opt-in retains
the corresponding existing behavior. Previously recorded runs are not rescored.

Codex implemented this on local branch `v02-d10-timing` from main `390827b`.
D10 validates disjoint aliases and fixed-value declarations, preserves exact
match precedence, rejects key collisions, and supports digit-string integers
and declared ASCII-whitespace/casefold tolerance. Field routing uses normalized
fields. Replay recomputes modes/rules from verified raw answer bytes; acceptance,
retention and eTPS treat correct deviations as correct. Reports expose headline
acceptance, exact/deviation counts, compliance numerator/denominator and rule
counts. Decode-v1 uses the authorized native first-token subtraction, explicit
compatible decode fields only, and source-labeled secondary telemetry.

Validation: all 229 tests pass (215 existing tests unchanged and 14 new tests),
using standard-library code and ephemeral fake servers. The 70-token timing
fixture yields 42.54 decode TPS. Rehashed timing tampering is rejected.

The private mapping-v3 proposal contains 22 full/reset manifests. Only the D10
opt-in and per-probe alias/fixed-value declarations were inserted; inverse byte
edits restore each source exactly. All 116 synthetic offline slots and replay
checks pass; 1,265 source mapping files and seven original SHA256SUMS entries
remain unchanged. Known wording issues remain for corpus vNext. No corpus text,
answer keys or private hashes are included in the repository.

Alias lists for the current corpus are **calibration-informed**, derived after
observing google/gemma-4-e4b failures on 2026-09-29/30. The private
`ALIAS_PROPOSAL.md` is labeled "calibration-informed proposal; requires user
approval before any run". Synthetic offline validation does not authorize a
model run or establish independent semantic validity. Local commits only;
stop for Claude's check. No live model calls, pushes or PRs.

Updated 2026-09-15. **An experimental byte scorer, offline runner and SQLite replay store now exist. No model benchmark runs, frozen calibration manifest, or timestamp proofs exist in this work.** Synthetic fixtures are not empirical validation or independent review.

## Implemented and checked

`etps_v02/scorer.py` is a standard-library-only pure function over a finite manifest and event record. It checks exact payloads/hashes, UTF-8 span boundaries, declared branches, source delivery and active-obligation failure links. It reports byte I/R, exact fractional RR, separate terminal acceptance and first-attempt retention, available backend TPS and conditional experimental eTPS. Protocol deviations have unavailable RR; ordinary wrong model answers follow failure branches. Legacy v0.1 modules are unchanged.

Run `python -m unittest discover -s tests -v` for synthetic checks. `python -m etps_v02.examples` reports fixture R/I/RR; TPS and experimental eTPS are unavailable because its evidence is synthetic. Pure arithmetic unit tests separately exercise dilution and cost-reversal formulas; they do not produce model performance claims.

`etps_v02/workload.py`, `runner.py`, `persistence.py` and the package CLI now support exact-byte bundle import, offline scripted execution, fixed slot order, durable request/event journaling, explicit abort, replay and export. No network or model adapter exists (historical; superseded by the live exploratory adapter section below). Every planned slot remains visible; interrupted slots cannot be silently rerun. These paths were tested with synthetic fixtures only, including separate-process replay. See [offline runner details](v0.2/OFFLINE_RUNNER.md). Offline wall time is unavailable, not estimated from harness speed.

## Adopted revision

Primary RR uses UTF-8 bytes, identity normalization, and character-aligned half-open spans (`utf8_bytes`). Tokenizer-relative RR is optional secondary telemetry with its own lock identity; it is not implemented here and does not block core accounting. Old token-based ratios cannot be relabeled byte ratios.

Calibration uses a committed manifest hash, exact artifacts and a complete attempt ledger. OpenTimestamps is binding from the first confirmatory manifest. No calibration superiority claims. Independent review remains a later evidence milestone, not a prerequisite for implementing this non-canonical prototype.

## Next step

Bring in the unpublished authored corpus and map it to the executable schema. Review semantics, all failure transitions, resource/timing budgets, and fixed calibration counts before model execution. Freeze two separate external criteria in that calibration manifest: total newly delivered user bytes across all attempts per accepted completion, and total end-to-end time across all attempts per accepted completion. Report acceptance and missingness alongside both; zero accepted completions makes them unavailable. Examine pairwise order agreement and list reversals without claiming the criteria are universal usefulness or independent validation.

The prototype does not implement a model runner, full semantic state schema, applicability predicates, arbitrary structured answer schemas, action verification, or budget enforcement. Backend timings are supplied telemetry, not independently authenticated. All of those limits remain explicit. Canonical manifest identity here uses sorted compact JSON/UTF-8; it is not exact-file external attestation.

The original draft workload was not found in the checkout or available Library searches. It has not been imported, reconstructed or replaced by synthetic fixtures. Workload-specific integration requires the original files. No workload freeze, model execution, commit or push was performed during this implementation.


## Review corrections and delivery

New offline plans use schema v2, pin `unit: utf8_bytes`, require stable event-ID obligation boundaries and enumerate invalidation codes. Finished journals record resolved boundaries. Offline TPS/eTPS are unavailable even when scripts supply generation values. Hash mismatches warn while returning recomputed evidence; legacy exports can be replayed with compatibility warnings. Source and tests are delivered together as a ZIP; the original corpus remains separately unavailable. No model runs, commits or pushes.


The follow-up review found that failure grants persisted after recovery/correction. They are now discharged once per obligation; repeated grants on a common path fail authoring validation. Old evidence remains replayable with findings and corrected R counts. Reports now call the summary helper per task/arm, expose cost per accepted completion and pooled RR including failures, and retain unavailable reasons. New probes explicitly declare unknown-answer shapes; delayed obligation starts remain an explicit pilot limitation. The revised archive includes 77 passing synthetic tests.

The final synthetic-infrastructure follow-up pins stale citations after a fresh failure and separates schema compatibility from replay context. A v2 export can reassert authoring checks with `replay-export --validate-authoring`. Further work is the absent corpus adapter, not expansion of synthetic infrastructure.

## Corpus intake preparation (2026-09-29)

The original workload is still absent, and its import remains blocked. [Corpus intake and gap review](v0.2/CORPUS_INTAKE.md) lists required source material, maps contract requirements to the executable schema, names decisions that need the original files, and registers unset budgets, calibration counts and acceptance values without assigning them. Documentation only; no code, fixtures, model runs, commits or pushes.

## Authorized correctness repairs (2026-09-29)

Codex (Astra) implemented the user-authorized local repairs for audit findings V01 through V06, with focused synthetic regression tests. Model bytes now journal safely before malformed branching; validation fails closed for malformed shapes; unknown manifest/node fields require a hashed, non-executable metadata namespace; recovery links require ancestor probes testing the referenced obligations; replay binds response sequences to pinned scripts and checks finish/abort claims. Invalid evidence stays visible with unavailable primary RR/acceptance and explicit warnings. See [runner behavior](v0.2/OFFLINE_RUNNER.md) and [repair handoff](V02_CORRECTNESS_REPAIR_2026-09-29.md).

V07 is partially addressed by iterative graph traversal; resource bounds and descendant-set complexity remain open. V06 is fixed to the authorized path-ancestor and tested-obligation scope; all-path dominance is not claimed. V08-V10, legacy issues, and corpus integration remain deferred. The historical audit report is unchanged. The original corpus remains absent, and no budgets, calibration counts or acceptance criteria were invented. Local repairs only; no commits, pushes, network calls, dependency installs or model runs. Ready for Claude's review after the recorded checks.

## Authorized offline CI and local data hygiene (2026-09-29)

The user authorized one local branch and commit for audit G02 (offline CI) and G01 (local data ignore rules), stopping for Claude's check before Claude pushes and opens the PR. Codex (Astra) authored the SHA-pinned, read-only GitHub Actions workflow and appended ignore rules for SQLite files and companions, evidence exports, private corpus/workload directories and environment files, while allowing `.env.example`. CI runs the standard-library unittest suite on Ubuntu with Python 3.11-3.14 and Windows with Python 3.14; all matrix cells report independently. It has no dependency installation, cache or artifact-upload steps.

Local validation: `python -B -m unittest discover -s tests -v` passed all 101 tests on Windows with Python 3.14.2. This was the only installed interpreter found; a Python311 directory contained no interpreter. Python 3.11, 3.12 and 3.13 were not run locally, and GitHub Actions results remain pending. No code changes, model runs or dependency installs were performed. The historical audit remains unchanged. The corpus-intake edit is limited to the authorized ignore-rule clause; originals should still live outside the working tree.

## Authorized corpus-independent hardening (2026-09-29)

The user authorized local branch `v02-hardening`, one commit per completed item, and a stop for Claude's check before Claude pushes and opens a PR. Codex (Astra) authored V07 admission safeguards, interval-union counting, selective reachability and transactional head-based append; V09 full normalized module/runtime identity; V10 explicit slot accounting and arm-pairing diagnostics; the optional V06 bypass-path finding; and G05 document/history guidance. The software safety constants are not benchmark budgets. All 101 original tests remain unchanged; 17 focused hardening regressions bring the suite to 118 passing tests on Windows Python 3.14.2.

V08 was stopped and its implementation reverted after it produced 10 errors across eight existing test methods. Export v1 completeness binding and global cross-slot chronology remain deferred; erased export journals can still appear unattempted. Remaining limitations include full-history request duplication, dense recovery-graph cost, absent corpus semantics and enforcement of schedule exposure, mandatory assertions, budgets and actions. No missing experiment values were invented. The [hardening handoff](V02_HARDENING_2026-09-29.md) includes per-item results, conflicts and the full test/probe output links. The [document index](INDEX.md) distinguishes operative guidance from historical proposals. Earlier session-specific no-commit/ZIP statements remain historical records; they do not describe this branch's delivery state.

No model runs, corpus work, dependency installs, live adapters, legacy v0.1 repairs, pushes or PR creation occurred. Network use was limited to the authorized setup pull. The historical audit and CORPUS_INTAKE are unchanged. Claude's review and hosted CI for this branch are pending.

## Authorized opt-in export v2 (2026-09-29)

The user authorized local branch `v02-export-v2` from `b1831ea`, with code/tests and documentation commits followed by a stop for Claude's check before any push. Codex (Astra) authored opt-in V08 completeness binding: v2 envelopes retain planned slot order and database head count/hash/state, captured with the journals in one read snapshot. Replay verifies the envelope, membership, lengths, hashes and lifecycle states. Default export remains v1 with unchanged serialization and warning behavior; replay adds `export_completeness_bound` for both formats. An erased completed journal remains unattempted in v1 but raises an integrity error in v2.

All 118 existing tests remain unchanged and pass; 16 new tests in `tests/test_v02_export_v2.py` bring the local suite to 134 passing tests on Windows Python 3.14.2. The default-v1 audit's behavioral rows are unchanged; only its syntax inventory rises from 20 to 21 files. Coherent full rewrites still defeat editable hashes. Signing, attestation and global cross-slot chronology remain deferred; no schema migration, model run, dependency install, legacy repair or corpus work occurred. See the [V08 handoff](V08_EXPORT_V2_2026-09-29.md). No push or PR was performed; Claude's review is pending.

## Authorized typed answers and private mapping policy (2026-09-29)

The user authorized local branch `v02-typed-answers` and a local commit before
Claude's review, plus separate private offline mapping. Codex (Astra) authored
opt-in `typed-v1` flat string/integer/null answers, type-strict comparison and
manifest-bound projection/replay. Default string-only behavior remains intact.
All 134 existing tests pass unchanged; 10 new synthetic regressions bring the
suite to 144 passing tests on Windows Python 3.14. No private payloads or answer
keys are included in this repository change.

User decisions D1-D3 select empty unknown/refusal declarations (unknown
unreachable), bare retries, current incorrect/malformed classification and
transport timeout paths distinct from storage/controller invalidations.
D5-D7 permit hashed metadata or hash-bound sidecars for recap identification,
new-content offsets and affiliation disclosure, stored but not enforced.
Boolean values are malformed under the declared typed language, never equal to
integers. Per-field routing is deferred, as are broader state semantics (D4),
review/exposure declarations (D8), arms/budgets/counts (D9) and acceptance/reference
rules (D10). No model run, dependency installation, legacy change or push is
authorized by this delivery. Private mapping results remain outside the repo.

## Authorized live exploratory adapter (2026-09-29)

The user authorized an independent local branch from merged typed-answer main,
amended to support OpenAI-compatible and Anthropic endpoints. Codex (Astra)
implemented opt-in live plans, explicit model/budget settings, dual remote
authorization, environment-reference credentials, exposure journaling and
replay, and monotonic response/trial timing. Client latency never substitutes
for generation timing. Offline plans and existing tests remain unchanged.
Validation uses fake loopback servers and mocked remote transport only; no
real model endpoint or port 1234 was contacted. All 159 tests pass on Windows
Python 3.14 (144 existing unchanged and 15 new). See [live adapter](v0.2/LIVE_ADAPTER.md)
for the exact schema, safety gates and measurement limits. No dependency
installs, legacy repairs, corpus publication or pushes. Claude reviews before
opening a PR; real smoke testing remains separately unauthorized.

## Authorized field routing (2026-09-29)

Codex (Astra) implemented the user-authorized opt-in field-v1 routing on a local
branch from merged typed-answer main. Exact-key incorrect responses route by
type-strict failed-field subsets, attribute failure and first-attempt retention
per obligation, and preserve recovery provenance and grant checks. Existing
manifests, journals and tests remain unchanged. All 152 tests pass on Windows
Python 3.14 (144 existing plus 8 new). Private mapping is separately authorized;
no private text or answer keys are included here. No model calls, installs,
legacy repairs or pushes. Claude reviews before publication.

## Authorized review fixes (2026-09-29)

Codex (Astra) added field-obligation coverage validation and merged field routing
into the live branch with a merge commit. Live dispatch now shares scorer routing,
checks credentials and TCP reachability before start, treats in-trial credential
loss as execution_error, and rejects empty/assistant-ended public histories
before dispatch. The user authorized narrow updates to the unmerged live test
fixtures while retaining D3 connection-refusal coverage. All 177 tests pass;
main's existing tests and the original field-routing tests remain unchanged.
Only ephemeral loopback fake endpoints were used. No real model call or push.

## External kit authorization (2026-09-29)

Codex (Astra) added opt-in per-arm endpoints and model-metadata checking, with
new loopback-only regression tests. The user authorized user-operated remote
exploratory SMOKE runs on synthetic input only; corpus runs remain unauthorized.
Private kits stay outside the repo. No provider API or documentation was queried
by Codex; Anthropic version currency and model endpoint compatibility are
unverified. No model run, dependency installation, legacy change or push.

## Native provider amendment and reported first run (2026-09-29)

Codex (Astra) added the user-authorized opt-in lmstudio-native provider with
loopback-only, no-key dispatch and explicitly named generation timing sources.
Tests use fake servers only. Separately, the user reports that Claude performed
the first live run with user authorization: one synthetic slot against local
google/gemma-4-e4b through LM Studio's OpenAI-compatible API, accepted, RR 0,
TPS unavailable because stats were empty. No corpus data was used. The private
run record retains details; this is not an Astra-executed or independently
verified run. This entry supersedes earlier no-live-run status chronologically.

## Manual development authorization (2026-09-29)

Codex (Astra) implemented the separately authorized opt-in manual development
adapter, pinned coding rubrics, confirmed human coding, private evidence export
and publication fences. Results remain dev-only and separate from automated
summaries. Tests use synthetic scripted stdin; no actual service session or
external request occurred. Optional independent recoding is deferred. Private
draft kits require user review; no corpus content is included here.

## Fence extraction and post-run decisions (2026-09-29)

The user authorized Codex (Astra) to implement opt-in live fence-v1 extraction,
replay-bound flags and per-arm strict-JSON diagnostics, preserving strict old
plans and all existing test files. Future-run output budget is user-set to
2048 tokens including reasoning, with the private smoke kit updated separately.
Only synthetic fake-server tests were run by Codex; no live model calls.

The user reports Claude's authorized first local corpus run on all 11 tasks
against google/gemma-4-e4b: max_tokens 256, strict parsing, 0/11 accepted.
The reported diagnosis is Markdown fences (seven answers would be correct
without them) and reasoning-token exhaustion. Recorded results stay unchanged;
the counterfactual diagnosis is not a rescore. S4 now records local prior exposure
of this corpus to google/gemma-4-e4b. Private run records retain the details.

## Reset/session profile and two-day plan (2026-09-30)

Day 1 (this task): Codex (Astra) implemented the user-authorized eTPS session
profile on local branch `v02-reset-profile` from main `a23a4f5`. Optional
session_boundary nodes leave obligations active and add no input bytes.
Per-arm full/reset-v1 policies control public history; full remains the default.
Offline/live replay checks policy-specific histories, and authoring requires a
user message between each boundary and the next probe. Reports expose processed
prompt-token counts with coverage and descriptive per-task full/reset vectors.
This lets a plain model lose prior turns so recovery can produce RR > 0 and
experimental eTPS can differ from TPS; it does not demonstrate a model result.

Windows full-path Python 3.14 verification passes 215 tests (207 existing tests
unchanged, eight new synthetic tests). Live tests use fake servers only.
The private mapping-v2-reset draft contains all 11 tasks with one proposed
boundary immediately before each first probe question. Validation passes all
264 synthetic slots under both policies, including replay; seven source
SHA256SUMS entries verify identically before/after, and 1,078 source mapping
files remain unchanged. Only the inserted node and necessary incoming edge
differ in each manifest; inverse edits reproduce the source bytes exactly.
The draft is labeled "UNREVIEWED DERIVED DRAFT; boundary placement is a proposal
for user review". Known wording issues in retained_fact, clarification, expired
and mixed_recovery remain for a separate corpus vNext decision. Private text,
answer keys and artifact hashes remain outside the repository.

Day 2 (separate, not started): the user's plan is a nyx-bridge prototype in its
own repository/folder, NOT inside ProjectNyx. An OpenAI-compatible proxy would
extract facts from chat, record them through Nyx's existing public APIs, inject
retrieved beliefs and forward to the local model. It would be a third arm
against the full and reset baselines. Results must be labeled "Nyx-backed
prototype memory"; Nyx is allowed to lose and the author conflict is disclosed.

Exposure includes the previously reported local google/gemma-4-e4b corpus run,
Codex/Astra's corpus/mapping work, and reviewer Claude having seen corpus content
during review (user-disclosed). Review is not independent corpus authorship.
No live model calls, pushes or PRs were performed in this task. Local commit
only; stop for Claude's check, with Claude responsible for pushing/opening a PR.

## Three-arm memory experiment support and reported runs (2026-09-30)

The user reports these runs executed by Claude with user authorization on
2026-09-30. They are calibration observations, not independently verified
Codex executions or controlled superiority claims:

- Full versus reset with mapping-v2-reset, fence-v1 and a 2048-token budget:
  full accepted 7/11, reset 3/11. The first observed experimental eTPS below TPS
  included scheduled_recap (44.59 TPS to 35.95 eTPS) and supersession_current
  (42.83 TPS to 36.88 eTPS).
- With mapping-v3, d10-v1 and decode-v1: full accepted 8/11 (7 exact, 1 format
  deviation); reset accepted 6/11 (4 exact, 2 deviations). Four recovered reset
  trials had eTPS below TPS. These use the new frozen conventions, not a
  retroactive rescore of the preceding run.
- LM Studio prompt caching reportedly reduced TTFT to approximately 0.1 seconds
  across runs. This motivates the declared warm-cache condition; TTFT/prefill
  remain diagnostics and must not be compared across arms under warm-declared.

User decisions: retain D10 as merged; approve the calibration-informed aliases
code <- project_code and word <- access_word. Code and word values remain
case-sensitive (do not declare them as fixed_value_fields). Decode-v1 is primary
timing. Warm-declared is the default condition for authoring future experiment
plans, explicitly recorded as `cache_policy: "warm-declared"`; an omitted field
does not silently acquire this declaration.

The planned experiment has three arms: Gemma full, Gemma reset, and Gemma reset
plus the nyx-bridge prototype. Label the third arm's results "Nyx-backed
prototype memory". Nyx is allowed to lose. The profile author/system-development
conflict remains disclosed; prototype results do not establish an independent
memory-system comparison.

On local branch `v02-memory-arms` from main `8827759`, Codex added descriptive
arm_comparison entries that preserve distinct arm identities even when policies
match, while retaining context_policy_pairing unchanged. Optional response-body
memory telemetry is copied and verified on replay, with per-key sums and request
coverage. It never enters I, R, RR or TPS. Optional cache_policy is reported for
all arms without changing scoring or server state. Validation uses new synthetic
tests and fake servers; existing tests remain unchanged. No corpus material,
live model calls, pushes or PRs are part of this implementation. The separate
nyx-bridge work is untouched. Local commits only, then stop for Claude's check;
Claude pushes and opens the PR.

Validation: 237 tests pass, including eight new synthetic tests and all 229
existing tests unchanged. New live-test request deadlines are 10 seconds and
trial limits are 30 seconds; all servers are ephemeral test servers.

## Boundary delivery correction for memory arms (2026-09-30)

The user identified that reset-v1 could clear pre-boundary user messages before
any request submitted them to the system. This is a harness delivery failure
for a memory experiment under contract section 3. The 2026-09-30 reset-v1 runs
stand as a no-memory baseline: for stateless models, undelivered and forgotten
earlier messages are equivalent at the next request. Those runs are not
rescored or represented as memory-arm evidence.

Memory arms require the new opt-in live-plan `boundary_delivery: "deliver-v1"`.
Every arm sends one delivery request at a boundary if user messages are pending
since the last request, then applies its full/reset policy. Raw responses and
processing telemetry are journaled and replay-verified. Delivery replies are
not classified; delivery generation is excluded from primary TPS/eTPS and
reported separately. I/R accounting and probe retention remain unchanged.
Transport failures are retained and the trial continues within its wall budget.
Absent the field, prior behavior is unchanged. Codex implemented and tested the
addition on v02-memory-arms with synthetic fixtures and fake servers only;
existing tests and the separate nyx-bridge workspace are untouched. One more
local commit, then stop for Claude's check; no model calls, push or PR.

Validation: 246 tests pass (237 existing tests unchanged, nine new boundary
delivery tests). Fake-server coverage includes both histories, first-attempt
retention, primary TPS exclusion, no-pending/repeated boundaries, failed
delivery, wall-limit stops, secondary timing and rehashed replay tampering.

## Performance and correctness batch (2026-10-01)

Codex (Astra) completed local W1, W2, W3, W4, W8 and W6 on
`v02-perf-correctness` from main `0925ae1`, with W7 evidence and handoff.
Plan hashing and distinct-script validation are reused; planned-order admission
checks only the immediate predecessor. The synthetic benchmark's start cost is
128 VM steps at both 100 and 400 predecessors (previously 1,022 and 3,722).
Incomplete groups now disclose unavailable planned acceptance and a separate
attempted-only rate. Live authoring rejects reply-to-probe successors, manual
D10 uses the scorer classifier, and replay checks required fields before access.

W5 hash journaling was stopped and fully reverted after an unchanged malformed-
plan test failed. Its empty outcome commit preserves the requested commit order;
the feature and its byte-size targets are not delivered. Full-history journals
remain the only request format. The [handoff](V02_PERF_CORRECTNESS_2026-10-01.md)
contains the conflict, decisions including the D4 override, before/after benchmark
output, per-item suite logs, compatibility evidence and existing-test diff stat.

Validation: 264 tests pass (246 baseline plus 18 new methods). Baseline tests
remain unchanged except the single authorized W4 runtime-guard test edit.
Tests used synthetic inputs and ephemeral loopback servers only. Codex did
create/run disposable D10 manual plans through automated scripted tests, but
no human manual service session or model run occurred. No private folders,
corpus or kits, LM Studio or real endpoints were accessed; no dependencies were
installed. ProjectNotes and CLAUDE.md were not edited. Stop after W7 for Claude's
review; no push or PR.

## W5 opt-in hashed request history (2026-10-02)

Codex applied Claude's model-authored W5 reference patch on
`v02-w5-request-journal` from `a2f3896`. Offline v2 and live plans may declare
`request_journal: "history-sha256-v1"` to store request counts and hashes;
replay reconstructs and verifies the histories. User text and response bytes
remain journaled. Omitting the field retains the existing request format.
This supersedes the earlier stopped W5 outcome above.

The user corrected work-order test 2.4: the first reset-v1 request hashes only
post-boundary user messages (one in the standard fixture), because authoring
requires a new user message between a boundary and a probe. The work-order
file and reference patch remain unchanged. See the
[W5 handoff](V02_W5_REQUEST_JOURNAL_2026-10-02.md) for validation evidence,
before/after benchmark output, provenance, and the local-review stop point.

Validation: 264 baseline tests and 274 final tests pass; SHA256 checks confirm
all 25 existing test files are byte-for-byte unchanged. The new file adds ten
tests using synthetic data and ephemeral loopback fake servers. Hash-mode
request payloads total 11,835 bytes and the journal totals 516,651 bytes;
default full-history sizes remain unchanged. No model runs, real endpoints,
private data, installs, push or PR. Two local commits, then Claude's review.

## Cleanup batch (2026-10-02)

Codex applied Claude's model-authored C1 and C2 patches on
`v02-cleanup-batch` from main `642ada5` (W5 merged). Finished manual traces
with invalid recomputed measurements no longer claim verified evidence.
Per-arm processing totals now combine answer/delivery usage and self-reported
memory extraction counts with explicit coverage; incomplete token totals are
null. Memory summaries also include `facts_rejected`. Scoring is unchanged.

Validation: 274 baseline tests, 277 after C1, and 283 after C2; the full suite
also passes 283 tests before the C3 documentation commit. All 26 existing test
files remain byte-for-byte unchanged. Nine new tests use synthetic scripted
input and ephemeral loopback fake servers only. The
[cleanup handoff](V02_CLEANUP_BATCH_2026-10-02.md) records per-item results and
the test diff. No model runs, LM Studio or real endpoints, private data,
installs, push or PR. Three local commits, then stop for Claude's review.
