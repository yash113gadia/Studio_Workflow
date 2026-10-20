"""
Preeti Studio — Core Model Downloader
Downloads only the weights the verified Creator path needs (FLUX.2 Klein keyframes,
LTX-Video 0.9.5 motion, DINOv2 visual QA), then checks every file's size and SHA256.
All files are public on Hugging Face; no token is required. Safe to re-run: finished
files are skipped and partial files resume.
"""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_staged_models import download_file_resumable  # noqa: E402

STUDIO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = STUDIO_ROOT / "models"
VERIFIED_FILE = MODELS_DIR / "core_models_verified.json"
HEADROOM_GB = 10.0  # free space left over after every core model is on disk

HF = "https://huggingface.co"
CORE_MODELS = [
    {
        "desc": "FLUX.2 Klein 4B FP8 (image diffusion)",
        "url": f"{HF}/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors",
        "dest": "image/diffusion_models/flux-2-klein-4b-fp8.safetensors",
        "size": 4070624520,
        "sha256": "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6",
    },
    {
        "desc": "Qwen 3 4B (FLUX.2 text encoder)",
        "url": f"{HF}/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
        "dest": "image/text_encoders/qwen_3_4b.safetensors",
        "size": 8044982048,
        "sha256": "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a",
    },
    {
        "desc": "FLUX.2 VAE",
        "url": f"{HF}/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/vae/flux2-vae.safetensors",
        "dest": "image/vae/flux2-vae.safetensors",
        "size": 336211292,
        "sha256": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
    },
    {
        "desc": "LTX-Video 2B 0.9.5 (real-motion video)",
        "url": f"{HF}/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.5.safetensors",
        "dest": "video/ltx25/ltx-video-2b-v0.9.5.safetensors",
        "size": 6340729500,
        "sha256": "720d15c9f19f7d0f6b2a92bbbc34410e2cfb2f6856a100b38f734fbf973d4adf",
    },
    {
        "desc": "T5-XXL FP8 (LTX text encoder)",
        "url": f"{HF}/Comfy-Org/mochi_preview_repackaged/resolve/main/split_files/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
        "dest": "image/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
        "size": 5157348688,
        "sha256": "a498f0485dc9536735258018417c3fd7758dc3bccc0a645feaa472b34955557a",
    },
    {
        "desc": "DINOv2 Small (visual QA weights)",
        "url": f"{HF}/facebook/dinov2-small/resolve/main/model.safetensors",
        "dest": "qa/dino/dinov2-small/model.safetensors",
        "size": 88249960,
        "sha256": "ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1",
    },
    {
        "desc": "DINOv2 Small config",
        "url": f"{HF}/facebook/dinov2-small/resolve/main/config.json",
        "dest": "qa/dino/dinov2-small/config.json",
        "size": 547,
        "sha256": None,
    },
    {
        "desc": "DINOv2 Small preprocessor config",
        "url": f"{HF}/facebook/dinov2-small/resolve/main/preprocessor_config.json",
        "dest": "qa/dino/dinov2-small/preprocessor_config.json",
        "size": 436,
        "sha256": None,
    },
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(16 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def load_verified() -> dict:
    try:
        return json.loads(VERIFIED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_verified(model: dict, verified: dict) -> bool:
    """A file counts as done when its size matches and its hash was checked at this size and mtime."""
    path = MODELS_DIR / model["dest"]
    if not path.exists() or path.stat().st_size != model["size"]:
        return False
    if model["sha256"] is None:
        return True
    record = verified.get(model["dest"])
    stat = path.stat()
    return bool(record) and record.get("sha256") == model["sha256"] and record.get("mtime") == stat.st_mtime


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    verified = load_verified()

    pending = [m for m in CORE_MODELS if not is_verified(m, verified)]
    remaining_bytes = 0
    for model in pending:
        path = MODELS_DIR / model["dest"]
        have = path.stat().st_size if path.exists() else 0
        remaining_bytes += max(model["size"] - have, 0)

    free_gb = shutil.disk_usage(STUDIO_ROOT).free / 1024**3
    need_gb = remaining_bytes / 1024**3 + HEADROOM_GB
    print("=" * 75)
    print("PREETI STUDIO - CORE MODEL DOWNLOAD")
    print(f"Files still needed: {len(pending)} of {len(CORE_MODELS)} ({remaining_bytes / 1024**3:.1f} GB to download)")
    print(f"Free disk space:    {free_gb:.1f} GB (need {need_gb:.1f} GB including {HEADROOM_GB:.0f} GB headroom)")
    print("=" * 75)
    if pending and free_gb < need_gb:
        print(f"[ABORT] Not enough disk space. Free up {need_gb - free_gb:.1f} GB on this drive and run setup again.")
        return 1

    for index, model in enumerate(CORE_MODELS, 1):
        label = f"[{index}/{len(CORE_MODELS)}] {model['desc']}"
        path = MODELS_DIR / model["dest"]
        if is_verified(model, verified):
            print(f"[SKIP] {label}: already downloaded and verified.")
            continue

        # The resumable downloader cannot resume past the end, so restart oversized files.
        if path.exists() and path.stat().st_size > model["size"]:
            path.unlink()

        if not (path.exists() and path.stat().st_size == model["size"]):
            ok = download_file_resumable(model["url"], path, desc=label, min_free_gb=0)
            if not ok:
                print(f"[FAIL] {label}: download did not finish. Check the internet connection and run setup again; it resumes.")
                return 1

        size = path.stat().st_size
        if size != model["size"]:
            print(f"[FAIL] {label}: size is {size} bytes, expected {model['size']}. Run setup again to resume.")
            return 1

        if model["sha256"]:
            print(f"  Checking SHA256 of {path.name} ...", flush=True)
            started = time.time()
            actual = sha256_of(path)
            if actual != model["sha256"]:
                path.unlink()
                print(f"[FAIL] {label}: SHA256 mismatch (file deleted). Run setup again to re-download it.")
                return 1
            print(f"  [OK] SHA256 verified in {time.time() - started:.0f}s")
            verified[model["dest"]] = {"sha256": actual, "mtime": path.stat().st_mtime}
            VERIFIED_FILE.write_text(json.dumps(verified, indent=2), encoding="utf-8")

    print("\nAll core models are downloaded and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
