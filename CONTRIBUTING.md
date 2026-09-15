# Contributing to eTPS

Current priority: measurement validity. Legacy code remains v0.1; the experimental v0.2 byte scorer has executable synthetic tests; the [v0.2 contract](docs/v0.2/MEASUREMENT_CONTRACT.md) is a draft. Read [status](docs/STATUS.md), [architecture](ARCHITECTURE.md) and [provenance](docs/v0.2/PROVENANCE.md) first.

## Methodology and corpus review

Identify the clause/version, supply a concrete counterexample, and distinguish a proposed outcome from an executed result. Preserve model authorship and source attribution. Do not represent model agreement or synthetic happy-path tests as independent empirical validation.

Review recovery designation, answer predicates and temporal obligations before expanding tasks. Finite paraphrases must preserve state meaning, negation, time and authority. Test both changed wording with unchanged meaning and unchanged keywords with changed meaning. No live evaluator judgment may repair a scored manifest.

Declare authorship, employment, funding and development interests in evaluated systems or components. The Nyx developer's profile remains developer-authored and non-canonical. Neutral treatment does not erase affiliation.

## Code changes

Preserve baseline implementation until contract review and adversarial analysis support the change. Do not silently adjust v0.1 penalty constants, convert old scores to v0.2, or add new scoring factors. Executable counterexamples and scorer work can proceed before the unpublished workload arrives; byte spans, branch links and expected verdicts must be reviewable.

For eventual implementation changes, run checks appropriate to the changed behavior and add meaningful adversarial/replay tests. Legacy self-tests alone do not validate the methodology. Existing SQLite/raw-SQL conventions remain until an explicit architecture decision changes them. Documentation-only work needs link/status/claim verification rather than running endpoint or database demos.

Keep README, architecture, status and affected contract clauses synchronized. Label implemented behavior, proposed behavior, historical behavior and evidence level. Include migration notes for changes to scoring or stored-result interpretation.

## Experimental results

There is no validated v0.2 submission format or leaderboard pipeline yet. Exploratory traces may inform methodology if clearly labeled; do not publish v0.1 output as a validated comparison.

Before a confirmatory experiment, freeze the profile/corpus/configuration and publish its hash with independent external evidence before a run-start record referencing it. A commit hash alone is not proof of timing. The earlier docs-only publication preceded manifest freeze. Current implementation authorization does not itself authorize model runs or remote publication.

Each result identifies one profile/version/hash and corpus release. Report acceptance, first-attempt retention, R/I/RR, timing and processing costs with availability. List planned/attempted/valid/unavailable trials and reasons, including failures. The proposed first-pilot completeness rule requires zero unavailable RR trials for a complete-workload comparison; incomplete results remain diagnostics rather than a workload claim. This threshold is still a proposal pending freeze.

No cross-profile ranking, pooled result or metric substitution is permitted under the proposed comparison rule, even for the same system. Sampled validation of experimental eTPS must preserve its independently frozen objective, assumptions and individually identified reversed pairs. Missing backend energy means no system-energy-per-accepted-task claim.

Freeze the number of paired pilot runs and task trials, all outcome transitions (including catch-all and exhausted retries), and stop conditions. Disclose every attempted, voided and unattempted slot; unavailable RR in either arm produces an incomplete comparison, not a winner. Do not rerun until a favorable complete result appears. Protocol repairs create a new manifest hash (and new external proof for confirmatory work) and require both arms to run again. Retain all previous attempts and revisions. Include attributable prior-run/workload-exposure disclosures; these are self-attested, not independently verified by timestamping. Documentation may be published before freeze; confirmatory runs require prior completed manifest attestation. Calibration instead requires a committed manifest hash, exact artifacts and an all-attempt ledger; it cannot support superiority claims.

## Historical documentation

The [v0.1 archive](docs/history/v0.1/README.md) preserves earlier instructions and claims for audit purposes. It is not current contribution, privacy, service-availability or scoring guidance. No new account, export or public-service promise is established by the legacy modules.
