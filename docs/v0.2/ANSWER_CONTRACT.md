# Opt-in v0.2 answer contract

The maintainer adopted the four-state vocabulary and compressed H3 wording on
2026-10-15 for **new, explicitly opted-in releases only**. Declaration schema:
`etps-question-contract-v1`; question contract version: `h3-compressed-v1`.
Absence of a declaration, or an explicit `legacy-v1` declaration, leaves legacy
releases unaffected: no new wording, key rewrites, label changes, rescoring or
replay changes. A frozen release cannot be opted in retroactively. Prepare a new
release, execution derivation and freeze inventory before using these rules.

This is an answer-format contract, not benchmark validation. TPS, input-based RR,
binary terminal acceptance, first-attempt retention and measurement validity keep
their existing separate meanings. The checker below is a custodian diagnostic;
it neither executes a model nor changes strict scoring. Existing `d10-v1`
digit-string tolerance and `fence-v1` extraction remain uniform across arms when
declared. Preferred integer/no-fence wording does not remove those policies.
The 2048-token probe reply reserve is unchanged. Budget and headroom checks must
include the rendered questions before freezing; no token-cost claim is made here.

## Status vocabulary and event precedence

Apply each field to its exact entity, property, scope and conversation point.
Current means after the latest delivered applicable event. A checkpoint means
just after the named public message; later events never change its answer.

| Ordinary label | Meaning |
| --- | --- |
| `active` | One value is in force, including an unchanged, updated, reinstated or explicitly settled value. |
| `expired` | An established value was explicitly withdrawn or lapsed, with no replacement or reinstatement in force. |
| `unestablished` | The asked property/scope has never been established by that point. |
| `unresolved` | Distinct incompatible supplied claims still compete, without explicit applicable precedence selecting one. Absence or model uncertainty is not disagreement. |

Selection follows evidence and events, rather than a ranking of label words:

1. Select the question's meaning and checkpoint first. An ordinary never-supplied
   property is `unestablished`; a designated required-item question uses the
   separate missing-information form below.
2. Without establishment, ordinary status is `unestablished`. Otherwise follow
   the admitted event sequence: unchanged state persists; explicit lapse gives
   `expired`; reinstatement gives `active`; an unresolved disagreement persists
   until explicit applicable precedence gives `active`. Recency alone does not
   settle competing claims. No new transition, such as unresolved-to-expired, is
   introduced by this contract.
3. After settlement, subsequent supported changes, lapse or reinstatement govern
   the current answer. An old disagreement has no permanent priority. `resolved`
   describes coverage/history only and is never an ordinary status answer.

These terms define benchmark task state, not a memory system's trust hierarchy,
merge behavior or storage representation.

## Designated missing information

Only a designated question about a declared required item that was **never
supplied before that question** uses `{"status":"missing_information"}`. When
requested, add the exact declared item ID in its identifier field, for example
the SYNTHETIC object
`{"status":"missing_information","missing_item":"SYNTHETIC-required-item"}`.
An ordinary question about the same absent property still uses `unestablished`.
Keep ordinary status and this designated status separate; do not mix their
vocabularies or invent an `active`/`unresolved` fallback for the designated query.

Previously supplied information that changed, was disputed, withdrawn, forgotten
or omitted from available context is ineligible. The required item is its own
declared proposition, with no version before the question. There is no free-form
clarification or model-uncertainty answer. Optional identifier projections must
name the same item as the `status` field.

## Field forms

Return one JSON object with exactly the declared fields, each once, without
commentary, fences, extra fields, nested objects or booleans. Copy strings
exactly, including case, spelling, punctuation and spacing. No descriptive
articles or added words are permitted.

| Field kind | Type and null/set rule |
| --- | --- |
| Ordinary status | Exact JSON string from the four ordinary labels; never null. |
| Designated missing status | Exact JSON string `missing_information`; never null. |
| Current/checkpoint scalar | Declared JSON integer or exact JSON string when uniquely active; JSON null if expired, unestablished or unresolved. New opted-in releases exclude active literal-null facts. Historical null-valued keys are untouched. |
| Current set | Complete unordered JSON array; singleton when active/settled, all distinct competing values when unresolved, `[]` when expired/unestablished. Each member has the declared integer or exact-string type. No duplicates, null members or superseded alternatives. No historical-set query. |
| Source | Exact public source-claim message ID for the unique active value, otherwise JSON null. When precedence selects an earlier claim, name that claim, not the later decision message. |
| Missing item | Exact declared required-item ID as a JSON string; null is forbidden. |
| Other ID | Exact requested public message/item ID as a JSON string, with an explicit field-specific null condition or explicit prohibition of null. Requires a separately admitted producer mapping. |

