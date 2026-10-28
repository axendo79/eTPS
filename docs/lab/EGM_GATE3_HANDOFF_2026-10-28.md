# EGM Gate 3 status and bounded handoff — 2026-10-28

**Status: incomplete infrastructure qualification. Gate 3 has not passed; Gate 4 is prohibited.** This is related EGM preparation on disclosed fixtures, not an eTPS held-out evaluation or a benchmark result. The eTPS authoring/custody work order and measurement contract are unchanged.

This content-free account is Codex-authored from the maintainer-authorized private session and pinned source. It reports local evidence, not independent attestation. The maintainer authorized this documentation publication; private fixture text, raw prompts, logs, runtime/model files and held-out material are excluded.

## Completed evidence

The environment-repaired package was explicitly authorized for one session. It performed one 8,192-context server/model load and 23 non-generating HTTP requests, then stopped after 37.859 seconds including cleanup at an exact-token mismatch. The owned server terminated and idleness was established. No generation, automatic retry, fallback or Gate 4 occurred.

All 151 files listed by its receipt were reverified. The first 20 counting/template checks matched exactly. Request 21 was a synthetic history-sizing witness: the frozen offline oracle expected 1,024 tokens; native tokenization returned 1,018.

The readiness owned-process shared-memory observation was exactly 86 MiB. This is within the inclusive numeric ceiling, but complete placement/attribution review and post-count observations were not reached. The compositor was approximately 824.473 MiB; observed loaded adapter headroom was approximately 968.5 MiB. These are context measurements, not deductions from owned-process counters or a guarantee of future fit.

| Retained artifact | SHA-256 |
| --- | --- |
| Environment-repaired package receipt | fd0a99253f11a0e551c1fe11075cab0fe171b55c60ee6e36fec72b70ab58cc77 |
| Incomplete session receipt | a1dc7bcbdaddf625a6159d0ff590c1979fd6df899b24c3b8239fc93fedc87de6 |
| Final private server log | 0ec24c18e129da677d11c08f3f3d88ef42e50a97846dd0da9a74f92a82eac534 |

These hashes identify privately retained artifacts; this repository does not distribute their contents.

## Concrete defect and narrow correction

At pinned llama.cpp commit 620d2225cc436ab0b001e3200e590e3b286ef9ab, the tokenizer recognizes USER_DEFINED tokens even with parse_special=false. CONTROL and UNKNOWN tokens are excluded from special pretokenization when that flag is false. The request handler passes the explicit boolean through. See [tokenizer semantics](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/src/llama-vocab.cpp#L3399-L3411) and [request handler](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/tools/server/server-context.cpp#L5730-L5740).

The offline ASCII oracle incorrectly gated CONTROL and USER_DEFINED tokens together. Cached model metadata identifies the tool-call delimiters as USER_DEFINED. Treating those delimiters as special reproduces the entire saved native sequence, not merely its length. This is an oracle/preparation finding; it does not demonstrate reasoning leakage or a model-quality failure.

The next work is limited to this required-path defect:

1. Correct token-class filtering in a new version, retaining the ASCII limitation, ordinary BPE, pinned metadata and exact-ID comparison.
2. Preserve the old failed witness as a regression. Rebuild new history padding to the original targets: two prior turns of 1,024 tokens each for the 8,192 profile, or 512 each for the 4,096 profile. Do not accept the shorter witness or change request flags to hide the defect.
3. Recompute affected serialized histories, prompts, expected IDs, request bytes and hashes. Preserve the selected summary stress input, its 1,903-token initial size and the missed 1,800 construction target.
4. Bind every copied controller/checker/allowlist layer to the same corrected oracle and new immutable bundle. Verify imported module paths/hashes; no global monkeypatch or old/new mixed dependency chain.
5. Run focused pure regressions and fake-process/transport orchestration. Retain exact mismatch refusal, owned cleanup, the environment repair, route restrictions and budgets.
6. Freeze the new installed package and present its exact command/hash/scope for a fresh execution decision. Prior authority is consumed. No automatic native retry is permitted.

Full-reserve fit remains input at most 6,080 with 2,048 generation plus 64 reserve in 8,192, or input at most 3,000 with 1,024 generation plus 64 reserve in 4,096. The changed witnesses require later native confirmation; offline success is not qualification.

## Unchanged execution boundaries

- 1,500 seconds from CLI entry; concurrency one; 80 HTTP requests; two loads only under the predeclared conditional fallback; 180 seconds per startup; bounded requests and cleanup.
- Same runtime/model and frozen launch profile. Only /health, /props, /tokenize, /apply-template and /v1/chat/completions/input_tokens; any other route is refused before sending.
- Recognized foreign inference processes stop the run. Only the single qualifying console compositor may use the inclusive 1,536 MiB cap; other foreign processes retain 512 MiB. Owned shared memory remains bounded by 86 MiB with no desktop subtraction.
- Baseline/compositor/headroom measurements are recorded context. Gate 3 placement evidence uses private verbosity-5 logs and owned counters; it makes no dynamic-paging proof.
- Logs containing disclosed EGM fixtures remain private. Debug logging is prohibited for custody-protected held-out material. No held-out text, keys or results are used in this handoff.
- An early OOM before complete native fit does not authorize the 4,096 fallback. Failed/incomplete attempts remain on record; no automatic gate passage.

Preparation stops after the narrow correction, focused checks and integrity freeze. Additional desktop, tracing or architecture work is not a prerequisite. Gate 4 retains its separate decision and evidence requirements.

## Related repository status

eTPS main c2e43bc already includes PR #35 (telemetry proposal), #36 (Spillover proposal) and #37 (temperature-zero lab work). Merging those proposals did not authorize their use during this qualification. They remain outside its scope.

Parallel Nyx and System Mechanic work produced bounded synthetic bug reproductions, unapplied patch proposals and future-work packets. Their publication does not activate a new Nyx behavior, authorize native probes or establish evaluation performance. The immediate milestone remains a qualified, reviewed Gate 3 profile before any separately authorized Gate 4.

