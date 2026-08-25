# RapidRAW Preset Migrator

**Unofficial community tool for migrating legacy Adobe Lightroom `.lrtemplate` presets to RapidRAW.**

RapidRAW Preset Migrator converts old Lightroom Develop presets into RapidRAW `.rrpreset` files and provides a local browser-based manager for selecting, favoriting and safely synchronizing migrated presets with RapidRAW.

A central feature of v1.0 is the **Camera Profile Library**: users can place their own DNG Camera Profile (`.dcp`) files in `CameraProfiles/` at any time. The Preset Manager scans that folder automatically, offers exact profile matches in a per-preset dropdown, and generates companion `.cube` LUTs only when a profile is actually selected for import.

> **Important:** This tool does not include or redistribute Lightroom presets, DCP profiles, commercial film profiles, LUT packs, or RapidRAW itself. You provide your own files and are responsible for having the right to use them.

## Highlights

- Batch conversion of legacy `.lrtemplate` files from folders or ZIP archives
- Preserves preset folder structure
- Converts common tone, HSL, point-curve, parametric-curve, grain, sharpening and color-grading settings
- Safe self-contained fallback preset for every successfully parsed preset
- **Live `CameraProfiles/` library** with recursive folder scanning
- Per-preset dropdown for exact matching DCP profiles and camera variants
- Add/remove DCP files later **without reconverting the `.lrtemplate` collection**
- Companion LUTs generated on demand and cached by profile/recipe hash
- DCP-aware black-and-white workflow with legacy Lightroom GrayMixer support
- HTML Preset Manager with search, filters, favorites and profile-library overview
- Migrated RapidRAW entries are prefixed with **`[MIG]`**
- Remove all migrated presets without touching presets created directly in RapidRAW
- Automatic backup of RapidRAW's `presets.json` before changes
- Windows, native Linux and Linux Flatpak path detection
- No third-party Python packages required

## Compatibility

v1.0.0 was prepared against the RapidRAW preset format used by **RapidRAW v1.6.2** and tested in the development workflow on Windows 11 and Nobara Linux with the RapidRAW Flatpak build.

RapidRAW is under active development. If its internal preset schema changes, use the optional `--template` argument with a freshly exported RapidRAW preset or check for a newer migrator release.

## Requirements

- Python **3.10 or newer**
- RapidRAW installed if you want to use the Preset Manager
- Your own `.lrtemplate` presets
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

## Camera Profile Library

The generated output contains:

```text
CameraProfiles/
  README.txt
  ...your own .dcp files...
```

The manager recursively watches/scans this folder. When files change, only changed/new profiles are parsed again.

For each legacy preset, the dropdown shows:

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

A normal input can be only your Lightroom presets:

```text
MyLegacyPresets/
  Color/
    My Look.lrtemplate
  Black and White/
    My B&W.lrtemplate
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

Third-party `.lrtemplate`, `.dcp`, `.cube` and commercial preset/profile files can have their own licenses. **Do not redistribute files you do not have permission to redistribute.**

See [DISCLAIMER.md](DISCLAIMER.md).

## License

The code in RapidRAW Preset Migrator is released under the **MIT License**. See [LICENSE](LICENSE).

## Development / smoke tests

```bash
python -m unittest discover -s tests -v
```
