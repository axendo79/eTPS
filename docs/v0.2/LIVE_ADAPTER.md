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

Task manifests still use the existing user/probe/terminal schema and may opt
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
