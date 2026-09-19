"""Driving Motion Library and SCAIL-2 Performance API Router."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.motion_library import MotionLibrary, MotionRecord
from app.core.scail_engine import (
    ScailEngine,
    ScailEngineError,
    ScailRenderRequest,
    ScailRenderResponse,
)

router = APIRouter(prefix="/motion", tags=["motion"])
motion_lib = MotionLibrary()
engine = ScailEngine()


@router.get("/library", response_model=List[MotionRecord])
def list_driving_motions(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    search: Optional[str] = Query(default=None, description="Search term in name, tags, description"),
) -> List[MotionRecord]:
    """Lists available driving performances from the motion library."""
    if search:
        return motion_lib.search_motions(search)
    return motion_lib.list_motions(category=category)


@router.get("/library/{motion_id}", response_model=MotionRecord)
def get_driving_motion(motion_id: str) -> MotionRecord:
    """Retrieves a specific motion record by motion_id."""
    motion = motion_lib.get_motion(motion_id)
    if not motion:
        raise HTTPException(status_code=404, detail=f"Motion {motion_id} not found in library.")
    return motion


@router.post("/scail-render", response_model=ScailRenderResponse)
def execute_scail_render(
    req: ScailRenderRequest,
    mock: bool = Query(default=False, description="Run in fast mock mode for testing"),
) -> ScailRenderResponse:
    """Executes a SCAIL-2 controlled performance transfer from keyframe + driving motion."""
    try:
        return engine.execute_controlled_performance(req, mock_mode=mock)
    except ScailEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SCAIL execution error: {str(exc)}")
