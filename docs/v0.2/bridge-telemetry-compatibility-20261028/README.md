# Bridge telemetry compatibility: decision packet

**Decision-gated; no implementation or contract change.** Composite bridge-v2
telemetry retains its raw costs but does not satisfy eTPS's accepted flat
telemetry shape. The [six-case synthetic proof](proof-results.json) demonstrates
invalid projection and zero coverage, with combined totals correctly remaining
null. This is a compatibility gap, not evidence of measured zero cost or a
benchmark advantage.

- [Mapping decision brief](MAPPING_DECISION_BRIEF.md): recommends an explicit
  producer compatibility mode; gives a versioned consumer mapping alternative.
- [Authority checklist](CONTRACT_AUTHORITY_CHECKLIST.md) and
  [disposition](CONTRACT_DISPOSITION.md): accepted rules versus unresolved
  decisions. [PR 35](https://github.com/axendo79/eTPS/pull/35) remains an
  unaccepted, separate telemetry draft.
- [Retention trace](RETENTION_REVIEW.md): failed HTTP bodies/status/hashes,
  request/event journals, first-attempt retention and unavailable denominators.

The source review used revision `ed1dd7c3de2f315f9a38e55406c22b548b22359c`.
The publication branch starts from main
`c2e43bca780a160677d65d37e79f25ab977b3920`; the four proof source hashes match.
No runtime, schema, scorer, acceptance, workload, or qualification permission
changes are made. This packet is outside Gate 3 qualification.

## Reproduce the pure proof

Run from the repository root with Python 3; choose an absent output file:

```sh
python -B docs/v0.2/bridge-telemetry-compatibility-20261028/prove_composite_projection.py --repo-root . --output /path/to/new-proof-results.json
```

The script AST-extracts explicitly selected definitions from four hash-pinned
source files, with standard-library dependencies. It imports no repository
package and uses synthetic response bytes and in-memory rows only. It refuses
changed source hashes and existing output files. It reads no corpus or store
and makes no network, model or native calls. It does not execute adapter
dispatch, journal durability, manifest routing or scoring.

The exact source pins identify the reviewed **CRLF working-tree bytes**.
Reproduce with a fresh checkout configured with Git `core.autocrlf=true` for
these source files. LF-only copies intentionally fail the hash guard. The
explicit path arguments are portable; the script does not normalize source
bytes, accept additional hashes, or revise pins automatically.

| Case | Current behavior |
| --- | --- |
| Flat scalar control | valid; known costs covered |
| Nested receipt list | invalid; raw costs retained; projected coverage 0 |
| Boolean status flag | invalid; raw costs retained; projected coverage 0 |
| Composite bridge-v2 shape | invalid; raw costs retained; projected coverage 0 |
| Failed 502 then cached 200 | two synthetic events; raw calls `[1,0]`; known extraction usage 8/4; incomplete combined costs null |
| Flat unknown usage | valid; unknown usage stays null and uncovered |

The failure/retry pair is projection evidence, not an executed HTTP or model
session. Both failed and retried attempts remain explicit; a cached zero means
zero new extraction only when reported. Unknown cost is never inferred as zero.
The eTPS profile author develops Nyx and controls the comparison arms; that
affiliation remains disclosed, and Nyx must be allowed to lose. Model-authored
proposals and synthetic software evidence do not establish benchmark validity.
