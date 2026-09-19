import hashlib
import json
import os
import shutil
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import get_connection, init_db
from app.core.asset_factory import AssetFactory
from app.core.models import AssetKind, JobKind

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    # Ensure fresh test DB
    test_db = tmp_path / "test_studio.db"
    monkeypatch.setattr("app.core.config.settings.paths.database", str(test_db))
    monkeypatch.setattr("app.core.config.settings.paths.projects", str(tmp_path / "projects"))

    def get_test_conn():
        c = sqlite3.connect(str(test_db), timeout=10.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        return c

    monkeypatch.setattr("app.core.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.asset_factory.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.queue.get_connection", get_test_conn)
    init_db()
    yield


def test_upstream_and_studio_workflows_registered():
    """Verify official untouched templates and Studio API workflows are registered."""
    upstream_templates = [
        "workflows/upstream/comfy_official/image_flux2_klein_text_to_image.json",
        "workflows/upstream/comfy_official/image_flux2_klein_image_edit_4b_distilled.json",
    ]
    for p in upstream_templates:
        assert os.path.exists(p), f"Missing upstream template: {p}"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data or "definitions" in data

    studio_workflows = [
        "workflows/api_format/flux_casting_v001.json",
        "workflows/api_format/flux_character_keyframe_v001.json",
        "workflows/api_format/flux_outfit_v001.json",
        "workflows/api_format/flux_location_plate_v001.json",
        "workflows/api_format/flux_thumbnail_art_v001.json",
    ]
    for p in studio_workflows:
        assert os.path.exists(p), f"Missing studio workflow: {p}"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data.keys()) > 0
        # Check required nodes
        class_types = [v.get("class_type") for v in data.values()]
        assert "UNETLoader" in class_types
        assert "CLIPLoader" in class_types
        assert "VAELoader" in class_types
        assert "SaveImage" in class_types


def test_character_casting_session():
    """Test generating 3 casting candidates with deterministic seed progression."""
    # 1. Create a project
    r_proj = client.post("/api/v1/projects/", json={
        "name": "Phase 4 Casting Project",
        "kind": "series"
    })
    assert r_proj.status_code == 200
    proj_id = r_proj.json()["id"]

    # 2. Trigger casting session via API
    r_cast = client.post("/api/v1/assets/casting/create", json={
        "project_id": proj_id,
        "character_name": "Maya",
        "prompt_description": "28yo female protagonist, sharp hazel eyes, dark leather jacket",
        "count": 3,
        "seed_base": 1000
    })
    assert r_cast.status_code == 200
    candidates = r_cast.json()
    assert len(candidates) == 3
    assert candidates[0]["candidate_id"] == "CAND_MAYA_001"
    assert candidates[1]["candidate_id"] == "CAND_MAYA_002"
    assert candidates[2]["candidate_id"] == "CAND_MAYA_003"
    assert candidates[0]["seed"] == 1000
    assert candidates[1]["seed"] == 1137
    assert candidates[2]["seed"] == 1274

    # 3. Verify jobs in queue
    r_jobs = client.get(f"/api/v1/jobs/?project_id={proj_id}")
    assert r_jobs.status_code == 200
    assert len(r_jobs.json()) == 3


def test_character_approval_and_immutability(tmp_path):
    """Test approving one candidate as CHAR_*_V001 and enforcing immutability."""
    factory = AssetFactory()

    # 1. Create project
    r_proj = client.post("/api/v1/projects/", json={"name": "Canon Test", "kind": "series"})
    proj_id = r_proj.json()["id"]

    # 2. Register a candidate image
    cand_img = tmp_path / "cand_maya_002.png"
    cand_img.write_bytes(b"FAKE_MAYA_CANDIDATE_PNG_BYTES")

    cand_asset = factory.register_candidate_asset(
        project_id=proj_id,
        candidate_id="CAND_MAYA_002",
        character_name="Maya",
        image_path=str(cand_img),
        prompt="Maya portrait test",
        seed=1137
    )
    assert cand_asset.id == "CAND_MAYA_002"
    assert cand_asset.tier == 1

    # 3. Approve candidate as canonical CHAR_MAYA_V001 via API
    r_app = client.post("/api/v1/assets/casting/approve", json={
        "project_id": proj_id,
        "candidate_asset_id": "CAND_MAYA_002",
        "character_code": "MAYA",
        "approval_actor": "lead_director"
    })
    assert r_app.status_code == 200
    canonical = r_app.json()
    assert canonical["id"] == "CHAR_MAYA_V001"
    assert canonical["tier"] == 0
    assert canonical["kind"] == "canonical_ref"
    assert canonical["provenance_json"]["source_candidate_id"] == "CAND_MAYA_002"
    assert canonical["provenance_json"]["canon_status"] == "APPROVED"
    assert canonical["provenance_json"]["approved_by"] == "lead_director"
    assert os.path.exists(canonical["file_path"])

    # 4. Strict Immutability Test: Attempt to approve over or overwrite CHAR_MAYA_V001
    with pytest.raises(ValueError, match="Immutable Asset Violation"):
        factory.approve_character_casting(
            project_id=proj_id,
            candidate_asset_id="CAND_MAYA_002",
            character_code="MAYA"
        )


