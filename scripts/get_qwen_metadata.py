import subprocess
import json

urls = [
    ("qwen_image_vae", "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors"),
    ("qwen_image_edit_2511_int8_convrot", "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors"),
    ("qwen_2.5_vl_7b_fp8_scaled", "https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"),
    ("lightning_lora", "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors")
]

for name, url in urls:
    print(f"\n--- Checking {name} ---")
    cmd = ["curl.exe", "-s", "-I", "-L", "--ssl-no-revoke", "-4", url]
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines = res.stdout.splitlines()
    for l in lines:
        if any(k in l.lower() for k in ["content-length", "etag", "location", "x-linked-size", "x-linked-etag", "content-disposition"]):
            print(" ", l)
