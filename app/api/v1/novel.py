"""FastAPI Router for Novel Ingestion & Season Planning."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.novel_parser import NovelParser, NovelChunk
from app.core.season_planner import SeasonPlanner, SeasonMap

router = APIRouter(prefix="/novel", tags=["Novel Ingestion & Season Planning"])


class IngestNovelRequest(BaseModel):
    project_id: str
    title: str
    raw_text: str


class PlanSeasonRequest(BaseModel):
    project_id: str
    novel_title: str
    raw_text: str
    target_episodes: int = 5


@router.post("/ingest")
def ingest_novel(req: IngestNovelRequest):
    """Ingest novel text, split into structural chapters, and create cited chunks."""
    try:
        chunks = NovelParser.ingest_novel_text(req.project_id, req.title, req.raw_text)
        return {
            "status": "ingested",
            "project_id": req.project_id,
            "title": req.title,
            "total_chunks": len(chunks),
            "sample_chunk_id": chunks[0].chunk_id if chunks else None
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plan_season", response_model=SeasonMap)
def plan_season(req: PlanSeasonRequest):
    """Ingest novel and produce an entire 5-episode or 45-episode vertical season map with citations."""
    try:
        chunks = NovelParser.ingest_novel_text(req.project_id, req.novel_title, req.raw_text)
        return SeasonPlanner.generate_season_map(
            project_id=req.project_id,
            novel_title=req.novel_title,
            chunks=chunks,
            target_episodes=req.target_episodes
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
