# One batch: blank to frozen

For the authorized human custodian, following the [runbook](../AUTHORING_RUNBOOK.md).
Use a new release; preserve every original, refusal and superseded revision.
Nothing here authorizes a model execution. All sample facts in this directory
are SYNTHETIC, model-authored teaching fixtures, never a development/evaluation set.

## 1. Confirm the authoring prerequisites and choose private destinations

Before evaluation authoring, verify the final development bundle and trusted
receipt; record the pinned candidate commit/configuration and comparison-arm
configurations in the evaluation manifest. Use a fresh author with recorded prior
exposure and no implementation exposure. Give that author only the exact brief-v2
instance and approved neutral frozen parameters. Retain its raw response, author,
model, session, affiliations, inspections and revisions. Developer direction is
not independent authorship; an isolated session does not remove affiliations.

Run commands from the repository root. Set these variables to **actual selected
private destinations** before running any command; never create placeholder paths.
The bundle, sheet, rendered questions, review output and receipt must be new paths.
TEMP/TMP must be private and outside the batch and bundle. For more than one
batch, repeat with distinct directories; release-wide assembly/count checks remain
the custodian's responsibility.

```powershell
$TaskPython = 'python'
$Kit = Join-Path (Get-Location) 'docs/v0.2/authoring-kit'
$Draft = '<new private draft directory>'
$Batch = '<private final batch directory>'
$Bundle = '<new private complete-bundle directory>'
$BriefInstance = '<exact brief instance actually supplied>'
$RawReply = '<byte-exact raw author response>'
$Rendered = '<new private rendered-questions JSON file>'
$Lint = '<new private lint JSON file>'
$Sheet = '<new private review-sheet HTML file>'
$ReviewInput = '<private browser-exported review-input JSON file>'
$ReviewOutput = '<new private review record outside the bundle>'
$Receipt = '<new private freeze receipt outside the bundle>'
$PrivateTmp = '<private temporary directory outside public repositories>'
$ReleaseId = '<new declared release ID>'
$FrozenAt = '<explicit freeze time>'
$Dataset = 'evaluation' # Use development for a development release.
$env:TEMP = $PrivateTmp
$env:TMP = $PrivateTmp
New-Item -ItemType Directory -Force -Path $PrivateTmp | Out-Null
& $TaskPython -B --version
```

Pass: the prerequisites are recorded, paths are private/distinct, and the selected
Python interpreter runs. No dependency installation is required. For evaluation,
verify the actual development parent now with:

```powershell
& $TaskPython -B -m etps_v02.intake.corpus_freeze verify $DevelopmentBundle $DevelopmentReceipt
```

Set `$DevelopmentBundle` and `$DevelopmentReceipt` to the preserved development
bundle and trusted receipt. Pass: exit 0, `status: verified`. Preserve that
verification separately; a receipt's self-hash alone does not verify its bundle.

## 2. Fill a task and its public descriptors

The [template](template/source.json) has all required authoring-v1 members;
[its descriptor input](template/question-contract-input.json) has the matching
question-contract entry. Copy it into a **new private draft** for custodian format
work, or compare it privately with the isolated author's output. These placeholders
are intentionally not admissible. Do not give the template or examples to the
isolated author, and do not overwrite an original author reply while filling them.

```powershell
New-Item -ItemType Directory -Path $Draft -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath (Join-Path $Kit 'template/source.json') -Destination (Join-Path $Draft 'source.json')
Copy-Item -LiteralPath (Join-Path $Kit 'template/question-contract-input.json') -Destination (Join-Path $Draft 'question-contract-input.json')
```

Fill strings and restore the indicated JSON number/boolean/enum types. For a
saved author response, retain its raw bytes and original extracted JSON separately;
any revision is a new documented draft with authorship/derivation disclosure.
Do not infer missing facts, keys or parameters from implementation behavior.
Consult the [complete format](../AUTHORING_BRIEF_V2.md) and
[structural schema](../authoring-v1.schema.json). Objects are closed; empty arrays
and nulls must be explicit. There is one expected object per question; use complete
sets for unordered multiple values, never alternative correct objects.

Pin the task's literal prefix throughout:

| Category | ID style |
| --- | --- |
| Message / question | `<task>-m001` / `<task>-q001` |
| Proposition / version | `<task>-p001` / `<task>-v001` |
| Requirement / correction | `<task>-r001` / **`<task>-c001`** |

