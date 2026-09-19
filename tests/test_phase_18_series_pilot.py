"""Acceptance Test Suite for Phase 18: Series Mode Staged Pilot (2 -> 5 -> 10 Episodes) & Continuity Audit."""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.core.models import ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.series_pilot import (
    PilotExecutionResult,
    PilotTier,
    SeriesPilotManager,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


client = TestClient(app)


def test_phase_18_pilot_a_2_episodes():
    """Verifies: Pilot A evaluates 2 consecutive episodes and unlocks Pilot B."""
    proj = ProjectManager.create_project(
        ProjectCreate(
            name="Series Pilot A Project",
            kind=ProjectKind.SERIES,
            description="Testing Pilot A 2-episode continuity",
        )
    )

    res = SeriesPilotManager.run_pilot(
        project_id=proj.id,
        tier=PilotTier.PILOT_A_2_EP,
        series_title="The Midnight Syndicate",
    )

    assert res.pilot_tier == PilotTier.PILOT_A_2_EP
    assert res.episodes_count == 2
    assert len(res.episodes_evaluated) == 2
    assert res.overall_passed is True
    assert res.unlocked_next_tier == PilotTier.PILOT_B_5_EP
    assert res.total_violations == 0


def test_phase_18_pilot_b_5_episodes():
    """Verifies: Pilot B evaluates 5 consecutive episodes and unlocks Pilot C."""
    proj = ProjectManager.create_project(
        ProjectCreate(
            name="Series Pilot B Project",
            kind=ProjectKind.SERIES,
            description="Testing Pilot B 5-episode continuity",
        )
    )

    res = SeriesPilotManager.run_pilot(
        project_id=proj.id,
        tier=PilotTier.PILOT_B_5_EP,
        series_title="The Midnight Syndicate",
    )

    assert res.pilot_tier == PilotTier.PILOT_B_5_EP
    assert res.episodes_count == 5
    assert len(res.episodes_evaluated) == 5
    assert res.overall_passed is True
    assert res.unlocked_next_tier == PilotTier.PILOT_C_10_EP


def test_phase_18_pilot_c_10_episodes_continuity_stress_test_and_gating():
    """Core Acceptance Test for Phase 18:

    Pilot C executes a 10-episode continuity stress test across all 8 dimensions
    and unlocks full 45-episode production authorization.
    """
    proj = ProjectManager.create_project(
        ProjectCreate(
            name="Series Pilot C Stress Project",
            kind=ProjectKind.SERIES,
            description="Testing Pilot C 10-episode stress test",
        )
    )

    res = SeriesPilotManager.run_pilot(
        project_id=proj.id,
        tier=PilotTier.PILOT_C_10_EP,
        series_title="The Midnight Syndicate",
    )

    assert res.pilot_tier == PilotTier.PILOT_C_10_EP
    assert res.episodes_count == 10
    assert len(res.episodes_evaluated) == 10
    assert res.overall_passed is True
    assert res.unlocked_next_tier == PilotTier.FULL_SERIES_45_EP
    assert res.total_violations == 0

    # Verify all 8 dimensions are present and passing thresholds
    required_dims = [
        "face_hair_body",
        "outfits",
        "props",
        "location_geometry",
        "voice",
        "character_knowledge",
        "relationships",
        "timeline_age_state",
    ]
    for dim_key in required_dims:
        assert dim_key in res.dimensions
        dim_data = res.dimensions[dim_key]
        assert dim_data.status == "PASS"
        assert dim_data.drift_score <= 0.18
        assert dim_data.baseline_similarity >= 0.80

    # Verify report written on disk
    report_file = os.path.join(os.getcwd(), "docs", "SERIES_PILOT_VERIFICATION.md")
    assert os.path.exists(report_file)


def test_phase_18_fastapi_endpoints():
    """Verifies REST endpoints for running series pilot."""
    proj = ProjectManager.create_project(
        ProjectCreate(
            name="Series API Project",
            kind=ProjectKind.SERIES,
            description="Testing API for Pilot",
        )
    )

    payload = {
        "project_id": proj.id,
        "tier": "pilot_a_2_ep",
        "series_title": "Shadow Protocol",
    }

    resp = client.post("/api/v1/series/pilot/run?mock=true", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pilot_tier"] == "pilot_a_2_ep"
    assert data["overall_passed"] is True
    assert data["unlocked_next_tier"] == "pilot_b_5_ep"
    assert len(data["dimensions"]) == 8
