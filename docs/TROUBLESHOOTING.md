# Troubleshooting & Verified Fixes (TROUBLESHOOTING.md)

This document records errors encountered and the exact fixes that resolved them.

---

### [TRB-001] Missing Toolchain in Fresh Environment
- **Symptom:** `git`, `python`, `ffmpeg` not found in default PATH during Phase 0 audit.
- **Root Cause:** Fresh Windows system configuration with WindowsApps redirect stubs.
- **Fix:** Install standalone Python 3.11, Git, and FFmpeg via `winget` or direct portable binaries and ensure PATH includes them cleanly.
