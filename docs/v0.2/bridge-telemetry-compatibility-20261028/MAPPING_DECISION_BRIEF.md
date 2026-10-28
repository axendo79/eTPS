# Decision brief: bridge telemetry compatibility

**Recommend option 1: a producer compatibility mode using the accepted flat
telemetry contract.** This changes the bridge response projection while keeping
eTPS's current validation and replay semantics. Neither option is approved or
implemented. This decision is separate from PR35 and Gate 3 qualification.

The [six-case proof](proof-results.json) shows composite bridge telemetry is
retained in raw HTTP evidence but rejected by the current flat projector.
Projected sums have zero coverage; incomplete combined totals correctly remain
null. The [authority checklist](CONTRACT_AUTHORITY_CHECKLIST.md) distinguishes
accepted rules from PR35's unaccepted draft. eTPS review base:
`ed1dd7c3de2f315f9a38e55406c22b548b22359c`.

| Decision | Option 1 — producer flat projection (recommended) | Option 2 — versioned consumer mapping |
| --- | --- | --- |
| Exact mapping | In an explicit bridge compatibility mode, `x_nyx_bridge` contains only the existing scalar strings, finite numbers and nulls. Preserve the original composite diagnostics separately; do not coerce booleans or derive costs from nested receipts. | Introduce an explicitly selected projector version that validates the composite bridge schema, then copies the named per-request scalar metrics into a flat diagnostic view. Nested receipts remain evidence and never supply inferred counters. |
| Change scope | Bridge success/error serialization, preservation of composite diagnostics, declared mode/provenance, and focused regressions. eTPS's existing `memory_telemetry_field` still selects `x_nyx_bridge`; no eTPS schema or scorer change. | eTPS plan admission for projector selection, projection and replay dispatch, recorded version/provenance, documentation and focused regressions. Bridge response shape can stay unchanged. No scorer change. |
| Compatibility | Keep current bridge default behavior until migration is explicitly selected; existing consumers may depend on nested `x_nyx_bridge`. Preserve the complete composite in a separately reserved response field or durable diagnostic record; select and document that location/collision rule before implementation. Historical eTPS journals stay under their recorded revision. | Preserve the old flat projector unchanged for old plans/journals. New plans opt into the new mapping; never reinterpret old invalid projections silently. A new recorded implementation/version must make replay selection deterministic. |
| Main tradeoff | Smaller accepted-contract change, with producer-mode deployment and downstream compatibility to review. | Wider consumer/schema/replay change; supports the current composite producer directly but requires new accepted mapping semantics. |

Both options must preserve the existing metric meanings: `extraction_calls`,
`extraction_prompt_tokens`, `extraction_completion_tokens`,
`extraction_seconds`, `beliefs_injected`, `injected_chars`, and `facts_rejected`.
They describe the dispatched request. Never sum an `ingestions` array on top of
already aggregated counters. Additional diagnostic identity/status fields must
not become numeric costs merely because they can be represented as numbers.
Preserve the accepted finite-number behavior, including finite negative
diagnostic values; PR35's proposed nonnegative hardware rule does not apply.

The required failed-502/cached-200 check is the same for both options:

1. The failed reply after successful extraction retains its original request
   and response evidence, `extraction_calls=1`, and the known extraction usage
   (the synthetic proof uses 8 prompt and 4 completion tokens).
2. A later cached-ingestion request is a separate request/event with zero
   **new** extraction. The pair reports extraction calls `[1, 0]` and total
   known extraction usage 8/4, with two request observations. It never overwrites
   the earlier error or first-attempt failure. This check authorizes no automatic
   retry; the workload's approved routing still controls subsequent dispatch.
3. An extraction transport failure with unavailable usage retains null usage,
   its failure evidence and denominator entry. Null is never converted to zero.
   Missing, invalid and unavailable telemetry remain distinguishable.
4. An explicitly reported cached zero counts toward coverage; a cache flag alone
   never licenses an inferred zero. Unknown usage does not count. Full
   answer-plus-extraction totals remain null unless **all** token components
   have complete nonempty coverage, including failed and pending requests.
   Keep the arm's `memory_telemetry_field` enabled; removing it to turn missing
   extraction costs into `not_applicable` is not a compatibility repair.

Before implementation, select the option and its compatibility/version boundary;
for option 1, also select the composite-diagnostic location. Then add paired
failure/retry and old-journal replay regressions. No request budgets, workload
routes, acceptance, TPS/RR definitions, first-attempt retention, or qualification
permissions change. Author/system affiliation remains disclosed and Nyx
failures receive the same accounting as other arms.
