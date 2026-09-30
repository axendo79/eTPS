# eTPS v0.2 status

Updated 2026-09-15. **An experimental byte scorer, offline runner and SQLite replay store now exist. No model benchmark runs, frozen calibration manifest, or timestamp proofs exist in this work.** Synthetic fixtures are not empirical validation or independent review.

## Implemented and checked

`etps_v02/scorer.py` is a standard-library-only pure function over a finite manifest and event record. It checks exact payloads/hashes, UTF-8 span boundaries, declared branches, source delivery and active-obligation failure links. It reports byte I/R, exact fractional RR, separate terminal acceptance and first-attempt retention, available backend TPS and conditional experimental eTPS. Protocol deviations have unavailable RR; ordinary wrong model answers follow failure branches. Legacy v0.1 modules are unchanged.

Run `python -m unittest discover -s tests -v` for synthetic checks. `python -m etps_v02.examples` reports fixture R/I/RR; TPS and experimental eTPS are unavailable because its evidence is synthetic. Pure arithmetic unit tests separately exercise dilution and cost-reversal formulas; they do not produce model performance claims.

`etps_v02/workload.py`, `runner.py`, `persistence.py` and the package CLI now support exact-byte bundle import, offline scripted execution, fixed slot order, durable request/event journaling, explicit abort, replay and export. No network or model adapter exists. Every planned slot remains visible; interrupted slots cannot be silently rerun. These paths were tested with synthetic fixtures only, including separate-process replay. See [offline runner details](v0.2/OFFLINE_RUNNER.md). Offline wall time is unavailable, not estimated from harness speed.

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
