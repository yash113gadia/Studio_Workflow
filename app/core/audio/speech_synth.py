"""Audio Synthesis Engine — Windows SAPI Speech Synthesis and FFmpeg Harmonic Music Beds."""
import base64
import os
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.core.post.ffmpeg_utils import get_ffmpeg_path, run_ffmpeg


def synthesize_speech(text: str, output_wav_path: str, rate: int = 0, voice_index: int = 0) -> bool:
    """Synthesizes human speech from text into a WAV file using Windows Speech Synthesis."""
    if not text or not text.strip():
        return False

    out_file = str(Path(output_wav_path).resolve())
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # Sanitize text for speech engine
    clean_text = text.replace("\n", " ").strip()
    ps_text = clean_text.replace("'", "''")
    ps_path = out_file.replace("'", "''")
    if not clean_text:
        return False

    ps_code = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {int(rate)}
$voices = @($synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }})
if ($voices.Count -gt 0) {{ $synth.SelectVoice($voices[{int(voice_index)} % $voices.Count].VoiceInfo.Name) }}
$synth.SetOutputToWaveFile('{ps_path}')
$synth.Speak('{ps_text}')
$synth.Dispose()
"""
    try:
        encoded = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=25,
        )
        if res.returncode == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            return True
    except Exception:
        pass

    return False


def assemble_speech_timeline(shots, output_path: str, total_duration: float) -> bool:
    """Place each spoken line at its shot start, preserving measured speech speed."""
    import wave
    import tempfile
    sample_rate = 24000
    timeline = bytearray(round(total_duration * sample_rate) * 2)
    cursor = 0.0
    has_speech = False
    for shot in shots:
        source = shot.get("speech_path")
        if source:
            with tempfile.TemporaryDirectory() as tmp:
                normalized = str(Path(tmp) / "speech.wav")
                code, _, err = run_ffmpeg(["-y", "-i", source, "-ar", str(sample_rate),
                                           "-ac", "1", "-c:a", "pcm_s16le", normalized])
                if code:
                    raise RuntimeError(f"Cannot normalize speech: {err[-500:]}")
                with wave.open(normalized, "rb") as wav:
                    data = wav.readframes(wav.getnframes())
            start = round((cursor + 0.3) * sample_rate) * 2
            if start + len(data) > len(timeline):
                raise RuntimeError("Speech exceeds the planned timeline")
            timeline[start:start + len(data)] = data
            has_speech = True
        cursor += shot["duration_s"]
    if has_speech:
        with wave.open(output_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(timeline)
    return has_speech


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
