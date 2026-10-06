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
updates until a precedence version selects a previously recorded
source/authority/value claim. The precedence event records resolution, but its
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
