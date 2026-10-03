# Codex prompts: after the control-arms review (run 8 preparation)

**Provenance.** Written by Claude (a model) on 2026-10-02 as a labelled model-authored proposal, after reviewing nyx-bridge Stage 2. Facts checked locally:
- nyx-bridge `control-arms` is at `32d8801`; `master` is at `e7fdcce`; 33/33 tests pass; no remote.
- The run 7 driver, plan, and tasks are in `D:\eTPS-private\runs\local-3arm-nyx-2026-09-30\`.
- eTPS `main` is at `02a01b4`.

**Disclosed conflict.** The eTPS author builds Nyx and owns the control arms. Nyx must be allowed to lose.

**Naming note.** The handoff calls this the "four-arm plan", but it lists five arms (A–E). These prompts use all five.

Send the prompts one at a time. Each ends with a stop. Prompt 3 starts a model run, so send it only when you have decided to run.

---

## Prompt 1: merge control-arms (local only)

```
In D:\nyx-bridge (no remote; use `git -c safe.directory=D:/nyx-bridge` if git refuses ownership):

1. Confirm the branch `control-arms` is at 32d8801 and the working tree is clean, including ignored files (`git status --short --ignored` prints nothing). If either is not true, stop and report.
2. `git checkout master`, then `git merge --ff-only control-arms`. A fast-forward is required; if it is not possible, stop and report. Do not create a merge commit.
3. Confirm master is at 32d8801. Run the README test command from the repository root (not from a copy; the protected-path tests assume the real checkout location). Paste the summary line.
4. Keep the control-arms branch. Do not push. Do not edit any file.

Report: master HEAD, test summary, final `git status --short --ignored`.
```

---

## Prompt 2: run 8 five-arm driver and offline validation (no model runs)

```
Build the run 8 driver and validate it offline. No model runs: do not contact LM Studio or any real endpoint. Use fake loopback upstreams only. Do not edit D:\eTPS, D:\ProjectNyx or D:\nyx-bridge. Do not modify anything in the run 7 directory. No commit or push.

Context: the run 7 driver D:\eTPS-private\runs\local-3arm-nyx-2026-09-30\run_3arm.py (read it first), plus its plan.json, tasks/ and RUN_RECORD.md. nyx-bridge master must be at 32d8801 and clean. Read D:\nyx-bridge\README.md, section "Memory modes and control fairness".

## Run directory
Create D:\eTPS-private\runs\local-5arm-controls-<today YYYY-MM-DD>\ containing:
- run_5arm.py
- tasks/: the 11 task JSON files copied byte-for-byte from run 7's tasks/. Verify every file's SHA-256 against run 7 plan.json "tasks". Stop on any mismatch.
- repeat-1/, repeat-2/, repeat-3/: one plan.json each, plus (in a live run only) run.db, report.json, export-v2.json, slot_log.jsonl and bridge-stores/.

## Arms
| Name | Letter | Bridge mode |
|---|---|---|
| gemma-full | A | none |
| gemma-reset | B | none |
| gemma-reset-nyx | C | nyx |
| gemma-reset-naive | D | naive |
| gemma-reset-recall | E | recall |

- Copy each arm config from run 7's plan.json. C, D and E use run 7's gemma-reset-nyx config unchanged: endpoint http://127.0.0.1:18234, memory_telemetry_field x_nyx_bridge.
- The only difference between C, D and E is NYX_BRIDGE_MEMORY_MODE, which the driver sets before each start_bridge call. Hold the arm→mode mapping in one constant in the driver.
- Copy all other plan fields from run 7 unchanged: fence-v1, decode-v1, warm-declared, deliver-v1, deadlines, invalidation_policy, exposure, purpose live-exploratory, model google/gemma-4-e4b, temperature 0, max_tokens 2048, seed null.

