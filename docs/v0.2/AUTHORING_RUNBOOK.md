# Isolated author-session runbook

This is the maintainer's procedure. The author receives only AUTHORING_BRIEF.md,
including its complete `authoring-v1` format. Do not send this runbook, the corpus
specification, implementation, denylist, prior results, governance material or
repository to that session. Codex authored tooling and SYNTHETIC software fixtures
under user authorization; this tooling session must not author any real task,
development task, answer key or prediction because it has implementation exposure.
No author session or corpus execution is performed by these instructions.

## Launch and custody

1. Choose an author/model without evaluated-system implementation exposure.
   Obtain and record its prior-exposure statement rather than inferring independence
   from a new session. The route remains developer-directed and non-canonical
   under the accepted specification. A future independent-human corpus is a
   separate release, not a relabeling of this one.
2. Launch a **fresh model session** with a new empty conversation, no inherited
   conversation, project instructions, files, saved context, connectors, browsing,
   shell, or repository tools. Use a session with **no repository access**, not a
   coding session attached to this workspace. If isolation cannot be established,
   record the problem and do not author the real corpus there.
3. The sole task message is the complete text of `AUTHORING_BRIEF.md`. Attach or
   paste only that document, preserving its version and saving the exact bytes
   supplied. Do not include filenames/paths to code, arm/system names, examples
   from earlier tasks, expected winners or results. Record provider/model identifier
   and session identifier before generation. Capture author output and raw session
   response in the private intake area, preserving original bytes.
4. For each development/evaluation instance, the only document can include a
   neutral parameter appendix to the brief: dataset, selected count targets,
   chain-length range, distractor/pressure settings and context budget. Initially
   request development proposals; after development, insert only the frozen
   settings in the evaluation instance. Choose no numeric values in this tooling
   session. Keep the base instructions at `authoring-brief-v1`; distinguish instance
   bytes by SHA-256 and corpus release. A change to rules rather than selected
   parameters requires a new brief version and separately tested validator support.
   Run the separate denylist scan on every instance before giving it to the author.
   The appendix contains no results, evaluated-system behavior or governance text.
5. Preserve public message identifiers for every arm. Freeze the maintainer-only
   A–F mapping to the six specified conditions with the arm/configuration records.
   E/F may have null predictions with structural reasons; never provide internal
   behavior to make the author predict them.
   Predictions are never used to drop or adjust tasks.
   Record per-task predictions and the derived per-family summary.

Private output destination is the literal placeholder
`<PRIVATE_CORPUS_ROOT_OUTSIDE_PUBLIC_REPOSITORIES>`. Do not create this placeholder path.
The maintainer later chooses a real private directory outside every public
repository. Originals, dev/eval task text, keys, session records, derivations,
review evidence and receipts stay there. Nothing is copied to public test fixtures.
Use separate `development/` and `evaluation/` directories with separate receipt
files outside each inventoried bundle. This runbook creates neither directory.

An intake/review custodian may inspect content. Anyone changing an evaluated
system's code/configuration must not inspect evaluation text or keys before the
run. Record every inspection; a separate session or repository does not remove
affiliation or exposure. Stop release if that separation fails.

## Record provenance before mapping

