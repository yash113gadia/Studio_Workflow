"""Acceptance Test Suite for Phase 11: SCAIL-2 Controlled Motion & Motion Library."""
import json
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_connection, init_db
from app.core.gpu_lease import GPULeaseManager
from app.core.models import AssetKind, ProjectCreate, ProjectKind
from app.core.motion_library import MotionLibrary
from app.core.projects import ProjectManager
from app.core.scail_engine import (
    ScailEngine,
    ScailEngineError,
    ScailRenderRequest,
    ScailRenderResponse,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes a fresh test database state."""
    init_db()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE gpu_lease
            SET owner_job_id = NULL, token = NULL, acquired_at = NULL, heartbeat_at = NULL
            WHERE resource = 'GPU0_HEAVY'
            """
        )
        conn.commit()
    finally:
        conn.close()
    yield


client = TestClient(app)

REQUIRED_11_MOTIONS = [
    "MOTION_IDLE_LISTEN_V001",
    "MOTION_TALKING_CALM_V001",
    "MOTION_TALKING_ANGRY_V001",
    "MOTION_STAND_UP_V001",
    "MOTION_SIT_DOWN_V001",
    "MOTION_WALK_IN_V001",
    "MOTION_TURN_AWAY_V001",
    "MOTION_POINT_V001",
    "MOTION_LOOK_AT_PHONE_V001",
    "MOTION_HAND_OBJECT_V001",
    "MOTION_SHOCKED_STEP_BACK_V001",
]


def test_phase_11_motion_library_manifest_and_files():
    """Verifies motion library manifest schema and physical presence of all 11 Master Plan driving motions."""
    lib = MotionLibrary()
    motions = lib.list_motions()
    assert len(motions) >= 11

    motion_ids = [m.motion_id for m in motions]
    for req_id in REQUIRED_11_MOTIONS:
        assert req_id in motion_ids, f"Required motion {req_id} missing from motion library!"

    # Verify each driving video exists on disk
    for m in motions:
        assert os.path.exists(m.driving_video_path), f"Video file missing for {m.motion_id}: {m.driving_video_path}"
        assert m.duration_s > 0
        assert m.framerate == 24


def test_phase_11_single_person_constraint_and_search(tmp_path):
    """Verifies single-person acting constraint enforcement and motion search capabilities."""
    lib = MotionLibrary()

    # Search by keyword
    phone_results = lib.search_motions("phone")
    assert any(m.motion_id == "MOTION_LOOK_AT_PHONE_V001" for m in phone_results)

    talk_results = lib.search_motions("talking")
    assert len(talk_results) >= 2

    engine = ScailEngine()

    # Multi-person request must be rejected
    multi_req = ScailRenderRequest(
        project_id="proj_test_scail",
        character_asset_id="dummy_char",
        motion_id="MOTION_WALK_IN_V001",
        single_person_only=False,
    )
    with pytest.raises(ScailEngineError, match="Multi-person performance transfer is not supported"):
        engine.validate_request(multi_req)


def test_phase_11_gpu_lease_locking():
    """Verifies GPU lease mutual exclusion for heavy SCAIL performance transfers."""
    status = GPULeaseManager.get_lease_status()
    assert not status.is_locked

    job1_id = "job_scail_test_001"
    ok1, token1, msg1 = GPULeaseManager.acquire(job1_id)
    assert ok1 is True
    assert token1 is not None

    # Verify lease is locked
    status = GPULeaseManager.get_lease_status()
    assert status.is_locked
    assert status.owner_job_id == job1_id

    # Second heavy render is blocked
    job2_id = "job_heavy_render_002"
    ok2, token2, msg2 = GPULeaseManager.acquire(job2_id)
    assert ok2 is False
    assert "GPU lease currently held" in msg2

    # Release lease cleanly
    assert GPULeaseManager.release(token1) is True
    assert not GPULeaseManager.get_lease_status().is_locked


