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
