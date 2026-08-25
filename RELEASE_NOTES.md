# RapidRAW Preset Migrator 1.0.0

First public release — 2026-08-25.

## Highlights

- Migrates legacy Lightroom `.lrtemplate` **and modern `.xmp`** presets to RapidRAW `.rrpreset`
- Batch processing of mixed `.lrtemplate` / `.xmp` collections from files, folders and ZIP archives
- XMP point curves, Texture and modern Color Grading support
- XMP custom white balance converted relative to As-Shot values where available
- Parametric-vs-point curve selection for modern XMP presets
- Conservative XMP Camera Calibration mapping, explicitly marked as approximate
- Lightroom lens/manual vignette is not mis-mapped as RapidRAW creative vignette
- XMP masking/adaptive/unsupported Creative Profile data is explicitly reported
- Safe self-contained fallback preset for every successfully converted preset
- **Live Camera Profile Library:** put user-owned `.dcp` files into `CameraProfiles/` at any time
- Exact-profile dropdown per preset, including multiple camera-specific variants
- Add new DCP files without reconverting the original Lightroom presets
- On-demand, cached companion `.cube` LUT generation
- DCP-aware B&W workflow using the legacy Lightroom GrayMixer
- Browser-based selection, filtering and favorites manager
- `[MIG]` namespace for reversible import/removal
- Automatic RapidRAW `presets.json` backups
- Windows + native Linux + Flatpak support
- No external Python packages

## Safety / rights

No Lightroom presets, DCP profiles, film packs, LUT packs, RapidRAW binaries or other third-party creative assets are bundled. Users provide their own source files and remain responsible for their licenses.

This is an unofficial community project and is not affiliated with RapidRAW/CyberTimon or Adobe.

## Conversion fidelity

This release performs best-effort **look migration**, not a pixel-identical 1:1 Lightroom renderer clone. Lightroom/Adobe Camera Raw and RapidRAW use different RAW engines and processing pipelines. Approximate mappings and unsupported settings are documented in `conversion_report.csv`.
