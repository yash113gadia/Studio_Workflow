import os
import subprocess
import time
from pathlib import Path

DEST_DIR = Path("models/qa/dino/dinov2-small")
DEST_DIR.mkdir(parents=True, exist_ok=True)

MODEL_URL = "https://huggingface.co/facebook/dinov2-small/resolve/main/model.safetensors"
OUT_FILE = DEST_DIR / "model.safetensors"
EXPECTED_SIZE = 86575696  # approximate 86MB

def download_with_retry():
    max_retries = 20
    for attempt in range(1, max_retries + 1):
        if OUT_FILE.exists() and OUT_FILE.stat().st_size >= 80_000_000:
            print(f"[SUCCESS] {OUT_FILE} already downloaded ({OUT_FILE.stat().st_size} bytes).")
            return True
            
        print(f"[{attempt}/{max_retries}] Downloading {MODEL_URL}...")
        cmd = [
            "curl.exe",
            "-L",
            "-C", "-",
            "--retry", "5",
            "--retry-delay", "2",
            "-o", str(OUT_FILE),
            MODEL_URL
        ]
        res = subprocess.run(cmd)
        if res.returncode == 0 and OUT_FILE.exists() and OUT_FILE.stat().st_size >= 80_000_000:
            print(f"[SUCCESS] Download completed ({OUT_FILE.stat().st_size} bytes).")
            return True
        print(f"Retrying in 2 seconds...")
        time.sleep(2)
        
    return False

if __name__ == "__main__":
    download_with_retry()
