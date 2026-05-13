"""
eTPS Task Validator — First Real Task
=======================================
A hardcoded single task that validates the full pipeline end-to-end
against a live local inference endpoint.

Run this BEFORE building automated task runners.
This tells you exactly what the logger needs to record.

Requirements:
  pip install openai

Usage:
  python task_validator.py --base-url http://localhost:1234/v1 --model "qwen3.5-9b"
"""

import argparse
import time
import re
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("pip install openai")

from scorer import (
    calculate_etps, TokenCounts, PenaltyRecord, ContinuityRecord, ETSPResult
)


# ─────────────────────────────────────────────────────────────
# TASK DEFINITION: B1 — Factual Context Retention
# Category B — multi-turn continuity
# ─────────────────────────────────────────────────────────────
TASK_ID = "B1_context_retention_v0.1"
TASK_CATEGORY = "B"

ESTABLISHED_FACTS = {
    "database": "SQLite",
    "mode": "WAL mode",
    "language": "Python 3.11",
    "model": "Qwen 3.5 9B",
    "hardware": "Legion 5i",
}

TURN_1 = (
    "I'm working on a project called NyxCore. It uses SQLite with WAL mode, "
    "Python 3.11, runs on a Legion 5i, and the primary inference model is Qwen 3.5 9B. "
    "Acknowledge that you've noted these details."
)

TURN_2 = "What are the main advantages of using WAL mode in SQLite for an AI memory system?"

TURN_3 = (
    "Given what you know about my project's database setup, "
    "how would you structure the decay scoring queries for efficiency?"
)

TURN_3_EXPECTED_REFERENCES = ["sqlite", "wal"]

RECONSTRUCTION_PATTERNS = [
    r"as (i |you |we )?(mentioned|noted|said|discussed)",
    r"to (recap|summarize|review)",
    r"earlier (you |i |we )?(mentioned|said|told me|established)",
    r"going back to",
    r"as previously (mentioned|noted|established)",
]


@dataclass
class TaskRunResult:
    """Raw output from a single task run before scoring."""
    turn_responses: list[str]
    total_tokens: int
    reconstruction_tokens: int
    reconstruction_events: int
    correction_rounds: int
    correction_tokens: int
    context_references_found: list[str]
    elapsed_seconds: float
    tps_raw: float


def detect_reconstruction(text: str) -> bool:
    """Detect if model is re-establishing context rather than using it."""
    text_lower = text.lower()
    for pattern in RECONSTRUCTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def check_context_reference(text: str, expected_refs: list[str]) -> list[str]:
    """Check which expected context items are referenced in the response."""
    text_lower = text.lower()
    return [ref for ref in expected_refs if ref in text_lower]


def run_task(
    client: OpenAI,
    model: str,
    seed: int = 42,
) -> TaskRunResult:
    """
    Execute the three-turn task against the inference endpoint.
    Returns raw observations before scoring.
    """
    conversation = []
    turn_responses = []
    total_tokens = 0
    reconstruction_tokens = 0
    reconstruction_events = 0
    correction_rounds = 0
    correction_tokens = 0
    context_references_found = []

    start = time.perf_counter()

    turns = [TURN_1, TURN_2, TURN_3]

    for i, turn_prompt in enumerate(turns):
        conversation.append({"role": "user", "content": turn_prompt})

        response = client.chat.completions.create(
            model=model,
            messages=conversation,
            seed=seed,
            temperature=0.7,
            stream=False,
        )

        assistant_text = response.choices[0].message.content
        usage = response.usage

        turn_tokens = usage.completion_tokens if usage else len(assistant_text.split()) * 1.3
        total_tokens += turn_tokens

        if i >= 1 and detect_reconstruction(assistant_text):
            reconstruction_events += 1
            reconstruction_tokens += int(turn_tokens * 0.3)
            print(f"  ⚠ Reconstruction detected in turn {i+1}")

        if i == 2:
            found = check_context_reference(assistant_text, TURN_3_EXPECTED_REFERENCES)
            context_references_found = found
            if not found:
                print(f"  ⚠ Turn 3: No expected context references found")
            else:
                print(f"  ✓ Turn 3: Referenced: {found}")

        conversation.append({"role": "assistant", "content": assistant_text})
        turn_responses.append(assistant_text)

        print(f"  Turn {i+1}: {turn_tokens:.0f} tokens")

    elapsed = time.perf_counter() - start
    tps_raw = total_tokens / elapsed if elapsed > 0 else 0

    return TaskRunResult(
        turn_responses=turn_responses,
        total_tokens=int(total_tokens),
        reconstruction_tokens=reconstruction_tokens,
        reconstruction_events=reconstruction_events,
        correction_rounds=correction_rounds,
        correction_tokens=correction_tokens,
        context_references_found=context_references_found,
        elapsed_seconds=elapsed,
        tps_raw=tps_raw,
    )


