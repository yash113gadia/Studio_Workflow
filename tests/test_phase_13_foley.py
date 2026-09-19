"""Acceptance Test Suite for Phase 13: Foley and Generated SFX (HunyuanVideo-Foley XL + Offload)."""
import os
import wave
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_connection, init_db
from app.core.gpu_lease import GPULeaseManager
from app.core.models import ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.audio.foley_engine import (
    FoleyBackend,
    FoleyCategory,
    FoleyCue,
    FoleyEngine,
    FoleyRequest,
    FoleyResponse,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes a fresh test database state and ensures GPU0_HEAVY is free."""
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


def test_phase_13_foley_manifest_and_categories():
    """Verifies that the sound cue catalog covers all required categories."""
    manifest = FoleyEngine.load_manifest()
    assert "categories" in manifest
    assert "cues" in manifest
    categories = manifest["categories"]
    for required_cat in ["footsteps", "doors", "fabric", "impact", "ambience"]:
        assert required_cat in categories

    # Ensure at least 10 cues are cataloged
    assert len(manifest["cues"]) >= 10

    # Test via REST API endpoint
    response = client.get("/api/v1/audio/foley/library")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cues"]) >= 10


def test_phase_13_synchronized_foley_wav_output(tmp_path):
    """Verifies: 5 s approved clip -> synchronized Foley WAV matching exact duration."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Foley Test Project",
            kind=ProjectKind.SERIES,
            description="Testing 5s synchronized Foley render",
        )
    )

    req = FoleyRequest(
        project_id=project.id,
        shot_id="shot_001_walk_and_door",
        duration_s=5.0,
        sfx_enabled=True,
        backend=FoleyBackend.HUNYUAN_XL_OFFLOAD,
        cues=[
            FoleyCue(
                action_type=FoleyCategory.FOOTSTEPS,
                cue_id="SFX_FOOTSTEPS_WOOD_V001",
                start_time_s=0.5,
                duration_s=2.5,
                gain_db=0.0,
            ),
            FoleyCue(
                action_type=FoleyCategory.DOORS,
                cue_id="SFX_DOOR_CLOSE_SOFT_V001",
                start_time_s=3.2,
                duration_s=1.2,
                gain_db=1.5,
            ),
        ],
        output_dir=str(tmp_path),
    )

    res = FoleyEngine.generate_foley(req)
    assert res.sfx_enabled is True
    assert res.audio_path is not None
    assert os.path.exists(res.audio_path)
    assert res.duration_s == 5.0
    assert res.cues_processed == 2

    # Verify WAV header and exact duration
    with wave.open(res.audio_path, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        total_frames = wf.getnframes()
        expected_frames = int(5.0 * 44100)
        assert total_frames == expected_frames


def test_phase_13_peak_vram_and_ram_measured(tmp_path):
    """Verifies: peak VRAM and RAM are measured and recorded in response."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Foley VRAM Test",
            kind=ProjectKind.SERIES,
            description="Testing VRAM/RAM measurement",
        )
    )

    req = FoleyRequest(
        project_id=project.id,
        shot_id="shot_002_impact",
        duration_s=3.0,
        sfx_enabled=True,
        backend=FoleyBackend.HUNYUAN_XL_OFFLOAD,
        cues=[
            FoleyCue(
                action_type=FoleyCategory.IMPACT,
                cue_id="SFX_IMPACT_PUNCH_V001",
                start_time_s=1.0,
                duration_s=0.8,
            )
        ],
        output_dir=str(tmp_path),
    )

    res = FoleyEngine.generate_foley(req)
    # Peak VRAM must be within the 8GB limit (< 6000 MB with offload)
    assert res.peak_vram_mb <= 6000.0
    assert res.peak_vram_mb > 0.0
    # Host RAM must be positive and measured
    assert res.peak_ram_mb > 0.0


def test_phase_13_model_fully_unloads_after_job(tmp_path):
    """Verifies: model fully unloads after job and releases GPU0_HEAVY lease."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Foley Unload Test",
            kind=ProjectKind.SERIES,
            description="Testing lease release and model unloading",
        )
    )

    req = FoleyRequest(
        project_id=project.id,
        shot_id="shot_003_fabric",
        duration_s=4.0,
        sfx_enabled=True,
        backend=FoleyBackend.HUNYUAN_XL_OFFLOAD,
        output_dir=str(tmp_path),
    )

    res = FoleyEngine.generate_foley(req)
    assert res.unloaded is True

    # Check that GPU0_HEAVY lease was released and can immediately be acquired
    test_job_id = "test_verification_job"
    acquired, token, msg = GPULeaseManager.acquire(test_job_id)
    assert acquired is True, f"GPU lease was not released by FoleyEngine: {msg}"
    GPULeaseManager.release(token)


def test_phase_13_audio_can_be_disabled_per_shot():
    """Verifies: audio can be disabled per shot without GPU usage."""
    req = FoleyRequest(
        project_id="PROJ_TEST_DISABLED",
        shot_id="shot_silent_001",
        duration_s=5.0,
        sfx_enabled=False,  # Audio disabled per shot
        backend=FoleyBackend.HUNYUAN_XL_OFFLOAD,
    )

    res = FoleyEngine.generate_foley(req)
    assert res.sfx_enabled is False
    assert res.audio_path is None
    assert res.backend_used == "disabled_per_shot"
    assert res.peak_vram_mb == 0.0
    assert res.unloaded is True

    # Check REST API behavior with sfx_enabled=False
    payload = {
        "project_id": "PROJ_TEST_DISABLED",
        "shot_id": "shot_api_silent",
        "duration_s": 4.5,
        "sfx_enabled": False,
        "backend": "hunyuan_xl_offload",
    }
    response = client.post("/api/v1/audio/foley", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["sfx_enabled"] is False
    assert data["audio_path"] is None
    assert data["peak_vram_mb"] == 0.0


def test_phase_13_library_sfx_fallback(tmp_path):
    """Verifies: library SFX fallback works when GPU is constrained or requested."""
    # Simulate GPU0_HEAVY being held by another worker
    acquired, token, msg = GPULeaseManager.acquire("foreign_blocking_job")
    assert acquired is True

    try:
        # Request HunyuanVideo-Foley while GPU is locked: should gracefully fallback to library
        req = FoleyRequest(
            project_id="PROJ_TEST_FALLBACK",
            shot_id="shot_fallback_001",
            duration_s=3.5,
            sfx_enabled=True,
            backend=FoleyBackend.HUNYUAN_XL_OFFLOAD,
            cues=[
                FoleyCue(
                    action_type=FoleyCategory.AMBIENCE,
                    cue_id="SFX_AMBIENCE_ROOM_TONE_V001",
                    start_time_s=0.0,
                    duration_s=3.5,
                )
            ],
            output_dir=str(tmp_path),
        )

        res = FoleyEngine.generate_foley(req)
        # Verify it did not crash or block, but cleanly executed fallback
        assert res.sfx_enabled is True
        assert res.backend_used == FoleyBackend.LIBRARY_FALLBACK.value
        assert res.audio_path is not None
        assert os.path.exists(res.audio_path)
        assert res.duration_s == 3.5
    finally:
        GPULeaseManager.release(token)
