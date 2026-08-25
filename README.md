# RapidRAW Preset Migrator

**Unofficial community tool for migrating Adobe Lightroom `.lrtemplate` and `.xmp` presets to RapidRAW.**

RapidRAW Preset Migrator converts legacy `.lrtemplate` and modern `.xmp` Lightroom Develop presets into RapidRAW `.rrpreset` files and provides a local browser-based manager for selecting, favoriting and safely synchronizing migrated presets with RapidRAW.

A central feature of v1.0 is the **Camera Profile Library**: users can place their own DNG Camera Profile (`.dcp`) files in `CameraProfiles/` at any time. The Preset Manager scans that folder automatically, offers exact profile matches in a per-preset dropdown, and generates companion `.cube` LUTs only when a profile is actually selected for import.

> **Important:** This tool does not include or redistribute Lightroom presets, DCP profiles, commercial film profiles, LUT packs, or RapidRAW itself. You provide your own files and are responsible for having the right to use them.

> **Look migration, not a 1:1 clone:** Lightroom/Adobe Camera Raw and RapidRAW use different RAW engines and processing pipelines. The migrator therefore aims to preserve the visual intent and character of a preset as closely as practical; pixel-identical or mathematically identical rendering is not promised. Approximate mappings and unsupported settings are called out in `conversion_report.csv`.

## Highlights

- Batch conversion of legacy `.lrtemplate` **and modern `.xmp`** files from individual files, folders or ZIP archives
- Preserves preset folder structure
- Converts common tone, HSL, point-curve, parametric-curve, grain, sharpening, Texture/Structure and modern color-grading settings
- Safe self-contained fallback preset for every successfully parsed preset
- **Live `CameraProfiles/` library** with recursive folder scanning
- Per-preset dropdown for exact matching DCP profiles and camera variants
- Add/remove DCP files later **without reconverting the Lightroom preset collection**
- Companion LUTs generated on demand and cached by profile/recipe hash
- DCP-aware black-and-white workflow with legacy Lightroom GrayMixer support
- HTML Preset Manager with search, filters, favorites and profile-library overview
- Migrated RapidRAW entries are prefixed with **`[MIG]`**
- Remove all migrated presets without touching presets created directly in RapidRAW
- Automatic backup of RapidRAW's `presets.json` before changes
- Windows, native Linux and Linux Flatpak path detection
- XMP masks/adaptive/local edits and unsupported creative XMP profiles are explicitly reported instead of silently dropped
- Preset Manager shows and filters the source format (`XMP` / `lrtemplate`)
- No third-party Python packages required

## Compatibility

v1.0.0 was prepared against the RapidRAW preset format used by **RapidRAW v1.6.2** and tested in the development workflow on Windows 11 and Nobara Linux with the RapidRAW Flatpak build.

RapidRAW is under active development. If its internal preset schema changes, use the optional `--template` argument with a freshly exported RapidRAW preset or check for a newer migrator release.

## Requirements

- Python **3.10 or newer**
- RapidRAW installed if you want to use the Preset Manager
- Your own `.lrtemplate` and/or `.xmp` presets
- Optional: your own `.dcp` camera profiles

## Quick start — Windows

1. Extract the release ZIP.
2. Double-click `Start_Converter_Windows.bat`.
3. Select your preset ZIP/folder and an output folder.
4. Convert.
5. Open the generated output folder.
6. Put any DCP files you own into its `CameraProfiles/` folder (subfolders are supported).
7. Close RapidRAW completely.
8. Double-click `Start_Preset_Manager_Windows.bat`.
9. In the browser, select presets and optionally choose a matching CameraProfile from the dropdown.
10. Click **START – Auswahl in RapidRAW übernehmen**.

## Quick start — Linux / Flatpak

Make the launchers executable once:

```bash
chmod +x Start_Converter_Linux.sh Start_Preset_Manager_Linux.sh
```

Start the converter:

```bash
./Start_Converter_Linux.sh
```

After conversion, open the generated output directory, copy your own `.dcp` files into `CameraProfiles/`, then start:

```bash
./Start_Preset_Manager_Linux.sh
```

For RapidRAW installed through Flatpak, the manager detects the application data directory automatically. Native Linux and a manual `RAPIDRAW_PRESETS_JSON` override are supported too.

## Lightroom XMP support

Version 1.0 supports both Lightroom preset generations:

- legacy `.lrtemplate` presets;
- modern Camera Raw / Lightroom `.xmp` presets.

XMP parsing uses the Camera Raw settings namespace and supports scalar settings plus RGB/luma point curves. Modern Color Grading and `Texture` are mapped where RapidRAW exposes a suitable control. Black-and-white XMP presets use the same tested `ConvertToGrayscale` / GrayMixer fallback and optional DCP-aware workflow as legacy presets.

