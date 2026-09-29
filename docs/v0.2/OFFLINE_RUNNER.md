# Offline runner and replay store

## Opt-in typed answers (2026-09-29)

The descriptions of string-field projection below remain the default. A task
manifest may opt in with top-level `"answer_schema": "typed-v1"`. Expected and
unknown-answer objects, and projected responses, then allow flat string-keyed
objects with string, integer or null values. Booleans, floats, containers and
other shapes are malformed; integers and their string spellings are distinct.
Equality compares each field's type and value. Missing/extra fields or a wrong
valid value are incorrect. Unknown schema names and invalid expected/unknown
declarations are rejected. With `unknown_answers: []`, unknown is unreachable;
an undeclared unknown/refusal object is incorrect if schema-valid, otherwise
malformed. Timeout takes precedence over answer classification.

Projection and replay derive the schema from the immutable, hash-bound task
manifest. Journal layout is unchanged; absent opt-in retains string-only
projection and historical replay compatibility. Typed journals require exact
projection agreement, including types. Implementation identity warnings still
identify changed source files when replaying older evidence.

The authorized mapping policy uses bare retries: a recovery user message is
followed by a probe, without redelivering the question. Recap markers,
new-content annotations, state descriptions and affiliation disclosures may be
hashed task/node metadata or hash-bound sidecars; these are stored, not enforced.
Strict plans and scripts still reject extra metadata fields. Per-field failure
routing, broader state semantics and experimental design remain deferred.

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
    "storage_error": "invalidate",
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
python -m etps_v02 export offline.db --output evidence-v2.json --format v2
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

## Bounded correctness repairs (2026-09-29)

Codex (Astra) authored these local repairs under explicit user authorization. Arbitrary model response bytes are retained exactly in the journal. Answer projection accepts only UTF-8 string-field objects; numeric overflow, nonfinite numbers, lone surrogates, other JSON shapes and decoder depth failures project to a malformed answer and take the declared malformed branch. A completed failure or recovery retains RR. An unknown user payload still invalidates protocol accounting; it is distinct from a malformed or wrong model answer. Old serializable malformed JSON projections remain replayable with a `legacy_answer_projection` warning.

Storage failures use `storage_error`, while controller failures use `execution_error`. Existing plans with the old exact invalidation policy remain readable and executable; because their policy did not declare `storage_error`, they retain the historical `execution_error` fallback. If persistence cannot record an abort, the durable prefix remains available for explicit operator handling.

Malformed manifest, plan, script, record and export shapes fail with `InvalidRecord`, with field paths where practical. Expected CLI validation errors print a concise `error:` message, exit nonzero and do not create a database during rejected import. Large finite Python integers no longer overflow the finiteness predicate. Graph validation uses an explicit stack instead of Python recursion; the hardening below removes the all-node descendant sets.

Newly authored manifests and nodes reject unknown fields. Both may include an object named `metadata` for arbitrary JSON annotations: it participates in the manifest hash but has no executable meaning. In particular, putting a budget in metadata does not enforce a budget. Replay with `authoring=False` retains old unknown fields with `legacy_unrecognized_fields` findings and warnings; explicit authoring revalidation rejects them. Recovery spans require a failure probe that can precede the recovery node along a graph path and tests each referenced obligation. Mutually exclusive legitimate recovery branches remain allowed. This ancestry check does not prove dominance on every path; runtime scoring still checks an actually observed, active failure.

Replay compares each probe event against the slot's pinned response script in order, including transport status, decoded raw bytes and generation telemetry. Finished slots must consume the script exactly; unfinished or aborted slots may contain a valid prefix. Excess responses and completed leftovers are discrepancies. Finish metadata must name the terminal actually reached and use `reason_code: null` for acceptance or `system_terminal_failure` for rejection. Abort reasons must be declared invalidations. Legacy v1 finishes without a reason receive an explicit compatibility warning; contradictory reasons are never accepted.

Discrepancies produce `unverified_evidence` warnings, `evidence_verified: false` and structured `evidence_issues`. The primary score is invalid with unavailable RR and acceptance; diagnostic `recomputed_score` is separate and does not enter accepted counts or complete-group metrics. Reports retain every slot and count `evidence_unverified`. Unattempted slots have `evidence_verified: null`. A true value means these local script and finish/abort consistency checks passed, not independent attestation, completed execution, or proof against wholesale evidence replacement. Source mismatches retain their separate warnings.

## Resource safeguards (V07, 2026-09-29)

The named constants in `etps_v02/limits.py` are **software safety limits, not benchmark budgets**. They do not set trial counts, timeouts, acceptance thresholds or calibration policy. They are generous relative to the valid admitted baseline fixtures (at least 100 times their corresponding maxima); deliberately malformed, deeply nested model-answer probes are not admitted manifest/plan structure.

| Constant | Limit |
| --- | --- |
| `MAX_ARTIFACT_BYTES` | 256 MiB per artifact |
| `MAX_PLAN_BYTES` | 64 MiB per plan |
| `MAX_EXPORT_BYTES` | 1 GiB per export file read by the CLI |
| `MAX_MANIFEST_NODES` | 250,000 nodes |
| `MAX_PLAN_SLOTS` | 100,000 slots |
| `MAX_SCRIPT_RESPONSES` | 100,000 responses per script |
| `MAX_RESPONSE_BYTES` | 16 MiB per decoded response |
| `MAX_JSON_NESTING_DEPTH` | 1,024 nested containers |

