"""Preeti Studio Model Stack Integrity & Disk Safety Checker."""
import os
import shutil
import sys
from pathlib import Path

REQUIRED_MODELS = [
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
    {
        "name": "DINOv2 Small Feature Extractor",
        "path": "models/qa/dino/dinov2-small/model.safetensors",
        "expected_bytes": 88249960,
        "phase": "Phase 8",
    },
]


def check_models_integrity():
    print("=" * 80)
    print("PREETI STUDIO LOCAL AI OS — MODEL INTEGRITY AUDIT")
    print("=" * 80)

    # 1. Disk Space Verification
    total, used, free = shutil.disk_usage("C:")
    free_gb = free / (1024**3)
    print(f"Drive C: Free Space: {free_gb:.2f} GB (Required buffer: >= 80.0 GB)")
    if free_gb < 80.0:
        print(f"WARNING: Disk space buffer violation! Only {free_gb:.2f} GB available.")
        return 1

    # 2. Check each model on disk
    all_ok = True
    print("\n{:<36} {:<12} {:<16} {:<10}".format("Model Component", "Phase", "Size on Disk", "Status"))
    print("-" * 80)

    for item in REQUIRED_MODELS:
        p = Path(item["path"])
        if not p.exists():
            print("{:<36} {:<12} {:<16} {:<10}".format(item["name"], item["phase"], "MISSING", "[FAIL]"))
            all_ok = False
            continue

        actual_bytes = p.stat().st_size
        size_mb = actual_bytes / (1024 * 1024)
        if actual_bytes == item["expected_bytes"]:
            status = "[VERIFIED]"
        else:
            status = f"[SIZE MISMATCH: {actual_bytes}]"
            all_ok = False

        print("{:<36} {:<12} {:<16} {:<10}".format(item["name"], item["phase"], f"{size_mb:.1f} MB", status))

    print("-" * 80)
    if all_ok:
        print("ALL REQUIRED MODEL WEIGHTS ARE PRESENT AND FULLY VERIFIED ON DISK.")
        return 0
    else:
        print("ONE OR MORE MODEL WEIGHTS FAILED INTEGRITY CHECKS.")
        return 1


if __name__ == "__main__":
    sys.exit(check_models_integrity())
