# eTPS composite telemetry: contract and decision checklist

Read-only review of the eTPS source/document revision, HEAD
`ed1dd7c3de2f315f9a38e55406c22b548b22359c`. No schema/source implementation,
model/GPU/native operation, private corpus, raw model log or journal was used.
The packet includes the six-case synthetic projection proof and
[MAPPING_DECISION_BRIEF.md](MAPPING_DECISION_BRIEF.md); this document supplies
the authority boundary. The review and proof were prepared by separate agents.

## Authority distinction

The current AGENTS rules and explicit endorsements in
`docs/v0.2/PROVENANCE.md:394–403` establish neutral input-side RR, binary terminal
acceptance, separate first-attempt retention, linked recovery, failed/unavailable
attempt disclosure, and primary TPS/RR with experimental eTPS. Memory cost is
reported separately; Nyx receives no scoring preference.

The measurement contract itself remains draft 4. Its lines 3–5 distinguish user
endorsements from model-authored operational details. In particular, the
zero-RR-unavailable complete-workload threshold at line 139 remains explicitly
proposed; it must not become an invented zero-missing-telemetry acceptance gate.
This review does not claim blanket human ratification of every contract clause.

For the actual compatibility boundary, the current shipped memory projection
and replay behavior is documented in `docs/v0.2/LIVE_ADAPTER.md:365–405,494–529`.
Its authorization/provenance is recorded at `PROVENANCE.md:658–665`; the later
null-field repair and its preserved invalid-value rules are recorded at
`docs/STATUS.md:271–279,296–301`.

