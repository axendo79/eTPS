"""
SEIT — Sustained Effective Inference Throughput
=================================================
Power-normalized sustained throughput metric.
Companion to eTPS. Exposes thermal efficiency under load.

Formula: SEIT = (eTPS_sustained × Quality Factor) / Watts

Where:
    eTPS_sustained = median eTPS over a 15-minute continuous inference window
    Quality Factor = from the same session's scorer output
    Watts          = measured or declared average power draw during the session

Why this matters:
    Intel 99 platform TOPS vs AMD 80 platform TOPS is the canonical example.
    Intel's number looks better until you normalize by power draw — 77 of
    those TOPS come from the GPU at full thermal load. AMD's NPU delivers
    inference at a fraction of the wattage. SEIT makes this visible.

The peak vs sustained delta is the thermal story:
    High peak, low sustained = throttling under load
    Consistent peak and sustained = stable thermal design

Spec version: v0.1
Author: Joshua Holliday / True Vector Media
"""

from dataclasses import dataclass, field
from typing import Optional
import time
import statistics

from scorer import ETSPResult, SPEC_VERSION, Q_FLOOR


# ─────────────────────────────────────────────────────────────
# SEIT CONSTANTS — lock before v1.0 public release
# ─────────────────────────────────────────────────────────────

# Minimum sustained window for a valid SEIT measurement
SEIT_WINDOW_SECONDS = 900  # 15 minutes

# Minimum samples required within the window
SEIT_MIN_SAMPLES = 3

# Thermal stability threshold — CV above this flags high variance
SEIT_STABILITY_THRESHOLD = 0.10

# Power source options for declared (non-measured) wattage
POWER_SOURCE_MEASURED   = "measured"   # Hardware sensor or smart plug
POWER_SOURCE_TDP        = "tdp"        # Manufacturer TDP — least accurate
POWER_SOURCE_ESTIMATED  = "estimated"  # User estimate based on known hardware

SPEC_VERSION_SEIT = "v0.1"


@dataclass
class PowerProfile:
    """
    Power draw declaration for SEIT calculation.

    Measured via hardware sensor or smart plug is preferred.
    TDP is the fallback — it overstates idle and understates peak.
    Always declare source — it affects result credibility.
    """
    watts_avg: float                    # Average watts during inference window
    watts_peak: Optional[float] = None  # Peak watts if measured
    watts_idle: Optional[float] = None  # Idle baseline if measured
    source: str = POWER_SOURCE_TDP      # How watts_avg was obtained
    notes: Optional[str] = None

    def __post_init__(self):
        if self.watts_avg <= 0:
            raise ValueError(f"watts_avg must be positive, got {self.watts_avg}")
        if self.source not in (
            POWER_SOURCE_MEASURED, POWER_SOURCE_TDP, POWER_SOURCE_ESTIMATED
        ):
            raise ValueError(
                f"source must be one of: measured, tdp, estimated. Got {self.source}"
            )
        if self.watts_peak and self.watts_peak < self.watts_avg:
            raise ValueError("watts_peak cannot be less than watts_avg")


@dataclass
class SEITSample:
    """A single eTPS sample within a SEIT measurement window."""
    etps: float
    quality_factor: float
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.etps < 0:
            raise ValueError(f"etps cannot be negative, got {self.etps}")
        if not Q_FLOOR <= self.quality_factor <= 1.0:
            raise ValueError(
                f"quality_factor must be {Q_FLOOR}-1.0, got {self.quality_factor}"
            )


