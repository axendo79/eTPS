# Evaluation authoring kit

For Josh, acting as the human custodian. Built from public documentation and
SYNTHETIC software examples only. Start with [AUTHOR_CHECKLIST.md](AUTHOR_CHECKLIST.md)
and use [COMMON_MISTAKES.md](COMMON_MISTAKES.md) during review.

The isolated real author still receives **only** [brief v2](../AUTHORING_BRIEF_V2.md)
with its approved neutral parameter appendix. Do not send this kit, its templates,
examples, code or previous results to that session. Custodians may inspect held-out
material; people changing evaluated-system code/configuration may not. Record
authorship, model assistance, inspections and the profile-author/Nyx development
affiliation. Nyx must be allowed to lose. These public examples are never held out.

## Try the synthetic batch

From the repository root, using Python 3.11 or later and no dependencies:

```powershell
$env:TEMP = Join-Path (Get-Location) 'scratch/tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -B docs/v0.2/authoring-kit/check_batch.py docs/v0.2/authoring-kit/examples
python -B -m unittest discover -s tests -p test_v02_authoring_kit.py -v
```

The batch report is one JSON line, exit 0, `status: PASS`: 9 tasks, 9 explicit
sidecar intakes, 58 conformance field visits, 0 violations and 0 lint warnings.
Its 23 observations are 12 window-count records, 2 evidence-position records
and 9 reminders that token sizes remain unverified. Conformance visits count
both the manifest and separate answer key. The 21 test methods include a separate
real admission/intake/lint/conformance check for each family.

`examples/source.json` contains complete `authoring-v1` tasks, keys, histories,
requirements, predictions and branches. `examples/question-contract-input.json`
contains their public descriptors. All predictions explicitly decline to predict
execution from a software fixture. No model was run and no human review or token
budget verification is claimed.

| Family | Synthetic task | Worked structure |
| --- | --- | --- |
| F1 | SYNTHETIC-K01 | Four-value update chain with A → B → A revisit. |
| F2 | SYNTHETIC-K02 | Earlier checkpoint answer after a subsequent lapse. |
| F3 | SYNTHETIC-K03 | Change then withdrawal; scalar null and expired status. |
| F4 | SYNTHETIC-K04 | Equal-authority conflict, complete competing set, later explicit precedence, source selection and preserved unresolved checkpoint. |
| F5 | SYNTHETIC-K05 | Similar entity names and independent integer updates. |
| F6 | SYNTHETIC-K06 | Evidence at message 1 of 11; unrelated intervening material. The `over` tag expresses intended pressure; no declared/token-verified budget exists. |
| F7 | SYNTHETIC-K07 | Reinstatement; current, historical and status fields; one incorrect-answer correction and fully worded retry. |
| F8 | SYNTHETIC-K08 | Bare source-claim ID for the updated value. |
| F9 | SYNTHETIC-K09 | Unchanged, never-established, expired and exact missing-item controls; two separate questions. |

This small teaching batch does not satisfy real corpus quotas, balance every
subcase, establish difficulty or demonstrate actual context overflow. In particular,
real F6 coverage needs both within- and beyond-budget tasks and counter receipts.

## Batch interface

```powershell
python -B docs/v0.2/authoring-kit/check_batch.py BATCH_FOLDER
python -B docs/v0.2/authoring-kit/check_batch.py BATCH_FOLDER --export NEW_BUNDLE_FOLDER
```

Only two named files in `BATCH_FOLDER` are read; nothing is discovered recursively:

- `source.json`: exact final authoring-v1 bytes under `authoring-brief-v2`.
- `question-contract-input.json`: the closed declaration input below.

```json
{
  "schema": "etps-question-contract-v1",
  "question_contract_version": "h3-compressed-v1",
  "release_id": "SYNTHETIC-new-release",
  "tasks": {
    "SYNTHETIC-task": {
      "questions": {
        "SYNTHETIC-task-q001": {
          "core": "[SYNTHETIC-task-q001] What is the workshop tray count now?",
          "fields": {"count": {"kind": "scalar", "value_type": "integer", "point": "now"}}
        }
      }
    }
  }
}
```

This **kit input convention** omits `bundle_sha256`; it is not a new upstream
schema. The script adds the exact mapper bundle hash to produce the existing
five-member [question declaration](../ANSWER_CONTRACT.md#declaration-schema).
Every question, retry and field must be covered. Source wording must already
equal `question_contract.render(spec)` byte-for-byte, including descriptor field
order. This kit consistency check prevents an implicit prompt rewrite; upstream
conformance alone does not compare rendered text with authored text.

The script invokes unchanged authoring admission, mapper, explicit v1/v1.1
state-record intake, default lint and conformance APIs. Mapper outputs and the
bound declaration are temporarily written under the caller's TEMP/TMP (TMPDIR
on Unix) and removed on normal exit. **For real material, select private temporary
storage outside public repositories, the batch and the release bundle.** The
synthetic quickstart's scratch setting is only for synthetic inputs.

Stdout contains fixed schema/stage/code names and numeric counts. It emits no
input text, answers, task/field/question IDs, paths, hashes, arguments or exception
messages. Normal stderr is empty. Exit 2 / `REFUSED` gives only `check_failed`
and the stage, or `usage_error`. Inspect raw diagnostics privately using the
checklist's upstream commands; share only the complete summary line. A host or
interpreter error outside this script is not a summary receipt.

`PASS` means mechanical stages completed with no conformance violations. Lint
remains advisory: a `PASS` can have nonzero `lint_warnings`; counts are preserved.
Unknown future lint codes become `unrecognized_lint`. Human review must disposition
all findings, including the ever-present `context_pressure_unverified` reminder.
`semantics_verified` and `token_sizes_verified` remain false.

Default operation writes no input/output artifacts. `--export` exclusively creates
a new directory outside the input batch, containing unchanged mapper files,
`question-contract.json` and the exact descriptor-input bytes. Existing destinations
are refused. Interrupted/failed writes can leave an unusable directory; preserve
failure evidence and use a new destination. Export is preparation for review,
not a freeze. It neither invents settings nor generates review declarations.

This checks one authoring document/batch, not cross-batch quotas, a combined
corpus inventory or candidate pins. Use the approved custodian procedure for
those release-wide checks. A batch pass or receipt cannot stand in for a complete
evaluation release.
