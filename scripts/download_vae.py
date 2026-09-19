import os
import sys
import time
import socket
import hashlib

# Force IPv4
old_getaddrinfo = socket.getaddrinfo
def ipv4_only(*args, **kwargs):
    return [r for r in old_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]
socket.getaddrinfo = ipv4_only

from huggingface_hub import hf_hub_download

def download_model(repo_id, filename, local_dir, subfolder=None):
    os.makedirs(local_dir, exist_ok=True)
    print(f"Starting download: {filename} from {repo_id}...")
    t0 = time.time()
    
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=f"{subfolder}/{filename}" if subfolder else filename,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        resume_download=True
    )
    dt = time.time() - t0
    sz_mb = os.path.getsize(downloaded_path) / (1024 * 1024)
    speed_mb = sz_mb / dt if dt > 0 else 0
    print(f"Downloaded {filename}: {sz_mb:.2f} MB in {dt:.1f}s ({speed_mb:.2f} MB/s)")
    return downloaded_path

if __name__ == "__main__":
    vae_dir = os.path.abspath("models/image/vae")
    p = download_model(
        repo_id="Comfy-Org/vae-text-encorder-for-flux-klein-4b",
        filename="flux2-vae.safetensors",
        subfolder="split_files/vae",
        local_dir=vae_dir
    )
    print("Completed:", p)
