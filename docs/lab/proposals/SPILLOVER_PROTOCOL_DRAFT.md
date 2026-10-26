Status: DRAFT, not accepted. Separate benchmark; not part of the eTPS contract. No code, schema or run is authorized by this document.

Revision 1: recommended pilot choices incorporated; not accepted.

# Spillover protocol proposal

Codex-authored paper design, 2026-10-26, for Josh's review; no measurements.
Every protocol, threshold and field requirement below is a proposed option,
pending Josh's ruling, not an adopted contract. The eTPS profile author also
develops Nyx; that affiliation remains disclosed, and Nyx must be allowed to lose.
Revision 1 incorporates the reviewer recommendations supplied by Josh on
2026-10-26. Recommendations are concrete pilot choices for review, not acceptance
or permission to implement or execute them. Earlier alternatives remain below.

Sources used in this draft:

- **S1:** `D:\eTPSDotty\00-STATE.md`, sections 1, 2 (TVD measurement lab),
  3 (Hardware) and 5 item 6; read 2026-10-26. Hardware entries are local
  owner/agent reports [J/R], not independently verified specifications.
- **S2:** `D:\eTPS-wt-followups-2026-10-26\docs\v0.2\proposals\RUN_RECORD_TELEMETRY_DRAFT.md`,
  draft dated 2026-10-26; field names and availability conventions only.
  It authorizes no collector and establishes no installed-backend capability.
- **S3:** eTPS [measurement contract](../../v0.2/MEASUREMENT_CONTRACT.md),
  [status](../../STATUS.md) and [provenance](../../v0.2/PROVENANCE.md) at base
  `92e469f472fea14084754bbd4cb52f87d5dce4d7`; boundaries, not Spillover rules.
