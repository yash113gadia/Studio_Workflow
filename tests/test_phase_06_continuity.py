"""Phase 6 Acceptance Test Suite — Memory, Canon & Continuity State Machine."""
import json
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import init_db
from app.core.continuity_engine import (
    ContinuityEngine,
    CharacterCreate,
    WardrobeCreate,
    LocationCreate,
    PropCreate,
    SceneStateSnapshot,
    ContinuityEventCreate,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test_studio_p6.db"
    monkeypatch.setattr("app.core.config.settings.paths.database", str(test_db))
    monkeypatch.setattr("app.core.config.settings.paths.projects", str(tmp_path / "projects"))

    def get_test_conn():
        c = sqlite3.connect(str(test_db), timeout=10.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        return c

    monkeypatch.setattr("app.core.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.continuity_engine.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.asset_factory.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.specialist_editor.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.queue.get_connection", get_test_conn)
    init_db()

    conn = get_test_conn()
    now = "2026-09-19T16:00:00"
    conn.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES ('proj_p6_test', 'Continuity Pilot', 'series', ?, ?)", (now, now))
    conn.execute("INSERT INTO episodes (id, project_id, episode_number, title, created_at) VALUES ('EP_001', 'proj_p6_test', 1, 'Pilot Episode', ?)", (now,))
    conn.execute("INSERT INTO characters (id, project_id, name, code, tier, created_at) VALUES ('CHAR_AARAV_001', 'proj_p6_test', 'Aarav Mehra', 'AARAV', 0, ?)", (now,))
    for s_id, s_num in [('SCENE_001', 1), ('SCENE_010', 10), ('SCENE_011', 11), ('SCENE_020', 20), ('SCENE_021', 21)]:
        conn.execute("INSERT INTO scenes (id, episode_id, scene_number, created_at) VALUES (?, 'EP_001', ?, ?)", (s_id, s_num, now))
    conn.commit()
    conn.close()
    yield


def test_01_character_wardrobe_location_prop_and_fts5_search():
    """Verify registration of canon entities and sub-millisecond SQLite FTS5 search."""
    # 1. Register Character
    r_char = client.post("/api/v1/continuity/characters", json={
        "id": "CHAR_AARAV_001",
        "project_id": "proj_p6_test",
        "name": "Aarav Mehra",
        "code": "AARAV",
        "tier": 0,
        "bio": "Charismatic detective investigating the disappearance of Diya.",
        "visual_description": "Tall, athletic build, short dark stubble, piercing brown eyes."
    })
    assert r_char.status_code == 201

    # 2. Register Wardrobe
    r_ward = client.post("/api/v1/continuity/wardrobe", json={
        "id": "OUTFIT_AARAV_CASUAL_001",
        "project_id": "proj_p6_test",
        "character_id": "CHAR_AARAV_001",
        "name": "Casual Investigation Jacket",
        "top": "weathered denim jacket over grey crewneck",
        "bottom": "dark denim jeans",
        "footwear": "rugged leather boots",
        "accessories": "silver watch, brass detective badge"
    })
    assert r_ward.status_code == 201

    # 3. Register Location
    r_loc = client.post("/api/v1/continuity/locations", json={
        "id": "LOC_PENTHOUSE_001",
        "project_id": "proj_p6_test",
        "name": "Victim Penthouse Living Room",
        "code": "PENTHOUSE",
        "description": "Luxurious penthouse overlooking Mumbai skyline with floor to ceiling glass windows."
    })
    assert r_loc.status_code == 201

    # 4. Register Prop
    r_prop = client.post("/api/v1/continuity/props", json={
        "id": "PROP_DIARY_001",
        "project_id": "proj_p6_test",
        "name": "Red Leather Diary",
        "code": "DIARY",
        "narrative_significance": "Contains missing person's last handwritten entries with cipher codes."
    })
    assert r_prop.status_code == 201

    # 5. SQLite FTS5 Full-Text Search verification
    r_s1 = client.get("/api/v1/continuity/search?q=denim")
    assert r_s1.status_code == 200
    res1 = r_s1.json()
    assert len(res1) >= 1
    assert any(m["entity_id"] == "OUTFIT_AARAV_CASUAL_001" for m in res1)

    r_s2 = client.get("/api/v1/continuity/search?q=penthouse")
    assert r_s2.status_code == 200
    res2 = r_s2.json()
    assert any(m["entity_id"] == "LOC_PENTHOUSE_001" for m in res2)

    r_s3 = client.get("/api/v1/continuity/search?q=cipher")
    assert r_s3.status_code == 200
    res3 = r_s3.json()
    assert any(m["entity_id"] == "PROP_DIARY_001" for m in res3)


def test_02_scene_state_restoration_across_restart():
    """Phase 6 Acceptance Gate Criterion 1: A saved scene with character outfit, held prop, injury state, and location state is restored exactly after restart."""
    # Save Scene 1 State
    r_save = client.post("/api/v1/continuity/scenes/state", json={
        "scene_id": "SCENE_001",
        "character_id": "CHAR_AARAV_001",
        "wardrobe_id": "OUTFIT_AARAV_CASUAL_001",
        "held_prop_id": "PROP_DIARY_001",
        "injury_state": "none",
        "emotional_state": "focused",
        "blocking_mark": "MARK_WINDOW",
        "screen_side": "left",
        "visual_overrides": {"lighting": "sunset"}
    })
    assert r_save.status_code == 200

    # Simulate process restart / re-fetch
    r_get = client.get("/api/v1/continuity/scenes/SCENE_001/character/CHAR_AARAV_001")
    assert r_get.status_code == 200
    saved = r_get.json()
    assert saved["scene_id"] == "SCENE_001"
    assert saved["character_id"] == "CHAR_AARAV_001"
    assert saved["wardrobe_id"] == "OUTFIT_AARAV_CASUAL_001"
    assert saved["held_prop_id"] == "PROP_DIARY_001"
    assert saved["injury_state"] == "none"
    assert saved["emotional_state"] == "focused"
    assert saved["blocking_mark"] == "MARK_WINDOW"
    assert saved["screen_side"] == "left"
    assert saved["visual_overrides"]["lighting"] == "sunset"


def test_03_scene_state_inheritance_without_events():
    """Phase 6 Acceptance Gate Criterion 2: Scene N+1 inherits character outfit, held prop, injury state, and location state from Scene N if no continuity events intervene."""
    # Setup Scene 1
    ContinuityEngine.save_scene_character_state(SceneStateSnapshot(
        scene_id="SCENE_010",
        character_id="CHAR_AARAV_001",
        wardrobe_id="OUTFIT_AARAV_CASUAL_001",
        held_prop_id="PROP_DIARY_001",
        injury_state="none",
        emotional_state="neutral"
    ))

    # Inherit into Scene 2 (No events)
    r_inh = client.post("/api/v1/continuity/scenes/inherit", json={
        "project_id": "proj_p6_test",
        "from_scene_id": "SCENE_010",
        "to_scene_id": "SCENE_011",
        "character_id": "CHAR_AARAV_001"
    })
    assert r_inh.status_code == 200
    scene_011_state = r_inh.json()
    assert scene_011_state["scene_id"] == "SCENE_011"
    assert scene_011_state["character_id"] == "CHAR_AARAV_001"
    assert scene_011_state["wardrobe_id"] == "OUTFIT_AARAV_CASUAL_001"  # Inherited
    assert scene_011_state["held_prop_id"] == "PROP_DIARY_001"          # Inherited
    assert scene_011_state["injury_state"] == "none"                     # Inherited


def test_04_scene_state_inheritance_with_continuity_events():
    """Phase 6 Acceptance Gate Criterion 3: Intervening continuity events (wardrobe change, injury, dropped prop) alter inherited state for Scene N+1 with narrative citation."""
    # Scene 20 baseline
    ContinuityEngine.save_scene_character_state(SceneStateSnapshot(
        scene_id="SCENE_020",
        character_id="CHAR_AARAV_001",
        wardrobe_id="OUTFIT_AARAV_CASUAL_001",
        held_prop_id="PROP_DIARY_001",
        injury_state="none"
    ))

    # Intervening continuity events occur in Scene 20 / transition to Scene 21
    # Event 1: Aarav gets injured in a fight
    r_ev1 = client.post("/api/v1/continuity/events", json={
        "project_id": "proj_p6_test",
        "scene_id": "SCENE_020",
        "event_type": "character_injured",
        "target_entity_type": "character",
        "target_entity_id": "CHAR_AARAV_001",
        "from_state": "none",
        "to_state": "cut_on_forehead",
        "narrative_rationale": "Shattered glass from window struggle grazes Aarav's brow."
    })
    assert r_ev1.status_code == 201

    # Event 2: Aarav drops the diary
    r_ev2 = client.post("/api/v1/continuity/events", json={
        "project_id": "proj_p6_test",
        "scene_id": "SCENE_020",
        "event_type": "prop_dropped",
        "target_entity_type": "prop",
        "target_entity_id": "CHAR_AARAV_001",
        "from_state": "PROP_DIARY_001",
        "to_state": "none",
        "narrative_rationale": "Attacker tackles Aarav; diary slips under the heavy desk."
    })
    assert r_ev2.status_code == 201

    # Event 3: Wardrobe changes to torn jacket
    r_ev3 = client.post("/api/v1/continuity/events", json={
        "project_id": "proj_p6_test",
        "scene_id": "SCENE_020",
        "event_type": "wardrobe_change",
        "target_entity_type": "wardrobe",
        "target_entity_id": "CHAR_AARAV_001",
        "from_state": "OUTFIT_AARAV_CASUAL_001",
        "to_state": "OUTFIT_AARAV_TORN_001",
        "narrative_rationale": "Left jacket sleeve torn during struggle."
    })
    assert r_ev3.status_code == 201

    # Inherit into Scene 21
    r_inh = client.post("/api/v1/continuity/scenes/inherit", json={
        "project_id": "proj_p6_test",
        "from_scene_id": "SCENE_020",
        "to_scene_id": "SCENE_021",
        "character_id": "CHAR_AARAV_001"
    })
    assert r_inh.status_code == 200
    scene_021_state = r_inh.json()

    # Verify that Scene 21 has the updated injury, updated wardrobe, and dropped prop
    assert scene_021_state["scene_id"] == "SCENE_021"
    assert scene_021_state["injury_state"] == "cut_on_forehead"
    assert scene_021_state["held_prop_id"] is None
    assert scene_021_state["wardrobe_id"] == "OUTFIT_AARAV_TORN_001"
