# State-record representation options

Docs-only decision memo, 2026-10-06. Codex authored this under the user's local
implementation authorization. The original options review selected nothing;
the subsequent maintainer rulings below select the pilot sidecar and bounded
intake validation. They do not authorize scorer schema growth or a model run. It addresses
[corpus intake section 3, decision 5](CORPUS_INTAKE.md#3-decisions-that-need-the-original-corpus)
and [measurement contract section 3](MEASUREMENT_CONTRACT.md#3-established-state-and-obligations).
The accepted [state-evolution specification](STATE_EVOLUTION_CORPUS_SPEC.md)
requires representation to be settled before authoring.

## Requirements a choice must cover

The contract requires each state record to identify its stable proposition ID
and version, value, source event and authority, establishment event, valid-time
interval, applicability, update/supersession links and retention obligations.
Event order describes learning; valid time describes applicability in the task
world. They remain distinct even though this corpus excludes questions needing
external calendar dates. State truth comes from the frozen corpus and reviewed
sources, independently of any evaluated memory system.

Obligations begin after establishment delivery and end before the designated
expiration event takes effect, or at trial end. A current obligation can end
while historical obligations continue. Contradictory sources require explicit
precedence or an unresolved state; recency alone never supplies precedence.
The answer key and separate status/value fields encode the required uncertainty.
Answer dimensions describe probes; they do not establish state truth.

The following obligations apply to every option; symbolic event names describe
requirements, not proposed corpus tasks:

| Evolution case | Required representation and obligation distinction |
|---|---|
| Change chain: A to B to C | Distinct versions and source/establishment events for each change, explicit predecessor/successor links, and current intervals ending at the next change. Historical questions identify the queried checkpoint and continue to reference the earlier version when its historical obligation remains active. |
| Lapse without successor | An explicit lapse/expiration event and an expired status, distinguishable from never-established and currently active state. Ending the current obligation must not erase the earlier value, its provenance or independently continuing historical obligations. |
| Reinstatement: A to B to lapse to A | A new establishment/version/source for the final A, even though its value repeats. Separate current intervals before/after the gap; no obligation or failure grant silently bridges the lapse. Earlier historical versions remain distinguishable. |
| Unresolved disagreement | Each source claim and its authority remain identifiable. An explicit unresolved status and complete competing value set are preserved; no supersession is inferred. Stated precedence or later resolution has its own event and must not rewrite an earlier unresolved checkpoint. |
| Partial changes and scoped exceptions | Unchanged properties retain their history; the changed property/scope has explicit identity and applicability. Any inability to express or check that scope is disclosed before authoring. |
| Provenance queries | The expected source/message is tied to the relevant version or resolution, with the same public identifiers visible to every arm. Internal retrieval records cannot substitute for evidential authority. |

The current executable obligation contains `source`, `begin_after` and
`end_before`. Authoring requires `begin_after == source`; delayed applicability
is unsupported. Ends may reference a manifest node or `$trial_end`. Probe and
recovery links test active obligations and grant byte credit, but do not verify
state versions, precedence, applicability or semantic truth. Metadata is
hash-bound but uninterpreted. [set-v1](SET_ANSWERS.md) adds answer checking and
diagnostics only.

## Unselected options

| Option | What it needs | Risks and limits | Tests needed if selected |
|---|---|---|---|
| Expiration events and separate obligation IDs only | A frozen authoring convention mapping each version to source/end events, distinct current/historical obligation IDs, and reviewed keys for expired and unresolved status. Change and lapse events must exist on every relevant branch. Reinstatement needs fresh obligation IDs. | No explicit S7 state records: version/value/authority, valid time, applicability and supersession remain conventions. It can check intervals without proving that a successor actually supersedes the same proposition. A lapse can be confused with absence; disagreement can be collapsed by a bad key. It does not by itself satisfy the full state-record contract. | Synthetic A-B-C and A-B-A chains; exact boundary behavior at establishment/change/lapse; historical obligations surviving current expiration; reinstatement gaps with fresh failure grants; branch-specific expiration not reached; unresolved claims without implicit supersession; current/expired/never-established contrasts. Semantic review must separately test the conventions. |
| Unchecked state-record sidecar, explicitly hash-bound | A separately versioned format holding all S7 records, references to executable nodes/obligations, and an immutable binding in the manifest (such as a sidecar hash in metadata). The evidence workflow must preserve exact sidecar bytes, identify who reviewed them, and verify the binding. Alternatively, an inline metadata object could hold the same unchecked records. | A bare sidecar is not checked by the current scorer or automatically retained as a required plan artifact. A hash proves identity, not valid references or true precedence. Scorer intervals, keys and sidecar state can disagree while a trial scores successfully. Inline metadata removes a missing-file risk but remains semantically unchecked. This requires an explicit pilot decision accepting that limit; it is not implicit contract compliance. | Binding and preservation checks; missing/changed sidecar rejection by the chosen intake workflow; duplicate IDs, broken version/source/obligation references, invalid interval order and inconsistent keys; change/lapse/reinstatement continuity; historical retention after current expiration; unresolved disagreement and late precedence; replay with exact sidecar bytes. Semantic mismatches remain review findings unless a separate validator is authorized. |
| Versioned executable schema growth | A separately reviewed manifest/state version with explicit state records and links from obligations/probes. Define event order versus valid time, applicability language, precedence/resolution rules, version identity, branch-dependent establishment and delayed obligations before implementation. Freeze authoring and replay compatibility rules. | Broadens the scorer beyond this narrow answer extension. A rich state language can accidentally privilege one memory design or turn implementation choices into ground truth. Migration may alter existing results unless strictly opt-in. Applicability and authority semantics can exceed finite deterministic checking; an executable validator still cannot establish source truth. | Test-first synthetic schema/reference validation and total branch policies; distinct valid-time/event-order cases; chained updates, repeats of earlier values, lapses and reinstatements; continuing historical obligations; unresolved/equal-authority sources and later precedence; scoped/partial changes; failure-grant and span accounting across every transition; malformed/timeout/unattempted outcomes; old manifest/export byte compatibility and new replay round trips. |

An independently versioned sidecar validator is a possible future extension of
the second option, not an implemented capability or a fourth selected route.
It would need its own acceptance scope, identity binding, reference and semantic
rules, compatibility tests and provenance. Moving a check out of the scorer
does not remove the need to specify it.

## Decisions still required

Before corpus authoring, an attributable ruling must settle the chosen option
and whether any unchecked contract fields are acceptable for this pilot. It
must also define stable state/version and obligation references, historical
obligation persistence after each transition, source authority and unresolved
status, the valid-time/applicability scope, and how state records and reviewed
answer keys are cross-checked and frozen. Any required executable growth needs
separate authorization and synthetic tests before tasks are authored.

The first/terminal diagnostic field plan also needs a rule if independent probes
have different shapes, plus explicit per-arm/per-repeat slot grouping for
corpus-wide reports. Those answer-unit questions cannot be settled by naming a
state-record storage format. All options and their tests above remain unselected;
none is a recommendation disguised as an implementation requirement.

## Maintainer rulings (2026-10-06)

The maintainer supplied the following rulings. They supersede the unselected
status and decision gaps above for this pilot; the options table remains the
historical review of alternatives.

1. **Field identity:** each task uses one frozen logical field map across its
   probes. If a probe cannot supply one of those fields, that field is reported
   unavailable; fields are never redefined or remapped mid-task.
2. **Repeat grouping:** one plan file per repeat; aggregate per arm within that
   plan only; never pool across plans/repeats.
3. **State representation for this pilot:** a hash-locked state-record sidecar,
   which is authoritative corpus metadata, not executable scorer logic. It
   carries the full state/version chain, source authority, establishment event,
   valid-time/applicability record, supersession/update relations, obligation
   references, lapse/reinstatement status, and unresolved-disagreement state.
   The sidecar bytes and hash are frozen with the manifest.
4. **Bounded intake validator:** a separately versioned intake/freeze tool,
   never called by scoring or replay and never changing a score. Neither the
   scorer nor the validator proves sidecar semantics, source truth or authority.
   Before freezing a corpus version, review cross-checks the sidecar against
   the executable obligations and answer keys. Any mismatch is a corpus/protocol
   defect that blocks that release from being run as valid evidence.

These are attributable maintainer decisions, not model-selected semantic
defaults. Implementation of the intake format and mechanical checks is documented
separately in [state-records-v1](STATE_RECORDS_V1.md). Recording rulings 1 and 2
does not silently change diagnostic field mapping or add report aggregation.
