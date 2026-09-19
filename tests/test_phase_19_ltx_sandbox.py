"""Acceptance Test Suite for Phase 19: Isolated LTX-2.5 Sandbox Profile."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.core.ltx_sandbox import (
    LTXSandboxEngine,
    LTXSandboxReport,
    SandboxCapability,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


client = TestClient(app)


def test_phase_19_sandbox_isolation_and_profile():
    """Verifies that the LTX sandbox is isolated and guarded from altering production."""
    profile = LTXSandboxEngine.get_sandbox_profile()
    assert profile["profile_name"] == "LTX-2.5-Sandbox"
    assert profile["environment_mode"] == "isolated_experimental"
    assert profile["production_interference_guard"] is True
    assert profile["memory_budget_mb"] <= 7500.0


def test_phase_19_comparative_benchmark_all_4_capabilities():
    """Verifies comparative evaluation across all 4 experimental capabilities required by Master Plan."""
    report = LTXSandboxEngine.run_comparative_benchmark()
    assert report.isolation_verified is True
    assert len(report.benchmarks) == 4

    caps_seen = {b.capability for b in report.benchmarks}
    assert caps_seen == {
        SandboxCapability.FIRST_LAST_FRAME_TRANSITIONS,
        SandboxCapability.MULTI_SUBJECT_REFERENCE_SHOTS,
        SandboxCapability.CHAINED_KEYFRAME_TRANSITIONS,
        SandboxCapability.RUNTIME_ACCEPTANCE_RATE,
    }

    for b in report.benchmarks:
        assert b.production_score > 0.0
        assert b.ltx_sandbox_score > 0.0
        assert b.vram_peak_mb > 0.0
        assert isinstance(b.promotable_to_production, bool)


def test_phase_19_gating_decision_rule():
    """Verifies Master Plan Phase 19 rule: promote only if benchmark shows clear advantage."""
    report = LTXSandboxEngine.run_comparative_benchmark()
    # On our 8GB laptop, W4A8 quantization causes texture artifacts and higher memory pressure.
    # Therefore, LTX-2.5 should be retained in the sandbox rather than displacing production H3.
    assert report.overall_promotable is False
    assert "KEEP IN EXPERIMENTAL SANDBOX" in report.final_recommendation


def test_phase_19_fastapi_endpoints():
    """Verifies REST endpoints for sandbox profile and comparative benchmarking."""
    # 1. GET /api/v1/sandbox/ltx/profile
    r1 = client.get("/api/v1/sandbox/ltx/profile")
    assert r1.status_code == 200
    p = r1.json()
    assert p["production_interference_guard"] is True

    # 2. POST /api/v1/sandbox/ltx/benchmark
    r2 = client.post("/api/v1/sandbox/ltx/benchmark")
    assert r2.status_code == 200
    rep = r2.json()
    assert rep["isolation_verified"] is True
    assert len(rep["benchmarks"]) == 4
