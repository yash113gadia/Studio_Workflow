"""Experimental Sandbox API Router."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from app.core.ltx_sandbox import (
    LTXSandboxEngine,
    LTXSandboxError,
    LTXSandboxReport,
)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@router.get("/ltx/profile")
def get_ltx_sandbox_profile() -> Dict[str, Any]:
    """Returns the isolated LTX-2.5 sandbox configuration and production isolation guard status."""
    return LTXSandboxEngine.get_sandbox_profile()


@router.post("/ltx/benchmark", response_model=LTXSandboxReport)
def run_ltx_sandbox_benchmark() -> LTXSandboxReport:
    """Executes comparative evaluation of LTX-2.5 vs production MiniMax H3 / SCAIL

    across 4 experimental dimensions before router promotion consideration.
    """
    try:
        return LTXSandboxEngine.run_comparative_benchmark()
    except LTXSandboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sandbox benchmark error: {str(exc)}")
