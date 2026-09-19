"""Download and verify Qwen-Image-Edit-2511 INT8 specialist model stack."""
import hashlib
import os
import shutil
import subprocess
import sys
import time

QWEN_MODELS = [
    {
        "id": "qwen_image_vae",
        "name": "qwen_image_vae.safetensors",
        "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors",
        "target_path": "models/image/vae/qwen_image_vae.safetensors",
        "expected_size": 253806246,
        "expected_sha256": "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f"
    },
    {
        "id": "lightning_lora",
        "name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "url": "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "target_path": "models/image/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "expected_size": 849608296,
        "expected_sha256": "22226e8d05d354bb356627d428809f5afd7819399b077238a2b70a82883a904f"
    },
    {
        "id": "qwen_2.5_vl_7b_fp8_scaled",
        "name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "url": "https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "target_path": "models/image/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "expected_size": 9384670680,
        "expected_sha256": "cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4"
    },
    {
        "id": "qwen_image_edit_2511_int8_convrot",
        "name": "qwen_image_edit_2511_int8_convrot.safetensors",
        "url": "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
        "target_path": "models/image/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
        "expected_size": 20499083824,
        "expected_sha256": "11b5af5ac601821d73930c84846c9a158e67177356daf927ce1c8d10f3963829"
    }
]


def check_disk_space():
    total, used, free = shutil.disk_usage("C:")
    free_gb = free / (1024**3)
    print(f"Free disk space on C: {free_gb:.2f} GB")
    if free_gb < 80:
        raise RuntimeError(f"Disk safety violation: only {free_gb:.2f} GB free, minimum 80 GB required.")
    return True


def verify_file(file_path, expected_size, expected_sha256):
    if not os.path.exists(file_path):
        return False, "File does not exist"
    actual_size = os.path.getsize(file_path)
    if actual_size != expected_size:
        return False, f"Size mismatch: {actual_size} != {expected_size}"

    print(f"Computing SHA256 for {file_path} ({actual_size / (1024*1024):.1f} MB)...")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(32 * 1024 * 1024):
            h.update(chunk)
    actual_sha256 = h.hexdigest()
    if actual_sha256.lower() != expected_sha256.lower():
        return False, f"SHA256 mismatch: {actual_sha256} != {expected_sha256}"
    return True, actual_sha256


def download_item(item):
    target = os.path.abspath(item["target_path"])
    os.makedirs(os.path.dirname(target), exist_ok=True)

    if os.path.exists(target) and os.path.getsize(target) == item["expected_size"]:
        ok, msg = verify_file(target, item["expected_size"], item["expected_sha256"])
        if ok:
            print(f"[ALREADY VERIFIED] {item['name']} (SHA256: {msg[:16]}...)")
            return True
        else:
            print(f"[VERIFY FAILED] {msg}, re-downloading...")

    check_disk_space()

    print(f"\n=======================================================")
    print(f"Downloading: {item['name']}")
    print(f"Target: {target}")
    print(f"Expected Size: {item['expected_size'] / (1024*1024):.1f} MB")
    print(f"URL: {item['url']}")
    print(f"=======================================================\n")

    cmd = [
        "curl.exe",
        "--ssl-no-revoke",
        "-4",
        "-L",
        "-C", "-",
        "--retry", "5",
        "--retry-delay", "3",
        "--retry-connrefused",
        item["url"],
        "-o", target
    ]

    max_attempts = 15
    for attempt in range(1, max_attempts + 1):
        print(f"[ATTEMPT {attempt}/{max_attempts}]")
        ret = subprocess.run(cmd)
        if ret.returncode == 0:
            break
        print(f"[WARN] curl exited with code {ret.returncode}, attempt {attempt}/{max_attempts}")
        if attempt < max_attempts:
            print("Retrying in 5 seconds...")
            time.sleep(5)
        else:
            print(f"[ERROR] All {max_attempts} attempts failed for {item['name']}")
            return False

    ok, msg = verify_file(target, item["expected_size"], item["expected_sha256"])
    if not ok:
        print(f"[CHECKSUM FAILED] {msg}")
        return False

    print(f"[SUCCESS] Verified {item['name']} (SHA256: {msg})")
    return True


if __name__ == "__main__":
    check_disk_space()
    for m in QWEN_MODELS:
        success = download_item(m)
        if not success:
            sys.exit(1)
    print("\nAll required Qwen-Image-Edit-2511 INT8 models downloaded and verified successfully!")
