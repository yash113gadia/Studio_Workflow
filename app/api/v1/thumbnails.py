"""Thumbnail Generation and Brief Planning API Router."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.thumbnails.brief_agent import ThumbnailBrief, ThumbnailBriefAgent
from app.core.thumbnails.thumbnail_manager import (
    ThumbnailGenerationRequest,
    ThumbnailGenerationResponse,
    ThumbnailManager,
    ThumbnailManagerError,
)

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])


class BriefRequest(BaseModel):
    episode_id: str
    series_title: str
    episode_number: int
    episode_title: str
    synopsis: str = ""
    cliffhanger_summary: str = ""


@router.post("/brief", response_model=ThumbnailBrief)
def generate_thumbnail_brief(req: BriefRequest) -> ThumbnailBrief:
    """Produces a spoiler-aware thumbnail brief with emotional hook and candidate artwork prompts."""
    try:
        return ThumbnailBriefAgent.generate_brief(req.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Brief generation error: {str(exc)}")


@router.post("/generate", response_model=ThumbnailGenerationResponse)
def generate_episode_thumbnails(
    req: ThumbnailGenerationRequest,
    mock: bool = Query(default=False, description="Run in mock mode for testing"),
) -> ThumbnailGenerationResponse:
    """Executes end-to-end thumbnail creation: 4 artwork candidates, DINO/QA ranking,

    winning candidate selection, programmatic typography, and multi-platform variant export.
    """
    try:
        return ThumbnailManager.generate_thumbnails(req, mock_mode=mock)
    except ThumbnailManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Thumbnail generation error: {str(exc)}")
