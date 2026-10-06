# State-evolution corpus specification

Authorship/provenance: Claude (Claude Code) drafted this document on 2026-10-06 from the user's direction to specify a corpus in which evolving state, not lucky recall, decides outcomes. The requirement list in section 2 was delivered by the user (relaying a model advisor's recommendations, which the user endorsed); every operational detail below is model-proposed and under review. Draft 2 incorporates a model design review (the Dot, 2026-10-06), whose points were adopted as proposals, not rulings. Traces to [contract](MEASUREMENT_CONTRACT.md) draft 4, [corpus intake](CORPUS_INTAKE.md) and [counterexamples](COUNTEREXAMPLES.md). No task, message, answer key or count has been authored. This is a specification for authoring, not a corpus.

**Status:** draft 2, **accepted by the user on 2026-10-06** with the rulings in section 8 (recorded in [provenance](PROVENANCE.md)). No tasks are authored yet. **Conflict:** the user builds Nyx, one of the systems this corpus will evaluate, and the drafting model has read Nyx's implementation. A corpus authored under this specification by the same people, or by a model session they direct, is developer-authored and non-canonical (contract §2.1). An isolated model session reduces tailoring but does not establish independence. Section 6 limits, but does not remove, that conflict.

## 1. Purpose and claim

Measure whether a memory configuration reduces errors and user reconstruction burden when established state **changes over time**: repeated updates, lapses, unresolved disagreement and questions about earlier states. The question is comparative and system-agnostic: given identical tasks, does configuration X answer current, historical, expired, ambiguous and provenance questions more correctly and with less re-supply than simpler configurations?

**Why a new corpus is needed.** In recent exploratory calibration runs on the existing 11-task workload, a reset-only arm with no memory layer accepted 10 of 11 tasks in each repeat. A workload that a no-memory arm nearly solves cannot separate memory designs. Those runs validated harness and bridge mechanics only. This motivation is governance context and is excluded from the authoring brief (section 6).

No claim beyond the frozen corpus, profile and arms is authorized (contract §2.1, §9). A memory arm may lose.

## 2. Requirements (user-delivered)

1. Long histories with repeated changes to the same property.
2. Multiple change → change → lapse chains.
3. Historical questions mixed with current-state questions.
4. Contradictions that remain unresolved, never silently collapsed.
5. Irrelevant intervening facts that create context pressure.
6. Queries separated substantially from the original fact and its updates.
7. No-memory and naive-recall baselines kept strong enough to be credible.
8. Task authoring done independently of any memory system's implementation details.
9. Held-out tasks and answer keys frozen before the run.
10. Separate scoring for current state, historical state, expired state, ambiguity and provenance.
11. **Hard constraint:** tasks describe ordinary state evolution in natural terms. No task may use, mirror or be shaped around any evaluated system's internal vocabulary or machinery. The governance list of prohibited terms is kept outside the authoring brief, so it cannot itself steer authoring.

## 3. Task families

Every task has exactly one primary family plus crossed coverage tags (section 5). Families constrain structure, not wording. Domains are neutral and fictional, with unpredictable values (no stereotyped answers such as round numbers or common names). Each task needs alternate response traces for correct, wrong, unknown, malformed and timeout outcomes.

| ID | Family | Required structure | Primary scoring dimension |
|---|---|---|---|
| F1 | Long update chain | One property changes N times across the conversation; probe asks for the present value. | current |
| F2 | Checkpoint history | Several changes; probe asks for the value at a named earlier point in the conversation, such as "before the second change" or "originally". Includes historical questions asked after a lapse. | historical |
| F3 | Change then lapse | Chains ending in an explicit lapse with no successor, balanced against matched tasks where the value is still in effect, was reinstated after a lapse, or was never established. Probe wording is identical across these cases. | expired |
| F4 | Disagreement | Equal-authority sources disagree, balanced against matched tasks where precedence is stated explicitly (sometimes only later), so "unresolved" cannot be guessed. Probe wording is identical across cases. | ambiguity |
| F5 | Similar entities | Several entities with similar names and the same kinds of properties change independently; probes target one entity. Similarity is natural, never spelling tricks. | current / historical |
| F6 | Distance and pressure | The fact and updates are separated from the probe by irrelevant material. Some tasks stay within the declared context budget and some exceed it (section 5). The irrelevant material makes no claims about obligated state. | current |
| F7 | Mixed probe | One probe asks for current and historical values (and, where applicable, status) together, in separate answer fields. | current + historical |
| F8 | Provenance | Probe asks which source or message established the present value, among several sources that updated it. Every arm must have equal access to the same public source/message identifiers. | provenance |
| F9 | Controls | Retained single fact, never established, legitimate clarification, explicitly expired without a chain. These confirm baseline competence. | per task |

