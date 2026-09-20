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

get_db_connection = get_connection


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

    # Shared library project: home for standalone uploads and generated images
    # that don't belong to a specific creator-mode render project.
    _now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT OR IGNORE INTO projects (id, name, kind, description, created_at, updated_at)
    VALUES ('LIBRARY', 'Shared Library', 'library', 'Uploaded and standalone generated images', ?, ?)
    """, (_now, _now))

    # ========================================================
    # Phase 6: Asset Registry, World Memory & Canon Continuity
    # ========================================================

    # 5. Characters & Versions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS characters (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        tier INTEGER DEFAULT 0,
        bio TEXT DEFAULT '',
        visual_description TEXT DEFAULT '',
        canonical_asset_id TEXT,
        voice_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 6. Wardrobe Outfits
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wardrobe (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        name TEXT NOT NULL,
        top TEXT DEFAULT '',
        bottom TEXT DEFAULT '',
        footwear TEXT DEFAULT '',
        accessories TEXT DEFAULT '',
        palette_json TEXT DEFAULT '[]',
        continuity_tags_json TEXT DEFAULT '{}',
        forbidden_additions_json TEXT DEFAULT '[]',
        asset_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
    )
    """)

    # 7. Locations & Recurring Sets
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        setting_type TEXT DEFAULT 'interior',
        description TEXT DEFAULT '',
        floorplan_asset_id TEXT,
        master_wide_asset_id TEXT,
        camera_positions_json TEXT DEFAULT '[]',
        lighting_recipes_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 8. Location States (e.g. pristine, damaged, trashed, renovated)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS location_states (
        id TEXT PRIMARY KEY,
        location_id TEXT NOT NULL,
        state_name TEXT NOT NULL,
        description TEXT DEFAULT '',
        visual_delta_json TEXT DEFAULT '{}',
        asset_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
    )
    """)

    # 9. Props & Vehicles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS props (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        prop_type TEXT DEFAULT 'object',
        owner_character_id TEXT,
        current_holder_id TEXT,
        location_id TEXT,
        current_state TEXT DEFAULT 'pristine',
        narrative_significance TEXT DEFAULT '',
        asset_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 10. Prop States
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prop_states (
        id TEXT PRIMARY KEY,
        prop_id TEXT NOT NULL,
        state_name TEXT NOT NULL,
        description TEXT DEFAULT '',
        is_damaged BOOLEAN DEFAULT 0,
        asset_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (prop_id) REFERENCES props(id) ON DELETE CASCADE
    )
    """)

    # 11. Voices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voices (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        name TEXT NOT NULL,
        engine TEXT DEFAULT 'chatterbox',
        language TEXT DEFAULT 'en',
        accent TEXT DEFAULT '',
        pace REAL DEFAULT 1.0,
        pitch REAL DEFAULT 0.0,
        canonical_audio_path TEXT DEFAULT '',
        pronunciation_notes_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 12. Character Relationships
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relationships (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        char_a_id TEXT NOT NULL,
        char_b_id TEXT NOT NULL,
        relation_type TEXT NOT NULL,
        sentiment_score REAL DEFAULT 0.0,
        knowledge_state_json TEXT DEFAULT '{}',
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (char_a_id) REFERENCES characters(id) ON DELETE CASCADE,
        FOREIGN KEY (char_b_id) REFERENCES characters(id) ON DELETE CASCADE
    )
    """)

    # 13. Episodes, Scenes, Shots
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episodes (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        episode_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        logline TEXT DEFAULT '',
        status TEXT DEFAULT 'DRAFT',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id TEXT PRIMARY KEY,
        episode_id TEXT NOT NULL,
        scene_number INTEGER NOT NULL,
        location_id TEXT,
        location_state_id TEXT,
        time_of_day TEXT DEFAULT 'day',
        story_time_timestamp TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        status TEXT DEFAULT 'PLANNED',
        created_at TEXT NOT NULL,
        FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
        FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shots (
        id TEXT PRIMARY KEY,
        scene_id TEXT NOT NULL,
        shot_number INTEGER NOT NULL,
        camera_slot TEXT DEFAULT 'CAM_WIDE',
        line_of_action_id TEXT DEFAULT 'LINE_01',
        duration_seconds REAL DEFAULT 3.0,
        action_prompt TEXT NOT NULL,
        dialogue_text TEXT DEFAULT '',
        status TEXT DEFAULT 'QUEUED',
        created_at TEXT NOT NULL,
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
    )
    """)

    # 14. World State Snapshots per Scene
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scene_character_states (
        id TEXT PRIMARY KEY,
        scene_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        wardrobe_id TEXT,
        held_prop_id TEXT,
        injury_state TEXT DEFAULT 'none',
        emotional_state TEXT DEFAULT 'neutral',
        blocking_mark TEXT DEFAULT 'MARK_CENTER',
        screen_side TEXT DEFAULT 'center',
        visual_overrides_json TEXT DEFAULT '{}',
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
        FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scene_location_states (
        id TEXT PRIMARY KEY,
        scene_id TEXT NOT NULL,
        location_id TEXT NOT NULL,
        state_id TEXT,
        lighting_state TEXT DEFAULT 'day',
        environmental_conditions_json TEXT DEFAULT '{}',
        FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
        FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
    )
    """)

    # 15. Continuity Events (Changes in wardrobe, injuries, damage)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS continuity_events (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        scene_id TEXT,
        shot_id TEXT,
        event_type TEXT NOT NULL,
        target_entity_type TEXT NOT NULL,
        target_entity_id TEXT NOT NULL,
        from_state TEXT,
        to_state TEXT NOT NULL,
        narrative_rationale TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 16. SQLite FTS5 Virtual Table for Canon & Novel Knowledge
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS canon_knowledge_fts USING fts5(
        entity_id,
        entity_type,
        title,
        content,
        tokenize='porter unicode61'
    )
    """)

    # Record migration v2
    cursor.execute("""
    INSERT OR IGNORE INTO schema_migrations (version, applied_at)
    VALUES (2, ?)
    """, (datetime.utcnow().isoformat(),))

    # ========================================================
    # Phase 8: Visual QA v1: DINO Embeddings & Candidate Reranking
    # ========================================================

    # 17. Visual Embeddings Cache
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visual_embeddings (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        sub_slot TEXT DEFAULT 'CANON_DEFAULT',
        asset_id TEXT,
        model_name TEXT NOT NULL,
        dim INTEGER NOT NULL,
        embedding_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 18. Candidate Evaluations & Multi-Candidate Reranking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_evaluations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        shot_id TEXT,
        candidate_id TEXT NOT NULL,
        candidate_path TEXT NOT NULL,
        character_id TEXT,
        location_id TEXT,
        raw_scores_json TEXT NOT NULL,
        normalized_scores_json TEXT NOT NULL,
        composite_score REAL NOT NULL,
        rank INTEGER DEFAULT 1,
        status TEXT DEFAULT 'ALTERNATIVE',
        is_winner INTEGER DEFAULT 0,
        rejection_reasons_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    """)

    # 19. Longitudinal Identity Drift Tracker
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS qa_drift_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        episode_id TEXT,
        scene_id TEXT,
        shot_id TEXT,
        candidate_id TEXT,
        similarity_to_canonical REAL NOT NULL,
        rolling_average REAL NOT NULL,
        drift_delta REAL NOT NULL,
        flagged_warning INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
    )
    """)

    # Record migration v3
    cursor.execute("""
    INSERT OR IGNORE INTO schema_migrations (version, applied_at)
    VALUES (3, ?)
    """, (datetime.utcnow().isoformat(),))

    conn.commit()
    conn.close()

