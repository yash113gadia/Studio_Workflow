# Upstream Workflow & Repository Manifest (UPSTREAM_MANIFEST.md)

Every borrowed workflow, repository, and external asset must be recorded with exact provenance, commit SHA, upstream path, local untouched copy path, and Studio modified variant path.

---

## Imported Workflows Registry

```yaml
# Schema template:
# - workflow_id: string
#   source_kind: comfy_official | model_authors | community
#   source_url: string
#   source_commit: string
#   source_file: string
#   local_upstream_copy: workflows/upstream/...
#   studio_variant: workflows/studio/...
#   api_variant: workflows/api_format/...
#   license_status: approved | review_required
#   models:
#     - filename: string
#       source: string
#       sha256: string
#   tested_on:
#     gpu: RTX 3070 Laptop 8GB
#     ram_gb: 16
#   result: pass | fail | experimental
#   notes: string
```

*(Workflows will be registered here as they are imported in Phase 4, Phase 5, Phase 10, etc.)*
