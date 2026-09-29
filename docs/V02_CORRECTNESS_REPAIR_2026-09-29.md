# Bounded v0.2 correctness repair handoff

Codex (Astra), model-authored, 2026-09-29. Explicit user authorization: local correctness repairs from the historical audit, with focused synthetic tests, no commits, pushes, network calls, dependency installs or model runs. Work is ready for Claude's review. These checks do not validate the absent original corpus.

## Findings and scope

| Finding | Result |
| --- | --- |
| V01 | Fixed: arbitrary response bytes project safely to the finite answer language; overflow, nonfinite values and lone surrogates are journaled exactly and classified malformed. Completed failure/recovery paths retain RR. Storage/controller errors have separate declared codes in the new policy. |
| V04 | Fixed for the authorized input-validation scope: malformed manifest/plan/script/record/export shapes raise InvalidRecord; finite huge integers do not overflow; expected CLI errors are concise and rejected imports create no database. |
| V05 | Fixed: authoring rejects unknown manifest/node keys; metadata is an object, hashed but not executed. Replay admits historical unknown fields with labeled warnings. |
| V06 | Fixed to the authorized scope: recovery probes must be path-ancestors and test the span obligations. Mutually exclusive legitimate branches pass. This does not prove all-path dominance; runtime linkage checks remain necessary. |
| V02 | Fixed: ordered status/raw-byte/generation comparisons against the pinned script; exact finished consumption, valid interrupted prefixes, and explicit unverified evidence on mismatch. |
| V03 | Fixed: finish terminal and acceptance reason are checked; abort codes must be declared invalidations. Contradictions invalidate primary evidence metrics. |
| V07 | Partially fixed: iterative graph traversal removes the recursion-depth failure. Resource caps and potentially quadratic descendant sets remain deferred. |

The historical [audit](ENGINEERING_SECURITY_AUDIT_2026-09-29.md) and [original probe output](audit_2026_09_29_results.jsonl) remain unchanged. Findings are closed only to the scope described here.

## Files changed by this repair

- `etps_v02/runner.py`: total answer projection, old malformed-projection compatibility, error categorization, script and finish/abort verification, diagnostic and report fields.
- `etps_v02/scorer.py`: explicit input validation, huge-integer finiteness, field gate and metadata, recovery ancestry, iterative graph traversal, reached-terminal reporting.
- `etps_v02/workload.py`: guarded JSON/base64/shape validation and storage-error policy.
- `etps_v02/persistence.py`: slot/journal validation and consistent legacy abort policy.
- `etps_v02/__main__.py`: concise expected validation errors with exit code 2.
- `tests/test_v02_repairs.py`: 24 new synthetic regression methods; original test files unchanged.
- `docs/audit_2026_09_29_probes.py`: catch the now-expected script-substitution rejection and use independent valid evidence for the finish contradiction, so all original counterexamples still run.
- `docs/v0.2/OFFLINE_RUNNER.md`: current behavior, compatibility rules and limits.
- `docs/STATUS.md`, `docs/v0.2/PROVENANCE.md`: new appended sections; preexisting content including Claude's additions preserved byte-for-byte.
- This handoff, `docs/v02_repair_test_output.txt`, and `docs/v02_repair_audit_output.jsonl`: review artifacts.

## Verification

`python -B -m unittest discover -s tests -v`: exit 0, **101 tests passed**, comprising the unchanged original 77 and 24 new regression methods. [Complete output](v02_repair_test_output.txt) includes every test name and result. Python used: installed Python 3.14 interpreter (local path omitted). No dependencies were installed.

New tests cover arbitrary bytes and malformed recovery/failure RR; exact legacy malformed projections; storage versus controller errors; null/scalar/list/missing/unhashable shapes; huge integers; CLI rejection without database creation; hashed inert metadata and legacy warnings; ancestor/tested-obligation recovery links and exclusive branches; script bytes/status/generation, consumption and interrupted prefixes; adapter substitution; finish terminal/reason/missing fields; abort policy in exports and a coherently modified database; and long graphs/cycles.

`python -B docs/audit_2026_09_29_probes.py`: exit 0. [Complete JSON-lines output](v02_repair_audit_output.jsonl). Compared with the historical output:

| Probe | Previous | Current |
| --- | --- | --- |
| Syntax | 17 Python files parsed | 18 parsed, including the new regression file |
| Huge-integer finiteness | OverflowError | Returns without error (the focused test asserts True) |
| Null plan / missing nodes | TypeError / KeyError | InvalidRecord / InvalidRecord |
| Ignored node policy field | Accepted | InvalidRecord |
| Future failure reference | Authoring accepted | InvalidRecord; legacy runtime still reports unlinked_recovery |
| 1,101-node graph | RecursionError | Accepted |
| Script mismatch | Accepted=1, no warnings | Accepted=0, unverified, incomplete, script_response_mismatch warning; execution aborts with InvalidRecord |
| Finish mismatch | Accepted=1, no warnings | Accepted=0, finish_terminal_mismatch and finish_reason_mismatch warnings |
| Overflow / surrogate runner | Abort, zero probe events | Finish, two probe events, no execution exception |

The standalone general JSON decoder still parses exponent overflow as infinity; model answer projection rejects it as malformed and manifest/telemetry validation rejects nonfinite executable declarations. This distinction is intentional. The deep-response probes remain completed malformed/recovery paths on this interpreter. The erased-attempt and legacy probes have unchanged results and remain open findings. In this probe script, exception="accepted" means the callable returned without an exception; it is not a model acceptance claim.

## Compatibility and deferred work

Old exact invalidation policies remain loadable and executable; they use execution_error for storage faults because storage_error was not predeclared. Newly authored policies include storage_error. Old serializable malformed answer shapes replay only if they equal the exact raw JSON decode, with a warning. Legacy v1 finishes may lack reason_code and receive a compatibility warning. None of these exceptions admits contradictory finish metadata or raw projections.

V07 resource bounds, V08 external completeness binding, V09 broader implementation identity, and V10 unsupported semantic/budget verification are outside this bounded repair. Stronger all-path provenance proof is deferred beyond the requested V06 ancestry check. Legacy v0.1 defects, unmerged branches, website, leaderboard, accounts and SEIT were not repaired. The requested audit command still characterizes its legacy counterexamples in temporary databases.

The original corpus import remains blocked by missing source files. No corpus, budgets, calibration counts or criteria were invented. CORPUS_INTAKE.md and _local_docs_draft0/ were not modified or staged. No files were staged. Original file line-ending conventions were retained; new repair files use LF. No commits, pushes, model runs, network calls or dependency installs occurred. Stop here for Claude's review.
