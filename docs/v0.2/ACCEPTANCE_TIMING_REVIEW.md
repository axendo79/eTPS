# eTPS v0.2 — acceptance and timing review

Authorship/provenance: Codex authored this review and its 23 paper cases using the supplied feedback and cited documentation. Recommendations are model proposals except where an explicit user requirement or endorsement is recorded in [PROVENANCE](PROVENANCE.md). Source citations do not validate this contract or its case outcomes.

Status: proposal and analytical adversarial review, 2026-09-14. No scoring implementation or executed test results. Read alongside `MEASUREMENT_CONTRACT.md` draft 0 and `COUNTEREXAMPLES.md`. This addendum proposes refinements to contract sections 5–9; it does not silently replace their unresolved gate policy.

Input: user-supplied Reddit feedback attributed to u/Mirantisde and subsequent pasted critique. Attribution is supplied by the user, not independently authenticated. The actual draft was read for this review. Baseline remains main at ea51ce82e011c7e65bdc43e9d5af923cdcec4897.

## 1. Acceptance: proposed definitions

Use binary acceptance of a completed task, determined by a frozen, deterministic answer-key predicate over observable outputs and required actions. Graded assertion counts remain diagnostic; they never multiply eTPS or change RR. Partial correctness does not constitute task acceptance when mandatory assertions remain wrong or missing.

Distinguish three fields:

- `measurement_valid`: trace, configuration and protocol satisfy the measurement contract. A model error or timeout is a measured failure, not automatically an invalid measurement.
- `task_accepted`: all mandatory terminal assertions and required action constraints pass within the frozen task budget. The manifest may explicitly forbid particular observable intermediate actions; such violations cannot be repaired by a correct final sentence.
- `first_attempt_retention`: per-probe correctness before recovery, with assertion counts and a strict all-pass flag. Unobserved internal reasoning is not judged or inferred.

A wrong intermediate retention answer followed by permitted recovery can yield `task_accepted=true` and `first_attempt_retention_all_pass=false`. Preserve the failed assertion and recovery tokens. Such a task is recovered success, never perfect retention. A confidently incorrect terminal answer has `task_accepted=false`, even if RR=0. Confidence wording itself earns no multiplier.

This is a proposed acceptance definition for studying recovery; the draft's strict retention gate for eTPS credit remains unresolved. Do not use acceptance to quietly relax that gate. The pilot should produce enough trace data to inspect both policies without publishing a selected winner after observing results.

### Answer-key satisfaction, not identical generations

The manifest freezes required fields, allowed alternatives, units, normalization, order-insensitive sets where appropriate, ambiguity rules, and handling of additional claims. Different correct serializations may pass the same deterministic predicate. For example, an unordered set containing both competing source IDs passes regardless of order; a missing source or an unsupported resolved value fails.

An answer such as `database=Postgres; prior_database=SQLite` fails a current-database key expecting SQLite. Keywords and partial field overlap cannot establish correctness. No live model judge is used for the deterministic pilot. Arbitrary free-form semantic equivalence remains out of scope unless a future separately versioned protocol can validate it.

