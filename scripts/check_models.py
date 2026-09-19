"""Preeti Studio Model Stack Integrity & Disk Safety Checker."""
import os
import shutil
import sys
from pathlib import Path

REQUIRED_MODELS = [
    # Phase 4: FLUX.2 Klein Asset Factory
    {
        "name": "FLUX.2 Klein 4B FP8",
        "path": "models/image/diffusion_models/flux-2-klein-4b-fp8.safetensors",
        "expected_bytes": 4070624520,
        "phase": "Phase 4",
    },
    {
        "name": "Qwen 3.4B Text Encoder",
        "path": "models/image/text_encoders/qwen_3_4b.safetensors",
        "expected_bytes": 8044982048,
        "phase": "Phase 4",
    },
    {
        "name": "FLUX2 VAE",
        "path": "models/image/vae/flux2-vae.safetensors",
        "expected_bytes": 336211292,
        "phase": "Phase 4",
    },

    # Phase 5: Qwen-Image-Edit Specialist
    {
        "name": "Qwen Image VAE",
        "path": "models/image/vae/qwen_image_vae.safetensors",
        "expected_bytes": 253806246,
        "phase": "Phase 5",
    },
    {
        "name": "Qwen 2511 Lightning LoRA",
        "path": "models/image/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "expected_bytes": 849608296,
        "phase": "Phase 5",
    },
    {
        "name": "Qwen 2.5-VL 7B FP8 Text Encoder",
        "path": "models/image/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "expected_bytes": 9384670680,
        "phase": "Phase 5",
    },
    {
        "name": "Qwen-Image-Edit 2511 INT8 ConvRot",
        "path": "models/image/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
        "expected_bytes": 20499083824,
        "phase": "Phase 5",
    },

    # Phase 8: Visual QA
    {
        "name": "DINOv2 Small Feature Extractor",
        "path": "models/qa/dino/dinov2-small/model.safetensors",
        "expected_bytes": 88249960,
        "phase": "Phase 8",
    },

    # Phase 10: MiniMax H3 Generative Video
    {
        "name": "H3 Audio VAE FP32",
        "path": "models/video/minimax_h3/MiniMax-H3-audio_vae_fp32.safetensors",
        "expected_bytes": 605429308,
        "phase": "Phase 10",
    },
    {
        "name": "H3 Video VAE FP16",
        "path": "models/video/minimax_h3/MiniMax-H3-video_vae_fp16.safetensors",
        "expected_bytes": 5207806512,
        "phase": "Phase 10",
    },
    {
        "name": "H3 FL2V Turbo 4-Step LoRA",
        "path": "models/video/minimax_h3/loras/minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors",
        "expected_bytes": 1383708328,
        "phase": "Phase 10",
    },
    {
        "name": "H3 Ref2V Turbo 4-Step LoRA",
        "path": "models/video/minimax_h3/loras/minimax_h3_lightx2v_ref2v_turbo_4step_alpha8_v0.1_bf16.safetensors",
        "expected_bytes": 1383712504,
        "phase": "Phase 10",
    },
    {
        "name": "H3 Qwen3-VL Text Encoder GGUF",
        "path": "models/video/minimax_h3/Qwen3-VL-32B-Instruct/qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf",
        "expected_bytes": 14576977888,
        "phase": "Phase 10",
    },
    {
        "name": "H3 Ref2VA INT8 Diffusion Model",
        "path": "models/video/minimax_h3/MiniMax-H3-Ref2VA-pruned_int8_convrot.safetensors",
        "expected_bytes": 22144108397,
        "phase": "Phase 10",
    },

    # Phase 11: SCAIL-2 Controlled Performance
    {
        "name": "Wan 2.1 Video VAE",
        "path": "models/video/wan21/Wan2.1_VAE.safetensors",
        "expected_bytes": 507593157,
        "phase": "Phase 11",
    },
    {
        "name": "SCAIL-2 14B INT8 Quanto Model",
        "path": "models/video/wan21/scail2_14B_quanto_mbf16_int8.safetensors",
        "expected_bytes": 16644305281,
        "phase": "Phase 11",
    },

    # Phase 12: Audio & Music Composition
    {
        "name": "ACE-Step 1.5 Music Transformer",
        "path": "models/audio/ace_step/ace_step_transformer/diffusion_pytorch_model.safetensors",
        "expected_bytes": 6611422728,
        "phase": "Phase 12",
    },
    {
        "name": "ACE-Step Music DCAE Autoencoder",
        "path": "models/audio/ace_step/music_dcae_f8c8/diffusion_pytorch_model.safetensors",
        "expected_bytes": 313646516,
        "phase": "Phase 12",
    },
    {
        "name": "ACE-Step Music Vocoder",
        "path": "models/audio/ace_step/music_vocoder/diffusion_pytorch_model.safetensors",
        "expected_bytes": 206350988,
        "phase": "Phase 12",
    },

    # Phase 15: Video Upscaler
    {
        "name": "FlashVSR v1.1 Transformer BF16",
        "path": "models/upscalers/flashvsr/FlashVSR_v1.1_transformer_bf16.safetensors",
        "expected_bytes": 2838077304,
        "phase": "Phase 15",
    },
    {
        "name": "FlashVSR v1.1 TC Decoder BF16",
        "path": "models/upscalers/flashvsr/FlashVSR_v1.1_tcdecoder_bf16.safetensors",
        "expected_bytes": 90683014,
        "phase": "Phase 15",
    },
    {
        "name": "FlashVSR v1.1 LQ Projection BF16",
        "path": "models/upscalers/flashvsr/FlashVSR_v1.1_lq_proj_bf16.safetensors",
        "expected_bytes": 575692496,
        "phase": "Phase 15",
    },

    # Phase 19: Sandbox Video
    {
        "name": "LTX-Video 2B v0.9.5 Sandbox Checkpoint",
        "path": "models/video/ltx25/ltx-video-2b-v0.9.5.safetensors",
        "expected_bytes": 6340729500,
        "phase": "Phase 19",
    },
]


