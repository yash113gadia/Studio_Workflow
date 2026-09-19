import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from app.core.database import get_connection
from app.core.config import settings
from app.core.models import JobRecord, JobStatus, JobCreate


class DurableQueue:

    @classmethod
    def enqueue(cls, job_in: JobCreate) -> JobRecord:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()
            payload_str = json.dumps(job_in.payload_json)

            cursor.execute("""
            INSERT INTO render_jobs (
                id, project_id, episode_id, shot_id, kind, priority, status,
                payload_json, attempt, max_attempts, backend, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (
                job_id, job_in.project_id, job_in.episode_id, job_in.shot_id,
                job_in.kind.value, job_in.priority, JobStatus.PENDING.value,
                payload_str, job_in.max_attempts, job_in.backend, now
            ))
            conn.commit()
            return cls.get_job(job_id)
        finally:
            conn.close()

    @classmethod
    def get_job(cls, job_id: str) -> Optional[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM render_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return cls._row_to_record(row)
        finally:
            conn.close()

    @classmethod
    def list_jobs(cls, project_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM render_jobs WHERE 1=1"
            params = []
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [cls._row_to_record(r) for r in rows]
        finally:
            conn.close()

    @classmethod
    def start_job(cls, job_id: str) -> Optional[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            UPDATE render_jobs
            SET status = ?, started_at = ?, heartbeat_at = ?, attempt = attempt + 1
            WHERE id = ? AND status IN (?, ?)
            """, (JobStatus.RUNNING.value, now, now, job_id, JobStatus.PENDING.value, JobStatus.FAILED_RETRYABLE.value))
            conn.commit()
            return cls.get_job(job_id)
        finally:
            conn.close()

    @classmethod
    def heartbeat(cls, job_id: str) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            UPDATE render_jobs
            SET heartbeat_at = ?
            WHERE id = ? AND status = ?
            """, (now, job_id, JobStatus.RUNNING.value))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def complete_job(cls, job_id: str, output_asset_ids: Optional[List[str]] = None) -> Optional[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            out_json = json.dumps(output_asset_ids or [])
            cursor.execute("""
            UPDATE render_jobs
            SET status = ?, finished_at = ?, output_asset_ids = ?
            WHERE id = ?
            """, (JobStatus.SUCCEEDED.value, now, out_json, job_id))
            conn.commit()
            return cls.get_job(job_id)
        finally:
            conn.close()

    @classmethod
    def fail_job(cls, job_id: str, error_class: str, error_message: str, retryable: bool = True) -> Optional[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            job = cls.get_job(job_id)
            if not job:
                return None

            new_status = JobStatus.FAILED_RETRYABLE if (retryable and job.attempt < job.max_attempts) else JobStatus.FAILED_FINAL
            cursor.execute("""
            UPDATE render_jobs
            SET status = ?, finished_at = ?, error_class = ?, error_message = ?
            WHERE id = ?
            """, (new_status.value, now, error_class, error_message, job_id))
            conn.commit()
            return cls.get_job(job_id)
        finally:
            conn.close()

    @classmethod
    def cancel_job(cls, job_id: str) -> Optional[JobRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            UPDATE render_jobs
            SET status = ?, finished_at = ?
            WHERE id = ? AND status NOT IN (?, ?)
            """, (JobStatus.CANCELLED.value, now, job_id, JobStatus.SUCCEEDED.value, JobStatus.CANCELLED.value))
            conn.commit()
            return cls.get_job(job_id)
        finally:
            conn.close()

    @classmethod
    def recover_stale_running_jobs(cls) -> int:
        """
        Recovers jobs that were left in RUNNING status without heartbeat (e.g. following process crash).
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM render_jobs WHERE status = ?", (JobStatus.RUNNING.value,))
            rows = cursor.fetchall()
            now = datetime.now(timezone.utc)
            timeout = settings.queue.heartbeat_timeout_seconds
            recovered = 0

            for row in rows:
                hb_str = row["heartbeat_at"] or row["started_at"]
                is_stale = True
                if hb_str:
                    hb_dt = datetime.fromisoformat(hb_str)
                    if (now - hb_dt).total_seconds() <= timeout:
                        is_stale = False

                if is_stale:
                    attempt = row["attempt"]
                    max_attempts = row["max_attempts"]
                    new_status = JobStatus.FAILED_RETRYABLE.value if attempt < max_attempts else JobStatus.FAILED_FINAL.value
                    cursor.execute("""
                    UPDATE render_jobs
                    SET status = ?, error_class = 'ProcessCrashOrHeartbeatTimeout',
                        error_message = 'Job recovered from stale RUNNING state upon studio restart'
                    WHERE id = ?
                    """, (new_status, row["id"]))
                    recovered += 1

            conn.commit()
            return recovered
        finally:
            conn.close()

    @classmethod
    def _row_to_record(cls, row) -> JobRecord:
        payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        assets = json.loads(row["output_asset_ids"]) if row["output_asset_ids"] else []
        return JobRecord(
            id=row["id"],
            project_id=row["project_id"],
            episode_id=row["episode_id"],
            shot_id=row["shot_id"],
            kind=row["kind"],
            priority=row["priority"],
            status=JobStatus(row["status"]),
            payload_json=payload,
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            backend=row["backend"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            heartbeat_at=row["heartbeat_at"],
            error_class=row["error_class"],
            error_message=row["error_message"],
            output_asset_ids=assets
        )
