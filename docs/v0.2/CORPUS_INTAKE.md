# Corpus intake and gap review

Authorship/provenance: Claude (Claude Code) drafted this document on 2026-09-29 from a user-delivered instruction to prepare an intake and gap review while keeping the original import blocked. Requirements are traced to [contract](MEASUREMENT_CONTRACT.md) draft 4, [status](../STATUS.md) and [offline runner](OFFLINE_RUNNER.md). Schema behavior was read from `etps_v02/` at `90ebad1` and spot-checked with scratch validation calls; no code, test or fixture was changed. Updated the same day to reflect the authorized correctness repair (audit V04–V06) and the audit's G04 correction. Nothing here is corpus content, a reconstruction of the missing workload, or evidence of validity.

**Import status: BLOCKED.** The original authored workload is not in this checkout, `D:\eTPS-from-nyx` (a same-commit copy), the local nyx-memory checkout, or any `workload/corpus/manifest`-named file on `D:`. No task, manifest, answer key, budget or count below has a value. Unset fields stay unset until a source supplies them.

## 1. Required source material

Intake needs the original files, unmodified. Each row states what must be present before mapping can begin. "Source" means the original authored material, not a derived or model-restated copy.

| # | Item | Required content | Contract ref |
|---|---|---|---|
| S1 | Original files, byte-exact | Every file as authored, with no re-save, re-encode or line-ending conversion. Record SHA-256 of each at intake. | §2, §8 |
| S2 | Authorship record | Named author(s), dates, which parts were model-assisted and by which model. | §2, §2.1, PROVENANCE |
| S3 | Affiliation disclosure | Author's relationship to every evaluated component (including Nyx). The developer-authored profile is non-canonical. | §2.1 |
| S4 | Prior-exposure disclosure | Declarant, date, corpus version, prior runs known `yes`/`no`/`unknown`, known dates/counts/configurations, manual or model-assisted inspection, resulting revisions. Unknown stays unknown. | §2.1 |
| S5 | Profile identity | Profile ID/version and which candidate profile applies (session, long-context, persistent-memory, agent-task). | §2 |
| S6 | Task list | Stable task IDs and intended task order. | §8 |
| S7 | State records | Per proposition: stable ID, version, value, source event and authority, establishment event, valid-time interval, applicability predicate, supersession links, historical-vs-current status. | §3 |
| S8 | Obligations | Per obligation: state reference, establishment event, expiration/supersession event or end of trial. | §3 |
| S9 | Scheduled user events | Every scheduled user message with exact text, in order, including questions, new evidence, clarifications and scheduled recaps (marked as recaps). | §4 |
| S10 | Probes and answer rules | Per probe: which obligations it tests, expected answer, allowed alternatives, normalization, explicit unknown/refusal forms, handling of extra claims, ambiguity checkpoints. | §5 |
| S11 | Failure branches | Per probe outcome (correct/incorrect/unknown/malformed/timeout): next event, max retries, terminal failure after exhaustion. | §5 |
| S12 | Recovery variants | Per recovery branch: exact message text, state-bearing span(s) with obligation IDs, new-content span(s), linked failure probe. One variant per branch for the first pilot. | §4, §5.1 |
| S13 | Terminal acceptance | Per task: mandatory terminal assertions and required/forbidden action constraints. | §6 |
| S14 | Budgets | Timeouts, retry ceilings, output/processing ceilings, retrieval/storage ceilings, cache/reset policy. | §7, §9 |
| S15 | Calibration plan | Pilot run count, trials per arm, run order, stop conditions, treatment of unattempted slots, completeness threshold. | §8, §10 |
| S16 | Arm definitions | Pinned model/configuration per arm, decoding settings, memory-layer configuration. | §9 |

If an item does not exist in the original, record it as **absent in source**. Do not fill it during mapping; that is an authoring decision (§4).

## 2. Contract → executable schema map

Status key: **Supported** = expressible and checked by current code. **Restricted** = expressible only in a narrower form. **Unchecked** = can be stored but code does not interpret or verify it. **Missing** = cannot be expressed.

### Manifest and state

| Requirement | Executable form | Status | Note |
|---|---|---|---|
| Accounting unit | `unit: "utf8_bytes"` | Supported | Plan and every task must agree. |
| Task entry | `start` node ID | Supported | |
| State records (S7) | none | Missing | Obligations carry only `source`, `begin_after`, `end_before`. Value, version, valid time, applicability and supersession have no field. Applicability predicates are listed as unimplemented in STATUS. |
| Obligation begin | `begin_after` | Restricted | Must equal `source` (pilot restriction). Checkpoint-delayed starts are rejected. |
| Obligation end | `end_before`: node ID or `$trial_end` | Supported | Supersession can be modeled only as an expiration event; no link to the superseding state. |
| Historical vs current queries | separate obligation IDs | Restricted | Workable by convention only; nothing verifies the distinction. |
| Metadata (profile, author, disclosures) | `metadata` object (top-level or per node) | Unchecked | Hashed into the manifest digest but never interpreted. Since the 2026-09-29 repair (V05), other unrecognized manifest/node fields are rejected at authoring and reported as findings on replay. Plan fields are strict, so plan-level metadata is rejected. |

