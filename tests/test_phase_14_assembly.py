"""Acceptance Test Suite for Phase 14: 2.5D Renderer and Deterministic Post Assembly."""
import json
import os
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_connection, init_db
from app.core.models import ProjectCreate, ProjectKind
from app.core.projects import ProjectManager
from app.core.post.ffmpeg_utils import create_srt_file, format_time_srt, get_ffmpeg_path, run_ffmpeg
from app.core.post.renderer_25d import (
    Motion25DType,
    OverlayEffectType,
    Render25DRequest,
    Render25DResponse,
    Renderer25D,
)
from app.core.post.assembly_engine import (
    AssemblyEngine,
    AssemblyRequest,
    AssemblyResponse,
    ShotClipInput,
    SubtitleEntry,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes fresh database state."""
    init_db()
    yield


client = TestClient(app)


def create_dummy_png(path: str, width: int = 480, height: int = 864):
    """Creates a valid minimal PNG image file using FFmpeg."""
    ffmpeg = get_ffmpeg_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = [
        "-f", "lavfi",
        "-i", f"color=c=navy:s={width}x{height}:d=1",
        "-frames:v", "1",
        "-y", path,
    ]
    code, stdout, stderr = run_ffmpeg(cmd)
    assert code == 0, f"Failed to create dummy PNG: {stderr}"


def create_dummy_mp4(path: str, duration_s: float = 2.0, width: int = 480, height: int = 864):
    """Creates a valid minimal MP4 video file using FFmpeg."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = [
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_s}:size={width}x{height}:rate=24",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-y", path,
    ]
    code, stdout, stderr = run_ffmpeg(cmd)
    assert code == 0, f"Failed to create dummy MP4: {stderr}"


