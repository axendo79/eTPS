Status: DRAFT, not accepted; no schema or code change.

# Run-record telemetry proposal

Codex-authored proposal, 2026-10-26, for Josh's review. Repository references
below use baseline `92e469f472fea14084754bbd4cb52f87d5dce4d7`.
This proposes descriptive hardware/runtime evidence for future run records.
It adopts no benchmark requirement, collector, backend setting or scoring rule.
No model, hardware collector, private run folder, corpus or answer key was accessed.
The profile-author/Nyx developer affiliation remains disclosed; Nyx may lose.

## Recording and availability

Propose a separately versioned telemetry sidecar beside the human run record,
identified by the exact plan SHA-256, harness revision, backend/build version,
arm, repeat, slot IDs and model-load instance. Shared configuration can be
recorded once per load instance, with each trial referencing that instance.
Observed quantities must name their measurement interval, devices, process or
whole-device scope, collector/version, sampling interval and evidence references.
Keep preparation/model loading separate from trial execution, consistent with
[MEASUREMENT_CONTRACT.md:127](../MEASUREMENT_CONTRACT.md#7-throughput-and-costs).

All field values below are **optional**. Within a future opted-in telemetry
record, propose an explicit availability entry for every listed field, so
missing evidence is visible. These entries would be documentation completeness
requirements only; their absence cannot invalidate a scored trial or remove it
from reporting. Old records stay unchanged and absent evidence stays absent.

Each field would wrap its typed value with `availability` (`available`,
`unavailable`, or `not_applicable`), `reason`, `source_refs` and capture time.
An unavailable entry looks like this; absence never means zero or disabled:

```json
{"availability":"unavailable","value":null,"reason":"not_captured","source_refs":[]}
```

Other proposed reasons include `backend_not_exposed`, `collector_unsupported`,
`permission_denied`, `incomplete_window` and `counter_reset`. A captured error may
have a source reference while the value remains null. `not_applicable` requires
affirmative evidence, such as a CPU-only execution without a PCIe accelerator;
it is not a substitute for unknown. Partial objects retain known members and
give unavailable members their own null/reason entries. Never guess from GPU
marketing specifications, CPU core counts, defaults, model sizes or TPS.

## Proposed fields

Types describe the wrapped `value`, not a change to any accepted JSON schema.
Integers exclude booleans; numeric measurements must be finite and nonnegative.
LM Studio and llama.cpp capture paths are distinguished in every row. Hardware
collectors are external to either backend. Source links describe possible
interfaces, not evidence that a particular installed build exposes them.

| Name | Type and unit | Proposed capture: LM Studio | Proposed capture: llama.cpp | Required/optional and unavailable value | Scoring effect |
|---|---|---|---|---|---|
| `peak_vram_bytes` | Array of device entries: device ID, integer bytes, scope, interval and sampling details. | External device-memory sampler, e.g. NVML on supported NVIDIA devices [N]. | Same external sampler [N]. | Optional. Null/reason if unsupported or no complete interval. Report maximum **sampled** usage, not a proven continuous peak. | None. |
| `offloaded_layer_count` | Integer layer count per target/draft model; per-device allocation only when reported. Preserve the backend's output-layer counting convention. | Capture actual resolved count from load/runtime evidence if exposed. Preserve requested `gpu`/CLI offload setting separately [L1, L2]. | Capture resolved loader count; retain requested `--gpu-layers` separately [C]. | Optional. Null/reason without resolved evidence; `auto`, `all`, a fraction or a requested maximum is not an observed count. | None. |
| `device_topology` | Object: device array (IDs, CPU/GPU model, backend runtime, role), placement and topology links; identifiers/enums, no physical unit. | Capture device assignment from runtime evidence; supplement topology with an OS/vendor inventory [L1, N]. | Capture selected devices and split settings (`--device`, `--split-mode`, `--tensor-split`, `--main-gpu`) plus OS/vendor inventory [C, N]. | Optional. Unknown devices, links or placement remain null/reason. Requested placement and observed placement stay distinct. | None. |
| `pcie_generation` | Positive integer generation per identified PCIe link; unit: generation ordinal. | External current-link query, e.g. NVML, during the declared execution interval [N]. | Same external query [N]. | Optional. Null/reason if unavailable; affirmative non-PCIe topology permits `not_applicable`. Keep current and maximum capability separate. | None. |
| `pcie_width_lanes` | Positive integer lane count per identified PCIe link; unit: lanes (`8` means x8). | External current-link-width query during execution [N]. | Same external query [N]. | Optional. Null/reason or evidenced `not_applicable`. Do not infer negotiated width from the slot or card rating. | None. |
| `cpu_thread_count` | Object of positive integer configured/resolved thread counts for generation and prompt processing where exposed; unit: threads. | Capture effective inference configuration if exposed; preserve requested `cpuThreads` separately [L3]. | Capture resolved generation/batch counts and requested `--threads`/`--threads-batch` [C]. | Optional. Unknown resolved counts are null/reason. An automatic sentinel or host logical-CPU count does not supply them. | None. |
| `kv_cache_type` | Object of exact K and V type strings and CPU/GPU placement per target/draft model; unit: backend type identifiers. | Capture effective load settings/logs; preserve `llamaKCacheQuantizationType`, `llamaVCacheQuantizationType`, `useFp16ForKVCache` and placement evidence separately [L1, L4]. | Capture resolved K/V types and placement, alongside requested `--cache-type-k`, `--cache-type-v` and KV offload settings [C]. | Optional. Null/reason for any unknown type or placement. A quantization-disabled flag alone must not be translated into an assumed precision. | None. |
| `drafter_config` | Object: enabled boolean, method string, draft model ID/hash or evidenced in-model method, backend parameters and draft resource settings; unit: identifiers, counts and declared parameter units. | Capture effective speculative settings and draft model identity; keep requested `draftModel` separately [L3]. | Capture resolved speculative method/model and parameters, alongside `--spec-type`, `--model-draft` and draft-specific settings [C]. | Optional. Null/reason when unknown. `enabled:false` requires evidence; enabled in-model methods need no invented separate draft artifact. | None. |
| `energy_joules` | Array of finite nonnegative numbers with device/component/system scope, interval, method, coverage and uncertainty; unit: joules. | External meter or supported energy counter. NVML GPU counter deltas convert mJ to J by dividing by 1000 [N]. | Same external measurement [N]. | Optional, only where measured. Null/reason for unsupported counters, reset, missing endpoints or incomplete intervals. Zero requires a valid measured zero. | None; component energy cannot become system energy or a score. |

For sampled memory, retain sample count and gaps; a device-wide measurement
includes other processes and must be labeled accordingly. Never sum per-device
peaks from different instants into a claimed simultaneous peak. For PCIe, retain
timestamped changes rather than silently choosing the fastest observed link.
For energy, preserve counter endpoints or meter samples and measurement coverage;
do not extrapolate a partial interval, substitute TDP, or fill unsupported devices
with zero. A GPU counter is component telemetry, not whole-system energy.

Telemetry must not feed I, R, RR, TPS, experimental eTPS, answer predicates,
acceptance, retention, measurement validity, branch selection, budgets or trial
eligibility. Settings can affect actual runtime behavior; recording them grants
no authorization to change them and adds no scoring multiplier. Keep failed,
unavailable and unattempted trials visible. Preserve the existing energy boundary
in [MEASUREMENT_CONTRACT.md:159](../MEASUREMENT_CONTRACT.md#9-later-controlled-experiment):
missing backend coverage prevents a system-energy-per-accepted-task claim.

## Fit with the current record, manifest and persistence

The public implementation has several distinct formats, not a single extensible
hardware run-record schema:

- The live trial record is constructed from `manifest_sha256`, events, wall time
  and stop information at [etps_v02/live_runner.py:247](../../../etps_v02/live_runner.py#L247).
  Backend `stats`/`timings` are preserved at
  [etps_v02/adapter_openai.py:62](../../../etps_v02/adapter_openai.py#L62), and replay
  checks their projection against the retained HTTP body at
  [etps_v02/live_runner.py:207](../../../etps_v02/live_runner.py#L207).
  External hardware evidence cannot be invented inside those response fields.
- Plan identities include `etps-live-plan-v1` and `etps-offline-plan-v2`; the
  exact top-level field check at
  [etps_v02/workload.py:95](../../../etps_v02/workload.py#L95) through line 123
  rejects an added telemetry key. The arm allowlist at
  [etps_v02/live_plan.py:82](../../../etps_v02/live_plan.py#L82) also excludes these
  fields. A sidecar cannot simply be inserted among imported artifacts: the
  loader rejects unreferenced artifacts at
  [etps_v02/workload.py:188](../../../etps_v02/workload.py#L188).
- Task/node `metadata` is a non-executable annotation extension at
  [etps_v02/scorer.py:82](../../../etps_v02/scorer.py#L82); the task manifest is
  hashed, including annotations, at
  [etps_v02/scorer.py:24](../../../etps_v02/scorer.py#L24).
  Putting per-run observations there would change the task identity and confuse
  frozen task content with later measurements. This proposal keeps them separate.
- SQLite currently uses `SCHEMA = 1` at
  [etps_v02/persistence.py:9](../../../etps_v02/persistence.py#L9), validates
  `user_version` at line 20, and stores exact plan/artifact bytes and journal
  payloads at [etps_v02/persistence.py:53](../../../etps_v02/persistence.py#L53).
  A human run record or separately retained sidecar is not currently admitted,
  persisted or replay-verified as hardware telemetry by this machinery.

**Versioning proposal:** this draft and a future external descriptive run-record
attachment require no change to existing plan, scorer, export or SQLite versions.
If Josh adopts a machine-readable attachment, give it its own explicit telemetry
schema version (proposed name `etps-run-telemetry-v1`) and hash its raw evidence;
binding a sidecar to a plan hash does not make it a current runner-verified
artifact or an independently attested measurement. Do not alter old frozen plans
or journals. Integrating telemetry into accepted plan fields would require a
new plan schema version and separately authorized ingestion/replay/export design.
A database version bump is needed only if that later design changes its storage
format or compatibility contract; JSON BLOB capacity alone does not decide this.
No version bump or implementation is applied here.

## Public backend references and verification limits

Reviewed public primary documentation on 2026-10-26. Actual capture paths on
Josh's installed builds are **UNVERIFIED**; no local endpoint, SDK, collector or
model was invoked. These are candidate evidence sources for later authorized
work, not claims of existing eTPS collection support.

- [L1: LM Studio load configuration](https://lmstudio.ai/docs/typescript/api-reference/llm-load-model-config)
  documents GPU and K/V configuration controls.
- [L2: LM Studio CLI load](https://lmstudio.ai/docs/cli/local-models/load)
  documents requested offload fractions/modes and memory estimates. An estimate
  is not measured peak VRAM.
- [L3: LM Studio prediction configuration](https://lmstudio.ai/docs/typescript/api-reference/llm-prediction-config-input)
  documents `cpuThreads` and `draftModel`.
- [L4: LM Studio REST load](https://lmstudio.ai/docs/developer/rest/load)
  documents `echo_load_config` and `offload_kv_cache_to_gpu`; only settings actually
  returned by the installed backend count as captured evidence.
- [C: llama.cpp server parameters](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
  documents the candidate configuration flags above. Preserve the actual build
  and resolved evidence rather than assuming today's defaults.
- [N: NVIDIA NVML device queries](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)
  documents device memory bytes, current PCIe generation/width and GPU energy
  counters in millijoules; unsupported queries remain unavailable. Other vendors
  need their own evidenced collector, not a fabricated NVML result.

## Open decisions for Josh

1. Adopt an external descriptive attachment first, or request a separately authorized runner/schema integration proposal?
2. Which optional fields should have mandatory availability declarations in an opted-in run record, without changing scoring or trial eligibility?
3. Which capture windows, sampling intervals and memory scopes should be used for comparable descriptive telemetry, including model loading and shared devices?
4. Which collectors and backend versions should be supported first, and what evidence should establish resolved offload, thread, KV and drafter settings?
5. Should energy reporting initially allow component-only measurements, and what coverage and uncertainty evidence should be required for any whole-system description?
6. What artifact retention, hashing, publication/redaction and independent review should apply before any later telemetry integration is authorized?
