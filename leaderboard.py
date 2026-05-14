"""
eTPS Leaderboard — Ranking and Query System
============================================
Pulls from logger.py (benchmark_runs) and user_profile.py (user_run_links)
to produce a ranked, filterable leaderboard with export support.

Data sources:
- logger_db:  benchmark_runs table — ground truth for all run data
- profile_db: user_run_links + users + hardware_profiles — display names,
              hardware tiers, consent flags

The two databases are kept separate by design. This module merges them
in Python — no cross-DB SQL joins. logger_db is append-only truth;
profile_db is user-managed display metadata.

Hardware tiers (based on NPU TOPS declared in hardware profile):
  cpu_only   — No NPU (null or 0 TOPS) — CPU / iGPU inference only
  entry_npu  — < 40 TOPS
  mid_npu    — 40 to 79 TOPS
  high_npu   — >= 80 TOPS (e.g. Ryzen AI 9 HX, Snapdragon X Elite)

Ranking is by etps_sustained descending within each filter combination.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from logger import DB_PATH as LOGGER_DB_PATH, get_connection as logger_conn
from user_profile import PROFILE_DB_PATH, get_connection as profile_conn


# ─────────────────────────────────────────────────────────────
# Hardware tier classification
# ─────────────────────────────────────────────────────────────

def _hardware_tier(npu_tops: Optional[float]) -> str:
    if npu_tops is None or npu_tops == 0:
        return "cpu_only"
    if npu_tops < 40:
        return "entry_npu"
    if npu_tops < 80:
        return "mid_npu"
    return "high_npu"


HARDWARE_TIERS = ("cpu_only", "entry_npu", "mid_npu", "high_npu")


def _model_family(model_name: Optional[str]) -> str:
    """Extract model family from a model name string."""
    if not model_name:
        return "unknown"
    # Split on common delimiters and take the first alphabetic token
    import re
    parts = re.split(r'[\-_\d.\s]', model_name.strip())
    for part in parts:
        if part and part.isalpha():
            return part.capitalize()
    return model_name.split()[0] if model_name else "unknown"


# ─────────────────────────────────────────────────────────────
# Core query functions
# ─────────────────────────────────────────────────────────────

def _query_logger_runs(
    spec_version: Optional[str],
    memory_system: Optional[str],
    model_family: Optional[str],
    limit: int,
    logger_db: Path,
) -> list[dict]:
    """Pull benchmark runs from logger DB, apply SQL-level filters where possible."""
    conditions = ["etps_sustained IS NOT NULL"]
    params: list = []

    if spec_version:
        conditions.append("spec_version = ?")
        params.append(spec_version)
    if memory_system:
        conditions.append("sw_memory_system = ?")
        params.append(memory_system)

    where = " AND ".join(conditions)
    params.append(limit * 10)  # Fetch extra to allow Python-level filtering

    conn = logger_conn(logger_db)
    try:
        rows = conn.execute(f"""
            SELECT
                run_id, spec_version,
                hw_cpu, hw_gpu, hw_vram_gb, hw_ram_gb, hw_ram_channels, hw_npu_tops,
                hw_storage_type, hw_cooling,
                sw_backend, sw_backend_version, sw_model_name, sw_quantization,
                sw_memory_system, sw_mtp_enabled, sw_context_window,
                etps_sustained, etps_peak, tps_raw_median,
                quality_factor_median, continuity_factor_median,
                efficiency_ratio_median, run_count,
                submitted_by, is_verified, timestamp
            FROM benchmark_runs
            WHERE {where}
            ORDER BY etps_sustained DESC
            LIMIT ?
        """, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _query_profile_links(
    run_ids: list[str],
    profile_db: Path,
) -> dict[str, dict]:
    """
    For a list of run_ids, fetch display metadata from profile DB.
    Returns {run_id: {display_name, is_registered, seit, watts_avg, power_source,
                       hw_npu_tops (from hardware_profile), hw_nickname}}
    """
    if not run_ids:
        return {}

    placeholders = ",".join(["?"] * len(run_ids))
    conn = profile_conn(profile_db)
    try:
        rows = conn.execute(f"""
            SELECT
                url.run_id,
                url.seit, url.watts_avg, url.power_source,
                url.is_public,
                u.display_name,
                u.is_anonymous,
                u.consent_leaderboard,
                hp.nickname as hw_nickname,
                hp.hw_npu_tops as profile_npu_tops
            FROM user_run_links url
            JOIN users u ON url.user_id = u.user_id
            LEFT JOIN hardware_profiles hp ON url.hardware_profile_id = hp.profile_id
            WHERE url.run_id IN ({placeholders})
              AND url.is_public = TRUE
        """, run_ids).fetchall()

        result = {}
        for row in rows:
            d = dict(row)
            # Only show display_name if user opted into leaderboard
            if d['consent_leaderboard'] and not d['is_anonymous']:
                display = d['display_name']
                is_registered = True
            else:
                display = "Anonymous"
                is_registered = False
            result[d['run_id']] = {
                "display_name": display,
                "is_registered": is_registered,
                "seit": d['seit'],
                "watts_avg": d['watts_avg'],
                "power_source": d['power_source'],
                "hw_nickname": d['hw_nickname'],
                "profile_npu_tops": d['profile_npu_tops'],
            }
        return result
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────

def build_leaderboard(
    spec_version: Optional[str] = None,
    memory_system: Optional[str] = None,
    model_family: Optional[str] = None,
    hardware_tier: Optional[str] = None,
    ram_channels: Optional[int] = None,
    limit: int = 50,
    logger_db: Path = LOGGER_DB_PATH,
    profile_db: Path = PROFILE_DB_PATH,
) -> list[dict]:
    """
    Build a ranked leaderboard with optional filters.

    spec_version:   e.g. "v0.1" — required for meaningful comparison
    memory_system:  e.g. "nyx_v2", "none" — exact match
    model_family:   e.g. "Qwen", "Llama" — derived from model name
    hardware_tier:  one of "cpu_only", "entry_npu", "mid_npu", "high_npu"
    ram_channels:   1 or 2 — filters by declared RAM channel count
    limit:          max entries returned (capped at 500)

    Returns list of entry dicts, ranked by etps_sustained descending.
    """
    if hardware_tier and hardware_tier not in HARDWARE_TIERS:
        raise ValueError(
            f"hardware_tier must be one of {HARDWARE_TIERS}, got '{hardware_tier}'"
        )
    if ram_channels and ram_channels not in (1, 2):
        raise ValueError("ram_channels must be 1 or 2")
    if limit > 500:
        limit = 500

    runs = _query_logger_runs(
        spec_version=spec_version,
        memory_system=memory_system,
        model_family=model_family,
        limit=limit,
        logger_db=logger_db,
    )

    run_ids = [r['run_id'] for r in runs]
    profile_meta = _query_profile_links(run_ids, profile_db)

    entries = []
    for run in runs:
        meta = profile_meta.get(run['run_id'], {})

        # Use profile-declared NPU TOPS if available, fall back to benchmark_runs hw field
        npu_tops = meta.get('profile_npu_tops') or run.get('hw_npu_tops')
        tier = _hardware_tier(npu_tops)
        family = _model_family(run.get('sw_model_name'))

        # Apply Python-level filters
        if hardware_tier and tier != hardware_tier:
            continue
        if ram_channels and run.get('hw_ram_channels') != ram_channels:
            continue
        if model_family and family.lower() != model_family.lower():
            continue

        display_name = meta.get('display_name') or (
            run.get('submitted_by') or "Anonymous"
        )
        is_registered = meta.get('is_registered', False)

        entries.append({
            "run_id": run['run_id'],
            "display_name": display_name,
            "is_registered": is_registered,
            "hw_cpu": run.get('hw_cpu'),
            "hw_gpu": run.get('hw_gpu'),
            "hw_ram_gb": run.get('hw_ram_gb'),
            "hw_ram_channels": run.get('hw_ram_channels'),
            "hw_npu_tops": npu_tops,
            "hw_nickname": meta.get('hw_nickname'),
            "hardware_tier": tier,
            "sw_model_name": run.get('sw_model_name'),
            "model_family": family,
            "sw_quantization": run.get('sw_quantization'),
            "sw_backend": run.get('sw_backend'),
            "sw_memory_system": run.get('sw_memory_system'),
            "sw_mtp_enabled": run.get('sw_mtp_enabled'),
            "etps_sustained": run.get('etps_sustained'),
            "etps_peak": run.get('etps_peak'),
            "tps_raw_median": run.get('tps_raw_median'),
            "quality_factor_median": run.get('quality_factor_median'),
            "efficiency_ratio_median": run.get('efficiency_ratio_median'),
            "seit": meta.get('seit'),
            "watts_avg": meta.get('watts_avg'),
            "power_source": meta.get('power_source'),
            "spec_version": run.get('spec_version'),
            "is_verified": run.get('is_verified', False),
            "submitted_at": run.get('timestamp'),
        })

        if len(entries) >= limit:
            break

    # Assign ranks (etps_sustained already sorted descending from SQL)
    for i, entry in enumerate(entries):
        entry['rank'] = i + 1

    return entries


def export_json(
    entries: list[dict],
    filters: Optional[dict] = None,
    spec_version: Optional[str] = None,
) -> str:
    """
    Serialize leaderboard entries to JSON for effectivetps.com export.

    Produces a self-describing payload with metadata, filters applied,
    and the ranked entry list. Safe to write directly to a .json file
    or return as an HTTP response body.
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_version": spec_version or "mixed",
        "entry_count": len(entries),
        "filters_applied": filters or {},
        "leaderboard": entries,
    }
    return json.dumps(payload, indent=2, default=str)


