# Opt-in live exploratory adapter

Codex (Astra), 2026-09-29. This is implementation documentation, not model-run
authorization or evidence of model performance. Tests use ephemeral loopback
fake servers and mocked remote transport. No real local/cloud model calls or
calls to port 1234 were made. Existing offline plans retain their execution and
replay behavior. Field-routing support is integrated by a merge commit.

## Explicit plan contract

Use `schema: "etps-live-plan-v1"`, `purpose: "live-exploratory"`,
`unit: "utf8_bytes"`, the exact offline-v2 invalidation policy including
`storage_error`, hash-pinned `tasks`, and ordered `slots`. Live slots contain
exactly `id`, `arm`, `task`: they do not reference synthetic response scripts.
The only pinned artifacts are the task manifests. No live value is inferred
from an offline plan or supplied by an adapter default.

The additional required top-level fields are:

| Field | Meaning |
|---|---|
| `endpoint` | Default base URL; an optional arm `endpoint` overrides it |
| `arms` | Object mapping each declared arm name to the explicit settings below |
| `request_deadline_seconds` | Positive finite controller deadline per request |
| `trial_wall_limit_seconds` | Positive finite limit from trial start to terminal |
| `exposure` | Exactly `non_loopback` and `remote_endpoint_authorized`, both Boolean; actual endpoint locality must agree |

Each arm requires `provider` (`openai-compatible` or `anthropic`), `model`,
`temperature`, `seed` (integer or explicit null), positive integer `max_tokens`,
and `api_key_env` (environment-variable name or explicit null). A `system_prompt`
string is optional. Anthropic additionally requires an explicit
`anthropic_version` date for its header and `seed: null`, because its Messages
request does not support a seed. No model/settings/budget values are selected
by this document. Provider-specific compatibility beyond this finite request
surface is not claimed; a server rejection remains a recorded transport outcome.

Task manifests use user/probe/terminal and optional session_boundary nodes and may opt
into typed-v1 answers and field-v1 routing. Live execution and replay use the
same scorer routing function as offline execution, including partial-field
failure attribution. State, budget or action metadata is not enforcement.

## Authorization and credentials

Import with `python -B -m etps_v02 import DB --plan PLAN --artifact TASK`, listing
every task artifact. A remote plan import also requires `--allow-remote` and
`exposure.remote_endpoint_authorized: true`; otherwise validation refuses it.
Run with `python -B -m etps_v02 run DB --slot ID --allow-live`. Remote execution
additionally requires `--allow-remote` on that run; prior import authorization
does not authorize dispatch. Offline plans never dispatch HTTP, even if flags
are supplied. Report/export/replay are read-only with respect to the endpoint;
they do not need dispatch authorization or credentials.

Loopback means exactly localhost, 127.0.0.1 or ::1. Localhost is routed to the
literal loopback address, avoiding DNS substitution. Non-loopback requires
HTTPS and both authorization gates. URLs containing embedded credentials,
query strings or fragments are rejected. Proxy environment settings and HTTP
redirects are disabled, and no HTTP retry is automatic.

Before writing a start entry, preflight checks any configured credential and
opens and closes a TCP connection to the endpoint host and port. No HTTP,
TLS handshake or application data is sent by this check. It uses the plan's
explicit request deadline. A refused preflight leaves the slot unattempted,
writes no journal entry and produces a concise `error:` with CLI exit 2.
Preflight proves reachability only; it cannot establish model availability or
credential acceptance. Trial wall timing begins after preflight.

Only an environment-variable reference is stored. A configured key must exist,
be non-empty and contain only visible ASCII without whitespace or controls.
The key is read again at request time after durable request intent.
OpenAI-compatible requests use Authorization
Bearer; Anthropic uses x-api-key plus the declared anthropic-version header.
Headers and exception text are never journaled or printed. A configured
credential that disappears or becomes malformed during a trial is a harness
fault: the trial aborts with the predeclared `execution_error` invalidation,
retaining its durable prefix. It is not a model timeout. A literal credential
echo in a response body is withheld as `credential_echo`, retaining its hash
but not its body. Tests check a sentinel across journals, reports and exports.
Operators must not place credentials themselves in task text, model names,
system prompts or other persisted plan fields.

