# v0.2 performance and correctness handoff

Codex (Astra), 2026-10-01. User-authorized local work from main `0925ae1`,
on `v02-perf-correctness`, in order W1, W2, W3, W4, W8, W5, W6, W7.
Stop after W7 for Claude's review; no push or PR. W5 was stopped and completely
reverted under the existing-test rule. Its empty outcome commit preserves the
requested one-commit-per-item order without claiming implementation.
No model runs, real endpoints, LM Studio, private corpus or kits, dependency
installs, private-folder searches, or remote publication occurred in this batch.
Live tests used ephemeral loopback fake servers only. Synthetic checks establish
software behavior, not model performance, measurement validity of a corpus, or
independent review.

## Per-item outcome

| Item | Outcome | Before / after and limits |
| --- | --- | --- |
| W1 (`0161011`) | Done | `Store.create` hashes the plan once before inserts; head seeds are unchanged. Each distinct script is validated once per bundle call, retaining per-slot reference checks and first-reference validation order. 248 tests pass. |
| W2 (`211f627`) | Done | Full predecessor scan becomes one indexed immediate-predecessor lookup. Error text and lifecycle checks remain. Seeded equivalence covers 40 sequences of 2-9 slots; VM-step ratio is below 1.25 for 50/200 predecessors. 250 tests pass. |
| W3 (`f9af53a`) | Done | Incomplete planned groups have null `acceptance_rate` with `unattempted_slots`; empty zero-plan groups use `no_trials`. `acceptance_rate_attempted` retains accepted/attempted. Complete groups retain their rate. Migration note added. 252 tests pass. |
| W4 (`1c1d22d`) | Done, D2=A | Live authoring rejects probe successors after replies, including field routes. Timeout-to-probe, user and terminal successors remain permitted. Historical replay and the runtime guard remain. Only the authorized existing test was edited. 257 tests pass. |
| W8 (`5c5e722`) | Done | Manual execution/replay use `classify_probe`. The alias reproduction is correct, valid and accepted with format deviation. A strict-classifier historical D10 manual journal now fails with `manual branch mismatch`. 260 tests pass. |
| W5 (`b9aedb8`, empty) | Stopped, fully reverted | An existing malformed-plan test failed. No hash-mode plan field, journal implementation, documentation or new W5 tests remain. Request histories still use full copies. 260 tests pass after revert. |
| W6 (`7e1dd86`) | Done for retained format | Missing required live/manual/delivery replay fields now raise `InvalidRecord` before subscripts. W5 hash fields are inapplicable because W5 was reverted. Probe request `kind` remains optional, as it was read with `.get()`, not a subscript. 264 tests pass. |
| W7 (this commit) | Done | Supplied benchmark, this handoff, append-only STATUS entry, before/after benchmark output, per-item full-suite logs and conflict evidence. Final suite: 264 tests, OK. |

## Decisions and supplied-file integrity

Section 0 was decided by the user and was not reopened. A0 authorized the local
branch and commit sequence. D1 selected null plus reason and the attempted-only
diagnostic. D2 selected import rejection with the single named test edit.
D3 authorized opt-in `history-sha256-v1`, but delivery stopped under Section 1's
existing-test rule. O1 memoization was skipped; O2 trickling-response cleanup
was deferred.

Both supplied files were checked with `Get-FileHash -Algorithm SHA256` before
work. The first work-order hash differed from the user's original expected hash,
so execution stopped until the user explicitly authorized the actual hash:

- Work order: `a402463cbe965eaa4ba212d0994e93e0af20aaf7f2d0dd8d6a29d3917e72a040`.
- Benchmark: `1c989248a135b671c47f5cc6301820085efb9d8f01f515915159e83597c3de7d`.

The benchmark was copied with `Copy-Item` to `tools/bench_v02_scaling.py` before
W1, then rehashed. Its bytes still match the supplied benchmark. ProjectNotes
was neither edited nor staged; all staging used explicit paths.

The user supplied this exact D4 override without authorizing an edit to the
work-order file; it was applied as an instruction:

> Fix the classifier. User confirmation, 2026-10-01: none known to exist. Claude ran no manual plans in its session. Codex must state in the handoff whether it ever created or ran a manual plan with a d10-v1 manifest, and must not search private folders.

