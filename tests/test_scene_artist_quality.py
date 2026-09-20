from unittest.mock import patch

import pytest
from PIL import Image

from app.core.scene_artist import build_ai_prompt, render_cinematic_keyframe, render_shot_video_clip


def test_prompt_preserves_full_action_without_invented_setting():
    action = "A farmer harvests ripe wheat. " * 10 + "A dog waits beside the gate."
    prompt = build_ai_prompt("Harvest", "EXT. FIELD - DAY", action, "Maya", "Hello", "drama", "wide")
    assert action in prompt
    assert "EXT. FIELD - DAY" in prompt
    for unwanted in ("cyberpunk", "holographic", "coat", "observatory", "wet skin", "rain"):
        assert unwanted not in prompt


def test_failure_does_not_create_fake_image(tmp_path):
    out = tmp_path / "frame.jpg"
    with patch("app.core.scene_artist.generate_flux_ai_image", return_value=False) as generate:
        with pytest.raises(RuntimeError, match="keyframe generation failed"):
            render_cinematic_keyframe("Harvest", "FIELD", "Maya", None, "drama", 1, str(out))
    assert not out.exists()
    assert generate.call_args.kwargs["steps"] == 4
    assert generate.call_args.kwargs["timeout_s"] >= 600


def test_actual_small_ffmpeg_render(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (240, 160), (50, 120, 170)).save(source)
    out = tmp_path / "shot.mp4"
    assert render_shot_video_clip(str(source), str(out), duration_s=0.5, fps=12, width=96, height=160)
    assert out.stat().st_size > 1000