Integers are unquoted, without decimal notation or units. IDs are quoted JSON
strings with no `[id]` wrapper, whitespace padding or descriptions. Numeric-looking
IDs remain strings with their original spelling; do not regenerate historical IDs
for a newer naming convention. JSON null is distinct from `"null"`, `""`, a guess,
unknown and refusal; only each field's stated null condition permits it.

## Exact compressed H3 slots

The seven strings below are also stored in `etps_v02/h3_wording.json`. Expand
angle-bracket placeholders using **public** field names, scope, checkpoints,
declared types and declared IDs only, never expected answer values. Include the
general slot and each applicable field slot in every question and retry,
identically across arms. For missing status without an identifier projection,
omit the final identifier sentence. Its slot already covers requested item fields.

**general**

> Return one JSON object with exactly these fields, each once: <field names>. No fences, commentary, extra fields, nested objects, or booleans. Numeric fields: JSON integers, never quoted, decimal, or unit-bearing. Text/IDs: JSON strings. Copy text exactly, including case, spelling, punctuation, and spacing; add no articles or descriptions. Use JSON null only under each field's null rule, never "null", "", or guesses; null is not unknown/refusal. Arrays only for declared set fields.

**ordinary**

> For <status field> about <entity, property, scope> <current point or named checkpoint>, use only "active" (one value in force, including after explicit conflict settlement), "expired" (established value explicitly withdrawn/lapsed, no replacement), "unestablished" (never established by then), or "unresolved" (incompatible supplied claims still compete without explicit applicable settlement). Recency alone cannot settle conflict. Settled value: "active", never "resolved". Missing information/your uncertainty is not disagreement. Later events cannot change checkpoint answers.

**missing**

> For "status", use "missing_information" only when required item <declared item ID> was never supplied before this question, not for disagreement. Changed, disputed, withdrawn, forgotten, or context-omitted information previously supplied is ineligible. <identifier field, if requested>: exact declared item ID as a JSON string, no brackets/additions.

**scalar**

> <scalar current/checkpoint field>: one value in force <at the specified point>, as <JSON integer or exact JSON string>; JSON null if expired, unestablished, or unresolved (no unique value).

**set**

> <set field>: complete unordered JSON array of values in force now; singleton if active/settled, all distinct competing values if unresolved, [] if expired/unestablished. Members: <explicit member type and exact-text/number form>. No duplicates or superseded alternatives.

**source**

> <source field>: exact public source-claim message ID for the unique active value, as a JSON string, no brackets/descriptions. After precedence, identify the selected claim, not the later decision. JSON null without a unique active claim.

**other**

> <other ID field>: exact requested public <message/item> ID as a JSON string, no brackets/descriptions. <State this field's null condition explicitly, or state that null is not permitted.>

## Declaration schema

Place `question-contract.json` beside mapper `bundle.json`. Objects are closed;
duplicate JSON keys, non-JSON constants, unknown versions and extra members are
rejected. Required root members are exactly:

| Member | Value |
| --- | --- |
| `schema` | `etps-question-contract-v1` |
| `question_contract_version` | `h3-compressed-v1`, or `legacy-v1` |
| `release_id` | Nonempty public release identifier for the new release. |
| `bundle_sha256` | SHA-256 of the exact mapper `bundle.json` bytes. |
| `tasks` | Object keyed by every mapper task ID. Each value contains only `questions`, an object keyed by every probe ID, including retries. |

Each question has exactly `core` (nonempty public question text) and `fields`
(nonempty object keyed by its exact public answer fields). Each field descriptor
contains exactly `kind` and the additional members in this table:

| `kind` | Additional members |
| --- | --- |
| `status` | `scope`, `point` |
| `missing_status` | `item_id`; only field name `status`, separate from ordinary status |
| `scalar` | `value_type`, `point` |
| `set` | `value_type` |
| `source` | None |
| `item` | `item_id`; requires a matching `missing_status` designation |
| `other` | `id_kind`, `null_rule` |

All descriptor members are nonempty public strings without unexpanded angle
brackets. `value_type` is exactly `integer` or `string`. A historical scalar's
`point` is exactly `just after public message <exact checkpoint ID>`, with the
placeholder replaced. Current points and ordinary-status scope are author-supplied
public descriptions; checking does not interpret their prose. An explicit legacy
declaration has the same root schema and binding, `question_contract_version`
equal to `legacy-v1`, and `tasks: {}`.

