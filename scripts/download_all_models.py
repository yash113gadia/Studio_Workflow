"""
Preeti Studio — Staged Model Downloader v2
Downloads all missing model weights one by one.
Resumes partial downloads from HuggingFace cache.
"""
import os
import sys
import shutil
import time
from pathlib import Path
from huggingface_hub import hf_hub_download, snapshot_download

STUDIO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = STUDIO_ROOT / "models"
SAFETY_BUFFER_GB = 80

def free_gb():
    return shutil.disk_usage("C:\\").free / (1024**3)

def dl(repo_id, filename, local_dir, subfolder=None, desc=""):
    """Download a single file from HuggingFace."""
    full = f"{subfolder}/{filename}" if subfolder else filename
    target = Path(local_dir) / full
    if target.exists() and target.stat().st_size > 1000:
        sz = target.stat().st_size / (1024**2)
        print(f"  [SKIP] {desc}: already exists ({sz:.1f} MB)")
        return True
    
    print(f"  [DL] {desc}")
    print(f"       {repo_id}/{full}")
    print(f"       Free: {free_gb():.1f} GB", flush=True)
    
    if free_gb() < SAFETY_BUFFER_GB + 1:
        print(f"  [FAIL] Disk too low!")
        return False
    try:
        path = hf_hub_download(repo_id=repo_id, filename=full, local_dir=str(local_dir))
        sz = os.path.getsize(path) / (1024**2)
        print(f"  [OK] {sz:.1f} MB -> {path}", flush=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {e}", flush=True)
        return False

def snap(repo_id, local_dir, allow=None, ignore=None, desc=""):
    """Download a model repo snapshot."""
    print(f"  [DL] {desc}")
    print(f"       {repo_id}")
    print(f"       Free: {free_gb():.1f} GB", flush=True)
    
    if free_gb() < SAFETY_BUFFER_GB + 1:
        print(f"  [FAIL] Disk too low!")
        return False
    try:
        path = snapshot_download(repo_id=repo_id, local_dir=str(local_dir),
                                 allow_patterns=allow, ignore_patterns=ignore)
        print(f"  [OK] -> {path}", flush=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {e}", flush=True)
        return False

R = {}  # results

# ===== STAGE C: VIDEO =====
print(f"\n{'='*60}\nSTAGE C — VIDEO\n{'='*60}", flush=True)

H3 = "DeepBeepMeep/MiniMax-H3"
H3D = MODELS_DIR / "video" / "minimax_h3"
H3D.mkdir(parents=True, exist_ok=True)

for sf, fn, d in [
    ("Qwen3-VL-32B-Instruct", "qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf", "H3 TextEnc GGUF Q4"),
    (None, "MiniMax-H3-video_vae_fp16.safetensors", "H3 Video VAE"),
    (None, "MiniMax-H3-audio_vae_fp32.safetensors", "H3 Audio VAE"),
    ("loras", "minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors", "H3 FL2V Turbo LoRA"),
    ("loras", "minimax_h3_lightx2v_ref2v_turbo_4step_alpha8_v0.1_bf16.safetensors", "H3 Ref2V Turbo LoRA"),
    (None, "minimax_h3_ref2va_33b_int8_convrot.safetensors", "H3 Ref2VA INT8 Diffusion"),
]:
    R[d] = dl(H3, fn, H3D, sf, d)

WAN = "DeepBeepMeep/Wan2.1"
WAND = MODELS_DIR / "video" / "wan21"
WAND.mkdir(parents=True, exist_ok=True)

for sf, fn, d in [
    (None, "wan2.1_image2video_480p_14B_quanto_int8.safetensors", "Wan2.1 I2V 480p INT8"),
    ("vae", "wan2.1_vae.safetensors", "Wan2.1 VAE"),
]:
    R[d] = dl(WAN, fn, WAND, sf, d)

# ===== STAGE D: AUDIO =====
print(f"\n{'='*60}\nSTAGE D — AUDIO\n{'='*60}", flush=True)

CBD = MODELS_DIR / "tts" / "chatterbox"
CBD.mkdir(parents=True, exist_ok=True)
R["Chatterbox TTS"] = snap("resemble-ai/chatterbox", CBD, desc="Chatterbox TTS")

MTD = MODELS_DIR / "lipsync" / "musetalk"
MTD.mkdir(parents=True, exist_ok=True)
R["MuseTalk 1.5"] = snap("TMElyralab/MuseTalk", MTD, desc="MuseTalk 1.5")

ASD = MODELS_DIR / "audio" / "ace_step"
ASD.mkdir(parents=True, exist_ok=True)
R["ACE-Step"] = snap("ace-step/ACE-Step-v1-3.5B", ASD, desc="ACE-Step Music")

FLD = MODELS_DIR / "audio" / "hunyuan_foley"
FLD.mkdir(parents=True, exist_ok=True)
R["Foley XL"] = snap("tencent/HunyuanVideo-Foley", FLD,
                      allow=["*xl*", "*.json", "*.yaml", "*.txt", "*.md"],
                      ignore=["*xxl*", "*XXL*"],
                      desc="HunyuanVideo-Foley XL")

# ===== STAGE E: UPSCALER =====
print(f"\n{'='*60}\nSTAGE E — UPSCALER\n{'='*60}", flush=True)

FVD = MODELS_DIR / "upscalers" / "flashvsr"
FVD.mkdir(parents=True, exist_ok=True)
R["FlashVSR"] = snap("JeffWang987/FlashVSR", FVD, desc="FlashVSR")

# ===== STAGE X: EXPERIMENTAL =====
print(f"\n{'='*60}\nSTAGE X — LTX-2.5\n{'='*60}", flush=True)

LTXD = MODELS_DIR / "video" / "ltx25"
LTXD.mkdir(parents=True, exist_ok=True)
R["LTX-2.5"] = dl("Lightricks/LTX-Video-2.5", "ltx-video-2b-v0.9.5.safetensors", LTXD, desc="LTX-2.5")

# ===== SUMMARY =====
print(f"\n{'='*60}\nRESULTS\n{'='*60}")
print(f"Disk free: {free_gb():.1f} GB")
for k, v in R.items():
    print(f"  {'OK' if v else 'FAIL':>4}  {k}")
ok = sum(1 for v in R.values() if v)
fail = sum(1 for v in R.values() if not v)
print(f"\n{ok} succeeded, {fail} failed")