@dataclass
class SEITResult:
    """Complete SEIT calculation result with thermal analysis."""
    seit: float                     # Primary metric: eTPS_sustained / Watts
    etps_peak: float                # Highest eTPS in window
    etps_sustained: float           # Median eTPS over window
    etps_floor: float               # Lowest eTPS in window
    quality_factor_median: float    # Median Q across window
    watts_avg: float                # Power draw used in calculation
    power_source: str               # How watts were obtained
    thermal_delta: float            # etps_peak - etps_floor (throttling signal)
    thermal_stable: bool            # CV < SEIT_STABILITY_THRESHOLD
    coefficient_of_variation: float # Statistical stability measure
    sample_count: int               # Number of eTPS samples in window
    window_seconds: float           # Actual measurement window duration
    spec_version: str = SPEC_VERSION_SEIT

    def summary(self) -> str:
        stability = "STABLE" if self.thermal_stable else "HIGH VARIANCE"
        lines = [
            f"SEIT:              {self.seit:.4f} eTPS/W",
            f"eTPS sustained:    {self.etps_sustained:.2f}",
            f"eTPS peak:         {self.etps_peak:.2f}",
            f"eTPS floor:        {self.etps_floor:.2f}",
            f"Thermal delta:     {self.thermal_delta:.2f} ({stability})",
            f"CV:                {self.coefficient_of_variation:.3f}",
            f"Quality (median):  {self.quality_factor_median:.3f}",
            f"Power draw:        {self.watts_avg:.1f}W ({self.power_source})",
            f"Samples:           {self.sample_count} over {self.window_seconds:.0f}s",
            f"Spec version:      {self.spec_version}",
        ]
        if not self.thermal_stable:
            lines.append(
                "\n⚠ High variance detected. Possible causes: thermal throttling, "
                "memory pressure, background processes. Run again after 30-minute idle."
            )
        if self.power_source == POWER_SOURCE_TDP:
            lines.append(
                "\n⚠ TDP-based power declaration. SEIT may be understated at peak "
                "and overstated at idle. Measure with a smart plug for accurate results."
            )
        return "\n".join(lines)

    def vs_baseline(self, baseline: "SEITResult") -> str:
        """Compare this result against a baseline (e.g. no memory system vs Nyx)."""
        delta = self.seit - baseline.seit
        pct = ((self.seit / baseline.seit) - 1) * 100 if baseline.seit > 0 else 0
        direction = "improvement" if delta > 0 else "regression"
        return (
            f"SEIT delta: {delta:+.4f} eTPS/W ({pct:+.1f}% {direction})\n"
            f"  This:     {self.seit:.4f} eTPS/W\n"
            f"  Baseline: {baseline.seit:.4f} eTPS/W"
        )


def calculate_seit(
    samples: list[SEITSample],
    power: PowerProfile,
    window_seconds: Optional[float] = None,
) -> SEITResult:
    """
    Calculate SEIT from a list of eTPS samples and a power profile.

    samples: list of SEITSample collected during the inference window
    power: PowerProfile declaring average watts during the window
    window_seconds: actual elapsed time — if None, derived from sample timestamps

    Minimum viable: SEIT_MIN_SAMPLES samples.
    Recommended: samples collected over SEIT_WINDOW_SECONDS (15 minutes).
    """
    if len(samples) < SEIT_MIN_SAMPLES:
        raise ValueError(
            f"SEIT requires at least {SEIT_MIN_SAMPLES} samples, "
            f"got {len(samples)}. Run more benchmark tasks."
        )

    etps_values = [s.etps for s in samples]
    q_values = [s.quality_factor for s in samples]

    etps_sustained = statistics.median(etps_values)
    etps_peak = max(etps_values)
    etps_floor = min(etps_values)
    q_median = statistics.median(q_values)

    # Coefficient of variation — thermal stability signal
    if len(etps_values) > 1 and etps_sustained > 0:
        cv = statistics.stdev(etps_values) / etps_sustained
    else:
        cv = 0.0

    thermal_stable = cv < SEIT_STABILITY_THRESHOLD
    thermal_delta = etps_peak - etps_floor

    # Actual window duration from timestamps if not provided
    if window_seconds is None and len(samples) > 1:
        window_seconds = samples[-1].timestamp - samples[0].timestamp
    elif window_seconds is None:
        window_seconds = 0.0

    # Core SEIT formula
    # Using sustained (median) eTPS — not peak — for honest thermal representation
    seit = etps_sustained / power.watts_avg

    return SEITResult(
        seit=round(seit, 6),
        etps_peak=round(etps_peak, 4),
        etps_sustained=round(etps_sustained, 4),
        etps_floor=round(etps_floor, 4),
        quality_factor_median=round(q_median, 4),
        watts_avg=power.watts_avg,
        power_source=power.source,
        thermal_delta=round(thermal_delta, 4),
        thermal_stable=thermal_stable,
        coefficient_of_variation=round(cv, 4),
        sample_count=len(samples),
        window_seconds=round(window_seconds, 1),
    )


def seit_from_etps_results(
    results: list[ETSPResult],
    power: PowerProfile,
    window_seconds: Optional[float] = None,
) -> SEITResult:
    """
    Convenience wrapper — build SEITSamples directly from ETSPResult list.
    Use this when you already have scorer output and want SEIT without
    manually constructing SEITSample objects.
    """
    samples = [
        SEITSample(etps=r.etps, quality_factor=r.quality_factor)
        for r in results
    ]
    return calculate_seit(samples, power, window_seconds)


