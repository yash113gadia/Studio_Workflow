"""Real local LTX-Video 0.9.5 image-to-video through ComfyUI, without fake fallbacks."""
import json
import math
import shutil
import time
import uuid
from pathlib import Path
import urllib.request
import urllib.error
from app.core.post.ffmpeg_utils import run_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
URL = 'http://127.0.0.1:8188'
ENCODER = 't5xxl_fp8_e4m3fn_scaled.safetensors'


def request(path, payload=None):
    req = urllib.request.Request(URL + path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI rejected {path}: {detail}") from exc


def build_workflow(image_name, prompt, width, height, frames, seed, steps=30):
    """LTX-Video 0.9.5 image-to-video, wired like the official ComfyUI example
    (ComfyUI_examples/ltxv/ltxv_image_to_video.0.9.5.json): the source frame is
    compressed like a video frame, pinned at frame 0 with full strength, and the
    guide is cropped off before a plain VAE decode."""
    def node(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}
    return {
        '1': node('CheckpointLoaderSimple', ckpt_name='ltx-video-2b-v0.9.5.safetensors'),
        '2': node('CLIPLoader', clip_name=ENCODER, type='ltxv', device='cpu'),
        '3': node('CLIPTextEncode', clip=['2', 0], text=prompt),
        '4': node('CLIPTextEncode', clip=['2', 0], text='low quality, worst quality, deformed, distorted, disfigured, '
                  'motion smear, motion artifacts, fused fingers, bad anatomy, weird hand, ugly, text, watermark'),
        '5': node('LoadImage', image=image_name),
        '13': node('LTXVPreprocess', image=['5', 0], img_compression=40),
        '14': node('EmptyLTXVLatentVideo', width=width, height=height, length=frames, batch_size=1),
        '6': node('LTXVAddGuide', positive=['3', 0], negative=['4', 0], vae=['1', 2], latent=['14', 0],
                  image=['13', 0], frame_idx=0, strength=1.0),
        '7': node('LTXVConditioning', positive=['6', 0], negative=['6', 1], frame_rate=24.0),
        '8': node('LTXVScheduler', steps=steps, max_shift=2.05, base_shift=0.95, stretch=True, terminal=0.1, latent=['6', 2]),
        '9': node('KSamplerSelect', sampler_name='euler'),
        '10': node('SamplerCustom', model=['1', 0], add_noise=True, noise_seed=seed, cfg=3.0, positive=['7', 0],
                   negative=['7', 1], sampler=['9', 0], sigmas=['8', 0], latent_image=['6', 2]),
        '15': node('LTXVCropGuides', positive=['7', 0], negative=['7', 1], latent=['10', 0]),
        # ComfyUI falls back to tiled decoding by itself if this runs out of VRAM.
        '11': node('VAEDecode', samples=['15', 2], vae=['1', 2]),
        '12': node('SaveWEBM', images=['11', 0], filename_prefix='studio_ltx/' + uuid.uuid4().hex, codec='vp9', fps=24.0, crf=18),
    }


def render_ltx_video(
    image_path, output_path, action, duration, aspect='9:16', seed=42,
    timeout=3600, quality_profile='balanced', client_id=None, progress_callback=None
):
    encoder = ROOT / 'models/image/text_encoders' / ENCODER
    if not encoder.exists():
        raise RuntimeError('LTX text encoder is not installed yet. Use cinematic mode until setup completes.')
    if duration > 12:
        raise RuntimeError('This dialogue needs a shot longer than 12 seconds. Split the line for generative mode.')
    queue = request('/queue')
    if queue.get('queue_running') or queue.get('queue_pending'):
        raise RuntimeError('ComfyUI is busy. Wait for its existing jobs before starting video inference.')
    request('/free', {'unload_models': True, 'free_memory': True})
    # LTX turns each 32x32 pixel block into one latent cell and was trained around 768x512
    # (0.39 MP). Far smaller frames give a coarse latent grid that decodes as smeared colour.
    profiles = {
        'draft': {
            'steps': 20,
            'size': {'9:16': (384, 672), '16:9': (672, 384), '1:1': (512, 512)},
            'crf': 21,
        },
        'balanced': {
            'steps': 30,
            'size': {'9:16': (480, 832), '16:9': (832, 480), '1:1': (640, 640)},
            'crf': 18,
        },
        'quality': {
            'steps': 36,
            'size': {'9:16': (544, 960), '16:9': (960, 544), '1:1': (736, 736)},
            'crf': 17,
        },
    }
    if quality_profile not in profiles:
        raise ValueError(f'Unknown LTX quality profile: {quality_profile}')
    profile = profiles[quality_profile]
    width, height = profile['size'][aspect]
    # Always 8n+1 frames; short chunks limit activation memory on the 8 GB GPU.
    source = Path(image_path)
    filename = 'studio_' + uuid.uuid4().hex + source.suffix
    input_path = ROOT / 'services/comfyui/ComfyUI/input' / filename
    shutil.copy2(source, input_path)
    segments = []
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = math.ceil(duration / 4)
    segment_duration = duration / count
    try:
        for index in range(count):
            if progress_callback:
                progress_callback(f'LTX segment {index + 1}/{count}: loading models and encoding the source frame.', 18 + int(42 * index / count))
            frames = math.ceil(segment_duration * 24 / 8) * 8 + 1
            prompt = (f'{action} The video follows the appearance and composition of the supplied image. '
                      'One continuous shot, natural restrained movement, physically plausible motion, stable lighting. '
                      'The camera remains steady. Subjects and surroundings retain their appearance throughout the shot.')
            workflow = build_workflow(
                filename, prompt, width, height, frames, seed + index,
                steps=profile['steps'],
            )
            for node_id, kind, field, basename in [('1', 'CheckpointLoaderSimple', 'ckpt_name', 'ltx-video-2b-v0.9.5.safetensors'), ('2', 'CLIPLoader', 'clip_name', ENCODER)]:
                info = request('/object_info/' + kind)
                names = info[kind]['input']['required'][field][0]
                matches = [name for name in names if name.replace('\\', '/').split('/')[-1] == basename]
                if not matches:
                    raise RuntimeError(f'ComfyUI cannot find {basename}; check extra_model_paths.yaml')
                workflow[node_id]['inputs'][field] = matches[0]
            payload = {'prompt': workflow}
            if client_id:
                payload['client_id'] = client_id
            response = request('/prompt', payload)
            prompt_id = response['prompt_id']
            deadline = time.monotonic() + timeout
            rendered = None
            while time.monotonic() < deadline:
                history = request('/history/' + prompt_id).get(prompt_id)
                if history:
                    if history.get('status', {}).get('status_str') == 'error':
                        raise RuntimeError('LTX execution failed: ' + str(history['status'].get('messages', []))[-1200:])
                    for data in history.get('outputs', {}).values():
                        for key in ('images', 'gifs', 'videos'):
                            for item in data.get(key, []):
                                path = ROOT / 'services/comfyui/ComfyUI/output' / item.get('subfolder', '') / item['filename']
                                if path.suffix.lower() in ('.webm', '.mp4') and path.exists():
                                    rendered = path
                    if rendered:
                        break
                time.sleep(2)
            if rendered is None:
                # Delete only this pending request; do not interrupt another user's active job.
                request('/queue', {'delete': [prompt_id]})
                raise RuntimeError('LTX generation timed out; inspect the ComfyUI queue before retrying.')
            segments.append(rendered)
            if progress_callback:
                progress_callback(f'LTX segment {index + 1}/{count}: denoise and tiled VAE decode complete.', 18 + int(42 * (index + 1) / count))
            # Feed the last generated frame to the next segment to preserve continuity.
            if index < count - 1:
                code, _, err = run_ffmpeg(['-y', '-sseof', '-0.1', '-i', str(rendered), '-frames:v', '1', str(input_path)])
                if code:
                    raise RuntimeError(err[-500:])
        inputs = []
        filters = []
        for i, path in enumerate(segments):
            inputs.extend(['-i', str(path)])
            filters.append(f'[{i}:v]trim=duration={segment_duration},setpts=PTS-STARTPTS[v{i}]')
        filters.append(''.join(f'[v{i}]' for i in range(len(segments))) + f'concat=n={len(segments)}:v=1:a=0[out]')
        code, _, err = run_ffmpeg(['-y'] + inputs + ['-filter_complex', ';'.join(filters), '-map', '[out]',
                    '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(profile['crf']), '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', str(output)], timeout_s=180)
        if code:
            raise RuntimeError('Video encode failed: ' + err[-500:])
        if progress_callback:
            progress_callback('LTX segments joined and encoded.', 62)
        output.with_suffix('.generation.json').write_text(json.dumps({'model':'ltx-video-2b-v0.9.5',
            'encoder':ENCODER,'seed':seed,'steps':profile['steps'],'quality_profile':quality_profile,
            'resolution':[width,height], 'segments':len(segments), 'guide_strength':1.0,
            'duration_s':duration, 'source_image':str(source), 'action':action},indent=2),encoding='utf-8')
        return output.exists() and output.stat().st_size > 1000
    finally:
        input_path.unlink(missing_ok=True)
