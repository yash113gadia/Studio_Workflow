# Quality repair - 20 September 2026

The main Creator pipeline had several deterministic output problems unrelated to model size: genre-specific invented settings, discarded dialogue, random recasting, a 90-second image timeout, artificial noise/flicker, substitute blank clips and audio tones, oversized captions, and hardcoded passing QA scores.

## Implemented

- Script-faithful FLUX prompts with complete action descriptions. Distilled FLUX uses its supplied four-step schedule; generation gets up to 30 minutes on low-memory hardware.
- Clean camera animation, aspect-preserving images, CRF 18 output, smaller outlined captions and streaming-friendly MP4 files.
- Every parsed dialogue line is retained. Speech is measured before rendering and placed at the corresponding shot time. Longer dialogue extends the shot instead of being clipped.
- One keyframe per scene reduces recasting and duplicate inference. A seed makes reruns reproducible within the same configuration. This does not establish identity across different scenes.
- Explicit cinematic-still and experimental LTX real-motion modes. The latter uses the installed LTX-Video 2B 0.9.5 checkpoint, not the unrelated LTX-2.5 claimed in older project documents.
- No gradient/blank-video or tone substitution in real Creator execution. Missing model operations now fail visibly. H3 and SCAIL adapters no longer pass off still animation as model inference.
- Creator GPU ownership has a repeating heartbeat; simultaneous Creator jobs are rejected. Lease acquisition uses a database write transaction.
- Unique output folders prevent overwriting prior renders in an existing project. New mock renders go to cache, outside the user gallery.
- No fabricated DINO/semantic score or continuity approval: completed output requires visual review. The UI displays elapsed time instead of inventing completed stages.
- The launcher now starts ComfyUI as well as the Studio server.

## Verification

- 37 combined Creator/scene/post/core/GPU/adapter tests passed, including an actual FFmpeg render, speech timing, script fidelity, and failure behavior.
- H3/SCAIL adapter regression tests use mocks; these do not validate H3 or SCAIL inference.
- Real local FLUX inference produced the requested farmer in a wheat field; inspected visually.
- Real Creator execution produced a narrated 1080x1920 MP4. FFprobe verified 4.000-second video and audio tracks. Captions were inspected and corrected by reassembling the same source clip.
- Updated server is running at http://127.0.0.1:8000 and exposes the new motion control.

## What remains limited

Speech currently uses installed Windows SAPI voices. Neural voice cloning, facial lip sync, cross-scene identity enforcement, semantic QA, full serial-drama continuity, and other advertised specialist engines are not established by this repair. Historical benchmark tables and fixed scores elsewhere in this repository should not be treated as measurements of real production inference.

Cinematic mode intentionally animates still images with a camera move. LTX mode generates actual image-conditioned frames at 384x672 (portrait), 672x384 (landscape), or 512 square, in short chunks with tiled VAE decoding. The 1080p export is resized; it is not native 1080p model detail. Slow or complex motion can still deform anatomy. Review the result before publishing.

Music is disabled by default; when explicitly enabled it is a procedural ambient chord bed. Failed speech produces an error, never a tone.

## Upstream references

- Official LTX 0.9.5 setup, including the FP8 T5 encoder: https://blog.comfy.org/p/ltx-video-095-day-1-support-in-comfyui
- Workflow reference: https://github.com/comfyanonymous/ComfyUI_examples/blob/master/ltxv/ltxv_image_to_video.0.9.5.json
- Encoder: Comfy-Org/mochi_preview_repackaged, split_files/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors. Installation downloads the weights; generation thereafter uses local files.

The laptop sleep inhibitor is temporary (six hours) and does not alter permanent Windows power settings. Existing user changes were retained; no repository reset was performed.

## Real motion validation

The FP8 T5 encoder downloaded completely (5,157,348,688 bytes) and its safetensors header parsed with 389 tensor keys. LTX generated a real 384x672, 48-frame, 2.000-second MP4 in 105.72 seconds. Sampled frames were visually inspected; motion is restrained and the scene remains consistent. This single example does not establish broad quality or stability.

The complete FLUX -> LTX -> Windows SAPI -> captions -> FFmpeg path also passed. The resulting master is 1080x1920, 96 frames at 24 fps, with matching 4.000-second video and audio streams. Four sampled frames were inspected: the farmer and field remain consistent, the hands move, and captions are readable. The output remains marked `REVIEW_REQUIRED` because automatic visual, semantic, anatomy, continuity, and lip-sync QA are not implemented.

Sample: `temp/quality_validation/harvest_real_motion.mp4`.

Real AI motion is now the default Creator mode; cinematic stills remain the faster alternative. Model names are resolved from ComfyUI rather than assuming a particular folder prefix. Idle ComfyUI model caches are released between image and video inference to reduce RAM pressure.
