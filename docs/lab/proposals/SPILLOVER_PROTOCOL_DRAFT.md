Status: DRAFT, not accepted. Separate benchmark; not part of the eTPS contract. No code, schema or run is authorized by this document.

# Spillover protocol proposal

Codex-authored paper design, 2026-10-26, for Josh's review; no measurements.
Every protocol, threshold and field requirement below is a proposed option,
pending Josh's ruling, not an adopted contract. The eTPS profile author also
develops Nyx; that affiliation remains disclosed, and Nyx must be allowed to lose.

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

## 1. Proposed question and measurand

For one pinned model, quantization, backend, device, prompt and output budget,
how do prefill and decode throughput change as active weights or KV cache
move from GPU VRAM to system RAM?

Propose separate phase rates: prefill = actually evaluated prompt tokens /
backend prefill seconds; decode = generated tokens / matching backend decode
seconds. Freeze the first-token counting/boundary convention before use.
Retain native counts, durations and timing definitions; TTFT and client wall
time are separate diagnostics, not substitutes for either phase rate.

For each phase, propose `penalty_pct = 100 * (1 - rate_cell / rate_resident)`
and `delta_tps = rate_resident - rate_cell`, using a matched, positive,
measurement-valid fully GPU-resident baseline on the same device. Preserve
negative penalties. Match model/tokenizer hashes, prompt, context, KV type,
threads, drafter, backend and all settings except the declared treatment.
If that baseline cannot fit or residency is unproved, report absolute rates
and the missing baseline; no normalized spillover penalty is available.

Keep deliberate CPU layer/KV placement and driver-managed fallback in separate
series. CPU placement measures the whole configuration change, including any
changed compute placement; it cannot isolate a transfer-only cost. Driver
fallback requires direct residency/backing or migration evidence, not a setting
or slowdown alone. **ASSUMPTION:** such evidence can be obtained on a future
selected platform; support and semantics are unverified.

This proposes no quality, useful-output, eTPS, energy-efficiency, universal
hardware ranking or isolated PCIe-bandwidth claim. Ordinary host buffers or
duplicate model-file mappings alone would not establish active spillover.

## 2. Proposed independent variables

Prefer staged sweeps to a full factorial initially; freeze exact cells before
execution. Alternative: a smaller factorial if interactions are the main question.

| Variable | Candidate first-stage policy and reason |
|---|---|
| GPU/CPU layer split | Sweep resolved `offloaded_layer_count`: fully resident reference, first evidenced CPU placement and two deeper CPU-placement points. Preserve the backend's layer-count convention and requested setting separately. This targets the residency response. |
| NVIDIA sysmem fallback on/off | Separate matched on/off series with identical requested placement and workload. **ASSUMPTION:** the chosen driver/platform exposes an effective control with these semantics. Record exact setting, application scope and evidence; unsupported/unknown is unavailable, never assumed off. An enabled setting does not prove fallback occurred. |
| CPU threads | Hold one declared generation/prefill thread pair during residency sweeps; later sweep three explicit pairs at selected residency points. Counts await Josh's choice; this separates thread effects from placement effects. |
| KV placement and type | Hold exact K/V types and GPU placement in weight sweeps; separate CPU/GPU KV-placement series, holding weights and types fixed. Later compare types as a different treatment, never as a substituted baseline. Support is an **ASSUMPTION** until evidenced. |
| Speculative drafter | Hold evidenced off initially. Later matched on/off series needs its own fully resident baseline, draft artifact/method and resource record. Backend support is an **ASSUMPTION**; count target output tokens, not rejected draft proposals, in decode TPS. |
| Context length / prompt size | Propose three frozen prompt sizes, each with its own resident baseline and fixed context allocation/output budget. Within a residency contrast, hold exact prompt/token identity and context fixed. This separates prompt/KV pressure from layer placement; sizes remain open. |

No unsupported setting would be silently replaced by a different treatment.
The final manifest would distinguish requested configuration from resolved
configuration and observed placement for every cell.

## 3. Proposed controls and confounds

Record thermal state, temperature/clock traces, throttle indications and power
limits across baseline and treatment intervals; propose a common stabilization
window and rejection limits, with values left for Josh. **ASSUMPTION:** relevant
signals are exposed and adequate to diagnose throttling; absent evidence would
leave thermal comparability unverified. Record AC/battery condition, OS power
plan, ambient conditions where measured, background processes/load, driver and
OS versions, runtime libraries and exact backend/build/configuration.

Hold model-file and tokenizer SHA-256, quantization, batch/microbatch sizes,
decoding settings, output-token budget, device assignment and non-treatment
settings fixed. Retain actual prompt/output counts and hashes; equal seeds
would not be treated as evidence of equal generated token streams.

Propose warm model/file cache but fresh request KV with prompt-prefix reuse
disabled and evidenced, to measure full prefill. Loading/warmup remain outside
phase timing and visible separately. Alternative: separately declared cold-load
series; never mix warm/cold or reused/full-prefill observations. Unknown cache
state makes the affected contrast unavailable.