def score_task(raw: TaskRunResult) -> ETSPResult:
    """Convert raw task observations into eTPS score."""
    expected_items = len(TURN_3_EXPECTED_REFERENCES)
    retained_items = len(raw.context_references_found)
    task_failed = retained_items == 0

    penalties = PenaltyRecord(
        correction_rounds=raw.correction_rounds,
        task_failed=task_failed,
        reconstruction_events=raw.reconstruction_events,
    )
    if task_failed:
        penalties.add_note("Turn 3 failed to reference any established context")

    tokens = TokenCounts(
        total=raw.total_tokens,
        correction=raw.correction_tokens,
        reconstruction=raw.reconstruction_tokens,
        refusal=0,
    )

    continuity = ContinuityRecord(
        expected_context_items=expected_items,
        retained_context_items=retained_items,
        session_coherence_score=0.9 if retained_items == expected_items else 0.6,
        is_single_turn=False,
    )

    return calculate_etps(
        tps_raw=raw.tps_raw,
        tokens=tokens,
        penalties=penalties,
        continuity=continuity,
    )


def main():
    parser = argparse.ArgumentParser(description="eTPS Task Validator")
    parser.add_argument("--base-url", default="http://localhost:1234/v1",
                        help="OpenAI-compatible API base URL")
    parser.add_argument("--model", required=True,
                        help="Model name as known to the server")
    parser.add_argument("--runs", type=int, default=3,
                        help="Number of runs (min 3 for published results)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    client = OpenAI(base_url=args.base_url, api_key="not-required")

    print(f"\neTPS Task Validator")
    print(f"Task:     {TASK_ID}")
    print(f"Model:    {args.model}")
    print(f"Endpoint: {args.base_url}")
    print(f"Runs:     {args.runs}")
    print(f"Seed:     {args.seed}")
    print("=" * 50)

    results = []

    for run_num in range(1, args.runs + 1):
        print(f"\nRun {run_num}/{args.runs}:")
        try:
            raw = run_task(client, args.model, seed=args.seed)
            result = score_task(raw)
            results.append((raw, result))
            print(f"  eTPS: {result.etps:.2f} | TPS: {result.tps_raw:.2f} | "
                  f"Q: {result.quality_factor:.3f} | C: {result.continuity_factor:.3f}")
        except Exception as e:
            print(f"  Run {run_num} failed: {e}")

    if not results:
        print("\nAll runs failed. Check your endpoint and model name.")
        return

    print(f"\n{'='*50}")
    print(f"Results across {len(results)} runs:")

    etps_values = [r.etps for _, r in results]
    tps_values = [raw.tps_raw for raw, _ in results]

    etps_median = sorted(etps_values)[len(etps_values) // 2]
    tps_median = sorted(tps_values)[len(tps_values) // 2]

    print(f"  eTPS median:    {etps_median:.2f}")
    print(f"  eTPS range:     {min(etps_values):.2f} – {max(etps_values):.2f}")
    print(f"  TPS median:     {tps_median:.2f}")
    print(f"  eTPS/TPS ratio: {etps_median/tps_median:.3f}")

    cv = (max(etps_values) - min(etps_values)) / etps_median if etps_median > 0 else 0
    stability = "STABLE" if cv < 0.10 else "HIGH VARIANCE — check thermal state"
    print(f"  Variance (CV):  {cv:.3f} — {stability}")

    print(f"\nSample penalty detail (run 1):")
    _, r1 = results[0]
    print(r1.summary())


if __name__ == "__main__":
    main()
