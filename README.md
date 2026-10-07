# eTPS — Effective Tokens Per Second

Research into user reconstruction burden and model generation throughput.

**Status: experimental v0.2 byte scorer, offline/live runners and SQLite replay store implemented alongside preserved v0.1 code. Local runs 7 and 8 used google/gemma-4-e4b for exploratory memory calibration. No independent held-out validation, calibration manifest, or benchmark claim is established. See [current state and run records](docs/STATUS.md).**

The preserved code baseline is `ea51ce82e011c7e65bdc43e9d5af923cdcec4897`. Its audit identified measurement defects; passing its self-tests does not establish benchmark validity. See [implementation limitations](docs/V0.1_STATUS.md).

## What v0.2 measures

Report raw generation TPS and reconstruction ratio (RR) separately. Primary RR uses UTF-8 bytes (`utf8_bytes`), without normalization. RR measures the fraction of newly delivered user input attributable to authorized re-supply of previously established state. The benchmark defines retention obligations; the evaluated system cannot redefine them.

The candidate `eTPS = TPS × (1 − RR)` remains a **labeled experimental index**, not measured useful output per second. It discounts a generation-side rate using an input-side fraction and does not capture every retry, retrieval, or waiting cost. Its tradeoff rankings have no validated external objective yet. The old Efficiency × Quality × Continuity formula and eScore factors are not carried into the v0.2 design.

Acceptance is binary at the trial boundary under a frozen recovery policy. Successful recovery may pass while first-attempt retention fails. Report both, with RR, re-supply bytes, attempts, timing and available processing costs. Do not let fast wrong answers count as accepted work or hide failures behind accepted-only summaries.

## Read the design

- [Measurement contract — draft 4](docs/v0.2/MEASUREMENT_CONTRACT.md): current consolidated definitions and explicitly marked proposals.
- [Architecture](ARCHITECTURE.md): existing modules versus proposed measurement flow.
- [Status and next steps](docs/STATUS.md): settled decisions, open details and release prerequisites.
- [Clause review](docs/v0.2/CLAUSE_REVIEW.md): span matching, author conflicts and comparison boundaries.
- [Counterexamples](docs/v0.2/COUNTEREXAMPLES.md) and [acceptance/timing review](docs/v0.2/ACCEPTANCE_TIMING_REVIEW.md): historical paper attacks, not executed benchmark evidence.
- [Provenance](docs/v0.2/PROVENANCE.md): user requirements, endorsements and model-authored proposals.
- [Contributing](CONTRIBUTING.md): review and change requirements.

See [offline runner usage](docs/v0.2/OFFLINE_RUNNER.md) for exact-file import, scripted execution, replay/export and interrupted-slot handling. It cannot execute model runs.

## Current work order

Follow the stages in the [isolated author-session runbook](docs/v0.2/AUTHORING_RUNBOOK.md):

1. **Development set.** Use a fresh isolated author without evaluated-system implementation exposure, given only [AUTHORING_BRIEF.md](docs/v0.2/AUTHORING_BRIEF.md) and no repository access. Preserve original outputs and provenance in private custody, then perform admission, mapping and human review. Tune design settings only on the separately disclosed development set through separately authorized development executions; record absent evidence as absent. Freeze and verify the reviewed final development bundle before evaluation authoring.
2. **Evaluation set.** Author the held-out corpus later, after final design settings and the development freeze are verified; do not author it while Nyx is under active development. Use a fresh isolated author given only the evaluation brief instance with frozen parameters. Keep evaluation text and keys in strict private custody, outside public repositories and away from anyone changing evaluated-system code or configuration. Apply the same admission, mapping and human review, then freeze untouched tasks, keys, field maps and predictions with the verified development parent before evaluation execution.
3. **Freeze and later reporting.** Verify the frozen corpus before every use and freeze one plan and grouping declaration per repeat before execution. Calibration follows under a committed manifest and complete attempt ledger; confirmatory work requires completed independent external attestation. Report all planned, attempted, unavailable and unattempted slots, with separate first/final accuracy and acceptance, primary measurements and costs. Aggregate per arm within a single plan; never combine plans or repeats or tune against evaluation outcomes.

No dependencies or model endpoint are needed for `python -m unittest discover -s tests -v` or `python -m etps_v02.examples`. The root Python programs remain legacy prototypes. Their self-tests and demonstrations must not be presented as validated benchmark runs.

Local runs 7 and 8 compared google/gemma-4-e4b with full history, reset-only and Nyx-backed prototype memory; run 8 also included naive extracted-fact memory and verbatim recall. Results are calibration only, on model-authored tasks that are not held out. Differences of one or two tasks are noise. Recovery follows frozen branches. The eTPS author builds Nyx and owns the control arms; Nyx must be allowed to lose. Backend energy unavailable means no system-energy-per-accepted-task result; local retrieval energy is component telemetry only.

The previously authored workload was intentionally excluded from the published repository and remains unavailable in this checkout. New synthetic executable fixtures are included; they are not that workload or a frozen experiment.

Pilot counts and failure branches must be fixed in advance. All attempts are disclosed; an incomplete comparison is not a Nyx win. Protocol repairs require a new manifest and both-arm reruns. Prior workload exposure remains self-disclosed. Independent freeze evidence is required for confirmatory work.

Website work, leaderboard expansion, account features, eScore and SEIT redesign are deferred. Documentation does not establish a hosted service or result-submission pipeline.

## Repository map

| File | Present role |
|---|---|
| `scorer.py` | Legacy v0.1 arithmetic and self-tests |
| `task_validator.py` | Legacy endpoint demonstration and heuristic scoring |
| `logger.py` | Legacy SQLite storage and summaries |
| `seit.py` | Legacy energy-related companion calculations |
| `user_profile.py`, `leaderboard.py` | Legacy profile/export/ranking utilities |
| `etps_v02/` | Experimental byte scorer, offline/live/manual runners, SQLite store, replay/export, CLI and synthetic examples |
| `tests/` | Synthetic unit, replay, adversarial and fake-server tests (standard library only) |
| `tools/bench_v02_scaling.py` | Synthetic harness scaling benchmark; not a model benchmark |
| `docs/v0.2/` | Draft measurement design and reviews |
| `docs/history/v0.1/` | Preserved baseline documentation, not current guidance |

Author: Joshua Holliday / True Vector Media. [MIT license](LICENSE). Cite the exact document revision and status; do not cite an unreleased v1 specification as established methodology.

Draft 4 uses character-aligned UTF-8 byte spans. Tokenizer artifacts no longer block primary RR. Token-relative secondary telemetry must identify its lock and remain separate; byte counts weight encodings differently and do not establish semantic validity.