Each remote slot appends a hash-chained `exposure` record before dispatch:
endpoint host, provider, model ID, that slot's task artifact hash, and UTC
timestamp. This is an intent/possible-exposure ledger, including uncertain
delivery and failed attempts. It covers this runner's recorded slots, not
undisclosed external executions or historical exposure. It is not attestation.

## Requests and evidence

The OpenAI-compatible path posts non-streaming JSON to BASE/chat/completions.
Anthropic posts to BASE/v1/messages; its system prompt is top-level `system`.
Only public user texts, previous successful assistant content and the explicit
model settings enter request bodies. Answer keys, obligation/branch IDs and
arm labels are excluded. System prompts are recorded but excluded from I.
Timeouts do not invent prior assistant content. No tools, retrieval, images,
streaming, or automatic conversation repair are supported.

Before each request intent and dispatch, the public conversation must be
non-empty and end with a user message. An empty history or assistant prefill
aborts with `execution_error` before any HTTP request for that probe. This is
a manifest/controller defect, and applies to both providers; a system prompt
does not satisfy the public-user requirement.

Intent is committed before transport. Response events retain exact UTF-8
assistant text as raw_base64, full HTTP body bytes and SHA-256 when available,
usage exactly as supplied (or null), named backend statistics and client
monotonic latency. Anthropic text blocks are concatenated in order with no
inserted separators. Unsupported/non-text envelopes are transport failures.
An empty assistant string is a model answer and normally classifies malformed.
Replay verifies body hashes, envelope/projection agreement, public request
history/settings, exposure binding, timings and terminal claims before scoring.
Editable hash chains still do not independently prove endpoint execution.

Inside a trial, deadline, refused connection, non-2xx, invalid envelope,
credential echo and response size limit use status timeout
with a transport_detail code. They follow the manifest's timeout transition,
not storage/controller invalidation. Unexpected model answers remain measured
outcomes. Unknown user payload remains a protocol deviation. Process crashes
can leave a durable unfinished request; there is no implicit resume or reissue.
An operator may explicitly abort such a prefix under the declared policy.

New start records carry `controller_policy: "guard-v1"`. Replay verifies the
conversation guard and rejects `credential_unavailable` as a timeout detail
under that policy. Older journals remain readable; an old credential timeout
has the explicit warning `legacy_credential_outcome: harness fault recorded as
timeout`. Harness-aborted trials retain unavailable measurements, rather than
becoming measured model failures. Replay does not repeat preflight or use keys.

## Budgets and timing

The request carries the exact declared max_tokens ceiling. The backend enforces
its native token cap; the client has no tokenizer and cannot independently
audit server tokenization. A worker bounds controller waiting by the request
deadline (also capped by remaining trial time). A timed-out worker cannot
journal or retry but may finish later; cancellation of backend generation is
not claimed. Slow/trickled responses cannot extend the controller wait. The
existing MAX_RESPONSE_BYTES ceiling also bounds HTTP reads; it is a software
safety limit, not an experimental budget.

Reaching the wall limit finishes a retained bounded failure with reason
`trial_wall_limit`, even if the last answer would otherwise accept. The scorer
accounts for the actually delivered prefix and preserves available RR; no
undelivered scheduled messages are fabricated. Such a prefix does not establish
complete schedule exposure. Wall time is monotonic trial start through terminal,
including request/journal work before that boundary; the final finish-record
write is after the measured boundary. Reports use measured wall time in
per-accepted-completion summaries, including measured failures in costs.

Usage plus client latency never becomes generation TPS. The only interpreted
backend generation pair is `timings.predicted_n` and `timings.predicted_ms`,
converted from milliseconds with source field names retained. Both must have
valid count/duration shapes; otherwise generation telemetry is unavailable.
Raw `stats` and `timings` are retained, including unrecognized fields. A lone
tokens_per_second field does not provide matching generation count and time.
Without that pair TPS and experimental eTPS remain unavailable for either
provider. Client latency is response latency, not backend generation time.
Backend statistics are provider assertions, not independently instrumented truth.