Each category uses three decimal digits 001–999. IDs need not be contiguous;
references and public `[id] ` prefixes must match exactly. Reinstatement needs
fresh version/requirement IDs even when the value repeats. Each requirement starts
at its version's establishing message; current requirements end at the next
version message or `$trial_end`. Historical obligations have their own ends.
Each correction links exactly one failed probe, the same active tested obligation,
and a predeclared authorized branch; its retry follows the correction. Use aligned
half-open **UTF-8 byte** spans, not character offsets. F7 demonstrates a bounded
correction/retry. An empty unknown list makes that outcome unreachable; retain
its declared route without inventing an admitted unknown answer.

For every field, declare its exact answer form in every question and retry:

| Projection | Form |
| --- | --- |
| Current / checkpoint scalar | Declared JSON integer or exact JSON string; null if expired, unestablished or unresolved. No active literal-null facts. |
| Ordinary status | Exactly active, expired, unestablished or unresolved; never null. Settled/reinstated is active; resolved is only a coverage label. |
| Current values set | Complete unordered array: singleton active, all competitors unresolved, empty expired/unestablished. Declared integer/string members, no duplicates/nulls. No historical set. |
| Source | Bare public source-claim message ID as a JSON string; null without a unique active claim. Precedence selects the earlier claim, not the decision message. |
| Designated missing item | Status is only missing_information; optional identifier is the exact declared required-item proposition ID, never null. The item must never have been supplied. |

Keep ordinary status and designated missing status separate. No booleans,
floats, nested objects, extra fields, fences or descriptive prose in answers.
Each field has one dimension and an immutable task-map entry; question maps are
unchanged subsets. A checkpoint descriptor's point is exactly
`just after public message <checkpoint ID>` with the ID substituted.
The template is a single-string starting skeleton; replace/extend its field maps,
histories and descriptors to fit the authored task. See the nine worked examples
for integer, null, set, history, provenance and missing-information forms.

## 3. Render complete H3 wording before finalizing the source

Fill only **public** descriptor core/scope/point/types/IDs, never answer values
or private annotations. Include every question and retry. Set release_id to the
new release. Use the public renderer; descriptor field order controls paragraph
order and is preserved by the kit.

```powershell
$RenderProgram = @'
from pathlib import Path
import json, sys
from etps_v02.workload import decode
from etps_v02.question_contract import render
d = decode(Path(sys.argv[1]).read_bytes())
out = {t: {q: render(s) for q, s in v["questions"].items()} for t, v in d["tasks"].items()}
with Path(sys.argv[2]).open("xb") as f:
    f.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
'@
& $TaskPython -B -c $RenderProgram (Join-Path $Draft 'question-contract-input.json') $Rendered
```

Pass: exit 0 and a new private JSON file of full question strings. Paste each
complete string as that probe's `wording` in the new draft, including retries.
Keep its exact `[question-id] ` prefix. Do not rewrite an already frozen release:
H3 adoption or wording correction requires a new release/derivation and review.
Finish a new final `$Batch` containing exact `source.json` and descriptor-input
bytes; preserve originals and the documented revision history elsewhere privately.

