# State-evolution corpus specification

Authorship/provenance: Claude (Claude Code) drafted this document on 2026-10-06 from the user's direction to specify a corpus in which evolving state, not lucky recall, decides outcomes. The requirement list in section 2 was delivered by the user (relaying a model advisor's recommendations, which the user endorsed); every operational detail below is model-proposed and under review. Traces to [contract](MEASUREMENT_CONTRACT.md) draft 4, [corpus intake](CORPUS_INTAKE.md) and [counterexamples](COUNTEREXAMPLES.md). No task, message, answer key or count has been authored. This is a specification for authoring, not a corpus.

**Status:** draft 1. Non-normative until the user accepts it. **Conflict:** the user builds Nyx, one of the systems this corpus will evaluate, and the drafting model has read Nyx's implementation. Any corpus authored under this specification by the same people is developer-authored and non-canonical (contract §2.1). Section 6 limits, but does not remove, that conflict.

## 1. Purpose and claim

Measure whether a memory configuration reduces errors and user reconstruction burden when established state **changes over time**: repeated updates, lapses, unresolved disagreement and questions about earlier states. The question is comparative and system-agnostic: given identical tasks, does configuration X answer current, historical, expired, ambiguous and provenance questions more correctly and with less re-supply than simpler configurations?

**Why a new corpus is needed.** In recent exploratory calibration runs on the existing 11-task workload, a reset-only arm with no memory layer accepted 10 of 11 tasks in each repeat. A workload that a no-memory arm nearly solves cannot separate memory designs. Those runs validated harness and bridge mechanics only.

No claim beyond the frozen corpus, profile and arms is authorized (contract §2.1, §9). A memory arm may lose.

## 2. Requirements (user-delivered)

1. Long histories with repeated changes to the same property.
2. Multiple replace → replace → expire chains.
3. Historical questions mixed with current-state questions.
4. Contradictions that remain unresolved, never silently collapsed.
5. Irrelevant intervening facts that create context pressure.
6. Queries separated substantially from the original fact and its updates.
7. No-memory and naive-recall baselines kept strong enough to be credible.
8. Task authoring done independently of any memory system's implementation details.
9. Held-out tasks and answer keys frozen before the run.
10. Separate scoring for current state, historical state, expired state, ambiguity and provenance.
11. **Hard constraint:** tasks describe ordinary state evolution in natural terms. No task may use, mirror or be shaped around any evaluated system's internal vocabulary or machinery (for Nyx, for example: projector, candidate, live/retained, replacement/expiry event names, belief identifiers). Each system solves the task however it can.

## 3. Task families

Every task belongs to exactly one family. Families constrain structure, not wording. Domains are neutral and fictional (contract-style blueprint, [counterexamples](COUNTEREXAMPLES.md)). Each family needs alternate response traces for correct, wrong, unknown, malformed and timeout outcomes.

| ID | Family | Required structure | Primary scoring dimension |
|---|---|---|---|
| F1 | Long update chain | One property changes N times across the conversation; probe asks for the present value. | current |
| F2 | Checkpoint history | Several changes; probe asks for the value at a named earlier point in the conversation, such as "before the second change" or "originally". | historical |
| F3 | Change then lapse | Chains of changes ending with an explicit lapse with no successor; probe expects an explicit "none in effect" answer, not the last value. | expired |
| F4 | Unresolved disagreement | Equal-authority sources disagree; no precedence is given. Probe expects both values plus an unresolved status. Variants add a later explicit precedence statement, after which the expected answer changes. | ambiguity |
| F5 | Similar entities | Several entities with similar names and the same kinds of properties change independently; probes target one entity. Similarity must be natural, never spelling tricks aimed at an implementation. | current / historical |
| F6 | Distance and pressure | The fact and updates are separated from the probe by irrelevant material exceeding a declared size; the irrelevant material makes no claims about obligated state. | current |
| F7 | Mixed probe | One probe asks for current and historical values (and, where applicable, status) together in separate answer fields. | current + historical |
| F8 | Provenance | Probe asks which source or message established the present value, among several sources that updated it. | provenance |
| F9 | Controls | Retained single fact, never established, legitimate clarification, explicitly expired without any chain. These confirm baseline competence and keep baselines credible. | per task |

