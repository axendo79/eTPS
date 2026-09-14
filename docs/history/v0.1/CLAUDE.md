# eTPS — Effective Tokens Per Second

Quality-adjusted local AI inference benchmark. Complements raw TPS.

## Spec version: v0.1 (PRE-RELEASE — do not publish numbers yet)

## File map
- scorer.py       — Core formula. Pure math. No I/O. Test this first.
- logger.py       — SQLite persistence. WAL mode. Schema versioned.
- task_validator.py — First real task. Run against live endpoint to validate pipeline.
- seit.py         — Power-normalized companion metric (SEIT).
- user_profile.py — User accounts, hardware profiles, consent, partner export.
- leaderboard.py  — Ranking, filtering, JSON export.
- CONTRIBUTING.md — Submission format and validation rules.

## Formula
eTPS = TPS_raw × Efficiency × Quality × Continuity

Efficiency = 1 - waste_ratio  (token waste proxies only)
Quality    = f(penalty record) (correctness only, independent of token counts)
Continuity = f(context retention) (multi-turn sessions only)

eScore = round((eTPS / reference_tps) × 100), capped at 100 by default.
Pass allow_bonus=True to expose delta above baseline for A/B comparisons.

## Critical constraints
- Efficiency and Quality are INDEPENDENT. Correction rounds affect Quality only.
- C factor ceiling is 1.0. No bonus multiplier above 1.0.
- Penalty constants in scorer.py are LOCKED until v1.0 release.
- Judge model must be versioned. Default: open model, locally runnable.
- All SQLite writes use WAL mode. foreign_keys=ON always.

## Do not
- Change penalty multiplier values without creating a new spec version
- Allow eTPS to exceed TPS_raw (formula error if this happens)
- Use ORM — raw SQL only for auditability
- Add frontend before scorer and logger are validated on real hardware

## Claude Code instructions
- Always read the current committed file before modifying. Never reconstruct from memory.

## Run order
1. python scorer.py          # Self-tests, no dependencies
2. python logger.py          # Smoke test, no API needed
3. python task_validator.py --base-url http://localhost:1234/v1 --model YOUR_MODEL

## Tech stack
Python 3.11+, SQLite (WAL), openai SDK (for API calls), no heavy frameworks
