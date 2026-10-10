# v0.2 authoring pipeline

This index is for maintainers. The isolated author receives only the
[neutral authoring brief](AUTHORING_BRIEF.md), which contains all authoring fields.
The pipeline consists of Codex-authored tooling and SYNTHETIC tests; it contains
no real corpus task, development task, key or prediction.

| Artifact | Purpose |
|---|---|
| [AUTHORING_BRIEF](AUTHORING_BRIEF.md) | Neutral purpose, families, balance, dimensions, size, predictions and complete hand-authorable format. |
| [Authoring format v1](AUTHORING_FORMAT_V1.md) | Closed JSON Schema and strict reason-coded admission. |
| [Mapper](AUTHORING_MAPPER.md) | Byte-stable executable manifests, bound state sidecars and full source-field derivation logs. |
| [State-records-v1/v1.1](STATE_RECORDS_V1.md) | Bounded intake; v1.1 adds only exact missing-information answerability; authoritative metadata, never scorer logic. |
| [Corpus aggregation](CORPUS_AGGREGATION.md) | Per-arm/family/tag diagnostics within one hash-bound plan/repeat. |
| [Corpus freeze](CORPUS_FREEZE.md) | Full artifact inventory, declared review gates, exact-byte change refusal and separate dev/eval records. |
| [Author-session runbook](AUTHORING_RUNBOOK.md) | Isolation, S2–S4 disclosures, private custody, development then held-out evaluation and human review. |
| [Advisory authoring lint](AUTHORING_LINT.md) | Literal vocabulary, restatement, ID-pattern and character-position observations; no admission or quality decisions. |
| [Human review sheet](REVIEW_SHEET.md) | Self-contained offline HTML with source-hash-bound checklists, notes and review-input-v1 downloads. |
| [Review record assembly](REVIEW_RECORD.md) | Complete checklists and empty defects to exact-artifact review.json, tested against the existing freeze gate in a temporary copy. |
| [Run handoff](authoring-pipeline-run.md) | Per-task commits, test-first evidence, totals, STUCK items and final task table. |

Follow the [accepted corpus specification](STATE_EVOLUTION_CORPUS_SPEC.md),
[maintainer rulings](STATE_RECORD_OPTIONS.md#maintainer-rulings-2026-10-06),
[measurement contract](MEASUREMENT_CONTRACT.md), [intake checklist](CORPUS_INTAKE.md),
[set-v1 answers](SET_ANSWERS.md) and [provenance](PROVENANCE.md).

All existing tests and scorer/runner/replay modules are preserved. The pipeline
never runs a model or infers source truth. No model judge, fuzzy matching,
unreviewed authority rule, or automatic corpus-semantic repair is admitted.
Numeric design and execution settings remain explicitly author/maintainer supplied.

The maintainer's [authoring rulings 1–4](PROVENANCE.md#maintainer-authoring-rulings-2026-10-06)
settle the earlier A3 STUCK choices: delayed requirements, multiple originating
failures and alternative correct objects are hard authoring-stage refusals.
F9 has one narrow versioned query: exact `status = missing_information` plus
an exact declared missing-item identifier when requested. Open-ended clarification
remains refused. The mapper opts these tasks into v1.1 and leaves all ordinary
v1 output bytes unchanged. Human sidecar/obligation/key review must precede
freeze; any unresolved defect blocks release as valid evidence.