Within F1–F3, chain length N is drawn from a declared range and the order of change types varies. At least some chains must revisit an earlier value (A → B → A) so recency of first mention cannot stand in for currency.

## 4. Scoring

Use the existing deterministic JSON answer contract: no model judge, no fuzzy matching (contract §5). Every answer field carries one dimension tag: `current`, `historical`, `expired`, `ambiguity`, `provenance`, or `control`.

Report per arm and repeat, never pooled across repeats:

- the existing acceptance, first-attempt retention, RR and costs (contract §4, §6–§8), unchanged;
- **per-dimension field accuracy**: correct fields / planned fields for each dimension tag, with planned, attempted and unavailable counts;
- per-family results, so that one family's gains cannot hide another's losses.

Ambiguity answers need an explicit structure, for example `{"status": "unresolved", "values": [...]}`. Multi-valued answers may need the versioned answer-predicate extension flagged in [corpus intake](CORPUS_INTAKE.md) §3 decision 2. That decision is open (section 8).

## 5. Power and baseline credibility

- **Separation target, recorded before any run:** the author predicts per family which arms should fail, and why, from the task structure alone. Predictions are frozen with the manifest. They are not used to drop or adjust tasks after observing results.
- **No-memory arm:** F1–F8 deliver all obligated state before a reset or context boundary, so a reset-only arm cannot pass by luck. F9 controls are passable by a competent baseline.
- **Full-history arm:** some F6 tasks exceed the declared context budget, so full history is unavailable for them by construction. Other tasks stay within budget, so full history remains a strong comparator.
- **Naive and recall arms:** tasks must remain solvable in principle from a verbatim log; difficulty comes from distance, volume and change, not from information that only a structured store retains. A memory layer earns credit only by handling change correctly under pressure.
- **Minimum size, proposed:** at least 6 tasks per family F1–F8 and at least 4 controls, about 50 tasks. The final counts are frozen in the manifest before execution (section 8).

## 6. Authoring independence and freezing

1. **Author:** preferably a person or model session independent of every evaluated system. A model author receives only this specification and the contract, with no system documentation, code or prior run evidence. Record the author, model and session in the authorship record (intake S2).
2. **Held out:** nobody who changes an evaluated system's code or configuration inspects task text or answer keys before the run. Any post-freeze change creates a new corpus version (contract §8).
3. **Freeze:** manifest, answer keys, branches, predictions and counts are hashed and committed before execution. Confirmatory use additionally needs the OpenTimestamps proofs in the [attestation decision](ATTESTATION_DECISION.md).
4. **Storage:** task text and keys live outside public repositories (intake §5); only aggregate results and task family names are published.
5. **Disclosure:** the author-system conflict and prior-exposure statements (intake S3–S4) travel with every result.

## 7. Prohibitions

- No evaluated system's internal terms, identifiers or operation names in task text, probes or keys (requirement 11).
- No tuning tasks against any arm's outcomes, no removing or replacing tasks after observing results, and no selective reporting.
- No external calendar dates are required to answer probes in this corpus. "Earlier" and "current" refer to conversation order. Questions needing world-validity time are out of scope for this version.
- No scheduled recap that restates obligated state unless it is marked as a recap (contract §4).

## 8. Open decisions for the user

1. Accept or change the families F1–F9 and their dimension tags.
2. Counts per family, chain-length range N, F6 distractor volume and the declared context budget.
3. The ambiguity and multi-valued answer format, and whether it needs the versioned answer-predicate extension.
4. The authoring route (section 6.1): an independent person, or an isolated model session with a derivation log.
5. Arms for the first run of this corpus (for example full history, reset-only, naive extracted facts, verbatim recall, and the memory configurations under study).
6. Whether provenance (F8) is in the first release or deferred.

Nothing here selects these values. When the user accepts the specification, record the acceptance in [provenance](PROVENANCE.md). Authoring begins only after that.
