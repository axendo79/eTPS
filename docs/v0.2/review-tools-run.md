# Review-tools local handoff — 2026-10-10

Completed the user-authorized SYNTHETIC review tooling on v02-review-tools from
main 94ff867. This is Codex-authored software and simulated review evidence,
not a real author session, human semantic approval, model run, corpus freeze,
benchmark result or independent attestation. No real corpus text or anything
under the private workspace was read. No push, PR or merge was performed; this
branch remains checked out.

## Commits

| Commit | Work |
|---|---|
| e7e18ed | Advisory authoring lint, shared factual views, SYNTHETIC fixture builders/tests, lint documentation and ignored scratch/tmp. |
| c7d20fd | Self-contained HTML human review sheet, source-hash/task-bound persistence, JSON downloads, HTML/JavaScript regressions and sheet documentation. |
| 5c8d9f8 | review.json assembly through the existing freeze gate in a temporary copy, end-to-end/refusal tests, runbook/index documentation, and F8 evidence-position coverage. |

This handoff, current status and provenance are recorded in the final local
documentation commit named "Document synthetic review-tools validation and handoff".
Its exact identity is available from git log on this branch; the report does
not attempt to include its own containing commit hash.

## Files

| Files | Purpose |
|---|---|
| etps_v02/intake/authoring_lint.py | Advisory canonical JSON report and stderr summary; configurable literal phrases/window; stable factual finding codes. |
| etps_v02/intake/review_sheet.py | Offline static HTML, key/full messages, probes/corrections, histories/predictions, inline findings, checklist/notes and review-input-v1 browser downloads. |
| etps_v02/intake/review_record.py | Complete explicit review-input validation, exact artifact binding, freeze admission in a temporary copy and exclusive outside-bundle output. |
| etps_v02/intake/_review_support.py | Shared five-item checklist and factual declared-version/source/linked-recovery views; no semantic inference or mapper changes. |
| tests/review_tools_fixtures.py | New trivial SYNTHETIC documents and simulated exports built from existing authoring_fixtures.py. |
| tests/test_v02_authoring_lint.py | 11 new advisory lint regressions. |
| tests/test_v02_review_sheet.py | 7 new HTML and actual embedded-JavaScript regressions. |
| tests/test_v02_review_record.py | 11 new assembly/refusal/freeze regressions, including the requested full synthetic pipeline and single-defect blocker. |
| [AUTHORING_LINT.md](AUTHORING_LINT.md), [REVIEW_SHEET.md](REVIEW_SHEET.md), [REVIEW_RECORD.md](REVIEW_RECORD.md) | APIs, CLIs, literal observation rules, offline persistence/export format, assembly procedure and practical limits. |
| [AUTHORING_RUNBOOK.md](AUTHORING_RUNBOOK.md#maintainer-review-tools), [README.md](README.md) | One added human-review procedure section and tool discoverability; existing runbook rules preserved exactly. |
| ../STATUS.md, [PROVENANCE.md](PROVENANCE.md), review-tools-run.md | Actual implementation/evidence, authorization/authorship and local handoff. |
| .gitignore | Only addition: ignore /scratch/tmp/ for all local temporary files. |

## Test-first evidence

Each tool's new tests were written and run before its module existed. The
fail-before runs each report one unittest loader error caused by the missing
module; they do not claim that every individual method executed before code.

| Tool | Fail before | Pass after | Main evidence |
|---|---|---|---|
| authoring_lint | ImportError: authoring_lint missing; one loader error | 11 methods pass | Status-label vocabulary including missing_information; normalized scalar/set/provenance hits; source exemptions; window/counts; standalone words/explicit phrases; question references; prefix patterns; Unicode character positions and multiple/checkpoint sources; linked retry windows; canonical output and CLI exit behavior. |
| review_sheet | ImportError: review_sheet missing; one loader error | 7 methods pass | Key messages and collapsed/full conversation, exact probe/history/prediction material, five unchecked checks/notes per task, hostile text/ID escaping, correction visibility, no external resources, light/dark styles, exclusive CLI, and actual JavaScript download/restore/hash-isolation/storage-failure behavior. |
| review_record | ImportError: review_record missing; one loader error | Initial 9 methods pass; final 11 pass in the full suite | Exact source-byte binding; complete strictly boolean checks and task identity; no defect removal; existing bundle defects; unchanged freeze gate on a physical temporary copy; changed mapper bytes; exclusive outside-bundle output; snapshot changes; temp directory refusal; evaluation-parent and additional-artifact binding. |

The end-to-end test authors only a trivial SYNTHETIC document, maps it, lints it,
generates the sheet, simulates a named review-input-v1 export, assembles review.json,
then calls corpus_freeze create/verify successfully. Lint findings remain present:
software does not decide whether a factual observation is a semantic defect.
The negative test adds a single unresolved defect, gets review_defect, creates
no output and retains both the source bundle and the defect unchanged.

The sheet's actual embedded script runs in the already installed Node runtime
with a small local DOM/storage/download harness. It verifies every task's checks,
notes, all listed defect lines, downloaded JSON, restoration under the same hash,
unchecked state after a hash change, and export when storage is unavailable.
No dependency was installed. Node is optional for this extra script-execution
test on environments where it is absent; it ran and passed locally.

## Full-suite and integrity checks

Windows interpreter:

~~~text
C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe
~~~

Executed from D:\eTPS with TEMP/TMP set to D:\eTPS\scratch\tmp:

~~~text
python.exe -B -m unittest discover -s tests
~~~

| Stage | Result |
|---|---|
| Clean main baseline | 419 tests in 44.593s; 418 pass, one skip. |
| Final implementation plus runbook/index documentation | 448 tests in 51.537s; 447 pass, one skip; no failures/errors. |

The unchanged skip is the POSIX FIFO regression on Windows. All 29 new methods
pass. Existing tests use their original synthetic inputs and ephemeral fake
servers; there were no real model/remote endpoint calls.

A repository-only integrity audit compared 81 historical implementation,
test/fixture and format/brief files against main after normalizing Git's Windows
line endings: all match. It also removed the one new runbook section and proved
that the remaining runbook text is identical, checked usage-document links,
the checked-out branch and scratch ignore behavior. Scoring, mapper admission,
authoring-v1 schema/format, AUTHORING_BRIEF.md and corpus_freeze are unchanged.
git diff --check passes. Existing fixture files were not edited.

Ignored local logs remain in scratch/tmp: review-tools-baseline.txt,
lint-before.txt, lint-after.txt, sheet-before.txt, sheet-after.txt,
record-before.txt, record-after.txt and review-tools-full-suite.txt. The scope
audit script is also confined there. The record-after log is the initial
nine-method pass; the final full-suite log covers all eleven.

## Limits

Literal lint can flag innocent words, short values or public provenance ID
prefixes. Prefix grouping is an explicit advisory convention. Character offsets
refer to declared conversation text, with linked correction characters for
retries; they do not estimate tokens, actual truncation or difficulty. No
version/source for an absence means no positioned evidence.

The sheet is readable without JavaScript; persistence/download require it.
Browser file-URL storage availability varies. The available browser-surface
inventory was empty, so screenshot QA was unavailable; HTML structure/escaping,
styles and actual script behavior were checked locally. The custodian must
inspect the real private sheet alone and perform every required human check.

Assembly proves that the declared review and exact copied inventory pass the
existing freeze gate, not that the review is correct. Original checklist/notes
are retained by placing the export in the complete bundle before assembly.
Temporary-copy custody matters. Interruptions or late changes can leave an
unusable output, which must be preserved as a failure; create a new path.

## STUCK-DECISION

None. No requested behavior required a scoring, admission, authoring-format or
brief change. Human semantic decisions and independent challenge review remain
with their existing authorized reviewers; these tools do not make those decisions.