Additional sub-cases distributed across families: partial-property changes (one field of a compound value changes), scoped exceptions ("for the north site only"), negation and retraction of an earlier statement, and reinstatement after a lapse. In F1–F3, chain length N is drawn from a declared range and change types vary; some chains revisit an earlier value (A → B → A), so recency of first mention cannot stand in for currency. No exposed family names, branch names or labels appear in anything delivered to an arm.

## 4. Scoring

Use the existing deterministic JSON answer contract: no model judge, no fuzzy matching (contract §5). Every answer field carries one dimension tag: `current`, `historical`, `expired`, `ambiguity`, `provenance` or `control`. Ambiguity answers use separate fields for status and for the values, for example `{"status": "unresolved", "values": [...]}`. Status and the value set are scored as separate fields.

Field units, frozen in the manifest: each answer field is one unit. A multi-valued field is correct only as the complete specified set. Malformed, unattempted and unavailable fields are not correct, and are reported with their reason codes, never zero-filled or silently dropped.

Report per arm and repeat, never pooled across repeats:

- the existing acceptance, first-attempt retention, RR and costs (contract §4, §6–§8), unchanged;
- **first-attempt dimension accuracy**: correct fields on the first scored answer probe / planned fields, per dimension;
- **terminal dimension accuracy**: correct fields on the terminal answer after any authorized recovery / planned fields, per dimension, reported separately;
- per-family and per-coverage-tag results, so one family's gains cannot hide another's losses.

Dimension accuracy is diagnostic partial credit. It never changes binary acceptance (contract §6). Multi-valued answers may need the versioned answer-predicate extension flagged in [corpus intake](CORPUS_INTAKE.md) §3 decision 2. That, and the manifest state/obligation representation, must be resolved before authoring.

## 5. Coverage, pressure and baseline credibility

- **Coverage tags:** each task carries tags for chain depth, distance from the last relevant statement, entity similarity, ambiguity status and provenance need. Family counts are coverage targets, not statistical power. No precision or significance claim follows from them.
- **Development and evaluation sets:** counts, chain lengths and pressure levels are chosen on a separately disclosed development set. The evaluation set is then authored and frozen untouched. No evaluation task is tuned to produce predicted winners.
- **Separation predictions:** before any evaluation run, the author predicts per family which arms should fail, from task structure alone. Predictions are frozen with the manifest and never used to drop or adjust tasks.
- **No-memory arm:** a reset cannot guarantee failure. Matched wording, balanced cases and unpredictable values (section 3) limit guessing, and the frequency of correct answers after a reset is measured and reported, not assumed zero.
- **Context budget and overflow:** within-budget and over-budget tasks are separately identified within the same frozen design. Each arm's overflow behavior (truncation policy, bounded failure or declared nonparticipation) and its retrieval, storage and input ceilings are declared before the run. Every planned slot and its exposure status is preserved. A missing or nonparticipating comparator never establishes a winner (contract §8).
- **Verbatim-retrievable cases:** some tasks fit within budget such that verbatim recall can supply every relevant old and new statement. This separates interpretation errors from retrieval failure.
- **Proposed minimum size:** at least 6 evaluation tasks per family F1–F8 and at least 4 controls, about 50 tasks. The final counts are frozen in the manifest (section 8).