def create_dummy_wav(path: str, duration_s: float = 2.0):
    """Creates a valid minimal WAV audio file using FFmpeg."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = [
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_s}",
        "-c:a", "pcm_s16le",
        "-y", path,
    ]
    code, stdout, stderr = run_ffmpeg(cmd)
    assert code == 0, f"Failed to create dummy WAV: {stderr}"


def test_phase_14_srt_formatting_and_file_creation(tmp_path):
    """Verifies SRT timestamp formatting and file generation."""
    assert format_time_srt(0.0) == "00:00:00,000"
    assert format_time_srt(65.5) == "00:01:05,500"

    subtitles = [
        {"start_s": 0.5, "end_s": 2.0, "text": "Hello, Vikram.", "character_name": "Maya"},
        {"start_s": 2.2, "end_s": 4.0, "text": "We need to leave now.", "character_name": "Vikram"},
    ]
    srt_out = str(tmp_path / "test.srt")
    created_path = create_srt_file(subtitles, srt_out)
    assert os.path.exists(created_path)

    with open(created_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Maya: Hello, Vikram." in content
    assert "00:00:00,500 --> 00:00:02,000" in content
    assert "Vikram: We need to leave now." in content


def test_phase_14_renderer_25d_cheap_shot(tmp_path):
    """Verifies: 2.5D cheap-shot engine generates camera motion with zero diffusion cost."""
    img_path = str(tmp_path / "keyframe_maya.png")
    create_dummy_png(img_path)

    project = ProjectManager.create_project(
        ProjectCreate(
            name="2.5D Test Project",
            kind=ProjectKind.SERIES,
            description="Testing 2.5D renderer",
        )
    )

    req = Render25DRequest(
        project_id=project.id,
        image_path=img_path,
        duration_s=2.0,
        fps=24,
        width=480,
        height=864,
        motion_type=Motion25DType.PUSH_IN,
        overlay_effect=OverlayEffectType.PARTICLE_DUST,
        depth_parallax=True,
        output_path=str(tmp_path / "render_push_in.mp4"),
    )

    res = Renderer25D.render(req, mock_mode=False)
    assert res.output_video_path is not None
    assert os.path.exists(res.output_video_path)
    assert res.duration_s == 2.0
    assert res.resolution == "480x864"
    assert res.motion_type == "push_in"
    assert res.overlay_effect == "particle_dust"
    assert res.parallax_enabled is True
    assert res.diffusion_cost == 0.0  # Zero diffusion cost!

    # Verify video file is non-empty
    assert os.path.getsize(res.output_video_path) > 1000


def test_phase_14_renderer_25d_pan_and_light_leak(tmp_path):
    """Verifies: Pan-left camera motion with light-leak atmospheric overlay."""
    img_path = str(tmp_path / "keyframe_vikram.png")
    create_dummy_png(img_path)

    req = Render25DRequest(
        project_id="PROJ_25D_PAN",
        image_path=img_path,
        duration_s=1.5,
        fps=24,
        motion_type=Motion25DType.PAN_LEFT,
        overlay_effect=OverlayEffectType.LIGHT_LEAK,
        output_path=str(tmp_path / "render_pan_left.mp4"),
    )

    res = Renderer25D.render(req, mock_mode=False)
    assert os.path.exists(res.output_video_path)
    assert res.motion_type == "pan_left"
    assert res.overlay_effect == "light_leak"


def test_phase_14_post_assembly_trims_and_master_encode(tmp_path):
    """Verifies: FFmpeg assembly performs exact trims, 1080x1920 encode, and sidecar creation."""
    project = ProjectManager.create_project(
        ProjectCreate(
            name="Assembly Test Project",
            kind=ProjectKind.SERIES,
            description="Testing deterministic post assembly",
        )
    )

    shot1_path = str(tmp_path / "shot_01.mp4")
    shot2_path = str(tmp_path / "shot_02.mp4")
    dialogue_path = str(tmp_path / "dialogue.wav")
    foley_path = str(tmp_path / "foley.wav")
    music_path = str(tmp_path / "music.wav")

    create_dummy_mp4(shot1_path, duration_s=3.0)
    create_dummy_mp4(shot2_path, duration_s=3.0)
    create_dummy_wav(dialogue_path, duration_s=4.0)
    create_dummy_wav(foley_path, duration_s=4.0)
    create_dummy_wav(music_path, duration_s=4.0)

    req = AssemblyRequest(
        project_id=project.id,
        sequence_id="seq_scene_01",
        shots=[
            ShotClipInput(shot_id="shot_01", video_path=shot1_path, in_trim_s=0.5, out_trim_s=2.5),
            ShotClipInput(shot_id="shot_02", video_path=shot2_path, in_trim_s=0.0, out_trim_s=2.0),
        ],
        dialogue_audio_path=dialogue_path,
        foley_audio_path=foley_path,
        music_audio_path=music_path,
        music_ducking_db=-12.0,
        subtitles=[
            SubtitleEntry(start_s=0.2, end_s=1.8, text="Wait, who is there?", character_name="Maya"),
            SubtitleEntry(start_s=2.1, end_s=3.8, text="Stay back!", character_name="Vikram"),
        ],
        burn_subtitles=True,
        target_width=1080,
        target_height=1920,
        output_dir=str(tmp_path / "assembly_out"),
    )

    res = AssemblyEngine.assemble(req, mock_mode=False)

    # 1. Output master video exists and is 1080x1920
    assert os.path.exists(res.master_video_path)
    assert res.resolution == "1080x1920"
    assert res.shots_count == 2
    assert "dialogue" in res.audio_stems
    assert "foley" in res.audio_stems
    assert "music" in res.audio_stems
    assert res.loudness_standard == "EBU_R128_LUFS_-16"

    # 2. Subtitles file exists
    assert res.subtitles_path is not None
    assert os.path.exists(res.subtitles_path)

    # 3. Provenance sidecar exists and contains valid JSON metadata
    assert os.path.exists(res.provenance_sidecar_path)
    with open(res.provenance_sidecar_path, "r", encoding="utf-8") as f:
        sidecar_data = json.load(f)
    assert sidecar_data["sequence_id"] == "seq_scene_01"
    assert sidecar_data["resolution"] == "1080x1920"
    assert sidecar_data["audio_mix"]["music_ducking_db"] == -12.0
    assert len(sidecar_data["shots_assembled"]) == 2


def test_phase_14_post_api_endpoints(tmp_path):
    """Verifies FastAPI REST endpoints for 2.5D rendering and post assembly."""
    img_path = str(tmp_path / "api_keyframe.png")
    create_dummy_png(img_path)

    # Test /api/v1/post/2.5d/render
    render_payload = {
        "project_id": "PROJ_API_TEST",
        "image_path": img_path,
        "duration_s": 1.0,
        "fps": 24,
        "motion_type": "static_subtle",
        "overlay_effect": "fog_mist",
        "output_path": str(tmp_path / "api_25d.mp4"),
    }
    r1 = client.post("/api/v1/post/2.5d/render?mock=false", json=render_payload)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["motion_type"] == "static_subtle"
    assert d1["overlay_effect"] == "fog_mist"
    assert os.path.exists(d1["output_video_path"])

    # Test /api/v1/post/assembly/assemble in mock mode for rapid API validation
    assemble_payload = {
        "project_id": "PROJ_API_TEST",
        "sequence_id": "seq_api_001",
        "shots": [
            {
                "shot_id": "shot_01",
                "video_path": d1["output_video_path"],
                "in_trim_s": 0.0,
                "out_trim_s": 1.0,
            }
        ],
        "burn_subtitles": False,
        "output_dir": str(tmp_path / "api_assembly_out"),
    }
    r2 = client.post("/api/v1/post/assembly/assemble?mock=true", json=assemble_payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["sequence_id"] == "seq_api_001"
    assert d2["resolution"] == "1080x1920"
    assert os.path.exists(d2["master_video_path"])
    assert os.path.exists(d2["provenance_sidecar_path"])
