import shutil
from fastapi import APIRouter
from app.core.config import settings
from app.core.gpu_lease import GPULeaseManager
from app.core.database import get_connection
from app.core.models import SystemHealthResponse, JobStatus

router = APIRouter(tags=["Health & System"])


@router.get("/health", response_model=SystemHealthResponse)
def get_health():
    # Database check
    db_ok = False
    pending_count = 0
    running_count = 0
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM render_jobs WHERE status = ?", (JobStatus.PENDING.value,))
        pending_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM render_jobs WHERE status = ?", (JobStatus.RUNNING.value,))
        running_count = cursor.fetchone()[0]
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    # GPU lease check
    lease = GPULeaseManager.get_lease_status()
    lease_status = "LOCKED" if lease.is_locked else "FREE"

    # Disk check
    total, used, free = shutil.disk_usage(settings.paths.root)
    free_gb = round(free / (1024 ** 3), 2)

    return SystemHealthResponse(
        status="ok" if db_ok else "degraded",
        studio_name=settings.studio_name,
        version=settings.version,
        database_connected=db_ok,
        queue_pending_count=pending_count,
        queue_running_count=running_count,
        gpu_lease_status=lease_status,
        gpu_lease_owner=lease.owner_job_id,
        free_disk_gb=free_gb
    )


@router.get("/system")
def get_system_info():
    total, used, free = shutil.disk_usage(settings.paths.root)
    return {
        "studio_name": settings.studio_name,
        "version": settings.version,
        "environment": settings.environment,
        "paths": settings.paths.model_dump(),
        "safety": {
            "minimum_free_disk_gb": settings.safety.minimum_free_disk_gb,
            "current_free_disk_gb": round(free / (1024 ** 3), 2)
        }
    }