Propose randomized treatment order within repeat blocks, with an adjacent
resident reference and logged seed/order; counterbalanced AB/BA blocks are an
alternative. Never run all baselines first and quietly attribute drift to spill.
Retain timestamped `pcie_generation` and `pcie_width_lanes` per identified link
during each run, with sampling gaps. S1 reports tower slots as PCIe 4.0 x8;
that report is not evidence of a card's negotiated generation/width under load.
Unknown links stay unknown; a maximum-capability value cannot replace a current
link measurement (S2's proposed distinction).

## 4. Reported hardware and candidate first stage

All inventory/capacity claims in this table cite S1 section 3 Hardware; they
are reported inventory, not hardware probes. Model fit and driver support
on every listed machine are **ASSUMPTIONS**, untested here.

| Reported machine/device (S1) | Candidate scope |
|---|---|
| Legion 5i, RTX 5060 8GB | First stage: one single-GPU host; S1 calls it the main work machine. |
| 3900X tower, 2080 Ti 11GB | First stage: one tower GPU, separate hardware stratum. |
| 1080 Ti 11GB | Later tower-device stratum; grouping with the tower follows the job brief. Installed topology/availability is unverified. |
| Alienware m17 R2, RTX 2070 Max-Q 8GB | Later laptop stratum. |
| Steam Deck | Later feasibility stratum; exact variant, memory topology and backend unknown. Do not assume a distinct VRAM/system-RAM boundary or NVIDIA control. |

Recommend proposing Legion plus tower/2080 Ti first to bound scope to two hosts
and two reported capacities; this is not a performance prediction. Alternative:
Legion alone for initial method review. Propose one active target GPU per cell;
other-device workload/assignment would be recorded, with no multi-GPU pooling.
Hardware differences cannot by themselves identify a capacity or PCIe effect.

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
Keep host active-weight/KV residency or migration evidence separate from total
host allocation. Retain raw prefill/decode counts and timing boundaries, wall
limits, load/warmup costs, stop/error records, per-phase availability/eligibility,
censor reasons and hashes/references for raw artifacts. These are candidate
record requirements, not new accepted schema keys or collection support.

## 6. Proposed validity and censoring options

| Evidence/outcome | Candidate disposition, pending ruling |
|---|---|
| Matching baseline, complete phase counters/timers, evidenced intended residency and controlled conditions | Eligible only for the evidenced phase/contrast; no binary task-acceptance claim. |
| Proven throttling, clock/power drift outside predeclared limits, background interference, settings mismatch or bad timing | Retain as measurement-invalid for the affected contrast with evidence/reason. Never remove a slow run merely because it is slow. |
| Alleged spill cell shows no active spill | Label `no_spill` diagnostic, ineligible for spill-effect inference. Planned resident/negative controls remain valid controls. |
| Spill/residency, cache, link or thermal evidence absent | Mark the relevant claim unverified/unavailable; never infer spill from VRAM totals, requested offload or TPS. A missing link alone need not erase valid phase TPS. |
| OOM or timeout | Retain as censored, reason-coded, with elapsed time, partial phase observations and configuration. No completed-phase rate for an unfinished phase, zero-TPS substitution or passed label. |
| Required resident reference unavailable/invalid/censored | Absolute valid phase rates may remain; paired penalty unavailable. An oversized model cannot borrow another GPU's baseline. |

Report planned, attempted, eligible, invalid, censored, unavailable and
unattempted counts, with per-phase status and coverage. Invalidity and censoring
may coexist; preserve both reasons. Propose no automatic replacements or
retry-until-success; alternatives need a bounded, frozen replacement policy
that retains originals. No censored observation would be reported as passed.

## 7. Proposed repeats, analysis and publication minimum

Candidate: five measured repeats per cell, each paired with a nearby resident
reference, after a fixed unscored warmup policy. Alternative: three repeats for
a separately labeled feasibility study. Exact warmups, token budgets, timeout
and exclusion thresholds await Josh; no precision or power claim follows from
these counts. Freeze all slots and stopping rules in advance.

Report individual rates and paired penalties, valid pair count, median/range,
arithmetic mean, sample standard deviation and CV (`sample SD / mean`,
unavailable for fewer than two observations or zero mean). Never compute a
penalty from unrelated aggregate medians. Keep censor counts/reasons beside
available-subset summaries; no survivor-only winner claim or imputed timeout
rate. Preserve variability across repeats; disclose that repeated prompts are
not independent workloads. No pooling across hardware, backend versions,
model/quantization, cache regimes or different treatment mechanisms.

A candidate minimal publishable result would contain one bounded, evidenced
residency contrast and its matched baseline, all scheduled attempts, raw
counts/times and artifact hashes, variance/coverage, deviations and limits.
Every result would name the **contract, harness version, model config, hardware
config and scoring version** (S1 section 2), plus the timing/penalty formula
version and review/authorship provenance. Missing spill or baseline evidence
allows a feasibility/negative report, not a spillover-penalty result. This
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

## 9. Open decisions for Josh

1. Scope: separate deliberate CPU placement and proven driver fallback as proposed, or restrict the initial contract to one mechanism? What evidence establishes active spill and a fully resident baseline?
2. Hardware/backend/model: Legion plus tower/2080 Ti, or Legion alone? Which exact backend/build, model/tokenizer hashes and quantization, with a feasible same-device baseline?
3. Sweep: staged design or small factorial; which resolved layer points, fallback states and thread pairs? Which KV placement/type and drafter contrasts should be deferred?
4. Workload/timing: which three prompt/context sizes, output-token budgets, decoding settings and first-token convention? How should early termination affect phase eligibility?
5. Controls: warm fresh-KV or separate cold series; randomized blocks or counterbalanced pairs; which warmups, stabilization windows and thermal/clock/background thresholds?
6. Evidence: which collectors, sampling windows and sources can establish resolved settings, active residency/migration, thermal state and current PCIe links? Which missing evidence blocks which claim?
7. Failure policy: adopt the proposed invalid/no-spill/censored distinctions and no replacements, or specify bounded replacements? What timeouts and incomplete-pair rules?
8. Repeats/analysis: five measured pairs per cell or three for feasibility; which variance/uncertainty presentation and completeness requirements should govern publication?
9. Governance: who reviews/accepts a separately versioned Spillover contract and publication minimum? Any harness, schema, collector, shared-infrastructure work or actual run requires separate authorization.
