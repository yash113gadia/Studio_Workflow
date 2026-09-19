from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.core.queue import DurableQueue
from app.core.models import JobRecord, JobCreate

router = APIRouter(prefix="/jobs", tags=["Jobs Queue"])


@router.post("", response_model=JobRecord)
def enqueue_job(job_in: JobCreate):
    return DurableQueue.enqueue(job_in)


@router.get("", response_model=List[JobRecord])
def list_jobs(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200)
):
    return DurableQueue.list_jobs(project_id=project_id, status=status, limit=limit)


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str):
    job = DurableQueue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/start", response_model=JobRecord)
def start_job(job_id: str):
    job = DurableQueue.start_job(job_id)
    if not job:
        raise HTTPException(status_code=400, detail="Unable to start job; not in pending or retryable state")
    return job


@router.post("/{job_id}/heartbeat")
def heartbeat_job(job_id: str):
    success = DurableQueue.heartbeat(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job not running or not found")
    return {"status": "ok"}


@router.post("/{job_id}/complete", response_model=JobRecord)
def complete_job(job_id: str, output_assets: Optional[List[str]] = None):
    job = DurableQueue.complete_job(job_id, output_asset_ids=output_assets)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/fail", response_model=JobRecord)
def fail_job(job_id: str, error_class: str = "ExecutionError", error_message: str = "", retryable: bool = True):
    job = DurableQueue.fail_job(job_id, error_class=error_class, error_message=error_message, retryable=retryable)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=JobRecord)
def cancel_job(job_id: str):
    job = DurableQueue.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
