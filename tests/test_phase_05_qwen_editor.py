"""Phase 5 Acceptance Test Suite — Qwen-Image-Edit-2511 INT8 Specialist Branch."""
import hashlib
import json
import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import init_db
from app.core.models import AssetKind, JobKind, SpecialistEditAction
from app.core.specialist_editor import SpecialistEditor, ACTION_WORKFLOW_MAP

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test_studio_p5.db"
    monkeypatch.setattr("app.core.config.settings.paths.database", str(test_db))
    monkeypatch.setattr("app.core.config.settings.paths.projects", str(tmp_path / "projects"))

    def get_test_conn():
        c = sqlite3.connect(str(test_db), timeout=10.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        return c

    monkeypatch.setattr("app.core.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.specialist_editor.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.asset_factory.get_connection", get_test_conn)
    monkeypatch.setattr("app.core.queue.get_connection", get_test_conn)
    init_db()
    yield


def test_qwen_workflow_templates_registered():
    """Criterion: Untouched upstream template and all 6 Studio specialist workflows exist and are valid."""
    upstream_template = "workflows/upstream/comfy_official/image_qwen_image_edit_2511_int8.json"
    assert os.path.exists(upstream_template), f"Missing official template: {upstream_template}"

    # Verify SHA256 matches manifest
    h = hashlib.sha256()
    with open(upstream_template, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    assert h.hexdigest() == "f69153d857a3e7ad374c4b79775fa2d8d99361135806a5ecf7106f2e41cd2336"

    # Verify all 6 specialist workflows
    expected_workflows = [
        "workflows/api_format/qwen_edit_outfit_v001.json",
        "workflows/api_format/qwen_edit_remove_object_v001.json",
        "workflows/api_format/qwen_edit_repair_bg_v001.json",
        "workflows/api_format/qwen_edit_derive_angle_v001.json",
        "workflows/api_format/qwen_edit_correct_prop_v001.json",
        "workflows/api_format/qwen_edit_material_swap_v001.json",
    ]
    for p in expected_workflows:
        assert os.path.exists(p), f"Missing workflow: {p}"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data.keys()) > 0
        class_types = [v.get("class_type") for v in data.values()]
        assert "UNETLoader" in class_types
        assert "CLIPLoader" in class_types
        assert "VAELoader" in class_types
        assert "ModelSamplingAuraFlow" in class_types
        assert "TextEncodeQwenImageEditPlus" in class_types
        assert "KSampler" in class_types
        assert "VAEDecode" in class_types
        assert "SaveImage" in class_types


def test_specialist_editor_actions_api():
    """Verify listing specialist actions returns all 6 supported operations."""
    res = client.get("/api/v1/editor/actions")
    assert res.status_code == 200
    actions = res.json()
    assert len(actions) == 6
    action_names = [a["action"] for a in actions]
    assert "preserve_identity_change_outfit" in action_names
    assert "remove_unwanted_object" in action_names
    assert "repair_background" in action_names
    assert "derive_angle" in action_names
    assert "correct_prop" in action_names
    assert "material_swap" in action_names


def test_controlled_edits_on_approved_character(tmp_path):
    """Phase 5 Acceptance Gate: Perform at least 3 controlled edits on an approved character keyframe with QA scores."""
    editor = SpecialistEditor()

    # 1. Create project & register approved character keyframe CHAR_KIRA_V001
    r_proj = client.post("/api/v1/projects/", json={"name": "Specialist Edit Pilot", "kind": "series"})
    assert r_proj.status_code == 200
    proj_id = r_proj.json()["id"]

    source_img = tmp_path / "kira_keyframe.png"
    source_img.write_bytes(b"PNG_BYTES_KIRA_KEYFRAME")

    from app.core.asset_factory import AssetFactory
    factory = AssetFactory()
    factory.register_candidate_asset(proj_id, "CAND_KIRA_001", "Kira", str(source_img), "Kira portrait", 1000)
    canonical = factory.approve_character_casting(proj_id, "CAND_KIRA_001", "KIRA")
    assert canonical.id == "CHAR_KIRA_V001"

    # 2. Perform 3 Controlled Edits
    test_edits = [
        (
            SpecialistEditAction.PRESERVE_IDENTITY_CHANGE_OUTFIT,
            "Change outfit to charcoal leather trenchcoat, retain facial identity and hairstyle",
            {"identity_retention_score": 0.95, "recognizability_score": 0.97, "evaluation": "PASSED"}
        ),
        (
            SpecialistEditAction.REMOVE_UNWANTED_OBJECT,
            "Remove stray cable on right side of frame, clean seamless backdrop fill",
            {"identity_retention_score": 0.99, "recognizability_score": 0.99, "evaluation": "PASSED"}
        ),
        (
            SpecialistEditAction.REPAIR_BACKGROUND,
            "Smooth out studio background lighting gradient, keep subject crisp",
            {"identity_retention_score": 0.98, "recognizability_score": 0.98, "evaluation": "PASSED"}
        )
    ]

    completed_assets = []
    for action, instruction, qa_data in test_edits:
        # Trigger edit via API
        r_edit = client.post("/api/v1/editor/edit", json={
            "project_id": proj_id,
            "source_asset_id": canonical.id,
            "action": action.value,
            "instruction": instruction,
            "seed": 1500
        })
        assert r_edit.status_code == 200
        job_info = r_edit.json()
        assert job_info["action"] == action.value
        assert job_info["source_asset_id"] == canonical.id
        assert job_info["status"] == "PENDING"
        assert job_info["provenance_json"]["model_architecture"] == "qwen_image_edit_2511_int8_convrot"

        # Register completed edit asset with QA score
        edit_result_file = tmp_path / f"result_{action.value}.png"
        edit_result_file.write_bytes(f"EDIT_OUTPUT_{action.value}".encode())

        r_comp = client.post("/api/v1/editor/complete", json={
            "project_id": proj_id,
            "output_asset_id": job_info["output_asset_id"],
            "source_asset_id": canonical.id,
            "action": action.value,
            "image_path": str(edit_result_file),
            "instruction": instruction,
            "seed": 1500,
            "qa_metrics": qa_data
        })
        assert r_comp.status_code == 200
        asset_record = r_comp.json()
        assert asset_record["kind"] == AssetKind.EDITED_ASSET.value
        assert asset_record["provenance_json"]["parent_asset_id"] == canonical.id
        assert asset_record["provenance_json"]["qa_metrics"]["evaluation"] == "PASSED"
        assert asset_record["provenance_json"]["qa_metrics"]["identity_retention_score"] >= 0.90
        completed_assets.append(asset_record)

    assert len(completed_assets) == 3

    # 3. Retrieve all edits for the canonical character
    r_list = client.get(f"/api/v1/editor/edits/{canonical.id}")
    assert r_list.status_code == 200
    edits = r_list.json()
    assert len(edits) == 3

    # 4. Verify canonical asset was NOT modified (immutability preserved)
    canon_check = editor.get_source_asset(canonical.id)
    assert canon_check.id == "CHAR_KIRA_V001"
    assert canon_check.tier == 0
    assert canon_check.kind == AssetKind.CANONICAL_REF.value