Deterministic checking means the same observed response receives the same verdict; it does not mean stochastic models must emit the same response. Speculative sampling may change individual samples without necessarily changing correctness. Equal distributions also do not guarantee equal observed pass rates in finite trials. Use repeated trials and report variation; never infer a regression solely from text inequality. vLLM documents both the intended losslessness and numerical qualifications. [vLLM speculative decoding](https://docs.vllm.ai/en/v0.17.0/features/speculative_decoding/)

### Retries and repeated trials

A task trial starts once and may contain frozen recovery attempts. User re-supply, regenerated answers, permitted request retries, and required verification all remain inside that trial's resource accounting. At most one accepted task is counted per trial. A repeated trial is a separately scheduled replication with the declared initial state, not a relabeling of a failed attempt.

Freeze recovery limits, timeouts, and transport-error handling before running. System-side failures remain outcomes. Harness faults use a distinct predeclared invalidation rule, retain their traces, and cannot be silently replaced. A system that fails indefinitely reaches a bounded failure outcome; it cannot leave the denominator open forever or disappear from reports.

## 2. Timing: proposed boundaries

Use one client monotonic clock for client intervals. Record backend timing separately; do not subtract timestamps from unsynchronized clocks. Each trial and request needs explicit start and end events.

| Window | Proposed boundary and scope |
|---|---|
| Trial execution | Start immediately before the first task-specific operation, including ingestion or retrieval. End when terminal delivery and all benchmark-required system work have completed, or the frozen failure/timeout boundary is reached. |
| Request latency | Immediately before dispatch at the declared system boundary through receipt of end-of-stream/completion status. Includes network and queue delays within that boundary. |
| Client TTFT | Same dispatch event through first nonempty output content received. Metadata-only events do not count. No output means unavailable, not zero. |
| Client inter-token latency | Differences between observable token-arrival timestamps only when token granularity is reliable. Chunk arrivals are labeled chunk latency, never fabricated token times. |
| Client mean TPOT | `(last_token_arrival − first_token_arrival)/(N−1)` only with a matching observed output-token count N>1. It is a client average, not backend decode time. |
| Raw generation | Backend generation-token counts and matching generation intervals, with the first-token convention declared. Cannot be recovered merely by renaming request throughput. |
| Final benchmark adjudication | Separately timed after terminal output; excluded from trial execution when it is offline benchmark scoring rather than required system behavior. |

Record last-content arrival, end-of-stream, and required-work completion separately. Ending at the first apparently correct field lets trailing errors or storage work disappear. The end event must follow the manifest's complete-output rule.

Online benchmark checks needed to select recovery branches occur inside observed multi-turn elapsed time; record their overhead separately. Do not call that overhead model generation time. A verifier deployed as part of the evaluated system always belongs to system latency and cost. An offline benchmark judge is not such a verifier. This prevents an adapter from moving work outside the window by calling it adjudication.

Record both per-turn and whole-trial intervals. The whole-trial clock is authoritative for elapsed session cost: do not replace it with summed request durations that omit gaps or double-count overlaps. The deterministic pilot should use scripted user events with a frozen delivery policy. It measures scripted recovery latency and actual re-supply tokens, not human detection, thought, or typing time. No assumed human delay is added to raw measurements.

If a later throughput experiment uses concurrency, the denominator is its common observed wall interval, not the sum of overlapping task durations. Queue policy, load generation, arrival schedule and drain rules must be frozen. Concurrent serving is outside the first sequential pilot.

### Cache and initialization boundaries

Declare distinct initial-state categories: cold, explicitly warmed, and prefix-preloaded. Record what was warmed, when, by which input, its cost, and whether task-derived data was used. Do not average these categories into one comparison. Across-trial reuse is prohibited unless the frozen profile explicitly permits it; within-session reuse is declared and preserved identically by policy across comparison arms.

Task-specific preload must appear as preparation cost even if the profile intentionally measures a warm steady state. Report measured execution and preparation separately, plus a full lifecycle total where observable. Generic model load may be excluded by a steady-state profile only with disclosure. Prefix reuse may improve TTFT and session elapsed time while leaving decode TPS unchanged; this is a useful latency improvement, not an increase in raw generation TPS. [vLLM prefix caching](https://docs.vllm.ai/en/v0.9.0/features/automatic_prefix_caching.html)

## 3. Consequences for metrics and disclosure

Keep `eTPS = TPS_raw × (1−RR)` provisional. With finite nonnegative TPS and `0≤RR≤1`, its arithmetic remains between zero and TPS. Partial-credit diagnostics cannot affect that bound because they are not formula inputs. A positive falsehood multiplier does not ensure correctness takes priority: 1,000 TPS × 0.1 still exceeds 50 TPS × 1. A zero multiplier is effectively a gate.

Candidate companion for a frozen sequential task set: `accepted_task_rate = accepted trial count / total trial execution seconds`, retaining failed-trial time. This is tasks per second, not tokens per second, and not a renamed eTPS. It measures success under a declared recovery policy; it does not guarantee that a flaky but very fast system ranks below every slower reliable system. Always report acceptance fraction and first-attempt retention beside it. Any minimum reliability or latency requirement must be frozen independently before scoring.

DistServe provides a useful precedent for performance subject to explicit latency requirements. Its serving goodput under TTFT/TPOT constraints does not establish semantic correctness. An eTPS companion needs its own task acceptance rules and must not claim direct numerical comparability with DistServe. [DistServe](https://arxiv.org/abs/2401.09670)

Energy per accepted task, if measured, is total energy for all attempted trials in the declared evaluation interval divided by accepted task count. Recovery and failed-attempt energy stay in the numerator. With zero accepted tasks report the ratio as unavailable (no accepted denominator), alongside total joules and zero successes. Missing energy from any trial prevents a complete-set energy claim; do not compute a convenient subset without disclosing it.

Use separately named boundary categories, including whole-system wall, GPU rail, and partial distributed-system measurement. Whole-system measured wall energy is the preferred local-system series; GPU-only energy is secondary. MLPerf uses whole-system measured AC power for its power results. [MLCommons](https://mlcommons.org/benchmarks/inference-edge/)

Wall measurement is not immune to offloading: a remote verifier, retrieval service, or API backend can move work beyond the measured machine. Declare all participating resources and unmeasured components. Do not claim complete energy efficiency for Gemini API experiments using only client-machine power. Record meter, sampling/integration method, coverage, baseline policy, uncertainty and matching time boundaries. Never mix boundary categories in one comparison series or substitute rated power for measurement.

The 9B/0.5 TPS observation remains an unverified diagnostic hypothesis. Require model revision, quantization format/bit width, backend/version, decoding settings, context limit, actual prompt and KV occupancy, explicit layer/device placement where available, resident memory per device, offload configuration, cache state, concurrency, and phase timings. Power/thermal/utilization observations help investigate causes. Do not infer PCIe bottlenecks from TPS alone. This record enables reproducibility assessment; it does not guarantee reproduction when hardware or provider details are inaccessible. Managed API fields must say unavailable with a reason rather than inventing values.

## 4. Additional adversarial cases and expected outcomes

These are paper fixtures for the next corpus, not executable tests or newly approved scoring rules.

| ID | Counterexample | Expected result under the proposal |
|---|---|---|
| A01 | Two differently serialized answers satisfy the same key | Both accepted; text inequality is irrelevant. |
| A02 | Correct keyword occurs within a false proposition | Assertion fails; no partial keyword credit. |
| A03 | Two of three mandatory final assertions pass | Task unaccepted; 2/3 is a diagnostic only. |
| A04 | Wrong retention answer, one permitted re-supply, then correct completion | Accepted recovered task, failed first-attempt retention, R>0 for active recovery spans; draft strict eTPS gate still fails. |
| A05 | Confident wrong terminal answer with R=0 | Unaccepted; RR alone cannot confer efficiency credit. |
| A06 | Correct final answer after a manifest-forbidden external action | Unaccepted despite correct text; trace records violation. |
| A07 | Three internal attempts cost 2 s and 10 J each; third succeeds | One accepted task, 6 s and 30 J, not one 2 s/10 J trial. |
| A08 | A completed 4 s/20 J trial fails; next 6 s/30 J trial succeeds | 1/2 acceptance, 0.1 accepted tasks/s, 50 J/accepted task for this sequential set. |
| A09 | Every trial fails | Accepted task rate 0 for positive measured duration; energy ratio unavailable; all time/energy retained. |
| A10 | A positive falsehood factor is applied to arbitrarily high TPS | Crossover remains possible; proposed multiplier does not establish correctness priority. |
| T01 | 5 s queue wait followed by 1 s response | Client request interval is 6 s; raw generation interval is separately measured. |
| T02 | Correct-looking last content at 1 s, end-of-stream at 2 s, required write completes at 3 s | Preserve all three times; trial cannot terminate at 1 s. |
| T03 | Offline final check takes an additional 0.4 s | Report separately; not backend generation or system execution. |
| T04 | System uses a verifier taking 0.4 s before delivering its answer | Include in execution and energy; cannot relabel it offline judging. |
| T05 | Prefix warming takes 8 s before a 2 s measured run | Report warm execution 2 s and preparation 8 s; cannot present this as a cold 2 s result. |
| T06 | Two output tokens arrive in one buffered chunk | Chunk timing available; individual inter-token latency unavailable. |
| T07 | Only one output token arrives | Mean TPOT unavailable; TTFT and completion latency remain reportable. |
| T08 | Two requests take 1 s each with a 2 s inter-turn gap | Session elapsed is 4 s, not 2 s; record the gap source. |
| E01 | Retrieval is moved from local GPU to unmetered remote host | GPU/wall reading remains partial; cannot claim complete-system energy reduction. |
| D01 | Same 0.5 TPS with unknown device placement and context occupancy | Insufficient diagnostic disclosure; no asserted bottleneck. |

## 5. Decision boundary before implementation

Recommended next contract revision: adopt binary terminal acceptance plus separate first-attempt retention; explicit retry identity; deterministic answer-key predicates; separate client/backend timing; declared cache categories; and explicit energy/disclosure boundaries. These are recommendations pending contract consolidation, not authorization to publish scores.

Still unresolved: which gate governs experimental eTPS credit; whether the candidate formula adds useful information beyond its components; voluntary recap semantics; frozen tokenizer choice; canonical governance; and the concrete pilot budgets and accepted-answer schema. The next step is to consolidate the chosen rules into a versioned draft and hand-replay the fixtures, then freeze the deterministic corpus. No scorer, routing, engine optimization, infrastructure, commit or push in this step.
