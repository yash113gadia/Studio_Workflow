import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from app.core.database import get_connection
from app.core.config import settings
from app.core.models import GPULeaseRecord


class GPULeaseManager:
    RESOURCE = "GPU0_HEAVY"

    @classmethod
    def get_lease_status(cls) -> GPULeaseRecord:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gpu_lease WHERE resource = ?", (cls.RESOURCE,))
            row = cursor.fetchone()
            if not row or not row["token"]:
                return GPULeaseRecord(resource=cls.RESOURCE, is_locked=False)

            # Check if lease has expired
            timeout = settings.gpu_lease.lease_timeout_seconds
            heartbeat_str = row["heartbeat_at"] or row["acquired_at"]
            if heartbeat_str:
                hb_dt = datetime.fromisoformat(heartbeat_str)
                now_dt = datetime.now(timezone.utc)
                if (now_dt - hb_dt).total_seconds() > timeout:
                    # Expired, clear it
                    cursor.execute("""
                    UPDATE gpu_lease
                    SET owner_job_id = NULL, token = NULL, acquired_at = NULL, heartbeat_at = NULL
                    WHERE resource = ?
                    """, (cls.RESOURCE,))
                    conn.commit()
                    return GPULeaseRecord(resource=cls.RESOURCE, is_locked=False)

            return GPULeaseRecord(
                resource=cls.RESOURCE,
                owner_job_id=row["owner_job_id"],
                token=row["token"],
                acquired_at=row["acquired_at"],
                heartbeat_at=row["heartbeat_at"],
                is_locked=True
            )
        finally:
            conn.close()

    @classmethod
    def acquire(cls, job_id: str) -> Tuple[bool, Optional[str], str]:
        """
        Attempts to acquire the global heavy GPU lease for job_id.
        Returns: (success: bool, token: Optional[str], message: str)
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gpu_lease WHERE resource = ?", (cls.RESOURCE,))
            row = cursor.fetchone()
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            if row and row["token"]:
                # Check if expired
                timeout = settings.gpu_lease.lease_timeout_seconds
                hb_str = row["heartbeat_at"] or row["acquired_at"]
                if hb_str:
                    hb_dt = datetime.fromisoformat(hb_str)
                    if (now - hb_dt).total_seconds() <= timeout:
                        # Lease currently active by someone else
                        if row["owner_job_id"] == job_id:
                            return True, row["token"], "Already acquired by this job"
                        return False, None, f"GPU lease currently held by job {row['owner_job_id']}"

            # Acquire or take over expired lease
            token = str(uuid.uuid4())
            cursor.execute("""
            UPDATE gpu_lease
            SET owner_job_id = ?, token = ?, acquired_at = ?, heartbeat_at = ?
            WHERE resource = ?
            """, (job_id, token, now_iso, now_iso, cls.RESOURCE))
            conn.commit()
            return True, token, "Lease acquired successfully"
        finally:
            conn.close()

    @classmethod
    def heartbeat(cls, token: str) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            UPDATE gpu_lease
            SET heartbeat_at = ?
            WHERE resource = ? AND token = ?
            """, (now_iso, cls.RESOURCE, token))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def release(cls, token: str) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE gpu_lease
            SET owner_job_id = NULL, token = NULL, acquired_at = NULL, heartbeat_at = NULL
            WHERE resource = ? AND token = ?
            """, (cls.RESOURCE, token))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
