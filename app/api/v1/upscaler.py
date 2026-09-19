"""Video Upscaling and Benchmark API Router."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query

from app.core.upscale_benchmark import (
    BenchmarkClipCategory,
    UpscaleBenchmarkReport,
    UpscaleRequest,
    UpscaleResponse,
    UpscalerBenchmark,
    UpscalerBenchmarkError,
)

router = APIRouter(prefix="/upscaler", tags=["upscaler"])


@router.post("/benchmark", response_model=UpscaleBenchmarkReport)
def run_upscaler_benchmark() -> UpscaleBenchmarkReport:
    """Executes comparative benchmark across SeedVR2, FlashVSR, and conventional Lanczos

    evaluating speed and artifact rate across 4 clip categories.
    """
    try:
        return UpscalerBenchmark.run_benchmark()
    except UpscalerBenchmarkError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upscaler benchmark error: {str(exc)}")


@router.get("/default-policy")
def get_default_upscaler_policy() -> Dict[str, Any]:
    """Returns the recommended upscaler engine policy per clip category."""
    report = UpscalerBenchmark.run_benchmark()
    return {
        "recommended_default": report.recommended_default_engine,
        "categories": report.category_recommendations,
        "rationale": report.decision_rationale,
    }


@router.post("/upscale", response_model=UpscaleResponse)
def upscale_video_shot(
    req: UpscaleRequest,
    mock: bool = Query(default=False, description="Run in mock mode for testing"),
) -> UpscaleResponse:
    """Upscales a video shot to target resolution (1080x1920) using policy-selected engine."""
    try:
        return UpscalerBenchmark.upscale_video(req, mock_mode=mock)
    except UpscalerBenchmarkError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upscaling error: {str(exc)}")
