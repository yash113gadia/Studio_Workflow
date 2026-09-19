"""Acceptance Test Suite for Phase 17: Creator Mode End-to-End Autonomous Pipeline."""
import json
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.core.creator_mode import (
    CreatorModeEngine,
    CreatorPackage,
    CreatorScriptInput,
    CreatorStoryBeat,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


client = TestClient(app)


SAMPLE_USER_SCRIPT = """
SCENE 1: ARCHIVE ROOM - NIGHT
The rain patters against the tall glass pane. Maya steps quietly across the polished floor.
MAYA: I knew the ledger was here.

SCENE 2: CONFRONTATION
Vikram turns sharply, stepping out from the long corridor shadows.
VIKRAM: You should not have returned, Maya.

SCENE 3: ESCAPE
The alarm siren explodes into action. Red emergency lights flash as Maya dashes for the heavy steel exit.
"""


def test_phase_17_story_beat_normalization_and_entity_extraction():
    """Verifies: raw 30-60s script is normalized into sequenced story beats with entity extraction."""
    beats = CreatorModeEngine.normalize_story_beats(SAMPLE_USER_SCRIPT, target_duration_s=42.0)
    assert len(beats) == 3

    # Beat 1: Maya in Archive Room
    b1 = beats[0]
    assert "scene 1" in b1.heading.lower()
    assert "MAYA" in b1.characters
    assert len(b1.dialogue) == 1
    assert b1.dialogue[0]["speaker"] == "MAYA"
    assert b1.recommended_route == "scail_motion"  # Dialogue -> controlled motion

    # Beat 2: Vikram confrontation
    b2 = beats[1]
    assert "scene 2" in b2.heading.lower()
    assert "VIKRAM" in b2.characters
    assert len(b2.dialogue) == 1
    assert b2.dialogue[0]["speaker"] == "VIKRAM"

    # Beat 3: Alarm explodes, dash for exit
    b3 = beats[2]
    assert "scene 3" in b3.heading.lower()
    assert b3.recommended_route == "h3_generative"  # High action/explodes -> H3 generative


def test_phase_17_automated_route_decisions():
    """Verifies automated engine route selection (2.5D vs SCAIL vs H3)."""
    script_subtle = "Maya stares silently at the flickering candle flame in the dark study."
    beats_subtle = CreatorModeEngine.normalize_story_beats(script_subtle, target_duration_s=6.0)
    assert beats_subtle[0].recommended_route == "2.5d"  # Reaction/insert -> 2.5D cheap-shot

    script_action = "The sports car explodes into flames as the motorcycle speeds into the tunnel."
    beats_action = CreatorModeEngine.normalize_story_beats(script_action, target_duration_s=8.0)
    assert beats_action[0].recommended_route == "h3_generative"


def test_phase_17_e2e_autonomous_execution_without_graph_editing(tmp_path):
    """Core Acceptance Test for Phase 17:

    Autonomous execution from script to final package (master video, SRT, thumbnails, QA, provenance)
    without manual node graph editing.
    """
    req = CreatorScriptInput(
        title="Midnight Ledger",
        raw_script_text=SAMPLE_USER_SCRIPT,
        target_duration_s=36.0,
    )

    package = CreatorModeEngine.execute_pipeline(req, mock_mode=True)
    assert package.package_id is not None
    assert package.title == "Midnight Ledger"
    assert package.total_duration_s > 0.0

    # 1. Master video file exists
    assert os.path.exists(package.master_video_path)
    assert os.path.getsize(package.master_video_path) > 1000

    # 2. Subtitles SRT file exists
    assert os.path.exists(package.subtitles_srt_path)

    # 3. Multi-platform thumbnail variants generated
    assert "vertical_9_16" in package.thumbnail_variants
    assert "square_1_1" in package.thumbnail_variants
    assert "widescreen_16_9" in package.thumbnail_variants
    for path in package.thumbnail_variants.values():
        assert os.path.exists(path)

    # 4. QA Report generated
    assert package.qa_report["overall_decision"] == "PASS"
    assert package.qa_report["visual_dino_score"] >= 0.80

    # 5. Provenance sidecar JSON exists
    assert os.path.exists(package.provenance_sidecar_path)
    with open(package.provenance_sidecar_path, "r", encoding="utf-8") as f:
        sidecar = json.load(f)
    assert sidecar["pipeline_type"] == "autonomous_creator_mode_no_manual_graph_editing"
    assert len(sidecar["story_beats_count"]) > 0 if isinstance(sidecar["story_beats_count"], list) else sidecar["story_beats_count"] == 3


def test_phase_17_fastapi_endpoints():
    """Verifies REST endpoints for script parsing and autonomous execution."""
    payload = {
        "title": "Neon Shadows",
        "raw_script_text": SAMPLE_USER_SCRIPT,
        "target_duration_s": 30.0,
    }

    # 1. /api/v1/creator/parse
    r1 = client.post("/api/v1/creator/parse", json=payload)
    assert r1.status_code == 200
    beats = r1.json()
    assert len(beats) == 3
    assert beats[0]["recommended_route"] in ["2.5d", "scail_motion", "h3_generative"]

    # 2. /api/v1/creator/execute
    r2 = client.post("/api/v1/creator/execute?mock=true", json=payload)
    assert r2.status_code == 200
    pkg = r2.json()
    assert pkg["title"] == "Neon Shadows"
    assert os.path.exists(pkg["master_video_path"])
    assert "vertical_9_16" in pkg["thumbnail_variants"]
