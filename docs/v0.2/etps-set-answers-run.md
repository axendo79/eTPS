# eTPS set-answer implementation handoff

2026-10-06. Work stayed in `D:\eTPS`, with synthetic verification artifacts in
the explicitly authorized `%TEMP%` area. Branch: `v02-set-answers`, based on
`530c5c2`. No push, external network request, model run, corpus authoring, private
workspace read, ProjectNyx edit or nyx-bridge edit occurred.

## Task table

| Task | Status | Evidence / commit |
|---|---|---|
| S1: opt-in complete sets | done | `86233d7`: `answer_predicate: set-v1`, per-probe `set_fields`, strict typed scalar elements, no duplicate/missing/extra elements, validation, field routing, offline/live/manual projection and replay. Twelve new synthetic tests. |
| S2: ambiguity shape | done | `a7dfb29`: three synthetic regressions for independent exact status and complete-set values, separate field-obligation failure routes and terminal acceptance. |
| S3: field dimensions | done for stable tagged plans; STUCK for heterogeneous plans and corpus aggregation | `ab858d6`: six diagnostic dimensions, first/terminal counts, reason counts, every planned tagged slot retained, no repeat pooling, exact replay and primary-score invariance. Eleven new synthetic tests. Scope gaps below. |
| S4: docs and authorization | done | `b4fb24e`: SET_ANSWERS.md, scorer/spec cross-references and PROVENANCE entry for explicit user authorization of local implementation/commits. |
| S5: options memo | done | This final docs commit: STATE_RECORD_OPTIONS.md covers change chains, lapses, reinstatement, disagreement, historical/current obligations and three unselected representation options with needs, risks and tests. No representation selected. |
| Full unittest run | done | Windows Python 3.14: 316 tests passed in 42.066 seconds, including all 290 original tests unchanged. |
| Existing evidence compatibility | done for score/report semantics; STUCK for literal whole-report source identity | Three pre-change synthetic exports: legacy, typed-v1 and d10-v1. All score bytes match; complete report bytes match when implementation identity is held fixed for verification. Normal replay reports changed source identities as required by existing tests. |
| Requested outside-repo handoff | STUCK | Requested path conflicts with the explicit prohibition on edits to D:\ProjectNyx and the instruction to work only in D:\eTPS. This repo-local handoff records the conflict without accessing the forbidden directory. |

## Verification

Executed from `D:\eTPS`:

```text
C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe -B -m unittest discover -s tests -v
Ran 316 tests in 42.066s
OK
```

All existing test files are byte-preserved, with only three new test files.
No old manifest, golden fixture or evidence export was edited. New tests were
written before implementation for S1 and S3; S2 adds fixture coverage of S1's
already-implemented behavior. Additional adapter tests use mocks and scripted
manual input; the existing full suite uses synthetic ephemeral fake servers.
No actual model endpoint was contacted.

The test log and pre-change synthetic exports are in
`%TEMP%\etps-set-answers-6njd0khq`. The compatibility check compared canonical
serialized score bytes directly. It also compared entire report bytes under a
test-only pinned implementation identity; this pin is not in production code.
Normal replay remains honest about source changes and reproduces classifications,
fractions and diagnostic results. Saved derived reports are ignored on replay.

## STUCK with evidence

1. **Heterogeneous planned field identity.** Spec section 4 says each answer
   field is one unit, first accuracy uses the first scored answer probe, and
   terminal accuracy uses the terminal answer after recovery. Neither section 4
   nor contract section 6 maps differently shaped probes to retry versus
   independent units. The implementation uses stable complete `field_dimensions`
   maps across probes. Different maps or partially tagged manifests yield
   `heterogeneous_field_plan` diagnostics, while classification and acceptance
   continue. No field-identity convention was silently selected.
2. **Corpus-wide repeat aggregation.** Spec section 4 requires per-arm/per-repeat
   reporting with no pooling across repeats. Current `workload.py` admits slots
   identified by task, arm and slot ID, without an explicit repeat field or
   corpus-wide repeat mapping. The report therefore retains one diagnostic row
   per tagged planned slot, including unattempted/aborted slots. It does not
   invent repeat identities or pool across them. A frozen grouping decision is
   needed for aggregate per-arm/per-repeat corpus accuracy.
3. **Literal byte-identical whole replay reports.** `runner.implementation()`
   fingerprints source files; existing hardening tests require changed modules
   to be named on replay. Altered source necessarily changes current identity
   and warnings for old exports. Legacy/typed/d10 score bytes stayed identical;
   report bytes also matched with identity held fixed in verification. Production
   identity reporting is preserved, so literal unchanged identity metadata
   cannot be promised. Existing tests were not changed to conceal this.
4. **Outside-repo handoff destination.** User instruction: "Work only in
   D:\eTPS" and "Never do ... edits to D:\ProjectNyx"; finish instruction:
   "write it to D:\ProjectNyx\scratch\etps-set-answers-run.md". These conflict.
   No write was made to that destination; this complete handoff stays inside
   the permitted workspace.
5. **State representation remains unselected.** Corpus intake section 3,
   decision 5 and contract section 3 require a representation ruling; this task
   explicitly asks the options memo to select nothing. The memo supplies the
   reviewable alternatives. Ruling 3's authoring prerequisite remains open.

No existing failing test required a change. Software checks establish mechanical
behavior only, not corpus validity or independent authorship. Stop after the
final local docs commit and clean branch/status verification.