## 6. Authoring independence and freezing

1. **Authoring brief:** authors receive a neutral brief containing only the requirements in section 2 (without examples of system vocabulary) and the structure in sections 3–5, phrased system-agnostically. The brief excludes this document's motivation and prior results, all system names and documentation, code and run evidence. The conflict, governance and prohibited-term material stays in a separate governance record.
2. **Author:** canonical status requires an author independent of every evaluated system, under the contract's governance (§2). Until then, the corpus is developer-authored and non-canonical, whoever or whatever drafts it. Record the author, any model and session, and the derivation (intake S2).
3. **Review:** an independent review challenges not only forbidden words but also architecture-informed family selection, that is, whether the families themselves favor one design.
4. **Held out:** nobody who changes an evaluated system's code or configuration inspects evaluation task text or answer keys before the run. Any post-freeze change creates a new corpus version (contract §8).
5. **Freeze:** manifest, answer keys, branches, predictions, field units, overflow policies and counts are hashed and committed before execution. Confirmatory use additionally needs the OpenTimestamps proofs in the [attestation decision](ATTESTATION_DECISION.md).
6. **Storage and reporting:** evaluation task text and answer keys live outside public repositories (intake §5). Results are still published at trial level with opaque task IDs, together with configurations, missingness reasons and IDs, component measurements and comparison diagnostics, as contract §8 requires. Aggregation never conceals failures or incomplete exposure.
7. **Disclosure:** the author-system conflict and prior-exposure statements (intake S3–S4) travel with every result.

## 7. Prohibitions

- No evaluated system's internal terms, identifiers or operation names in task text, probes or keys (requirement 11).
- No tuning evaluation tasks against any arm's outcomes, no removing or replacing tasks after observing results, and no selective reporting.
- No external calendar dates are required to answer probes in this release. "Earlier" and "current" refer to conversation order. The manifest still records the contract's distinction between valid time and event order (contract §3); questions needing world-validity time are out of scope.
- No scheduled recap restating obligated state unless it is marked as a recap (contract §4).

## 8. User rulings (2026-10-06)

1. **Families:** all nine families F1–F9, plus the sub-cases partial-property changes, scoped exceptions, negation/retraction and reinstatement after a lapse.
2. **Size and pressure:** about 6 evaluation tasks per family F1–F8 plus controls, roughly 50 tasks. Counts are coverage, not statistical power. Chain lengths, distractor volume and the context budget are tuned only on the development set; the evaluation set is then frozen untouched.
3. **Answers:** ambiguity uses separate `status` and `values` fields. A designated multi-valued field is correct only as the complete set, order-insensitive; missing or extra values fail. A narrow, versioned scorer extension implementing exactly this (exact scalar fields plus unordered complete-set fields where the manifest designates them, with no fuzzy evaluation) is built **before any task is authored**. The manifest state/obligation representation is resolved at the same time.
4. **Authoring route:** an isolated model session given only the neutral authoring brief, explicitly developer-directed and non-canonical, with the exact author, model and session recorded. A later independent-human corpus can become the canonical test.
5. **Arms (six):** full history, reset-only, naive extracted facts, verbatim recall, the projector-0 Nyx configuration, and the projector-3 Nyx configuration, all on the same frozen corpus. Including projector 0 tests whether projector 3's transition handling matters at all on a harder workload.
6. **Provenance:** F8 is in the first release. Every arm sees identical visible source/message identifiers, so provenance tests retention and selection, not privileged metadata.

Next step: the scorer extension in ruling 3. Authoring begins only after it exists.

Implementation cross-reference (2026-10-06): the user-authorized local
[set-v1 extension](SET_ANSWERS.md) implements designated complete-set answers
and separate status/value field scoring, with diagnostic first/terminal field
counts for stable tagged plans. Heterogeneous field identity and corpus-wide
repeat grouping remain unresolved. The [state-record options memo](STATE_RECORD_OPTIONS.md)
selects no representation; ruling 3's state/obligation decision is still required
before corpus authoring.
