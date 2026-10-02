# Codex work order: cleanup batch (rev 4)

**Provenance.** Written by Claude (a model) on 2026-10-02. It is a labelled model-authored proposal under `CLAUDE.md`, and the user authorized eTPS cleanup and optimization work through Monday. Both patches were verified by Claude on Linux with Python 3.11.15:

| Applied to | Result |
|---|---|
| `main` at `a2f3896` | 264/264 tests pass |
| `main` + the W5 patch | 264/264 tests pass |

The patches touch different files from W5, so the order of the two batches doesn't matter.

## Base

- If W5 has been merged into `main`: branch from the latest `main`.
- Otherwise: branch from `a2f3896`.
- Branch name: `v02-cleanup-batch`.
- Record the base commit in the handoff.

## Items

### C1 — `fix:` manual replay must not report invalid finished traces as verified

**Problem (reproduced).**
- `replay_manual_slot` always returns `evidence_verified: True`. Today `manual_runner.py:218` hardcodes it.
- A manual journal whose user message text was edited and re-chained replays with `measurement_valid False` (`unmatched_user_payload`) while still claiming `evidence_verified True`.
- Offline replay flags the same situation as `invalid_finished_trace`.

**Change.** Apply `C1_manual_evidence.patch`, which edits `etps_v02/manual_runner.py` only. A finished slot whose recomputed measurement is invalid gets:
- `evidence_verified: False`;
- the warnings `recomputed_measurement_invalid` and `unverified_evidence: invalid_finished_trace`, matching the offline runner.

Unattempted slots, running slots, aborted slots and valid finished slots are unchanged.

**Tests (new file `tests/test_v02_manual_evidence.py`).**
1. A clean manual run stays `evidence_verified True`.
2. Edit a user event's text in a v1 export, re-chain it (`rechain` from `test_v02_session_profile`) and replay it. The result is `evidence_verified False` with both warnings, and the score is `measurement_valid False`.
3. Aborted and running manual slots keep their current `evidence_verified` values.

### C2 — `feat:` per-arm processing totals for the cost table

**Why.** The four-arm run must report total cost next to accuracy. Today the parts are spread across `processed_prompt_tokens`, `memory_telemetry` and `delivery_processing`, and someone has to add them up by hand, which invites mistakes. The Nyx bridge also reports rejected extraction batches as `facts_rejected`, but eTPS doesn't summarize that key.

**Change.** Apply `C2_processing_totals.patch`, which edits `etps_v02/memory_telemetry.py` and `etps_v02/session_profile.py`:

1. `memory_telemetry.KEYS` gains `"facts_rejected"`, summarized the same way as the other keys.
2. `session_profile.completion_requests(rows)` collects `usage.completion_tokens` for every answer and delivery request. Unanswered intents still count in the denominator.
3. `session_profile.total()` takes an optional `key` argument, defaulting to `"prompt_tokens"`. Existing callers are unchanged.
4. Live reports with arm comparison gain `processing_totals[arm]`, containing:
   - answer-and-delivery prompt and completion token totals (each with coverage);
   - extraction prompt tokens, extraction completion tokens, extraction seconds and `facts_rejected` from memory telemetry, or `"not_applicable"` for arms without memory telemetry;
   - `all_prompt_tokens` and `all_completion_tokens`, which are `null` unless every part is reported for every request;
   - a `definition` string that labels extraction figures as self-reported.

No scoring, acceptance, RR, TPS or eTPS value changes.

**Verified example.** A deliver-v1 memory arm with 2 requests, where each reply reports 100 prompt and 7 completion tokens and extraction reports 40 prompt, 9 completion and 1 facts_rejected:
- `all_prompt_tokens` = 280;
- `all_completion_tokens` = 32;
- `facts_rejected` sum = 2;
- the replayed export reproduces the same `processing_totals`.

**Tests (new file `tests/test_v02_processing_totals.py`).** Use the `plan()` fixture from `test_v02_boundary_delivery` and `FakeServer`.
1. The verified example above, with exact values.
2. A non-memory arm: extraction fields are `"not_applicable"` and the all-totals equal the answer-and-delivery totals.
3. One reply missing `usage.completion_tokens`: `all_completion_tokens` is `null`, and coverage shows 1 of 2.
4. Memory telemetry missing on one request: the extraction totals are incomplete, so `all_prompt_tokens` is `null`.
5. `replay_export(export_bundle(store))` reproduces `processing_totals` exactly.
6. `facts_rejected` appears in `memory_telemetry[arm]["metrics"]`.

### C3 — `docs:` documentation

- **`docs/v0.2/LIVE_ADAPTER.md`:** add a section on `processing_totals`. It should state:
  - what each field sums;
  - that extraction figures are self-reported by the memory system;
  - that totals are `null` unless coverage is complete;
  - that this is a descriptive diagnostic, never scoring.
- **`docs/v0.2/MANUAL_DEV.md`:** add one paragraph on C1.
- **`README.md` repository map:** replace the row that names three test files with a row for `tests/` reading "Synthetic unit, replay, adversarial and fake-server tests (standard library only)", and add a row for `tools/bench_v02_scaling.py`.
- **`docs/STATUS.md`:** append an entry.
- **Handoff:** write a short `docs/V02_CLEANUP_BATCH_<date>.md` containing:
  - the base commit;
  - per-item results;
  - test count before and after;
  - `git diff --stat <base> -- tests/`, which must show new files only.
- Do not commit per-run test logs.

## Ground rules (unchanged)

- **Commits:** three, C1 `fix:`, C2 `feat:`, C3 `docs:`. Stop for Claude's review. No push and no PR.
- **Patches:** before applying, verify both patch hashes and run `git apply --check`. If either fails, stop and report rather than redesigning.
  - `C1_manual_evidence.patch` = `c3d063d109781beb1526d2d4c24e84dcf5094c8dc6211862b27344a2cf7307bb`
  - `C2_processing_totals.patch` = `8c85f399f2df565f3b6eadd608122c273549aa70445778600699a165f9d9b16c`
- **Tests:** existing tests stay byte-for-byte unchanged, with no exceptions. If one fails, stop, revert that item and report.
- **Spec errors:** if a test this order specifies conflicts with existing behavior, stop and ask, as you did for W5's test 2.4. Do not bend the test.
- **Scope:** standard library only. No renames, reformatting or drive-by fixes. List anything else you notice in the handoff.
- **Prohibited:** model runs, LM Studio or real endpoints, private data, installs, push or PR.
- **Staging:** never stage `ProjectNotes/`. Stage explicit paths only.