The adapter cannot establish fairness, independent semantic validity, energy,
hidden reasoning scope, endpoint version stability or absence of prior exposure.
No calibration count, arm configuration, comparison threshold or winner rule
is supplied here. Real smoke tests require separate user authorization.

## External providers

An optional per-arm `endpoint` overrides the plan endpoint for preflight,
dispatch, model checks and exposure records. `exposure.non_loopback` must equal
whether ANY effective arm endpoint is remote. Such a plan requires both its
remote authorization flag and `--allow-remote`, even when selecting a local arm.
Only remote slots record remote exposure; the host belongs to the selected arm.
All slots remain in one plan's pairing/accounting and per-arm summaries.

The user specified Anthropic at `https://api.anthropic.com` with
`ANTHROPIC_API_KEY`, OpenAI-compatible at `https://api.openai.com/v1` with
`OPENAI_API_KEY`, and Gemini's compatible base at
`https://generativelanguage.googleapis.com/v1beta/openai` with `GEMINI_API_KEY`.
These are user-supplied settings, not verified endpoint/model availability.
The supplied Anthropic version is `2023-06-01`; current documentation was NOT
queried because this authorization forbids external requests by Codex.

The operator can run `python -B -m etps_v02 check-models PLAN --allow-remote`.
It sends only GET requests for model metadata: BASE/models/MODEL for compatible
providers and BASE/v1/models/MODEL for Anthropic. It sends no task text, answer
keys or artifact bytes. Credentials use the same environment references and
headers as generation, with no proxy, redirects or retries. Output per arm is
`ok`, `not-found`, or `auth-error`; network, unexpected HTTP and malformed data
are honestly labeled `unavailable`. Any unsuccessful check exits 2. Metadata
recognition does not prove Chat Completions compatibility: no actual generation
was attempted, including for the user-specified Astra model. A Responses adapter
has not been added. Cloud TPS/eTPS remain unavailable without matching backend
generation counts AND durations; usage/client latency cannot supply them.

Only user-operated synthetic smoke runs are authorized here. Corpus runs need
separate permission. Codex authored the private kits and synthetic task; those
are model-authored software fixtures, not benchmark evidence.

## Opt-in native LM Studio

`provider: "lmstudio-native"` uses BASE/api/v0/chat/completions, non-streaming,
and requires a loopback endpoint and `api_key_env: null`. It retains the explicit
live settings and normal authorization/journaling rules. `check-models` uses
BASE/api/v0/models/MODEL for this provider. No actual LM Studio instance was
contacted to implement or test it; all dispatch tests used ephemeral fake servers.

The only native generation pair interpreted is `usage.completion_tokens` (a
nonnegative integer, not Boolean) and `stats.generation_time` (positive finite
seconds). Both source field names are recorded in `generation_source`. If either
field is missing or invalid, generation TPS and eTPS stay unavailable. A lone
`stats.tokens_per_second`, client latency, or compatible-provider `timings`
object does not supply that native pair. Raw stats and usage are retained for
inspection. These are explicit fixture/schema interpretations, not independent
verification of a currently installed backend's telemetry semantics. The
OpenAI-compatible provider's existing timing interpretation is unchanged.

## Frozen opt-in response extraction: fence-v1

Live plans may set `response_extraction: "fence-v1"`. The rule is plan-wide,
identical for every arm/provider. Absence retains strict projection and the old
journal/report layout; offline and manual plans do not accept this field.

For fence recognition only, trim leading/trailing ASCII space, tab, CR, LF,
vertical tab and form feed. The entire remainder must be one block: an opening
line of three backticks or three backticks followed by lowercase `json`, with
optional trailing ASCII spaces, then the body, then a closing line of exactly
three backticks. LF and CRLF line endings are accepted. An additional fence line
in the body rejects extraction. Other tags, surrounding prose, unclosed fences,
embedded or multiple blocks take the strict path on the unchanged original
reply. No Unicode whitespace normalization or partial-match/prose repair occurs.
The body uses the existing schema projection; extracting malformed JSON does
not make it a valid answer. Even an empty recognized block records extraction.