def print_leaderboard(entries: list[dict], show_seit: bool = True) -> None:
    """Print a formatted leaderboard table to stdout."""
    if not entries:
        print("No results found for the given filters.")
        return

    col_w = {
        'rank': 4, 'name': 20, 'model': 18, 'quant': 10,
        'memory': 10, 'tier': 10, 'etps': 8, 'tps': 8,
        'quality': 7, 'seit': 10,
    }

    header = (
        f"{'#':>{col_w['rank']}}  "
        f"{'Name':<{col_w['name']}}  "
        f"{'Model':<{col_w['model']}}  "
        f"{'Quant':<{col_w['quant']}}  "
        f"{'Memory':<{col_w['memory']}}  "
        f"{'Tier':<{col_w['tier']}}  "
        f"{'eTPS':>{col_w['etps']}}  "
        f"{'TPS':>{col_w['tps']}}  "
        f"{'Q':>{col_w['quality']}}"
    )
    if show_seit:
        header += f"  {'SEIT (eTPS/W)':>{col_w['seit']}}"

    print(header)
    print("-" * len(header))

    for e in entries:
        name = (e['display_name'] or 'Anonymous')[:col_w['name']]
        model = (e['sw_model_name'] or '')[:col_w['model']]
        quant = (e['sw_quantization'] or '')[:col_w['quant']]
        memory = (e['sw_memory_system'] or 'none')[:col_w['memory']]
        tier = e['hardware_tier'][:col_w['tier']]
        etps = f"{e['etps_sustained']:.2f}" if e['etps_sustained'] else 'N/A'
        tps = f"{e['tps_raw_median']:.2f}" if e['tps_raw_median'] else 'N/A'
        quality = f"{e['quality_factor_median']:.3f}" if e['quality_factor_median'] else 'N/A'

        row = (
            f"{e['rank']:>{col_w['rank']}}  "
            f"{name:<{col_w['name']}}  "
            f"{model:<{col_w['model']}}  "
            f"{quant:<{col_w['quant']}}  "
            f"{memory:<{col_w['memory']}}  "
            f"{tier:<{col_w['tier']}}  "
            f"{etps:>{col_w['etps']}}  "
            f"{tps:>{col_w['tps']}}  "
            f"{quality:>{col_w['quality']}}"
        )
        if show_seit:
            seit = f"{e['seit']:.4f}" if e['seit'] else 'N/A'
            row += f"  {seit:>{col_w['seit']}}"
        print(row)