# ─────────────────────────────────────────────────────────────
# SELF-TEST — run directly: python seit.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from scorer import (
        calculate_etps, TokenCounts, PenaltyRecord, ContinuityRecord
    )

    print("Running SEIT self-tests...\n")

    # Build sample ETSPResults representing a 15-minute inference window
    def make_result(tps, reconstruction=0, reconstruction_events=0):
        return calculate_etps(
            tps_raw=tps,
            tokens=TokenCounts(total=800, reconstruction=reconstruction),
            penalties=PenaltyRecord(reconstruction_events=reconstruction_events),
            continuity=ContinuityRecord(is_single_turn=True),
        )

    # Test 1: Stable thermal — consistent eTPS across samples
    stable_results = [make_result(tps) for tps in [42.0, 43.0, 41.0, 42.5, 43.5]]
    power_measured = PowerProfile(
        watts_avg=35.0,
        watts_peak=45.0,
        watts_idle=8.0,
        source=POWER_SOURCE_MEASURED,
    )

    seit_stable = seit_from_etps_results(stable_results, power_measured, window_seconds=900)
    assert seit_stable.thermal_stable, "Test 1 failed: should be thermally stable"
    assert seit_stable.seit > 0, "Test 1 failed: SEIT should be positive"
    print(f"Test 1 PASS — Stable thermal: SEIT={seit_stable.seit:.4f} eTPS/W")

    # Test 2: Thermal throttling — eTPS drops significantly mid-window
    throttled_results = [
        make_result(45.0),
        make_result(44.0),
        make_result(28.0),  # Throttle kicks in
        make_result(25.0),
        make_result(24.0),
    ]
    seit_throttled = seit_from_etps_results(
        throttled_results, power_measured, window_seconds=900
    )
    assert not seit_throttled.thermal_stable, "Test 2 failed: should detect instability"
    assert seit_throttled.etps_sustained < seit_stable.etps_sustained, \
        "Test 2 failed: throttled sustained should be lower"
    print(f"Test 2 PASS — Throttling detected: CV={seit_throttled.coefficient_of_variation:.3f}")

    # Test 3: TDP declaration vs measured — SEIT differs only in power source flag
    power_tdp = PowerProfile(watts_avg=45.0, source=POWER_SOURCE_TDP)
    seit_tdp = seit_from_etps_results(stable_results, power_tdp, window_seconds=900)
    assert seit_tdp.power_source == POWER_SOURCE_TDP
    assert seit_tdp.seit < seit_stable.seit  # Higher declared wattage = lower SEIT
    print(f"Test 3 PASS — TDP vs measured: {seit_tdp.seit:.4f} vs {seit_stable.seit:.4f} eTPS/W")

    # Test 4: Intel vs AMD platform TOPS illustration
    # AMD: 80 TOPS NPU — lower power draw, good sustained eTPS
    amd_results = [make_result(tps) for tps in [38.0, 39.0, 38.5, 37.5, 39.5]]
    amd_power = PowerProfile(watts_avg=28.0, source=POWER_SOURCE_MEASURED,
                             notes="AMD HX 470 NPU inference, iGPU idle")

    # Intel: 99 platform TOPS — but GPU-dependent, higher power
    intel_results = [make_result(tps) for tps in [41.0, 38.0, 32.0, 29.0, 28.0]]
    intel_power = PowerProfile(watts_avg=65.0, source=POWER_SOURCE_MEASURED,
                               notes="Intel Arc GPU carrying 77 of 99 TOPS")

    seit_amd = seit_from_etps_results(amd_results, amd_power, window_seconds=900)
    seit_intel = seit_from_etps_results(intel_results, intel_power, window_seconds=900)

    print(f"\nTest 4 — Platform TOPS illustration:")
    print(f"  AMD  (80 TOPS NPU):    SEIT={seit_amd.seit:.4f} eTPS/W  "
          f"sustained={seit_amd.etps_sustained:.1f}  stable={seit_amd.thermal_stable}")
    print(f"  Intel (99 platform):   SEIT={seit_intel.seit:.4f} eTPS/W  "
          f"sustained={seit_intel.etps_sustained:.1f}  stable={seit_intel.thermal_stable}")
    print(f"  {seit_amd.vs_baseline(seit_intel)}")
    assert seit_amd.seit > seit_intel.seit, \
        "Test 4 failed: AMD should win on power-normalized metric"
    print("Test 4 PASS — AMD wins on SEIT despite lower raw TOPS claim")

    # Test 5: Insufficient samples guard
    try:
        calculate_seit(
            [SEITSample(etps=40.0, quality_factor=0.9)],
            power_measured
        )
        assert False, "Test 5 failed: should have raised ValueError"
    except ValueError as e:
        print(f"\nTest 5 PASS — Insufficient samples guard: {e}")

    # Test 6: Invalid power declaration
    try:
        PowerProfile(watts_avg=0.0, source=POWER_SOURCE_MEASURED)
        assert False, "Test 6 failed: should have raised ValueError"
    except ValueError as e:
        print(f"Test 6 PASS — Invalid power guard: {e}")

    print(f"\n{'='*50}")
    print(f"All SEIT tests passed. Spec version: {SPEC_VERSION_SEIT}")
    print(f"{'='*50}\n")

    print("Sample SEIT summary (stable AMD system):")
    print(seit_stable.summary())
