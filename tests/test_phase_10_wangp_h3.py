"""Acceptance Test Suite for Phase 10: WanGP Backend + MiniMax H3 Short-Shot Profile."""
import json
import os
import shutil
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import get_connection, init_db
from app.core.gpu_lease import GPULeaseManager
from app.core.models import (
    AssetKind,
    H3ShotRequest,
    H3ShotResponse,
    JobKind,
    JobStatus,
    ProjectCreate,
    ProjectKind,
)
from app.core.projects import ProjectManager
from app.core.wangp_adapter import (
    WanGPAdapter,
    WanGPAdapterError,
    WANGP_PINNED_COMMIT,
    WANGP_MIN_DISK_BUFFER_GB,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes a fresh test database state."""
    init_db()
    # Reset GPU lease to clean unlocked state
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


def test_phase_10_upstream_manifest_and_commit():
    """Verifies Wan2GP repository presence, pinned commit SHA, manifest documentation, and license."""
    adapter = WanGPAdapter()
    assert adapter.wangp_dir.exists(), f"Wan2GP repository missing at {adapter.wangp_dir}"

    # Verify pinned commit constant
    assert WANGP_PINNED_COMMIT == "bfaff285463ef6124c2357136e8d36c6c93c0fb2"

    # Verify UPSTREAM_MANIFEST.md contains Wan2GP and H3 entries
    manifest_path = os.path.abspath("docs/UPSTREAM_MANIFEST.md")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "deepbeepmeep/Wan2GP" in content
    assert WANGP_PINNED_COMMIT in content
    assert "video_minimax_h3_short_shot" in content

    # Verify LICENSES_AND_MODEL_TERMS.md contains WanGP license
    licenses_path = os.path.abspath("docs/LICENSES_AND_MODEL_TERMS.md")
    assert os.path.exists(licenses_path)
    with open(licenses_path, "r", encoding="utf-8") as f:
        lic_content = f.read()
    assert "WanGP Community License 2.0" in lic_content


def test_phase_10_low_vram_profile_constraints():
    """Verifies that the H3 profile strictly enforces 8GB VRAM rules (vertical 480x864, 4-6s duration, <=3 candidates)."""
    adapter = WanGPAdapter()

    # Valid short-shot profile
    valid_req = H3ShotRequest(
        project_id="proj_test_h3",
        keyframe_asset_id="dummy_keyframe",
        prompt="A cinematic hero walks forward into neon lights",
        duration_s=5.0,
        aspect="9:16",
        width=480,
        height=864,
        candidates=1,
    )
    profile = adapter.validate_h3_profile(valid_req)
    assert profile["resolution"] == "480x864"
    assert profile["duration_s"] == 5.0
    assert profile["fps"] == 24
    assert profile["frames"] == 120
    assert profile["denoising_priority"] == "lower_vram"
    assert profile["text_encoder_variant"] == "gguf_q2_k"
    assert profile["video_vae_variant"] == "fp8mix"
    assert profile["model_architecture"] == "minimax_h3_fl2va_pruned"

    # Invalid aspect ratio (horizontal / landscape must be rejected for short-shot vertical profile)
    bad_aspect_req = H3ShotRequest(
        project_id="proj_test_h3",
        keyframe_asset_id="dummy_keyframe",
        prompt="Landscape shot",
        width=1280,
        height=720,
    )
    with pytest.raises(WanGPAdapterError, match="Invalid vertical aspect ratio"):
        adapter.validate_h3_profile(bad_aspect_req)

    # Resolution exceeding 8GB VRAM class
    high_res_req = H3ShotRequest(
        project_id="proj_test_h3",
        keyframe_asset_id="dummy_keyframe",
        prompt="Too high resolution",
        width=720,
        height=1280,
    )
    with pytest.raises(WanGPAdapterError, match="exceeds 8GB VRAM class"):
        adapter.validate_h3_profile(high_res_req)

    # Duration out of bounds (> 8s)
    with pytest.raises(Exception):
        H3ShotRequest(
            project_id="proj_test_h3",
            keyframe_asset_id="dummy_keyframe",
            prompt="Too long",
            duration_s=12.0,
        )

    # Candidates out of bounds (> 3)
    with pytest.raises(Exception):
        H3ShotRequest(
            project_id="proj_test_h3",
            keyframe_asset_id="dummy_keyframe",
            prompt="Too many candidates",
            candidates=5,
        )


def test_phase_10_gpu_lease_locking():
    """Verifies GPU lease mutual exclusion for heavy WanGP renders."""
    # Ensure initial lease is free
    status = GPULeaseManager.get_lease_status()
    assert not status.is_locked

    job1_id = "job_wangp_h3_test_001"
    ok1, token1, msg1 = GPULeaseManager.acquire(job1_id)
    assert ok1 is True
    assert token1 is not None

    # Verify lease is locked by job1
    status = GPULeaseManager.get_lease_status()
    assert status.is_locked
    assert status.owner_job_id == job1_id

    # Second heavy job must be blocked
    job2_id = "job_comfy_render_test_002"
    ok2, token2, msg2 = GPULeaseManager.acquire(job2_id)
    assert ok2 is False
    assert "GPU lease currently held" in msg2

    # Heartbeat works
    assert GPULeaseManager.heartbeat(token1) is True

    # Release lease cleanly
    assert GPULeaseManager.release(token1) is True
    status_after = GPULeaseManager.get_lease_status()
    assert not status_after.is_locked


def test_phase_10_adapter_end_to_end_execution(tmp_path):
    """End-to-end integration: project -> approved keyframe -> WanGP shot generation -> asset registration -> lease release."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="WanGP H3 Test Project",
            kind=ProjectKind.SERIES,
            description="Testing Phase 10 generative shot pipeline",
        )
    )

    # Create dummy approved keyframe on disk and in DB
    dummy_keyframe_path = tmp_path / "CHAR_MAYA_FRONT_V001.png"
    dummy_keyframe_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    keyframe_id = f"CHAR_MAYA_{uuid.uuid4().hex[:6].upper()}_V001"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                keyframe_id,
                project.id,
                0,
                AssetKind.CANONICAL_REF.value,
                "V001",
                "Canonical Maya Neutral",
                str(dummy_keyframe_path),
                json.dumps({"character_name": "Maya", "seed": 1000}),
                json.dumps({"source": "flux2_klein"}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    adapter = WanGPAdapter()

    req = H3ShotRequest(
        project_id=project.id,
        keyframe_asset_id=keyframe_id,
        prompt="Maya turns toward camera with intense determination, dramatic alleyway shadows",
        duration_s=5.0,
        aspect="9:16",
        width=480,
        height=864,
        candidates=1,
        seed=42,
    )

    # 1. Test queue submission
    sub_res = adapter.submit_h3_shot_job(req)
    assert sub_res.job_id.startswith("job_")
    assert sub_res.status == JobStatus.PENDING.value

    # 2. Execute shot generation (mock mode for deterministic test)
    exec_res = adapter.execute_shot_generation(sub_res.job_id, req, mock_mode=True)
    assert exec_res.status == JobStatus.SUCCEEDED.value
    assert exec_res.output_video_asset_id.startswith("SHOT_H3_")
    assert os.path.exists(exec_res.output_path)
    assert exec_res.output_path.endswith(".mp4")
    assert exec_res.vram_peak_mb <= 8192.0  # Must stay strictly within 8GB VRAM limit

    # 3. Verify asset table registration
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (exec_res.output_video_asset_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["kind"] == AssetKind.VIDEO_SHOT.value
        assert row["tier"] == 1
        assert row["version"] == "V001"

        prov = json.loads(row["provenance_json"])
        assert prov["upstream_repo"] == "deepbeepmeep/Wan2GP"
        assert prov["pinned_commit"] == WANGP_PINNED_COMMIT
        assert prov["keyframe_asset_id"] == keyframe_id
        assert prov["resolution"] == "480x864"
        assert "timings_ms" in prov
    finally:
        conn.close()

    # 4. Verify GPU lease was released cleanly
    lease_status = GPULeaseManager.get_lease_status()
    assert not lease_status.is_locked


def test_phase_10_api_endpoints(tmp_path):
    """Verifies the REST API endpoints /api/v1/video/h3-profile and /api/v1/video/h3-execute."""
    # 1. Profile endpoint
    res_prof = client.get("/api/v1/video/h3-profile")
    assert res_prof.status_code == 200
    prof_data = res_prof.json()
    assert prof_data["backend"] == "wangp_h3"
    assert prof_data["pinned_commit"] == WANGP_PINNED_COMMIT
    assert prof_data["default_profile"]["resolution"] == "480x864"
    assert prof_data["default_profile"]["aspect"] == "9:16"
    assert prof_data["default_profile"]["duration_s"] == 5.0
    assert prof_data["disk_safe"] is True

    # 2. Setup project & keyframe
    project = ProjectManager.create_project(
        ProjectCreate(
            name="API Test Project",
            kind=ProjectKind.SERIES,
            description="Testing video endpoints",
        )
    )
    dummy_keyframe_path = tmp_path / "CHAR_KEYFRAME.png"
    dummy_keyframe_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    keyframe_id = f"CHAR_KEY_{uuid.uuid4().hex[:6].upper()}_V001"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assets (id, project_id, tier, kind, version, name, file_path, metadata_json, provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                keyframe_id,
                project.id,
                0,
                AssetKind.CANONICAL_REF.value,
                "V001",
                "Maya Keyframe",
                str(dummy_keyframe_path),
                json.dumps({"character_name": "Maya"}),
                json.dumps({"source": "test"}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # 3. Direct execute endpoint
    payload = {
        "project_id": project.id,
        "keyframe_asset_id": keyframe_id,
        "prompt": "Maya walks through a crowded neon market",
        "duration_s": 5.0,
        "aspect": "9:16",
        "width": 480,
        "height": 864,
        "candidates": 1,
        "seed": 42,
    }
    res_exec = client.post("/api/v1/video/h3-execute?mock=true", json=payload)
    assert res_exec.status_code == 200
    data = res_exec.json()
    assert data["status"] == "SUCCEEDED"
    assert data["output_video_asset_id"].startswith("SHOT_H3_")
    assert data["resolution"] == "480x864"
    assert data["duration_s"] == 5.0
    assert os.path.exists(data["output_path"])
