"""Specialist Editor API Endpoints — Qwen-Image-Edit-2511 Branch."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.models import (
    SpecialistEditAction,
    SpecialistEditRequest,
    SpecialistEditResponse,
    AssetRecord,
)
from app.core.specialist_editor import SpecialistEditor, ACTION_WORKFLOW_MAP, DEFAULT_INSTRUCTIONS

router = APIRouter(prefix="/editor", tags=["Specialist Editor"])
editor = SpecialistEditor()


class CompleteEditRequest(BaseModel):
    project_id: str
    output_asset_id: str
    source_asset_id: str
    action: SpecialistEditAction
    image_path: str
    instruction: str
    seed: int
    qa_metrics: Optional[Dict[str, Any]] = None


@router.get("/actions")
def list_actions():
    """List supported specialist edit actions and their descriptions."""
    return [
        {
            "action": a.value,
            "workflow": ACTION_WORKFLOW_MAP[a],
            "default_instruction": DEFAULT_INSTRUCTIONS[a],
        }
        for a in SpecialistEditAction
    ]


@router.post("/edit", response_model=SpecialistEditResponse)
def trigger_edit(req: SpecialistEditRequest):
    """Trigger a specialist image edit on an approved character or scene keyframe."""
    try:
        return editor.create_edit_job(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/complete", response_model=AssetRecord)
def complete_edit(req: CompleteEditRequest):
    """Register a completed specialist edit asset with QA scores and provenance."""
    try:
        return editor.register_completed_edit_asset(
            project_id=req.project_id,
            output_asset_id=req.output_asset_id,
            source_asset_id=req.source_asset_id,
            action=req.action,
            image_path=req.image_path,
            instruction=req.instruction,
            seed=req.seed,
            qa_metrics=req.qa_metrics,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/edits/{source_asset_id}", response_model=List[AssetRecord])
def list_edits_for_asset(source_asset_id: str):
    """Retrieve all edited assets derived from a source reference."""
    return editor.list_edits_for_asset(source_asset_id)
