"""
Preeti Studio — Resilient HTTP Range-Resuming Model Downloader
Uses Python standard urllib + ssl with Range resume, retry backoff,
and strict 80 GB disk safety enforcement.
"""
import os
import sys
import time
import json
import ssl
import shutil
import socket
import urllib.request
from pathlib import Path

# Ensure any hung socket drops and retries within 30s
socket.setdefaulttimeout(30)

STUDIO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = STUDIO_ROOT / "models"
SAFETY_BUFFER_GB = 80.0
HF_TOKEN = os.environ.get("HF_TOKEN", "")

STATUS_FILE = MODELS_DIR / "download_manifest.json"

def get_free_disk_gb():
    total, used, free = shutil.disk_usage("C:\\")
    return free / (1024 ** 3)

def load_status():
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_status(status_dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_dict, f, indent=2)

def download_file_resumable(url, destination_path, desc="", token=HF_TOKEN, max_retries=15):
    dest = Path(destination_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    free_gb = get_free_disk_gb()
    if free_gb < SAFETY_BUFFER_GB + 0.5:
        print(f"\n[ABORT] Disk space safety limit reached: {free_gb:.2f} GB free (< {SAFETY_BUFFER_GB} GB required)")
        return False

    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    
    headers = {
        "User-Agent": "PreetiStudio/1.0 (Windows NT 10.0; Win64; x64)",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"\n{'='*75}")
    print(f"MODEL: {desc or dest.name}")
    print(f"TARGET: {dest.relative_to(STUDIO_ROOT) if dest.is_relative_to(STUDIO_ROOT) else dest}")
    print(f"SOURCE: {url}")
    print(f"DISK FREE: {free_gb:.2f} GB (Buffer: {SAFETY_BUFFER_GB} GB)")
    print(f"{'='*75}")

    retries = 0
    backoff = 2.0

    while retries < max_retries:
        try:
            req = urllib.request.Request(url, headers=headers)
            current_bytes = dest.stat().st_size if dest.exists() else 0

            if current_bytes > 0:
                req.add_header("Range", f"bytes={current_bytes}-")

            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                code = resp.status
                content_range = resp.headers.get("Content-Range")
                content_len = resp.headers.get("Content-Length")

                if code == 206 and content_range:
                    total_bytes = int(content_range.split("/")[-1])
                    mode = "ab"
                elif code == 200:
                    total_bytes = int(content_len) if content_len else None
                    if current_bytes == total_bytes and total_bytes is not None and total_bytes > 0:
                        print(f"  [ALREADY COMPLETE] Size: {total_bytes / (1024**2):.2f} MB")
                        return True
                    current_bytes = 0
                    mode = "wb"
                else:
                    total_bytes = int(content_len) if content_len else None
                    mode = "ab" if current_bytes > 0 else "wb"

                total_mb_str = f"{total_bytes / (1024**2):.1f} MB" if total_bytes else "unknown"
                print(f"  Streaming: resume from {current_bytes / (1024**2):.1f} MB of {total_mb_str} ...")

                chunk_size = 4 * 1024 * 1024
                t_start = time.time()
                bytes_this_session = 0
                last_print = 0

                with open(dest, mode) as f_out:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        current_bytes += len(chunk)
                        bytes_this_session += len(chunk)

                        now = time.time()
                        if now - last_print >= 1.5:
                            speed = (bytes_this_session / (1024**2)) / max(now - t_start, 0.001)
                            if total_bytes:
                                pct = (current_bytes / total_bytes) * 100.0
                                rem_s = (total_bytes - current_bytes) / max(bytes_this_session / max(now - t_start, 0.001), 1)
                                eta_str = f"{int(rem_s // 60)}m {int(rem_s % 60):02d}s"
                                print(f"  [{pct:5.1f}%] {current_bytes/(1024**2):8.1f} / {total_bytes/(1024**2):.1f} MB ({speed:5.1f} MB/s) ETA: {eta_str}", flush=True)
                            else:
                                print(f"  {current_bytes/(1024**2):8.1f} MB ({speed:5.1f} MB/s)", flush=True)
                            last_print = now

                if total_bytes and current_bytes < total_bytes:
                    raise IOError(f"Incomplete download: received {current_bytes} of {total_bytes} bytes")

                final_mb = current_bytes / (1024 ** 2)
                elapsed = time.time() - t_start
                avg_speed = (bytes_this_session / (1024**2)) / max(elapsed, 0.001)
                print(f"  [SUCCESS] {final_mb:.2f} MB verified in {elapsed:.1f}s ({avg_speed:.2f} MB/s)")
                return True

        except Exception as e:
            retries += 1
            current_bytes = dest.stat().st_size if dest.exists() else 0
            print(f"\n  [WARN] Network glitch at {current_bytes / (1024**2):.1f} MB: {e}")
            if retries < max_retries:
                wait_time = min(backoff * (1.5 ** retries), 30)
                print(f"  [RETRY {retries}/{max_retries}] Resuming in {wait_time:.1f}s ...", flush=True)
                time.sleep(wait_time)
            else:
                print(f"  [ERROR] Max retries exceeded for {desc}")
                return False

    return False


def run_stage_downloads():
    status = load_status()

    DOWNLOAD_PLAN = [
        # --- STAGE C1: MiniMax H3 (Already 100% Downloaded!) ---
        {
            "id": "h3_audio_vae",
            "stage": "Stage C (Video - H3 Audio VAE)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/MiniMax-H3-audio_vae_fp32.safetensors",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "MiniMax-H3-audio_vae_fp32.safetensors",
            "desc": "MiniMax H3 Audio VAE FP32 (577 MB)",
        },
        {
            "id": "h3_video_vae",
            "stage": "Stage C (Video - H3 Video VAE)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/MiniMax-H3-video_vae_fp16.safetensors",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "MiniMax-H3-video_vae_fp16.safetensors",
            "desc": "MiniMax H3 Video VAE FP16 (4.9 GB)",
        },
        {
            "id": "h3_turbo_fl2v",
            "stage": "Stage C (Video - H3 Turbo LoRA)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "loras" / "minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors",
            "desc": "MiniMax H3 FL2V Turbo 4-Step LoRA (1.3 GB)",
        },
        {
            "id": "h3_turbo_ref2v",
            "stage": "Stage C (Video - H3 Turbo Ref LoRA)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/minimax_h3_lightx2v_ref2v_turbo_4step_alpha8_v0.1_bf16.safetensors",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "loras" / "minimax_h3_lightx2v_ref2v_turbo_4step_alpha8_v0.1_bf16.safetensors",
            "desc": "MiniMax H3 Ref2V Turbo 4-Step LoRA (1.3 GB)",
        },
        {
            "id": "h3_q4_text_encoder",
            "stage": "Stage C (Video - H3 Low-VRAM Text Encoder)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/Qwen3-VL-32B-Instruct/qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "Qwen3-VL-32B-Instruct" / "qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf",
            "desc": "MiniMax H3 Qwen3-VL Text Encoder GGUF Q4_K_M (13.9 GB)",
        },
        {
            "id": "h3_diffusion_pruned_int8",
            "stage": "Stage C (Video - H3 INT8 Diffusion Model)",
            "url": "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/MiniMax-H3-Ref2VA-pruned_int8_convrot.safetensors",
            "dest": MODELS_DIR / "video" / "minimax_h3" / "MiniMax-H3-Ref2VA-pruned_int8_convrot.safetensors",
            "desc": "MiniMax H3 Ref2VA Pruned INT8 ConvRot Diffusion (21.1 GB)",
        },

        # --- STAGE C2: Wan 2.1 / SCAIL-2 (WanGP) ---
        {
            "id": "wan21_vae",
            "stage": "Stage C (SCAIL/Wan - VAE)",
            "url": "https://huggingface.co/DeepBeepMeep/Wan2.1/resolve/main/Wan2.1_VAE.safetensors",
            "dest": MODELS_DIR / "video" / "wan21" / "Wan2.1_VAE.safetensors",
            "desc": "Wan 2.1 Video VAE",
        },
        {
            "id": "scail2_14b_int8",
            "stage": "Stage C (SCAIL/Wan - SCAIL-2 14B INT8)",
            "url": "https://huggingface.co/DeepBeepMeep/Wan2.1/resolve/main/scail2_14B_quanto_mbf16_int8.safetensors",
            "dest": MODELS_DIR / "video" / "wan21" / "scail2_14B_quanto_mbf16_int8.safetensors",
            "desc": "SCAIL-2 14B INT8 Quanto (Controlled character motion transfer)",
        },

        # --- STAGE E: Upscaler (FlashVSR via WanGP) ---
        {
            "id": "flashvsr_transformer",
            "stage": "Stage E (Upscaler - FlashVSR Transformer)",
            "url": "https://huggingface.co/DeepBeepMeep/Wan2.1/resolve/main/FlashVSR/FlashVSR_v1.1_transformer_bf16.safetensors",
            "dest": MODELS_DIR / "upscalers" / "flashvsr" / "FlashVSR_v1.1_transformer_bf16.safetensors",
            "desc": "FlashVSR v1.1 Transformer BF16 (2.7 GB)",
        },
        {
            "id": "flashvsr_tcdecoder",
            "stage": "Stage E (Upscaler - FlashVSR Decoder)",
            "url": "https://huggingface.co/DeepBeepMeep/Wan2.1/resolve/main/FlashVSR/FlashVSR_v1.1_tcdecoder_bf16.safetensors",
            "dest": MODELS_DIR / "upscalers" / "flashvsr" / "FlashVSR_v1.1_tcdecoder_bf16.safetensors",
            "desc": "FlashVSR v1.1 TC Decoder BF16 (86.5 MB)",
        },
        {
            "id": "flashvsr_lq_proj",
            "stage": "Stage E (Upscaler - FlashVSR LQ Proj)",
            "url": "https://huggingface.co/DeepBeepMeep/Wan2.1/resolve/main/FlashVSR/FlashVSR_v1.1_lq_proj_bf16.safetensors",
            "dest": MODELS_DIR / "upscalers" / "flashvsr" / "FlashVSR_v1.1_lq_proj_bf16.safetensors",
            "desc": "FlashVSR v1.1 LQ Projection BF16 (549 MB)",
        },

        # --- STAGE D: Audio (ACE-Step Music) ---
        {
            "id": "acestep_transformer",
            "stage": "Stage D (Audio - ACE-Step 1.5 Music)",
            "url": "https://huggingface.co/ace-step/ACE-Step-v1-3.5B/resolve/main/ace_step_transformer/diffusion_pytorch_model.safetensors",
            "dest": MODELS_DIR / "audio" / "ace_step" / "ace_step_transformer" / "diffusion_pytorch_model.safetensors",
            "desc": "ACE-Step 1.5 Music Transformer Model (6.3 GB)",
        },
        {
            "id": "acestep_dcae",
            "stage": "Stage D (Audio - ACE-Step DCAE)",
            "url": "https://huggingface.co/ace-step/ACE-Step-v1-3.5B/resolve/main/music_dcae_f8c8/diffusion_pytorch_model.safetensors",
            "dest": MODELS_DIR / "audio" / "ace_step" / "music_dcae_f8c8" / "diffusion_pytorch_model.safetensors",
            "desc": "ACE-Step Music DCAE Autoencoder",
        },
        {
            "id": "acestep_vocoder",
            "stage": "Stage D (Audio - ACE-Step Vocoder)",
            "url": "https://huggingface.co/ace-step/ACE-Step-v1-3.5B/resolve/main/music_vocoder/diffusion_pytorch_model.safetensors",
            "dest": MODELS_DIR / "audio" / "ace_step" / "music_vocoder" / "diffusion_pytorch_model.safetensors",
            "desc": "ACE-Step Music Vocoder (197 MB)",
        },

        # --- STAGE X: Experimental (LTX-Video) ---
        {
            "id": "ltx_video_2b",
            "stage": "Stage X (Experimental - LTX Video 2B)",
            "url": "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.5.safetensors",
            "dest": MODELS_DIR / "video" / "ltx25" / "ltx-video-2b-v0.9.5.safetensors",
            "desc": "LTX-Video 2B v0.9.5 Sandbox Model (6.0 GB)",
        },
    ]

    print("\n" + "="*80)
    print("PREETI STUDIO — AUTONOMOUS STAGED MODEL DOWNLOAD ENGINE")
    print(f"Safety Buffer Enforced: >= {SAFETY_BUFFER_GB} GB Free")
    print(f"Current Free Space:     {get_free_disk_gb():.2f} GB")
    print(f"Total Target Models:    {len(DOWNLOAD_PLAN)}")
    print("="*80)

    for i, task in enumerate(DOWNLOAD_PLAN, 1):
        task_id = task["id"]
        desc = f"[{i}/{len(DOWNLOAD_PLAN)}] {task['desc']}"

        if status.get(task_id) == "COMPLETED" and Path(task["dest"]).exists() and Path(task["dest"]).stat().st_size > 1000:
            print(f"\n[SKIP] {desc} — already verified on disk.")
            continue

        print(f"\n>>> Starting Stage: {task['stage']}")
        success = download_file_resumable(
            url=task["url"],
            destination_path=task["dest"],
            desc=desc,
            token=HF_TOKEN
        )

        if success:
            status[task_id] = "COMPLETED"
            status[f"{task_id}_path"] = str(task["dest"])
            status[f"{task_id}_bytes"] = Path(task["dest"]).stat().st_size
            status[f"{task_id}_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_status(status)
        else:
            print(f"\n[STOP] Download halted on {desc}. Will not proceed to subsequent models.")
            break

    print("\n" + "="*80)
    print("DOWNLOAD RUN SUMMARY")
    print(f"Disk Free Space: {get_free_disk_gb():.2f} GB")
    print("="*80)
    for task in DOWNLOAD_PLAN:
        st = status.get(task["id"], "PENDING")
        mark = "[OK]" if st == "COMPLETED" else "[..]"
        print(f"  {mark} {task['desc']} -> {st}")

if __name__ == "__main__":
    run_stage_downloads()
