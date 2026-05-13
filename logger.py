"""
eTPS Logger — SQLite persistence layer
========================================
Built after the scorer and a real test task, not before.
Schema reflects what the scorer actually produces.

Design decisions:
- WAL mode for concurrent reads during leaderboard queries
- Indexes on hot query paths from day one
- spec_version column on every table — comparisons across versions are invalid
- No ORM — raw SQL for transparency and auditability
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scorer import ETSPResult, SPEC_VERSION


DB_PATH = Path("etps_results.db")
SCHEMA_VERSION = 1


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    WAL mode connection with row_factory for dict-like access.
    Consistent with NyxCore SQLite architecture.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_schema(db_path: Path = DB_PATH) -> None:
    """
    Create tables if they don't exist. Safe to call on every startup — idempotent.
    """
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                schema_version INTEGER PRIMARY KEY,
                applied_at DATETIME NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                spec_version TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                timestamp DATETIME NOT NULL,

                -- Hardware declaration (all required for published results)
                hw_cpu TEXT NOT NULL,
                hw_gpu TEXT NOT NULL,
                hw_vram_gb REAL,
                hw_ram_gb REAL NOT NULL,
                hw_ram_channels INTEGER NOT NULL,
                hw_npu_tops REAL,
                hw_storage_type TEXT,
                hw_cooling TEXT,

                -- Software declaration
                sw_backend TEXT NOT NULL,
                sw_backend_version TEXT NOT NULL,
                sw_model_name TEXT NOT NULL,
                sw_model_params TEXT,
                sw_quantization TEXT NOT NULL,
                sw_context_window INTEGER,
                sw_temperature REAL,
                sw_mtp_enabled BOOLEAN DEFAULT FALSE,
                sw_memory_system TEXT DEFAULT 'none',
                sw_memory_system_version TEXT,
                sw_judge_model TEXT,
                sw_judge_model_version TEXT,

                -- Aggregate results
                etps_peak REAL,
                etps_sustained REAL,
                tps_raw_median REAL,
                quality_factor_median REAL,
                continuity_factor_median REAL,
                efficiency_ratio_median REAL,
                thermal_delta_c REAL,
                run_count INTEGER NOT NULL DEFAULT 1,

                -- Submission metadata
                submitted_by TEXT,
                notes TEXT,
                is_verified BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS task_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
                spec_version TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_category TEXT NOT NULL,

                -- Token counts
                tokens_total INTEGER NOT NULL,
                tokens_correction INTEGER DEFAULT 0,
                tokens_reconstruction INTEGER DEFAULT 0,
                tokens_refusal INTEGER DEFAULT 0,

                -- Penalty record
                hallucinations INTEGER DEFAULT 0,
                correction_rounds INTEGER DEFAULT 0,
                task_failed BOOLEAN DEFAULT FALSE,
                unprompted_refusal BOOLEAN DEFAULT FALSE,
                format_noncompliant BOOLEAN DEFAULT FALSE,
                reconstruction_events INTEGER DEFAULT 0,

                -- Continuity
                is_single_turn BOOLEAN DEFAULT TRUE,
                expected_context_items INTEGER DEFAULT 0,
                retained_context_items INTEGER DEFAULT 0,
                session_coherence_score REAL DEFAULT 1.0,

                -- Calculated results
                etps REAL NOT NULL,
                tps_raw REAL NOT NULL,
                efficiency_ratio REAL NOT NULL,
                waste_ratio REAL NOT NULL,
                quality_factor REAL NOT NULL,
                continuity_factor REAL NOT NULL,

                -- Audit
                raw_prompt TEXT,
                raw_response TEXT,
                penalty_notes TEXT,
                elapsed_seconds REAL,
                timestamp DATETIME NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_task_results_run_id
                ON task_results(run_id);

            CREATE INDEX IF NOT EXISTS idx_task_results_task_id
                ON task_results(task_id);

            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_model
                ON benchmark_runs(sw_model_name, sw_quantization);

            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_spec
                ON benchmark_runs(spec_version);

            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_memory
                ON benchmark_runs(sw_memory_system);
        """)

        conn.execute("""
            INSERT OR IGNORE INTO schema_meta (schema_version, applied_at, notes)
            VALUES (?, ?, ?)
        """, (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(), "Initial schema"))

        conn.commit()
    finally:
        conn.close()


