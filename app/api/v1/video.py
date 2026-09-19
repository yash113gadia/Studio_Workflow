"""Video Generation API Router — WanGP MiniMax H3 Short-Shot Profile."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.models import H3ShotRequest, H3ShotResponse
from app.core.wangp_adapter import (
    WanGPAdapter,
    WanGPAdapterError,
    WANGP_PINNED_COMMIT,
    WANGP_MIN_DISK_BUFFER_GB,
)

router = APIRouter(prefix="/video", tags=["video"])
adapter = WanGPAdapter()


@router.get("/h3-profile")
def get_h3_profile() -> Dict[str, Any]:
    """Returns the Master Plan recommended MiniMax H3 low-VRAM short-shot profile."""
    try:
        free_gb = adapter.check_disk_safety()
        disk_ok = True
    except WanGPAdapterError:
        disk_ok = False
        free_gb = 0.0

    return {
        "backend": "wangp_h3",
        "pinned_commit": WANGP_PINNED_COMMIT,
        "supported_architectures": [
            "minimax_h3_fl2va_pruned",
            "minimax_h3_ref2va_pruned",
        ],
        "default_profile": {
            "resolution": "480x864",
            "aspect": "9:16",
            "duration_s": 5.0,
            "fps": 24,
            "candidates": 1,
            "denoising_priority": "lower_vram",
            "text_encoder_variant": "gguf_q2_k",
            "video_vae_variant": "fp8mix",
        },
        "hardware_target": "NVIDIA RTX 3070 Laptop (8GB VRAM)",
        "disk_safety_buffer_gb": WANGP_MIN_DISK_BUFFER_GB,
        "free_disk_gb": round(free_gb, 2),
        "disk_safe": disk_ok,
    }


@router.post("/h3-shot", response_model=H3ShotResponse)
def create_h3_shot(req: H3ShotRequest) -> H3ShotResponse:
    """Queues a MiniMax H3 short-shot job in the durable queue."""
    try:
        return adapter.submit_h3_shot_job(req)
    except WanGPAdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error submitting H3 shot: {str(exc)}")


@router.post("/h3-execute", response_model=H3ShotResponse)
def execute_h3_shot_direct(
    req: H3ShotRequest,
    mock: bool = Query(default=False, description="Run in fast mock mode for testing"),
) -> H3ShotResponse:
    """Directly executes an H3 short-shot job with GPU lease protection."""
    try:
        initial = adapter.submit_h3_shot_job(req)
        return adapter.execute_shot_generation(initial.job_id, req, mock_mode=mock)
    except WanGPAdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(exc)}")