Original raw_base64 and public assistant conversation content remain unchanged.
Every opted-in probe records a Boolean `extracted`, including false for strict
answers and transport timeouts. Replay recomputes both answer and flag from the
pinned plan and raw bytes, rejecting disagreement or a missing/non-Boolean flag.

Opted-in reports add `strict_json_rate` keyed by arm: raw counts `numerator`
and `denominator`, plus exact fractional `value` (null when denominator is zero).
The denominator includes every recorded status-ok probe across that arm's slots,
including unfinished/failed trials. The numerator counts replies projected as
an answer under that task's schema WITHOUT extraction; wrong but valid objects
count, while malformed objects and fenced replies do not. Transport timeouts
are excluded. This diagnostic never changes classification or acceptance.
Reports for old plans do not acquire this field, and old runs are not rescored
under the new extraction policy.

The user chose max_tokens 2048 for future runs, with reasoning tokens counting
against that output budget. The private smoke plan uses this explicit value;
it is not a new adapter default or a retroactive change to evidence. Backend
token-budget enforcement remains provider-dependent and is not independently
measured by this client.

## Frozen opt-in timing: decode-v1 (2026-09-30)

Live plans may freeze `"timing_convention": "decode-v1"`, identically for every
arm. Absent this field, full-generation scoring and event layout are unchanged.
Unknown convention names and this field on offline/manual plans are rejected.
Under decode-v1 primary TPS and experimental eTPS use summed decode tokens /
summed decode intervals. Any probe lacking that pair makes trial TPS unavailable;
full-generation TPS never substitutes for it.

For `lmstudio-native`, decode tokens are `usage.completion_tokens - 1` and
decode seconds are `stats.generation_time - stats.time_to_first_token`.
Completion tokens must exceed one; both times must be present and finite, TTFT
nonnegative, and their difference positive. Full-generation TPS remains the
secondary `completion_tokens / generation_time`. The synthetic case of 70
tokens, 3.217 seconds generation and 1.595 seconds TTFT gives 42.54 decode TPS.

For `openai-compatible`, the frozen explicit allowlist is `timings.decode_n`
and `timings.decode_ms` (decode token count and milliseconds). Both must be
usable and positive. `predicted_n`, `predicted_ms`, a reported rate, or client
latency alone do not establish decode semantics and remain unavailable.
Secondary full-generation throughput requires explicitly named
`timings.full_generation_n` and `timings.full_generation_ms`; this does not
claim that a particular llama.cpp build emits these fields. No ambiguous
predicted interval is relabeled. Other providers currently have no decode pair.

Each opted-in probe adds `timing`: full_generation_tps, decode_tps,
ttft_seconds, prompt_tokens, prompt_prefill_seconds, decode_seconds,
completion_tokens and client_elapsed_seconds, each with value (or null) and
source_fields. Native prefill uses only `stats.prompt_eval_time` in seconds;
compatible prefill uses `timings.prompt_ms`, and TTFT uses
`timings.time_to_first_token_ms`. Prompt tokens use `usage.prompt_tokens`,
falling back to explicitly reported `timings.prompt_n` for compatible responses.
Completion counts use `usage.completion_tokens`, including reasoning tokens;
reasoning counts are never subtracted or estimated. Client elapsed uses the
recorded `client_latency_seconds`. Unsupported/missing fields stay unavailable.

The original full-generation `generation` pair remains in the event for legacy
inspection. The selected decode pair and all secondary projections are verified
against raw HTTP envelope fields on replay, with client elapsed identified as
client evidence. These are backend-reported observations, not independently
authenticated clocks. D10 answer tolerance can be used independently or together
with decode-v1 and fence-v1. Existing recorded runs are not rescored.

## Session boundaries and processing costs (2026-09-30)

An arm may declare `context_policy: "full"` or `"reset-v1"`. Absence means
`full`; request bodies retain the existing full-history behavior byte for byte.
No policy name is sent to the provider. Both arms reference the same exact task
artifact. A task opts in by including a node such as
`"boundary": {"kind": "session_boundary", "next": "question"}`. It has no
text, contributes nothing to I or R, and does not end retention obligations.
The event marks a possible context reset, not new user input.

