"""Creator Mode API Router — Autonomous Script-to-Screen Execution."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query

from app.core.creator_mode import (
    CreatorModeEngine,
    CreatorModeError,
    CreatorPackage,
    CreatorScriptInput,
    CreatorStoryBeat,
)

router = APIRouter(prefix="/creator", tags=["creator-mode"])


@router.post("/parse", response_model=List[CreatorStoryBeat])
def parse_script_beats(req: CreatorScriptInput) -> List[CreatorStoryBeat]:
    """Parses raw text script into normalized dramatic story beats and automated engine routes."""
    try:
        return CreatorModeEngine.normalize_story_beats(req.raw_script_text, req.target_duration_s)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Script parsing error: {str(exc)}")


@router.post("/execute", response_model=CreatorPackage)
def execute_creator_mode(
    req: CreatorScriptInput,
    mock: bool = Query(default=True, description="Run in mock mode for testing"),
) -> CreatorPackage:
    """Executes the complete autonomous Creator Mode pipeline without requiring manual node graph interaction."""
    try:
        return CreatorModeEngine.execute_pipeline(req, mock_mode=mock)
    except CreatorModeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Creator mode execution error: {str(exc)}")
