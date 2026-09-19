"""FFmpeg Utilities for Deterministic Assembly, Trimming, Audio Mixing, and Encoding."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_ffmpeg_path() -> str:
    """Locates the FFmpeg executable on the machine."""
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    # Check known winget installation directory on this machine
    winget_candidate = Path(
        r"C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
    )
    if winget_candidate.exists():
        return str(winget_candidate)

    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Locates the FFprobe executable on the machine."""
    which_ffprobe = shutil.which("ffprobe")
    if which_ffprobe:
        return which_ffprobe

    winget_candidate = Path(
        r"C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"
    )
    if winget_candidate.exists():
        return str(winget_candidate)

    return "ffprobe"


def run_ffmpeg(cmd_args: List[str], timeout_s: int = 180) -> Tuple[int, str, str]:
    """Executes FFmpeg with the provided arguments and captures stdout/stderr."""
    ffmpeg_exe = get_ffmpeg_path()
    full_cmd = [ffmpeg_exe] + cmd_args

    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        proc.kill()
        raise TimeoutError(f"FFmpeg command timed out after {timeout_s}s: {' '.join(full_cmd)}")


def format_time_srt(seconds: float) -> str:
    """Formats seconds into SRT timestamp format: HH:MM:SS,mmm."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def create_srt_file(subtitles: List[Dict[str, Any]], output_path: str) -> str:
    """Generates an SRT subtitle file from subtitle entries.

    Each entry must contain: 'start_s', 'end_s', 'text', and optionally 'character_name'.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    lines = []
    for idx, entry in enumerate(subtitles, 1):
        start_ts = format_time_srt(float(entry["start_s"]))
        end_ts = format_time_srt(float(entry["end_s"]))
        char = entry.get("character_name")
        text = f"{char}: {entry['text']}" if char else entry["text"]
        lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path
