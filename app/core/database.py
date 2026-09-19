import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.config import settings


def get_db_path() -> Path:
    db_rel = settings.paths.database
    db_path = settings.paths.absolute(db_rel)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Schema migration tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """)

    # 1. Projects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        description TEXT DEFAULT '',
        style_id TEXT DEFAULT 'STYLE_SERIES_A_V001',
        autonomy_mode TEXT DEFAULT 'review',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # 2. Durable Jobs Queue
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS render_jobs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        episode_id TEXT,
        shot_id TEXT,
        kind TEXT NOT NULL,
        priority INTEGER DEFAULT 50,
        status TEXT NOT NULL,
        payload_json TEXT DEFAULT '{}',
        attempt INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        backend TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        heartbeat_at TEXT,
        error_class TEXT,
        error_message TEXT,
        output_asset_ids TEXT DEFAULT '[]',
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 3. Global GPU Lease
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_lease (
        resource TEXT PRIMARY KEY,
        owner_job_id TEXT,
        token TEXT,
        acquired_at TEXT,
        heartbeat_at TEXT
    )
    """)

    # Ensure default GPU0_HEAVY row exists
    cursor.execute("""
    INSERT OR IGNORE INTO gpu_lease (resource, owner_job_id, token, acquired_at, heartbeat_at)
    VALUES ('GPU0_HEAVY', NULL, NULL, NULL, NULL)
    """)

    # 4. Canonical Assets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        tier INTEGER DEFAULT 0,
        kind TEXT NOT NULL,
        version TEXT NOT NULL,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        metadata_json TEXT DEFAULT '{}',
        provenance_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # Record migration v1
    cursor.execute("""
    INSERT OR IGNORE INTO schema_migrations (version, applied_at)
    VALUES (1, ?)
    """, (datetime.utcnow().isoformat(),))

    conn.commit()
    conn.close()
