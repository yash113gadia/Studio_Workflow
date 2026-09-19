"""Series Mode Pilot and Multi-Episode Continuity API Router."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.series_pilot import (
    PilotExecutionResult,
    PilotTier,
    SeriesPilotError,
    SeriesPilotManager,
)

router = APIRouter(prefix="/series", tags=["series-mode"])


class RunPilotRequest(BaseModel):
    project_id: str
    tier: PilotTier = PilotTier.PILOT_A_2_EP
    series_title: str = "The Long Shadows"


@router.post("/pilot/run", response_model=PilotExecutionResult)
def run_series_pilot(
    req: RunPilotRequest,
    mock: bool = Query(default=True, description="Run in mock mode for testing"),
) -> PilotExecutionResult:
    """Executes a staged series pilot (Pilot A: 2 eps, Pilot B: 5 eps, Pilot C: 10 eps)

    tracking 8 continuity dimensions before unlocking full season production.
    """
    try:
        return SeriesPilotManager.run_pilot(
            project_id=req.project_id,
            tier=req.tier,
            series_title=req.series_title,
            mock_mode=mock,
        )
    except SeriesPilotError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Series pilot error: {str(exc)}")
