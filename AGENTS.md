# eTPS contributor context

Implementation: v0.1 at baseline `ea51ce82e011c7e65bdc43e9d5af923cdcec4897` remains preserved; the experimental v0.2 byte scorer, offline/live/manual runners and SQLite journal are implemented. Local runs 7 and 8 are exploratory calibration only. The state-evolution authoring pipeline merged in PR #25; the next stage is authoring a development corpus per [AUTHORING_RUNBOOK.md](docs/v0.2/AUTHORING_RUNBOOK.md), using an isolated author given only [AUTHORING_BRIEF.md](docs/v0.2/AUTHORING_BRIEF.md). Read [README](README.md), [architecture](ARCHITECTURE.md), [status](docs/STATUS.md), [contract](docs/v0.2/MEASUREMENT_CONTRACT.md) and [provenance](docs/v0.2/PROVENANCE.md).

## Required working rules

- Read the current file before changing it; preserve user edits and the historical baseline.
- Executable counterexamples and pure scorer → reviewed workload/criteria/budgets → runner/persistence → calibration → independently attested confirmation.
- RR stays input-based, using character-aligned UTF-8 bytes and benchmark-designated obligations. TPS and RR are primary; eTPS is experimental. Do not restore v0.1's four-factor composition or eScore in v0.2.
- Binary terminal acceptance is separate from first-attempt retention and measurement validity. Retain failed and unavailable trials.
- Scripted recovery requires the linked failure, same active obligation and authorized branch. No treatment-dependent user recaps or private answer-key leakage.
- No model judge or fuzzy matching for the finite deterministic pilot. Unknown user payload and wrong model answer are different outcomes.
- Nyx must be allowed to lose. Disclose profile-author/system affiliation.
- Do not expand website, leaderboard, accounts or SEIT before validity work.
- Do not run legacy endpoint demos as if they were v0.2 validation; no dependencies are needed for document review.
- No commit or push without explicit instruction. The current user authorized local implementation, executable synthetic fixtures and affected policy updates; no model runs or remote publication were performed.

## Existing files

`scorer.py`: old arithmetic; `task_validator.py`: endpoint demo; `logger.py`: SQLite storage; `seit.py`: old companion calculations; `user_profile.py` and `leaderboard.py`: ancillary legacy utilities. Their existence does not imply complete v0.2 behavior. Preserve SQLite/raw-SQL conventions and old constants until versioned implementation work is authorized.

Update documentation with actual behavior and evidence. Model-authored proposals and paper cases must remain labeled. Earlier instructions are preserved under `docs/history/v0.1/`; they do not override the current contract or user directions.
