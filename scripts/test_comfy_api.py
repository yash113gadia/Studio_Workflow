import sys
import json
import time
from pathlib import Path
import urllib.request
import urllib.parse
from PIL import Image

COMFY_HOST = "127.0.0.1:8188"
ROOT_DIR = Path(__file__).resolve().parent.parent
COMFY_DIR = ROOT_DIR / "services" / "comfyui" / "ComfyUI"


def test_system_stats():
    url = f"http://{COMFY_HOST}/system_stats"
    print(f"Connecting to {url}...")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        print("[Pass] /system_stats response received:")
        system_info = data.get("system", {})
        devices = data.get("devices", [])
        print(f"   OS: {system_info.get('os')}, Python: {system_info.get('python_version')}")
        for d in devices:
            print(f"   Device: {d.get('name')} | VRAM: {round(d.get('total_vram', 0)/(1024**3), 2)} GB")
        return data


def test_object_info():
    url = f"http://{COMFY_HOST}/object_info"
    print(f"Connecting to {url}...")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "LoadImage" in data, "LoadImage node missing"
        assert "SaveImage" in data, "SaveImage node missing"
        print(f"[Pass] /object_info verified ({len(data)} nodes registered).")
        return data


def create_test_input_image() -> str:
    input_dir = COMFY_DIR / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    test_img_path = input_dir / "test_api_input.png"

    # Create a small 64x64 solid green image with PIL
    img = Image.new("RGB", (64, 64), color=(0, 200, 100))
    img.save(test_img_path)
    print(f"[Pass] Created test input image at {test_img_path}")
    return "test_api_input.png"


def queue_prompt(prompt_workflow: dict) -> str:
    url = f"http://{COMFY_HOST}/prompt"
    payload = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        prompt_id = data.get("prompt_id")
        print(f"[Pass] Prompt queued with ID: {prompt_id}")
        return prompt_id


def wait_for_execution(prompt_id: str, max_seconds: int = 30) -> dict:
    url = f"http://{COMFY_HOST}/history/{prompt_id}"
    start_time = time.time()
    while time.time() - start_time < max_seconds:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if prompt_id in data:
                    history = data[prompt_id]
                    status = history.get("status", {})
                    if status.get("completed", False) or status.get("status_str") == "success":
                        print("[Pass] Workflow execution completed successfully!")
                        return history
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Workflow execution timed out after {max_seconds}s")


def main():
    print("=========================================")
    print(" COMFYUI API ACCEPTANCE TEST (Phase 2)   ")
    print("=========================================")

    # 1. System stats
    test_system_stats()

    # 2. Object info
    test_object_info()

    # 3. Create test input image
    image_filename = create_test_input_image()

    # 4. Define minimal deterministic workflow (LoadImage -> SaveImage)
    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename
            }
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "api_acceptance_test",
                "images": ["1", 0]
            }
        }
    }

    # 5. Queue workflow
    prompt_id = queue_prompt(workflow)

    # 6. Wait for output
    history = wait_for_execution(prompt_id)

    # 7. Verify output file exists
    outputs = history.get("outputs", {}).get("2", {}).get("images", [])
    assert len(outputs) > 0, "No output images found in history"
    out_file = outputs[0]
    out_filename = out_file.get("filename")
    out_subfolder = out_file.get("subfolder", "")

    output_dir = COMFY_DIR / "output"
    if out_subfolder:
        final_path = output_dir / out_subfolder / out_filename
    else:
        final_path = output_dir / out_filename

    assert final_path.exists(), f"Output file does not exist at {final_path}"
    print(f"\n[ACCEPTANCE TEST PASSED]")
    print(f"Generated Output Image: {final_path}")
    print(f"File Size: {final_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
