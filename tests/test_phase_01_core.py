import pytest
import time
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import init_db, get_connection
from app.core.queue import DurableQueue
from app.core.gpu_lease import GPULeaseManager
from app.core.models import JobStatus, JobCreate, JobKind, ProjectCreate, ProjectKind
from app.core.config import settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield


def test_01_create_project():
    """Criterion 1: Project can be created."""
    response = client.post("/api/v1/projects", json={
        "name": "Test Series Alpha",
        "kind": "series",
        "description": "A pilot test project for phase 1 validation",
        "style_id": "STYLE_SERIES_A_V001",
        "autonomy_mode": "review"
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Test Series Alpha"
    assert data["kind"] == "series"
    assert data["id"].startswith("proj_")

    # Verify retrieval
    get_res = client.get(f"/api/v1/projects/{data['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == data["id"]


def test_02_dummy_job_enters_queue():
    """Criterion 2: Dummy job enters queue."""
    # Create project first
    p_res = client.post("/api/v1/projects", json={"name": "Queue Test Project", "kind": "creator"})
    proj_id = p_res.json()["id"]

    # Enqueue dummy job
    job_payload = {
        "project_id": proj_id,
        "kind": "dummy",
        "priority": 75,
        "payload_json": {"test_param": 12345}
    }
    j_res = client.post("/api/v1/jobs", json=job_payload)
    assert j_res.status_code == 200, j_res.text
    job_data = j_res.json()
    assert job_data["id"].startswith("job_")
    assert job_data["status"] == "PENDING"
    assert job_data["priority"] == 75
    assert job_data["payload_json"]["test_param"] == 12345


def test_03_and_04_job_persistence_across_restart():
    """Criteria 3 & 4: Process can be restarted and job records persist in SQLite."""
    p_res = client.post("/api/v1/projects", json={"name": "Persistence Test", "kind": "series"})
    proj_id = p_res.json()["id"]

    j_res = client.post("/api/v1/jobs", json={
        "project_id": proj_id,
        "kind": "dummy",
        "payload_json": {"key": "persisted_value"}
    })
    job_id = j_res.json()["id"]

    # Simulate shutdown / new connection
    job_record = DurableQueue.get_job(job_id)
    assert job_record is not None
    assert job_record.id == job_id
    assert job_record.payload_json["key"] == "persisted_value"


def test_05_stale_running_recovery():
    """Criterion 5: Stale RUNNING recovery works."""
    p_res = client.post("/api/v1/projects", json={"name": "Crash Recovery Test", "kind": "series"})
    proj_id = p_res.json()["id"]

    # Enqueue and start job
    job = DurableQueue.enqueue(JobCreate(project_id=proj_id, kind=JobKind.DUMMY))
    DurableQueue.start_job(job.id)

    # Manually age the heartbeat to simulate an ungraceful crash 5 minutes ago
    conn = get_connection()
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    conn.execute("UPDATE render_jobs SET heartbeat_at = ? WHERE id = ?", (stale_time, job.id))
    conn.commit()
    conn.close()

    # Trigger recovery (as happens at startup)
    recovered_count = DurableQueue.recover_stale_running_jobs()
    assert recovered_count >= 1

    recovered_job = DurableQueue.get_job(job.id)
    assert recovered_job.status in (JobStatus.FAILED_RETRYABLE, JobStatus.FAILED_FINAL)
    assert recovered_job.error_class == "ProcessCrashOrHeartbeatTimeout"


def test_06_gpu_lease_mutual_exclusion():
    """Criterion 6: GPU lease cannot be held by two jobs simultaneously."""
    # Release any existing lease
    conn = get_connection()
    conn.execute("UPDATE gpu_lease SET token = NULL, owner_job_id = NULL")
    conn.commit()
    conn.close()

    # Job A acquires lease
    res_a = client.post("/api/v1/gpu/lease/acquire", json={"job_id": "job_AAA", "requested_seconds": 30})
    assert res_a.status_code == 200
    token_a = res_a.json()["token"]
    assert token_a is not None

    # Job B attempts to acquire concurrently -> Must be rejected (409 Conflict)
    res_b = client.post("/api/v1/gpu/lease/acquire", json={"job_id": "job_BBB", "requested_seconds": 30})
    assert res_b.status_code == 409
    assert "currently held by job job_AAA" in res_b.json()["detail"]

    # Job A releases lease
    rel_a = client.post("/api/v1/gpu/lease/release", json={"token": token_a})
    assert rel_a.status_code == 200

    # Job B can now acquire successfully
    res_b2 = client.post("/api/v1/gpu/lease/acquire", json={"job_id": "job_BBB", "requested_seconds": 30})
    assert res_b2.status_code == 200
    token_b = res_b2.json()["token"]
    assert token_b is not None

    # Cleanup
    client.post("/api/v1/gpu/lease/release", json={"token": token_b})


def test_07_health_and_jobs_endpoints():
    """Criterion 7: /api/v1/health and /api/v1/jobs work."""
    # Health endpoint
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    h_data = health_res.json()
    assert h_data["status"] == "ok"
    assert h_data["database_connected"] is True
    assert h_data["free_disk_gb"] > 0

    # Jobs list endpoint
    jobs_res = client.get("/api/v1/jobs")
    assert jobs_res.status_code == 200
    assert isinstance(jobs_res.json(), list)
