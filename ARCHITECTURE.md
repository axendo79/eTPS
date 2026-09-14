# eTPS architecture

Status: documentation design; no v0.2 implementation is claimed. Baseline code inspected at `ea51ce82e011c7e65bdc43e9d5af923cdcec4897`. This document was drafted with Codex assistance; [provenance](docs/v0.2/PROVENANCE.md) distinguishes decisions from proposals.

## Existing v0.1 implementation

`task_validator.py` calls an OpenAI-compatible endpoint, derives heuristic observations from assistant output, and passes them to `scorer.py`. It prints trial summaries; it does not complete the documented logger lifecycle. `scorer.py` applies the legacy efficiency, quality and continuity formula. `logger.py` provides separate SQLite run/task storage and aggregation functions. `seit.py` consumes scorer result types. `leaderboard.py` reads logger and user-profile stores; `user_profile.py` provides profile, consent and linking utilities.

These are existing code paths, not endorsements of measurement correctness. In particular, keyword presence, estimated reconstruction, timing boundaries and aggregate persistence are inadequate for the proposed v0.2 contract. Full limitations are recorded in [v0.1 status](docs/V0.1_STATUS.md). No attempt has been made to reinterpret old stored scores as v0.2 measurements.

## Proposed v0.2 flow — not implemented

```text
Versioned specification + frozen profile/corpus + configuration
                            |
                 Scripted task controller
                            |
              System adapter -> evaluated system
                            |
      Raw event, output, usage and timing record
                 |                        |
       Frozen answer predicate     Input span accounting
                 |                        |
       Failure/acceptance events    Verified R subset of I
                 |                        |
          Authorized recovery branch -----+
                            |
          Replayable trial record and separate metrics
```

### Specification and manifest

The specification defines meaning and authority. The manifest supplies state IDs and versions, sources, applicability, current/historical validity, obligation intervals, expected-answer predicates, complete user-event variants, recovery spans, branch rules, budgets, cache/reset policy and recap schedule. The evaluated system declares configuration only.

Detailed finite-variant matching and governance rules remain proposals in the [contract](docs/v0.2/MEASUREMENT_CONTRACT.md). The manifest is not yet authored or frozen. A measurement tokenizer must be pinned before numeric token goldens are produced.

### Controller and adapter

The controller delivers fixed scheduled user content. A recovery event requires a linked observed failure on the same active obligation and authorization by the frozen branch. Treatment identity is not a branch input. The adapter exposes only public task material to the system; private answer keys, failure annotations and scoring labels must not enter prompts or memory stores.

An unknown model answer follows the frozen failure policy. An off-script user message is a measurement protocol deviation, with RR unavailable rather than implicitly zero. Recovery is not inferred from an assistant saying “as mentioned earlier.”

The controller policy must cover every output with ordered categories and a final catch-all, including timeout, malformed data and exhausted retries. No unfamiliar answer should require operator-authored recovery. Missing transitions are protocol defects; retain their traces, report incomplete comparisons and repair only through a new frozen manifest. A run ledger records fixed planned slots and every attempted/unattempted outcome across both arms. Prior exposure declarations sit alongside independent freeze evidence but have a different, self-attested trust status.

### Independent outputs

Record binary terminal acceptance separately from first-attempt retention. Input accounting uses actual delivered text, fixed variant spans, the shared tokenizer and union of qualifying token indices. RR excludes replayed history, generated output and internal retrieval input; record those processing costs separately.

Raw generation TPS needs matching backend token counts and generation timings. Client latency, time to first token, observable inter-token/chunk timing, task elapsed time, retrieval and retry costs are separate. Missing backend observability is reported as unavailable, not estimated away.

Experimental eTPS is derived only where its components and acceptance conditions permit it. It cannot replace the recorded measurements. One result binds to one profile/version/hash and corpus release; no cross-profile metric mixing is permitted in the proposed publication rule.

### Replay and trust boundary

Retain exact delivered text, response bytes, ordered events, state/obligation references, branch/variant IDs, token offsets, raw clocks/counts, acceptance outcomes, deviations and configuration hashes. Replay must reproduce classifications and unrounded arithmetic. Existing storage is not assumed to satisfy this requirement.

A frozen hash identifies content; independent external publication evidence and a later run-start reference are needed to demonstrate freeze-before-run ordering. A local file timestamp or commit date alone does not establish it. Mechanism selection is still open.

## Scope boundaries

Nyx is one possible treatment, not an internal dependency or source of benchmark ground truth. No Nyx-specific scoring dimension is authorized. Account systems, leaderboard infrastructure, website features and SEIT are not prerequisites for measurement validity. Real traces must test whether answer keys probe state meaning rather than wording; consistency among these documents is not empirical evidence.
