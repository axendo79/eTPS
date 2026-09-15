# Offline runner and replay store

This is verification infrastructure for the finite byte schema, **not a model runner or the unpublished workload**. Only `purpose=offline-verification` is accepted. There are no network clients, model loaders, credentials or live adapters. A schema adapter for the original workload cannot be verified until those files are supplied.

## Inputs

The plan is strict UTF-8 JSON with exactly these fields:

```json
{
  "schema": "etps-offline-plan-v2",
  "unit": "utf8_bytes",
  "invalidation_policy": {
    "script_exhausted": "invalidate",
    "script_leftover": "invalidate",
    "execution_error": "invalidate",
    "interrupted": "invalidate",
    "operator_abort": "invalidate",
    "system_terminal_failure": "retain"
  },
  "purpose": "offline-verification",
  "tasks": {"task-id": "SHA256_OF_EXACT_TASK_FILE_BYTES"},
  "slots": [
    {"id": "trial-1-baseline", "arm": "baseline", "task": "task-id", "script_sha256": "SHA256_OF_SCRIPT_BYTES"}
  ]
}
```

The plan pins `unit: utf8_bytes`; every task must agree. Every slot is fixed before execution. Include all intended arms and repetitions in their intended order. Each artifact is supplied explicitly; missing, changed or unreferenced files are rejected. Sources are read without modification. File-byte hashes are distinct from the scorer's canonical-JSON identity; both are retained.

Task files use the existing scorer's `unit`, `start`, `obligations` and `nodes` schema. This runner supports only `user`, `probe` and `terminal`; internal/reset/retrieval actions are rejected rather than silently skipped. User nodes deliver their exact text into the offline conversation; a probe requests the next scripted response without adding an uncounted prompt. Questions must therefore be declared user nodes. Obligations use `source`, `begin_after` (the establishment event ID) and `end_before` (an expiration event ID or `$trial_end`). Pilot restriction: `begin_after` must equal `source`; checkpoint-delayed obligation starts are not implemented. This is not a general restriction of contract §3. They become active after establishment and expire before the named event. Recovery branches cannot move these semantic boundaries. Finished journals record the resolved half-open index pair; replay also exposes the event IDs and recomputed pair. An unreached boundary is reported as unresolved, never guessed. New plans reject positional intervals. Legacy v1 exports remain readable with a positional-boundary warning.

Each probe declares `unknown_answers`, a list of exact string-field answer objects (an empty list is valid). Unknown/refusal spellings have no special meaning unless declared by that probe. Old records lacking the field use the historical shapes only during replay, with an explicit compatibility warning. Overlap with the correct answer is rejected.

A response script has one field, `responses`, containing an ordered list of objects with `status` (`ok` or `timeout`), `raw_base64` (exact response bytes), and optional `generation` (`tokens` integer and positive `seconds`). No answer-key lookup generates responses. JSON duplicates, invalid encoding and non-JSON answers become malformed model-outcome fixtures. Exhaustion is `script_exhausted` (coverage defect); leftovers are `script_leftover` (authoring count error). Both invalidate the slot under its predeclared policy. A bounded terminal failure is `system_terminal_failure`, retained as a finished measured failure. Operator abort requires a declared code, with optional explanatory text. Synthetic generation is retained only as fixture input; TPS and experimental eTPS are forced unavailable in offline replay, reports and exports. Wall time is unavailable, never inferred from offline execution speed.

Recovery grants are single-use per obligation. All spans in one recovery event are union-counted before its grant is discharged; a correct probe clears any remaining standing failures for its obligations. A later message citing a consumed or corrected failure is scheduled input (I only, R=0), with the stale linkage visible. A never-observed/unrelated failure remains a protocol error. Import validation rejects two recovery user nodes on a common path citing the same failure/obligation; mutually exclusive branches are allowed. Legacy offending traces can still be recomputed with authoring warnings and corrected counts.

## Commands

```bash
python -m etps_v02 import offline.db --plan plan.json --artifact task.json --artifact responses.json
python -m etps_v02 run offline.db --slot trial-1-baseline
python -m etps_v02 report offline.db
python -m etps_v02 export offline.db --output evidence.json
python -m etps_v02 replay-export evidence.json
python -m etps_v02 replay-export evidence.json --validate-authoring
python -m etps_v02 abort offline.db --slot interrupted-slot --code interrupted --reason "Interrupted offline execution"
```

Import refuses an existing database. Export refuses an existing output file. Reports include every planned slot, including unattempted, running, aborted and finished slots, with failed and unavailable outcomes. The `summaries` list is scoped per task and arm: input bytes per accepted completion, wall seconds per accepted completion, and labeled pooled `sum(R)/sum(I)`. Measured failures stay in cost and pooled-RR numerators. Unattempted or invalid trials block complete-group metrics with explicit reasons. Offline wall-time cost remains unavailable. Unlike task manifests or arms are never pooled. No cross-task composite or ranking is produced.

## Persistence and recovery

SQLite stores the exact plan and artifact bytes, fixed slot order, request intents, and raw replay events. Each journal append and its head update are one transaction. WAL with FULL synchronous mode provides SQLite's durability guarantees subject to the host filesystem. No legacy database is migrated or reused.

Requests are journaled before consuming a scripted response. A durable unfinished slot cannot be resumed or silently rerun; explicitly abort it and preserve the original attempt. There are no replacement slots added after the plan. Backend exactly-once delivery is not claimed.

Reopening verifies plan/artifact hashes, ledger membership, journal sequence/hash links and heads. Replay recomputes classifications and exact fractions from events. Update/delete triggers protect immutable records from normal API mistakes. These checks detect tested corruption; an administrator who coherently rewrites the whole database can defeat them. This is not independent attestation. Source-hash mismatches produce explicit warnings, recorded/current hashes and recomputed results; they do not block replay. `replay-export` ignores the old derived report and recomputes from verified artifact/journal content. Legacy schemas remain labeled rather than silently upgraded. Schema compatibility (`allow_legacy`) and authoring enforcement (`authoring`) are separate loader choices. Normal evidence replay explicitly relaxes the latter; `replay-export --validate-authoring` reasserts the current gate, including for v2 exports. Its result records `authoring_gate_reasserted`. Retain source revisions to reproduce old behavior exactly. Integrity failures still block trusting corrupted evidence.

Run `python -m unittest discover -s tests -v` for synthetic scorer and storage/controller tests, including fresh-process CLI replay. Model endpoint timing, budget enforcement, action verification, retrieval/reset behavior and real-workload integration remain unimplemented.