## Repeats and order
- eTPS plans have no repeat field. Each repeat is therefore a separate plan and store with 55 slots (11 tasks × 5 arms). Nothing is pooled across repeats in any output.
- Rotate arm order deterministically, with no RNG: for task index t (in run 7's task order) and repeat r (0–2), rotate the A–E list by (t + r) mod 5.
- Print a matrix of arm × position counts per repeat and across all repeats.

## Driver behaviour
- Before anything else, record code_versions.json: the eTPS, nyx-bridge and ProjectNyx HEADs, plus `git status --porcelain` for each. Refuse to start a live run if any tree is dirty or nyx-bridge is not at 32d8801.
- Assert that NYX_BRIDGE_MODEL equals the plan arm model, and record both.
- For every slot, append one JSON line to repeat-N/slot_log.jsonl: slot id, arm, memory_mode (null for A/B), bridge PID, port, absolute store path, start/stop UTC timestamps, bridge exit code, run_live state and result_state, and any exception type/message.
- Store paths: repeat-N/bridge-stores/<slot_id>.db for nyx and <slot_id>.jsonl for naive/recall. Each must be fresh; never reuse one.
- Keep run 7's try/finally structure: always call stop_bridge, and continue to the next slot after a slot error.
- After each repeat, verify from the journal that every C/D/E response's x_nyx_bridge.memory_mode matches the arm, and that A/B have no memory telemetry. Any mismatch marks that repeat invalid in the output; do not silently drop it.
- Live mode requires an explicit `--live` flag. The default is synthetic. Do not run `--live`.

## Offline synthetic validation (the deliverable for this prompt)
Run the whole driver end to end in synthetic mode: all 5 arms × 3 repeats, with real nyx-bridge subprocesses. Upstream is a scripted fake LM Studio-compatible server on loopback, and tasks are INVENTED fixtures with the same schema (the eTPS test fixtures are fine). Real private tasks are only validated structurally with the eTPS plan validator; no request is sent with them.

Report evidence for each of the following:
1. All 165 slots finished or failed as scripted. slot_log has one line per slot, with distinct PIDs for every bridge slot and a fresh store per bridge slot.
2. The memory_mode check passes per repeat. Deliberately break it once (wrong mode for one slot) and show the repeat is flagged invalid.
3. No slot id, arm name, task name or plan hash appears in any raw bytes the fake upstream received through the bridge.
4. Per-arm processing_totals are present in every repeat's report. E's extraction totals are 0. A/B show not_applicable.
5. The rotation matrix.
6. Missing extraction usage. Script one C and one D extraction response without "usage". Show what eTPS records for that request's memory_telemetry_status. Expected: "invalid", because etps_v02/memory_telemetry.py rejects null values and the bridge reports null token counts. Show the effect on processing_totals coverage. E cannot hit this. Do NOT change eTPS; just report it, because it is a cost-coverage asymmetry that must be disclosed.
7. Killing a bridge mid-slot: the slot is retained as failed/invalid per invalidation_policy, the store and log are kept, and the next slot starts cleanly.
8. A dry structural check of the three real repeat plans with the eTPS plan validator, with no requests sent.

Write the validation output to VALIDATION.md in the run directory, with the exact commands. Then STOP for review. Do not freeze and do not run live.
```

---

## Review of Prompt 2 (Claude, 2026-10-02): approved after two fixes

Independently verified: 165 slot-log rows; 99 bridge slots with 99 distinct PIDs and stores; zero leaks across 466 raw upstream files (84 needles); task hashes; plan structure. Accepted as harness evidence. Apply these fixes to run_5arm.py before Prompt 3:

1. **Live gate vs ProjectNotes.** `live_gate` refuses eTPS because of the untracked `ProjectNotes/` folder. Allow eTPS status to be either empty or exactly `?? ProjectNotes/\n`. Refuse anything else, including any other untracked path and any tracked change in any repository. Keep recording the full porcelain in code_versions.json. Show with in-memory `versions` dicts (do not create files in D:\eTPS) that the gate accepts: empty; exactly ProjectNotes. Show that it refuses: another untracked path; a modified tracked file; dirty ProjectNyx.
2. **Bridge upstream.** In `--live`, set NYX_BRIDGE_UPSTREAM to `http://127.0.0.1:1234`, exactly as run 7 did, instead of the plan's `http://localhost:1234`. Record the value used in each slot_log entry.

Then rerun `--validate-only` (zero requests) and the default synthetic validation into a new `synthetic/validation-003`, and confirm the same results as validation-002. Append a short "Review fixes" section to VALIDATION.md. Then continue with Prompt 3. The FREEZE must also hash audit_offline.py.

---

## Prompt 3: freeze (after the Prompt 2 review approves it)

```
In D:\eTPS-private\runs\local-5arm-controls-<date>\ (no model runs, no edits outside this directory):

1. Write ANALYSIS_PLAN.md before any live data exists:
   - Outcomes per arm, per repeat, never pooled: accepted (exact / format deviation), first-attempt retained on the fact-dependent tasks (list them by name from task metadata), accepted only after user re-supply (R > 0), pooled RR, eTPS examples, and processing_totals beside accuracy.
   - Comparisons: C vs D (what the Nyx store adds over naive retention of the same extracted facts), C vs E (extraction vs verbatim recall), and C vs A/B as in run 7.
   - Interpretation rules: with 8 fact-dependent tasks, differences of 1–2 tasks are noise. This is calibration, not proof. Report Nyx losses plainly. A fair result needs independently authored held-out tasks.
   - Known differences: those in the nyx-bridge README fairness section, plus the missing-usage coverage asymmetry from VALIDATION.md.
   - Conflict disclosure.
2. Write FREEZE.json with SHA-256 of run_5arm.py, each repeat-N/plan.json, each task file, ANALYSIS_PLAN.md and VALIDATION.md, plus the three repository commits. Add one combined hash over the sorted entries.
3. Make run_5arm.py --live verify FREEZE.json before its first request, and refuse on any mismatch.

Report the combined hash. STOP. Do not run live.
```

---

## Prompt 4: the run. Send only when you authorize a model run.

```
I authorize run 8. Run it as follows:

1. LM Studio is running on 127.0.0.1:1234 with google/gemma-4-e4b loaded. Verify FREEZE.json, then run `run_5arm.py --live` for repeats 1–3 in order.
2. Make no code or plan changes mid-run. If a repeat is flagged invalid or the driver crashes, stop and report; do not retry or patch.
3. Afterwards, write RUN_RECORD.md in the style of run 7's. Report results per repeat exactly as ANALYSIS_PLAN.md specifies, and include the conflict disclosure.
4. Results describe "Nyx-backed prototype memory", not Nyx. No commit, push or publication.
```
