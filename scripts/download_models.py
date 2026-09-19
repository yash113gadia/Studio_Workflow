import hashlib
import os
import subprocess
import sys
import time

MODELS = [
    {
        "id": "flux2-vae",
        "name": "flux2-vae.safetensors",
        "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/vae/flux2-vae.safetensors",
        "target_path": "models/image/vae/flux2-vae.safetensors",
        "expected_size": 336211292,
        "expected_sha256": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3"
    },
    {
        "id": "flux-2-klein-4b-fp8",
        "name": "flux-2-klein-4b-fp8.safetensors",
        "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors",
        "target_path": "models/image/diffusion_models/flux-2-klein-4b-fp8.safetensors",
        "expected_size": 4070624520,
        "expected_sha256": "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6"
    },
    {
        "id": "qwen_3_4b",
        "name": "qwen_3_4b.safetensors",
        "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
        "target_path": "models/image/text_encoders/qwen_3_4b.safetensors",
        "expected_size": 8044982048,
        "expected_sha256": "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a"
    }
]

def verify_file(file_path, expected_size, expected_sha256):
    if not os.path.exists(file_path):
        return False, "File does not exist"
    actual_size = os.path.getsize(file_path)
    if actual_size != expected_size:
        return False, f"Size mismatch: {actual_size} != {expected_size}"
    
    print(f"Computing SHA256 for {file_path} ({actual_size / (1024*1024):.1f} MB)...")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
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
    
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        print(f"[ATTEMPT {attempt}/{max_attempts}]")
        ret = subprocess.run(cmd)
        if ret.returncode == 0:
            break
        print(f"[WARN] curl exited with code {ret.returncode}, attempt {attempt}/{max_attempts}")
        if attempt < max_attempts:
            print(f"Retrying in 5 seconds...")
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
    for m in MODELS:
        success = download_item(m)
        if not success:
            sys.exit(1)
    print("\nAll required FLUX models downloaded and verified successfully!")