Before saving, check the three delivered messages immediately before **each**
probe. Its position message counts among the three, including an establishing
source message. None may repeat or confirm the tested value or its source.
Correction text is exempt; other nearby messages still count. Keep status words
and annotation phrases out of conversation text; describe concrete events.
No filler may refer to a later question. Public message IDs remain visible to
every answering arm.

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath $RawReply).Hash
(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Batch 'source.json')).Hash
(Get-FileHash -Algorithm SHA256 -LiteralPath $BriefInstance).Hash
```

Pass: original/final/brief hashes are retained with provenance; the final batch
is complete and contains no placeholders. These hashes establish identity only.

## 4. Run the one-command check, then inspect diagnostics privately

```powershell
& $TaskPython -B (Join-Path $Kit 'check_batch.py') $Batch
```

Pass: exit 0, `status: PASS`, all seven stages through conformance, task/intake
totals equal, zero violations. Lint remains advisory; inspect every nonzero code.
Only the single summary line is shareable. It has no corpus text or identifiers.
This command temporarily materializes derived private artifacts in TEMP/TMP.

If refused or to examine findings, the custodian alone runs these unchanged tools:

```powershell
& $TaskPython -B -m etps_v02.intake.authoring (Join-Path $Batch 'source.json')
& $TaskPython -B -m etps_v02.intake.authoring_lint (Join-Path $Batch 'source.json') > $Lint
```

Pass: admission exit 0 / `validated`; lint exit 0 with every finding dispositioned
by the human reviewer. Raw lint contains private text/keys and must never be pasted
to an agent. A lint exit 0 can still describe a release-blocking defect. To locate
a mapping refusal privately, use the mapper CLI with a separately chosen new
diagnostic destination; it must not be reused as a completed release:

```powershell
& $TaskPython -B -m etps_v02.intake.mapper (Join-Path $Batch 'source.json') $DiagnosticBundle
```

`$DiagnosticBundle` is a new private directory. Pass: exit 0 / `mapped`;
otherwise preserve the refusal and resolve the source defect in a new revision.

## 5. Export the complete mechanical derivation and verify every sidecar

```powershell
& $TaskPython -B (Join-Path $Kit 'check_batch.py') $Batch --export $Bundle
$Index = Get-Content -Raw -LiteralPath (Join-Path $Bundle 'bundle.json') | ConvertFrom-Json
foreach ($Task in $Index.tasks) {
    & $TaskPython -B -m etps_v02.intake.state_records_v11 --manifest (Join-Path $Bundle $Task.manifest) --sidecar (Join-Path $Bundle $Task.sidecar)
    if ($LASTEXITCODE -ne 0) { throw 'Sidecar intake refused' }
}
& $TaskPython -B -m etps_v02.conformance (Join-Path $Bundle 'bundle.json')
```

Pass: export exit 0; every sidecar exit 0 / `validated`; conformance exit 0 /
`violation_count: 0`. Preserve the exact mapper source, manifests, sidecars,
keys, field maps, predictions, per-family predictions, derivations and receipts.
The script adds a hash-bound `question-contract.json` without changing mapper
bytes or question text. All `semantics_verified` flags remain false.

## 6. Verify placement and measured sizes, then complete provenance/settings

For an `over` task, annotated tested evidence must be within the first
`ceil(message_count / 10)` conversation messages, counted from 1. For 11 messages,
positions 1 and 2 qualify. Character length cannot move that boundary. Positive
source, transition and tested requirement evidence require review; absence has
no positive source position and must not be assigned an invented one.

The **conversation must be at least 1.5× the declared context budget** for over;
within conversations must be **strictly under 0.5×**. Use the declared locked
token counter, not a character-to-token estimate. Separately check complete
requests including rendered questions, wrappers/system inputs as declared,
retrieval/delivery policies and the unchanged 2048-token probe reply reserve.
An intentional over-budget conversation still needs the declared overflow policy
and complete-request headroom checks. The kit has no tokenizer or universal token
counter CLI; it cannot verify this from authoring-v1 or choose settings for you.

Set `$CounterExe` and `$CounterArgs` to the **already declared counter executable
and its exact argument array** from the frozen parameter appendix, then run:

```powershell
& $CounterExe @CounterArgs
if ($LASTEXITCODE -ne 0) { throw 'Declared token counter failed' }
Copy-Item -LiteralPath $CounterReceipt -Destination (Join-Path $Bundle 'token-counter-receipt.json')
```

`$CounterReceipt` is the selected counter's actual saved receipt, checked against
this release's exact inputs. Pass: measured ratios satisfy the thresholds and
the declared full-request/headroom convention, not merely exit 0. Record the
exact invocation, counter/version/lock, input hashes, conversation message and
Unicode-character counts, measured token counts, context budget and results in
settings.parameters. No receipt or settings sub-schema is imposed by upstream;
retain the counter's actual receipt and describe its convention. If no locked
counter/receipt exists, stop **release**, record the missing evidence, and retain
the draft; neither the kit nor freeze software proves token sizes.

Write `authorship.json` per [CORPUS_FREEZE](../CORPUS_FREEZE.md): exact author,
model, session, date, affiliations and prior-exposure record; unknown stays unknown.
Write a settings draft with version corpus-settings-v1, dataset, parameters and
development_freeze_sha256. For evaluation, copy the verified development receipt
as `development-freeze.json` and put the SHA-256 of its exact bytes in that field.
For development use JSON null and omit the parent file. Record actual settings;
do not adopt any numeric setting from a teaching example.

```powershell
Copy-Item -LiteralPath $BriefInstance -Destination (Join-Path $Bundle 'authoring-brief.md')
Copy-Item -LiteralPath $AuthorshipRecord -Destination (Join-Path $Bundle 'authorship.json')
# Evaluation only:
Copy-Item -LiteralPath $DevelopmentReceipt -Destination (Join-Path $Bundle 'development-freeze.json')
(Get-FileHash -Algorithm SHA256 -LiteralPath $DevelopmentReceipt).Hash.ToLowerInvariant()
```

`$AuthorshipRecord` and `$SettingsDraft` are completed private records. Save counts
from the actual mapper, leaving the other declared settings intact:

```powershell
$SettingsProgram = @'
from pathlib import Path
import sys
from etps_v02.workload import decode, encode
s = decode(Path(sys.argv[1]).read_bytes())
s["counts"] = decode(Path(sys.argv[2]).read_bytes())["counts"]
with Path(sys.argv[3]).open("xb") as f:
    f.write(encode(s))