Apply [CORPUS_INTAKE S1–S16](CORPUS_INTAKE.md#1-required-source-material).
For each item record present, absent in source, or ambiguous with evidence;
absence is never filled by mapper inference.

- **S1:** byte-exact originals and SHA-256 before opening for mapping; preserve
  originals read-only. Retain raw author response as well as its extracted JSON.
- **S2:** named author, date, model assistance, exact model/provider identifier,
  session identifier, exact brief bytes/hash, corpus version and derivation.
- **S3:** relationship to every evaluated component, including Nyx; author and
  maintainer affiliation/funding/direct interests. Disclose developer direction
  and non-canonical status even if the isolated author saw no implementation.
- **S4:** declarant, date, corpus_version, prior_runs `yes`/`no`/`unknown`, known
  dates/counts/configurations, manual/model inspection and resulting revisions.
  Unknown stays unknown. Record known exposure instead of claiming none by default.
- **S5–S10:** profile identity, stable task order, full plain state histories,
  explicit requirement intervals, scheduled messages/recaps, frozen field maps,
  keys, exact unknown objects, and deterministic answer rules.
- **S11–S13:** every outcome branch, bounded retries, exact corrections and byte
  spans/new content, mandatory assertions and required/forbidden action constraints.
- **S14–S16:** exact budgets, model settings, context/overflow policies, cache/reset
  behavior, declared run count/order/stops/completeness and pinned arm definitions.
  Corpus hashing does not implement any missing budget or action enforcement.

Use `authorship.json` in [the freeze record format](CORPUS_FREEZE.md), with
`author-session-v1` and all required S2–S4 fields. Detailed disclosures, original
responses and the complete intake checklist can be additional frozen artifacts.
Do not fabricate author statements, known runs, dates, numeric budgets or provenance.

## Development, then evaluation

### 1. Development set

Launch the isolated development session as above and preserve its outputs before
intake. Run the admission/mapping/review procedure below. Tune counts, chain lengths,
distractor volume and context budget **only** using the separately disclosed
development set and separately authorized development executions. Record every
attempt and revision. This runbook does not authorize a model run.

Choose the final design, overflow behavior and other S14–S16 settings before
evaluation authoring. Preserve development revisions with their old hashes;
produce a reviewed final development bundle and separate freeze receipt.
Verify that receipt before using its hash as the evaluation parent. If no authorized
development evidence exists, do not pretend tuning has happened: record it absent.

### 2. Evaluation set

Use a fresh isolated session with only the evaluation brief instance, containing
the neutral frozen parameters selected above. Preserve that brief's exact bytes.
Author a new set with distinct task IDs; target about six tasks per F1–F8 plus
controls, roughly fifty, and freeze actual counts. Do not show development answers,
run results or evaluated-system implementation. Apply the same intake/review
procedure. Require untouched evaluation tasks, keys, field maps and predictions
before any evaluation execution. The evaluation bundle includes the byte-exact
`development-freeze.json` and its SHA-256 in `settings.json`.

No tuning, replacement or selective deletion follows evaluation outcomes.
Corrections create a new corpus release, review, brief instance where applicable,
and freeze receipt. Preserve the old release/results and rerun all comparison arms;
never repair an old result silently or combine releases/repeats.

## Admission, derivation and human review

These commands describe future private intake by the authorized custodian.
Replace placeholders explicitly; do not run them with the literal placeholder.
Windows PowerShell can use this interpreter without installing dependencies:

```powershell
$TaskPython = 'C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe'
& $TaskPython -B -m etps_v02.intake.authoring ORIGINAL.json
& $TaskPython -B -m etps_v02.intake.mapper ORIGINAL.json NEW_DERIVED_DIRECTORY
& $TaskPython -B -m etps_v02.intake.state_records --manifest NEW_DERIVED_DIRECTORY/task-0001.manifest.json --sidecar NEW_DERIVED_DIRECTORY/task-0001.sidecar.json
```

Run the explicit sidecar command for **every** task (the mapper already calls the
same validator). Preserve all receipts and reason-coded refusals. Review the
derivation log's source fields, output nodes, byte spans and requirement links
against the unchanged original. No text/offset repair is permitted during mapping.
Missing or contradictory source material is a finding for its author, not a guess.
`semantics_verified: false` is a mechanical pass only.

Create separately declared offline scripted contrast traces for every reachable
outcome branch: correct, incorrect, unknown, malformed and timeout; validate with
`validate_bundle(..., authoring=True)` and exercise each authorized recovery path.
These are mechanical traces, not predictions or model evidence. Never put real
tasks into public test fixtures. If a declared unknown list is empty, record that
the unknown outcome is unreachable rather than inventing an admitted unknown.

Before freeze, a named **human cross-check** review under maintainer **ruling 4**
compares sidecar versions, authority, transitions, scope/negation, lapse/reinstatement,
unresolved checkpoints/precedence and provenance with public source text. It also
checks executable requirement intervals/tested links, complete sets, answer keys,
field identity, correction branches/spans, recap schedule and coverage/counts.
Review must check semantic validity that neither validator proves. Retain findings
and their resolution evidence. Architecture-informed selection and affiliations
also require the specified independent challenge review; a software pass does not
replace it or establish canonical status.

Current unsupported forms are STUCK rather than approximated: delayed starts,
multi-probe failure linkage, alternative correct answer objects, and
`clarification_unrepresentable`. F9's legitimate-clarification subcase cannot
pass the present mandatory sidecar projection, despite scorer support. Obtain a
representation ruling and separately tested extension before releasing full F9
coverage. Do not drop the subcase or substitute a different control silently.

The **defect blocks release** rule is absolute: any sidecar/obligation/key
mismatch or unresolved corpus/protocol defect prevents freeze and use as valid
evidence. Write a closed `review.json` with cross-check true only after review,
empty defects only after every defect is resolved, and exact SHA-256 for every
other artifact. A mismatch invalidates release even when an execution would score.

## Freeze and later reporting

Place the exact brief, `authorship.json`, `settings.json`, reviewed original/
derived files and review evidence in the appropriate private bundle.
Counts must equal mapper counts; settings contain the declared design/budgets,
with no hidden defaults. Freeze and immediately verify:

```powershell
& $TaskPython -B -m etps_v02.intake.corpus_freeze create PRIVATE_BUNDLE NEW_RECEIPT.json --release RELEASE_ID --dataset development --frozen-at DECLARED_TIME
& $TaskPython -B -m etps_v02.intake.corpus_freeze verify PRIVATE_BUNDLE RECEIPT.json
```

For evaluation, select `--dataset evaluation`, a new release/receipt, and the
verified development parent. Record freeze time explicitly and preserve trusted
receipts separately. Verify before every use. Any changed/added/missing artifact
blocks use; a new receipt never silently replaces the old one. Confirmatory
execution additionally requires completed external attestation under the contract.
No hash or local commit provides independent timing/execution evidence.

Freeze exactly one plan file per repeat and its `corpus-grouping-v1` declaration
before execution. Aggregate per arm inside that single plan with
`etps_v02.intake.corpus_aggregation`; never combine plans or repeats. Report all
planned, attempted, unavailable and unattempted slots with reasons, first/final
dimension accuracy, family/tag coverage and acceptance. Keep primary measurements,
costs and existing trial reports. Publish only permitted opaque trial identifiers
and disclosure/configuration records; private text/keys remain private.

See [brief](AUTHORING_BRIEF.md), [format](AUTHORING_FORMAT_V1.md),
[mapper](AUTHORING_MAPPER.md), [aggregation](CORPUS_AGGREGATION.md),
[freeze](CORPUS_FREEZE.md), [sidecar intake](STATE_RECORDS_V1.md) and
[accepted specification](STATE_EVOLUTION_CORPUS_SPEC.md).
