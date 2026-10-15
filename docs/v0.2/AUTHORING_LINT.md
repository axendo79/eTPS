# Advisory authoring lint

`authoring-lint-v2` is Codex-authored maintainer tooling with SYNTHETIC software
tests. It makes literal observations, never judges quality/difficulty, edits a
source, changes mapper admission or establishes semantic validity. A finding
does not block this command; human review still decides whether a defect exists.

```powershell
& $TaskPython -B -m etps_v02.intake.authoring_lint ORIGINAL.json > LINT.json
& $TaskPython -B -m etps_v02.intake.authoring_lint ORIGINAL.json --window 4
```

The API `lint_authoring(raw, window=None, status_phrases=None,
question_phrases=None)` returns a deterministic report. `report_bytes` returns
sorted compact canonical UTF-8 JSON. CLI stdout is that JSON plus a newline;
stderr is a short summary. Exit 0 includes all advisory findings; exit 2 is
unreadable/invalid authoring input or invalid configuration. The existing strict
authoring-v1 validator checks input shape; the mapper is not invoked.

Every finding has a stable code, task ID, message/probe ID and unchanged evidence
snippet (up to 240 characters). Codes and precise observation rules:

| Code | Observation |
|---|---|
| `answer_form_missing` | For each probe field, a field-scoped wording clause lacks its expected bare JSON number, exact text, bare ID, null-when-none or allowed status vocabulary form. Sets also require an array statement and each member type's form; empty sets require an empty-array-when-none statement. Determined from query kind/projection and expected value types, never a model judge. |
| `status_vocabulary_missing` | For an ordinary status field, probe wording lacks a standalone record status_labels **value**. A designated missing_information status projection requires only missing_information, without ordinary labels. Identifier projections do not require status words. |
| `answer_restated_before_probe` | A scalar or individual set member occurs after casefold and removal of whitespace in the preceding N delivered messages. Null searches for literal null; integers use decimal spelling; empty strings are not searched. V2 also checks selected source/transition IDs for non-provenance fields, marked restatement=source_id, and has no source exemptions. V2 correction messages are exempt, including retry correction positions. V1 preserves establishment and matching-source exemptions except for provenance IDs. Public ID prefixes can count as literal source mentions. |
| `status_word_leak` | A declared label or configured annotation phrase occurs with Unicode word boundaries, case-insensitively and with flexible whitespace. Ordinary uses can be false positives. |
| `question_reference_in_filler` | A configured question-reference phrase occurs in any conversation message, including a state source. The code name does not assert that the message is filler. |
| `id_style_mixed` | V1 message/probe/record IDs have differing prefix patterns within a task, or task-ID/content patterns differ across the document. A prefix is everything through the final hyphen, underscore or dot; digit runs become #; IDs without separators are unprefixed. V2 pins six ID categories at admission, including corrections; its arbitrary literal task prefix does not create a competing document style. |
| `evidence_position` | For family F8 or context_pressure=over, each field lists the selected version's transition and claim source messages. V2 reports message position as primary: zero-based message_index, one-based message_position, total_messages and first_tenth_messages (10% rounded up). Character start/end, start/total fraction and characters from source start to probe remain supplementary; v1 retains its character-based report. No version means no positioned source; absence cannot be localized to a message. |
| `key_restatement_window_counts` | Per-probe number of examined messages, their IDs, literal field/member/message hits and source-exempted hits. These are counts, not a difficulty score. |
| `missing_item_not_named` | V2 missing_information wording does not literally name its declared missing_item ID. Advisory only. |
| `values_not_in_force` | V2 values query's expected set disagrees with the selected declared state: all unresolved claim values, the one active value, or empty when expired/never established. This checks annotations, not source truth. Advisory only. |
| `evidence_outside_first_tenth` | An over-budget v2 field has an annotated tested source/transition whose one-based message position exceeds the first 10% of conversation messages, rounded up. Character fraction does not determine this finding. Human review still verifies the evidence designation. |
| `context_pressure_unverified` | Each v2 task reports conversation messages/characters and its required token-budget fraction (<0.5 within, >=1.5 over). No token budget/counter receipt exists in authoring-v1; the maintainer verifies sizes with the token counter at freeze and records them in settings.json. The lint fabricates no token estimate. |

The default window is 2 for brief v1 and 3 for brief v2. A scheduled probe follows its position message, which
counts in the window. Retry windows follow the single linked failure's
conversation prefix plus its correction(s). V2 skips correction text after taking
the window, without extending it to earlier messages; other nearby messages still
undergo the check. V1 continues to report recovery restatements.
Cyclic/unanchored declarations have an empty context and a null
probe character position; this tool does not replace mapper graph checks.

V2's primary evidence-position basis counts only ordered conversation messages;
probe wording and linked corrections do not change the first-tenth cutoff.
Supplementary character positions count Python Unicode characters in exact conversation text,
including public IDs, with no added separators, probe wording, transport wrappers
or token estimates. A retry position additionally includes linked correction
characters. Historical fields select the checkpoint version; other fields select
the last declared version through the probe anchor. Missing-information fields
also include any declared missing-item version. These are annotation references,
not a proof that the text supports the key or that truncation actually occurred.

Default annotation phrases are `expires here`, `new active version`,
`fresh version`, `status label`; v2 also adds `never established`. Default question references are
`the question that follows`, `the next question`, `the following question`,
`the upcoming question`, `the subsequent question`, `the question below`,
`the question to follow`. Repeated `--status-phrase` or `--question-phrase` options
replace the corresponding default list; API empty lists disable phrase checks
(declared status labels are still checked). The report embeds the exact lists
and window used, source-byte SHA-256, sorted findings and code counts.

Answer-form detection is a literal advisory. It splits sentence/semicolon clauses
and capitalized For/Return/Report/Provide/Give field instructions, then checks
field names at word boundaries. Shared clauses can name several fields; one
field's separate clause cannot satisfy another field. The core phrases are
`bare JSON number(s)` or `JSON integer(s)`, `exact`/`exactly` with
`text`/`written`/`conversation`/`JSON string`, `bare ID(s)`/`identifier(s)`
or an ID as a JSON string with no/without brackets, `null` with an absence
condition, and `allowed`/`one of`/`use only` plus the applicable status words.
The designated form also recognizes `use "missing_information" only`.
Field-labelled `name:` blocks retain subsequent sentences and semicolon rules
through the next field label, capitalized For/Return/Report/Provide/Give field
instruction, or paragraph boundary. This recognizes the adopted
[compressed H3](ANSWER_CONTRACT.md) scalar null conditions, source null without
a unique active claim, set member types and `[] if expired/unestablished` form
without borrowing a different field's rules. Valid alternative wording can be a false
positive; instructions that merely mention rather than command a form can be a
false negative. Human review decides; the lint never understands prose intent.
No answer-form finding adds an authoring refusal.

The maintainer's 2026-10-14 Addendum 7 settles message-position basis, size
verification in settings.json, correction-ID style, correction exemption and
keeping the normalized diagnostic as built. See the [brief-v2 handoff](brief-v2-run.md)
for the rulings and historical decision list. No authoring-format fields or
scoring rules change; broader representation/integration would need separate work.

Reports contain private text and keys. For evaluation, the authorized human
custodian runs the tool alone and retains outputs in private custody under the
[runbook](AUTHORING_RUNBOOK.md). Software findings neither grant access nor
replace the human cross-check or independent challenge review.
For a report limited to rule IDs, task IDs, field names and counts, use the
separate opt-in `python -B -m etps_v02.conformance` diagnostic described in the
answer contract. Advisory lint reports retain their existing private evidence.
