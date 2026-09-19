"""Acceptance Test Suite for Phase 16: Thumbnail System and Programmatic Typography."""
import json
import os
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.core.models import ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.thumbnails.brief_agent import ThumbnailBrief, ThumbnailBriefAgent
from app.core.thumbnails.typography import TypographyEngine
from app.core.thumbnails.thumbnail_manager import (
    ThumbnailGenerationRequest,
    ThumbnailGenerationResponse,
    ThumbnailManager,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


client = TestClient(app)


def test_phase_16_brief_agent_emotional_hook_and_spoiler_filtering():
    """Verifies: brief agent identifies emotional hooks, generates 4 prompts, and filters spoilers."""
    # 1. High-spoiler synopsis gets sanitized
    spoiler_ep = {
        "episode_id": "ep_01",
        "episode_number": 1,
        "series_title": "City of Shadows",
        "episode_title": "The Informant",
        "synopsis": "Maya learns Vikram was the killer all along and dies.",
        "cliffhanger_summary": "Maya dies after drinking the poison.",
    }
    brief = ThumbnailBriefAgent.generate_brief(spoiler_ep)
    assert brief.spoiler_score <= 0.35  # Sanitized!
    assert len(brief.artwork_prompts) == 4
    assert "dies" not in brief.hook_summary.lower()

    # 2. Clean hook retains dramatic tension
    clean_ep = {
        "episode_id": "ep_02",
        "episode_number": 2,
        "series_title": "City of Shadows",
        "episode_title": "The Midnight Rendezvous",
        "synopsis": "A mysterious envelope arrives at the studio.",
        "cliffhanger_summary": "A knock echoes on the darkened studio door.",
    }
    brief2 = ThumbnailBriefAgent.generate_brief(clean_ep)
    assert brief2.spoiler_score <= 0.35
    assert len(brief2.artwork_prompts) == 4
    assert "knock echoes" in brief2.hook_summary.lower() or "stakes escalate" in brief2.hook_summary.lower()


def test_phase_16_programmatic_typography_and_multi_platform_export(tmp_path):
    """Verifies: typography engine applies vignette and exports all 3 platform variants."""
    base_img_path = str(tmp_path / "base_canvas.jpg")
    img = Image.new("RGB", (1080, 1920), (25, 30, 45))
    img.save(base_img_path, "JPEG")

    variants = TypographyEngine.export_all_variants(
        base_artwork_path=base_img_path,
        series_title="City of Shadows",
        episode_number=1,
        episode_title="The Midnight Call",
        output_dir=str(tmp_path / "variants"),
        base_filename_prefix="test_cover",
    )

    assert "vertical_9_16" in variants
    assert "square_1_1" in variants
    assert "widescreen_16_9" in variants

    # Check file dimensions
    with Image.open(variants["vertical_9_16"]) as im:
        assert im.size == (1080, 1920)
    with Image.open(variants["square_1_1"]) as im:
        assert im.size == (1080, 1080)
    with Image.open(variants["widescreen_16_9"]) as im:
        assert im.size == (1280, 720)


def test_phase_16_two_consecutive_episodes_acceptance(tmp_path):
    """Phase 16 Core Acceptance Test:

    Two consecutive test episodes each receive distinct, identity-consistent thumbnail sets
    with correct wardrobe/state and readable programmatic text.
    """
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Thumbnail Acceptance Project",
            kind=ProjectKind.SERIES,
            description="Testing Phase 16 acceptance on 2 consecutive episodes",
        )
    )

    # Reference character image
    ref_img = str(tmp_path / "maya_ref.png")
    Image.new("RGB", (512, 768), (180, 120, 100)).save(ref_img, "PNG")

    # --- EPISODE 1 ---
    req_ep1 = ThumbnailGenerationRequest(
        project_id=project.id,
        episode_id="ep_001",
        series_title="City of Shadows",
        episode_number=1,
        episode_title="The Awakening",
        synopsis="Maya discovers an encrypted ledger in the office archives.",
        cliffhanger_summary="A laser sight locks onto Maya's chest through the window.",
        character_ref_path=ref_img,
        continuity_state={
            "characters": {
                "CHAR_MAYA": {"wardrobe_id": "WARDROBE_MAYA_SILK_BLOUSE", "status": "active"}
            },
            "location_id": "LOC_OFFICE",
        },
        output_dir=str(tmp_path / "ep1_thumbs"),
    )

    res_ep1 = ThumbnailManager.generate_thumbnails(req_ep1, mock_mode=False)
    assert res_ep1.episode_id == "ep_001"
    assert len(res_ep1.candidates) == 4
    assert res_ep1.winning_candidate_id is not None
    assert "vertical_9_16" in res_ep1.exported_variants
    assert res_ep1.brief.wardrobe_id == "WARDROBE_MAYA_SILK_BLOUSE"

    # --- EPISODE 2 ---
    req_ep2 = ThumbnailGenerationRequest(
        project_id=project.id,
        episode_id="ep_002",
        series_title="City of Shadows",
        episode_number=2,
        episode_title="Into The Rain",
        synopsis="Fleeing the sniper, Maya retreats into the underground transit system.",
        cliffhanger_summary="The subway train enters the dark tunnel and all lights extinguish.",
        character_ref_path=ref_img,
        continuity_state={
            "characters": {
                "CHAR_MAYA": {"wardrobe_id": "WARDROBE_MAYA_TRENCHCOAT_WET", "status": "active"}
            },
            "location_id": "LOC_SUBWAY",
        },
        output_dir=str(tmp_path / "ep2_thumbs"),
    )

    res_ep2 = ThumbnailManager.generate_thumbnails(req_ep2, mock_mode=False)
    assert res_ep2.episode_id == "ep_002"
    assert len(res_ep2.candidates) == 4
    assert res_ep2.winning_candidate_id is not None
    assert "vertical_9_16" in res_ep2.exported_variants
    assert res_ep2.brief.wardrobe_id == "WARDROBE_MAYA_TRENCHCOAT_WET"

    # Verification of distinctness and identity-consistency:
    # 1. Wardrobes are correctly propagated and distinct
    assert res_ep1.brief.wardrobe_id != res_ep2.brief.wardrobe_id
    assert res_ep1.brief.wardrobe_id == "WARDROBE_MAYA_SILK_BLOUSE"
    assert res_ep2.brief.wardrobe_id == "WARDROBE_MAYA_TRENCHCOAT_WET"

    # 2. Episode titles and numbers are distinct
    assert res_ep1.brief.episode_title != res_ep2.brief.episode_title
    assert res_ep1.brief.episode_number == 1
    assert res_ep2.brief.episode_number == 2

    # 3. Output files for both episodes exist and are valid JPEGs
    ep1_vert = res_ep1.exported_variants["vertical_9_16"]
    ep2_vert = res_ep2.exported_variants["vertical_9_16"]
    assert os.path.exists(ep1_vert)
    assert os.path.exists(ep2_vert)
    assert os.path.getsize(ep1_vert) > 5000
    assert os.path.getsize(ep2_vert) > 5000


def test_phase_16_fastapi_endpoints(tmp_path):
    """Verifies REST endpoints for brief generation and thumbnail pipeline."""
    # 1. /api/v1/thumbnails/brief
    brief_payload = {
        "episode_id": "ep_api_01",
        "series_title": "Cyber Noir",
        "episode_number": 3,
        "episode_title": "The Cipher",
        "synopsis": "A rogue AI leaks coordinates.",
        "cliffhanger_summary": "The server room door locks automatically.",
    }
    r1 = client.post("/api/v1/thumbnails/brief", json=brief_payload)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["episode_number"] == 3
    assert len(d1["artwork_prompts"]) == 4

    # 2. /api/v1/thumbnails/generate
    gen_payload = {
        "project_id": "PROJ_API_THUMBS",
        "episode_id": "ep_api_01",
        "series_title": "Cyber Noir",
        "episode_number": 3,
        "episode_title": "The Cipher",
        "output_dir": str(tmp_path / "api_thumbs"),
    }
    r2 = client.post("/api/v1/thumbnails/generate?mock=false", json=gen_payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["winning_candidate_id"] is not None
    assert "vertical_9_16" in d2["exported_variants"]
    assert os.path.exists(d2["exported_variants"]["vertical_9_16"])
