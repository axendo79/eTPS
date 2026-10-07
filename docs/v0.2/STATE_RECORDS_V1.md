# state-records-v1: bounded sidecar intake

User-authorized implementation of the [maintainer rulings](STATE_RECORD_OPTIONS.md#maintainer-rulings-2026-10-06).
Codex authored the format, validator and synthetic fixtures. The sidecar is
authoritative corpus metadata, not executable scorer logic. This explicit
intake/freeze tool is never called by scoring or replay and changes no score.

**Limitation:** neither scorer nor validator proves sidecar semantics, source
truth or authority. Before freezing a corpus version, review cross-checks the
sidecar against executable obligations and answer keys. Any mismatch is a
corpus/protocol defect that blocks the release from being run as valid evidence.
An intake pass reports `semantics_verified: false`, not review signoff. The
freeze/release process must require both intake and semantic review; the scorer
does not load the sidecar or enforce those procedural release gates.

## Binding and explicit invocation

The manifest opts in through otherwise uninterpreted metadata:

```json
{"metadata":{"state_records":{"version":"state-records-v1","sha256":"<64 lowercase hex characters>"}}}
```

The angle-bracket text is a placeholder. Compute SHA-256 over exact sidecar
bytes, including whitespace and line endings. Freeze those bytes and the
manifest together. The binding object has exactly `version` and `sha256`;
other metadata remains governed by existing rules. Neither artifact is rewritten.

```text
python -B -m etps_v02.intake.state_records --manifest manifest.json --sidecar state-records.json
```

API: `validate_state_records(manifest, sidecar_bytes)` in
`etps_v02/intake/state_records.py`. Success returns a JSON-compatible result;
failure raises `IntakeError` with `code`, `path` and `detail`. CLI output is one
JSON result, with exit 0 on success/opt-out and exit 2 on rejection. Without a
binding, the result is `not_opted_in`: no sidecar is opened or additional
manifest admission rule applied. A binding without sidecar bytes fails.
The existing manifest authoring validator is called only from this intake tool
before interpreting its graph, never the other way around.

## Closed JSON format

Every listed key is required, including nulls and empty arrays. Every structural
object is closed. Strict UTF-8 JSON rejects duplicate keys, nonfinite constants
and invalid encoding. Values are typed-v1 scalars: string, integer or null;
bool, float and nested containers are rejected. Record and version IDs share a
globally unique namespace within the sidecar.

| Object | Exact keys and types |
|---|---|
| Root | `version`: state-records-v1; `records`: record array; `fields`: logical field name to query object; `probes`: probe node ID to field-name array |
| Record | `id`, `entity`, `property`, `scope`: nonempty strings; `status_values`: label object; `versions`: ordered version array |
| Status labels | `active`, `expired`, `unresolved`, `unestablished`: nonempty answer strings chosen and frozen by the author |
| Version | `id`: string; `number`: positive integer; `previous`, `next`: version IDs or null; `event`: establishing user-node ID; `transition`: establish/change/lapse/reinstate/precedence; `status`: active/expired/unresolved; `value`: typed scalar; `claims`: claim array; `valid_time`: interval object; `applicability`: nonempty string; `obligations`: binding array |
| Claim | `source`: user-node ID; `authority`: nonempty authority description; `value`: typed scalar |
| Valid-time interval | `begin`, `end`: nonempty world-validity labels or null |
| Obligation binding | `id`: executable obligation ID; `kind`: current/historical; `begin_after`, `end_before`: event boundaries, with $trial_end allowed for end |
| Query | `record`: stable record ID; `kind`: current/at-checkpoint/status/values/provenance; `checkpoint`: node ID for at-checkpoint, otherwise null |

All identifiers are nonempty strings. World-validity labels and applicability
descriptions are stored without interpretation: no date inference, scope
evaluation or free-form predicate evaluation. Event order remains separate from
valid time. This corpus still excludes questions needing external calendar dates.
Separate records identify distinct entity/property/scope combinations, allowing
scoped or partial changes without rewriting unrelated properties.

This complete synthetic sidecar illustrates one establishment. It is a format
example, not a corpus task or frozen answer key:

```json
{
  "version": "state-records-v1",
  "records": [{
    "id": "r", "entity": "synthetic entity", "property": "code", "scope": "north",
    "status_values": {
      "active": "active", "expired": "expired",
      "unresolved": "unresolved", "unestablished": "unestablished"
    },
    "versions": [{
      "id": "r1", "number": 1, "previous": null, "next": null,
      "event": "establish", "transition": "establish", "status": "active", "value": "A",
      "claims": [{"source": "establish", "authority": "synthetic source", "value": "A"}],
      "valid_time": {"begin": "first task-world checkpoint", "end": null},
      "applicability": "north site code",
      "obligations": [{
        "id": "current-r1", "kind": "current",
        "begin_after": "establish", "end_before": "$trial_end"
      }]
    }]
  }],
  "fields": {
    "answer": {"record": "r", "kind": "current", "checkpoint": null},
    "status": {"record": "r", "kind": "status", "checkpoint": null},
    "values": {"record": "r", "kind": "values", "checkpoint": null},
    "source": {"record": "r", "kind": "provenance", "checkpoint": null},
    "old": {"record": "r", "kind": "at-checkpoint", "checkpoint": "establish"}
  },
  "probes": {"probe": ["answer", "status", "values", "source", "old"]}
}
```

The executable obligation has source/begin_after `establish` and end_before
`$trial_end`. The probe expects answer `A`, status `active`, values `["A"]`,
source `establish` and old `A`; values requires a set-v1 designation. Actual
source content and authority still require independent semantic review.

## Version, event and obligation checks

Version numbers run contiguously from 1. Ordered neighbors must match reciprocal
previous/next IDs, null at each end. Links cannot jump records, omit versions or
cycle. Repeated values such as A-B-A keep distinct versions and establishing events.

Version events and claim sources reference reachable delivered user nodes.
Sources precede or equal establishment; versions strictly follow predecessors.
Earlier events must dominate dependent later events: every path from task start
to the later event includes the earlier event. Outcome and field-routing edges
both participate. At a probe/checkpoint, an ancestral version present on only
some incoming paths makes state branch-dependent and rejects. The tool never
chooses a convenient branch or enumerates every possible trace.

The first version establishes active or unresolved state. A change updates active
state or continues unresolved state. A lapse changes active to expired, with null
current value and no current claims. Reinstatement follows expired state, creates
a new active version and needs a fresh current obligation; it cannot reuse any
older obligation ID. Unresolved versions have at least two claims from distinct
source nodes and a null single-value projection. They stay unresolved across
updates until a precedence version selects a previously recorded claim. A claim
is identified by its source node and typed value; its authority text is
descriptive and need not match (maintainer ruling 2026-10-07). Precedence is
admitted only from unresolved to active state; anything else is refused as
`precedence_claim`. The precedence event records resolution, but its
authority is not proven by the validator.

Each obligation reference resolves exactly once across versions. Its executable
source and begin_after equal the version's establishing event; its end equals
the recorded end_before. Current obligations end at the next version event
(change, lapse, reinstatement or precedence), or trial end for the last version.
Historical obligations have independent explicit ends; trial end keeps them
after current-state changes. Nonterminal ends follow establishment on consistent
branches. Positional legacy intervals and delayed starts are outside this format.
Unreferenced executable obligations are not inferred into records: review must
check that the full required state has been represented.

## Frozen fields and answer correspondence

`fields` is the single frozen logical field map. No probe changes a field's
record, query kind or checkpoint. `probes` covers exactly all executable probes;
its names equal each probe's expected keys and belong to the logical map.
Omitted logical fields appear in the intake result's `unavailable_fields`, never
remapped. This intake output does not modify existing dimension reports.
Unsuppliable-field diagnostic integration and per-arm within-plan aggregation
are separate implementation work; R records those rulings only.

At a probe, select the latest established version common to all incoming paths.
An at-checkpoint query selects state **after** the frozen checkpoint, which must
precede the probe. Before any establishment, state is unestablished.

| Query | Exact projection |
|---|---|
| current | Active scalar value; null for expired, unresolved or unestablished state |
| at-checkpoint | Active scalar value at the checkpoint; null otherwise |
| status | The record's frozen answer label for the selected status |
| values | One active value, distinct typed unresolved claim values, or an empty array for expired/unestablished state |
| provenance | Unique active claim's source-node ID; null without a unique active current value |

Set-v1 designated fields use complete-set equality with exact typed elements and
no duplicates. Other fields use exact type/value equality. No d10 tolerance
repairs a frozen answer key or sidecar value; response tolerance remains the
scorer's independent declared behavior. A mismatched key is a protocol defect.

## Failure codes and bounds

The first deterministic failure has a reason code and location; no rejection
becomes a score or successful intake.

| Check | Rejection codes |
|---|---|
| (a) Binding/version/hash | binding_version, binding_hash, sidecar_missing, hash_mismatch |
| (b) JSON, IDs, required/closed/typed fields | invalid_json, sidecar_version, duplicate_id, closed_fields, required_fields, field_type |
| (c) Version chain | chain_link_unresolved, version_chain |
| (d) Events, order and branches | event_reference, event_order, branch_inconsistent, state_transition |
| (e) Obligations and boundaries | obligation_reference, obligation_reused, obligation_boundary |
| (f) Fresh reinstatement | reinstatement_not_fresh |
| (g) Disagreement and precedence | disagreement_claims, state_claims, unresolved_without_precedence, precedence_claim |
| (h) Fields, probes and keys | answer_reference, probe_reference, probe_fields, answer_mismatch |
| Tool admission | safety_limit, manifest_invalid, file_unavailable |

Software ceilings: 4 MiB sidecar bytes, 8 MiB manifest file bytes, 4,096 nodes,
128 records, 1,024 total versions, 256 logical fields and 16,384 supplied
probe-field pairs. Strict JSON uses the existing nesting safeguard. These are
tool limits, not experiment budgets or selected corpus sizes. DAG ancestry and
dominance use bounded bitsets rather than exponential path enumeration.

## Evidence and freeze obligations

Synthetic tests cover the requested chains, lapse/reinstatement, disagreement
and precedence, scoped changes, each failure group (a)-(h), checkpoint/source
branch consistency, types, software bounds, unavailable fields and CLI failure
codes. Exact score/report byte comparisons cover binding and opt-out. The intake
tool is a separate subpackage and changes no production scorer/runner file or
their existing implementation identity.

Preserve sidecar bytes beside frozen corpus artifacts. Generic runner/export
does not automatically retain or admit a sidecar merely because metadata binds
its hash. The frozen release must preserve sidecar and review evidence separately.
Mechanical success and a hash do not establish semantic correctness, independent
authorship, source truth, authority or lack of prior exposure. Review mismatches
block release. Corrections after freeze require a new corpus version; no silent
old-run repair is authorized.

## Authoring pipeline cross-reference (2026-10-06)

The [neutral format](AUTHORING_FORMAT_V1.md) and [mapper](AUTHORING_MAPPER.md)
now derive hash-bound sidecars and explicitly call this intake validator.
The separate [within-plan aggregator](CORPUS_AGGREGATION.md) implements the
frozen logical-map/one-plan-per-repeat rulings, including omitted fields.
[Corpus freeze](CORPUS_FREEZE.md) reasserts intake and requires exact-artifact
declared review; [the runbook](AUTHORING_RUNBOOK.md) requires a human cross-check.
Scoring/replay still never calls this validator or proves semantics.
The complete [pipeline index](README.md) includes the only author-facing brief.

## state-records-v1.1: exact missing-information answerability

This separate opt-in version implements the maintainer's 2026-10-06 authoring
ruling 4, attributed with rulings 1–3 in [PROVENANCE](PROVENANCE.md#maintainer-authoring-rulings-2026-10-06).
It adds only the query kind `missing_information`. All record, version, source,
transition, interval, obligation, probe and ordinary-query shapes and checks
remain v1. There is no new state status or general clarification semantics.
Existing `state-records-v1` bindings, validator behavior and fixtures are unchanged.

Both the root `version` and manifest binding version are `state-records-v1.1`;
the binding still has exactly `version` and `sha256`, hashing the original bytes.
The new query has exactly `record`, `kind`, `missing_item`, and `projection`.
`record` identifies the proposition needing information; `missing_item` identifies
a separately declared required item record, such as a proposition's unit component.
Both identifiers must resolve. Missing information is never inferred from an
undeclared or misspelled ID. The relationship and need for the item are authored
metadata requiring human review, not inferred from prose.

The following field-map fragment is explicitly **SYNTHETIC**, only a format example:

```json
{
  "status": {
    "record": "SYNTHETIC-quantity",
    "kind": "missing_information",
    "missing_item": "SYNTHETIC-unit",
    "projection": "status"
  },
  "missing_item": {
    "record": "SYNTHETIC-quantity",
    "kind": "missing_information",
    "missing_item": "SYNTHETIC-unit",
    "projection": "identifier"
  }
}
```

Every probe using a new query requires the literal answer field `status`, with
this query's `status` projection and expected value exactly `missing_information`.
Optional identifier fields use `projection = identifier` and expect exactly the
declared missing-item ID. All new fields in that answer refer to the same
record/item pair. Identifier-only answers, alternate status labels, vague requests
and open-ended or "any reasonable" clarification are refused. Ordinary fields
can coexist and still pass their original v1 state projections; the full typed-v1
manifest is admitted before any projection check.

At the probe's graph position, the missing item's version history must have no
established version on any incoming path. An empty history is sufficient; a first
establishment strictly later than the probe is also permitted. Prior active,
expired, reinstated or unresolved information is not insufficient information:
`missing_item_established` refuses it. An establishment on only some paths refuses
with `branch_inconsistent`. Exact answer-form mismatches refuse with
`missing_information_answer`; reference/shape/binding errors retain the v1 codes.
This distinguishes insufficient information from forgetting and nothing more.

Use the explicit dispatcher API in `etps_v02/intake/state_records_v11.py`, or:

```text
python -B -m etps_v02.intake.state_records_v11 --manifest manifest.json --sidecar state-records.json
```

The dispatcher delegates v1 bindings and opt-out unchanged to the old validator;
unsupported bindings still refuse. The original v1 CLI/API remain available and
intentionally refuse a v1.1 binding. Scoring, runner and replay do not call either
intake module. A v1.1 pass adds `missing_information` to its receipt's checks and
still returns `semantics_verified: false`. Review must cross-check public source,
the missing item's full earlier history, exact identifiers and answer keys before
freeze; a mismatch remains a defect blocking release.
