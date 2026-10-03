# Codex work order: W5 redo — opt-in hashed request history (rev 3)

**Provenance.** Written by Claude (a model) on 2026-10-02 from `main` at `a2f3896` (the PR #19 merge). It is a labelled model-authored proposal under `CLAUDE.md`. The decision is D3 from rev 2, already made by the user: an opt-in plan field `request_journal: "history-sha256-v1"`, with the default unchanged. The user authorized this redo on 2026-10-02.

## Why the first attempt stopped, and what changes

- The rev 2 attempt tested `plan.get("schema")` for membership in a Python set.
- The existing test `test_v02_repairs.RepairTests.test_v04_plan_and_script_shapes_fail_before_database_creation`, subtest `{"schema": []}`, passes a list, which is unhashable, and the check raised `TypeError`.
- This redo uses only `==` comparisons on plan values and adds the field after the existing shape logic. Nothing is hashed.

## Reference implementation (verified)

`W5_reference.patch` (attached) changes `etps_v02/workload.py`, `etps_v02/runner.py` and `etps_v02/live_runner.py`. Claude verified it on Linux with Python 3.11.15 against `a2f3896`. The results:

| Check | Result |
|---|---|
| Existing suite, unchanged | **264/264 pass**, including the `{"schema": []}` subtest |
| Bench, full-history mode (unchanged) | requests 14,711,785 bytes; total 15,216,602 |
| Bench, hash mode | requests **11,835** bytes; total **516,652** (targets: < 20,000 and < 600,000) |
| Live, deliver-v1, both `reset-v1` and `full` | finished, valid, `evidence_verified`; delivery intents keep `kind`; `replay_export(export_bundle(format="v2"))` equals the run result |
| Tamper on a re-chained v1 export: `body_sha256`, `message_count`, or a prior user `text` edited | rejected with `request public history/settings mismatch` |
| Offline tamper: `messages_sha256` edited | rejected with `request history mismatch` |
| Offline tamper: extra request field | rejected with `invalid request fields` |
| Plan with `request_journal: "nope"` | rejected with `unsupported request_journal` |

Apply the patch as given. If it doesn't apply cleanly, or you believe it is wrong, stop and report rather than redesigning it.

## Item

### W5 — `feat:` opt-in hashed request history

1. **Apply the reference patch.**
   - Offline requests become `{"node", "message_count", "messages_sha256"}`.
   - Live requests become `{"node", "message_count", "body_sha256", "elapsed_seconds", "deadline_seconds"}`, plus `"kind": "delivery"` for delivery requests.
   - Replay reconstructs the history and checks the count and hash.
   - With the field absent, everything is byte-identical to `a2f3896`.
2. **Tests (new file `tests/test_v02_request_journal.py`).** Use loopback fake servers only.
   1. Equivalence: run the same offline plan in both modes. Score dicts and event lists are equal, and request payloads in hash mode have exactly the three fields.
   2. Size: a 50-turn chain; hash-mode request payloads total at most 150 bytes per turn, and full mode is more than 10× larger.
   3. Offline tamper on a re-chained v1 export (`rechain` from `test_v02_session_profile`):
      - an edited `messages_sha256`;
      - an edited `message_count`;
      - an edited prior user `text`;
      - an extra field, which must be rejected with `invalid request fields`.
   4. `reset-v1` offline arm: the first request after a boundary has `message_count == 0` and `messages_sha256 == sha(encode([]))`. Replay passes.
   5. Live, both `openai-compatible` and `anthropic`: exact request field sets; a v2 export round-trip equals the run result; a re-chained v1 export with a tampered `body_sha256` is rejected.
   6. Live with deliver-v1 (fixture `plan()` from `test_v02_boundary_delivery`) under `reset-v1` and `full`: valid and verified. The delivery intent carries `kind`. A moved or retyped delivery request is still rejected.
   7. Plan-field validation:
      - an unknown value is rejected with `unsupported request_journal`;
      - on manual and legacy v1 plans the field fails with `invalid plan fields`;
      - `{"schema": [], "request_journal": "history-sha256-v1"}` raises `InvalidRecord`, never `TypeError`.
3. **Docs.**
   - Add a section to `docs/v0.2/OFFLINE_RUNNER.md` and `docs/v0.2/LIVE_ADAPTER.md`. It must state that user text and response bytes are still journaled, and that request histories are reconstructed and verified against their hashes rather than stored. The default is unchanged.
   - Append an entry to `docs/STATUS.md`.
   - Add a short handoff, `docs/V02_W5_REQUEST_JOURNAL_<date>.md`, containing:
     - test count before and after;
     - bench output before and after;
     - `git diff --stat a2f3896 -- tests/`, which must show the new file only.
   - Do not commit per-run test logs. Paste the final `unittest` summary lines into the handoff instead.

## Ground rules (unchanged from rev 2, Section 1)

- **Branch and commits.** Branch `v02-w5-request-journal` from `main` at `a2f3896`, with two commits:
  - `feat:` code and tests;
  - `docs:` docs, STATUS and handoff.
- **Stop point.** Stop for Claude's review. No push and no PR.
- **Runtime.** Standard library only; Python 3.11–3.14.
- **Existing tests are byte-for-byte unchanged, with no exceptions.** If one fails, stop, revert completely and report it.
- **Scope.** No renames, reformatting or drive-by fixes. List anything else you notice in the handoff.
- **Prohibited.** Model runs, LM Studio or real endpoints, private corpus or kits, installs, push or PR.
- **Staging.** Never stage `ProjectNotes/`. Stage explicit paths only.