def test_phase_11_e2e_controlled_performance_execution(tmp_path):
    """End-to-end test: approved character + driving motion -> controlled shot with VRAM and H3 comparison."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="SCAIL Test Project",
            kind=ProjectKind.SERIES,
            description="Testing Phase 11 controlled acting shot pipeline",
        )
    )

    # Setup dummy canonical character keyframe
    char_img = tmp_path / "CHAR_MAYA_CANONICAL.png"
    char_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    char_id = f"CHAR_MAYA_{uuid.uuid4().hex[:6].upper()}_V001"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                char_id,
                project.id,
                0,
                AssetKind.CANONICAL_REF.value,
                "V001",
                "Maya Canonical",
                str(char_img),
                json.dumps({"character_name": "Maya"}),
                json.dumps({"source": "flux2_klein"}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    engine = ScailEngine()

    req = ScailRenderRequest(
        project_id=project.id,
        character_asset_id=char_id,
        motion_id="MOTION_LOOK_AT_PHONE_V001",
        single_person_only=True,
        seed=42,
    )

    res = engine.execute_controlled_performance(req, mock_mode=True)
    assert res.status == "SUCCEEDED"
    assert res.output_video_asset_id.startswith("SHOT_SCAIL_")
    assert os.path.exists(res.output_path)
    assert res.duration_s == 4.5
    assert res.vram_peak_mb <= 8192.0  # Must fit in 8GB VRAM
    assert "h3_benchmark_comparison" in res.provenance_json

    # Verify asset table record
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (res.output_video_asset_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["kind"] == AssetKind.VIDEO_SHOT.value
        assert row["tier"] == 1
        prov = json.loads(row["provenance_json"])
        assert prov["motion_id"] == "MOTION_LOOK_AT_PHONE_V001"
        assert prov["character_asset_id"] == char_id
        assert prov["vram_peak_mb"] == res.vram_peak_mb
    finally:
        conn.close()

    # Verify GPU lease released
    assert not GPULeaseManager.get_lease_status().is_locked


def test_phase_11_api_endpoints(tmp_path):
    """Verifies REST API endpoints /api/v1/motion/library and /api/v1/motion/scail-render."""
    # 1. Full library endpoint
    res_lib = client.get("/api/v1/motion/library")
    assert res_lib.status_code == 200
    motions = res_lib.json()
    assert len(motions) >= 11

    # 2. Category filter
    res_cat = client.get("/api/v1/motion/library?category=dialogue_performance")
    assert res_cat.status_code == 200
    cat_motions = res_cat.json()
    assert all(m["category"] == "dialogue_performance" for m in cat_motions)

    # 3. Setup test project & character
    project = ProjectManager.create_project(
        ProjectCreate(
            name="SCAIL API Test",
            kind=ProjectKind.SERIES,
            description="Testing SCAIL API",
        )
    )
    char_img = tmp_path / "CHAR_TEST.png"
    char_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    char_id = f"CHAR_TEST_{uuid.uuid4().hex[:6].upper()}_V001"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                char_id,
                project.id,
                0,
                AssetKind.CANONICAL_REF.value,
                "V001",
                "Maya Test",
                str(char_img),
                json.dumps({"character_name": "Maya"}),
                json.dumps({"source": "test"}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # 4. Render endpoint
    payload = {
        "project_id": project.id,
        "character_asset_id": char_id,
        "motion_id": "MOTION_STAND_UP_V001",
        "single_person_only": True,
        "seed=42": 42,
    }
    res_render = client.post("/api/v1/motion/scail-render?mock=true", json=payload)
    assert res_render.status_code == 200
    data = res_render.json()
    assert data["status"] == "SUCCEEDED"
    assert data["output_video_asset_id"].startswith("SHOT_SCAIL_")
    assert data["duration_s"] == 3.5
    assert os.path.exists(data["output_path"])
