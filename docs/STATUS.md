# eTPS v0.2 status

Updated 2026-09-14. **No model benchmark runs have occurred in this v0.2 work. No manifest is frozen. No OpenTimestamps stamp or completed proof exists.** Paper reviews and structural checks on local authored data are not model runs. No claim is made about undisclosed historical activity outside this work.

## Published now

README, architecture, contributor/agent guidance, audit limitations and contract/review/provenance documents. This is pre-freeze documentation. The owner explicitly authorized publishing these docs before the manifest. The earlier manifest-first/docs-after commit order is superseded; the manifest-attested-before-run requirement remains intact.

This publication contains no manifest, corpus task file, tokenizer lock, token golden, or hash of any such artifact. Baseline Git commit identifiers refer to preserved code history, not a frozen experiment. The original v0.1 root documentation is preserved as clearly historical material.

## Settled design

RR is input-based and benchmark-authorized. Binary terminal acceptance is separate from first-attempt retention and measurement validity. Recovery requires a linked failure on the same active obligation and frozen-branch authorization. Scheduled input and recaps are identical across arms; authorized recovery may differ. TPS and RR are primary; eTPS is an experimental index. Same-system cross-profile metric mixing is prohibited by the proposed publication rule. System energy is withheld when backend measurement is unavailable.

The shared measurement tokenizer is selected as cl100k_base via tiktoken 0.12.0, independently of Gemini native accounting. Draft 3 rejects recovery endpoints that cut tokens. Actual tokenizer artifacts, dependency hashes and token goldens remain unverified because installation was blocked by network permissions. Encoding names alone do not establish comparability; the eventual lock must be frozen.

## Paused / next session

- Do not run calibration, stamp a manifest, repair scoring code or publish rankings yet.
- Obtain and verify tokenizer artifacts; validate every authored span against actual token boundaries and produce token goldens.
- Review corpus semantics and complete branch coverage; set retrieval/storage/context and timing ceilings in the profile.
- Set calibration pilot/trial counts after authoring and before execution. The first pilot is calibration, not a confirmatory comparison.
- Freeze exact manifest, lock and golden bytes; obtain completed independently verifiable OpenTimestamps proofs before run declarations and execution.

All attempts must be disclosed. An incomplete comparison is not a winner. Repairs require a newly frozen manifest and both-arm reruns. Known prior workload exposure is separately self-attested.

## Reading order

1. [Measurement contract](v0.2/MEASUREMENT_CONTRACT.md): draft 3; details marked proposed remain under review.
2. [Architecture](../ARCHITECTURE.md): preserved v0.1 modules versus proposed design.
3. [Clause review](v0.2/CLAUSE_REVIEW.md), [counterexamples](v0.2/COUNTEREXAMPLES.md), [acceptance/timing review](v0.2/ACCEPTANCE_TIMING_REVIEW.md): paper analysis, with older rules explicitly historical.
4. [Attestation decision](v0.2/ATTESTATION_DECISION.md) and [provenance](v0.2/PROVENANCE.md).
5. [v0.1 limitations](V0.1_STATUS.md).

Implementation remains at v0.1. This docs-only publication changes no Python code and supplies no validated scores.
