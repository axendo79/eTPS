# eTPS live bridge-error retention: source-only review

The current live path retains an ordinary bridge HTTP 502 response and its
failed attempt. **The bounded gap is projected cost coverage:** if an opted-in
`x_nyx_bridge` object contains a nested `ingestions` list or a boolean such as
`memory_complete`, the entire memory projection is invalid. Numeric extraction
costs remain recoverable from raw HTTP evidence, but are absent from summaries.
Incomplete combined cost totals remain **null**, so this is not evidence that
Nyx gets a zero-cost failure or a favorable score.

Reviewed only Python source under `etps_v02/` at the source pins below.
This retention trace is static control/data-flow evidence. The projection branch
is checked separately by the [six-case synthetic proof](proof-results.json).
No repository modules were imported, corpora/logs/stores opened, or production
files changed. Bridge proposals remain unapplied. This is not a live-run result
or a claim about a saved trial.

## Retention trace

- The adapter catches `HTTPError` as a response, retains its bounded body, then
  stores HTTP status, body base64 and SHA-256. A non-2xx envelope maps to the
  existing `timeout` outcome with `transport_detail=http_status`; it does not
  erase the raw error body. See [adapter_openai.py:90](../../../etps_v02/adapter_openai.py#L90),
  [adapter_openai.py:189](../../../etps_v02/adapter_openai.py#L189),
  and [adapter_openai.py:36](../../../etps_v02/adapter_openai.py#L36).
- The runner commits a request intent before dispatch and appends the whole
  returned response as a probe/delivery event, including optional memory
  projection. Replay verifies the raw body hash, envelope projection and memory
  projection. See [live_runner.py:21](../../../etps_v02/live_runner.py#L21),
  [live_runner.py:207](../../../etps_v02/live_runner.py#L207),
  and [live_runner.py:227](../../../etps_v02/live_runner.py#L227).
- There is one transport dispatch and no automatic retry. Any subsequent
  dispatched probe follows the manifest's existing route and gets another
  request/event pair. The journal is append-only, hash-chained, and refuses a
  second start for an attempted slot. See [adapter_openai.py:152](../../../etps_v02/adapter_openai.py#L152),
  [live_runner.py:98](../../../etps_v02/live_runner.py#L98),
  [persistence.py:73](../../../etps_v02/persistence.py#L73),
  and [persistence.py:130](../../../etps_v02/persistence.py#L130).
- Each probe increments attempts; `first.setdefault` preserves its first
  outcome across later recovery. Reports retain every planned slot, failed
  terminal outcomes, running/aborted prefixes, and unavailable counts. See
  [scorer.py:523](../../../etps_v02/scorer.py#L523),
  [scorer.py:596](../../../etps_v02/scorer.py#L596),
  [runner.py:342](../../../etps_v02/runner.py#L342),
  and [live_runner.py:263](../../../etps_v02/live_runner.py#L263).

## Concrete projection gap and safe next task

`memory_telemetry.project` requires every value to be null, an exact string, or
an exact integer/finite float. Lists, dictionaries and booleans reject the
whole object ([memory_telemetry.py:12](../../../etps_v02/memory_telemetry.py#L12),
[memory_telemetry.py:27](../../../etps_v02/memory_telemetry.py#L27)).
Thus the source-derived input `{"x_nyx_bridge":{"extraction_calls":1,
"extraction_prompt_tokens":8,"ingestions":[]}}` yields an invalid projection,
while its complete JSON remains in `http_body_base64`. The
[source-extracted proof](prove_composite_projection.py) exercises this branch
with synthetic success/error response records.

Only valid observations enter metric sums; invalid/unavailable counts and all
request denominators remain explicit. Combined processing totals require full
coverage and become null otherwise. See [memory_telemetry.py:36](../../../etps_v02/memory_telemetry.py#L36),
[memory_telemetry.py:52](../../../etps_v02/memory_telemetry.py#L52),
[session_profile.py:37](../../../etps_v02/session_profile.py#L37),
and [session_profile.py:95](../../../etps_v02/session_profile.py#L95).

Next bounded task: establish an explicit compatible bridge-v2 telemetry
projection contract, then prepare synthetic regressions for nested receipts,
boolean status, known failed-request extraction usage, null unknown usage,
and cached retry zero NEW extraction. Preserve raw bytes, per-attempt identity,
coverage denominators, old flat-object semantics and replay determinism. Do not
silently broaden the current projector or infer unknown usage. A paired
failure/retry regression must show both events and the original first-attempt
failure, even if the later request succeeds. No implementation is proposed here.

## Explicit boundaries

Credential-echo bodies are withheld while their hash/status remain; oversized
responses and transport/deadline failures may lack a body. The daemon can
outlive the deadline and cannot journal a late result; cancellation is not
claimed ([adapter_openai.py:98](../../../etps_v02/adapter_openai.py#L98),
[adapter_openai.py:152](../../../etps_v02/adapter_openai.py#L152)).
A crash/storage failure before response append leaves the committed request
prefix, not guaranteed complete response evidence. These boundaries must stay
visible; unknown usage is not zero. The prototype's author/system affiliation
must remain disclosed, and failed/unavailable Nyx trials must stay in reports.

## Source pins (SHA-256)

| File | SHA-256 |
| --- | --- |
| adapter_openai.py | 2d97a6965aad1ee9b902720009f67c7707038e96f988d0152acbd8e254cdf6ff |
| live_runner.py | 168294d7f0dfa25a5bc7ab113df4909419ae079a1b2525a7cd4ea753ba65d835 |
| memory_telemetry.py | b6fe8cd739c0d921b1ec5fba6d1a2b7a42f63dede2dfe6ab071cb73925316870 |
| persistence.py | 59afb60a48e18b6070e187fe8b59d79786554bf789a2af0fdd3cb69b6a820e8a |
| runner.py | b10a5e14a636b2a080084d270780f63154c3b129a68cdb6edf952da143aa82f7 |
| scorer.py | 299e74d020fb5b894b19781fd8c05ada5409d3c3cda884dd7ae02e1a8396f07a |
| live_plan.py | d71f6ae016f6b01937d972a5a16152c8482931b79f927022b41c680d920a4d69 |
| session_profile.py | 6436fb75ea64ddee7ca2191e0275fdd4f9eb72cd90ca60bdf3dd3af440c89864 |