Full ignores boundaries when building public history. Reset-v1 clears all
prior public user and assistant messages at every boundary. The next request
contains only public messages delivered afterward, plus the arm's persistent
system_prompt if declared. Subsequent messages accumulate until another
boundary. This controls submitted context; it cannot independently prove that
a provider has forgotten hidden server-side state or cleared a cache.

Authoring rejects any boundary-to-probe path without an intervening user node,
under either policy. A boundary belongs before the question's user node, not
between that question and its probe. The existing dispatch prefill guard still
applies. Replay rebuilds history from the pinned arm policy and boundary events
and checks the complete request body; rehashing a tampered history does not make
it valid. Scoring obligations and recovery grants persist across a reset.

Response events already retain exact `usage` (or null) and available raw HTTP
bytes. Reports now expose each request's exact `usage.prompt_tokens` value or
null in `context_policy_pairing[task][policy][trial].requests`. No input_tokens
alias, tokenizer estimate, cache adjustment, or client-time inference is used.
Only nonnegative integer counts enter processing sums; unusual reported values
remain visible but do not count toward coverage. Missing/unsupported usage stays
unavailable, including unanswered request intents.

`processed_prompt_tokens[arm]` reports the observed sum as `numerator`, the
number of requests with usable counts as `coverage_count`, and all recorded
request intents as `request_count`. `total` is available only for nonempty,
complete request coverage. Failed/unfinished attempts remain in these diagnostic
counts; zero observed tokens with missing usage is not a zero total. Future
memory-layer injected context belongs in the backend's processed prompt count,
never I, R, RR, TPS or experimental eTPS. Counts remain provider-reported and
their native scope is not independently verified.

`context_policy_pairing` presents `full` and `reset-v1` lists side by side for
each task, preserving slot/arm identities, absent arms, repetitions and unfinished
slots. Each entry includes acceptance, first-attempt obligation results and
retention, I, R, RR, TPS, experimental eTPS, and processing costs. The shared
task artifact hash binds the comparison. These are trial vectors, with no
cross-task score pooling, automatic repetition matching, deltas or winner logic.
Live reports receive these additive diagnostics even for old full-history plans;
their stored evidence and request bodies are unchanged.

## Arm comparison and optional memory telemetry (2026-09-30)

The existing `context_policy_pairing` field keeps its schema and contents.
The same diagnostic reporting path now also emits
`arm_comparison[task].arms[arm_name]`: one entry for each declared arm, even when
multiple arms share reset-v1. Each entry identifies arm, context_policy and
provider, with a `trials` list retaining slot identity, lifecycle state,
result_state (null when not supplied by the scorer), accepted, first_attempt,
I, R, RR, TPS, eTPS (the existing experimental_eTPS), processed_prompt_tokens
and memory_telemetry. Repetitions are separate trial records; absent arms have
empty trial lists. Unattempted/unfinished trials retain unavailable values.
The task artifact hash binds each comparison. This is descriptive reporting,
with no score pooling, winner logic or automatic pairing of repetitions.

A live arm may declare `"memory_telemetry_field": "x_nyx_bridge"` (or another
nonempty literal top-level JSON field name). No dotted-path lookup or guessing
is performed. The setting is harness configuration and is not sent in requests.
Each probe then records `memory_telemetry` as the exact decoded object plus a
separate `memory_telemetry_status`. A valid object has string keys and flat
values that are null, strings or finite numbers. Individual null values are
preserved and do not invalidate other available fields. Boolean, nested
object/list, nonfinite number or invalid Unicode values make the entire object
invalid. Unknown keys and strings are preserved without interpretation. Raw HTTP
bytes retain original spelling; the copied object does not promise byte-identical
JSON serialization.

Statuses are valid, invalid, missing (the body lacks the declared field), and
unavailable (no journaled body). Invalid/missing/unavailable observations record
a null object. An undecodable or non-object HTTP body is invalid. Replay derives
the object and status again from the hash-checked HTTP body and rejects any
disagreement, even when journal hashes have been recomputed. The existing HTTP
envelope and answer checks still apply. With no arm declaration, no telemetry
fields are added to probe events and that arm has no memory summary.

