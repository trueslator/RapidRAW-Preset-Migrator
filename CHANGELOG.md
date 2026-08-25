# Changelog

## 1.0.0 — 2026-08-25

First public release.

- Legacy `.lrtemplate` batch conversion to RapidRAW `.rrpreset`
- Folder/ZIP input and preserved folder structure
- Standard-library-only Python implementation
- Safe fallback preset generation
- Live recursive `CameraProfiles/` library
- Incremental CameraProfile rescanning when files change
- Exact DCP profile matching with explicit camera-variant dropdown
- Persistent CameraProfile choices in `migration_manager_state.json`
- On-demand cached companion `.cube` generation
- DCP-aware color and black-and-white workflows
- Local HTML Preset Manager
- `[MIG]` namespace to isolate migrated presets
- Favorites and `[MIG] Favoriten` mirror folder
- Automatic `presets.json` backup
- Refuses writes while RapidRAW is running
- Windows, native Linux and Linux Flatpak storage detection
- Manual `RAPIDRAW_PRESETS_JSON` override
- Explicit RapidRAW `presetType: style` for migrated looks
