# authoring-v1 mapper

Codex-authored tooling only. API: `map_authoring(source_bytes)` returns a filename
to exact-bytes map; `recover_source(files)` checks the entire derivation again
and returns the byte-exact original. Original text is never edited for offsets.

```text
python -B -m etps_v02.intake.mapper SOURCE.json NEW_OUTPUT_DIRECTORY
```

The [authoring validator](AUTHORING_FORMAT_V1.md) runs first. All tasks are mapped
and pass [state-records-v1 intake](STATE_RECORDS_V1.md) in memory before output
creation. An existing destination is refused (`output_exists`). I/O errors report
`file_unavailable`; interrupted writes must be discarded and re-derived to a new
directory. No executable plan or experiment budget is invented.

Each task yields a typed-v1 + set-v1 manifest, bound sidecar, answer-key object,
field map, prediction file, intake receipt and derivation log. `bundle.json`
records versions, dataset, exact source SHA-256, task order, manifest SHA-256,
family and coverage counts. `family-predictions.json` groups only the supplied
per-task predictions/reasons by family and anonymous condition, with separate
failing/not-failing/unknown task-ID lists; it invents no prediction.
`source.json` preserves byte-exact original input.
The manifest's canonical digest equals its emitted byte SHA-256. Sidecar binding
hashes exact sidecar bytes. Correct paths reach acceptance; author-declared
failure paths reject or enter the exact correction/retry route. Questions are
new user nodes immediately preceding their answer probes. Scheduled recaps and
new-content spans are identified in hash-bound metadata, without changing scorer
semantics. The runner delivers node text, never keys or prediction metadata.

Requirement IDs/boundaries and tested links come from source. Version numbers
and reciprocal links come from the ordered version list. Public source message
IDs remain unchanged. Logical fields omitted at a question remain unavailable;
the separate [aggregation tool](CORPUS_AGGREGATION.md) handles diagnostic reporting.
Expected set fields, obligation lists, correction spans and predictions are
sorted; object keys use canonical JSON. Identical input bytes produce identical
output bytes, without timestamps or random IDs.

Each derivation log enumerates **every source JSON pointer**, including empty
containers, with output artifact/pointer targets and node/span/obligation/state/
field-map/prediction/metadata roles. A transformed container entry identifies its
output container; child entries are explicitly labeled `within mapped container`
when no direct leaf correspondence exists. The exact original remains available
for human field-level comparison; no line numbers are guessed after JSON decoding.
Generated node/hash/link conventions are listed separately. This implements the
field-to-artifact trace requirement in [intake §5](CORPUS_INTAKE.md#5-intake-procedure-when-the-files-arrive).

Mapping refusals include `delayed_obligation`, `multi_failure_recovery`,
`alternative_answers`, `clarification_unrepresentable`, `schedule_unrepresentable`,
`recovery_cycle`, `probe_obligation_inactive`, and `bundle_changed`. Format and
state-record intake reason codes propagate with their evidence paths. No refusal
becomes an approximation or a valid release. Delayed obligations and multi-probe
linkage are explicitly unsupported by the executable pilot (intake §3).
Clarification answers work in the scorer, but no clarification query projection
exists in the mandatory sidecar. This is a release blocker for F9's clarification
subcase until a separately authorized representation decision is supplied.

Synthetic round trips exercise A→B→C, A→B→A, lapse, reinstatement, unresolved
disagreement then precedence, partial/scoped updates, provenance, recaps, missing
logical fields and correction spans. These are mechanical checks, not semantic
validation. Human cross-check review is mandatory before [freeze](CORPUS_FREEZE.md)
under [ruling 4](STATE_RECORD_OPTIONS.md#maintainer-rulings-2026-10-06).
