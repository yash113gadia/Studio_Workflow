"""
Preeti Studio — Autonomous Video Generator CLI
Generates a complete vertical video (1080x1920) from a text script or story.
Runs the full autonomous pipeline: Beats -> Shots -> Voices -> Foley -> Music -> Master Assembly -> Subtitles.
"""
import os
import sys
import argparse
import time
from pathlib import Path

# Add studio root to path
STUDIO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDIO_ROOT))

# Safe Windows UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.core.creator_mode import CreatorModeEngine, CreatorScriptInput


DEFAULT_SCRIPT = """
SCENE 1: EXT. NEO-MUMBAI RAINY ALLEYWAY - NIGHT
Rain glistens on the neon-lit asphalt. STEAM rises from a street vendor's cart.
DIYA (24), sharp-eyed and wearing a sleek high-collar cyber jacket, walks quickly through the alleyway, looking over her shoulder.

DIYA
(whispering urgently)
We don't have much time. They've already breached the mainframe.

SCENE 2: INT. HIDDEN ROOFTOP HAVEN - CONTINUOUS
A door slams shut. Diya enters a dimly lit room glowing with holographic displays.
She pulls a glowing quantum drive from her pocket and plugs it into the terminal.

DIYA
(smiling with relief)
The encrypted signal is locked. The broadcast begins now.
"""


def main():
    parser = argparse.ArgumentParser(description="Preeti Studio — Autonomous Video Generator")
    parser.add_argument("--title", type=str, default="The Cipher of Neo-Mumbai", help="Video / Episode Title")
    parser.add_argument("--script", type=str, default=None, help="Raw script text or path to .txt file")
    parser.add_argument("--duration", type=float, default=30.0, help="Target duration in seconds")
    parser.add_argument("--genre", type=str, default="cyberpunk_thriller", help="Genre (e.g. suspense, romance, action)")
    parser.add_argument("--aspect", type=str, default="9:16", help="Aspect ratio (9:16 or 16:9)")
    parser.add_argument("--open", action="store_true", default=True, help="Open finished video in media player")
    args = parser.parse_args()

    script_text = args.script
    if script_text and Path(script_text).exists():
        with open(script_text, "r", encoding="utf-8") as f:
            script_text = f.read()
    elif not script_text:
        script_text = DEFAULT_SCRIPT

    print("\n" + "=" * 80)
    print("PREETI STUDIO -- AUTONOMOUS VERTICAL VIDEO GENERATION PIPELINE")
    print(f"Title:           {args.title}")
    print(f"Target Duration: {args.duration:.1f} seconds")
    print(f"Aspect Ratio:    {args.aspect} (1080x1920)")
    print(f"Genre:           {args.genre}")
    print("=" * 80)

    input_data = CreatorScriptInput(
        title=args.title,
        raw_script_text=script_text,
        target_duration_s=args.duration,
        genre=args.genre,
        aspect_ratio=args.aspect,
    )

    t0 = time.time()
    print("\n[1/7] Normalizing story beats & extracting entities...")
    print("[2/7] Generating shot routing plan (H3 Generative / SCAIL Motion / 2.5D Camera)...")
    print("[3/7] Synthesizing multilingual dialogue & voice performance...")
    print("[4/7] Generating synchronized foley sound effects...")
    print("[5/7] Composing soundtrack & applying dialogue ducking (-12dB)...")
    print("[6/7] Master post assembly (EBU R128 loudness, 1080x1920 render, SRT subtitles)...")
    print("[7/7] Generating multi-platform thumbnails & cryptographic provenance sidecar...\n")

    # Run the autonomous engine
    package = CreatorModeEngine.execute_pipeline(input_data, mock_mode=False)

    total_time = time.time() - t0

    print("=" * 80)
    print("SUCCESS: VIDEO GENERATION COMPLETE!")
    print("=" * 80)
    print(f"Master Video:        {package.master_video_path}")
    print(f"Subtitles (SRT):     {package.subtitles_srt_path}")
    print(f"Total Video Runtime: {package.total_duration_s:.1f} seconds")
    print(f"Generation Time:     {total_time:.1f} seconds")
    print(f"Provenance Sidecar:  {package.provenance_sidecar_path}")
    print(f"Thumbnails Exported: {len(package.thumbnail_variants)} variants")
    print("=" * 80)

    if args.open and os.path.exists(package.master_video_path):
        print(f"\nLaunching video: {package.master_video_path}")
        os.system(f'start "" "{package.master_video_path}"')

    return 0


if __name__ == "__main__":
    sys.exit(main())
