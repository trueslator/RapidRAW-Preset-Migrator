# Changelog

## 1.0.0 — 2026-08-25

First public release.

- Legacy `.lrtemplate` and modern `.xmp` batch conversion to RapidRAW `.rrpreset`
- Shared Lightroom mapping pipeline for both source formats
- XMP RGB/luma point curves, Texture and modern Color Grading
- Explicit reporting of unsupported XMP masks, Point Color and Creative XMP profile/look structures
- Source-format display/filter in HTML Preset Manager
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

### Final v1.0 XMP validation

- Relative XMP white-balance migration from target vs As-Shot values
- Meaningful parametric Lightroom curve edits select RapidRAW parametric curve mode; competing point curves are reported
- Conservative modern XMP Camera Calibration scaling, explicitly flagged as approximate
- Lightroom lens/manual vignette is intentionally not mapped to RapidRAW creative vignette
- UI/documentation now states clearly that migration is an approximation, not a 1:1 reproduction
- Real-image validation added alongside automated regression tests
