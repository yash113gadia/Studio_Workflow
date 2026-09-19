import os
import uuid
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db, get_db_connection
from app.core.visual_qa.dino_extractor import DINOExtractor
from app.core.visual_qa.canon_registry import CanonVisualRegistry
from app.core.visual_qa.reranker import CandidateReranker
from app.core.visual_qa.drift_tracker import LongitudinalDriftTracker

client = TestClient(app)

FIXTURES_DIR = Path("tests/fixtures/qa")

@pytest.fixture(scope="module", autouse=True)
def setup_test_fixtures():
    init_db()
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Canonical Reference Character (Gold portrait on blue canvas)
    ref_char_img = Image.new("RGB", (256, 256), color=(30, 60, 120))
    draw = ImageDraw.Draw(ref_char_img)
    draw.ellipse((80, 50, 176, 160), fill=(240, 200, 140)) # Face
    draw.rectangle((60, 160, 196, 256), fill=(180, 40, 40)) # Red outfit
    ref_char_path = FIXTURES_DIR / "ref_character.png"
    ref_char_img.save(ref_char_path)

    # 2. Canonical Reference Location (Green park landscape with sun)
    ref_loc_img = Image.new("RGB", (256, 256), color=(100, 180, 240)) # Sky
    draw = ImageDraw.Draw(ref_loc_img)
    draw.ellipse((200, 20, 240, 60), fill=(255, 230, 50)) # Sun
    draw.rectangle((0, 140, 256, 256), fill=(40, 140, 40)) # Grass
    ref_loc_path = FIXTURES_DIR / "ref_location.png"
    ref_loc_img.save(ref_loc_path)

    # 3. Candidate 1 (High fidelity match: character in location)
    cand1_img = Image.new("RGB", (256, 256), color=(90, 170, 230))
    draw = ImageDraw.Draw(cand1_img)
    draw.ellipse((200, 20, 240, 60), fill=(255, 230, 50))
    draw.rectangle((0, 140, 256, 256), fill=(40, 140, 40))
    draw.ellipse((82, 52, 174, 158), fill=(240, 200, 140))
    draw.rectangle((62, 158, 194, 256), fill=(180, 40, 40))
    cand1_path = FIXTURES_DIR / "cand_01_high_match.png"
    cand1_img.save(cand1_path)

    # 4. Candidate 2 (Moderate match: character in location with alternate outfit)
    cand2_img = Image.new("RGB", (256, 256), color=(90, 170, 230))
    draw = ImageDraw.Draw(cand2_img)
    draw.rectangle((0, 140, 256, 256), fill=(40, 140, 40))
    draw.ellipse((80, 50, 176, 160), fill=(240, 200, 140))
    draw.rectangle((60, 160, 196, 256), fill=(20, 20, 120)) # Blue outfit
    cand2_path = FIXTURES_DIR / "cand_02_moderate_match.png"
    cand2_img.save(cand2_path)

    # 5. Candidate 3 (Mismatched / Drifted: grey dark scene, different colors)
    cand3_img = Image.new("RGB", (256, 256), color=(40, 40, 40))
    draw = ImageDraw.Draw(cand3_img)
    draw.rectangle((40, 40, 200, 200), fill=(90, 90, 90))
    cand3_path = FIXTURES_DIR / "cand_03_drifted_match.png"
    cand3_img.save(cand3_path)

    yield


def test_01_canonical_reference_embedding_registration():
    """Verify DINO extractor calculates 384-d normalized embeddings and registers them into visual_embeddings."""
    proj_id = f"PROJ_{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES (?, ?, 'series', ?, ?)",
                   (proj_id, "QA Test Project", "2026-09-19T00:00:00", "2026-09-19T00:00:00"))
    conn.commit()
    conn.close()

    registry = CanonVisualRegistry()
    char_img = str(FIXTURES_DIR / "ref_character.png")
    res = registry.register_canonical_reference(
        project_id=proj_id,
        entity_type="character",
        entity_id="CHAR_PREETI_V001",
        image_path=char_img,
        sub_slot="front"
    )

    assert res["project_id"] == proj_id
    assert res["entity_id"] == "CHAR_PREETI_V001"
    assert res["dim"] == 384

    # Verify retrieval
    emb = registry.get_canonical_embedding(proj_id, "character", "CHAR_PREETI_V001", "front")
    assert emb is not None
    assert len(emb) == 384

    # Check unit norm (magnitude ~= 1.0)
    magnitude = sum(x**2 for x in emb)**0.5
    assert 0.99 < magnitude < 1.01


