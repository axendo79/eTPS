# eTPS document index

## Current operative documents

- [Contributor instructions](../AGENTS.md): current implementation context and required working rules for repository agents.
- [Measurement contract, draft 4](v0.2/MEASUREMENT_CONTRACT.md): adopted byte accounting and experimental measurement policy; unimplemented requirements remain requirements.
- [STATUS](STATUS.md): implementation and evidence state. Read dated appendices chronologically; old session statements such as "no commits" and ZIP delivery are historical, not the current repository state.
- [Offline runner](v0.2/OFFLINE_RUNNER.md): actual supported offline inputs, replay behavior and limitations.
- [Corpus intake](v0.2/CORPUS_INTAKE.md): blocked original-workload intake and unset decisions; no replacement corpus is implied.
- [Authoring pipeline](v0.2/README.md): neutral brief, strict authoring format, mapper, within-plan aggregation, reviewed freeze and isolated-session runbook; tooling and SYNTHETIC fixtures only.
- [PROVENANCE](v0.2/PROVENANCE.md): authorship, authorization and explicit superseding decisions.
- [Engineering/security audit, 2026-09-29](ENGINEERING_SECURITY_AUDIT_2026-09-29.md): preserved findings at the audited revision, not a claim that all findings remain open.
- [Correctness repair handoff](V02_CORRECTNESS_REPAIR_2026-09-29.md): scope and evidence for the earlier bounded repairs. Later dated status/provenance sections record subsequent work.
- [Hardening handoff](V02_HARDENING_2026-09-29.md): resource, identity, reporting and documentation changes, with the stopped V08 conflict and current test/probe output.
- [Legacy v0.1 status](V0.1_STATUS.md): isolation and non-maintenance policy; not operative v0.2 measurement rules.

## Historical or superseded in part

- [CLAUSE_REVIEW](v0.2/CLAUSE_REVIEW.md): draft-2/draft-3 analysis. Token-boundary requirements are superseded by draft 4's primary UTF-8 byte accounting; historical paper cases are not new corpus tasks.
- [ACCEPTANCE_TIMING_REVIEW](v0.2/ACCEPTANCE_TIMING_REVIEW.md): historical proposed acceptance/timing gates. Use the current contract and runner documentation to distinguish adopted policy from implemented checks.
- [COUNTEREXAMPLES](v0.2/COUNTEREXAMPLES.md): retains historical rows and revisions. Old token-based rows cannot be relabeled as byte measurements or empirical results.
- [v0.1 history](history/v0.1/README.md): archived formula, workflow and public-service proposals; not current implementation guarantees.

## Retained raw evidence

The [audit script](audit_2026_09_29_probes.py) stays at its current path because
its repository-root calculation depends on this directory. Its `--inventory`
mode reads every tracked file returned by `git ls-files -z` to verify UTF-8,
including all raw artifacts below. These files therefore remain at their existing
paths under the rule to retain files read or written by scripts, tests or workflows;
existing handoff links remain valid.

- [audit_2026_09_29_results.jsonl](audit_2026_09_29_results.jsonl)
- [v02_hardening_audit_output.jsonl](v02_hardening_audit_output.jsonl)
- [v02_hardening_test_output.txt](v02_hardening_test_output.txt)
- [v02_perf_correctness_W5_conflict.txt](v02_perf_correctness_W5_conflict.txt)
- [v02_perf_correctness_bench_after.txt](v02_perf_correctness_bench_after.txt)
- [v02_perf_correctness_bench_before.txt](v02_perf_correctness_bench_before.txt)
- [v02_perf_correctness_compatibility.txt](v02_perf_correctness_compatibility.txt)
- [v02_perf_correctness_tests_W1.txt](v02_perf_correctness_tests_W1.txt)
- [v02_perf_correctness_tests_W2.txt](v02_perf_correctness_tests_W2.txt)
- [v02_perf_correctness_tests_W3.txt](v02_perf_correctness_tests_W3.txt)
- [v02_perf_correctness_tests_W4.txt](v02_perf_correctness_tests_W4.txt)
- [v02_perf_correctness_tests_W5.txt](v02_perf_correctness_tests_W5.txt)
- [v02_perf_correctness_tests_W6.txt](v02_perf_correctness_tests_W6.txt)
- [v02_perf_correctness_tests_W7.txt](v02_perf_correctness_tests_W7.txt)
- [v02_perf_correctness_tests_W8.txt](v02_perf_correctness_tests_W8.txt)
- [v02_perf_correctness_tests_before.txt](v02_perf_correctness_tests_before.txt)
- [v02_repair_audit_output.jsonl](v02_repair_audit_output.jsonl)
- [v02_repair_test_output.txt](v02_repair_test_output.txt)

No document or synthetic test here establishes benchmark validity, supplies the missing original corpus, or authorizes live model execution.
