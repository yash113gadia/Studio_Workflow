import os
import json
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.semantic_qa.schema import SemanticQAResponse, PropRequirement
from app.core.semantic_qa.auditor import SemanticQAAuditor

client = TestClient(app)
FIXTURES_DIR = Path("tests/fixtures/qa")

@pytest.fixture(scope="module", autouse=True)
def setup_semantic_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    # Ensure test images exist
    pass_img = FIXTURES_DIR / "cand_01_high_match.png"
    if not pass_img.exists():
        Image.new("RGB", (256, 256), color=(50, 150, 50)).save(pass_img)
    drift_img = FIXTURES_DIR / "cand_03_drifted_match.png"
    if not drift_img.exists():
        Image.new("RGB", (256, 256), color=(10, 10, 10)).save(drift_img)


def test_01_strict_json_schema_validation():
    """Verify strict JSON response schema compliant with Master Plan Section 3467."""
    raw_json = {
        "characters_visible": 1,
        "expected_character_match": "likely",
        "outfit_match": True,
        "location_match": True,
        "required_props": [{"id": "PROP_RED_DIARY", "present": True}],
        "anatomy_warning": False,
        "continuity_warnings": [],
        "confidence": 0.78
    }

    parsed = SemanticQAResponse(**raw_json)
    assert parsed.characters_visible == 1
    assert parsed.expected_character_match == "likely"
    assert parsed.outfit_match is True
    assert parsed.location_match is True
    assert len(parsed.required_props) == 1
    assert parsed.required_props[0].id == "PROP_RED_DIARY"
    assert parsed.required_props[0].present is True
    assert parsed.anatomy_warning is False
    assert len(parsed.continuity_warnings) == 0
    assert parsed.confidence == 0.78


def test_02_mandatory_props_verification():
    """Verify semantic auditor flags missing required props like PROP_RED_DIARY."""
    auditor = SemanticQAAuditor()
    drift_img = str(FIXTURES_DIR / "cand_03_drifted_match.png")

    result = auditor.audit_image(
        image_path=drift_img,
        expected_character="Preeti",
        required_props=["PROP_RED_DIARY", "PROP_ENVELOPE"]
    )

    assert result.characters_visible == 0
    assert result.expected_character_match == "unlikely"
    # In drifted/mismatched image, props are detected as missing
    assert any(p.id == "PROP_RED_DIARY" and p.present is False for p in result.required_props)
    assert any("PROP_RED_DIARY" in w for w in result.continuity_warnings)


def test_03_anatomy_and_continuity_warnings():
    """Verify anatomy warnings and continuity warnings are captured in schema."""
    auditor = SemanticQAAuditor()
    drift_img = str(FIXTURES_DIR / "cand_03_drifted_match.png")

    result = auditor.audit_image(
        image_path=drift_img,
        expected_character="Preeti",
        expected_wardrobe="Crimson Silk Sari"
    )

    assert result.anatomy_warning is True
    assert any("ANATOMY_WARNING" in w for w in result.continuity_warnings)


def test_04_multi_factor_decision_vlm_cannot_approve_alone():
    """Verify Master Plan rule: VLM cannot approve alone; visual and semantic must both pass."""
    auditor = SemanticQAAuditor()

    # Scenario A: Both Visual and Semantic PASS -> APPROVED
    vis_pass = {"composite_score": 0.84, "is_passing": True}
    sem_pass = SemanticQAResponse(
        characters_visible=1,
        expected_character_match="likely",
        outfit_match=True,
        location_match=True,
        required_props=[PropRequirement(id="PROP_RED_DIARY", present=True)],
        anatomy_warning=False,
        continuity_warnings=[],
        confidence=0.88
    )
    dec_a = auditor.evaluate_composite_decision("CAND_01", vis_pass, sem_pass)
    assert dec_a.is_approved is True
    assert dec_a.final_status == "APPROVED"
    assert len(dec_a.reasons) == 0

    # Scenario B: Visual FAILS (0.42 < 0.60) but VLM reports high confidence -> REJECTED
    vis_fail = {"composite_score": 0.42, "is_passing": False}
    dec_b = auditor.evaluate_composite_decision("CAND_02", vis_fail, sem_pass)
    assert dec_b.is_approved is False
    assert dec_b.final_status == "REJECTED"
    assert any("VISUAL_QA_FAILED" in r for r in dec_b.reasons)

    # Scenario C: Visual PASSES but VLM detects anatomy distortion -> REJECTED
    sem_anatomy_fail = SemanticQAResponse(
        characters_visible=1,
        expected_character_match="likely",
        outfit_match=True,
        location_match=True,
        required_props=[PropRequirement(id="PROP_RED_DIARY", present=True)],
        anatomy_warning=True, # Distortion
        continuity_warnings=[],
        confidence=0.75
    )
    dec_c = auditor.evaluate_composite_decision("CAND_03", vis_pass, sem_anatomy_fail)
    assert dec_c.is_approved is False
    assert dec_c.final_status == "REJECTED"
    assert any("Anatomy warning flagged" in r for r in dec_c.reasons)

    # Scenario D: Visual PASSES but required prop is missing -> REJECTED
    sem_prop_fail = SemanticQAResponse(
        characters_visible=1,
        expected_character_match="likely",
        outfit_match=True,
        location_match=True,
        required_props=[PropRequirement(id="PROP_RED_DIARY", present=False)],
        anatomy_warning=False,
        continuity_warnings=[],
        confidence=0.80
    )
    dec_d = auditor.evaluate_composite_decision("CAND_04", vis_pass, sem_prop_fail)
    assert dec_d.is_approved is False
    assert dec_d.final_status == "REJECTED"
    assert any("Missing mandatory props" in r for r in dec_d.reasons)


def test_05_fastapi_endpoints_semantic_audit():
    """Verify FastAPI semantic audit and composite decision endpoints."""
    cand_img = str(FIXTURES_DIR / "cand_01_high_match.png")

    # 1. /api/v1/qa/semantic-audit
    resp = client.post("/api/v1/qa/semantic-audit", json={
        "image_path": cand_img,
        "expected_character_name": "Preeti",
        "expected_wardrobe": "Crimson Sari",
        "expected_location": "Rose Garden",
        "required_props": ["PROP_RED_DIARY"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["characters_visible"] == 1
    assert data["expected_character_match"] == "likely"
    assert data["outfit_match"] is True
    assert data["location_match"] is True
    assert data["anatomy_warning"] is False
    assert len(data["required_props"]) == 1
    assert data["required_props"][0]["present"] is True

    # 2. /api/v1/qa/composite-decision
    resp_comp = client.post("/api/v1/qa/composite-decision", json={
        "candidate_id": "CAND_WINNER_01",
        "visual_eval": {"composite_score": 0.85, "is_passing": True},
        "semantic_eval": data,
        "min_visual_score": 0.60
    })
    assert resp_comp.status_code == 200
    comp_data = resp_comp.json()
    assert comp_data["is_approved"] is True
    assert comp_data["final_status"] == "APPROVED"
    assert comp_data["visual_score"] == 0.85
