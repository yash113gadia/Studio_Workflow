"""End-to-end FLUX.2 Klein image generation test via ComfyUI API."""
import json
import time
import sys
import urllib.request
import urllib.error

COMFY_URL = "http://127.0.0.1:8188"

# API-format prompt matching the official FLUX.2 Klein text-to-image workflow
# Uses our downloaded FP8 model + qwen_3_4b text encoder + flux2-vae
PROMPT = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "diffusion_models\\flux-2-klein-4b-fp8.safetensors",
            "weight_dtype": "default"
        }
    },
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "text_encoders\\qwen_3_4b.safetensors",
            "type": "flux2"
        }
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "vae\\flux2-vae.safetensors"
        }
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "A cute orange tabby cat sitting on a windowsill, warm afternoon sunlight, soft focus background, digital photography",
            "clip": ["2", 0]
        }
    },
    "5": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "",
            "clip": ["2", 0]
        }
    },
    "6": {
        "class_type": "CFGGuider",
        "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "cfg": 5.0
        }
    },
    "7": {
        "class_type": "KSamplerSelect",
        "inputs": {
            "sampler_name": "euler"
        }
    },
    "8": {
        "class_type": "Flux2Scheduler",
        "inputs": {
            "steps": 20,
            "width": 512,
            "height": 512
        }
    },
    "9": {
        "class_type": "EmptyFlux2LatentImage",
        "inputs": {
            "width": 512,
            "height": 512,
            "batch_size": 1
        }
    },
    "10": {
        "class_type": "RandomNoise",
        "inputs": {
            "noise_seed": 42
        }
    },
    "11": {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["10", 0],
            "guider": ["6", 0],
            "sampler": ["7", 0],
            "sigmas": ["8", 0],
            "latent_image": ["9", 0]
        }
    },
    "12": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["11", 0],
            "vae": ["3", 0]
        }
    },
    "13": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["12", 0],
            "filename_prefix": "flux2_klein_e2e_test"
        }
    }
}


def queue_prompt(prompt):
    """Submit a prompt to ComfyUI and return the prompt_id."""
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    return result.get("prompt_id")


def poll_history(prompt_id, timeout=600):
    """Poll ComfyUI history for the given prompt_id until complete or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
            resp = urllib.request.urlopen(req, timeout=10)
            history = json.loads(resp.read())
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    return entry
                if status.get("status_str") == "error":
                    print(f"[ERROR] ComfyUI reported error:")
                    msgs = status.get("messages", [])
                    for m in msgs:
                        print(f"  {m}")
                    return None
        except urllib.error.URLError:
            pass
        time.sleep(3)
        elapsed = int(time.time() - start)
        if elapsed % 15 == 0:
            print(f"  ...waiting ({elapsed}s elapsed)")
    print(f"[ERROR] Timeout after {timeout}s waiting for prompt {prompt_id}")
    return None


def main():
    print("=" * 60)
    print("FLUX.2 Klein End-to-End Image Generation Test")
    print("=" * 60)
    
    # Check ComfyUI is alive
    try:
        req = urllib.request.Request(f"{COMFY_URL}/system_stats")
        resp = urllib.request.urlopen(req, timeout=5)
        stats = json.loads(resp.read())
        vram = stats.get("devices", [{}])[0].get("vram_total", 0)
        print(f"ComfyUI online. GPU VRAM: {vram / (1024**3):.1f} GB")
    except Exception as e:
        print(f"[ERROR] ComfyUI not reachable: {e}")
        sys.exit(1)
    
    # Queue the prompt
    print(f"\nSubmitting FLUX.2 Klein text-to-image prompt...")
    print(f"  Model: flux-2-klein-4b-fp8.safetensors")
    print(f"  Text Encoder: qwen_3_4b.safetensors")
    print(f"  VAE: flux2-vae.safetensors")
    print(f"  Resolution: 512x512, Steps: 20, CFG: 5.0")
    print(f"  Prompt: 'A cute orange tabby cat...'")
    
    prompt_id = queue_prompt(PROMPT)
    if not prompt_id:
        print("[ERROR] Failed to queue prompt")
        sys.exit(1)
    
    print(f"  Prompt ID: {prompt_id}")
    print(f"\nWaiting for generation (this may take 1-5 minutes on RTX 3070)...")
    
    result = poll_history(prompt_id, timeout=600)
    if not result:
        print("[FAILED] Generation did not complete.")
        sys.exit(1)
    
    # Check outputs
    outputs = result.get("outputs", {})
    save_node = outputs.get("13", {})
    images = save_node.get("images", [])
    
    if images:
        for img in images:
            filename = img.get("filename", "unknown")
            subfolder = img.get("subfolder", "")
            print(f"\n[SUCCESS] Image generated: {filename} (subfolder: {subfolder})")
        print(f"\nFLUX.2 Klein end-to-end test PASSED!")
        print(f"Images saved in ComfyUI output directory.")
    else:
        print("[FAILED] No images found in output")
        sys.exit(1)


if __name__ == "__main__":
    main()