**Codex D4 disclosure:** yes, during this batch Codex created and ran disposable
synthetic manual plans with `d10-v1` manifests through automated scripted-input
tests for W8, including the deliberately strict historical-journal reproduction.
These were temporary test artifacts, with no human manual service session or
model interaction. Before those tests, no D10 manual plan was created or run in
this conversation. Codex cannot attest to unavailable session history; the public
provenance records earlier manual scaffolding but no Codex manual service session.
No private folders were searched. The user's confirmation above is recorded as
given, not as pending or as independently verified.

## Regression coverage

Baseline: **246 tests, OK**. Final: **264 tests, OK** (18 new test methods).
All baseline test files are unchanged in Git except the single authorized edit
to `test_assistant_prefill_guard_both_providers` in `tests/test_v02_live_review.py`.
That method now first checks import rejection, then runs its original runtime
guard body under a patch of `check_live_successors`.

- `test_v02_perf.py` (4): plan hash call count and head seeds; distinct script
  validation; 40 seeded order-equivalence sequences with identical errors; VM steps.
- `test_v02_acceptance_rate.py` (2): complete/incomplete/empty direct summaries;
  eight-slot, two-arm report with only the first slot accepted.
- `test_v02_live_successors.py` (5): all reply outcomes versus timeout; field
  routing; user/terminal successors; offline import; historical live export replay.
- `test_v02_manual_d10.py` (3): alias reproduction; exact, alias, digit-string,
  fixed-value, collision, malformed, unknown, timeout and field-route cases;
  deliberate historical strict-classifier rejection.
- `test_v02_replay_fields.py` (4): one subtest per deleted field in re-chained
  exports, covering both providers, probe/delivery, HTTP-body and transport-failure
  paths, manual probes, and direct delivery-path missing fields.

Each retained item and the W5 revert passed the full suite before its commit.
During development, new tests in W3 and W8 used incorrect report lookup keys,
and a new W4 field-routing fixture left an unreachable recovery node. Those
new-test mistakes were corrected; no existing tests failed in those items.
W5 is the only existing-test conflict and was not repaired or retried as a feature.

Commands were the requested `python -B tools/bench_v02_scaling.py` and
`python -B -m unittest discover -s tests -v`, using the installed interpreter
`C:/Users/axend/AppData/Local/Python/pythoncore-3.14-64/python.exe` because `python`
was absent from this shell's PATH and the sandbox could not access the interpreter.
Windows Python 3.14.2 / SQLite 3.50.4 were used. Python 3.11-3.13 were not run or
installed. The saved PowerShell test logs include NativeCommandError formatting
for unittest's ordinary stderr output; the terminal unittest result is authoritative.
Subsequent suite commands explicitly propagated the native exit code. Saved logs
are UTF-8 with LF line endings and trailing presentation whitespace removed;
test messages and results are unchanged.

`git diff --stat 0925ae1 -- tests/`:

```text
 tests/test_v02_acceptance_rate.py |  42 +++++++++++++++
 tests/test_v02_live_review.py     |  19 ++++---
 tests/test_v02_live_successors.py |  66 +++++++++++++++++++++++
 tests/test_v02_manual_d10.py      |  93 ++++++++++++++++++++++++++++++++
 tests/test_v02_perf.py            |  94 ++++++++++++++++++++++++++++++++
 tests/test_v02_replay_fields.py   | 110 ++++++++++++++++++++++++++++++++++++++
 6 files changed, 416 insertions(+), 8 deletions(-)
```

## W5 existing-test conflict

The attempted `validate_bundle` addition tested `plan.get("schema")` for
membership in a set of the two supported schemas before the existing shape
rejection. The unchanged regression
`test_v02_repairs.RepairTests.test_v04_plan_and_script_shapes_fail_before_database_creation`,
subtest `value={'schema': []}`, then raised:

```text
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
Ran 267 tests in 39.037s
FAILED (errors=1)
```

The rule requires stopping the item, not repairing the implementation until the
test passes. All W5 changes to workload.py, runner.py, live_runner.py,
OFFLINE_RUNNER.md and LIVE_ADAPTER.md were restored to the W8 commit, and the new
test_v02_request_journal.py was removed. No existing test was weakened, skipped,
rewritten or patched to bypass this failure. The full reverted suite passed 260
tests. The empty W5 commit contains only the outcome message. Reattempting W5
requires a later work order or explicit authorization.