### User events and recovery

| Requirement | Executable form | Status | Note |
|---|---|---|---|
| Exact payload + hash | `text`, `sha256` | Supported | Identity normalization; hash verified. |
| Recovery spans | `spans: [[start, end, obligation_id], ...]` | Supported | Half-open, UTF-8 boundaries enforced, union counted. |
| Linked failure | `failure`: one probe ID | Restricted | One failure per user node. A recovery message addressing failures from two different probes cannot be expressed. Since the repair (V06), authoring requires the failure probe to be a path-ancestor that tests each span's obligation. |
| New-content spans (§5.1) | none | Missing | Only recovery spans exist. New content is implicitly "everything else" and is not separately designated or checked. |
| Variant ID and schedule (§5.1) | node ID | Restricted | Each variant is its own node; one variant per branch works. A predeclared variant schedule across trials is not expressible. |
| Scheduled recap marker (§4) | none | Missing | A recap is a span-less user node, indistinguishable in schema from any other scheduled message. |
| Whole recovery-message bytes | per-event `I` in classifications | Supported | Derivable from the report. |
| Probe question text | preceding `user` node | Supported | Probes add no prompt, so questions count in I. |

### Probes and answers

| Requirement | Executable form | Status | Note |
|---|---|---|---|
| Expected answer | `expected`: flat object; string-only by default, or string/int/null values with manifest `answer_schema: "typed-v1"` | Restricted | Opt-in typed-v1 uses type-strict equality. One correct answer; no bools, floats, lists, nested values, sets or alternative correct answers. |
| Response format | raw bytes parsed as strict JSON object | Restricted | Prose and fenced code blocks parse as **malformed**. Surrounding whitespace is tolerated. The original answer format must be a JSON object, or a response contract must be decided. |
| Normalization (§5) | none | Missing | Exact equality only. Case, spacing and field-set differences fail. |
| Extra claims | exact equality | Supported (strict) | Any extra field makes the answer `incorrect`, including compatible extras. |
| Unknown/refusal | `unknown_answers`: list of exact objects | Supported | Must be declared per probe; may be empty. |
| Clarification at ambiguity checkpoint (§5) | clarification as the `expected` answer | Restricted | A probe whose single expected answer is a clarification (e.g. `{"clarify":"unit"}`) is supported and tested. Not expressible: accepting either a clarification or a direct answer at the same probe, or a distinct clarification outcome; outcomes are fixed to `correct, incorrect, unknown, malformed, timeout`. (Corrected per audit G04.) |
| Total outcome policy | `next` over all five outcomes | Supported | Enforced. |
| Retry ceiling | unrolled acyclic graph | Supported | Cycles rejected; max retries = unrolling depth. |
| Probe obligations | `obligations` list | Supported | |

### Terminal, budgets and execution

| Requirement | Executable form | Status | Note |
|---|---|---|---|
| Binary acceptance | terminal `accepted: bool` | Supported | Acceptance is a property of the terminal node reached, not of evaluated assertions. |
| Mandatory terminal assertions (S13) | probe path to accepting terminal | Restricted | Assertions must be encoded as probes whose correct path reaches an accepting terminal. |
| Action constraints | none | Missing | Action verification is not implemented. |
| Budgets (S14) | none | Missing | Budget enforcement is not implemented. A budget placed in `metadata` is hashed but inert; anywhere else it is rejected. |
| Internal/replay/reset events | `internal`, `replay` kinds | Restricted | Scorer excludes them from I; the offline runner rejects them. Persistent-memory and reset profiles are not runnable. |
| Slots, arms, order | plan `slots` | Supported | Fixed before execution; no replacements. |
| Invalidation policy | plan `invalidation_policy` | Supported | Exact fixed map. |
| Live model execution | none | Missing | Offline scripted responses only; no adapter. |
| TPS / wall time | offline forced unavailable | Missing for live use | Requires an adapter with backend telemetry. |

### Defect found during review

A `failure` value that is a list (or other unhashable type) raised `TypeError` from `validate`, not `InvalidRecord`. Fixed by the 2026-09-29 correctness repair (audit V04); it now fails with `InvalidRecord`.

## 3. Decisions that need the original corpus

These cannot be made from the contract or code alone. Each is answered by inspecting the original.