# ─────────────────────────────────────────────────────────────
# SELF-TEST — run directly: python leaderboard.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile
    from logger import initialize_schema as init_logger, start_run, record_task_result, finalize_run
    from user_profile import (
        initialize_schema as init_profile, create_user,
        update_consent, register_hardware_profile, link_run
    )
    from scorer import calculate_etps, TokenCounts, PenaltyRecord, ContinuityRecord

    print("Running leaderboard smoke test...\n")

    with (
        tempfile.NamedTemporaryFile(suffix="_logger.db", delete=False) as lf,
        tempfile.NamedTemporaryFile(suffix="_profile.db", delete=False) as pf
    ):
        test_logger_db = Path(lf.name)
        test_profile_db = Path(pf.name)

    init_logger(test_logger_db)
    init_profile(test_profile_db)
    print("Schemas initialized.")

    # Create two benchmark runs with different hardware tiers
    hw_high_npu = {
        'cpu': 'AMD Ryzen AI 9 HX 470', 'gpu': 'Radeon 890M',
        'ram_gb': 32, 'ram_channels': 2, 'npu_tops': 86,
        'storage_type': 'NVMe PCIe 4.0', 'cooling': 'active',
    }
    hw_cpu_only = {
        'cpu': 'Intel Core i7-13700H', 'gpu': 'Intel Iris Xe',
        'ram_gb': 16, 'ram_channels': 2,
        'storage_type': 'NVMe PCIe 3.0', 'cooling': 'active',
    }
    sw_base = {
        'backend': 'llama.cpp', 'backend_version': 'b3600',
        'model_name': 'Qwen3.5-9B', 'quantization': 'Q4_K_XL',
        'context_window': 8192, 'temperature': 0.7,
        'mtp_enabled': True, 'memory_system': 'nyx_v2', 'memory_system_version': '2.0.0',
    }

    run_id_1 = start_run(hardware=hw_high_npu, software=sw_base, db_path=test_logger_db)
    result_1 = calculate_etps(
        tps_raw=45.0, tokens=TokenCounts(total=600),
        penalties=PenaltyRecord(), continuity=ContinuityRecord(is_single_turn=True),
    )
    record_task_result(run_id_1, "B1", "B", result_1, 12.0, db_path=test_logger_db)
    finalize_run(run_id_1, test_logger_db)

    run_id_2 = start_run(hardware=hw_cpu_only, software={**sw_base, 'memory_system': 'none'}, db_path=test_logger_db)
    result_2 = calculate_etps(
        tps_raw=28.0, tokens=TokenCounts(total=600),
        penalties=PenaltyRecord(), continuity=ContinuityRecord(is_single_turn=True),
    )
    record_task_result(run_id_2, "B1", "B", result_2, 21.0, db_path=test_logger_db)
    finalize_run(run_id_2, test_logger_db)
    print(f"Logger runs created: {run_id_1[:8]}... and {run_id_2[:8]}...")

    # Registered user links run 1 with consent
    user = create_user(display_name="Joshua Holliday", email="test@test.com", db_path=test_profile_db)
    update_consent(
        user_id=user['user_id'],
        consent_telemetry=True, consent_leaderboard=True,
        consent_data_sharing=True, data_sharing_partners=['ai_companies'],
        db_path=test_profile_db,
    )
    hw_prof = register_hardware_profile(
        user_id=user['user_id'], hardware=hw_high_npu,
        nickname="Legion 5i AI", db_path=test_profile_db,
    )
    link_run(
        user_id=user['user_id'], run_id=run_id_1, spec_version='v0.1',
        hardware_profile_id=hw_prof, is_public=True,
        aggregate_cache={
            'etps_sustained': 45.0, 'etps_peak': 45.0, 'tps_raw_median': 45.0,
            'quality_factor_median': 1.0, 'seit': 1.607, 'watts_avg': 28.0,
            'power_source': 'measured', 'sw_model_name': 'Qwen3.5-9B',
            'sw_quantization': 'Q4_K_XL', 'sw_memory_system': 'nyx_v2',
        },
        db_path=test_profile_db,
    )
    print("User profile and run link created.")

    # Build full leaderboard
    board = build_leaderboard(
        logger_db=test_logger_db, profile_db=test_profile_db,
    )
    assert len(board) == 2, f"Expected 2 entries, got {len(board)}"
    assert board[0]['rank'] == 1
    assert board[0]['display_name'] == "Joshua Holliday"  # registered with consent
    assert board[1]['display_name'] == "Anonymous"  # no profile link
    print(f"Full leaderboard: {len(board)} entries, rank 1 = {board[0]['display_name']}")

    # Filter by hardware_tier
    npu_board = build_leaderboard(
        hardware_tier="high_npu",
        logger_db=test_logger_db, profile_db=test_profile_db,
    )
    assert len(npu_board) == 1
    assert npu_board[0]['hardware_tier'] == "high_npu"
    print(f"Tier filter (high_npu): {len(npu_board)} entry")

    # Filter by memory_system
    mem_board = build_leaderboard(
        memory_system="nyx_v2",
        logger_db=test_logger_db, profile_db=test_profile_db,
    )
    assert len(mem_board) == 1
    assert mem_board[0]['sw_memory_system'] == 'nyx_v2'
    print(f"Memory filter (nyx_v2): {len(mem_board)} entry")

    # Filter by model_family
    qwen_board = build_leaderboard(
        model_family="Qwen",
        logger_db=test_logger_db, profile_db=test_profile_db,
    )
    assert len(qwen_board) == 2
    assert all(e['model_family'] == 'Qwen' for e in qwen_board)
    print(f"Model family filter (Qwen): {len(qwen_board)} entries")

    # JSON export
    exported = export_json(board, filters={'spec_version': 'v0.1'}, spec_version='v0.1')
    parsed = json.loads(exported)
    assert parsed['entry_count'] == 2
    assert 'leaderboard' in parsed
    print(f"JSON export: {len(exported)} bytes, {parsed['entry_count']} entries")

    # Print table
    print("\nFormatted leaderboard:")
    print_leaderboard(board)

    # Hardware tier classification tests
    assert _hardware_tier(None) == "cpu_only"
    assert _hardware_tier(0) == "cpu_only"
    assert _hardware_tier(25.0) == "entry_npu"
    assert _hardware_tier(55.0) == "mid_npu"
    assert _hardware_tier(86.0) == "high_npu"
    print("\nHardware tier classification: OK")

    # Model family extraction tests
    assert _model_family("Qwen3.5-9B") == "Qwen"
    assert _model_family("Llama-3.2-3B") == "Llama"
    assert _model_family("Mistral-7B-Instruct") == "Mistral"
    assert _model_family(None) == "unknown"
    print("Model family extraction: OK")

    test_logger_db.unlink()
    test_profile_db.unlink()
    print("\nLeaderboard smoke test passed.")
