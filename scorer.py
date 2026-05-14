"""
eTPS Scorer — Core Calculation Engine
======================================
Pure math. No API calls. No I/O. Fully testable in isolation.
This is the foundation. Build everything else on top of this.

Spec version: v0.1
Author: Joshua Holliday / True Vector Media
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math


# ─────────────────────────────────────────────────────────────
# PENALTY CONSTANTS — LOCK THESE BEFORE v1.0 PUBLIC RELEASE
# Changing these after publication invalidates all prior results.
# ─────────────────────────────────────────────────────────────
PENALTY_HALLUCINATION       = 0.30
PENALTY_CORRECTION_ROUND    = 0.15
PENALTY_CORRECTION_MAX      = 0.45
PENALTY_TASK_FAILURE        = 0.50
PENALTY_REFUSAL             = 0.10
PENALTY_FORMAT_NONCOMPLIANCE= 0.05
PENALTY_RECONSTRUCTION      = 0.10

Q_FLOOR = 0.10
Q_CEILING = 1.00
C_FLOOR = 0.00
C_CEILING = 1.00

WASTE_WEIGHT_CORRECTION     = 0.40
WASTE_WEIGHT_RECONSTRUCTION = 0.40
WASTE_WEIGHT_REFUSAL        = 0.20

SPEC_VERSION = "v0.1"


class TaskCategory(Enum):
    FACTUAL_SINGLE  = "A"
    CONTINUITY      = "B"
    REASONING       = "C"
    MEMORY_AB       = "D"


@dataclass
class TokenCounts:
    total: int = 0
    correction: int = 0
    reconstruction: int = 0
    refusal: int = 0

    def __post_init__(self):
        if self.total < 0:
            raise ValueError("total tokens cannot be negative")
        if self.correction + self.reconstruction + self.refusal > self.total:
            raise ValueError(
                "waste token components exceed total — audit your counter. "
                f"total={self.total}, waste={self.correction + self.reconstruction + self.refusal}"
            )


@dataclass
class PenaltyRecord:
    hallucinations: int = 0
    correction_rounds: int = 0
    task_failed: bool = False
    unprompted_refusal: bool = False
    format_noncompliant: bool = False
    reconstruction_events: int = 0
    notes: list[str] = field(default_factory=list)

    def add_note(self, note: str):
        self.notes.append(note)


@dataclass
class ContinuityRecord:
    expected_context_items: int = 0
    retained_context_items: int = 0
    session_coherence_score: float = 1.0
    is_single_turn: bool = True

    def __post_init__(self):
        if not 0.0 <= self.session_coherence_score <= 1.0:
            raise ValueError(
                f"session_coherence_score must be 0.0-1.0, got {self.session_coherence_score}"
            )
        if self.retained_context_items > self.expected_context_items:
            raise ValueError(
                "retained_context_items cannot exceed expected_context_items"
            )


@dataclass
class ETSPResult:
    etps: float
    tps_raw: float
    efficiency_ratio: float
    waste_ratio: float
    quality_factor: float
    continuity_factor: float
    penalty_record: PenaltyRecord
    token_counts: TokenCounts
    spec_version: str = SPEC_VERSION

    def summary(self) -> str:
        lines = [
            f"eTPS:             {self.etps:.2f}",
            f"TPS (raw):        {self.tps_raw:.2f}",
            f"Efficiency ratio: {self.efficiency_ratio:.3f}",
            f"Quality factor:   {self.quality_factor:.3f}",
            f"Continuity factor:{self.continuity_factor:.3f}",
            f"Spec version:     {self.spec_version}",
            "",
            "Penalties fired:",
        ]
        p = self.penalty_record
        if p.hallucinations:
            lines.append(f"  Hallucinations:     {p.hallucinations} × {PENALTY_HALLUCINATION}")
        if p.correction_rounds:
            lines.append(f"  Correction rounds:  {p.correction_rounds} × {PENALTY_CORRECTION_ROUND}")
        if p.task_failed:
            lines.append(f"  Task failed:        -{PENALTY_TASK_FAILURE}")
        if p.unprompted_refusal:
            lines.append(f"  Unprompted refusal: -{PENALTY_REFUSAL}")
        if p.format_noncompliant:
            lines.append(f"  Format issue:       -{PENALTY_FORMAT_NONCOMPLIANCE}")
        if p.reconstruction_events:
            lines.append(f"  Reconstructions:    {p.reconstruction_events} × {PENALTY_RECONSTRUCTION}")
        if p.notes:
            lines.append("\nNotes:")
            for note in p.notes:
                lines.append(f"  - {note}")
        return "\n".join(lines)


def calculate_efficiency_ratio(tokens: TokenCounts) -> tuple[float, float]:
    if tokens.total == 0:
        return 0.0, 1.0

    waste_ratio = (
        (tokens.correction / tokens.total)     * WASTE_WEIGHT_CORRECTION +
        (tokens.reconstruction / tokens.total) * WASTE_WEIGHT_RECONSTRUCTION +
        (tokens.refusal / tokens.total)        * WASTE_WEIGHT_REFUSAL
    )

    waste_ratio = min(waste_ratio, 1.0)
    efficiency_ratio = 1.0 - waste_ratio

    return efficiency_ratio, waste_ratio


def calculate_quality_factor(penalties: PenaltyRecord) -> float:
    penalty_sum = 0.0

    hallucination_count = min(penalties.hallucinations, 3)
    penalty_sum += hallucination_count * PENALTY_HALLUCINATION

    if not penalties.task_failed:
        correction_penalty = min(
            penalties.correction_rounds * PENALTY_CORRECTION_ROUND,
            PENALTY_CORRECTION_MAX
        )
        penalty_sum += correction_penalty

    if penalties.task_failed:
        penalty_sum += PENALTY_TASK_FAILURE

    if penalties.unprompted_refusal:
        penalty_sum += PENALTY_REFUSAL
    if penalties.format_noncompliant:
        penalty_sum += PENALTY_FORMAT_NONCOMPLIANCE

    reconstruction_penalty = min(
        penalties.reconstruction_events * PENALTY_RECONSTRUCTION,
        0.30
    )
    penalty_sum += reconstruction_penalty

    q = max(Q_FLOOR, min(Q_CEILING, 1.0 - penalty_sum))
    return q


def calculate_continuity_factor(record: ContinuityRecord) -> float:
    if record.is_single_turn:
        return 1.0

    if record.expected_context_items == 0:
        return max(C_FLOOR, min(C_CEILING, record.session_coherence_score))

    retention_ratio = record.retained_context_items / record.expected_context_items
    c = retention_ratio * record.session_coherence_score

    return max(C_FLOOR, min(C_CEILING, c))


def calculate_etps(
    tps_raw: float,
    tokens: TokenCounts,
    penalties: PenaltyRecord,
    continuity: ContinuityRecord,
) -> ETSPResult:
    if tps_raw < 0:
        raise ValueError(f"tps_raw cannot be negative, got {tps_raw}")
    if tps_raw == 0:
        return ETSPResult(
            etps=0.0, tps_raw=0.0, efficiency_ratio=0.0, waste_ratio=1.0,
            quality_factor=Q_FLOOR,
            continuity_factor=calculate_continuity_factor(continuity),
            penalty_record=penalties, token_counts=tokens,
        )

    efficiency_ratio, waste_ratio = calculate_efficiency_ratio(tokens)
    quality_factor = calculate_quality_factor(penalties)
    continuity_factor = calculate_continuity_factor(continuity)

    etps = tps_raw * efficiency_ratio * quality_factor * continuity_factor

    return ETSPResult(
        etps=round(etps, 4), tps_raw=round(tps_raw, 4),
        efficiency_ratio=round(efficiency_ratio, 4),
        waste_ratio=round(waste_ratio, 4),
        quality_factor=round(quality_factor, 4),
        continuity_factor=round(continuity_factor, 4),
        penalty_record=penalties, token_counts=tokens,
    )


# ─────────────────────────────────────────────────────────────
# eSCORE — normalized readability scale derived from eTPS
# Default: 0-100. Pass allow_bonus=True for Nyx A/B comparisons
# where the delta above baseline is the signal being published.
# reference_tps is per hardware profile, not a global constant.
# ─────────────────────────────────────────────────────────────

def calculate_escore(
    etps: float,
    reference_tps: float,
    allow_bonus: bool = False,
) -> int:
    """
    Normalize eTPS to a human-readable integer score.

    eScore = round((eTPS / reference_tps) × 100)

    Default (allow_bonus=False): capped at 100. Use for general
    leaderboard display where 0-100 intuitive meaning matters.

    allow_bonus=True: uncapped. Use for Nyx A/B comparisons where
    the delta above 100 is the published signal — e.g. eScore 107
    demonstrates memory system value above the no-memory baseline.

    reference_tps should be declared per hardware profile, not as
    a global constant. A Legion 5i reference differs from an
    X1 Pro-470 reference. Store it in the hardware declaration.
    """
    if reference_tps <= 0:
        raise ValueError("reference_tps must be positive")
    if etps < 0:
        raise ValueError("etps cannot be negative")

    raw = round((etps / reference_tps) * 100)
    return raw if allow_bonus else min(100, raw)


if __name__ == "__main__":
    print("Running eTPS scorer self-tests...\n")

    result = calculate_etps(
        tps_raw=50.0,
        tokens=TokenCounts(total=500),
        penalties=PenaltyRecord(),
        continuity=ContinuityRecord(is_single_turn=True),
    )
    assert result.etps == 50.0, f"Test 1 failed: got {result.etps}"
    print(f"Test 1 PASS — Perfect run: eTPS={result.etps}")

    result = calculate_etps(
        tps_raw=50.0,
        tokens=TokenCounts(total=1000, correction=400),
        penalties=PenaltyRecord(correction_rounds=2),
        continuity=ContinuityRecord(is_single_turn=True),
    )
    expected = round(50.0 * (1 - 0.4 * 0.4) * (1 - 2 * 0.15), 4)
    assert abs(result.etps - expected) < 0.01, f"Test 2 failed: got {result.etps}"
    print(f"Test 2 PASS — Correction waste: eTPS={result.etps}")

    result = calculate_etps(
        tps_raw=50.0,
        tokens=TokenCounts(total=200),
        penalties=PenaltyRecord(task_failed=True),
        continuity=ContinuityRecord(is_single_turn=True),
    )
    assert result.quality_factor == 0.50
    assert result.etps == 25.0
    print(f"Test 3 PASS — Task failure: eTPS={result.etps}")

    result = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=800, reconstruction=80),
        penalties=PenaltyRecord(reconstruction_events=1),
        continuity=ContinuityRecord(
            expected_context_items=5, retained_context_items=3,
            session_coherence_score=0.8, is_single_turn=False,
        ),
    )
    assert result.continuity_factor == 0.48
    print(f"Test 4 PASS — Multi-turn: eTPS={result.etps}, C={result.continuity_factor}")

    cold = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=1000, reconstruction=200),
        penalties=PenaltyRecord(reconstruction_events=2),
        continuity=ContinuityRecord(
            expected_context_items=5, retained_context_items=2,
            session_coherence_score=0.6, is_single_turn=False),
    )
    nyx = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=1000, reconstruction=20),
        penalties=PenaltyRecord(),
        continuity=ContinuityRecord(
            expected_context_items=5, retained_context_items=5,
            session_coherence_score=0.95, is_single_turn=False),
    )
    assert nyx.etps > cold.etps
    print(f"Test 5 PASS — Nyx vs Cold: {nyx.etps:.2f} > {cold.etps:.2f}")

    result = calculate_etps(
        tps_raw=0.0, tokens=TokenCounts(total=0),
        penalties=PenaltyRecord(), continuity=ContinuityRecord(is_single_turn=True),
    )
    assert result.etps == 0.0
    print(f"Test 6 PASS — Zero TPS: eTPS={result.etps}")

    # eScore — capped mode (default)
    assert calculate_escore(50.0, 50.0) == 100
    assert calculate_escore(0.0, 50.0) == 0
    assert calculate_escore(25.0, 50.0) == 50
    assert calculate_escore(31.5, 50.0) == 63
    assert calculate_escore(55.0, 50.0) == 100   # capped
    # eScore — bonus mode (Nyx A/B)
    assert calculate_escore(55.0, 50.0, allow_bonus=True) == 110
    assert calculate_escore(50.0, 50.0, allow_bonus=True) == 100
    try:
        calculate_escore(10.0, 0.0)
        assert False, "Should have raised"
    except ValueError:
        pass
    print(f"Test 7 PASS — eScore: capped default + allow_bonus delta visible")

    print(f"\n{'='*50}")
    print(f"All tests passed. Spec version: {SPEC_VERSION}")
    print(f"{'='*50}\n")

    sample = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=800, reconstruction=80),
        penalties=PenaltyRecord(reconstruction_events=1, notes=["Context partially lost at turn 3"]),
        continuity=ContinuityRecord(
            expected_context_items=5, retained_context_items=3,
            session_coherence_score=0.8, is_single_turn=False),
    )
    print(sample.summary())
    print(f"\neScore (ref=40.0):              {calculate_escore(sample.etps, 40.0)}")
    print(f"eScore allow_bonus (ref=40.0):  {calculate_escore(sample.etps, 40.0, allow_bonus=True)}")
