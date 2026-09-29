# eTPS v0.2 status

Updated 2026-09-15. **An experimental byte scorer, offline runner and SQLite replay store now exist. No model benchmark runs, frozen calibration manifest, or timestamp proofs exist in this work.** Synthetic fixtures are not empirical validation or independent review.

## Implemented and checked

`etps_v02/scorer.py` is a standard-library-only pure function over a finite manifest and event record. It checks exact payloads/hashes, UTF-8 span boundaries, declared branches, source delivery and active-obligation failure links. It reports byte I/R, exact fractional RR, separate terminal acceptance and first-attempt retention, available backend TPS and conditional experimental eTPS. Protocol deviations have unavailable RR; ordinary wrong model answers follow failure branches. Legacy v0.1 modules are unchanged.

Run `python -m unittest discover -s tests -v` for synthetic checks. `python -m etps_v02.examples` reports fixture R/I/RR; TPS and experimental eTPS are unavailable because its evidence is synthetic. Pure arithmetic unit tests separately exercise dilution and cost-reversal formulas; they do not produce model performance claims.

`etps_v02/workload.py`, `runner.py`, `persistence.py` and the package CLI now support exact-byte bundle import, offline scripted execution, fixed slot order, durable request/event journaling, explicit abort, replay and export. No network or model adapter exists. Every planned slot remains visible; interrupted slots cannot be silently rerun. These paths were tested with synthetic fixtures only, including separate-process replay. See [offline runner details](v0.2/OFFLINE_RUNNER.md). Offline wall time is unavailable, not estimated from harness speed.

## Adopted revision

Primary RR uses UTF-8 bytes, identity normalization, and character-aligned half-open spans (`utf8_bytes`). Tokenizer-relative RR is optional secondary telemetry with its own lock identity; it is not implemented here and does not block core accounting. Old token-based ratios cannot be relabeled byte ratios.

Calibration uses a committed manifest hash, exact artifacts and a complete attempt ledger. OpenTimestamps is binding from the first confirmatory manifest. No calibration superiority claims. Independent review remains a later evidence milestone, not a prerequisite for implementing this non-canonical prototype.

## Next step

Bring in the unpublished authored corpus and map it to the executable schema. Review semantics, all failure transitions, resource/timing budgets, and fixed calibration counts before model execution. Freeze two separate external criteria in that calibration manifest: total newly delivered user bytes across all attempts per accepted completion, and total end-to-end time across all attempts per accepted completion. Report acceptance and missingness alongside both; zero accepted completions makes them unavailable. Examine pairwise order agreement and list reversals without claiming the criteria are universal usefulness or independent validation.

The prototype does not implement a model runner, full semantic state schema, applicability predicates, arbitrary structured answer schemas, action verification, or budget enforcement. Backend timings are supplied telemetry, not independently authenticated. All of those limits remain explicit. Canonical manifest identity here uses sorted compact JSON/UTF-8; it is not exact-file external attestation.

The original draft workload was not found in the checkout or available Library searches. It has not been imported, reconstructed or replaced by synthetic fixtures. Workload-specific integration requires the original files. No workload freeze, model execution, commit or push was performed during this implementation.


## Review corrections and delivery

New offline plans use schema v2, pin `unit: utf8_bytes`, require stable event-ID obligation boundaries and enumerate invalidation codes. Finished journals record resolved boundaries. Offline TPS/eTPS are unavailable even when scripts supply generation values. Hash mismatches warn while returning recomputed evidence; legacy exports can be replayed with compatibility warnings. Source and tests are delivered together as a ZIP; the original corpus remains separately unavailable. No model runs, commits or pushes.


The follow-up review found that failure grants persisted after recovery/correction. They are now discharged once per obligation; repeated grants on a common path fail authoring validation. Old evidence remains replayable with findings and corrected R counts. Reports now call the summary helper per task/arm, expose cost per accepted completion and pooled RR including failures, and retain unavailable reasons. New probes explicitly declare unknown-answer shapes; delayed obligation starts remain an explicit pilot limitation. The revised archive includes 77 passing synthetic tests.

The final synthetic-infrastructure follow-up pins stale citations after a fresh failure and separates schema compatibility from replay context. A v2 export can reassert authoring checks with `replay-export --validate-authoring`. Further work is the absent corpus adapter, not expansion of synthetic infrastructure.

## Corpus intake preparation (2026-09-29)

The original workload is still absent, and its import remains blocked. [Corpus intake and gap review](v0.2/CORPUS_INTAKE.md) lists required source material, maps contract requirements to the executable schema, names decisions that need the original files, and registers unset budgets, calibration counts and acceptance values without assigning them. Documentation only; no code, fixtures, model runs, commits or pushes.

## Authorized correctness repairs (2026-09-29)

Codex (Astra) implemented the user-authorized local repairs for audit findings V01 through V06, with focused synthetic regression tests. Model bytes now journal safely before malformed branching; validation fails closed for malformed shapes; unknown manifest/node fields require a hashed, non-executable metadata namespace; recovery links require ancestor probes testing the referenced obligations; replay binds response sequences to pinned scripts and checks finish/abort claims. Invalid evidence stays visible with unavailable primary RR/acceptance and explicit warnings. See [runner behavior](v0.2/OFFLINE_RUNNER.md) and [repair handoff](V02_CORRECTNESS_REPAIR_2026-09-29.md).

V07 is partially addressed by iterative graph traversal; resource bounds and descendant-set complexity remain open. V06 is fixed to the authorized path-ancestor and tested-obligation scope; all-path dominance is not claimed. V08-V10, legacy issues, and corpus integration remain deferred. The historical audit report is unchanged. The original corpus remains absent, and no budgets, calibration counts or acceptance criteria were invented. Local repairs only; no commits, pushes, network calls, dependency installs or model runs. Ready for Claude's review after the recorded checks.

## Authorized offline CI and local data hygiene (2026-09-29)

The user authorized one local branch and commit for audit G02 (offline CI) and G01 (local data ignore rules), stopping for Claude's check before Claude pushes and opens the PR. Codex (Astra) authored the SHA-pinned, read-only GitHub Actions workflow and appended ignore rules for SQLite files and companions, evidence exports, private corpus/workload directories and environment files, while allowing `.env.example`. CI runs the standard-library unittest suite on Ubuntu with Python 3.11-3.14 and Windows with Python 3.14; all matrix cells report independently. It has no dependency installation, cache or artifact-upload steps.

Local validation: `python -B -m unittest discover -s tests -v` passed all 101 tests on Windows with Python 3.14.2. This was the only installed interpreter found; a Python311 directory contained no interpreter. Python 3.11, 3.12 and 3.13 were not run locally, and GitHub Actions results remain pending. No code changes, model runs or dependency installs were performed. The historical audit remains unchanged. The corpus-intake edit is limited to the authorized ignore-rule clause; originals should still live outside the working tree.