SYNTHETIC question descriptor example (not a complete release declaration):

```json
{
  "core": "[SYNTHETIC-q001] What is the workshop tray count now?",
  "fields": {
    "count": {"kind": "scalar", "value_type": "integer", "point": "now"},
    "status": {"kind": "status", "scope": "workshop, tray count, main room", "point": "now"},
    "source": {"kind": "source"}
  }
}
```

The native mapper supports current/checkpoint scalars, ordinary status, current
sets, provenance and designated missing-item projections. `other` is renderable
but has no native producer mapping and fails native descriptor conformance.
The public renderer cannot verify that descriptor prose is truthful or that
`core` is free of answer hints; authoring review remains required.

`etps_v02.question_contract` validates declarations and renders public descriptors.
It is not automatically invoked by mapper, runner or replay. Its explicit `apply`
helper operates on a caller-supplied manifest copy, validates task/question/field
coverage and projection kinds, and changes only question-user text/hash. A future
execution derivation must render once before selecting an arm, preserve expected
objects and obligations, record the declaration and prompt hashes, and bind the
declaration into the new receipt/seal inventory. This tooling does not create a
freeze or authorize an execution.

## Content-free conformance checker

Run from the repository root, with no dependencies or model endpoint:

```powershell
python -B -m etps_v02.conformance path/to/release/bundle.json
```

Exit 0 means no detected violation under the opted-in contract. Exit 2 means
violations or malformed input, including absent/legacy declarations: the checker
does not certify legacy releases, and refusal does not invalidate their original
contracts. Stdout is one JSON object with `schema: "etps-conformance-v1"`,
`tasks_checked`, `fields_checked`, `violation_count` and `violations`. Each row has
only `task_id`, `field_name`, `rule_id` and `count`. Empty identity strings denote
input/task-wide issues. Counts include both the manifest expected object and the
separate key object; repeated violations aggregate. Field counts are descriptor
visits, including missing fields, rather than unique logical fields.

Output never emits answer values, question/probe IDs, conversation text, expected
objects, paths, hashes, arguments or exception messages. Stderr is empty for
ordinary success, violation and malformed-input invocations. Task IDs and field
names are the only input-derived output identifiers.

| Rule ID | Check |
| --- | --- |
| `R1-INPUT` | Unreadable, unsafe, malformed or unbound input/declaration. |
| `R1-CONTRACT` | No opted-in declaration. |
| `R1-BUNDLE` | Unsupported mapper bundle version. |
| `R1-DESCRIPTOR` | Task/question/retry/field coverage, descriptor projection or checkpoint mismatch. |
| `R1-LABEL` / `R1-STATE-LABEL` | Exact ordinary label map / admitted state-version labels. |
| `R1-ACTIVE-NULL` | Prohibited active literal-null fact. |
| `R1-STATUS` / `R1-STATUS-PROJECTION` | Status type/vocabulary / ordinary state projection. |
| `R1-MISSING-DESIGNATION` | Required missing item was previously established. |
| `R1-TYPE` / `R1-TYPED-NULL` | Exact field/member type / null eligibility or null surrogate. |
| `R1-SET-DECLARATION` / `R1-SET-FORM` | Declared set fields / JSON array form. |
| `R1-SET-DUPLICATE` / `R1-SET-PROJECTION` | Duplicate members / complete in-force set. |
| `R1-BARE-ID` / `R1-ID-PROJECTION` | Bare ID form / source or item projection. |
| `R1-KEY-FIELDS` / `R1-KEY-BINDING` | Expected field/probe coverage / separate key equals manifest expected object. |
| `R1-STRUCTURE` | Malformed task artifacts or graph. |

Only the named bundle, declaration, manifests, sidecars and key files are read.
Artifact references must be single filenames within the bundle directory;
symlinks/junctions and non-regular files are refused. Files are bounded to 16 MiB,
with 8 MiB for the declaration. The checker neither scans other directories nor
writes input files.

It checks format and declared projections, not corpus semantics or truthful
absence, and does not independently validate arbitrary scalar answers. Key
equality is an additional binding check, not a proof of correctness. It does not
replace authoring admission, state-record intake, mapping, lint, human cross-check,
budget checks, corpus freeze or independent attestation. Verification uses
SYNTHETIC fixtures only; it establishes no model or benchmark result.
