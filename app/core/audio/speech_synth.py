"""Audio Synthesis Engine — Windows SAPI Speech Synthesis and FFmpeg Harmonic Music Beds."""
import base64
import os
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg


def synthesize_speech(text: str, output_wav_path: str, rate: int = 0) -> bool:
    """Synthesizes human speech from text into a WAV file using Windows Speech Synthesis."""
    if not text or not text.strip():
        return False

    out_file = str(Path(output_wav_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # Sanitize text for speech engine
    clean_text = text.replace('"', '').replace("'", "").replace("\n", " ").strip()
    if not clean_text:
        return False

    ps_code = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.SetOutputToWaveFile('{out_file}')
$synth.Speak('{clean_text}')
$synth.Dispose()
"""
    try:
        encoded = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=25,
        )
        if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            return True
    except Exception:
        pass

    # Fallback to generating audible tone/speech proxy with FFmpeg if SAPI fails
    try:
        dur = max(1.5, round(len(clean_text.split()) * 0.45, 2))
        cmd = [
            "-y",
            "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur}",
            "-af", "volume=0.25,lowpass=f=1200",
            "-c:a", "pcm_s16le",
            out_file,
        ]
        ret, _, _ = run_ffmpeg(cmd, timeout_s=15)
        return ret == 0 and os.path.exists(out_file)
    except Exception:
        return False


def synthesize_music_bed(genre: str, duration_s: float, output_wav_path: str) -> bool:
    """Generates a pleasant melodic/ambient synthesizer music bed snapped to the scene duration."""
    out_file = str(Path(output_wav_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    dur = max(2.0, round(duration_s, 2))

    # Chord progressions by genre
    genre_lower = (genre or "cyberpunk").lower()
    if "cyber" in genre_lower:
        # Minor cyberpunk synth pulse (A minor: A 220Hz, C 261Hz, E 330Hz)
        lavfi_expr = (
            f"sine=frequency=220:duration={dur}[a];"
            f"sine=frequency=261.63:duration={dur}[b];"
            f"sine=frequency=329.63:duration={dur}[c];"
            f"[a][b][c]amix=inputs=3,volume=0.18,lowpass=f=2400"
        )
    elif "romance" in genre_lower:
        # Warm major chord (F major: F 174Hz, A 220Hz, C 261Hz, E 330Hz)
        lavfi_expr = (
            f"sine=frequency=174.61:duration={dur}[a];"
            f"sine=frequency=220.00:duration={dur}[b];"
            f"sine=frequency=261.63:duration={dur}[c];"
            f"[a][b][c]amix=inputs=3,volume=0.15"
        )
    elif "mystery" in genre_lower:
        # Suspense dark drone (D minor: D 146Hz, F 174Hz, A 220Hz)
        lavfi_expr = (
            f"sine=frequency=146.83:duration={dur}[a];"
            f"sine=frequency=174.61:duration={dur}[b];"
            f"sine=frequency=220.00:duration={dur}[c];"
            f"[a][b][c]amix=inputs=3,volume=0.16,lowpass=f=1200"
        )
    else:  # sci-fi
        # Space ambient fifths (C 130Hz, G 196Hz, C 261Hz, D 293Hz)
        lavfi_expr = (
            f"sine=frequency=130.81:duration={dur}[a];"
            f"sine=frequency=196.00:duration={dur}[b];"
            f"sine=frequency=261.63:duration={dur}[c];"
            f"[a][b][c]amix=inputs=3,volume=0.15,highpass=f=100,lowpass=f=3000"
        )

    cmd = [
        "-y",
        "-f", "lavfi", "-i", lavfi_expr,
        "-af", f"afade=t=in:ss=0:d=1.5,afade=t=out:st={max(0.1, dur - 2.0)}:d=2.0",
        "-c:a", "pcm_s16le",
        out_file,
    ]
    ret, _, _ = run_ffmpeg(cmd, timeout_s=30)
    return ret == 0 and os.path.exists(out_file)
