"""
eTPS User Profile — Account and Data Collection System
=======================================================
SQLite-backed user accounts with hardware profile tracking,
benchmark history, and opt-in telemetry for aggregate export.

Design decisions:
- WAL mode, consistent with logger.py
- No auth framework — email + UUID token, simple and auditable
- Anonymous by default — registration is opt-in
- Consent tracked per field with timestamp and policy version
- Aggregate export structured for AI companies and hardware vendors
- All writes parameterized — no string interpolation in SQL

Privacy model:
- is_anonymous=True: no email stored, display_name auto-generated, token still issued
- consent_telemetry: opt-in to aggregate performance telemetry
- consent_leaderboard: opt-in to public leaderboard display
- consent_data_sharing: opt-in to anonymized bulk export to declared partners
"""

import sqlite3
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


PROFILE_DB_PATH = Path("etps_profiles.db")
SCHEMA_VERSION = 1
PRIVACY_POLICY_VERSION = "v0.1"

# Valid partner keys for data_sharing_partners consent field
VALID_PARTNERS = frozenset(["ai_companies", "hardware_vendors", "researchers"])


def get_connection(db_path: Path = PROFILE_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_schema(db_path: Path = PROFILE_DB_PATH) -> None:
    """Create all tables. Idempotent — safe to call on every startup."""
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                schema_version INTEGER PRIMARY KEY,
                applied_at DATETIME NOT NULL,
                notes TEXT
            );

            -- Core user account
            -- email is nullable — anonymous users get a token but no email
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                display_name TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at DATETIME NOT NULL,
                last_active DATETIME NOT NULL,
                is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,

                -- Privacy and consent
                -- All consent fields default FALSE — explicit opt-in required
                consent_telemetry BOOLEAN NOT NULL DEFAULT FALSE,
                consent_leaderboard BOOLEAN NOT NULL DEFAULT FALSE,
                consent_data_sharing BOOLEAN NOT NULL DEFAULT FALSE,
                -- JSON array of partner keys: ["ai_companies", "hardware_vendors", "researchers"]
                data_sharing_partners TEXT NOT NULL DEFAULT '[]',
                privacy_policy_version TEXT,
                consent_recorded_at DATETIME
            );

            -- Hardware configuration snapshots
            -- One user may have multiple hardware profiles (desktop + laptop, upgrades over time)
            CREATE TABLE IF NOT EXISTS hardware_profiles (
                profile_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                nickname TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                last_used DATETIME NOT NULL,

                -- Mirrors hw_* fields in benchmark_runs (logger.py)
                hw_cpu TEXT NOT NULL,
                hw_gpu TEXT NOT NULL,
                hw_vram_gb REAL,
                hw_ram_gb REAL NOT NULL,
                hw_ram_channels INTEGER NOT NULL,
                hw_npu_tops REAL,
                hw_storage_type TEXT,
                hw_cooling TEXT
            );

            -- Links users to benchmark runs recorded in logger.py
            -- run_id references benchmark_runs.run_id in the logger DB (cross-DB FK by convention)
            CREATE TABLE IF NOT EXISTS user_run_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                run_id TEXT NOT NULL,
                hardware_profile_id TEXT REFERENCES hardware_profiles(profile_id),
                submitted_at DATETIME NOT NULL,
                is_public BOOLEAN NOT NULL DEFAULT FALSE,
                spec_version TEXT NOT NULL,
                -- Cached aggregate fields to avoid cross-DB join on every leaderboard query
                etps_sustained REAL,
                etps_peak REAL,
                tps_raw_median REAL,
                quality_factor_median REAL,
                seit REAL,
                watts_avg REAL,
                power_source TEXT,
                sw_model_name TEXT,
                sw_quantization TEXT,
                sw_memory_system TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email) WHERE email IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_users_token
                ON users(token);

            CREATE INDEX IF NOT EXISTS idx_hardware_profiles_user
                ON hardware_profiles(user_id);

            CREATE INDEX IF NOT EXISTS idx_user_run_links_user
                ON user_run_links(user_id);

            CREATE INDEX IF NOT EXISTS idx_user_run_links_run
                ON user_run_links(run_id);

            CREATE INDEX IF NOT EXISTS idx_user_run_links_public
                ON user_run_links(is_public, spec_version);
        """)

        conn.execute("""
            INSERT OR IGNORE INTO schema_meta (schema_version, applied_at, notes)
            VALUES (?, ?, ?)
        """, (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(), "Initial schema"))

        conn.commit()
    finally:
        conn.close()


def _anonymous_display_name() -> str:
    """Generate a reproducible anonymous display name from a short UUID segment."""
    suffix = str(uuid.uuid4())[:8].upper()
    return f"Anon-{suffix}"


def create_user(
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    db_path: Path = PROFILE_DB_PATH,
) -> dict:
    """
    Create a new user account. Returns {user_id, token, display_name, is_anonymous}.

    - If email is None: anonymous account, no email stored.
    - If email is provided: registered account; display_name required.
    - Token is a UUID issued for all subsequent API calls — treat like a password.
    """
    is_anonymous = email is None

    if not is_anonymous and not display_name:
        raise ValueError("display_name required for registered accounts")

    if email and (not isinstance(email, str) or len(email) > 254 or "@" not in email):
        raise ValueError("Invalid email address")

    if display_name and len(display_name) > 100:
        raise ValueError("display_name must be <= 100 characters")

    user_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    resolved_name = display_name or _anonymous_display_name()
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO users (
                user_id, email, display_name, token,
                created_at, last_active, is_anonymous
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, resolved_name, token, now, now, is_anonymous))
        conn.commit()
    finally:
        conn.close()

    return {
        "user_id": user_id,
        "token": token,
        "display_name": resolved_name,
        "is_anonymous": is_anonymous,
    }


def get_user_by_token(token: str, db_path: Path = PROFILE_DB_PATH) -> Optional[dict]:
    """Look up a user by their token. Returns None if not found."""
    if not isinstance(token, str) or len(token) != 36:
        return None
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_consent(
    user_id: str,
    consent_telemetry: bool,
    consent_leaderboard: bool,
    consent_data_sharing: bool,
    data_sharing_partners: Optional[list[str]] = None,
    privacy_policy_version: str = PRIVACY_POLICY_VERSION,
    db_path: Path = PROFILE_DB_PATH,
) -> None:
    """
    Record explicit consent choices. Call whenever user updates privacy settings.
    Overwrites previous consent record — full state is always stored, not deltas.
    """
    partners = data_sharing_partners or []
    invalid = set(partners) - VALID_PARTNERS
    if invalid:
        raise ValueError(f"Unknown partner keys: {invalid}. Valid: {VALID_PARTNERS}")

    if consent_data_sharing and not partners:
        raise ValueError(
            "data_sharing_partners must be non-empty when consent_data_sharing=True"
        )

    conn = get_connection(db_path)
    try:
        conn.execute("""
            UPDATE users SET
                consent_telemetry = ?,
                consent_leaderboard = ?,
                consent_data_sharing = ?,
                data_sharing_partners = ?,
                privacy_policy_version = ?,
                consent_recorded_at = ?
            WHERE user_id = ?
        """, (
            consent_telemetry,
            consent_leaderboard,
            consent_data_sharing,
            json.dumps(sorted(partners)),
            privacy_policy_version,
            datetime.now(timezone.utc).isoformat(),
            user_id,
        ))
        conn.commit()
    finally:
        conn.close()


def register_hardware_profile(
    user_id: str,
    hardware: dict,
    nickname: str,
    db_path: Path = PROFILE_DB_PATH,
) -> str:
    """
    Save a hardware configuration for this user. Returns profile_id.

    hardware keys mirror hw_* columns in logger.py benchmark_runs:
    cpu, gpu, vram_gb, ram_gb, ram_channels, npu_tops, storage_type, cooling
    """
    if not nickname or len(nickname) > 100:
        raise ValueError("nickname must be 1-100 characters")
    for key in ['cpu', 'gpu']:
        val = hardware.get(key)
        if not isinstance(val, str) or len(val) > 200:
            raise ValueError(f"hardware.{key} must be a string <= 200 chars")

    profile_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO hardware_profiles (
                profile_id, user_id, nickname, created_at, last_used,
                hw_cpu, hw_gpu, hw_vram_gb, hw_ram_gb, hw_ram_channels,
                hw_npu_tops, hw_storage_type, hw_cooling
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile_id, user_id, nickname, now, now,
            hardware.get('cpu', 'unknown'),
            hardware.get('gpu', 'unknown'),
            hardware.get('vram_gb'),
            hardware.get('ram_gb', 0),
            hardware.get('ram_channels', 1),
            hardware.get('npu_tops'),
            hardware.get('storage_type'),
            hardware.get('cooling'),
        ))
        conn.commit()
    finally:
        conn.close()

    return profile_id


def link_run(
    user_id: str,
    run_id: str,
    spec_version: str,
    hardware_profile_id: Optional[str] = None,
    is_public: bool = False,
    aggregate_cache: Optional[dict] = None,
    db_path: Path = PROFILE_DB_PATH,
) -> None:
    """
    Associate a benchmark run (from logger.py) with a user account.

    aggregate_cache: pass finalized aggregate stats from logger to avoid cross-DB
    joins on every leaderboard query. Keys: etps_sustained, etps_peak,
    tps_raw_median, quality_factor_median, seit, watts_avg, power_source,
    sw_model_name, sw_quantization, sw_memory_system
    """
    c = aggregate_cache or {}
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO user_run_links (
                user_id, run_id, hardware_profile_id, submitted_at,
                is_public, spec_version,
                etps_sustained, etps_peak, tps_raw_median, quality_factor_median,
                seit, watts_avg, power_source,
                sw_model_name, sw_quantization, sw_memory_system
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, run_id, hardware_profile_id,
            datetime.now(timezone.utc).isoformat(),
            is_public, spec_version,
            c.get('etps_sustained'), c.get('etps_peak'),
            c.get('tps_raw_median'), c.get('quality_factor_median'),
            c.get('seit'), c.get('watts_avg'), c.get('power_source'),
            c.get('sw_model_name'), c.get('sw_quantization'), c.get('sw_memory_system'),
        ))

        # Touch last_used on the hardware profile
        if hardware_profile_id:
            conn.execute("""
                UPDATE hardware_profiles SET last_used = ? WHERE profile_id = ?
            """, (datetime.now(timezone.utc).isoformat(), hardware_profile_id))

        # Touch last_active on the user
        conn.execute("""
            UPDATE users SET last_active = ? WHERE user_id = ?
        """, (datetime.now(timezone.utc).isoformat(), user_id))

        conn.commit()
    finally:
        conn.close()


def get_user_history(
    user_id: str,
    limit: int = 100,
    db_path: Path = PROFILE_DB_PATH,
) -> list[dict]:
    """Return a user's benchmark run history, most recent first."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT
                url.run_id, url.submitted_at, url.is_public, url.spec_version,
                url.etps_sustained, url.etps_peak, url.tps_raw_median,
                url.quality_factor_median, url.seit, url.watts_avg, url.power_source,
                url.sw_model_name, url.sw_quantization, url.sw_memory_system,
                hp.nickname as hw_nickname,
                hp.hw_cpu, hp.hw_gpu, hp.hw_ram_gb, hp.hw_ram_channels, hp.hw_npu_tops
            FROM user_run_links url
            LEFT JOIN hardware_profiles hp ON url.hardware_profile_id = hp.profile_id
            WHERE url.user_id = ?
            ORDER BY url.submitted_at DESC
            LIMIT ?
        """, (user_id, min(limit, 500))).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_hardware_profiles(
    user_id: str,
    db_path: Path = PROFILE_DB_PATH,
) -> list[dict]:
    """Return all hardware profiles for a user."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT * FROM hardware_profiles
            WHERE user_id = ?
            ORDER BY last_used DESC
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def export_for_partners(
    partner_key: str,
    spec_version: Optional[str] = None,
    db_path: Path = PROFILE_DB_PATH,
) -> dict:
    """
    Build an anonymized aggregate export for a declared partner category.

    Only includes results from users who have:
    - consent_data_sharing = TRUE
    - partner_key present in data_sharing_partners

    Returns aggregate statistics grouped by hardware configuration and model.
    No individual user_id or email is included in the export.

    partner_key: one of 'ai_companies', 'hardware_vendors', 'researchers'
    """
    if partner_key not in VALID_PARTNERS:
        raise ValueError(f"Unknown partner_key: {partner_key}. Valid: {VALID_PARTNERS}")

    conn = get_connection(db_path)
    try:
        conditions = [
            "u.consent_data_sharing = TRUE",
            "json_each.value = ?",
            "url.is_public = TRUE",
        ]
        params = [partner_key]

        if spec_version:
            conditions.append("url.spec_version = ?")
            params.append(spec_version)

        where = " AND ".join(conditions)

        rows = conn.execute(f"""
            SELECT
                hp.hw_cpu,
                hp.hw_gpu,
                hp.hw_ram_gb,
                hp.hw_ram_channels,
                hp.hw_npu_tops,
                url.sw_model_name,
                url.sw_quantization,
                url.sw_memory_system,
                url.spec_version,
                COUNT(*) as result_count,
                AVG(url.etps_sustained) as etps_avg,
                MAX(url.etps_peak) as etps_peak,
                AVG(url.tps_raw_median) as tps_avg,
                AVG(url.quality_factor_median) as quality_avg,
                AVG(url.seit) as seit_avg
            FROM user_run_links url
            JOIN users u ON url.user_id = u.user_id
            LEFT JOIN hardware_profiles hp ON url.hardware_profile_id = hp.profile_id
            JOIN json_each(u.data_sharing_partners) ON {where}
            GROUP BY
                hp.hw_cpu, hp.hw_gpu, hp.hw_ram_gb, hp.hw_ram_channels,
                hp.hw_npu_tops, url.sw_model_name, url.sw_quantization,
                url.sw_memory_system, url.spec_version
            HAVING result_count >= 1
            ORDER BY etps_avg DESC
        """, params).fetchall()

        return {
            "partner": partner_key,
            "spec_version": spec_version or "all",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
            "record_count": len(rows),
            "data": [dict(row) for row in rows],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import tempfile

    print("Running user_profile smoke test...\n")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = Path(f.name)

    initialize_schema(test_db)
    print("Schema initialized.")

    # Anonymous user
    anon = create_user(db_path=test_db)
    assert anon['is_anonymous'] is True
    assert anon['token']
    print(f"Anonymous user created: {anon['display_name']} ({anon['user_id'][:8]}...)")

    # Registered user
    reg = create_user(
        display_name="Joshua Holliday",
        email="test@example.com",
        db_path=test_db,
    )
    assert reg['is_anonymous'] is False
    print(f"Registered user created: {reg['display_name']}")

    # Token lookup
    found = get_user_by_token(reg['token'], db_path=test_db)
    assert found['display_name'] == "Joshua Holliday"
    print(f"Token lookup: OK")

    # Consent update
    update_consent(
        user_id=reg['user_id'],
        consent_telemetry=True,
        consent_leaderboard=True,
        consent_data_sharing=True,
        data_sharing_partners=["ai_companies", "hardware_vendors"],
        db_path=test_db,
    )
    print("Consent updated: telemetry=True, leaderboard=True, data_sharing=True")

    # Hardware profile
    hw_profile_id = register_hardware_profile(
        user_id=reg['user_id'],
        hardware={
            'cpu': 'AMD Ryzen AI 9 HX 470',
            'gpu': 'Radeon 890M',
            'ram_gb': 32,
            'ram_channels': 2,
            'npu_tops': 86,
            'storage_type': 'NVMe PCIe 4.0',
            'cooling': 'active',
        },
        nickname="Legion 5i AI",
        db_path=test_db,
    )
    print(f"Hardware profile registered: {hw_profile_id[:8]}...")

    # Link a run
    link_run(
        user_id=reg['user_id'],
        run_id="test-run-uuid-001",
        spec_version="v0.1",
        hardware_profile_id=hw_profile_id,
        is_public=True,
        aggregate_cache={
            'etps_sustained': 38.2,
            'etps_peak': 43.1,
            'tps_raw_median': 44.0,
            'quality_factor_median': 0.91,
            'seit': 1.364,
            'watts_avg': 28.0,
            'power_source': 'measured',
            'sw_model_name': 'Qwen3.5-9B',
            'sw_quantization': 'Q4_K_XL',
            'sw_memory_system': 'nyx_v2',
        },
        db_path=test_db,
    )
    print("Run linked to user.")

    # History
    history = get_user_history(reg['user_id'], db_path=test_db)
    assert len(history) == 1
    assert history[0]['sw_model_name'] == 'Qwen3.5-9B'
    print(f"History: {len(history)} run(s), eTPS={history[0]['etps_sustained']}")

    # Hardware profiles list
    profiles = get_hardware_profiles(reg['user_id'], db_path=test_db)
    assert len(profiles) == 1
    assert profiles[0]['nickname'] == 'Legion 5i AI'
    print(f"Hardware profiles: {profiles[0]['nickname']}")

    # Partner export
    export = export_for_partners("ai_companies", spec_version="v0.1", db_path=test_db)
    assert export['partner'] == 'ai_companies'
    assert export['record_count'] == 1
    assert export['data'][0]['hw_cpu'] == 'AMD Ryzen AI 9 HX 470'
    print(f"Partner export: {export['record_count']} record(s) for ai_companies")

    # Consent guard: data_sharing=True requires partners list
    try:
        update_consent(
            user_id=reg['user_id'],
            consent_telemetry=False,
            consent_leaderboard=False,
            consent_data_sharing=True,
            data_sharing_partners=[],
            db_path=test_db,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"Consent guard: OK ({e})")

    test_db.unlink()
    print("\nUser profile smoke test passed.")
