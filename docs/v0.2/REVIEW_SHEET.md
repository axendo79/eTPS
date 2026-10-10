# Offline human review sheet

Codex-authored maintainer tooling; SYNTHETIC tests simulate checklist state, not
human semantic review. The sheet contains private conversation text, keys,
histories and predictions. Held-out evaluation custodians run it alone under
the [author-session runbook](AUTHORING_RUNBOOK.md); no agent may inspect that
corpus through this tool.

~~~powershell
& $TaskPython -B -m etps_v02.intake.review_sheet ORIGINAL.json NEW_REVIEW_SHEET.html
~~~

API: render_sheet(raw, **lint_options) returns a deterministic HTML string.
The CLI creates the explicitly named output exclusively, never overwrites a
sheet or edits a source, and reports the exact source-byte SHA-256. Exit 0 means
created; exit 2 means invalid/unreadable input, configuration or output refusal.
It supports the same window and phrase options as [authoring_lint](AUTHORING_LINT.md).

Open the file locally in a browser. No network, external scripts, styles or
fonts are used. A content security policy denies network connections. Light/dark
colors follow the browser preference. Text/IDs are escaped before HTML insertion;
embedded metadata escapes script-closing characters.

Per task, the main view shows the first message, every declared version/claim
source, probe positions and lint-flagged messages. Other consecutive messages
collapse to "... N filler messages ..."; a full-conversation details element
exposes every message and scheduled probe. This presentation label does not
prove that omitted messages are irrelevant. Correction text, failure links,
byte spans and retries are also shown. Every probe includes wording, exact
expected object, field kinds, set declarations, requirements, unknown/alternative
answers and outcome routes. Histories, authority, time, applicability, coverage,
author predictions and inline lint observations remain available. Lint makes
no task-quality or difficulty judgment.

Review each task against all existing runbook requirements before marking:

- Conversation supports every answer.
- State history matches the conversation.
- Keys, fields, requirements and correction spans are exact.
- No unintended answer giveaway.
- Coverage tags are plausible.

Each task also has a notes box. All checks start unchecked. Browser localStorage
keys include both source SHA-256 and encoded task ID; reviewer/date/defect state
also includes the hash. Changing even source JSON whitespace starts a fresh
review. File-URL storage availability varies by browser; if unavailable, an
explicit status message says to export before closing, and current state still
downloads. Local storage contains private review information; use the authorized
custodian's browser profile and custody rules.

Enter the named reviewer and an explicit review date. List unresolved defects,
one per line. **Download review input JSON** creates a browser download:

~~~json
{
  "version": "review-input-v1",
  "source_sha256": "<exact source byte SHA-256>",
  "reviewer": "<human reviewer>",
  "date": "<declared review date>",
  "tasks": [{
    "task_id": "<source task ID>",
    "checks": {
      "conversation_supports_answers": false,
      "history_matches": false,
      "keys_exact": false,
      "no_giveaway": false,
      "tags_plausible": false
    },
    "notes": ""
  }],
  "defects": []
}
~~~

Export preserves unchecked items and every nonblank defect line (including
duplicates and its original text). It never clears defects because checks are
true. Downloading is evidence preservation, not approval; [review_record](REVIEW_RECORD.md)
refuses incomplete checks or any defect. Retain the export byte-exactly in the
private bundle as review evidence so notes/checks are bound by the final record.
The software cannot verify the truth of a review declaration or replace the
required independent challenge review.