- **S4:** [Google's Gemma memory guidance](https://ai.google.dev/gemma/docs/core),
  memory requirements and planning considerations; reviewed read-only 2026-10-26.
  Effective parameter count does not establish the local artifact's footprint.
- **S5:** [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md),
  timing and prompt-cache descriptions; reviewed read-only 2026-10-26.
  This moving upstream reference is not the still-unselected pilot build.

## 1. Proposed question and measurand

For one pinned model, quantization, backend, device, prompt and output budget,
how do prefill and decode throughput change with deliberate CPU weight
placement relative to a verified fully GPU-resident condition? Describe the
first result as a **placement penalty**, including changed compute placement,
not an isolated transfer cost or evidence of driver-managed spillover.

Propose separate phase rates: prefill = actually evaluated prompt tokens /
backend prefill seconds; decode = generated tokens / matching backend decode
seconds. Verify and freeze the first-token counting/boundary convention against
the pinned backend before use. S5 documents `timings.prompt_n`, `prompt_ms`,
`predicted_n` and `predicted_ms`; their exact count/interval mapping on the
selected build remains **ASSUMPTION** until checked.
Retain native counts, durations and timing definitions; TTFT and client wall
time are separate diagnostics, not substitutes for either phase rate.

For each phase, propose `penalty_pct = 100 * (1 - rate_cell / rate_resident)`
and `delta_tps = rate_resident - rate_cell`, using a matched, positive,
measurement-valid fully GPU-resident baseline on the same device. Preserve
negative penalties. Match model/tokenizer hashes, prompt, context, KV type,
threads, drafter, backend and all settings except the declared treatment.
If that baseline cannot fit or residency is unproved, report absolute rates
and the missing baseline; no normalized placement or spillover penalty is available.

Start with deliberate CPU weight placement only. Defer KV-placement and
driver-managed fallback series; fallback would require actual backing or
migration evidence, not a setting or slowdown alone. **ASSUMPTION:** such
evidence can be obtained on a future selected platform; support and semantics
are unverified. Host buffers or duplicate model-file mappings alone would
not establish the active placement or spillover being claimed.

This proposes no quality, useful-output, eTPS, energy-efficiency, universal
hardware ranking or isolated PCIe-bandwidth claim.

## 2. Proposed independent variables

Use one placement sweep across three prompt sizes; concurrency is one. Freeze
the exact resolved settings before execution. All other sweeps are deferred.

| Variable | Recommended first-pilot policy and reason |
|---|---|
| GPU/CPU layer split | Four placements: resident, smallest supported CPU-layer step, approximately 25% CPU layers and approximately 50%. Freeze exact resolved counts, preserving the backend's layer-count convention and requested settings separately. This targets the placement response. |
| NVIDIA sysmem fallback on/off | No fallback sweep; preserve the observed setting/evidence and do not attribute placement results to fallback. **ASSUMPTION:** a chosen driver exposes a control with these semantics; unsupported/unknown remains unavailable, not assumed off. |
| CPU threads | Hold one explicit generation/prefill thread pair across every placement and prompt; its values remain open. This separates thread effects from placement effects. |
| KV placement and type | Hold exact K/V types and GPU placement fixed, with batch/microbatch sizes fixed. Resolved support and placement are **ASSUMPTIONS** until evidenced; no KV sweep in this pilot. |
| Speculative drafter | Hold evidenced off; no drafter sweep. Count target output tokens in decode TPS. |
| Context length / prompt size | Three invented synthetic prompts targeting 512, 2,048 and 5,120 input tokens after formatting; allocate 8,192 context tokens. Each prompt has its own matched resident baseline and fixed bytes/token identity. Target 256 generated tokens, temperature zero and a fixed seed; exact prompt hashes and seed remain to be frozen. |

No unsupported setting would be silently replaced by a different treatment.
The final manifest would distinguish requested configuration from resolved
configuration and observed placement for every cell.

## 3. Proposed controls and confounds

Fix power and cooling conditions; record thermal state, temperature/clock traces,
throttle indications and power limits across baseline and treatment intervals.
Retain treatment-induced throttling as a reported outcome, not an automatic
exclusion. External environmental deviations and instrumentation faults remain
distinct, with any comparability limits declared before execution.
**ASSUMPTION:** relevant signals are exposed and adequate to diagnose throttling;
absent evidence leaves thermal comparability unverified. Record AC/battery
condition, OS power plan, ambient conditions where measured, background
processes/load, driver and OS versions, runtime libraries and exact
backend/build/configuration.

Hold model-file and tokenizer SHA-256, quantization, batch/microbatch sizes,
decoding settings, output-token budget, device assignment and non-treatment
settings fixed. Retain actual prompt/output counts and hashes; equal seeds
would not be treated as evidence of equal generated token streams.

Use warm model/file caches, fresh request KV and evidenced zero prompt-prefix
reuse to measure full prefill. Perform one declared untimed warmup after each
load; loading/warmup remain outside phase timing and visible separately.
S5 documents `/completion`'s `cache_prompt` control and chat timing's `cache_n`
reused-token count. The selected endpoint/build's controls and evidence mapping
remain to be verified; a requested flag alone does not establish zero reuse.
Unknown cache state makes the affected full-prefill contrast unavailable.

Counterbalance resident/treatment pairs as AB/BA, retaining the actual order.
Schedule exclusive GPU time only after the current LM Studio work finishes;
this draft grants no access to that live job. Retain all scheduled attempts.
Retain timestamped `pcie_generation` and `pcie_width_lanes` per identified link
during each run, with sampling gaps. S1 reports tower slots as PCIe 4.0 x8;
that report is not evidence of a card's negotiated generation/width under load.
Unknown links stay unknown; a maximum-capability value cannot replace a current
link measurement (S2's proposed distinction).

## 4. Reported hardware and recommended first stage

All inventory/capacity claims in this table cite S1 section 3 Hardware; they
are reported inventory, not hardware probes. Model fit and driver support
on every listed machine are **ASSUMPTIONS**, untested here.

| Reported machine/device (S1) | Candidate scope |
|---|---|
| Legion 5i, RTX 5060 8GB | First pilot alone; S1 calls it the main work machine. |
| 3900X tower, 2080 Ti 11GB | Later separate replication, not pooled with the Legion. |
| 1080 Ti 11GB | Later tower-device stratum; grouping with the tower follows the job brief. Installed topology/availability is unverified. |
| Alienware m17 R2, RTX 2070 Max-Q 8GB | Later laptop stratum. |
| Steam Deck | Later feasibility stratum; exact variant, memory topology and backend unknown. Do not assume a distinct VRAM/system-RAM boundary or NVIDIA control. |

Use the Legion alone to bound the first method review; this is not a performance
prediction. Prefer a pinned llama.cpp CUDA build with native phase counters.
Try the existing Gemma 4 E4B artifact named in the reviewer recommendation,
conditional on weights, KV cache and working buffers fitting the resident
condition. **ASSUMPTION:** that local artifact is compatible and can fit; neither
its quantization nor memory footprint was inspected or measured here. Its
effective parameter count is not a memory-footprint measurement (S4).
Record the exact build, quantization and model/tokenizer artifact hashes before
execution. Use one target GPU and concurrency one; record other-device workload
and assignment. Hardware differences cannot identify a capacity or PCIe effect.

## 5. Proposed run record

Reuse S2's names without adopting its proposed eTPS sidecar schema. For every
telemetry field, propose `availability` (`available`, `unavailable`,
`not_applicable`), `value`, `reason`, `source_refs` and capture time. Absent
evidence means `value:null`, with a reason such as `not_captured` or
`backend_not_exposed`; absence never means zero, false or disabled.
`not_applicable` needs affirmative evidence. Partial objects preserve known
members and unavailable-member reasons.

| S2 field name | Proposed Spillover content |
|---|---|
| `peak_vram_bytes` | Per-device maximum sampled bytes, process/device scope, phase/window, sample count and gaps; not a proven continuous peak. |
| `offloaded_layer_count` | Resolved target/draft counts and counting convention, alongside requested counts and evidence of active CPU/GPU placement. |
| `device_topology` | Identified CPU/GPU/RAM, roles, placement, links and single/multi-device configuration; unknown placement remains unknown. |
| `pcie_generation` | Timestamped current generation per link; capability recorded separately. |
| `pcie_width_lanes` | Timestamped current lane count per link; S1's x8 report is not a measurement. |
| `cpu_thread_count` | Requested and resolved generation/prompt-processing counts, not host core count. |
| `kv_cache_type` | Exact K/V types and observed CPU/GPU placement for target/draft. |
| `drafter_config` | Evidenced enabled state, method, artifact/hash where applicable, parameters and resource configuration. |
| `energy_joules` | Optional measured energy with scope, interval, method and coverage; absent if unmeasured, never estimated from power ratings. |

Also propose a run envelope identifying contract/draft revision, harness and
analysis/scoring versions, exact manifest SHA-256, cell/repeat/slot IDs,
baseline pairing, load instance, timestamps, order/seed and cache policy.
Retain model/tokenizer/prompt/output hashes, quantization, backend/build/driver/OS,
hardware/RAM configuration, fallback setting evidence, all fixed/swept settings,
thermal/power/background evidence and collectors' versions/sampling windows.
Preserve backend allocation/configuration logs and per-request phase counters.
Target one-second CPU/GPU/RAM/thermal sampling, retaining actual timestamps and
gaps; collector support is an **ASSUMPTION** until evidenced. Report maxima as
sampled peaks, not proven continuous peaks. Retain zero-prefix-reuse evidence.
Keep host active-weight/KV residency or migration evidence separate from total
host allocation. Retain raw prefill/decode counts and timing boundaries, wall
limits, load/warmup costs, stop/error records, per-phase availability/eligibility,
censor reasons and hashes/references for raw artifacts. These are candidate
record requirements, not new accepted schema keys or collection support.

## 6. Proposed validity and censoring options

| Evidence/outcome | Candidate disposition, pending ruling |
|---|---|
| Matching baseline, complete phase counters/timers, evidenced intended CPU/resident placement and controlled conditions | Eligible for the evidenced placement contrast; no driver-spill or binary task-acceptance claim. |
| Instrumentation fault, settings mismatch, bad timing or evidenced external environmental/background deviation | Retain with reason/evidence; invalidate only the affected measurement/contrast under declared rules. Keep faults distinct from workload outcomes. |
| Treatment-induced throttling or clock/power response | Report as an outcome alongside available phase rates and placement penalties, with thermal evidence; no automatic exclusion for the treatment's effect. Never remove a run merely because it is slow. |
| Alleged CPU-placement cell shows no active CPU weight placement | Label `no_spill`/no intended placement as a diagnostic, ineligible for that treatment inference. Planned resident/negative controls remain valid controls. |
| Placement/residency evidence absent | No evidenced placement/spillover claim; do not infer it from VRAM totals, requested offload or TPS. Available absolute phase rates may remain. |
| Cache, link or thermal evidence absent | Mark the affected claim unverified/unavailable. Missing PCIe evidence blocks link-specific explanations without necessarily invalidating throughput; unknown prefix reuse blocks full-prefill comparison. |
| OOM or timeout | Retain as censored, reason-coded, with elapsed time, partial phase observations and configuration. No completed-phase rate for an unfinished phase, zero-TPS substitution or passed label. |
| Required resident reference unavailable/invalid/censored | Absolute valid phase rates may remain; paired penalty unavailable. An oversized model cannot borrow another GPU's baseline. |

Report planned, attempted, eligible, invalid, censored, unavailable and
unattempted counts, with per-phase status and coverage. Invalidity and censoring
may coexist; preserve both reasons. Keep every attempt; no automatic replacements
or retry-until-success. Propose a **10-minute request ceiling**, pending Josh's
confirmation. After timeout, confirm cancellation and backend idleness before
proceeding; cancellation evidence/support remains **ASSUMPTION** until checked
on the selected build. No censored observation would be reported as passed.

## 7. Proposed repeats, analysis and publication minimum

After an instrumentation smoke test, use **five measured pairs per
treatment/prompt combination**, each treatment paired with its matched resident
reference in the AB/BA schedule. This is separate from the one untimed warmup
after each load. Label results exploratory: repeated runs of three prompts
establish neither broad workload coverage nor precise uncertainty. Freeze
slots and stopping rules in advance. The smoke test requires separate future
authorization; it was not performed by this documentation revision.

Report individual rates and paired penalties, valid pair count, median/range,
arithmetic mean, sample standard deviation and CV (`sample SD / mean`,
unavailable for fewer than two observations or zero mean). Never compute a
penalty from unrelated aggregate medians. Keep censor counts/reasons beside
available-subset summaries; no survivor-only winner claim or imputed timeout
rate. Preserve variability across repeats; disclose that repeated prompts are
not independent workloads. No pooling across hardware, backend versions,
model/quantization, cache regimes or different treatment mechanisms.

A candidate minimal publishable result would contain one bounded, evidenced
CPU-placement contrast and its matched resident baseline, all scheduled attempts, raw
counts/times and artifact hashes, variance/coverage, deviations and limits.
Every result would name the **contract, harness version, model config, hardware
config and scoring version** (S1 section 2), plus the timing/penalty formula
version and review/authorship provenance. Missing placement or baseline evidence
allows absolute rates/feasibility reporting, not a placement-penalty result. This
paper design and passing software checks supply none of that empirical evidence.

## 8. Relationship to eTPS and a future lab

Spillover would own its residency definitions, phase timing, eligibility,
censoring, budgets and penalty analysis. eTPS's public definition and current
contracts remain unchanged: TPS and input-based RR are primary; experimental
eTPS, binary terminal acceptance and first-attempt retention stay separate (S3).
Spillover proposes no RR reconstruction task or eTPS scoring multiplier.

Potential later common parts are run manifests, model adapters, telemetry
availability wrappers and artifact hashes (S1 section 2). A future harness
would need evidenced placement, phase counters/timing, configuration identity
and an all-attempt ledger. No infrastructure extraction is proposed for action
until a second benchmark demonstrates actual reuse. Sharing names or adapters
would not share scoring/validity rules or authorize changing an eTPS plan,
SQLite schema, scorer or frozen run.
Josh would accept a separately versioned Spillover contract after technical
review, then separately authorize implementation with fake-server tests and,
later, live execution. eTPS scoring, protected runs and shared-infrastructure
extraction remain outside this pilot. None of those stages is authorized here.

## 9. Recommended first pilot

These nine reviewer recommendations are incorporated for review, not accepted.

1. **Scope/proof:** deliberate CPU weight placement; report its placement penalty, including changed compute placement. Defer driver fallback; publish absolute rates only without a verified resident baseline.
2. **Hardware/backend/model:** Legion alone; tower later as a separate replication. Prefer a pinned llama.cpp CUDA build with native phase counters and the existing Gemma 4 E4B artifact only if weights, KV and buffers fit. Pin build, quantization and hashes; effective parameter count proves no footprint.
3. **Sweep:** resident, smallest supported CPU-layer step, approximately 25% CPU layers and approximately 50%; freeze resolved counts. Hold one explicit thread pair, KV types/placement, batch sizes and drafter-off fixed; concurrency one. Defer other sweeps.
4. **Workload/timing:** invented prompts targeting 512/2,048/5,120 tokens after formatting, 8,192-token context, target 256 generated tokens, temperature zero and fixed seed. Verify the pinned first-token boundary, retain matching native counts/timers and keep TTFT separate.
5. **Cache/environment:** warm model/file caches, fresh request KV, evidenced zero prefix reuse, one untimed warmup per load and AB/BA resident/treatment pairs. Fix power/cooling; schedule exclusive GPU time after current LM Studio work finishes.
6. **Evidence:** backend allocation/configuration logs and per-request phase counters; target one-second CPU/GPU/RAM/thermal sampling with timestamps/gaps and sampled peaks. Missing residency evidence blocks the placement/spill claim; missing PCIe evidence blocks link explanations, not necessarily throughput.
7. **Failures:** retain every attempt, no automatic replacements; propose a 10-minute ceiling. Confirm cancellation/idleness after timeout. Separate instrumentation faults from workload outcomes, retaining treatment-induced throttling as an outcome.
8. **Repeats/publication:** instrumentation smoke test, then five measured pairs per treatment/prompt combination; every observation, paired penalties, median/range, mean, sample SD/CV and failure counts. Exploratory results only; three prompts provide limited coverage and uncertainty evidence.
9. **Governance:** Josh accepts a separate versioned contract after technical review, then separately authorizes fake-server-tested implementation and live execution. eTPS scoring, protected runs and infrastructure extraction stay outside the pilot.

## 10. Deferred / alternatives

- **Mechanisms/sweeps:** driver fallback on/off only with actual backing/migration
  evidence; separate CPU/GPU KV-placement and KV-type series, three explicit
  thread-pair sweeps at selected placements, and drafter on/off with its own
  resident baseline, artifact/method and resource record. Preserve target-output
  counting rather than rejected draft proposals. Support remains **ASSUMPTION**.
- **Design:** staged expansion, a smaller factorial for interactions or a full
  factorial are alternatives to the initial placement-only sweep. The original
  unsized first-CPU/two-deeper points are superseded for the recommended pilot
  by the four specified placements, not retroactively removed from history.
- **Hardware:** the original Legion-plus-tower first stage is deferred to separate
  tower replication; 1080 Ti, Alienware and Steam Deck strata and any multi-GPU
  design remain later possibilities, never pooled into this pilot.
- **Cache/order/environment:** separately declared cold-load runs and randomized
  blocks with logged seeds remain alternatives to warm/fresh-KV AB/BA pairs.
  Do not mix cache regimes. Earlier stabilization/exclusion-limit proposals
  require review and must not automatically exclude treatment-induced throttling.
- **Repeats/failures:** three-repeat feasibility reporting and a bounded,
  predeclared replacement policy retaining all originals remain alternatives,
  not the recommended five-pair/no-replacement pilot. General protocol and
  publication acceptance remain Josh's responsibility, not inferred from checks.

## 11. Still open for Josh

1. Exact CUDA build, artifact/quantization and hashes; evidence that all resident weights, KV and working buffers fit.
2. Exact resolved layer counts, thread pair, K/V types/placement, batch sizes, seed, formatted prompt identities/counts and AB/BA schedule.
3. Pinned-build first-token/cache/residency evidence mapping, collectors and capture gaps, and fixed power/cooling/comparability details.
4. Confirmation of the proposed 10-minute ceiling, cancellation/idleness evidence and handling of early output termination or incomplete pairs.
5. Technical review and acceptance of the separate contract, followed by distinct implementation and live-run authorizations/exclusive GPU scheduling.