New admission exceeding a limit raises `InvalidRecord` naming the constant. CLI input files are sized before reading, then read with a bound to catch growth after the size check. Structural JSON depth is scanned before full parsing, respecting quoted text and escapes. Base64 response size is checked before and after decoding. Node/slot/response counts are checked before semantic traversal. These ceilings do not guarantee that every combination fitting them is cheap; Python's JSON parser can also reject input at its own recursion boundary.

Historical database and in-memory export replay bypasses new bundle admission ceilings and reports `legacy_safety_limit` warnings for exceeded limits; explicit authoring revalidation enforces them. The CLI's export-file read ceiling and outer JSON depth check remain safety boundaries even for old files. Old journal hashes and evidence bytes are never rewritten to fit new limits. Integrity failures still reject evidence. Deep or otherwise malformed raw response JSON remains a model-answer outcome, distinct from an unmatched user payload protocol deviation.

R is counted by sorting and merging half-open intervals, without expanding byte-position sets. Validation retains the cycle check and computes reachability only for referenced recovery checks; it no longer stores every node's full descendants. Recovery-heavy graphs can still require repeated traversals. Append uses the database head and indexed tail within the same `BEGIN IMMEDIATE` transaction as the insert/head update. It no longer rereads the prefix. Full-chain verification remains on database open, replay and export, including detection of corrupted middle entries. Request records still duplicate conversation history; aggregate artifact/journal memory and dense-graph work are not universally bounded. The synthetic scaling regression uses 5,000 nodes and 2,000 appended events without a machine-dependent timing assertion.

## Implementation identity (V09)

Start records include a name-sorted SHA-256 map for every `etps_v02/*.py` module, Python version and `sqlite3.sqlite_version`. Only source CRLF line endings are normalized to LF before hashing; artifact and evidence byte hashes remain exact. The historical scorer/runner keys remain available for old clients. Replay compares recorded keys only. Missing identity fields or missing current module names produce `legacy_implementation_identity: partial`; absent fields are not invented as mismatches. Changed recorded modules are listed by filename in `implementation.changed` and the `implementation_mismatch` warning. Runtime-version changes are also named. Mismatches warn and recompute rather than rejecting otherwise intact old evidence.

Since V09, the legacy keys `scorer_sha256`/`runner_sha256` hold LF-normalized hashes, so older Windows journals may report a mismatch for unchanged source.

## Slot accounting and diagnostic pairing (V10)

`comparison_incomplete` means **slot accounting only**: at least one planned slot lacks valid, available RR. Its additive inverse is `slot_accounting_complete`. Neither field verifies experimental comparability. A finished measured failure may have available RR and remains counted; an aborted, unfinished or unavailable slot remains visible.

`arm_pairing` maps each declared task to every arm present anywhere in the plan, with `planned`, `finished` and `rr_available` counts, including zeros for an arm absent from that task. `equal_planned_counts` reports equality across those declared arms; a one-arm plan can satisfy it. It does not invent required arms, sample counts or thresholds. `unverified_dimensions` always lists schedule exposure equality across arms, mandatory assertions beyond terminal Boolean, budgets, and action constraints. There is no winner logic.

## Recovery-path diagnostic and export boundary

The optional V06 check emits `recovery_failure_not_dominating` when a path from the manifest start can reach a recovery node while bypassing its linked failure probe. It is a finding and replay warning, not a new rejection. Existing ancestry/tested-obligation rejection and actual observed-failure scoring remain unchanged; merely passing through a probe does not prove it failed or that an obligation was active.

## Opt-in export completeness (V08)

The earlier default-v2 attempt was stopped as recorded in the [historical hardening handoff](../V02_HARDENING_2026-09-29.md). V2 is now opt-in: call `export_bundle(store, format="v2")` or use `export DB --output FILE --format v2`. Omitting the option, or selecting `v1`, retains the existing v1 export layout and serialization. Unsupported API formats raise `InvalidRecord`; invalid CLI choices and replay integrity errors retain concise `error:` output and exit status 2.

`etps-offline-export-v2` includes all v1 fields plus an `envelope` with `slot_order` (planned IDs in plan order), `heads` (each database head's `count`, `hash`, and `state`), and `envelope_sha256`. The digest is SHA-256 of the canonical encoding of `[plan_sha256, slot_order, heads]`. Heads, journals and the report are read in one SQLite snapshot, preserving a caller-owned transaction. There is no schema migration.

V2 replay verifies the envelope digest, exact planned order, exact journal/head slot membership, journal lengths, final hashes (the plan/slot seed for empty journals), and lifecycle end states, alongside the existing chain and semantic checks. An inconsistency raises `InvalidRecord`; it is not downgraded to an unattempted slot or a warning. Thus accidentally emptying a completed journal is rejected in v2, while unchanged v1 behavior still reports that slot as unattempted.

Replay adds `export_completeness_bound: true` for verified v2 and `false` for v1. No new v1 warning is added. This flag means the supplied envelope matches the supplied evidence; it does not mean every slot finished or has available RR. Running, aborted and unattempted slots remain exportable and visible.

A coherent rewrite of the whole export, including journals, heads and envelope, defeats these checks. This is accident/truncation detection, with no signing or attestation and no proof of execution. Global cross-slot chronology remains deferred: the schema has per-slot sequence numbers and planned ordinals, but no global event sequence. See the [V08 opt-in handoff](../V08_EXPORT_V2_2026-09-29.md) for tests and the erased-attempt comparison.
