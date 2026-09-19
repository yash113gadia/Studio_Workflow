from fastapi import APIRouter, HTTPException
from app.core.gpu_lease import GPULeaseManager
from app.core.models import (
    GPULeaseRecord,
    GPULeaseAcquireRequest,
    GPULeaseHeartbeatRequest,
    GPULeaseReleaseRequest
)

router = APIRouter(prefix="/gpu", tags=["Global GPU Mutex"])


@router.get("/lease", response_model=GPULeaseRecord)
def get_lease():
    return GPULeaseManager.get_lease_status()


@router.post("/lease/acquire")
def acquire_lease(req: GPULeaseAcquireRequest):
    success, token, msg = GPULeaseManager.acquire(req.job_id)
    if not success:
        raise HTTPException(status_code=409, detail=msg)
    return {"status": "acquired", "token": token, "message": msg}


@router.post("/lease/heartbeat")
def heartbeat_lease(req: GPULeaseHeartbeatRequest):
    ok = GPULeaseManager.heartbeat(req.token)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid token or lease expired")
    return {"status": "heartbeat_ok"}


@router.post("/lease/release")
def release_lease(req: GPULeaseReleaseRequest):
    ok = GPULeaseManager.release(req.token)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid token or lease not active")
    return {"status": "released"}