Reports add `memory_telemetry[arm]` only for opted-in arms; the same summaries
appear per task/arm and per trial in arm_comparison. They contain request_count,
valid/invalid/missing/unavailable counts and `metrics` entries for
extraction_calls, extraction_prompt_tokens, extraction_completion_tokens,
extraction_seconds, beliefs_injected, injected_chars and facts_rejected. Each
metric reports the observed numeric `sum`, `coverage_count` and `request_count`.
Zero is covered; null and numeric-looking strings supply no numeric coverage and
are not converted. Other available fields retain independent coverage. Finite
negative values are preserved as reported diagnostics, not repaired. Fractional
sums are exact fractions in JSON exports. A zero sum with zero coverage is not
a measured zero cost.
Every dispatch intent, including pending requests and failed/unfinished trials,
stays in the request denominator. Unattempted slots create no requests.

Before the null-field fix, journals could record an entire telemetry object as
invalid because one field was null. Such journals may fail projection verification
under the current revision; use their recorded code revision for faithful replay
and preserve the original evidence. See [missing-usage coverage and provenance](../STATUS.md#missing-usage-coverage-and-provenance).

Memory telemetry is unauthenticated backend reporting under contract section 7.
It does not change acceptance, I, R, RR, TPS or experimental eTPS. Injected text
may affect the backend's processed prompt count, but never becomes new user I/R.

## Declared cache condition

A live plan may declare `"cache_policy": "warm-declared"`, the only supported
value. The report header copies this field; it applies to every arm. Absence
preserves prior behavior and adds no cache header. The user's default for
future experiment authoring is to declare warm-declared explicitly. This is
not a cache-control API: the harness neither warms nor flushes server caches.
TTFT and prefill measurements depend on server cache state and are diagnostic
only. Do not compare TTFT across arms under warm-declared, or use these timings
to infer a memory-layer speedup. Decode-v1 remains primary generation timing.

## Boundary delivery: deliver-v1

A live plan may opt in with `"boundary_delivery": "deliver-v1"`. At each
session_boundary, if any user messages were appended since the last request,
the runner sends exactly one delivery request with the current public
conversation, ending in a user message. The declaration applies to every arm,
including full, reset-v1, and memory arms. It does not add a prompt, answer key,
or new user bytes. With no pending user messages there is no delivery request.
Absent the field, request/event sequencing retains its previous behavior.

The journal stores a request intent with `kind: "delivery"` and an event with
`kind: "delivery"`, both naming the boundary node. The event retains raw reply
and HTTP bytes, usage, generation, transport detail, client latency, and the
same opted-in timing/memory telemetry as probes. Delivery replies have no answer
projection, extraction flag or classification. A status-ok reply is appended
verbatim as an assistant message; a transport failure is recorded without an
assistant append, and the trial continues. The session_boundary event then
applies the arm policy: full keeps history, reset-v1 clears it. A failed request
is still the last request for pending-message tracking; delivery is not retried.

Delivery uses the same request deadline and remaining trial-wall budget as a
probe. No request begins after the wall limit. A delivery that exhausts the
wall budget prevents further requests and ends under the existing wall-limit
policy. Interrupted requests remain durable unfinished intents, never silently
reissued. Successful HTTP delivery does not independently attest that a memory
system extracted or stored facts.

Replay checks delivery placement, completeness, exactly-one dispatch per dirty
boundary, full public request history, deadline, raw envelope, opted-in memory
and timing projections, and subsequent policy-specific history. Missing,
duplicated, moved or retyped deliveries are rejected even after journal rehashing.
Verified delivery events are excluded from the scorer's event indexing and
generation sums. They never count as probe attempts or affect classification,
routing, acceptance, retention, I, R or RR. User bytes were already counted in
their original user events. Primary TPS/eTPS uses probe generation only.

Opted-in reports add `boundary_delivery: "deliver-v1"` and
`delivery_processing[arm]`, with slot/task identities and a per-request list.
Each delivery observation carries status, full generation token/time pair and
source fields when available, raw usage, and source-labeled decode/full timing,
prompt tokens, completion tokens, TTFT/prefill and client elapsed diagnostics.
Timing interpretation uses the existing decode-v1 rules for these separate
diagnostics even when the primary plan retains legacy timing. Pending intents
remain visible with null telemetry. All-request processed-prompt and memory
summaries include delivery requests and their coverage; primary throughput does
not. No delivery processing cost is silently converted into a scoring factor.

The 2026-09-30 reset-v1 runs remain a no-memory baseline: for stateless models,
undelivered earlier facts and forgotten earlier facts are equivalent at the
next request. They do not test memory retention across a delivered session.
Memory arms require deliver-v1 so the harness first submits the facts rather
than clearing them before any request (contract section 3, harness delivery).

## Opt-in hashed request history (2026-10-02)

A live plan may declare `"request_journal": "history-sha256-v1"`. Request
intents then store `node`, `message_count`, `body_sha256`, `elapsed_seconds`,
and `deadline_seconds`; deliver-v1 delivery intents also retain `kind: "delivery"`.
The count covers the provider request body's messages, and the SHA256 hash
covers the canonical `encode(body)` bytes, including public request settings.

Request histories are reconstructed from journal events, the pinned arm
settings, and the context policy, then verified against their counts and hashes
rather than stored in each request intent. User text and response bytes,
including raw HTTP evidence, are still journaled. The actual provider request
body and scoring behavior are unchanged. The default is unchanged: omitting
the field retains the full public body in each intent. Unknown values are
rejected; manual and legacy offline v1 plans do not accept this option.

Both export versions replay hashed histories. Replay rejects inconsistent
counts, body hashes, or prior user text even after the journal chain is
recomputed. Deliver-v1 placement and kind checks still apply under both full
and reset-v1; moved or retyped delivery requests remain invalid. Hashes provide
consistency checks, not independent proof of execution or external attestation.

## Per-arm processing totals (2026-10-02)

Reports with arm comparison include `processing_totals[arm]`, aggregating
recorded answer and delivery requests across the arm's tasks and repetitions.
These are descriptive cost diagnostics, never scoring: acceptance, I, R, RR,
TPS and experimental eTPS do not change.

- `answer_and_delivery_prompt_tokens` sums usable `usage.prompt_tokens`.
- `answer_and_delivery_completion_tokens` sums usable `usage.completion_tokens`.
- `extraction_prompt_tokens`, `extraction_completion_tokens`,
  `extraction_seconds` and `facts_rejected` copy the corresponding memory
  metric summaries, summing numeric reports across answer and delivery requests.
  Extraction figures and rejected-fact counts are self-reported by the memory
  system, not independently measured. `facts_rejected` also appears in the
  existing `memory_telemetry[arm].metrics` summaries.
- `all_prompt_tokens` adds answer-and-delivery prompt tokens to extraction
  prompt tokens; `all_completion_tokens` adds the corresponding completion
  counts. Arms without a memory telemetry declaration report the four extraction
  fields as `"not_applicable"`, so their all-totals equal backend usage totals.
- `definition` labels the backend-usage and self-reported extraction sources
  and the completeness requirement.

Each answer-and-delivery summary contains the observed `numerator`,
`coverage_count`, `request_count` and `total`. Only nonnegative integer
usage values count; `total` is null unless request coverage is nonempty and
complete. Each extraction summary retains its observed `sum` and coverage
counts even when incomplete. Each all-total is null unless both its usage
component and, for memory arms, its extraction token component have complete,
nonempty coverage. Missing extraction seconds or rejected-fact counts remain
visible through their own coverage counts. Unanswered intents and failed or
unfinished requests stay in denominators; missing telemetry is never zero cost.

For two requests each reporting 100 prompt and 7 completion tokens, plus
40 extraction prompt and 9 extraction completion tokens and 1 rejected fact,
the all-totals are 280 prompt and 32 completion tokens, with 2 facts rejected.
Export replay reproduces these diagnostics from the recorded evidence.
