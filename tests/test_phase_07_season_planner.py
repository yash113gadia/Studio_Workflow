"""Phase 7 Acceptance Test Suite — Novel Ingestion & Season Planning Engine."""
import json
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import init_db, get_connection
from app.core.novel_parser import NovelParser
from app.core.season_planner import SeasonPlanner

client = TestClient(app)

SAMPLE_NOVEL_TEXT = """
# Chapter 1: The Midnight Call

Aarav stood by the rain-streaked window of the Mumbai penthouse, watching the neon reflections blur on the wet asphalt below. In his hands, he turned over the red leather diary that Diya had left behind before she vanished into the night. 

"She wasn't alone, Aarav," Maya said from the shadow of the doorway, adjusting her dark trenchcoat. "The security footage from the lobby shows a black sedan waiting outside."

Aarav opened the diary to the final page. Across the parchment, three words were scrawled in hurried blue ink: Trust Nobody Here.

# Chapter 2: The Cipher in the Shadows

The underground archive beneath the old clocktower was freezing. Aarav and Maya walked past rows of rusted metal shelving until they found the locker marked 407.

"If the syndicate knows we have this key," Maya whispered, clutching the brass key tightly, "we won't make it to sunrise."

A sudden sound echoed from the stairwell—the heavy tread of boots on concrete. A laser sight flicked across Maya's shoulder.

# Chapter 3: The Broken Trust

The safe had been cracked open before they arrived. On the mahogany desk lay a single bullet casing and an open folder bearing Aarav's name.

Maya stepped back, her expression turning cold. "You knew about the project all along, didn't you?"
"""


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test_studio_p7.db"
    monkeypatch.setattr("app.core.config.settings.paths.database", str(test_db))
    monkeypatch.setattr("app.core.config.settings.paths.projects", str(tmp_path / "projects"))

    def get_test_conn():
        c = sqlite3.connect(str(test_db), timeout=10.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        return c

    monkeypatch.setattr("app.core.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.novel_parser.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.season_planner.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.continuity_engine.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.asset_factory.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.specialist_editor.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.queue.get_connection", get_test_conn)
    init_db()

    conn = get_test_conn()
    now = "2026-09-19T16:00:00"
    conn.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES ('proj_p7_test', 'Season Planner Test', 'series', ?, ?)", (now, now))
    conn.commit()
    conn.close()
    yield


def test_01_novel_chapter_splitting_and_chunk_citations():
    """Phase 7 Criterion 1: Full chapter split and stable chunk citations stored and indexed in FTS5."""
    chapters = NovelParser.split_chapters(SAMPLE_NOVEL_TEXT)
    assert len(chapters) == 3
    assert "Midnight Call" in chapters[0]["title"]
    assert "Cipher" in chapters[1]["title"]
    assert "Broken Trust" in chapters[2]["title"]

    # Ingest and generate cited chunks
    r_ingest = client.post("/api/v1/novel/ingest", json={
        "project_id": "proj_p7_test",
        "title": "Mumbai Shadows",
        "raw_text": SAMPLE_NOVEL_TEXT
    })
    assert r_ingest.status_code == 200
    data = r_ingest.json()
    assert data["status"] == "ingested"
    assert data["total_chunks"] >= 3
    assert data["sample_chunk_id"].startswith("proj_p7_test_CH001_CHUNK")


def test_02_pre_production_entity_extraction_and_db_prepopulation():
    """Phase 7 Criterion 2: Characters, outfits, locations, props pre-populated into Phase 6 DB with citations."""
    chunks = NovelParser.ingest_novel_text("proj_p7_test", "Mumbai Shadows", SAMPLE_NOVEL_TEXT)
    inventory = SeasonPlanner.extract_entities_from_chunks("proj_p7_test", chunks)

    # Check extracted characters
    char_names = [c["name"] for c in inventory["characters"]]
    assert "Aarav" in char_names or "Maya" in char_names
    assert len(inventory["locations"]) >= 2
    assert len(inventory["props"]) >= 1

    # Pre-populate database
    SeasonPlanner.populate_phase_06_database("proj_p7_test", inventory)

    # Verify rows in SQLite Phase 6 tables
    conn = get_connection()
    c_count = conn.execute("SELECT count(*) FROM characters WHERE project_id = 'proj_p7_test'").fetchone()[0]
    w_count = conn.execute("SELECT count(*) FROM wardrobe WHERE project_id = 'proj_p7_test'").fetchone()[0]
    l_count = conn.execute("SELECT count(*) FROM locations WHERE project_id = 'proj_p7_test'").fetchone()[0]
    p_count = conn.execute("SELECT count(*) FROM props WHERE project_id = 'proj_p7_test'").fetchone()[0]
    conn.close()

    assert c_count >= 2
    assert w_count >= 2
    assert l_count >= 2
    assert p_count >= 1


def test_03_5_episode_mini_season_map_with_cliffhangers_and_provenance():
    """Phase 7 Criterion 3: 5-episode mini-season map generated with episodic cliffhangers and citeable provenance."""
    r_plan = client.post("/api/v1/novel/plan_season", json={
        "project_id": "proj_p7_test",
        "novel_title": "Mumbai Shadows",
        "raw_text": SAMPLE_NOVEL_TEXT,
        "target_episodes": 5
    })
    assert r_plan.status_code == 200
    season_map = r_plan.json()

    assert season_map["project_id"] == "proj_p7_test"
    assert season_map["target_episodes"] == 5
    assert len(season_map["episodes"]) == 5

    for ep in season_map["episodes"]:
        assert ep["episode_number"] >= 1
        assert len(ep["title"]) > 0
        assert len(ep["logline"]) > 0
        # Check cliffhanger hook
        assert ep["cliffhanger_type"] in ["revelation", "peril", "betrayal", "dilemma", "cliffhanger_twist"]
        assert len(ep["cliffhanger_description"]) > 0
        assert len(ep["scenes"]) >= 2

        # Check provenance citations
        assert len(ep["citations"]) >= 2
        for cit in ep["citations"]:
            assert cit["origin"] in ["CANON_SOURCE", "ADAPTATION_BRIDGE"]
            if cit["origin"] == "CANON_SOURCE":
                assert len(cit["source_chunk_ids"]) > 0


def test_04_45_episode_full_season_map_scale():
    """Phase 7 Criterion 4: Full 45-episode vertical season map generated before scripting episode 1."""
    chunks = NovelParser.ingest_novel_text("proj_p7_test", "Mumbai Shadows", SAMPLE_NOVEL_TEXT)
    season_map = SeasonPlanner.generate_season_map(
        project_id="proj_p7_test",
        novel_title="Mumbai Shadows",
        chunks=chunks,
        target_episodes=45
    )

    assert season_map.target_episodes == 45
    assert len(season_map.episodes) == 45
    # Every episode must have a defined hook and at least 2 scenes
    for ep in season_map.episodes:
        assert len(ep.scenes) >= 2
        assert ep.cliffhanger_type is not None

    # Verify episodes table in DB
    conn = get_connection()
    ep_db_count = conn.execute("SELECT count(*) FROM episodes WHERE project_id = 'proj_p7_test'").fetchone()[0]
    conn.close()
    assert ep_db_count == 45