def check_models_integrity():
    print("=" * 85)
    print("PREETI STUDIO LOCAL AI OS — COMPREHENSIVE MODEL INTEGRITY AUDIT")
    print("=" * 85)

    # 1. Disk Space Verification
    total, used, free = shutil.disk_usage("C:")
    free_gb = free / (1024**3)
    print(f"Drive C: Free Space: {free_gb:.2f} GB (Required buffer: >= 80.0 GB)")
    if free_gb < 80.0:
        print(f"WARNING: Disk space buffer violation! Only {free_gb:.2f} GB available.")
        return 1

    # 2. Check each model on disk
    all_ok = True
    print("\n{:<42} {:<10} {:<16} {:<10}".format("Model Component", "Phase", "Size on Disk", "Status"))
    print("-" * 85)

    for item in REQUIRED_MODELS:
        p = Path(item["path"])
        if not p.exists():
            print("{:<42} {:<10} {:<16} {:<10}".format(item["name"], item["phase"], "MISSING", "[FAIL]"))
            all_ok = False
            continue

        actual_bytes = p.stat().st_size
        size_mb = actual_bytes / (1024 * 1024)
        if actual_bytes == item["expected_bytes"]:
            status = "[VERIFIED]"
        else:
            status = f"[SIZE MISMATCH: {actual_bytes}]"
            all_ok = False

        print("{:<42} {:<10} {:<16} {:<10}".format(item["name"], item["phase"], f"{size_mb:.1f} MB", status))

    print("-" * 85)
    if all_ok:
        print(f"ALL {len(REQUIRED_MODELS)} REQUIRED MODEL WEIGHTS ARE PRESENT AND FULLY VERIFIED ON DISK.")
        return 0
    else:
        print("ONE OR MORE MODEL WEIGHTS FAILED INTEGRITY CHECKS.")
        return 1


if __name__ == "__main__":
    sys.exit(check_models_integrity())
