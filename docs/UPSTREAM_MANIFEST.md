# Upstream Workflow & Repository Manifest (UPSTREAM_MANIFEST.md)

Every borrowed workflow, repository, and external asset must be recorded with exact provenance, commit SHA, upstream path, local untouched copy path, and Studio modified variant path.

---

## Imported Workflows Registry

```yaml
- workflow_id: image_flux2_klein_text_to_image
  source_kind: comfy_official
  source_url: https://github.com/Comfy-Org/workflow_templates
  source_commit: pinned_core_v0.0.0
  source_file: templates/image_flux2_klein_text_to_image.json
  local_upstream_copy: workflows/upstream/comfy_official/image_flux2_klein_text_to_image.json
  sha256: f5b2e75448e1ef44ab3d08da00900000f0258f8f963934370c6a1c329d1328c2
  api_variant: workflows/api_format/flux_casting_v001.json
  license_status: approved (apache-2.0)
  models:
    - filename: flux-2-klein-4b-fp8.safetensors
      source: black-forest-labs/FLUX.2-klein-4b-fp8
      sha256: 97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6
    - filename: qwen_3_4b.safetensors
      source: Comfy-Org/vae-text-encorder-for-flux-klein-4b
      sha256: 6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a
    - filename: flux2-vae.safetensors
      source: Comfy-Org/vae-text-encorder-for-flux-klein-4b
      sha256: 868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3
  tested_on:
    gpu: RTX 3070 Laptop 8GB
    ram_gb: 16
  result: pass
  notes: Base FLUX.2 Klein 4B casting and text-to-image pipeline.

- workflow_id: image_flux2_klein_image_edit_4b_distilled
  source_kind: comfy_official
  source_url: https://github.com/Comfy-Org/workflow_templates
  source_commit: pinned_core_v0.0.0
  source_file: templates/image_flux2_klein_image_edit_4b_distilled.json
  local_upstream_copy: workflows/upstream/comfy_official/image_flux2_klein_image_edit_4b_distilled.json
  sha256: e0388a8870495802314d58fa61616ddcdb7064dac5f85a8787c9e08180b8a560
  api_variant: workflows/api_format/flux_character_keyframe_v001.json
  license_status: approved (apache-2.0)
  models:
    - filename: flux-2-klein-4b-fp8.safetensors
      source: black-forest-labs/FLUX.2-klein-4b-fp8
      sha256: 97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6
    - filename: qwen_3_4b.safetensors
      source: Comfy-Org/vae-text-encorder-for-flux-klein-4b
      sha256: 6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a
    - filename: flux2-vae.safetensors
      source: Comfy-Org/vae-text-encorder-for-flux-klein-4b
      sha256: 868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3
  tested_on:
    gpu: RTX 3070 Laptop 8GB
    ram_gb: 16
  result: pass
  notes: Reference conditioning character keyframe derivation (5 canonical angles) & outfit variation pipeline.

- workflow_id: image_qwen_image_edit_2511_int8
  source_kind: comfy_official
  source_url: https://github.com/Comfy-Org/workflow_templates
  source_commit: pinned_core_v0.0.0
  source_file: templates/image_qwen_image_edit_2511_int8.json
  local_upstream_copy: workflows/upstream/comfy_official/image_qwen_image_edit_2511_int8.json
  sha256: f69153d857a3e7ad374c4b79775fa2d8d99361135806a5ecf7106f2e41cd2336
  api_variant: workflows/api_format/qwen_edit_outfit_v001.json
  license_status: approved (apache-2.0)
  models:
    - filename: qwen_image_edit_2511_int8_convrot.safetensors
      source: Comfy-Org/Qwen-Image-Edit_ComfyUI
      sha256: 11b5af5ac601821d73930c84846c9a158e67177356daf927ce1c8d10f3963829
    - filename: qwen_2.5_vl_7b_fp8_scaled.safetensors
      source: Comfy-Org/HunyuanVideo_1.5_repackaged
      sha256: cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4
    - filename: qwen_image_vae.safetensors
      source: Comfy-Org/Qwen-Image_ComfyUI
      sha256: a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f
    - filename: Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
      source: lightx2v/Qwen-Image-Edit-2511-Lightning
      sha256: 22226e8d05d354bb356627d428809f5afd7819399b077238a2b70a82883a904f
  tested_on:
    gpu: RTX 3070 Laptop 8GB
    ram_gb: 16
  result: pending_benchmark
  notes: Specialist image editor for identity-preserving outfit swap, object removal, background repair, and prop correction.
```