'@
& $TaskPython -B -c $SettingsProgram $SettingsDraft (Join-Path $Bundle 'bundle.json') (Join-Path $Bundle 'settings.json')
```

Pass: complete truthful authorship/settings, exact brief instance, actual measured
sizes, matching counts, correct verified development parent and pinned evaluation
candidate/configuration artifacts. Include raw original responses, revision and
challenge-review evidence, branch trace evidence, lint and other intended records
**before** review assembly. The runbook requires private scripted contrast traces
for reachable correct/incorrect/unknown/malformed/timeout routes and each authorized
recovery; an empty unknown list is recorded as unreachable. Use the existing
`validate_bundle(..., authoring=True)` API with explicitly authored scripts;
do not run real tasks as public tests or invent model evidence.

## 7. Perform human cross-check and assemble the declared review

```powershell
& $TaskPython -B -m etps_v02.intake.review_sheet (Join-Path $Batch 'source.json') $Sheet
Invoke-Item -LiteralPath $Sheet
```

Pass: exit 0 / `created`, a new local sheet bound to the exact source hash.
The custodian checks every source/history/authority/transition/checkpoint,
scope/negation, obligation, complete set, answer key, field identity, branch/span,
recap, absence claim, coverage and size. Independently required challenge review
remains required. Mark checks true only after the actual review, enter the named
human/date, retain notes/resolutions, and export review-input-v1. Every defect
blocks release; no tool may clear findings on your behalf.

Put the export and all other intended evidence into the bundle **before** assembly:

```powershell
Copy-Item -LiteralPath $ReviewInput -Destination (Join-Path $Bundle 'review-input.json')
Copy-Item -LiteralPath $Lint -Destination (Join-Path $Bundle 'authoring-lint.json')
Copy-Item -LiteralPath $Sheet -Destination (Join-Path $Bundle 'review-sheet.html')
& $TaskPython -B -m etps_v02.intake.review_record $ReviewInput $Bundle $ReviewOutput
```

Pass: exit 0 / `assembled`, `freeze_validation: accepted`, exact-source binding,
all five checks true for every task and an explicitly empty defects array only
after resolution. This validates a declaration through the existing admission
gate; it does not prove human judgment. Inspect the record privately, then add
only its exact bytes as review.json. Adding other files now requires reassembly.

```powershell
Copy-Item -LiteralPath $ReviewOutput -Destination (Join-Path $Bundle 'review.json')
```

## 8. Freeze and verify the exact inventory

```powershell
& $TaskPython -B -m etps_v02.intake.corpus_freeze create $Bundle $Receipt --release $ReleaseId --dataset $Dataset --frozen-at $FrozenAt
if ($LASTEXITCODE -ne 0) { throw 'Freeze refused' }
& $TaskPython -B -m etps_v02.intake.corpus_freeze verify $Bundle $Receipt
```

Pass: both exit 0; `frozen` then `verified`. Preserve the trusted receipt outside
the inventoried bundle and verify it again before every use. Changed, added or
missing bytes block use. Never overwrite an old receipt or silently repair a
frozen result: create a new reviewed release and rerun all arms when authorized.
Confirmatory work additionally requires completed external attestation and the
contract's run-start ordering evidence. A local hash/commit is not that evidence.
This procedure produces a reviewed batch inventory, not permission to execute or
a claim that all evaluation quotas, semantic validity or independent governance
have been established.
