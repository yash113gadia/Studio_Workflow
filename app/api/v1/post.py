"""Post-Production, 2.5D Cheap-Shot Renderer, and FFmpeg Assembly API Router."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query

from app.core.post.renderer_25d import (
    Render25DRequest,
    Render25DResponse,
    Renderer25D,
    Renderer25DError,
)
from app.core.post.assembly_engine import (
    AssemblyEngine,
    AssemblyEngineError,
    AssemblyRequest,
    AssemblyResponse,
)

router = APIRouter(prefix="/post", tags=["post-production"])


@router.post("/2.5d/render", response_model=Render25DResponse)
def render_25d_shot(
    req: Render25DRequest,
    mock: bool = Query(default=False, description="Run in fast mock mode for testing"),
) -> Render25DResponse:
    """Renders a 2.5D cheap-shot clip from a still keyframe image using camera motion and atmospheric overlays."""
    try:
        return Renderer25D.render(req, mock_mode=mock)
    except Renderer25DError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"2.5D rendering error: {str(exc)}")


@router.post("/assembly/assemble", response_model=AssemblyResponse)
def assemble_sequence(
    req: AssemblyRequest,
    mock: bool = Query(default=False, description="Run in fast mock mode for testing"),
) -> AssemblyResponse:
    """Deterministically assembles video shots, trims, multi-stem audio mix, EBU R128 loudness normalization,

    captions, and encodes 1080x1920 master MP4 with provenance sidecar.
    """
    try:
        return AssemblyEngine.assemble(req, mock_mode=mock)
    except AssemblyEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Post assembly error: {str(exc)}")
