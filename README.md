# eTPS — Effective Tokens Per Second

Research into user reconstruction burden and model generation throughput.

**Status: v0.2 measurement design; implementation remains v0.1. No validated v0.2 scores, frozen executable corpus, or controlled comparison is available.**

The preserved code baseline is `ea51ce82e011c7e65bdc43e9d5af923cdcec4897`. Its audit identified measurement defects; passing its self-tests does not establish benchmark validity. See [implementation limitations](docs/V0.1_STATUS.md).

## What v0.2 measures

Report raw generation TPS and reconstruction ratio (RR) separately. RR measures the fraction of newly delivered user input attributable to authorized re-supply of previously established state. The benchmark defines retention obligations; the evaluated system cannot redefine them.

The candidate `eTPS = TPS × (1 − RR)` remains a **labeled experimental index**, not measured useful output per second. It discounts a generation-side rate using an input-side fraction and does not capture every retry, retrieval, or waiting cost. Its tradeoff rankings have no validated external objective yet. The old Efficiency × Quality × Continuity formula and eScore factors are not carried into the v0.2 design.

Acceptance is binary at the trial boundary under a frozen recovery policy. Successful recovery may pass while first-attempt retention fails. Report both, with RR, re-supply tokens, attempts, timing and available processing costs. Do not let fast wrong answers count as accepted work or hide failures behind accepted-only summaries.

## Read the design

- [Measurement contract — draft 3](docs/v0.2/MEASUREMENT_CONTRACT.md): current consolidated definitions and explicitly marked proposals.
- [Architecture](ARCHITECTURE.md): existing modules versus proposed measurement flow.
- [Status and next steps](docs/STATUS.md): settled decisions, open details and release prerequisites.
- [Clause review](docs/v0.2/CLAUSE_REVIEW.md): span matching, author conflicts and comparison boundaries.
- [Counterexamples](docs/v0.2/COUNTEREXAMPLES.md) and [acceptance/timing review](docs/v0.2/ACCEPTANCE_TIMING_REVIEW.md): historical paper attacks, not executed benchmark evidence.
- [Provenance](docs/v0.2/PROVENANCE.md): user requirements, endorsements and model-authored proposals.
- [Contributing](CONTRIBUTING.md): review and change requirements.

## Current work order

1. Settle remaining contract details and attack them with counterexamples.
2. Build the deterministic corpus with frozen answer predicates and recovery spans.
3. Repair scorer, runner and replay persistence against that corpus.
4. Run controlled experiments under a prepublished manifest.

No dependency installation or model endpoint is needed to review the documents. Existing Python programs are legacy prototypes, not a v0.2 quick start. Their self-tests and demonstrations must not be presented as validated benchmark runs.

The first intended experiment compares the same Gemini model/configuration with and without a memory layer, using identical scheduled input, decoding and budget policies. Recovery may differ only through frozen branches. Nyx must be allowed to lose. Author affiliation with Nyx is disclosed; the initial developer-authored profile is non-canonical. Backend energy unavailable means no system-energy-per-accepted-task result; local retrieval energy is component telemetry only.

An unfrozen corpus exists locally but is intentionally excluded from this documentation publication. No corpus task files, tokenizer lock, token goldens or their hashes are included.

Pilot counts and failure branches must be fixed in advance. All attempts are disclosed; an incomplete comparison is not a Nyx win. Protocol repairs require a newly frozen manifest and both-arm reruns. Prior workload exposure is self-disclosed separately from independent evidence that the manifest hash was published before the run.

Website work, leaderboard expansion, account features, eScore and SEIT redesign are deferred. Documentation does not establish a hosted service or result-submission pipeline.

## Repository map

| File | Present role |
|---|---|
| `scorer.py` | Legacy v0.1 arithmetic and self-tests |
| `task_validator.py` | Legacy endpoint demonstration and heuristic scoring |
| `logger.py` | Legacy SQLite storage and summaries |
| `seit.py` | Legacy energy-related companion calculations |
| `user_profile.py`, `leaderboard.py` | Legacy profile/export/ranking utilities |
| `docs/v0.2/` | Draft measurement design and paper reviews |
| `docs/history/v0.1/` | Preserved baseline documentation, not current guidance |

Author: Joshua Holliday / True Vector Media. [MIT license](LICENSE). Cite the exact document revision and status; do not cite an unreleased v1 specification as established methodology.

Draft 3 boundary revision: reject recovery spans whose endpoints cut tokens. Byte-span checks have passed; token-boundary checks remain blocked. Different tokenizer-lock hashes prohibit RR comparison, and the manifest must bind exact golden hashes.