def start_run(
    hardware: dict,
    software: dict,
    db_path: Path = DB_PATH,
) -> str:
    """
    Begin a new benchmark run. Returns run_id.

    hardware keys: cpu, gpu, vram_gb, ram_gb, ram_channels,
                   npu_tops, storage_type, cooling
    software keys: backend, backend_version, model_name, model_params,
                   quantization, context_window, temperature,
                   mtp_enabled, memory_system, memory_system_version,
                   judge_model, judge_model_version
    """
    # Sanitize all string fields — prevent injection
    for key in ['cpu', 'gpu']:
        if key in hardware:
            if not isinstance(hardware[key], str) or len(hardware[key]) > 200:
                raise ValueError(f"Invalid hardware.{key}: must be string <= 200 chars")

    for key in ['backend', 'backend_version', 'model_name', 'quantization']:
        if key in software:
            if not isinstance(software[key], str) or len(software[key]) > 200:
                raise ValueError(f"Invalid software.{key}: must be string <= 200 chars")

    run_id = str(uuid.uuid4())
    conn = get_connection(db_path)

    try:
        conn.execute("""
            INSERT INTO benchmark_runs (
                run_id, spec_version, schema_version, timestamp,
                hw_cpu, hw_gpu, hw_vram_gb, hw_ram_gb, hw_ram_channels,
                hw_npu_tops, hw_storage_type, hw_cooling,
                sw_backend, sw_backend_version, sw_model_name, sw_model_params,
                sw_quantization, sw_context_window, sw_temperature,
                sw_mtp_enabled, sw_memory_system, sw_memory_system_version,
                sw_judge_model, sw_judge_model_version
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
        """, (
            run_id, SPEC_VERSION, SCHEMA_VERSION,
            datetime.now(timezone.utc).isoformat(),
            hardware.get('cpu', 'unknown'),
            hardware.get('gpu', 'unknown'),
            hardware.get('vram_gb'),
            hardware.get('ram_gb', 0),
            hardware.get('ram_channels', 1),
            hardware.get('npu_tops'),
            hardware.get('storage_type'),
            hardware.get('cooling'),
            software.get('backend', 'unknown'),
            software.get('backend_version', 'unknown'),
            software.get('model_name', 'unknown'),
            software.get('model_params'),
            software.get('quantization', 'unknown'),
            software.get('context_window'),
            software.get('temperature'),
            software.get('mtp_enabled', False),
            software.get('memory_system', 'none'),
            software.get('memory_system_version'),
            software.get('judge_model'),
            software.get('judge_model_version'),
        ))
        conn.commit()
    finally:
        conn.close()

    return run_id


