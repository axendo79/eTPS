# Within-plan corpus aggregation

`corpus-aggregation-v1` implements [maintainer ruling 2](STATE_RECORD_OPTIONS.md#maintainer-rulings-2026-10-06):
one plan per repeat, per-arm aggregation within that plan only. No cross-plan
or cross-repeat pooling is admitted. This is diagnostic reporting, not a new
score, efficiency multiplier or winner test.

API: `aggregate_report(plan_bytes, artifacts, per_plan_report, grouping)`.
`grouping` is a separately frozen closed object with `version` =
`corpus-grouping-v1`, one nonempty `repeat_id`, and the exact `plan_sha256`.
The existing strict plan does not accept a repeat field. This explicit external
declaration binds repeat identity without changing old plans. The tool requires
one byte-string plan and one report object; arrays of either, repeat arrays,
different plan hashes, duplicate slots, and missing planned slots are refused.
Multiple task trials already declared within that one plan remain separate
slots; the tool never interprets them as another repeat.

```text
python -B -m etps_v02.intake.corpus_aggregation --export EXPORT.json --grouping GROUPING.json --output NEW_REPORT.json
```

The CLI replays v1/v2 evidence exports and recomputes their reports, ignoring
saved derived reports. It never dispatches a model or contacts an endpoint.
Output creation is exclusive. API callers supply a replayed per-plan report;
the API checks identity/accounting, not the authenticity of an externally
invented report. A declaration/hash cannot prove that no undisclosed runs occurred.

Each arm has overall, primary-family and individual coverage-tag buckets.
Tags overlap, so tag counts must not be summed into a corpus total. Each bucket
reports acceptance planned/attempted/accepted/failed/unavailable/unattempted counts
and reasons. `accepted_over_planned` preserves the planned denominator;
`complete_rate` is null when acceptance observations are incomplete. It leaves
the runner's existing acceptance summaries unchanged.

Each first-attempt and terminal dimension reports correct, planned, attempted,
unavailable and unattempted field counts, exact correct/planned ratio (null for
zero planned), reason counts and detailed unavailable reasons. A whole set is one
field. All six dimensions appear, even if unused. Attempted means the selected
answer event requested that field, including a timeout or invalid measurement.
No observation or an omitted logical field is unattempted at field level; omitted
fields specifically carry `field_not_supplied` and zero attempted count.
Unattempted slots carry `unattempted`. Invalid measurements make both phases
unavailable with their invalidation reason. Aborted slots retain `operator_abort`
when supplied. Wrong, unknown, malformed and timeout answers are distinct.

The immutable logical field map is read from mapper-generated hash-bound
manifest metadata. Every question's dimensions must be an unchanged subset.
For differing subsets, observations are interpreted against that single map:
omitted fields are unavailable, never redefined. This resolves the older
`heterogeneous_field_plan` reporting gap under ruling 1 without modifying any
existing scorer/runner/replay output. The selected observations are the first
scored answer and last scored answer on a finished path, per SET_ANSWERS.
Per-slot field statuses remain in the aggregate artifact for audit.

Refusals: `multiple_plans`, `multiple_reports`, `grouping_fields`,
`repeat_identity`, `plan_mismatch`, `plan_invalid`, `slot_accounting`,
`report_shape`, `field_identity`; format checks also preserve their reason codes.
CLI evidence/read/write failures use `evidence_unavailable` or bounded-reader
codes. All outputs use sorted canonical JSON and exact integer ratios.

See [authoring format](AUTHORING_FORMAT_V1.md), [mapper](AUTHORING_MAPPER.md),
[freeze](CORPUS_FREEZE.md) and [runbook](AUTHORING_RUNBOOK.md). Synthetic tests
exercise recovery, missing fields, every outcome class, incomplete plans,
repeat/plan refusals and both evidence-export formats.
