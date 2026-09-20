"""Standalone WanGP MiniMax H3 Short-Shot Runner Script."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.post.ffmpeg_utils import run_ffmpeg
from app.core.scene_artist import render_shot_video_clip


def main():
    parser = argparse.ArgumentParser(description="WanGP H3 Shot Runner")
    parser.add_argument("--payload", required=True, help="Path to execution payload JSON")
    args = parser.parse_args()

    payload_path = Path(args.payload).resolve()
    if not payload_path.exists():
        print(f"Error: payload file not found: {payload_path}", file=sys.stderr)
        sys.exit(1)

    with open(payload_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    job_id = data.get("job_id", "job_unknown")
    prompt = data.get("prompt", "")
    keyframe_path = data.get("keyframe_path")
    output_path = data.get("output_path")
    profile = data.get("profile", {})

    print(f"Starting WanGP H3 Short-Shot Runner for Job: {job_id}")
    print(f"Prompt: {prompt}")
    print(f"Keyframe: {keyframe_path}")
    print(f"Output: {output_path}")
    print(f"Profile: {profile.get('model_architecture')} at {profile.get('resolution')}, {profile.get('duration_s')}s")

    raise RuntimeError(
        "MiniMax H3 inference is not connected in this adapter. No substitute video was generated. "
        "Use AI actor motion (LTX Video) in the main Studio, or connect WanGP's real inference API."
    )


if __name__ == "__main__":
    main()
