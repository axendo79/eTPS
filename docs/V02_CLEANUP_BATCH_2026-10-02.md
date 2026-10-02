# Cleanup batch handoff (2026-10-02)

Codex implemented the user-authorized cleanup batch from Claude's model-authored
rev 4 work order and exact C1/C2 patches. All three supplied SHA256 hashes
matched. Branch: `v02-cleanup-batch`. Base: `642ada5`
(`642ada5111ed31e1bea4abadde7eac35f5391452`), main with W5 merged.
`codex-handoff` supplied files only; it was not merged, rebased onto, or used
as the work base.

## Results

- C1, `0ad243d`: applied the supplied manual-evidence patch. Invalid finished
  measurements report unverified evidence and both required warnings. Three
  new tests cover valid, edited/rechained, unattempted, aborted and running
  evidence. Full suite: 277 passing.
- C2, `dd87980`: applied the supplied processing-totals patch. Six new tests
  cover the exact 280/32 token example, rejected facts, non-memory totals,
  incomplete usage/telemetry and export replay. Full suite: 283 passing.
- C3: documented the diagnostics and manual-evidence rule, updated the README
  repository map, appended status, and wrote this handoff. Full suite before
  commit: 283 passing.

Baseline: 274 passing. Final: 283 passing, nine new tests. Tests used
`python -B -m unittest discover -s tests -v`, synthetic inputs and ephemeral
loopback fake servers only. SHA256 comparisons confirm all 26 pre-existing
test files stayed byte-for-byte unchanged.

The initial C1 application was denied by the sandbox; an elevated retry
succeeded. A mistakenly started test process had already imported the
unpatched code and failed the new invalid-evidence regression (277 tests,
one failure). Work stopped without commits. On the user's continuation,
C1 passed `git apply --reverse --check` and a fresh full suite passed all
277 tests before its commit. C2 passed both forward and reverse checks,
with application completed before tests began. No patch redesign was needed.

## Test-file diff

`git diff --stat 642ada5 -- tests/`:

```text
 tests/test_v02_manual_evidence.py   |  67 +++++++++++++++++++++++
 tests/test_v02_processing_totals.py | 102 ++++++++++++++++++++++++++++++++++++
 2 files changed, 169 insertions(+)
```

`git diff --name-status 642ada5 -- tests/` reports only these two added
files; no existing tests changed.

No additional issues were identified within this scope. No model runs,
LM Studio or real endpoints, private data, installs, push or PR. ProjectNotes
and per-run test logs were not staged or committed. Stop after the three
local commits for Claude's review; synthetic tests do not establish
benchmark validity or independent review.
