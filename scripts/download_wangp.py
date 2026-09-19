import os
import time
import subprocess
import zipfile
from pathlib import Path

DEST_DIR = Path("services/wangp")
DEST_DIR.mkdir(parents=True, exist_ok=True)
ZIP_FILE = DEST_DIR / "Wan2GP.zip"
EXTRACT_DIR = DEST_DIR / "Wan2GP"

URL = "https://codeload.github.com/deepbeepmeep/Wan2GP/zip/refs/heads/main"

def download_and_extract():
    if EXTRACT_DIR.exists() and (EXTRACT_DIR / "wgp.py").exists():
        print("[SUCCESS] Wan2GP already extracted.")
        return True

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        if ZIP_FILE.exists():
            ZIP_FILE.unlink()
        print(f"[{attempt}/{max_retries}] Downloading Wan2GP zip from {URL}...")
        cmd = [
            "curl.exe",
            "-L",
            "--retry", "5",
            "--retry-delay", "2",
            "-o", str(ZIP_FILE),
            URL
        ]
        subprocess.run(cmd)

        if ZIP_FILE.exists() and ZIP_FILE.stat().st_size > 50_000_000:
            print(f"[SUCCESS] Downloaded {ZIP_FILE.stat().st_size} bytes. Extracting...")
            try:
                with zipfile.ZipFile(ZIP_FILE, 'r') as z:
                    z.extractall(DEST_DIR)
                extracted_main = DEST_DIR / "Wan2GP-main"
                if extracted_main.exists():
                    if EXTRACT_DIR.exists():
                        import shutil
                        shutil.rmtree(EXTRACT_DIR)
                    extracted_main.rename(EXTRACT_DIR)
                if ZIP_FILE.exists():
                    ZIP_FILE.unlink()
                print("[SUCCESS] Wan2GP installed successfully!")
                return True
            except Exception as e:
                print(f"Extraction error: {e}, will retry...")

        time.sleep(2)

    return False

if __name__ == "__main__":
    download_and_extract()