def test_02_three_candidate_reranking_and_winner_selection():
    """Verify 3 test candidates are scored across components, normalized, ranked, and the top candidate wins."""
    proj_id = f"PROJ_{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES (?, ?, 'series', ?, ?)",
                   (proj_id, "QA Test Project", "2026-09-19T00:00:00", "2026-09-19T00:00:00"))
    conn.commit()
    conn.close()


    ref_char = str(FIXTURES_DIR / "ref_character.png")
    ref_loc = str(FIXTURES_DIR / "ref_location.png")
    candidates = [
        str(FIXTURES_DIR / "cand_01_high_match.png"),
        str(FIXTURES_DIR / "cand_02_moderate_match.png"),
        str(FIXTURES_DIR / "cand_03_drifted_match.png")
    ]

    shot_id = f"SHOT_TEST_{uuid.uuid4().hex[:8].upper()}"
    reranker = CandidateReranker(min_identity_threshold=0.60, min_composite_threshold=0.50)
    result = reranker.evaluate_and_rerank(
        project_id=proj_id,
        candidate_paths=candidates,
        shot_id=shot_id,
        ref_char_path=ref_char,
        ref_loc_path=ref_loc,
        character_id="CHAR_PREETI_V001",
        location_id="LOC_PARK"
    )

    assert result["total_candidates"] == 3
    assert result["status"] == "SUCCESS"
    assert result["winner"] is not None

    winner = result["winner"]
    assert winner["is_winner"] is True
    assert winner["status"] == "ACCEPTED"
    assert winner["rank"] == 1
    assert winner["composite_score"] > 0.80

    # Verify that the drifted candidate 3 was rejected
    drifted_cand = next(c for c in result["candidates"] if "cand_03_drifted_match" in c["candidate_path"])
    assert drifted_cand["status"] == "REJECTED"
    assert len(drifted_cand["rejections"]) > 0

    # Verify score components are present
    assert "whole_subject_similarity" in winner["raw_scores"]
    assert "identity_crop_similarity" in winner["raw_scores"]
    assert "location_similarity" in winner["raw_scores"]
    assert "composite" in winner["normalized_scores"]

    # Verify persistence to SQLite
    db_evals = client.get(f"/api/v1/qa/evaluations/{shot_id}").json()
    assert len(db_evals["evaluations"]) == 3
    assert db_evals["evaluations"][0]["is_winner"] == 1



def test_03_fallback_ladder_triggered_when_all_candidates_fail():
    """Verify that when all candidates fail strict thresholds, status is ALL_FAILED and fallback ladder is triggered."""
    proj_id = f"PROJ_{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES (?, ?, 'series', ?, ?)",
                   (proj_id, "QA Fail Test", "2026-09-19T00:00:00", "2026-09-19T00:00:00"))
    conn.commit()
    conn.close()

    ref_char = str(FIXTURES_DIR / "ref_character.png")
    # All drifted candidates
    candidates = [
        str(FIXTURES_DIR / "cand_03_drifted_match.png"),
        str(FIXTURES_DIR / "cand_03_drifted_match.png"),
        str(FIXTURES_DIR / "cand_03_drifted_match.png")
    ]

    # Set strict threshold
    reranker = CandidateReranker(min_identity_threshold=0.95, min_composite_threshold=0.90)
    result = reranker.evaluate_and_rerank(
        project_id=proj_id,
        candidate_paths=candidates,
        shot_id="SHOT_FAIL_TEST",
        ref_char_path=ref_char
    )

    assert result["status"] == "ALL_FAILED"
    assert result["winner"] is None
    assert result["fallback_ladder_action"] == "TRIGGER_CINEMATIC_FALLBACK_LADDER_ATTEMPT_2"
    assert all(c["status"] == "REJECTED" for c in result["candidates"])