1. **Answer format.** Are the original probe answers already structured, or prose? If prose, choose between a JSON response contract (changes the task's public instructions) and a new answer-parser design. Either is a protocol decision, not a mapping step.
2. **Answer shape.** Do any answers need lists, sets, multiple correct forms or normalization? If so, the scorer's answer predicate needs a versioned extension before import.
3. **Delayed obligations.** Does any obligation begin after a checkpoint rather than at establishment? If so, the pilot restriction blocks the task.
4. **Multi-failure recovery.** Does any recovery message re-supply state for failures observed at more than one probe? If so, `failure` must become a list with defined linkage semantics.
5. **State model.** Do tasks depend on supersession, valid time or applicability beyond what expiration events capture? If so, decide whether a state-record sidecar (unchecked) is acceptable for the pilot or the schema must grow.
6. **Recaps.** Which scheduled messages are recaps? A marker is needed so recaps are "separately identified" (§4).
7. **New-content spans.** Do recovery messages mix new facts with re-supply? If so, decide whether to add explicit new-content spans or split messages (§4 recommends separating clauses).
8. **Clarification.** Does any probe accept *either* a clarification *or* a direct answer? A clarification-only expected answer already works; accepting alternatives needs a versioned answer-predicate extension.
9. **Profile.** Which profile applies? Anything other than a session-style profile with user/probe/terminal events is not runnable offline.
10. **Arms.** Which model/configuration and memory layer form each arm? Needed before any live adapter is scoped.
11. **Mapping fidelity.** Every mapped file must trace to its original with a derivation log. Any place the mapping has to change meaning is a finding for the user, not a silent edit.

## 4. Unset values register

None of these has a value in any repo document. They must be frozen before calibration and cannot be chosen after observing results.

| Value | Needed for | Current state |
|---|---|---|
| Per-request deadline | timeout outcome | UNSET |
| Per-task wall-clock limit | bounded terminal failure | UNSET |
| Max retries / recovery depth per probe | branch unrolling | UNSET |
| Output token ceiling per response | budget | UNSET |
| Retrieval, storage and internal-input ceilings | memory arm budget | UNSET |
| Cache and reset policy | comparability | UNSET |
| Decoding settings (temperature, seed, etc.) | arm fixity | UNSET |
| Pinned model and endpoint version per arm | arm identity | UNSET |
| Number of scheduled pilot runs | calibration | UNSET |
| Task-trial count per arm | calibration | UNSET |
| Run order / randomization | calibration | UNSET |
| Stop conditions | calibration | UNSET |
| Completeness threshold | complete-workload comparison | Proposed by model: zero RR-unavailable trials (§8). Not frozen. |
| Mandatory terminal assertions per task | acceptance | UNSET (corpus-dependent) |
| Action constraints per task | acceptance | UNSET (not implementable yet) |
| Criterion 1: new user bytes across all attempts / accepted completions | calibration reference | Defined (§10); no reference value or comparison rule frozen |
| Criterion 2: end-to-end task time across all attempts / accepted completions | calibration reference | Defined (§10); no reference value or comparison rule frozen. Offline wall time unavailable. |
| Order-agreement reporting rule | calibration | Defined as a pairwise map with reversals listed; no threshold, deliberately |

## 5. Intake procedure when the files arrive

1. Place originals outside the git working tree (for example a sibling private folder). `private/` and `corpus-private/` are ignored by `.gitignore` but originals should still live outside the working tree, and PROVENANCE excludes corpus publication. No commit or push without explicit instruction.
2. Record SHA-256 of every original file and the S2–S4 records before opening anything for mapping. Keep originals read-only.
3. Fill section 1: mark each item present, absent in source, or ambiguous.
4. Answer section 3 decisions with the user. Any decision that requires a schema change becomes a separately versioned change with tests, before import.
5. Map to executable manifests as separate derived files. Keep a derivation log from original lines/fields to nodes, spans and obligations. Verify spans with the scorer's boundary check; do not adjust text to make spans fit.
6. Run `validate_bundle` (authoring gate on) with a plan whose slots use scripted fixture responses only. Contrast traces cover every outcome branch. This checks mechanics, not semantics.
7. Semantic review of the mapped corpus, including aliases, negation, time and applicability (CLAUSE_REVIEW S11).
8. Freeze section 4 values in the calibration manifest; commit the manifest hash only when instructed. Live runs remain a separate authorization.

## 6. If the original is permanently unavailable

That requires an explicit user decision, recorded in PROVENANCE. The alternative is a **new, separately named corpus** with its own authorship, affiliation and prior-exposure records. It is not a reconstruction of the missing workload, may not reuse its name or version, and is not evidence of benchmark validity. The section 1 checklist and section 4 register apply to it unchanged.