PR 35's `docs/v0.2/proposals/RUN_RECORD_TELEMETRY_DRAFT.md:1` explicitly says
**DRAFT, not accepted; no schema or code change**. That status was present in the reviewed revision above.
See [PR 35](https://github.com/axendo79/eTPS/pull/35) for the separate proposal;
this publication does not adopt it. Its proposed hardware sidecar does not redefine the existing
`x_nyx_bridge` response field or authorize composite projection.

## Existing rules that a bridge compatibility change must preserve

| Area | Current rule | Source |
|---|---|---|
| Opt-in lookup | Exact literal top-level response field; no dotted lookup or guessing; declaration is harness configuration, not sent to the model. | `LIVE_ADAPTER.md:365–367` |
| Valid memory shape | String keys; flat null/string/finite-number values. Null preserves other fields. Boolean, nested object/list, nonfinite or invalid-Unicode values invalidate the whole object. Unknown keys/strings are retained without interpretation. | `LIVE_ADAPTER.md:368–375`; `STATUS.md:271–279` |
| Projection statuses | `valid`, `invalid`, `missing` declared field, or `unavailable` without journaled body. Invalid/missing/unavailable use null projected object. Raw HTTP remains retained. | `LIVE_ADAPTER.md:377–383` |
| Numeric coverage | Each named memory metric has observed sum, coverage_count and request_count. Numeric zero is covered; null and numeric-looking strings are not converted or covered. Coverage is independent per field. Finite negative memory diagnostic values are preserved rather than repaired. | `LIVE_ADAPTER.md:385–395` |
| Request denominator | Every dispatch intent counts, including pending, failed and unfinished requests. Unattempted slots create no requests. A zero sum with zero coverage is not measured zero cost. | `LIVE_ADAPTER.md:394–397,523–524` |
| Combined totals | Backend usage counts require nonnegative integers. Each backend total is null unless coverage is complete and nonempty. Memory-arm all-token totals additionally require complete, nonempty extraction-token coverage. Known numerators/coverage remain visible when totals are null. | `LIVE_ADAPTER.md:501–524` |
| No-memory distinction | Only an arm without a memory declaration uses extraction `not_applicable`. Removing an existing declaration to hide incomplete memory cost is not a compatibility repair. | `LIVE_ADAPTER.md:511–512`, together with frozen configuration/replay rules |
| Replay | Re-derive projection/status from hash-checked raw HTTP and reject disagreement, including recomputed journal hashes. Preserve old evidence and use its recorded revision where projection semantics differ. | `LIVE_ADAPTER.md:379–402`; `STATUS.md:277–279` |
| Acceptance/scoring | Memory telemetry is unauthenticated backend reporting and does not change acceptance, I, R, RR, TPS or experimental eTPS. Invalid telemetry is not, by itself, a wrong answer or invalid measurement. Existing HTTP/answer rules still apply independently. | `LIVE_ADAPTER.md:381–405,496–499`; AGENTS required rules |
| Cost boundaries | Report ingestion/preparation separately; include task retrieval, updates, retries and storage work without adding overlapping intervals twice. Missing usage stays unavailable; processed history/internal input is processing telemetry, not newly delivered user I. | `MEASUREMENT_CONTRACT.md:125–129`; `ARCHITECTURE.md`, Independent outputs |
| Outcome disclosure | Preserve binary terminal acceptance separately from first attempt, valid failure separately from invalid measurement, and all failed/unavailable/unattempted work. | AGENTS; `PROVENANCE.md:394–403`; `MEASUREMENT_CONTRACT.md:115–119,133–145` |
| Energy | Component-only observations cannot supply a whole-system energy-per-accepted-task claim without backend coverage. | `MEASUREMENT_CONTRACT.md:159`; README current limitations |

The current code references supplied by the companion source/proof worker are
`etps_v02/memory_telemetry.py:12–13,27–33,36–63` and
`etps_v02/session_profile.py:37–66`. Their SHA-256 values are respectively
`b6fe8cd739c0d921b1ec5fba6d1a2b7a42f63dede2dfe6ab071cb73925316870` and
`6436fb75ea64ddee7ca2191e0275fdd4f9eb72cd90ca60bdf3dd3af440c89864`.
See `proof-results.json` for that worker's executed synthetic evidence; this
contract review did not repeat its projection test.

## PR 35 remains a separate proposal

The draft's proposed typed availability wrappers and nested hardware fields
(`RUN_RECORD_TELEMETRY_DRAFT.md:23–47`) are not currently valid flat memory
telemetry. Do not insert them into `x_nyx_bridge`, task metadata, frozen plan
fields or runner artifacts merely because JSON storage can hold them.

Its proposed hardware numeric rule is nonnegative; the existing memory
diagnostic rule preserves finite negative values. Importing that rule would
silently change the current projection contract. Its optional-field availability
entries are proposed documentation completeness rules, explicitly without trial
acceptance/eligibility effects (`:23–27,47–49,73–79`).

The proposed name `etps-run-telemetry-v1`, sidecar binding, and any runner/schema
integration are unadopted (`:114–124`). The draft explicitly separates a
descriptive attachment from admitted/replay-verified artifacts and leaves six
human decisions open (`:151–158`). No collector, sampling window, WPR policy,
hardware setting or schema version is selected by this review.

## Decisions needed before implementation

1. Select the compatibility surface described in `MAPPING_DECISION_BRIEF.md`:
   producer-side accepted flat telemetry with separate composite diagnostics,
   or an explicitly versioned consumer mapping. The recommendation in that
   brief is a proposal, not adopted behavior.
2. Define the exact per-request meanings of each flattened aggregate, especially
   multiple ingestion attempts, rejected batches, retries and cached responses.
   The accepted accounting rules require cost visibility but do not define a
   mapping from an `ingestions` array or `memory_complete` boolean into existing
   numeric coverage. Do not choose those semantics implicitly.
3. Specify which observed components are independently complete for tokens,
   seconds, calls and rejected facts. A known cached no-work zero may be reported
   as such; cache status alone must not fill unknown prior-attempt usage with zero.
   Retain known costs and null complete totals when any required token coverage
   remains missing.
4. Bind any new behavior to producer/consumer versions and an explicit new
   configuration/plan where required. Define replay/migration handling without
   rewriting old HTTP bytes or reinterpreting old journals silently. No default
   flip or implicit key-filtering salvage is selected here.
5. Authorize only the chosen bounded implementation and its synthetic regression
   scope. This packet does not authorize schema changes, plan/journal mutation,
   a model run, corpus access or a hardware collector.

## Focused acceptance checklist for the chosen future change

- [ ] Existing flat valid/null/string/unknown-key behavior remains unchanged;
  nested/bool handling changes only if explicitly versioned and adopted.
- [ ] Success and failed HTTP attempts retain their raw observations and request
  identity; failed/pending/unfinished dispatches remain in denominators.
- [ ] In the two-attempt failure/cached case, preserve known costs and actual
  calls independently; incomplete extraction-token coverage keeps all-token
  totals null. An apparently valid flat object must not manufacture completeness.
- [ ] Known measured/reported numeric zero remains distinct from no numeric
  coverage; partial null fields do not erase other known fields.
- [ ] Replaying the same recorded revision reproduces statuses, exact observed
  numerators and coverage. Changed projected values disagreeing with raw response
  evidence are rejected. Old journals remain intact.
- [ ] Acceptance, retention, I/R/RR/TPS/eTPS, branches and budgets remain unchanged
  for identical answer/event evidence. Report telemetry limitations separately.
- [ ] Cost sums disclose native counting scope and avoid double counting nested
  component times or duplicate aggregation. No word-count estimate replaces
  unavailable API token usage.
- [ ] Documentation records actual synthetic validation, selected compatibility
  version and unrun model/evaluation work. PR 35 stays labeled draft unless a
  separate explicit adoption changes its status.

No implementation decision was filled in here. The narrow finding is an explicit
producer/consumer projection-contract mismatch with retained raw costs and visible
incomplete coverage, not a new scoring failure or a demonstrated benchmark result.
