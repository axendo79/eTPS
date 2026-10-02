# W5 request journal handoff (2026-10-02)

Implemented on `v02-w5-request-journal` from `a2f3896443b08801bbb33be7b3ad021adc01a322`.
Code is Claude's model-authored reference patch, applied without redesign;
Codex authored the new regressions and documentation. Synthetic checks establish
software behavior, not model performance or independent benchmark validity.

## Setup and instruction override

`Get-FileHash -Algorithm SHA256` matched both required values:

- `CODEX_WORK_ORDER_W5_redo.md`: `6e557518e5be3b5a7a81fe064b50cdbd15351d6a0307ea752de5686727ae064b`
- `W5_reference.patch`: `8c4649edc77a078ba6257084035a78f58eff436aded63b1e53b20c0368bff79d`

The existing branch was selected; no new branch was created. Baseline suite
and bench ran before application. `git apply --check` passed. The first apply
was blocked by sandbox file permissions and left no changes; the identical
command succeeded with permission outside the sandbox. A reverse patch check
confirmed that the supplied code changes were applied intact.

The user explicitly corrected work-order test 2.4 because its original
zero-message expectation conflicted with the existing boundary authoring rule.
The first reset-v1 request contains only user messages delivered after the
boundary: one in the standard fixture. Its count and hash cover those messages
only. Replay passes; a re-chained export with a tampered post-boundary
`messages_sha256` is rejected with `request history mismatch`. This is an
instruction override; neither the work-order file nor the patch was edited.

## Validation

Commands used the installed Windows Python executable with `-B`:
`python -B -m unittest discover -s tests -v` and
`python -B tools/bench_v02_scaling.py`. Runtime: Python 3.14.2, SQLite 3.50.4.
Complete outputs were saved in the temporary directory as
`w5-baseline-tests.txt`, `w5-baseline-bench.txt`, `w5-after-tests.txt`, and
`w5-after-bench.txt`; no per-run logs are committed.

Baseline unittest summary:

```text
----------------------------------------------------------------------
Ran 264 tests in 39.829s

OK
```

Final unittest summary:

```text
----------------------------------------------------------------------
Ran 274 tests in 43.455s

OK
```

All ten new tests passed separately, then in the full suite. Coverage includes
offline score/event equivalence, exact request field sets and hashes, 50-turn
size bounds, re-chained count/hash/text/extra-field tampering, the corrected
reset case, both requested live providers, v2 round-trips, deliver-v1 under
full/reset with moved/retyped-intent rejection, and plan-field validation
including list-valued schema rejection as InvalidRecord.

SHA256 comparison confirmed all 25 pre-existing test files are byte-for-byte
unchanged. `git diff --stat a2f3896 -- tests/`:

```text
 tests/test_v02_request_journal.py | 223 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 223 insertions(+)
```

## Bench output

Before:

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
report_seconds.slots_200	0.79
report_calls.validate	400
report_calls.implementation	200
```

After:

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
journal_bytes.history_sha256.total	516651
journal_bytes.history_sha256.requests	11835
journal_bytes.history_sha256.reply_bytes	202100
report_seconds.slots_200	0.60
report_calls.validate	400
report_calls.implementation	200
```

Hash-mode requests are below 20,000 bytes and total journal size is below
600,000 bytes. Default full-history sizes are unchanged. Timings are informational.
The Windows journal totals are one byte below the work order's Linux figures;
the request byte counts match exactly. No benchmark code was changed.

## Delivery and scope

Feature commit: `5c0dda9` (`feat: add opt-in hashed request history`). The second
commit contains only OFFLINE_RUNNER, LIVE_ADAPTER, the STATUS append, and this
handoff, with a `docs:` subject. Stop for Claude's review after that commit.

Only synthetic fixtures and ephemeral loopback fake servers were used. No model
runs, LM Studio or real endpoints, private data, installs, push or PR. ProjectNotes
was never staged. No existing test was edited. No other implementation issues
were identified or changed; the instruction conflict and platform byte-count
difference are recorded above. Full request histories remain the default, and
user text and response bytes remain journaled even in hash mode.