For modern XMP presets, v1.0 also converts custom white balance relative to the XMP `AsShotTemperature` / `AsShotTint` values where both sides are available. Meaningful Lightroom parametric tone-curve edits are preferred over competing point-curve data because RapidRAW renders one curve mode at a time. Modern Camera Calibration values are conservatively scaled as a cross-engine approximation rather than copied 1:1. These choices are documented in the conversion report.

Some modern XMP features have no safe RapidRAW equivalent. In particular, AI/adaptive masks, local masking structures, Point Color adjustments and custom Creative XMP profile/look references are **reported in `conversion_report.csv` rather than silently discarded**. The migrator does not attempt to recreate Adobe's masking engine.

## Camera Profile Library

The generated output contains:

```text
CameraProfiles/
  README.txt
  ...your own .dcp files...
```

The manager recursively watches/scans this folder. When files change, only changed/new profiles are parsed again.

For each Lightroom preset that references a DCP CameraProfile, the dropdown shows:

- **Standard / ohne DCP** — always available and self-contained;
- one or more DCP choices **only when the internal DCP ProfileName exactly matches the CameraProfile requested by the Lightroom preset**.

If several camera-specific DCP files share the same profile name, all of those bodies are shown separately. The tool does not guess which camera variant you intended.

Your dropdown choices are stored in `migration_manager_state.json`, so they survive removing `[MIG]` presets from RapidRAW.

### On-demand LUT generation

When a DCP choice is selected and synchronized:

1. the manager reads that user-provided DCP;
2. it uses only the creative profile data relevant to the companion look;
3. it does **not** transplant camera input ColorMatrix/ForwardMatrix calibration to another camera;
4. it generates a `.cube` companion LUT into RapidRAW's migration LUT directory;
5. the LUT is cached and reused while its profile/recipe hash remains unchanged.

For black-and-white presets, the manager restores color until the LUT stage so the legacy GrayMixer can react to the original colors before monochrome conversion.

## Input layout

A normal input can contain legacy and/or modern Lightroom presets:

```text
MyLegacyPresets/
  Color/
    My Legacy Look.lrtemplate
    My Modern Look.xmp
  Black and White/
    My B&W.xmp
```

If an input ZIP/folder already contains `.dcp` files, v1.0 can seed them into the generated `CameraProfiles/` library for convenience. A separate DCP folder can also be selected during conversion, but this is optional; profiles can always be added later.

## Output layout

```text
RapidRAW_Migrated_Presets/
  CameraProfiles/
  Presets_Fallback/
  camera_profile_requirements.csv
  conversion_report.csv
  migration_dcp_prep.json
  migration_summary.json
  migration_catalog.json
  RapidRAW_Preset_Manager.html
  preset_manager.py
  dcp_support.py
  Start_Preset_Manager_Windows.bat
  Start_Preset_Manager_Linux.sh
```

## Preset Manager and `[MIG]`

The manager edits RapidRAW's central `presets.json`, so it uses strict separation:

- presets written by this tool begin with **`[MIG]`**;
- native RapidRAW presets are preserved;
- synchronization replaces only previous `[MIG]` entries;
- **Remove all `[MIG]`** deletes only migrated entries;
- favorites are stored separately and mirrored into `[MIG] Favoriten`;
- CameraProfile dropdown choices are stored separately and survive removal of migrated presets;
- every write creates a backup first;
- the manager refuses to write while RapidRAW is running.

## CLI

```bash
python rapidraw_preset_migrator.py INPUT -o OUTPUT
```

Useful options:

```text
--dcp PATH       Optional DCP folder/ZIP/.dcp used only to seed CameraProfiles/
--template FILE  Fresh .rrpreset exported by RapidRAW to use as schema baseline
--grid 17|33|65  Companion LUT grid size metadata/default; current manager uses 33 by default
```

Example:

```bash
python rapidraw_preset_migrator.py Templates.zip -o RapidRAW_Migrated_Presets
```

Then copy your own profiles into:

```text
RapidRAW_Migrated_Presets/CameraProfiles/
```

## What this tool does **not** promise

This is **not** an Adobe rendering-engine emulator. Lightroom and RapidRAW use different RAW engines and control semantics. The goal is to preserve the creative intent of legacy presets as closely and transparently as practical.

Camera input matrices from DCP files are not transplanted to unrelated cameras. Unsupported or ambiguous data is reported instead of silently guessed whenever possible. See [MAPPING.md](MAPPING.md).

## Legal / trademark note

This is an **unofficial, independent community project** and is not affiliated with, endorsed by, or sponsored by CyberTimon/RapidRAW, Adobe, or any preset/profile vendor.

Third-party `.lrtemplate`, `.xmp`, `.dcp`, `.cube` and commercial preset/profile files can have their own licenses. **Do not redistribute files you do not have permission to redistribute.**

See [DISCLAIMER.md](DISCLAIMER.md).

## License

The code in RapidRAW Preset Migrator is released under the **MIT License**. See [LICENSE](LICENSE).

## Development / smoke tests

```bash
python -m unittest discover -s tests -v
```