Consequently the benchmark's hash-mode acceptance targets (requests under 20,000
bytes and total under 600,000 bytes) are **not met**: that mode remains unsupported.
W6 validates the existing full-body journal format and does not silently add W5.

## W2 soundness and default-path compatibility

`start` requires `count == 0`; every other append requires `state == "running"`.
Thus `finished` and `aborted` are absorbing states. When slot k-1 started, slot
k-2 was already terminal and stays terminal. By induction, a terminal predecessor
means every earlier slot is terminal. Full head and journal verification on open,
replay and export is unchanged. This argument is also in the W2 commit message.

A disposable compatibility probe extracted only tracked source/tests from
`0925ae1` and used the same two-slot synthetic fixture in baseline and current
code. A fixed `PYTHONHASHSEED=0` was necessary because the fixture builds an
insertion-ordered JSON object from the OUTCOMES set; otherwise separate processes
construct different source artifact bytes. No production change was made for that.
`Store.create` produced identical database bytes. With implementation identity
held constant in both processes, default v1 export and journal payloads/chains
were identical after accounting for W3's acceptance fields. Actual source identity
naturally changes, along with hashes derived from start records containing it.
The probe's first comparison with unfixed fixture construction was discarded and
rerun with the identical-input condition enforced.

## Benchmark output before and after

These are synthetic harness scaling measurements, not model measurements. Times
are informational; the deterministic VM-step and byte rows are the evidence.
No new benchmark budgets, criteria or thresholds were invented.

Before W1:

```text
python	3.14.2
sqlite	3.50.4
create_seconds.slots_1000	0.18
create_seconds.slots_4000	1.03
start_vm_steps.predecessors_100	1022
start_vm_steps.predecessors_400	3722
start_vm_steps.ratio_400_over_100	3.64
journal_bytes.full_history.total	15216601
journal_bytes.full_history.requests	14711785
journal_bytes.full_history.reply_bytes	202100
journal_bytes.history_sha256	unsupported (invalid plan fields)
report_seconds.slots_200	0.36
report_calls.validate	400
report_calls.implementation	200
```

After implementation, for W7:

```text
python	3.14.2
sqlite	3.50.4
create_seconds.slots_1000	0.07
create_seconds.slots_4000	0.14
start_vm_steps.predecessors_100	128
start_vm_steps.predecessors_400	128
start_vm_steps.ratio_400_over_100	1.00
journal_bytes.full_history.total	15216601
journal_bytes.full_history.requests	14711785
journal_bytes.full_history.reply_bytes	202100
journal_bytes.history_sha256	unsupported (invalid plan fields)
report_seconds.slots_200	0.34
report_calls.validate	400
report_calls.implementation	200
```

## Evidence and remaining limits

- [Baseline full suite](v02_perf_correctness_tests_before.txt)
- Full suites: [W1](v02_perf_correctness_tests_W1.txt),
  [W2](v02_perf_correctness_tests_W2.txt), [W3](v02_perf_correctness_tests_W3.txt),
  [W4](v02_perf_correctness_tests_W4.txt), [W8](v02_perf_correctness_tests_W8.txt),
  [W5 after revert](v02_perf_correctness_tests_W5.txt),
  [W6](v02_perf_correctness_tests_W6.txt), [W7 final](v02_perf_correctness_tests_W7.txt).
- [W5 failed full-suite output](v02_perf_correctness_W5_conflict.txt)
- [Baseline benchmark](v02_perf_correctness_bench_before.txt) and
  [final benchmark](v02_perf_correctness_bench_after.txt)
- [Default-path compatibility output](v02_perf_correctness_compatibility.txt)
- [Supplied benchmark](../tools/bench_v02_scaling.py)

Noticed and left unchanged: `replay_manual_slot` can return `evidence_verified:
True` for a finished trace whose recomputed measurement is invalid; offline
replay instead records `invalid_finished_trace`. CLAUDE.md's historical
"no model runs" line is stale relative to later user-reported runs in public
provenance; CLAUDE.md was not edited. README/architecture/status also retain
historical statements about absent live execution alongside later implementation
entries; no unrelated documentation repair was made.

Full-history storage cost remains after W5's revert. Memoization, trickling
transport cleanup, streaming exports, graph-complexity changes, wall-limit and
interrupt policy, legacy v0.1 modules, corpus work and private history remain
outside this batch. Existing real evidence was neither searched nor rescored.
Claude's review remains pending.