def test_04_longitudinal_identity_drift_detection():
    """Verify longitudinal drift tracker alerts when character identity progressively drifts away from Tier 0."""
    proj_id = f"PROJ_{uuid.uuid4().hex[:8].upper()}"
    char_id = f"CHAR_DRIFT_{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES (?, ?, 'series', ?, ?)",
                   (proj_id, "QA Drift Project", "2026-09-19T00:00:00", "2026-09-19T00:00:00"))
    cursor.execute("INSERT INTO characters (id, project_id, name, code, created_at) VALUES (?, ?, ?, ?, ?)",
                   (char_id, proj_id, "Preeti", "PREETI", "2026-09-19T00:00:00"))
    conn.commit()
    conn.close()

    tracker = LongitudinalDriftTracker(drift_warning_delta=0.15, window_size=5)

    # First 3 shots have strong identity similarity
    s1 = tracker.record_shot_identity(proj_id, char_id, 0.92, episode_id="EP01", scene_id="SC01")
    assert s1["flagged_warning"] is False

    s2 = tracker.record_shot_identity(proj_id, char_id, 0.89, episode_id="EP01", scene_id="SC02")
    assert s2["flagged_warning"] is False

    s3 = tracker.record_shot_identity(proj_id, char_id, 0.87, episode_id="EP01", scene_id="SC03")
    assert s3["flagged_warning"] is False

    # Drift introduces across next episodes
    s4 = tracker.record_shot_identity(proj_id, char_id, 0.72, episode_id="EP02", scene_id="SC01")
    s5 = tracker.record_shot_identity(proj_id, char_id, 0.65, episode_id="EP02", scene_id="SC02")

    # Now rolling average has dropped and drift delta > 0.15
    assert s5["flagged_warning"] is True
    assert "CHARACTER_IDENTITY_DRIFT_ALERT" in s5["warning_message"]

    # Test history retrieval endpoint
    hist = tracker.get_drift_history(proj_id, char_id)
    assert hist["total_records"] == 5
    assert hist["has_active_warning"] is True



def test_05_fastapi_endpoints_integration():
    """Verify REST API endpoints for embedding extraction, canonical registration, reranking and drift tracking."""
    proj_id = f"PROJ_{uuid.uuid4().hex[:8].upper()}"
    char_id = f"CHAR_{uuid.uuid4().hex[:8].upper()}"
    shot_id = f"SHOT_API_{uuid.uuid4().hex[:8].upper()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (id, name, kind, created_at, updated_at) VALUES (?, ?, 'series', ?, ?)",
                   (proj_id, "QA API Project", "2026-09-19T00:00:00", "2026-09-19T00:00:00"))
    cursor.execute("INSERT INTO characters (id, project_id, name, code, created_at) VALUES (?, ?, ?, ?, ?)",
                   (char_id, proj_id, "Preeti", "PREETI", "2026-09-19T00:00:00"))
    conn.commit()
    conn.close()

    ref_char = str(FIXTURES_DIR / "ref_character.png")

    # 1. /api/v1/qa/extract-embedding
    resp = client.post("/api/v1/qa/extract-embedding", json={
        "image_path": ref_char,
        "device": "cpu"
    })
    assert resp.status_code == 200
    assert resp.json()["dim"] == 384

    # 2. /api/v1/qa/register-canonical
    resp = client.post("/api/v1/qa/register-canonical", json={
        "project_id": proj_id,
        "entity_type": "character",
        "entity_id": char_id,
        "image_path": ref_char,
        "sub_slot": "front"
    })
    assert resp.status_code == 200
    assert resp.json()["dim"] == 384

    # 3. /api/v1/qa/rerank-candidates
    resp = client.post("/api/v1/qa/rerank-candidates", json={
        "project_id": proj_id,
        "candidate_paths": [
            str(FIXTURES_DIR / "cand_01_high_match.png"),
            str(FIXTURES_DIR / "cand_02_moderate_match.png"),
            str(FIXTURES_DIR / "cand_03_drifted_match.png")
        ],
        "shot_id": shot_id,
        "ref_char_path": ref_char
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["winner"]["is_winner"] is True

    # 4. /api/v1/qa/record-drift
    resp = client.post("/api/v1/qa/record-drift", json={
        "project_id": proj_id,
        "character_id": char_id,
        "similarity_to_canonical": 0.88,
        "shot_id": shot_id
    })
    assert resp.status_code == 200
    assert resp.json()["rolling_average"] == 0.88

    # 5. /api/v1/qa/drift/{project_id}/{character_id}
    resp = client.get(f"/api/v1/qa/drift/{proj_id}/{char_id}")
    assert resp.status_code == 200
    assert resp.json()["total_records"] >= 1

