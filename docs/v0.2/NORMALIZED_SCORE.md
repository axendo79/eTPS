# Normalized diagnostic score

`normalized-score-v1` is a pure, deterministic diagnostic beside the strict
score. It has no model judge or fuzzy matching and never changes strict scoring,
acceptance, failure branches, retention, RR, TPS, persistence or replay.
Declare its version and field metadata before any run; retain both numbers.
Existing evidence is not retroactively rescored as a new experimental result.

```python
from etps_v02.normalized_score import normalized_score

# SYNTHETIC software example, not a model result.
normalized_score({"source": "[m2]", "quantity": "7 kg"},
                 {"source": "M2", "quantity": 7}, id_fields=("source",))
# strict=0, normalized=1; diagnostic=True
```

The API takes decoded answer/expected objects and optional explicit `id_fields`
and `set_fields` from frozen field metadata. It returns object-level 0/1
`strict` and `normalized` scores together, the version, diagnostic marker and
the sorted declared fields. This is a paired answer report, not trial acceptance
or a new runner policy. Authoring sets retain the existing complete unordered
typed-set comparison in the strict column; scalar strict equality uses the
existing type-strict predicate. Malformed answers score 0 in both columns.
Invalid expected objects or field declarations raise `ValueError`.

Only these transformations apply to values; keys remain exact:

- Casefold strings and fold whitespace by trimming and joining whitespace runs
  with one space. Word separation remains meaningful.
- For explicitly declared ID fields, remove balanced surrounding square brackets
  and straight single/double quotes, including nested pairs, before folding.
  JSON string delimiters were already removed by decoding; this handles wrappers
  inside the string value. It does not extract an ID from surrounding prose.
- For integer expected values, read a full numeric string with a trailing unit
  as a number. The implemented core spelling is a signed ASCII decimal, optional
  fraction/exponent, optional intervening whitespace, and one alphabetic unit
  token (every character must satisfy Python's `str.isalpha()`). All number,
  fraction and exponent digits must be ASCII `0`–`9`. Superscripts, fractions
  and other Unicode numerics are neither number digits nor alphabetic units:
  `7²`, `٣` and `7½` do not normalize to integers. Decimal comparison is exact:
  `7.0 kg` matches 7, `7.1 kg` does not.
  There is no unit conversion or numerical tolerance. A unitless string stays
  a string; d10-v1 is a different existing acceptance policy.

The same value transformations apply to explicitly designated set members.
Complete membership, typed identity and duplicate rejection remain required;
no sorting/deduplication repairs an answer. Expected sets whose distinct members
collapse under folding are ambiguous for diagnostics; exact matches still score 1.
Other mismatches in such sets score 0 pending the decision below.

No key folding/aliasing, punctuation removal, accent/Unicode normalization,
spelling repair, substring extraction, string-to-null/boolean conversion,
unit conversion, rounding, Markdown/prose extraction or fuzzy matching applies.
`M2` is not `bin M2`. The strict scorer, runner and replay do not import this
module. A reporting caller must keep the paired diagnostic separate from its
existing strict outcome and declare the diagnostic configuration prospectively.

## STUCK-DECISION

Section B does not define ID discovery, exact whitespace/wrapper/unit grammar,
or runner/report schema integration. The implementation exposes an explicit
ID/set declaration and a tested conservative core rather than guessing from
answers. No experimental configuration or additional tolerance is selected here.

| Unsettled scope | Options | Recommendation |
|---|---|---|
| ID identity | Frozen field metadata; infer from key names; infer from string shape. | Use frozen field metadata; never classify a value as an ID by guessing. |
| Whitespace | Collapse runs and trim; delete all whitespace. | Freeze the implemented collapse rule; do not equate joined and separated words. |
| Additional wrappers | Square brackets and straight quotes; all bracket types, typographic quotes or backticks. | Keep the tested core; require an explicit new version for broader wrappers. |
| Unit grammar | One alphabetic token; compound/Unicode-symbol units; unitless numeric strings too. | Keep the core until an explicit grammar is adopted; never perform unit conversion. |
| Fold-colliding expected set members | Diagnostic unavailable; compare multiplicities; refuse corpus at review. | Human review should flag the ambiguity; do not add an authoring refusal. |
| Runner integration and denominators | Explicit paired answer reports; versioned persisted per-field/trial summaries. | Keep the pure paired report now; specify availability, malformed/timeout handling and a schema before runner integration. |

These are pending decisions, not permission to silently broaden rules. See the
[implementation handoff](brief-v2-run.md) for evidence and remaining authoring
decisions. All fixtures are SYNTHETIC; no model run or corpus result is claimed.
