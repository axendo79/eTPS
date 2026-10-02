# Codex work order: nyx-bridge control arms D and E (two-stage)

**Provenance.** Written by Claude (a model) on 2026-10-02 as a labelled model-authored proposal. It implements the user-approved four-arm plan and fairness rules ("Nyx must be allowed to lose"). Claude has **not** seen the nyx-bridge code. Everything here comes from Codex's read-only report on `D:\nyx-bridge` at `e7fdcce`, which named these files:
- `nyx_bridge/server.py`: extraction, injection, `x_nyx_bridge` telemetry, `facts_rejected`;
- `nyx_bridge/memory.py`: `Memory`, deduplication, current-belief retrieval;
- `nyx_bridge/run_slot.py`: a fresh subprocess and store per slot, with `NYX_BRIDGE_MODEL`.

**Disclosed conflict.** The Nyx author also owns this control. The control must be a fair effort, and that review happens in Stage 1.

## Goal

Add two memory modes to the bridge alongside the existing Nyx mode. They must differ from Nyx **only in what the memory keeps**.

| Mode | Store | Extraction | Injected each request |
|---|---|---|---|
| `nyx` (existing, arm C) | Nyx belief store | existing | all current beliefs, as today |
| `naive` (arm D) | append-only list of extracted facts in arrival order: no dedup, no supersession, no contradiction or time handling | **the same function, prompt, settings and validation as `nyx`**, called at the same trigger points | **all** stored facts, chronological, using the **same serializer, role and position** as `nyx` |
| `recall` (arm E) | each unseen user message, verbatim, in arrival order | none: zero extraction calls | **all** stored messages, chronological, same serializer, role and position |

**Fixed rules** (decided by the user; do not change them):
- No injection cap in any mode, because Nyx has none.
- One fresh process and one fresh store per slot in every mode, using the existing `run_slot` lifecycle.
- Unseen-message deduplication uses the existing SHA-256-of-content check in every mode.
- The bridge only ever sees the public request messages. It never sees task IDs, arm labels, manifests or answer keys.

**Telemetry.** All modes report the same `x_nyx_bridge` keys:
- `extraction_calls`, `extraction_prompt_tokens`, `extraction_completion_tokens`, `extraction_seconds`, `beliefs_injected`, `injected_chars`, `facts_rejected`.
- `recall` reports the extraction keys as 0 and counts each injected message in `beliefs_injected`.
- Add string fields `memory_mode`, `extraction_model` and `request_model` in every mode, so model mismatches are recorded rather than assumed away. Do not add enforcement that changes `nyx` behavior.

**`nyx` mode must be unchanged.** Against a fake upstream server, the upstream request bodies the bridge sends (extraction and final) and the responses it returns must be byte-identical before and after this work, for the same inputs. Only the three new telemetry string fields may differ.

## Stage 1 — read-only design note (stop after this)

Do not edit or commit anything. In `D:\nyx-bridge` at its current HEAD (record the commit), write the note in your reply. Answer each point with file and line references:

1. The exact functions or classes you would change or add for `naive` and `recall`, and how the mode is selected (a CLI flag or env var through `run_slot.py`).
2. How `naive` calls the **same** extraction function and the **same** serializer as `nyx`, without copying or reimplementing them. If that isn't possible without refactoring `nyx` code, say what refactor and why, and how the byte-identity of `nyx` would be proven.
3. How `recall` gets unseen user messages, and that it makes no upstream extraction call.
4. Where `facts_rejected` is counted, and whether `naive` inherits that counting unchanged.
5. The test setup that exists today (framework, fake upstream, how to run it), and the tests you would add, including the `nyx` byte-identity golden test.
6. Anything that would make D or E weaker or stronger than C other than the store itself, for example ordering, truncation, error paths or retries.
7. Whether `D:\nyx-bridge` has a git remote, and its URL if so.

Then **stop**. The user pastes the note to Claude, who checks it against the fairness rules before Stage 2 is authorized.

## Stage 2 — implementation (only after explicit authorization)

- Branch `control-arms` from the HEAD recorded in Stage 1. Make two commits, `feat:` (code and tests) then `docs:` (README section on modes, fairness rules and the disclosed conflict). Stop for review. No push.
- **Tests**, against a fake upstream only:
  - the `nyx` byte-identity golden test;
  - `naive` stores and injects all extracted facts, including superseded ones, in order, with the same serializer;
  - `recall` makes zero extraction calls and injects the verbatim user messages in order;
  - deduplication per mode;
  - `facts_rejected` per mode;
  - telemetry keys and the three string fields;
  - a fresh store per process, with no carry-over between two `run_slot` invocations.
- **Must not change in `nyx` mode:** its outputs, its prompts, its ordering, and every existing test, which stays byte-for-byte unchanged. If an existing test fails, stop, revert and report.

## Prohibited

- Model runs, LM Studio or any real endpoint. Use fake upstream servers only.
- Changes to ProjectNyx or eTPS.
- Private corpus or kits, dependency installs, push or PR.
