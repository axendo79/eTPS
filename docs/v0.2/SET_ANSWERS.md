# Complete-set answers and field diagnostics: set-v1

User-authorized local implementation, 2026-10-06, for
[state-evolution ruling 3](STATE_EVOLUTION_CORPUS_SPEC.md#8-user-rulings-2026-10-06).
Codex authored the implementation and synthetic tests. This is scorer behavior,
not corpus authoring, a model experiment, or independent semantic validation.

## Opt-in and answer language

A task manifest declares both `"answer_schema": "typed-v1"` and
`"answer_predicate": "set-v1"`. Each probe may declare `set_fields`, a list of
unique canonical expected field names; omission means no set fields. The
validator rejects unknown fields, unsupported versions, a non-array expected
set, or duplicate expected elements. A designation without the opt-in is not
admitted for new authoring. Existing manifests are not upgraded.

The following is a synthetic answer-rule fragment, not a corpus task or a
complete runnable manifest:

```json
{
  "answer_schema": "typed-v1",
  "answer_predicate": "set-v1",
  "nodes": {
    "probe": {
      "kind": "probe",
      "expected": {"status": "unresolved", "values": ["alpha", "beta"]},
      "set_fields": ["values"],
      "field_dimensions": {"status": "ambiguity", "values": "ambiguity"},
      "unknown_answers": []
    }
  }
}
```

A designated field must be a JSON array whose elements are typed-v1 scalars:
strings, integers or null. Each element compares by its exact type and value.
Booleans, floats, objects and nested arrays are outside this language. An array
with duplicate elements is incorrect. The answer must contain the entire
expected set, with no missing or extra elements; order is ignored. The empty
set is allowed. Integer `7`, string `"7"` and null are distinct elements.

Transport timeout has precedence. Invalid JSON, a non-array designated field
or an element outside typed-v1 is malformed. A missing field, extra claim or
wrong schema-valid value is incorrect. Explicit unknown/refusal objects remain
exact declarations; correct set matches have precedence, and an unknown
declaration overlapping the correct set in another order is rejected.

Scalar fields retain typed-v1 equality and optional d10-v1 behavior. Declared
d10 key aliases can name a set field; they never normalize its elements.
Digit-string conversion and fixed-string tolerance apply only to scalars.
Set reordering counts as an exact answer, not a format deviation. The existing
d10 mode/rule reporting and unknown/collision priority are retained. An
ambiguity status is exact unless scalar tolerance is explicitly declared for
that field; the ambiguity fixtures declare none.

`field-v1` routing compares designated fields with complete-set equality and
scalars with their existing rules. Status and values can have independent
field-obligation links and recovery routes. A missing or extra answer key still
takes the ordinary outcome branch. Duplicate elements fail the whole set field,
never individual element units. Recovery byte accounting is unchanged.

## Diagnostic dimensions

Within set-v1, a probe may declare `field_dimensions`: one tag for every expected
field, chosen from `current`, `historical`, `expired`, `ambiguity`, `provenance`
and `control`. Unknown fields, missing tags or unsupported tag values are
rejected. Tags are optional for general set-v1 use; the accepted state-evolution
spec requires them when its corpus is authored.

For a stable tagged field plan across the manifest's probes, the score adds
`dimension_accuracy` with `first_attempt` and `terminal` entries for all six
dimensions. Each entry contains `correct`, `planned`, exact `accuracy`,
`reason_counts` and `unavailable_reasons`. A set is one field unit. An unused
dimension has planned zero and accuracy null. Fractions serialize as
`{"numerator": ..., "denominator": ...}` using the existing export convention.
`first_fields` and `terminal_fields` retain individual field outcomes.

The first observation is the first scored answer probe; the terminal observation
is the last scored answer on a completed terminal path, after any authorized
recovery. These phases are separate. Fields use the declared scalar/set rules
even when another field fails. A schema-valid missing field is incorrect;
an extra claim can fail acceptance while every planned field is correct.
An explicit unknown response gives unknown field reasons. A malformed answer
gives malformed reasons for all fields, and a timeout gives unavailable reasons
with a timeout count. A d10 alias collision cannot yield an unambiguous normalized
object and gives incorrect field reasons.

Unobserved first fields are unattempted. Terminal fields in truncated, aborted
or running slots are unavailable; wholly unattempted slots retain unattempted
counts in both phases. Invalid evidence gives unavailable diagnostic credit.
Known first observations from an otherwise unfinished trace remain visible.
Every planned tagged field stays in the denominator; no missing observation is
silently discarded. Accuracy is a diagnostic count ratio, never an efficiency
multiplier or a replacement for binary acceptance or obligation retention.

The report adds a `dimension_accuracy` list with one row per tagged planned
slot, including slot, task, arm and state. It includes unattempted and aborted
slots, and does not pool repeats. The plan currently has no explicit repeat
identity; corpus-wide per-arm/per-repeat aggregation needs a frozen mapping
before implementation. Slot-level diagnostics are available now.

**STUCK for heterogeneous probe plans:** the contract and accepted spec do not
identify which differently named/shaped probe fields are retries of a single
planned unit versus independent units. If probe tag maps differ, or some probes
are untagged, the diagnostic reports `heterogeneous_field_plan`, with phase
values null. Validation, classification and acceptance still proceed. This
avoids selecting a field-identity rule before corpus authoring settles it.

## Replay and compatibility

Offline, live and manual projection use the immutable manifest's designations.
Strict JSON, raw response bytes and journal layouts are preserved. Export replay
verifies raw projection and recomputes diagnostics; it does not trust the saved
report. The live check uses a mocked adapter, and manual checks use scripted
synthetic input; neither is a model or human-service run.

Manifests without set-v1 retain their scalar projection, classifications,
score fields and report layout. Original tests and fixtures remain unchanged.
As before, replay under changed source identifies implementation differences;
source hashes and those warnings cannot stay identical across an implementation
change. Arithmetic and classifications of old synthetic evidence remain exact.
No existing export or manifest is rewritten or upgraded.

State-record representation remains an independent unresolved decision; see
[the unselected options](STATE_RECORD_OPTIONS.md). Set-v1 does not implement
state truth, source precedence, valid time or applicability.
