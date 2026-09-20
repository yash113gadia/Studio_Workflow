"""Live local model and runtime capability API."""
from fastapi import APIRouter

from app.core.capabilities import discover_capabilities


router = APIRouter(prefix="/capabilities", tags=["Runtime capabilities"])


@router.get("")
def get_capabilities():
    return discover_capabilities()
