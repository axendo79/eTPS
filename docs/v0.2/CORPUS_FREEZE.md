# corpus-freeze-v1

Codex-authored tooling under user authorization. This tool hashes an exact
private corpus bundle; no corpus, human review or release is created by this
repository's synthetic tests. Hashing proves identity, not semantic correctness,
author independence, lack of prior exposure or execution. It is not independent
attestation; confirmatory use still requires the contract's external proofs.

API: `create_freeze(files, release_id, dataset, frozen_at)` returns canonical
record bytes. Receipt bytes must remain canonical; whitespace changes also fail.
`verify_freeze(files, record_bytes)` rechecks the complete byte
inventory and admission gates. `files` maps canonical relative POSIX filenames
to byte-exact contents. No date, budget or release name is invented: freeze time
is an explicit declaration. Same input and declarations yield the same bytes.

```text
python -B -m etps_v02.intake.corpus_freeze create PRIVATE_BUNDLE NEW_RECEIPT.json --release RELEASE_ID --dataset development --frozen-at DECLARED_TIME
python -B -m etps_v02.intake.corpus_freeze verify PRIVATE_BUNDLE RECEIPT.json
```

Create refuses an existing receipt; the receipt must be outside the inventoried
bundle. A second snapshot catches changes during preparation; verification also
runs after exclusive creation. A preparation/write interruption can leave an
unusable receipt: preserve the failure and start a new release, never overwrite
an old receipt. Verification rejects every added, removed or changed file. It
does not change permissions or prevent the filesystem from being edited: run
the verifier before every use and block use on failure.

The bundle includes **all files emitted by the mapper**, plus four required
records. Originals remain byte-exact; this tool never re-saves them.

| File | Required content |
|---|---|
| `authoring-brief.md` | Exact brief bytes actually given to the isolated session, including any neutral frozen-parameter appendix. |
| `authorship.json` | Closed `author-session-v1` record: version, author, model, session, date, affiliations (explicit string array), prior_exposure. |
| `settings.json` | Closed `corpus-settings-v1`: version, dataset, counts (exact mapper counts), parameters (nonempty object of declared design/budget settings), development_freeze_sha256. No numerical defaults are supplied. |
| `review.json` | Closed `corpus-review-v1`: version, reviewer, date, obligations_answer_keys_cross_checked (true), defects (empty array), artifacts (every other relative filename to exact SHA-256). |

`prior_exposure` is closed: declarant, date, corpus_version, prior_runs
(`yes`/`no`/`unknown`), known_runs (array), inspection (nonempty statement),
revisions (array). Known-run entries record known dates, counts and configurations;
unknown facts stay unknown. Affiliation and session statements are disclosures,
not an independence certificate. Model assistance must be explicit.

The reviewer first checks exact mapper/sidecar/obligation/key correspondence,
then hashes every artifact other than the review itself. The tool re-derives
all mapper bytes, re-runs sidecar intake, checks counts, and checks the review's
complete hash inventory. Any unresolved defect or missing cross-check blocks
freeze. A `semantics_verified: false` response is always returned: the tool
requires a declared review but cannot prove the review was performed correctly.

Sidecar intake dispatches from the exact binding version: v1.1 adds only the F9
missing-information query; v1 remains unchanged. The full v1.1 sidecar, exact
answer/status/identifier fields, field map and intake receipt are inventoried
and re-derived like every other artifact. Human review must additionally confirm
that the required missing item was never established before its question; a
declared empty history alone cannot prove faithful source interpretation.

Development and evaluation are separate directories and receipts. Development
settings have null development_freeze_sha256 and no parent receipt. Evaluation
requires `development-freeze.json`: a development receipt whose exact byte
SHA-256 equals settings.development_freeze_sha256. Dataset labels must match;
source hashes and task IDs must be distinct across the two releases. Task IDs
alone do not prove absence of content reuse or tuning: the [runbook](AUTHORING_RUNBOOK.md)
requires an untouched evaluation set. A development receipt's self-hash is checked;
verification of its original bundle must be retained separately.

Additional files (for example frozen plan/grouping/configuration/review evidence)
are also inventoried; none are silently excluded. The record includes release,
dataset, declared freeze time, brief/format versions, brief/source SHA-256,
task order, counts, every artifact path/hash/length/role, and a canonical payload
self-hash. The artifact list binds manifests (including branches), sidecars,
keys, predictions, field maps, counts, derivation logs and intake receipts.
Verify against a separately preserved trusted receipt; a malicious party can
rewrite both a bundle and its unsigned receipt coherently. Hashes do not replace
external attestation or the maintainer's release controls.

Refusal codes include `artifact_type`, `artifact_path`, `safety_limit`,
`missing_artifact`, `derived_bundle`, `dataset_separation`, `record_fields`,
`record_type`, `record_json`, `counts_mismatch`, `review_required`, `review_defect`,
`review_binding`, `brief_version`, `freeze_record`, `bundle_changed`,
`freeze_exists`, `file_unavailable`. Exit 0 means created/verified; exit 2 is refusal.
Software ceilings: 64 MiB/file, 256 MiB/bundle, 4,096 files; these are not
experiment budgets. Linked paths and noncanonical relative paths are refused.

Corrections after freeze require a new corpus release, new review, new receipt,
preserved old records and reruns of all comparison arms. They never repair an
old result silently. See [brief](AUTHORING_BRIEF.md), [format](AUTHORING_FORMAT_V1.md),
[mapper](AUTHORING_MAPPER.md), [aggregation](CORPUS_AGGREGATION.md) and
[state-record intake](STATE_RECORDS_V1.md).
