# eTPS v0.2 provenance

## Maintainer state-record rulings and intake authorization (2026-10-06)

The user supplied the four [maintainer rulings](STATE_RECORD_OPTIONS.md#maintainer-rulings-2026-10-06):
one frozen logical field map per task (unsuppliable fields unavailable), one plan
per repeat with within-plan per-arm aggregation only, authoritative hash-locked
state-record sidecars, and a bounded separately versioned intake/freeze validator.
The sidecar contains state/version chains, authority, establishment, valid time,
applicability, update links, obligations, lapse/reinstatement and disagreement.
Sidecar bytes and hash freeze with the manifest. This supersedes the earlier
unselected representation status, not the preserved historical options analysis.

The user authorized local F1/F2 repairs, a docs-first rulings commit and synthetic
test-first validator implementation on `v02-set-answers`; no push or model run.
Codex records the rulings and authors the mechanical intake format/checks.
Neither scorer nor validator proves semantics, source truth or authority.
Review must cross-check obligations and keys before freezing; any mismatch is a
corpus/protocol defect blocking valid-evidence execution. F2 remains STUCK under
the existing-test preservation rule, as documented in the handoff. No corpus
task, private key or model result is authored by this implementation work.

Codex implemented [state-records-v1](STATE_RECORDS_V1.md) in a separate intake
subpackage with closed JSON, an exact-byte SHA-256 binding, bounded graph/order
and obligation checks, fresh reinstatement, explicit disagreement/precedence
and exact answer correspondence. The tool is never imported by production
scoring or replay. All fixtures are public synthetic examples; no state corpus
was authored or frozen. Normal replay of pre-validator synthetic exports with
and without bindings remains byte-identical, including implementation identity.

## Complete-set implementation authorization (2026-10-06)

The user explicitly authorized local implementation on `v02-set-answers`,
synthetic tests before code, documentation, and one local commit per task,
overriding CLAUDE.md's no-commit default for this task. Scope is `D:\eTPS` only:
no push, external network, model runs or private corpus reads. Codex authored
[set-v1](SET_ANSWERS.md), the synthetic status/value fixtures and diagnostic
field counts, and [the state-record options memo](STATE_RECORD_OPTIONS.md).
The memo selects no state representation. No corpus task or answer key was
authored, and passing synthetic tests does not establish semantic validity,
independence or a benchmark result. The existing author/system conflict remains.

First/terminal diagnostics cover stable tagged field plans, with unavailable
reasons for heterogeneous plans and no repeat pooling. Corpus-wide repeat
identity and heterogeneous field identity remain decisions, not inferred facts.
Original tests, fixtures, manifests and evidence exports are preserved; older
score arithmetic and classification remain unchanged. Implementation identity
warnings continue to disclose changed source on replay.

## State-evolution corpus specification accepted (2026-10-06)

The user accepted [STATE_EVOLUTION_CORPUS_SPEC](STATE_EVOLUTION_CORPUS_SPEC.md)
draft 2 with the rulings recorded in its section 8. Claude drafted it; the
requirement list came from the user, relaying model-advisor recommendations
the user endorsed. A model design review (the Dot) shaped draft 2. Rulings:
all nine families plus sub-cases; about 50 evaluation tasks after a separate
development set; separate status/values fields with order-insensitive
complete-set scoring; an isolated neutral-brief model session as the
developer-directed, non-canonical author; six arms, including both projector-0
and projector-3 Nyx configurations; provenance tasks in the first release. A
narrow, versioned scorer extension must exist before any task is authored. The
user builds Nyx; the author-system conflict applies. No task, answer key or
model run exists under this specification yet.

## D10 and timing decisions and calibration exposure (2026-09-30)

The user authorized opt-in d10-v1 answer tolerance and decode-v1 live timing on
`v02-d10-timing` from main `390827b` or later. The three frozen answer rules are
declared key aliases, digit-string-to-expected-integer equality, and declared
fixed-string ASCII-whitespace/casefold tolerance. Exact type-strict matches have
precedence. Trial states are accepted_exact, accepted_with_format_deviation and
failed, with measurement validity still separate. Format compliance is a
separate accepted_exact / accepted rate, never an eTPS multiplier. Decode-only
TPS/eTPS is primary under decode-v1; full-generation TPS is secondary. Both
conventions and answer declarations must be frozen before a run.

Codex authored the implementation, new synthetic tests, documentation and
private mapping-v3 derivation. Existing tests on main remain unchanged. Tests
use synthetic responses and ephemeral fake servers only. The requested
Co-Authored-By trailer follows the existing local contribution convention;
it does not establish independent review or change implementation authorship.

The current corpus alias lists are **calibration-informed**, derived after
observing google/gemma-4-e4b failures on 2026-09-29/30. They are not prospective
independent evidence. The private proposal lists each alias and fixed-value
declaration with a reason and is labeled "calibration-informed proposal;
requires user approval before any run". Only unambiguous aliases are proposed.
Existing recorded runs are not rescored; later runs require newly frozen hashes.

The private full mapping-v1/v1.1 and reset mapping-v2-reset sources yielded 22
new manifests with only D10 declarations added. Inverse edits restore exact
source bytes, including payload spelling. All 116 newly authored synthetic
offline slots replay successfully. SHA256SUMS verification matches before/after
for seven original entries, and all 1,265 source mapping files remain unchanged.
Wording repairs remain deferred to corpus vNext. No private corpus material or
hashes are committed. This work authorizes local commits only and stops for
Claude's check; no live model calls, remote publication or old-run rescoring.

These documents were drafted by Codex from user instructions, supplied critiques, inspected repository code and cited primary sources. User-supplied review text is not automatically independently authored human review. Reddit attribution to u/Mirantisde is supplied by the user, not independently authenticated. No second-model identity or independence is inferred from style.

## Decisions and evidence

- User-required: neutral benchmark, input-side RR, benchmark-controlled retention obligations, documentation before code repair, Nyx permitted to lose.
- Explicitly endorsed in user messages: binary terminal acceptance, separate first-attempt retention, linked same-obligation failure, fixed scheduled input/recaps, experimental eTPS with primary TPS/RR, individual ranking reversals, cross-profile result separation, incomplete-attempt disclosure and both-arm reruns after protocol repairs.
- Selected by Codex and endorsed in discussion: OpenTimestamps and the shared cl100k_base/tiktoken 0.12.0 measurement convention. Exact runtime verification remains pending.
- Model-authored operational detail: finite paraphrase schema, byte-span formats, total branch precedence, six-confirmation gate, chained run-start declaration, and zero-unavailable completeness threshold. Writing a rule is not empirical validation or blanket approval of every detail.
- Draft 3 adopts the user's recommended exact-token-boundary rejection, superseding draft 2's intersection convention before any measured scoring.
- Paper examples and expected outcomes are model-authored. Structural checks on local draft data establish only byte/hash/reference consistency, not token-boundary validity, semantic validity or model performance.

## Revision authorized 2026-09-15

After reviewing the proposed corrections, the user said “Ok, sounds good, proceed.” This authorizes local implementation of the deterministic byte scorer, executable synthetic counterexamples and affected documentation updates. Primary RR becomes UTF-8 bytes, independent attestation is deferred to confirmation, and independent review is a later evidence milestone. External calibration criteria are input burden and elapsed cost per accepted completion, including failed-attempt costs and acceptance disclosure. These decisions supersede the earlier tokenizer/code-order/attestation gates below. They do not establish empirical validity or authorize model execution or remote publication. Synthetic executable cases were authored by Codex; they are not the unpublished workload.

## Historical publication authority

The user's latest explicit instruction authorizes committing and pushing documentation now, provided no manifest, corpus task file, tokenizer lock, token golden or corresponding artifact hash is included, and status explicitly records no runs and no frozen manifest. It supersedes the previous manifest-first/docs-after publication ordering. It does not authorize a model run, timestamp submission, implementation repair or corpus publication.

Earlier drafts and reviews may discuss superseded alternatives. The measurement contract draft 4 and current status identify the operative design. All documents remain pre-freeze material; none is an externally attested experiment manifest. No model benchmark runs, tokenizer execution or attestation submissions have occurred in this v0.2 work. There is no independent empirical audit of the proposed measurement.

Original v0.1 documentation is preserved in the history directory for audit purposes. Legacy v0.1 code remains unchanged. The separately versioned experimental scorer is new. This publication intentionally excludes the local corpus and accounting artifacts; it makes no claim that they are ready for freeze.

## Offline infrastructure follow-through

The user requested importing the unpublished workload and implementing runner/persistence, with no model runs, commits or pushes. The original workload could not be located in the checkout or available Library search. Codex implemented the independently useful offline controller/store and tested it only with explicitly synthetic fixtures. This does not constitute import or validation of the missing workload.

## Reviewer corrections

The user identified a delivery failure (only documentation was linked), branch-sensitive positional intervals, synthetic-throughput leakage, unstructured invalidation reasons, replay blocked by source changes, and missing plan-level unit identity. The local code now addresses these with event-ID boundaries, an offline throughput interlock, versioned plan policy/unit fields, and warning-based replay compatibility. These are tested implementation changes, not independent workload validation. The downloadable source/test archive includes test output and file hashes; no unpublished corpus is claimed.


## Executable follow-up review

The user reported independent checksum verification of all 35 covered files and a fresh-process Python 3.12 run of the prior 60-test suite. The user then supplied two synthetic reproductions of reused failure authorization. Codex reproduced them as regression fixtures and corrected consumption, clearing and authoring validation. Additional changes expose existing cost metrics and pooled RR in reports, declare unknown-answer shapes per probe, and document the pilot-only establishment/start restriction. This is user-reported independent execution of synthetic tests, not independent validation of the absent workload or a model comparison.

The user identified the mirror-case stale citation after a genuine second failure and the conflated schema/replay flag. The named regression preserves the distinction between runtime accounting and authoring admission; loader flags are now independent, with explicit authoring revalidation available for exported evidence. No claim about corpus fit follows.

## Corpus intake review (2026-09-29)

Claude (Claude Code) drafted [CORPUS_INTAKE](CORPUS_INTAKE.md) from a user-delivered instruction to prepare an intake and gap review while keeping the original import blocked. Schema statements come from reading `etps_v02/` at `90ebad1` plus scratch validation calls; they are not independent review. The document assigns no corpus values. Authoring a replacement corpus requires a separate explicit user decision and a new corpus name.

## Bounded repair authorization and authorship (2026-09-29)

The user explicitly authorized bounded v0.2 correctness repair from `docs/ENGINEERING_SECURITY_AUDIT_2026-09-29.md`, in the order V01, V04, V05, V06, V02 and V03, with optional iterative traversal for V07. Authorization was local only, with no commits, pushes, model runs, network calls or dependency installs, and required focused regressions while retaining the original 77 tests unchanged.

Codex (Astra) authored the implementation changes, new `tests/test_v02_repairs.py` synthetic regressions, audit-probe continuation adjustment, this provenance section, the appended status section, offline-runner documentation and repair handoff/output artifacts. These are model-authored repairs and synthetic checks, not an independent human review, corpus import, corpus replacement or empirical benchmark result. The probe harness now catches the corrected script-mismatch rejection and uses separate valid evidence for the finish-mismatch probe; its historical report and original captured results remain unchanged. Claude's existing corpus-intake file and appended documentation sections were preserved. No legacy modules were repaired. The original authored corpus remains unavailable. Work stops for Claude's review after verification.

## Offline CI and data hygiene authorization and authorship (2026-09-29)

The user explicitly authorized one local branch and commit covering audit G02 and G01, followed by a stop for Claude's check. Claude will push and open the PR after review; this authorization excludes a Codex push or PR, model runs and dependency installs.

Codex (Astra) authored `.github/workflows/tests.yml`, the appended `.gitignore` section, the appended status and provenance sections, and only the authorized clause replacement in Claude's corpus-intake document. Existing documentation sections and the historical engineering/security audit are preserved. The workflow uses SHA-pinned checkout/setup-python actions, read-only contents permission, Ubuntu Python 3.11-3.14 and Windows Python 3.14, and the standard-library unittest command without dependency installation, caches or artifact uploads.

Local execution used Windows Python 3.14.2: `python -B -m unittest discover -s tests -v` passed all 101 tests. Only that interpreter was found installed; the Python311 directory had no interpreter. Python 3.11-3.13 and the hosted CI matrix were not executed locally. These are synthetic software checks, not model benchmark runs, corpus validation or independent review. The requested commit trailer credits Claude Opus 5.5; implementation authorship for these changes remains Codex (Astra).

## Corpus-independent hardening authorization and authorship (2026-09-29)

The user authorized one local branch and a separate passing commit per completed hardening item, with existing test files immutable and a stop of any item conflicting with them. Codex must stop for Claude's check; Claude will push and open the PR after review. Authorization excludes model runs, network use beyond git fetch/pull, dependency installs, legacy v0.1 changes, corpus work and live adapters.

Codex (Astra) authored the V07, V09, V10 and optional V06 implementation changes, `tests/test_v02_hardening.py`, documentation hygiene, runner documentation, appended status/provenance, and the handoff/output artifacts. V08 was attempted, produced 10 errors across eight existing test methods, and was entirely reverted without a V08 commit. Global chronology is also deferred. G05 documents isolated, unmaintained legacy code; it does not repair L01-L12. The historical audit, CORPUS_INTAKE, all original tests and all legacy modules remain unchanged.

Local verification used Windows Python 3.14.2: all 118 tests passed, including the original 101 and 17 new synthetic regressions. The unchanged audit probe ran locally; only its syntax-file count and direct deep-JSON decode result differ from the prior repair output. The exported-journal erasure probe still exposes deferred V08. These checks are model-authored software verification, not independent review, attestation, benchmark validity or original-corpus evidence. No benchmark budgets, calibration counts, acceptance thresholds or winner criteria were assigned. Software admission constants are explicitly labeled implementation safety limits. Each commit retains the user-requested Claude Opus 5.5 co-author trailer while the authorship of these changes remains Codex (Astra).

## Opt-in V08 authorization and authorship (2026-09-29)

The user separately authorized V08 as an opt-in export format on one local branch, preserving default v1 output and all existing test files. Codex (Astra) authored the runner/CLI changes, `tests/test_v02_export_v2.py`, runner documentation, these appended provenance/status sections and the new V08 handoff. The historical audit, CORPUS_INTAKE and earlier handoffs remain unchanged. The requested Claude Opus 5.5 co-author trailer does not change this implementation authorship record.

Local Windows Python 3.14.2 verification passes all 134 tests (118 existing plus 16 new), including v1 serialization/warning compatibility, opt-in head/envelope binding, coherent-rewrite acceptance, snapshot consistency and CLI behavior. The unchanged default-v1 audit retains every behavioral row; its syntax count increases only because of the new test file. Completeness binding is accident/truncation detection, not signing, attestation, proof of execution or corpus validation. Cross-slot chronology stays deferred because the schema has no global sequence. No model runs, dependency installs, legacy repairs or corpus work were performed. Work stops for Claude's check; Claude will push and open the PR after review. No push or PR was performed by Codex.

## Typed-answer authorization and authorship (2026-09-29)

The user authorized a local typed-answer extension and separate private mapping,
with no model runs, pushes or legacy v0.1 changes. Codex (Astra) authored the
opt-in schema, projection/comparison/replay changes, ten new synthetic tests and
these documentation updates. All 134 existing tests remain unchanged; 144 tests
pass on Windows Python 3.14. The requested co-author trailer credits Claude
Opus 5.5; implementation authorship remains Codex (Astra).

User mapping decisions D1-D3 select no unknown/refusal forms (unknown unreachable),
bare retries without repeated questions, and current incorrect/malformed rules
with transport failure on the timeout path, distinct from storage/controller
invalidations. D5-D7 authorize hashed metadata or hash-bound sidecars for recap
markers, new-content offsets and author affiliation, stored but not enforced.
These decisions do not edit original source material or endorse semantic validity.
No corpus text, payload, answer key or corpus artifact hash is included here.
Per-field routing and D4 broader state semantics, D8 review/exposure, D9
arms/budgets/counts and D10 acceptance/reference rules remain deferred.
Boolean responses follow the explicit out-of-schema rule (malformed), never
integer equality. Private derived fixtures are not model results. Claude reviews
before any push; no push or PR was performed by Codex.

## Live-adapter authorization and authorship (2026-09-29)

The user authorized a separate branch for an opt-in local live adapter, then
expanded that authorization to OpenAI-compatible and Anthropic providers with
explicit remote gates and environment-referenced keys. Codex (Astra) authored
the implementation, new fake-server tests and documentation. No actual local
or cloud model execution, dependency installation, legacy change or push was
authorized or performed. Exposure records describe recorded dispatch intent,
not proof of delivery or a complete history outside this runner. Existing
tests and offline evidence behavior are retained. All private artifacts stay
outside the repository; no budgets, model settings or counts for real runs
were selected. The full suite passes 159 tests on Windows Python 3.14, including
all 144 unchanged existing tests and 15 new fake-server/transport regressions.
Claude reviews the local commit before remote publication.

## Field-routing authorization (2026-09-29)

The user authorized a separate local field-routing branch and private synthetic
mapping, with no push or model execution. Codex (Astra) authored the opt-in
implementation, eight new regressions and documentation. Validation passes
152 tests, retaining the original 144 unchanged. Field-level recovery remains
linked to one originating probe; multi-probe failure linkage is not implemented.
Private artifacts and mapping results stay outside the public repository.
These checks establish software behavior, not corpus validity or independence.

## Review-fix authorization and authorship (2026-09-29)

The user authorized local review fixes to both branches, then explicitly allowed
narrow preflight-related changes to the unmerged live adapter tests. Codex (Astra)
authored coverage validation, live routing integration, credential/TCP preflight,
harness-fault and conversation guards, replay compatibility, and synthetic
regressions. The field branch passes 154 tests; the integrated live branch passes
177. No corpus payload is included. No model calls, dependency installs or pushes
were performed; Claude reviews the local commits before publication.

## External synthetic smoke authorization (2026-09-29)

The user authorized per-arm endpoints, metadata checks and private synthetic
smoke kits. Codex (Astra) authored the changes and fake-server tests. Only the
user may execute the remote exploratory SMOKE runs; this does not authorize
corpus runs. Codex/Astra authored the corpus, mapping and harness, so the Astra
arm has an author/system conflict. The reviewer (Claude) is an Anthropic model,
as is the Fable arm. These affiliations are disclosures, not independence.
No external provider/docs requests or model calls were made by Codex. The
supplied Anthropic version and model IDs remain unverified by this work.

## First authorized live run — user-reported (2026-09-29)

The user reports the first live model run, performed by Claude with user
authorization on 2026-09-29: one synthetic slot against local google/gemma-4-e4b
via LM Studio's OpenAI-compatible API. It was accepted with RR 0; TPS was
unavailable because the stats were empty. Details are in the private run record.
No corpus data was used. This entry records the supplied account without claiming
independent verification, model-run execution by Codex/Astra, or benchmark validity.

The same user authorized a new lmstudio-native provider. Codex (Astra) authored
its loopback-only/no-key implementation and native count/time interpretation,
tested solely with fake servers. No real LM Studio endpoint was contacted by
Codex. Native field interpretation does not retroactively manufacture timing for
the earlier compatible-API run.

## Manual development authorization and conflict (2026-09-29)

The user authorized a separate local manual-dev branch and private draft kit.
Codex (Astra) authored the implementation, scripted-input regressions and draft
rubric/task scaffolding. No manual service session was performed by Codex.
The evidence is dev-manual-human-coded, excluded from publication, and cannot
verify human coding correctness. When the task author also builds the competing
Skopos product, that author/product conflict must be disclosed; these results
remain internal-only. Independent second-coder recoding is deferred. Claude
reviews before any push; no legacy code or CLAUDE.md was edited.

## Authorized run history and fence-v1 decision (2026-09-29)

The user reports the following runs performed by Claude with user authorization
on 2026-09-29; details remain in private run records, not this public repository:

- First local smoke: synthetic, LM Studio OpenAI-compatible API, accepted,
  TPS unavailable because stats were empty.
- First TPS/eTPS measurement: synthetic, native API, 9 tokens / 0.2515 seconds,
  approximately 35.79 tokens/second. LM Studio's own decode-only figure was
  44.88 tokens/second. The first-token timing convention remains an open decision;
  these figures are not presented as equivalent measurement definitions.
- FIRST CORPUS RUN: all 11 tasks, local google/gemma-4-e4b, max_tokens 256,
  strict parsing, 0/11 accepted. The user-reported diagnosis identifies Markdown
  fences (seven would be correct without them) and reasoning-token exhaustion.
  The recorded results are not rescored. No task text, payloads or answer keys
  are included in this account.

Prior exposure (S4): the corpus has now been exposed to google/gemma-4-e4b,
locally only. This supersedes the earlier unknown/no-recorded-run state; it does
not assert anything about exposure outside the supplied run history. These are
user-reported Claude executions, not independently verified Astra executions.

After that first local corpus run, the user adopted the frozen, versioned
fence-v1 extraction rule and chose max_tokens 2048 for future runs, with reasoning
tokens counting against it. Codex (Astra) authored the opt-in implementation,
new synthetic regressions and private-kit update under local-commit-only
authorization. Existing evidence, budgets and parsing results remain unchanged.
Codex made no real model calls. Claude reviews the local commit before pushing.

## Reset/session authorization, exposure and two-day plan (2026-09-30)

The user authorized Day 1 on `v02-reset-profile` from main `a23a4f5` or later:
session_boundary nodes, per-arm full versus reset-v1 context, processed prompt
token telemetry, paired descriptive reporting, and a private mapping-v2-reset
derivation. Codex (Astra) authored the implementation, eight new synthetic
tests, documentation and private derivation. The existing 207 tests remain
unchanged; all 215 pass with full-path Windows Python 3.14. Only fake servers
were used for live adapter checks. The requested Claude Opus 5.5 co-author
trailer does not change this implementation-authorship record.

The private 11-task derivation is explicitly "UNREVIEWED DERIVED DRAFT; boundary
placement is a proposal for user review". It adds one boundary immediately
before each first-question user node, plus the necessary incoming-edge change.
All other byte spelling is preserved and inverse edits reproduce each source
exactly. All 264 existing-script slots under full/reset-v1 validate and replay;
these are synthetic checks, not model results or semantic validation. The seven
original SHA256SUMS entries verify identically before/after and 1,078 source
mapping files remain unchanged. Known retained_fact/clarification/expired/
mixed_recovery wording issues are deliberately retained for corpus vNext, a
separate user decision. No corpus payloads, keys or private hashes are published.

The user's two-day plan is recorded without authorizing or starting Day 2:

- Day 1: eTPS reset/session profile and private reset derivation, allowing
  context loss and meaningful recovery burden so RR and experimental eTPS can
  differ from a zero-recovery baseline and raw TPS respectively.
- Day 2 (separate, not started): nyx-bridge in its own repo/folder, NOT inside
  ProjectNyx. An OpenAI-compatible proxy extracts facts from chat, records them
  through Nyx's existing public APIs, injects retrieved beliefs, and forwards
  to the local model. Test it as a third arm against full/reset baselines;
  label results "Nyx-backed prototype memory", allow Nyx to lose, and disclose
  the author conflict.

Exposure register: Codex/Astra authored the corpus/mapping/harness and has seen
the private material; the user states reviewer Claude has seen corpus content
during review. This supplements the previously reported local exposure to
google/gemma-4-e4b. Claude's review is not evidence of unexposed or independent
corpus authorship. The profile author/system affiliation remains a conflict;
delegation to a proxy, another repository, or model assistance does not remove
it. No claim about other undisclosed exposure is made.

Authorization is local commits only, followed by a stop for Claude's check.
Claude will push and open the PR. Codex made no live model calls, pushes or PRs
and did not begin nyx-bridge or modify ProjectNyx.

## Authorized run reports and memory-arm support (2026-09-30)

The user attributes the following authorized local runs to Claude on 2026-09-30:
mapping-v2-reset with fence-v1 and 2048 output tokens accepted 7/11 full and
3/11 reset. Initial observations of experimental eTPS below TPS included
scheduled_recap, 44.59 to 35.95, and supersession_current, 42.83 to 36.88.
With mapping-v3 under d10-v1 and decode-v1, full accepted 8/11 (7 exact and
1 deviation), while reset accepted 6/11 (4 exact and 2 deviations); four
recovered reset trials had eTPS below TPS. These are user-reported calibration
results, not independently verified Codex runs, and no previous run is rescored.

The user reports LM Studio prompt caching reducing TTFT to approximately
0.1 seconds across runs. Server cache state affects TTFT/prefill diagnostics;
under warm-declared, those measurements must not be compared across arms.
The user selected warm-declared as the default cache condition for future plan
authoring. It remains an explicit optional plan declaration, with no implicit
upgrade of old plans or cache flushing/warming performed by the harness.

D10 remains as merged. The user approved code <- project_code and
word <- access_word aliases, with code/word values case-sensitive. The alias
lists are calibration-informed from the previously disclosed model failures,
not independent prospective evidence. Decode-v1 remains primary timing.

The planned three arms are Gemma full, Gemma reset, and Gemma reset plus the
nyx-bridge prototype. Results must be labeled "Nyx-backed prototype memory";
Nyx is allowed to lose. The profile author also develops the evaluated system,
so the author/system conflict remains. Separate sessions or repositories do not
remove that conflict or constitute independent corpus authorship.

Codex authored the eTPS arm-comparison, optional memory-telemetry and cache
declaration support, new synthetic tests, and documentation on
`v02-memory-arms` from main `8827759`. Main's existing test files are unchanged.
Only fake servers were used; no corpus text was added, no live model calls were
made, and the separate nyx-bridge workspace was not accessed or modified. The
Co-Authored-By trailer follows the existing contribution convention and does not
establish completed independent review. Authorization is local commits only,
then a stop for Claude's check; Claude pushes and opens the PR.

## Delivery authorization and interpretation of reset baselines (2026-09-30)

The user identified the pre-boundary delivery gap and authorized one additional
local commit on v02-memory-arms. Under prior reset-v1 behavior, earlier user
messages could be cleared before any request was sent. For stateless models,
undelivered and forgotten earlier messages are equivalent at the next request,
so the user-reported 2026-09-30 reset-v1 runs stand as a no-memory baseline.
They are not retrospectively rescored and cannot establish delivered-session
memory retention. For memory arms, omission is failed harness delivery under
contract section 3; those arms require opt-in deliver-v1.

Codex implemented the plan-wide delivery request, raw-evidence replay checks,
separate processing diagnostics and new synthetic tests. All arms use the same
delivery policy, and delivery output receives no correctness or primary TPS
credit. Transport failures are disclosed and budget enforcement remains in
force. Tests use ephemeral fake servers; no live model calls, corpus material,
or nyx-bridge access were involved. This is local implementation evidence, not
an executed three-arm experiment or independent review. Stop for Claude's check
after the local commit; Claude remains responsible for push and PR.
