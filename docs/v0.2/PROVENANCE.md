# eTPS v0.2 provenance

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
