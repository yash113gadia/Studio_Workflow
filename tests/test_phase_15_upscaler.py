"""Acceptance Test Suite for Phase 15: Upscaler Benchmark (SeedVR2 vs FlashVSR vs Conventional Lanczos)."""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.core.post.ffmpeg_utils import run_ffmpeg
from app.core.upscale_benchmark import (
    BenchmarkClipCategory,
    UpscaleRequest,
    UpscaleResponse,
    UpscalerBenchmark,
    UpscalerEngine,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


client = TestClient(app)


def create_dummy_video(path: str, duration_s: float = 1.0, width: int = 480, height: int = 864):
    """Creates a small 480x864 test video file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = [
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_s}:size={width}x{height}:rate=24",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y", path,
    ]
    code, stdout, stderr = run_ffmpeg(cmd)
    assert code == 0, f"Failed to create dummy test video: {stderr}"


def test_phase_15_benchmark_all_engines_and_categories():
    """Verifies that all 3 engines are benchmarked across all 4 canonical categories."""
    report = UpscalerBenchmark.run_benchmark()
    assert report.hardware_target is not None
    assert len(report.metrics) == 12  # 3 engines x 4 categories

    engines_seen = {m.engine for m in report.metrics}
    assert engines_seen == {UpscalerEngine.NO_AI_LANCZOS, UpscalerEngine.WANGP_SEEDVR2, UpscalerEngine.FLASHVSR}

    categories_seen = {m.category for m in report.metrics}
    assert categories_seen == {
        BenchmarkClipCategory.STYLIZED_FACES,
        BenchmarkClipCategory.HANDS,
        BenchmarkClipCategory.TEXTLESS_BACKGROUNDS,
        BenchmarkClipCategory.HIGH_MOTION_CLIPS,
    }

    # Verify metric fields
    for m in report.metrics:
        assert m.speed_fps > 0.0
        assert m.vram_peak_mb >= 0.0
        assert 0.0 <= m.artifact_rate <= 1.0
        assert 0.0 <= m.sharpness_score <= 100.0
        assert m.composite_efficiency_score >= 0.0


def test_phase_15_decision_policy_enforcement():
    """Verifies: default selection by artifact rate + speed, and hands safety rule."""
    report = UpscalerBenchmark.run_benchmark()

    # Master AI default is FlashVSR (17.6 FPS, low artifact rate)
    assert report.recommended_default_engine == UpscalerEngine.FLASHVSR

    # Hands category must enforce NO_AI_LANCZOS to prevent finger hallucination
    assert report.category_recommendations[BenchmarkClipCategory.HANDS.value] == UpscalerEngine.NO_AI_LANCZOS
    engine_for_hands = UpscalerBenchmark.get_default_engine_for_category(BenchmarkClipCategory.HANDS)
    assert engine_for_hands == UpscalerEngine.NO_AI_LANCZOS


def test_phase_15_upscale_video_execution(tmp_path):
    """Verifies: upscaling execution from 480x864 to 1080x1920."""
    input_vid = str(tmp_path / "shot_input_480x864.mp4")
    create_dummy_video(input_vid)

    req = UpscaleRequest(
        project_id="PROJ_UPSCALE_TEST",
        shot_id="shot_001_upscale",
        input_video_path=input_vid,
        category=BenchmarkClipCategory.STYLIZED_FACES,
        target_width=1080,
        target_height=1920,
        output_path=str(tmp_path / "shot_upscaled_1080x1920.mp4"),
    )

    res = UpscalerBenchmark.upscale_video(req, mock_mode=False)
    assert res.output_video_path is not None
    assert os.path.exists(res.output_video_path)
    assert res.output_res == "1080x1920"
    assert res.engine_used == UpscalerEngine.FLASHVSR.value
    assert res.artifact_rate_estimate < 0.15
    assert os.path.getsize(res.output_video_path) > 1000


def test_phase_15_fastapi_endpoints(tmp_path):
    """Verifies REST endpoints for benchmark report, policy retrieval, and upscaling."""
    # 1. Benchmark endpoint
    r1 = client.post("/api/v1/upscaler/benchmark")
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["metrics"]) == 12

    # 2. Default policy endpoint
    r2 = client.get("/api/v1/upscaler/default-policy")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["recommended_default"] == "flashvsr"
    assert d2["categories"]["hands"] == "no_ai_lanczos"

    # 3. Upscale API execution (using mock mode for fast API verification)
    input_vid = str(tmp_path / "api_test_vid.mp4")
    create_dummy_video(input_vid)
    upscale_payload = {
        "project_id": "PROJ_API_TEST",
        "shot_id": "shot_api_upscale",
        "input_video_path": input_vid,
        "category": "hands",
        "target_width": 1080,
        "target_height": 1920,
        "output_path": str(tmp_path / "api_upscaled.mp4"),
    }
    r3 = client.post("/api/v1/upscaler/upscale?mock=true", json=upscale_payload)
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["engine_used"] == "no_ai_lanczos"
    assert d3["output_res"] == "1080x1920"
    assert os.path.exists(d3["output_video_path"])
