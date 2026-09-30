# Manual development adapter — internal only

This opt-in adapter is for human-operated service development checks. It is
not an automated model arm, publishable benchmark, or service-latency measure.
No service/network client is invoked by the adapter. Codex (Astra) authored the
implementation and scripted-input tests; no actual manual service session was
performed as part of implementation.

## Pinned plan

Use schema `etps-manual-plan-v1`, purpose `dev-manual`, unit `utf8_bytes`, the
complete standard invalidation policy, task artifact hashes and ordered slots.
Each slot has exactly `id`, `arm`, `task`. Each arm has exactly `provider: manual`,
`service` (operator-supplied label), `coder` (operator ID), and
`coding_rubric_sha256`. The nonempty UTF-8 rubric is an additional pinned artifact.
No endpoint, API key, temperature, token limit or model setting is supported.
Rubric content is not automatically interpreted or verified.

Import with the existing CLI, listing each task and rubric via `--artifact`.
Run `python -B -m etps_v02 run DB --slot ID --allow-manual`. Omitting the flag
refuses before start. Existing offline/live plans retain their behavior.

## Operator procedure and fidelity

User nodes print their exact text between UI markers and also write the exact
UTF-8 bytes to DB-STEM-messages/SLOT-HASH/NUMBER.txt beside the database. Copy
from that file to avoid terminal line-ending/rendering changes. Files are
exclusive-created, never silently overwritten. The operator must actually
deliver them; the journal cannot prove delivery or service provenance.

For each probe, paste the complete raw reply, preserving all lines, then a line
containing `<<<END_ETPS_REPLY>>>`. `--reply-sentinel` chooses another delimiter
if the reply itself contains that line. The delimiter is excluded; preceding
line endings are retained. The stored raw_base64 is exactly the bytes received
on stdin, including any newline used to terminate the final reply line. A
clipboard/terminal may already have transformed the service text; this does
not claim fidelity to inaccessible original service bytes.

Enter coded-answer JSON on one line according to the pinned rubric, or `timeout`
for a failed/unavailable service response. The code is projected under the
manifest's answer schema and classified; raw prose is not classified. Bad JSON
or out-of-schema coding projects to malformed. The adapter shows the outcome
and next node, and requires `yes` before persisting the response event. It
records raw reply, original coded bytes, projected answer, coder, confirmation,
branch and timezone-aware local timestamps. Request intent precedes input.

Refusing confirmation aborts with operator_abort and no probe response event.
EOF/input errors invalidate as execution_error; filesystem/database faults use
storage_error. They are harness faults, not model failures. Confirmed timeout,
incorrect and malformed outcomes retain the normal task branches and failed
trials. Unfinished requests remain visible. Unknown user payload remains a
protocol deviation distinct from a wrong answer. Field routing is supported.

## Evidence fence and replay

Every trial, report and evidence export has label `dev-manual-human-coded`,
`publish_excluded: true`, and `coding_correctness_verified: false`. Reports
put all manual trials/summaries inside `dev_manual`; top-level automated
`trials` and `summaries` are empty. Automated and manual providers cannot mix
in this schema. TPS and experimental eTPS are always unavailable. Monotonic
`operator_wall_seconds` is explicitly operator-paced, not service latency;
it is not supplied to automated wall-time summaries.

Ordinary v1/v2 evidence exports remain available privately. `export --audience
leaderboard` and `export --audience website` reject manual evidence before
creating a file; the Python export API applies the same guard. These are
publication fences, not website uploaders or automatic redactors. No existing
v0.2 leaderboard/website publisher existed to modify. Default export remains
private evidence, not permission to publish its contents.

Replay verifies the journal chain, pinned inputs/rubric, coded-byte projection,
coder IDs, branch choices, confirmation, timestamps and lifecycle. It explicitly
cannot verify coding correctness. Rewriting raw replies plus codes and all
hashes coherently defeats the checks; there is no attestation. Old plans and
exports do not acquire manual fields. Optional independent second-coder recode
storage/agreement reporting is deferred; no independence is claimed.

If the task author also builds a competing product (Skopos), disclose that
conflict and keep the results internal-only. Human coding and this author
conflict rule out treating these development sessions as publishable evidence.
Private draft tasks/rubrics require user review and approval before operation.
