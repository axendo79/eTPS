# Attestation decision: OpenTimestamps

Selected 2026-09-14 by Codex in response to the user's instruction to choose a mechanism. This is a documented design choice, not an executed stamp, freeze, commit or run. The first pilot is calibration; it estimates variability and protocol coverage, not confirmatory evidence of superiority.

## Mechanism and reason

Use OpenTimestamps with a completed Bitcoin-backed proof for the exact manifest bytes. Public calendars submit commitments; the proof permits verification against Bitcoin independently of the project. The service's calendar submission receipt is not sufficient: wait for an upgraded, verifiable Bitcoin attestation. Publish the original manifest and its .ots proof together so a stranger need not request either from the author.

Sources: [OpenTimestamps specification overview](https://opentimestamps.org/) and [official client instructions](https://github.com/opentimestamps/opentimestamps-client). The official client supports independent verification with a local Bitcoin Core node, including a pruned node. Hosted verification is convenient but adds trust in that verifier. Calendar servers are not relied upon as the final time authority once the Bitcoin proof is complete.

## Project procedure

1. Finish the corpus and calibration manifest. Include hashes of all scoring-relevant files, actual fixed pilot/trial counts, configuration, tokenizer, budgets, prior-exposure declaration, and this attestation policy. Commit manifest-only when explicitly authorized.
2. Stamp the exact manifest file, archive the receipt, upgrade to a completed Bitcoin proof, and verify it. Our conservative policy requires six confirmations of its anchoring block; this is a chosen project parameter, not an OpenTimestamps guarantee. Pin the verification tool version and preserve block height/hash and verification output.
3. Publish downloadable manifest and proof before starting the pilot. File hosting is distribution, not the authority for time. A changed file will not verify against the original proof; a deleted file makes the public claim unverifiable until the bundle is restored. Pre-freeze documentation may already be public; it is not freeze evidence.
4. Prepare a run-start declaration with the manifest hash, proof hash, anchoring block hash/height, planned run IDs and prior-exposure statement. Timestamp this declaration with OpenTimestamps too; require its verified anchor to be in a later block and meet the same confirmation policy before executing the declared run. Preserve and publish both proofs with results.
5. Protocol repairs require a new manifest, new completed freeze proof and new run-start declaration; rerun both arms and retain prior attempts. Never reuse a successful old arm under the new manifest.

### Waiting and exact-byte gate

Execution is blocked until both proof-verification and confirmation gates above pass. No fixed number of minutes substitutes for those conditions, and an unfinished gate cannot be waived to fit a session. The workflow may span sessions, but same-session completion is not intrinsically prohibited. Record receipt, anchor, verification and observed confirmation events separately. Six confirmations is a conservative operational choice, not absolute finality; recheck anchors before accepting the record chain.

Preserve the exact manifest bytes, completed `.ots` file and the stamped run-start declaration with its own proof in a publicly downloadable evidence bundle. Record SHA-256, byte length, UTF-8 encoding and newline policy for each text artifact. The release authoring convention is UTF-8 without BOM and LF; serialize once and hash those actual bytes. Verification hashes the stored bytes without trimming, parsing/reserializing or newline normalization. CRLF-converted or newline-modified copies are different artifacts and cannot substitute for the stamped original. Download and verify the published bytes before execution. Git checkout conversion must not be trusted; preserve the stamped files as binary release assets, and keep proofs as binary throughout. A newer upgraded proof is retained with its own hash and linked to the earlier receipt, not confused with unchanged proof bytes.

## Exact evidentiary claim

The proof establishes a cryptographic commitment to those manifest bytes by the anchoring block. It does not prove when the full document first became publicly readable, exact wall-clock execution time, actual compliance by the runner, or absence of earlier experiments. Run-start stamping is an externally anchored declaration, not a witness observing execution. Referencing the first anchor in a declaration anchored later establishes the intended record chain; actual execution still requires trace evidence and attributable disclosure. Use block order rather than comparing project-authored dates or treating block timestamps as precise stopwatches.

If independent witnessing of actual execution becomes required, this design alone is insufficient and a separately reviewed execution-attestation mechanism will be needed. No such stronger claim is made by the current contract.

## Calibration versus later comparison

Choose and freeze the first pilot count after the corpus is authored and before any pilot execution. Report variability, coverage and all attempted outcomes; no stopping on favorable results. A later confirmatory manifest defines the meaningful effect, planning method, new count and fresh run schedule using the disclosed calibration observations. Calibration is evidence about variability and feasibility, not confirmation of the memory-layer benefit. Do not reuse calibration outcomes as if they were fresh confirmatory trials. Counts are not selected here.

The calibration manifest must declare `purpose=calibration` and prohibit superiority, winner and confirmatory-comparison claims from those trials. Preserve arm-specific raw outcomes and paired observations for variance planning and audit; this restriction must not hide unfavorable data. The later planning method must acknowledge uncertainty in pilot variance estimates.


Golden binding: the stamped manifest must commit to exact tokenizer-lock and token-golden file hashes and byte lengths. Publish those exact files with the manifest and completed proof. A manifest commitment covers its referenced golden hashes; individual separate stamps are optional, not required. A changed golden requires a new manifest and attestation, never an in-place replacement. Goldens remain ungenerated while tokenizer execution is blocked.
