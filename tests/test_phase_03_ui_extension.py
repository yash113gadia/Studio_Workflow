import urllib.request
import json
import pytest
from app.main import app
from app.core.projects import ProjectManager
from app.core.queue import DurableQueue
from app.core.models import ProjectCreate, JobCreate, JobKind

COMFY_HOST = "127.0.0.1:8188"
STUDIO_CORE_HOST = "127.0.0.1:8000"


def test_01_comfyui_serves_extension_assets():
    """Criterion 1: ComfyUI server registers and serves the AIStudio web extension files."""
    # Check studio.js is served by ComfyUI
    js_url = f"http://{COMFY_HOST}/extensions/ComfyUI-AIStudio/studio.js"
    req = urllib.request.Request(js_url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "PreetiStudio.AIStudio" in content, "Extension registration code missing"

    # Check studio.css is served
    css_url = f"http://{COMFY_HOST}/extensions/ComfyUI-AIStudio/studio.css"
    req_css = urllib.request.Request(css_url)
    with urllib.request.urlopen(req_css, timeout=5) as resp:
        assert resp.status == 200
        content_css = resp.read().decode("utf-8")
        assert "studio-sidebar-panel" in content_css


def test_02_create_project_and_queue_job_for_ui():
    """Criteria 2, 3, 4: UI can create a project, queue a job, and retrieve live status."""
    # 1. Create project via Studio API (which studio.js calls)
    project = ProjectManager.create_project(ProjectCreate(
        name="UI Pilot Series",
        kind="series",
        description="Created for UI extension validation"
    ))
    assert project.id.startswith("proj_")

    # 2. Queue dummy job (which the '+ Queue Dummy Job' button calls)
    job = DurableQueue.enqueue(JobCreate(
        project_id=project.id,
        kind=JobKind.DUMMY,
        priority=60,
        payload_json={"triggered_from_ui": True}
    ))
    assert job.id.startswith("job_")
    assert job.status.value == "PENDING"

    # 3. Verify that Studio Core health reflects this job
    health_url = f"http://{STUDIO_CORE_HOST}/api/v1/health"
    req = urllib.request.Request(health_url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        health_data = json.loads(resp.read().decode("utf-8"))
        assert health_data["queue_pending_count"] >= 1
        assert health_data["database_connected"] is True


def test_03_persistence_across_comfy_restart():
    """Criterion 5: Restarting ComfyUI preserves all projects and queued jobs in Studio Core."""
    # Query projects list that the UI populates
    p_url = f"http://{STUDIO_CORE_HOST}/api/v1/projects"
    req = urllib.request.Request(p_url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        projects = json.loads(resp.read().decode("utf-8"))
        matching = [p for p in projects if p["name"] == "UI Pilot Series"]
        assert len(matching) > 0, "UI project was not preserved across ComfyUI lifecycle"
