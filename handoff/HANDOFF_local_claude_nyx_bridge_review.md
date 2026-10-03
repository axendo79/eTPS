# Handoff to the local Claude session: nyx-bridge control arms (D/E) review

From the cloud Claude session, 2026-10-02. This is a model-authored summary. Verify the details against the files.

## Your role

You are reviewing the work. Codex (GPT-6-Astra) implements. Do not commit, push or edit `nyx-bridge`, ProjectNyx or eTPS yourself unless the user explicitly asks. Follow `D:\eTPS\CLAUDE.md`:
- no commit or push without explicit instruction;
- Nyx must be allowed to lose;
- disclose the author/system conflict;
- no model runs unless the user authorizes them.

## Where things stand

- **eTPS `main` is at `02a01b4`** on GitHub, axendo79/eTPS. PRs merged this week: #19 (performance and correctness), #20 (W5, opt-in hashed request history), #21 (manual evidence fix plus per-arm `processing_totals`). All 283 tests pass on CI.
- **Work orders and patches for Codex** travel on the orphan branch `codex-handoff`, under `handoff/`. It is never merged.
- **Run 7 Nyx-arm isolation is confirmed.** `run_3arm.py` (SHA-256 `c9b9a1e6…065b`) started a fresh bridge process and store per Nyx slot, recorded in `D:\eTPS-private\runs\local-3arm-nyx-2026-09-30\RUN_RECORD.md`.
- **nyx-bridge:** `D:\nyx-bridge` at `e7fdcce`, with no git remote. Codex has finished Stage 1 (read-only design note) and the user approved Stage 2 with the decisions below. Stage 2 may be in progress or finished. Check `git log` in `D:\nyx-bridge`.

## Four-arm plan (run 8)

| Arm | What it is |
|---|---|
| A | gemma full history |
| B | gemma reset-v1 |
| C | reset + Nyx (`--memory-mode nyx`) |
| D | reset + naive extraction (`naive`): same extractor, all extracted facts injected, no supersession handling |
| E | reset + transcript recall (`recall`): no extraction, verbatim user messages injected |

Rules settled with the user:
- no injection cap in any mode;
- a fresh process and store per slot;
- `NYX_BRIDGE_MODEL` equals the answer model, and both are recorded;
- temperature 0 with 3 repeats, reported per repeat and not pooled;
- arm order rotated;
- outcomes frozen before the run;
- costs reported next to accuracy using eTPS `processing_totals`;
- with 8 fact-dependent tasks, differences of 1–2 tasks are noise; treat this as calibration, not proof;
- a fair result eventually needs held-out tasks written by someone independent.

## Stage 2 decisions the user approved

1. **Existing tests** stay byte-for-byte unchanged, except the single assertion at `tests/test_bridge.py:145`. It may be extended to the exact new key set: the existing keys plus `memory_mode`, `extraction_model`, `request_model` and `bridge_instance`.
2. **`bridge_instance`** = the store file's base name, with no directory path, in all modes.
3. **All modes** use the existing "Facts remembered…" prefix and system-message position through the shared `serialize_memory`. Recall's wording is not changed. This is documented as a known difference.
4. **Four commits in order:**
   a. `test:` raw-byte golden fixtures captured from **unmodified** `e7fdcce`;
   b. `refactor:` a mechanical move into `Bridge._extract_facts` and `serialize_memory`, with the goldens unchanged and passing;
   c. `feat:` the modes, `NYX_BRIDGE_MEMORY_MODE`, `NaiveMemory`, `RecallMemory`, the four telemetry fields, and new tests;
   d. `docs:` the README section on modes, fairness differences, accounting fields and the conflict disclosure.
5. **Deliverables:**
   - `D:\etps\ProjectNotes\nyx_bridge_control_arms.diff`, containing `git diff e7fdcce..HEAD`;
   - `D:\etps\ProjectNotes\nyx_bridge_control_arms_tests.txt`, the full test output.

## Review checklist (you can run things the cloud session could not)

1. **History:** exactly 4 commits on top of `e7fdcce`, in the order above. `git diff e7fdcce..HEAD -- tests/` shows new files plus only the one authorized line change at `test_bridge.py:145`.
2. **Golden proof is real:**
   - Check out commit (a) alone and confirm the golden tests pass on unmodified source code.
   - Then confirm the same golden files are unchanged in (b), (c) and HEAD.
   - The goldens must compare raw bytes of every upstream request, extraction and final, plus the response bytes. The only normalizer allowed strips exactly the four new telemetry members.
3. **The refactor in (b) is purely mechanical:** prompt text, field order, `temperature 0`, `max_tokens=1024`, `stream=False`, timing, usage handling, parser and exception handling are all identical.
4. **Naive shares code with Nyx:** it calls `_extract_facts` and `serialize_memory`, with no copies, and uses the same unseen-message loop and the same `facts_rejected` accounting. It stores every admitted fact in arrival order, as `subject`/`property`/`value`.
5. **Recall makes zero extraction calls,** stores verbatim unseen user messages in arrival order and counts them in `beliefs_injected`.
6. **No mode receives task IDs, arm labels, manifests or answer keys.** Fresh-store refusal and per-process isolation are preserved in `run_slot`. Add your own check: two `run_slot` runs per mode with no carry-over.
7. **Run the full nyx-bridge suite yourself** with the command in the README, and compare against Codex's test log.
8. **Read every line of the diff adversarially.** Is there anything that makes D or E weaker or stronger than C beyond the store itself and the documented differences: ordering, recall keeping non-factual text, the shared prefix, extraction cost?

## After review

Report to the user. Do not merge or commit for them.

Separately, the run 8 driver should log each slot's bridge process ID, store path and port. Then it's offline synthetic validation of the four-arm plan, then the frozen plan hash, then the run, which only happens with the user's authorization.
