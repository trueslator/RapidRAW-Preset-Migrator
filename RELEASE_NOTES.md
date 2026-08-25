# RapidRAW Preset Migrator 1.0.0

First public release — 2026-08-25.

## Highlights

- Migrates legacy Lightroom `.lrtemplate` presets to RapidRAW `.rrpreset`
- Batch processing from folders and ZIP archives
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
