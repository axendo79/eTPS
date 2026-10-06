# authoring-v1 admission

Codex-authored tooling under local user authorization. No corpus content.
The isolated author receives only [AUTHORING_BRIEF.md](AUTHORING_BRIEF.md),
which includes every format field. The [JSON Schema](authoring-v1.schema.json)
describes structural shape; `etps_v02.intake.authoring` additionally checks
references, immutable field maps, typed sets, routes, public IDs and byte spans.
No external package, schema download or network operation is needed.

```text
python -B -m etps_v02.intake.authoring SOURCE.json
```

API: `validate_authoring(exact_utf8_bytes)` returns the validated document
without rewriting source bytes. CLI returns a SHA-256 receipt and
`semantics_verified: false`; exits 0 on admission or 2 on reason-coded refusal.
All structural objects are closed, with all fields required. Strict JSON rejects
duplicate keys, nonfinite numbers, invalid UTF-8 and nonportable surrogate strings.
Values are typed scalars or explicitly designated complete sets, without fuzzy
matching. IDs beginning with `$` or containing `:` are reserved for derived nodes.
Messages and questions must start with their exact public `[id] ` prefix.

Version arrays preserve author order; previous/next links and contiguous numbers
are a mechanical derivation. Requirement boundaries, authority, applicability,
answer keys, branches and predictions are supplied by the author, never inferred
from prose. Field maps remain identical subsets of one task map. Omitted logical
fields remain unavailable. The format can record delayed starts, multiple failure
links, desired answer alternatives and clarification-only questions, so the
mapper can refuse them explicitly rather than discarding an author decision.

Refusal codes: `invalid_json`, `safety_limit`, `required_fields`, `closed_fields`,
`field_type`, `format_version`, `brief_version`, `duplicate_id`, `coverage_tag`,
`reference`, `position`, `field_map`, `answer_shape`, `unknown_overlap`, `route`,
`span`, `prediction`, `public_identifier`, `history_order`. File-read failures
use `file_unavailable` from the bounded intake reader. The first failure includes
a source path and detail. All refusal groups have trivial SYNTHETIC fixtures.

Admission ceilings (software limits, not experiment budgets): 8 MiB source,
256 tasks, 4,096 members per array, and the existing strict JSON depth limit.
The [mapper](AUTHORING_MAPPER.md) applies the narrower executable/sidecar bounds
and validates the resulting sidecar. Admission is neither semantic review nor
authorization to execute a corpus. Review before [freeze](CORPUS_FREEZE.md) is
mandatory; follow the [runbook](AUTHORING_RUNBOOK.md).