def record_task_result(
    run_id: str,
    task_id: str,
    task_category: str,
    result: ETSPResult,
    elapsed_seconds: float,
    raw_prompt: Optional[str] = None,
    raw_response: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> None:
    """Record a single task result under a benchmark run."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO task_results (
                run_id, spec_version, task_id, task_category,
                tokens_total, tokens_correction, tokens_reconstruction, tokens_refusal,
                hallucinations, correction_rounds, task_failed,
                unprompted_refusal, format_noncompliant, reconstruction_events,
                is_single_turn, expected_context_items, retained_context_items,
                session_coherence_score,
                etps, tps_raw, efficiency_ratio, waste_ratio,
                quality_factor, continuity_factor,
                raw_prompt, raw_response, penalty_notes,
                elapsed_seconds, timestamp
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?
            )
        """, (
            run_id, SPEC_VERSION, task_id, task_category,
            result.token_counts.total,
            result.token_counts.correction,
            result.token_counts.reconstruction,
            result.token_counts.refusal,
            result.penalty_record.hallucinations,
            result.penalty_record.correction_rounds,
            result.penalty_record.task_failed,
            result.penalty_record.unprompted_refusal,
            result.penalty_record.format_noncompliant,
            result.penalty_record.reconstruction_events,
            True,
            0, 0, 1.0,
            result.etps, result.tps_raw,
            result.efficiency_ratio, result.waste_ratio,
            result.quality_factor, result.continuity_factor,
            raw_prompt[:5000] if raw_prompt else None,
            raw_response[:5000] if raw_response else None,
            json.dumps(result.penalty_record.notes),
            elapsed_seconds,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def finalize_run(run_id: str, db_path: Path = DB_PATH) -> None:
    """Calculate and store aggregate stats. Call after all task results recorded."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("""
            SELECT
                AVG(etps)               as etps_avg,
                MAX(etps)               as etps_peak,
                AVG(tps_raw)            as tps_raw_avg,
                AVG(quality_factor)     as q_avg,
                AVG(continuity_factor)  as c_avg,
                AVG(efficiency_ratio)   as eff_avg,
                COUNT(*)                as task_count
            FROM task_results
            WHERE run_id = ?
        """, (run_id,)).fetchone()

        conn.execute("""
            UPDATE benchmark_runs SET
                etps_peak = ?,
                etps_sustained = ?,
                tps_raw_median = ?,
                quality_factor_median = ?,
                continuity_factor_median = ?,
                efficiency_ratio_median = ?,
                run_count = ?
            WHERE run_id = ?
        """, (
            row['etps_peak'],
            row['etps_avg'],
            row['tps_raw_avg'],
            row['q_avg'],
            row['c_avg'],
            row['eff_avg'],
            row['task_count'],
            run_id,
        ))
        conn.commit()
    finally:
        conn.close()


def query_leaderboard(
    limit: int = 50,
    memory_system: Optional[str] = None,
    spec_version: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Query leaderboard sorted by etps_sustained descending."""
    if memory_system and not isinstance(memory_system, str):
        raise ValueError("memory_system must be a string")
    if limit > 1000:
        limit = 1000

    conn = get_connection(db_path)
    try:
        conditions = ["1=1"]
        params = []

        if memory_system:
            conditions.append("sw_memory_system = ?")
            params.append(memory_system)
        if spec_version:
            conditions.append("spec_version = ?")
            params.append(spec_version)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = conn.execute(f"""
            SELECT
                run_id, sw_model_name, sw_quantization,
                sw_backend, sw_memory_system, sw_mtp_enabled,
                hw_cpu, hw_gpu, hw_ram_gb, hw_ram_channels,
                etps_sustained, etps_peak, tps_raw_median,
                quality_factor_median, continuity_factor_median,
                efficiency_ratio_median, spec_version,
                submitted_by, timestamp
            FROM benchmark_runs
            WHERE {where}
            ORDER BY etps_sustained DESC
            LIMIT ?
        """, params).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import tempfile
    from scorer import calculate_etps, TokenCounts, PenaltyRecord, ContinuityRecord

    print("Running logger smoke test...\n")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = Path(f.name)

    initialize_schema(test_db)
    print("Schema initialized.")

    run_id = start_run(
        hardware={
            'cpu': 'AMD Ryzen AI 9 HX 470',
            'gpu': 'Radeon 890M',
            'ram_gb': 32,
            'ram_channels': 2,
            'npu_tops': 86,
            'storage_type': 'NVMe PCIe 4.0',
            'cooling': 'active',
        },
        software={
            'backend': 'llama.cpp',
            'backend_version': '0.0.1',
            'model_name': 'Qwen3.5-9B',
            'quantization': 'Q4_K_XL',
            'context_window': 8192,
            'temperature': 0.7,
            'mtp_enabled': True,
            'memory_system': 'nyx_v2',
            'memory_system_version': '2.0.0',
        },
        db_path=test_db,
    )
    print(f"Run started: {run_id}")

    result = calculate_etps(
        tps_raw=45.0,
        tokens=TokenCounts(total=600, reconstruction=60),
        penalties=PenaltyRecord(reconstruction_events=1),
        continuity=ContinuityRecord(is_single_turn=True),
    )

    record_task_result(
        run_id=run_id,
        task_id="A1_factual_continuity",
        task_category="A",
        result=result,
        elapsed_seconds=13.3,
        raw_prompt="Test prompt",
        raw_response="Test response",
        db_path=test_db,
    )
    print(f"Task recorded: eTPS={result.etps}")

    finalize_run(run_id, test_db)
    print("Run finalized.")

    board = query_leaderboard(db_path=test_db)
    assert len(board) == 1
    assert board[0]['sw_model_name'] == 'Qwen3.5-9B'
    print(f"Leaderboard query: {board[0]['sw_model_name']} — eTPS={board[0]['etps_sustained']:.2f}")

    test_db.unlink()
    print("\nLogger smoke test passed.")
