# Codex work order: v0.2 performance and correctness batch (rev 2)

**Provenance.** Written by Claude (a model) on 2026-10-01, from a read-only review of `main` at `0925ae1` (the PR #18 merge). It supersedes rev 1, which was based on `390827b`. Under `CLAUDE.md` this is a labelled model-authored proposal. The user completed Section 0 on 2026-10-01; that approval is the authorization.

Every number below was measured on Linux with Python 3.11.15 and SQLite 3.45.1. The "prototype" results come from in-memory monkeypatches run against the unchanged suite of **246 tests**; no repository file was edited.

---

## 0. Authorization and decisions (the user completes this before Codex starts)

**Status: decided.** On 2026-10-01 the user approved the recommended default for every row (in the Claude session, "go with recommendations on the work order").

| # | Decision | User choice (recommended default approved) |
|---|---|---|
| A0 | Local branch `v02-perf-correctness` from `0925ae1`, one commit per item, stop for Claude's review, no push or PR | **Authorized** |
| D1 | What `acceptance_rate` reports when some slots were never attempted (W3) | **`None` plus a reason, and a separate `acceptance_rate_attempted`** |
| D2 | Live plans in which a model reply is followed directly by another probe (W4) | **A: reject at import.** The one existing-test edit named in W4 is authorized. No other existing test may change. |
| D3 | Request history journaled by hash instead of by copy (W5) | **Opt-in plan field `request_journal: "history-sha256-v1"`; the default stays as it is** |
| D4 | Manual plans with a `d10-v1` manifest (W8) | **Fix the classifier.** The user still has to confirm that no private manual-plan journals with d10-v1 manifests exist (all reported runs were live). Codex records the confirmation as pending in the handoff and does not search private folders. |
| O1 | Memoization (Section 5) | **Skip.** Not part of this batch. |
| O2 | Trickling-response cleanup (Section 5) | **Defer.** Not part of this batch. |

---

## 1. Ground rules (a breach means the item is rejected in review)

1. **Base and delivery.**
   - Branch `v02-perf-correctness` from `0925ae1`.
   - Commit order: W1, W2, W3, W4, W8, W5, W6, W7.
   - One commit per item, with conventional prefixes (`perf:`, `fix:`, `feat:`, `docs:`).
   - Stop after W7. No push and no PR.
2. **Code constraints.** Standard library only, no new dependencies, Python 3.11–3.14.
3. **Existing tests stay byte-for-byte unchanged.** The only exception is the single edit authorized under D2=A. If any other existing test fails, stop that item, revert it completely and record the conflict in the handoff (the V08 precedent).
4. **Scope discipline.** Change only the functions and lines named in the item.
   - No renames, reformatting, import reordering, comment or docstring rewrites, type hints, new classes, helper layers or drive-by fixes.
   - List anything else you notice in the handoff instead.
5. **Local idiom.**
   - Compact expressions in the style of `require(condition, "lowercase message")`.
   - Reuse an existing message wherever the failure is the same.
   - No new exception types.
6. **Behavior preservation.** On the default path, journals, reports and exports stay identical except for the fields an item names.
7. **Test rules.**
   - Tests must be deterministic: no wall-clock thresholds, and seeded RNG where randomness is used.
   - Fake servers are loopback-only.
   - No real endpoints, LM Studio, model runs, private corpus, kits or answer keys.
   - New tests go in new files.
8. **Evidence.**
   - Run `python -B -m unittest discover -s tests -v` at every commit.
   - Run `python -B tools/bench_v02_scaling.py` before W1 and after W7, and paste both outputs into the handoff.
9. **Invent nothing.** No budgets, counts, acceptance criteria or measurement thresholds of any kind.

---

## 2. Measured baseline at `0925ae1`

| Measurement (synthetic fixtures) | Baseline | Cause |
|---|---|---|
| `Store.create` with 5k / 20k / 50k slots | 3.0 s / 43.1 s / 258.5 s (quadratic) | `persistence.py:70` hashes the whole plan file once per slot |
| The same, with the hash hoisted (prototype) | 0.17 s / 0.74 s for 5k / 20k | W1 |
| SQLite VM steps for one `start` after 100 vs 400 terminal predecessors | 1,222 vs 4,522 (ratio 3.70) | `persistence.py:131-134` scans every earlier head |
| 100-turn slot with 2 KB replies: journal bytes | 15,216,602 total, of which 14,711,785 are request entries; the replies themselves are 202,100 | `runner.py:81` and `live_runner.py:25` copy the full history into each request |
| Export + replay, 4 slots × 400 turns | 1,005 MB file; replay peaks at 3,047 MiB RSS and takes 44 s | same cause |
| `acceptance_rate` when 1 of 4 slots ran and was accepted | `1` | `scorer.py:599` divides by attempted slots only |
| Manual plan + d10-v1 manifest, alias-shaped coded answer | operator shown `Class: incorrect`; recovery run; trial `measurement_valid False`, `reason off_script_event` | `manual_runner.py:120,191` use strict `classify`, while the scorer uses `classify_probe` |

Prototype results against the unchanged suite (246/246 unless noted):

| Prototype | Result |
|---|---|
| D1 rule | Pass |
| W1 + W2 | Pass; old and new order predicates agree on 40/40 random sequences |
| W8 (`classify_probe` in the manual runner) | Pass; the reproduction becomes valid, accepted, `accepted_with_format_deviation` |
| D2 gate | Breaks only `test_v02_live_review.py::test_assistant_prefill_guard_both_providers` (2 subtests) |

---

## 3. Items

### W1 — `perf:` hash the plan once in `Store.create`; validate each script once per bundle

**Change in `persistence.py`.** In `Store.create`, compute `plan_hash = sha(plan_raw)` once, before `with db:`. Use it for the plan-row insert (line 66) and for each head seed (line 70): `sha(encode([plan_hash, slot["id"]]))`. The database bytes must come out identical to today's.

**Change in `workload.py`.**
- In `validate_bundle`, slot loop (lines 163–177): call `script_responses(...)` (line 175) once per distinct `slot["script_sha256"]`, tracked in a local set.
- Keep the per-slot `in artifacts` check and `referenced.add`.
- The first slot that references an invalid script must still be the one that raises.

**Tests (new `tests/test_v02_perf.py`).**
- `sha` is called on the plan bytes at most twice for a 50-slot plan (baseline: 52).
- Head seeds equal `sha(encode([sha(plan_raw), id]))` and all heads are `unattempted`.
- A 30-slot plan with 2 distinct scripts makes exactly 2 `script_responses` calls per `validate_bundle` call.

### W2 — `perf:` constant-time planned-order check

**Change in `persistence.py:131-134`.**
- Look up only the head at `ordinal - 1`. A missing row (ordinal 0) passes; otherwise the state must be `finished` or `aborted`.
- Keep the message `"planned run order violated"`.

**Soundness argument** (state it in the commit message and the handoff):
- `start` requires `count == 0`, and every other append requires `state == "running"`. So `finished` and `aborted` are absorbing states.
- When slot *k−1* started, slot *k−2* was already terminal, and it stays terminal. By induction, a terminal predecessor means every earlier slot is terminal.
- Full head and journal verification on open, replay and export is unchanged.

**Tests.**
- A seeded randomized equivalence test against the old full-scan SQL implemented inside the test: 40 sequences over 2–9 slots, mixing start, finish and abort. Accept and reject outcomes and messages must be identical.
- VM steps counted with `db.set_progress_handler(counter, 1)` for one `start` after 50 vs 200 started-and-aborted predecessors: the ratio must be below 1.25.

### W3 — `fix:` acceptance rate must not ignore unattempted slots (D1)

**Change in `scorer.summarize` (lines 585–610).**
- `acceptance_rate` is `Fraction(accepted, len(results))` only when there are results and `planned == len(results)`; otherwise it is `None`.
- Add `acceptance_rate_unavailable_reason`: `"unattempted_slots"`, `"no_trials"`, or `None`.
- Add `acceptance_rate_attempted`, which is accepted/attempted, or `None` when nothing was attempted.

**Tests (new `tests/test_v02_acceptance_rate.py`).**
- Direct cases: complete plan, incomplete plan, and empty results.
- A report built from an 8-slot plan (4 slots per arm) where only `slot-0` ran. Expected: `acceptance_rate None`, reason `"unattempted_slots"`, `acceptance_rate_attempted == 1`.

**Docs.** Add a migration note to `OFFLINE_RUNNER.md`.

### W4 — `fix:` reject live plans that cannot dispatch (D2)

**D2 = A.**

New function `check_live_successors(manifest)` in `live_plan.py`:
- For every `probe` node, none of the targets `next.correct`, `next.incorrect`, `next.unknown`, `next.malformed` or `field_routes[*].next` may be a `probe`.
- Error message: `"live probe successor after a model reply must be a user message"`.
- A `timeout` target may be a probe, because a timeout appends no assistant turn.
- A `session_boundary` target needs no new check: the existing boundary authoring rule already requires a user message before the next probe, and deliver-v1 only dispatches when user messages are pending.

Call it from `workload.validate_bundle` inside the task loop (line 149 onward), only when `live and authoring`. Import it inside the function, the same way `validate_live` is imported at line 121.

The runtime guard in `live_runner._dispatch` (lines 22–23) stays unchanged.

**The one authorized edit to an existing test:** `tests/test_v02_live_review.py::test_assistant_prefill_guard_both_providers` (lines 175–187).
- First assert that `self.create(...)` raises `InvalidRecord` matching `"live probe successor"`.
- Then wrap the existing body, unchanged, in `with patch("etps_v02.live_plan.check_live_successors"):`, so the runtime guard is still exercised.

**New tests (`tests/test_v02_live_successors.py`).**
- A probe whose timeout successor is another probe is accepted.
- A probe target reached through `field_routes` is rejected.
- probe→user and probe→terminal are accepted.
- An offline v2 plan with probe→probe still imports.
- A journal from a now-rejected plan still replays through `replay_export`. Build the export with the check patched out.

**D2 = B.** No enforcement and no test edit. `report()` adds the warning `authoring_findings: live_probe_successor_after_reply` for affected live plans.

### W8 — `fix:` the manual runner must use the scorer's classifier (D4)

**Change.** In `manual_runner.py` line 120, use `scorer.classify_probe(manifest, node, event)`; in line 191, use `scorer.classify_probe(manifest, node, p)`. Nothing else changes.

For manifests without `answer_tolerance` this is equivalent: manual execution requires authoring validation, so `unknown_answers` is always present.

**Tests (new `tests/test_v02_manual_d10.py`).**
1. Reproduction: the d10 fixture from `test_v02_d10_tolerance.manifest()` with coded answer `{"value":42,"label":"Ready"}`. Expected: operator output `Class: correct`, a valid and accepted trial, `result_state == "accepted_with_format_deviation"`.
2. Cross-runner agreement: for every answer used in `test_v02_d10_tolerance` (exact, alias, digit-string, fixed-value, collision, malformed, unknown), the manual outcome equals `classify_probe`.
3. A historical manual journal recorded with the strict classifier on a d10 manifest, built with `classify` patched back in, now fails replay with `"manual branch mismatch"`. The test documents this deliberate change.

**Noticed but not part of this batch.** `replay_manual_slot` returns `evidence_verified: True` even for a finished trace whose recomputed measurement is invalid (`manual_runner.py:217`). Offline replay records `invalid_finished_trace` in that case. List this in the handoff.

### W5 — `feat:` opt-in hashed request history (D3)

**Plan field.**
- Optional `"request_journal": "history-sha256-v1"`. It is accepted only on `etps-offline-plan-v2` and `etps-live-plan-v1`.
- Any other value fails with `"unsupported request_journal"`.
- Legacy and manual plans refuse it through the existing `"invalid plan fields"` check.
- When the field is absent, journals are byte-identical to today's.

**Offline.**
- `runner.run_offline` (line 81) journals `{"node", "message_count": len(messages), "messages_sha256": sha(encode(messages))}`.
- The adapter still receives the full history.
- `replay_slot` (line 163) checks exactly these three fields and the reconstructed count and hash. It reuses the message `"request history mismatch"`.

**Live.**
- `_dispatch` (line 25) journals `{"node", "message_count": len(body["messages"]), "body_sha256": sha(encode(body)), "elapsed_seconds", "deadline_seconds"}`. For delivery requests it also keeps `"kind": "delivery"`, because `boundary_delivery.Path.request` and `observations` read `node` and `kind`.
- `encode(body)` is exactly the request body `_http_once` sends (`adapter_openai.py:91`).
- `replay_live_slot` (line 165) recomputes `adapter.public_request(arm, conversation)` and compares count and hash. It reuses `"request public history/settings mismatch"` and keeps the deadline checks.

**Constraints.**
- No incremental hashing.
- Only `runner.py:163` and `live_runner.py:165` read `messages` or `body` from journal payloads. Re-check this with grep before changing anything.

**Tests (new `tests/test_v02_request_journal.py`).**
1. Score and events are equal across the two modes.
2. A 50-turn chain: hash-mode request payloads total at most 150 bytes × turns.
3. Re-chained tampering (the helper pattern at `test_v02_live_review.py:149-152`) is rejected.
4. reset-v1: after a boundary, `message_count == 0` and the hash is of `[]`.
5. Live, both providers:
   - exact field sets;
   - `replay_export(export_bundle(store, format="v2"))["trials"][0]` equals the run result;
   - a tampered `body_sha256` is rejected.
6. deliver-v1: delivery intents keep `kind`, and a moved or retyped delivery is still rejected.
7. Field validation.
8. v1 and v2 export round-trips.

**Acceptance.** The bench row `journal_bytes.history_sha256` shows requests under 20,000 bytes and a total under 600,000 bytes.

**Docs.** Add a section to `OFFLINE_RUNNER.md` and `LIVE_ADAPTER.md`. It must state that user text and response bytes are still stored, and that request histories are reconstructed and verified against their hashes.

### W6 — `fix:` replay must raise `InvalidRecord`, never `KeyError`

**Change.** Before each existing subscript, add `mapping(payload, path, required)` in these places:
- `live_runner.replay_live_slot`:
  - request: `node`, `elapsed_seconds`, `deadline_seconds`, plus `body` (or the W5 hash fields);
  - event: `kind`;
  - user event: `node`, `text`;
  - probe or delivery event: `node`, `raw_base64`, `client_latency_seconds`, `http_body_base64`, plus `answer` for probes;
  - when `http_body_base64` is not `None`: `http_body_sha256`, `http_status`, `status`, `usage`, `generation`, `generation_source`, `backend_stats`, `transport_detail`;
  - otherwise: the fields read at lines 197–202.
- `manual_runner.replay_manual_slot`, probe events: `raw_base64`, `coded_raw_base64`, `status`, `answer`.
- `boundary_delivery.Path.request` and `.event`: `node`, `kind`.

Add no requirement that is not already a subscript today.

**Tests (new `tests/test_v02_replay_fields.py`).** One subtest per field. Delete the field from a finished live export (fake server; include a deliver-v1 plan) or a manual export, re-chain the hashes, and assert `InvalidRecord`.

### W7 — `docs:` bench, handoff, status

- Add `tools/bench_v02_scaling.py`, exactly as supplied with this order.
- Write the handoff `docs/V02_PERF_CORRECTNESS_<date>.md` in the `V02_HARDENING_2026-09-29.md` format. It includes:
  - a per-item table;
  - the decisions taken;
  - bench output before and after;
  - the test count (246 plus new tests);
  - `git diff --stat 0925ae1 -- tests/`, showing new files only, plus the D2 edit if authorized;
  - any stopped items.
- Append an entry to `docs/STATUS.md`. Do not edit `CLAUDE.md`; note in the handoff that its "no model runs" line is stale.

---

## 4. Out of scope for this batch

| Topic | Reason |
|---|---|
| Streaming export | Hash mode shrinks exports by about 100×; re-measure first |
| Graph complexity in `scorer.validate` | Real manifests are small; this is a design question |
| `field_routes` needing 2^k − 1 entries | Same |
| `check_json_depth` / `boundaries()` micro-optimizations | Their cost only matters near the safety ceilings |
| The wall-limit edge case (`live_runner.py:102`) | Measurement-policy decision for the user |
| Interrupt policy differing between runners | Measurement-policy decision for the user |
| Manual `evidence_verified` flag | Listed in the W8 handoff only |
| Circular imports, long functions, duplicate checks | Need a separate authorization |
| Legacy v0.1 modules | `CLAUDE.md` requires preserving them |

## 5. Optional items

**O1: memoization.**
- Cache `implementation()`: split out `_implementation_uncached()` with `lru_cache(maxsize=1)` and have `implementation()` return deep copies. Keep the public name, because tests patch it. Add a CRLF test against the uncached function.
- Memoize `scorer.validate`: key on `(digest(manifest), authoring)`, at most 64 entries, successful results only, returning deep copies. If computing the digest raises, fall back to uncached validation so the existing error messages are preserved.
- Gain: about 0.1–0.2 s at 264 slots.

**O2: trickling-response cleanup.**
- Rewrite `_http_once` on `http.client` with the total deadline enforced inside the worker: call `sock.settimeout(remaining)` before every read. Keep the existing signature, because tests patch it with four positional arguments.
- Test it with a raw-socket server that trickles bytes: the server must observe the close within 0.5 s of `deadline_exceeded`.
- Measured today: silent servers are already closed at the deadline plus 0.01 s; only trickling servers leave orphaned connections. Whether LM Studio cancels generation when the client disconnects can only be established by a user-operated check.

## 6. Review checklist (Claude, before pushing)

1. One commit per item, each touching only its named files; existing tests unchanged except the D2 edit.
2. Suite green at every commit, at 246 plus the new tests.
3. Every changed line read, with error messages reused.
4. Bench output from before and after, with each acceptance line met.
5. A default-path export of the same synthetic plan, before and after (with no W5 opt-in), differs only in the W3 fields and the `implementation` hashes.
6. Documentation claims match the code, and no values were invented.