def test_canonical_angles_derivation(tmp_path):
    """Test deriving 5 canonical compositions from the approved reference."""
    factory = AssetFactory()

    # 1. Create project & approved character
    r_proj = client.post("/api/v1/projects/", json={"name": "Angles Test", "kind": "series"})
    proj_id = r_proj.json()["id"]

    cand_img = tmp_path / "cand_maya.png"
    cand_img.write_bytes(b"FAKE_MAYA_BYTES")
    factory.register_candidate_asset(proj_id, "CAND_MAYA_001", "Maya", str(cand_img), "prompt", 1000)
    canonical = factory.approve_character_casting(proj_id, "CAND_MAYA_001", "MAYA")

    # 2. Request canonical angles via API
    r_angles = client.post("/api/v1/assets/canonical/angles", json={
        "project_id": proj_id,
        "canonical_id": canonical.id,
        "seed_base": 2000
    })
    assert r_angles.status_code == 200
    angle_jobs = r_angles.json()
    assert len(angle_jobs) == 5

    expected_suffixes = [
        "FRONT_NEUTRAL",
        "THREE_QUARTER_LEFT",
        "THREE_QUARTER_RIGHT",
        "PROFILE_LEFT",
        "PROFILE_RIGHT"
    ]
    for i, exp_suffix in enumerate(expected_suffixes):
        assert angle_jobs[i]["suffix"] == exp_suffix
        assert angle_jobs[i]["angle_asset_id"] == f"CHAR_MAYA_V001_{exp_suffix}"

        # Register completed angle asset
        angle_file = tmp_path / f"angle_{exp_suffix}.png"
        angle_file.write_bytes(b"FAKE_ANGLE_BYTES")
        asset = factory.register_canonical_angle_asset(
            project_id=proj_id,
            canonical_id=canonical.id,
            suffix=exp_suffix,
            name=angle_jobs[i]["angle_name"],
            image_path=str(angle_file),
            prompt=angle_jobs[i]["prompt"],
            seed=angle_jobs[i]["seed"]
        )
        assert asset.kind == AssetKind.CANONICAL_ANGLE.value
        assert asset.provenance_json["parent_canonical_id"] == "CHAR_MAYA_V001"

    # 3. Verify all assets listed under project
    r_list = client.get(f"/api/v1/assets/project/{proj_id}")
    assert r_list.status_code == 200
    all_assets = r_list.json()
    # 1 candidate + 1 canonical ref + 5 angles = 7 assets
    assert len(all_assets) == 7


def test_verified_vae_model_on_disk():
    """Verify that the official FLUX2 VAE model is bit-verified on disk."""
    vae_path = "models/image/vae/flux2-vae.safetensors"
    assert os.path.exists(vae_path), "flux2-vae.safetensors must exist on disk"
    assert os.path.getsize(vae_path) == 336211292, "VAE size must be exactly 336211292 bytes"

    h = hashlib.sha256()
    with open(vae_path, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            h.update(chunk)
    assert h.hexdigest() == "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3"


def test_verified_diffusion_and_text_encoder_models_on_disk():
    """Verify that the FP8 diffusion model and Qwen 3.4B text encoder exist with exact expected byte sizes."""
    diff_path = "models/image/diffusion_models/flux-2-klein-4b-fp8.safetensors"
    assert os.path.exists(diff_path), "flux-2-klein-4b-fp8.safetensors must exist on disk"
    assert os.path.getsize(diff_path) == 4070624520, "FP8 model size must be exactly 4070624520 bytes"

    clip_path = "models/image/text_encoders/qwen_3_4b.safetensors"
    assert os.path.exists(clip_path), "qwen_3_4b.safetensors must exist on disk"
    assert os.path.getsize(clip_path) == 8044982048, "Qwen text encoder size must be exactly 8044982048 bytes"

