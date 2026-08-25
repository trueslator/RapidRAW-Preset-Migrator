# RapidRAW Preset Migrator

**Migrate Adobe Lightroom presets to RapidRAW on Windows and Linux.**

Convert legacy **`.lrtemplate`** and modern **`.xmp`** Lightroom presets into native RapidRAW presets, manage large preset collections in a local browser interface, and optionally reuse compatible creative data from your own **DNG Camera Profiles (`.dcp`)**.

> **Important:** This project performs a **best-effort look migration**, not a pixel-perfect 1:1 reproduction of Adobe Lightroom. Lightroom and RapidRAW use different RAW engines, color pipelines, tone mapping and parameter interpretations.

[![Latest Release](https://img.shields.io/github/v/release/trueslator/RapidRAW-Preset-Migrator?label=Download)](https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-supported-blue)](#windows)
[![Linux](https://img.shields.io/badge/Linux-supported-green)](#linux--nobara--flatpak)

**[Download the latest release](https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest)**  
**[Deutsche Anleitung](README_DE.md)**

---

## Why this project exists

RapidRAW is a fast, open-source RAW editor for Windows, macOS and Linux.

For photographers moving away from Lightroom, however, one problem can be surprisingly difficult: years of accumulated presets often represent much more than a few slider values. They may contain custom curves, HSL settings, grain, split toning, black-and-white mixes, white balance changes and references to camera profiles.

The RapidRAW Preset Migrator was created to preserve as much of that **creative intent and visual character** as reasonably possible when moving to RapidRAW.

It started as a personal migration project while moving a long-established photography workflow from **Windows 11 and Adobe Lightroom to Nobara Linux and RapidRAW**.

---

## Features

- Convert legacy Lightroom **`.lrtemplate`** presets
- Convert modern Lightroom / Adobe Camera Raw **`.xmp`** presets
- Process single files, folders or ZIP archives
- Preserve folder structure
- Generate native RapidRAW **`.rrpreset`** files
- Detect color and black-and-white presets
- Convert many commonly used Lightroom adjustments
- Handle Lightroom white-balance shifts when the XMP contains usable `AsShot` values
- Support HSL, point curves, parametric curves, grain, split toning / color grading and more
- Report settings that cannot be safely migrated
- Manage hundreds of presets through a local HTML interface
- Mark favorite presets
- Prefix migrated presets with **`[MIG]`**
- Remove all migrated presets without touching presets created directly in RapidRAW
- Automatically back up RapidRAW's `presets.json` before changes
- Detect Windows, native Linux and RapidRAW Flatpak installations
- Optional DCP-based companion LUT generation using **your own** camera-profile files
- Camera Profile Library with matching-profile dropdowns
- Cache generated LUTs to avoid unnecessary regeneration
- No third-party Python packages required

---

## Supported Lightroom preset formats

| Format | Support |
|---|---|
| `.lrtemplate` | ✅ Supported |
| `.xmp` | ✅ Supported |
| Mixed folders / ZIP archives | ✅ Supported |
| DNG Camera Profiles `.dcp` | ✅ Optional, user-supplied |
| AI / adaptive masks | ⚠️ Not reproduced |
| Local masks | ⚠️ Not reproduced |
| Unsupported Lightroom-only features | ⚠️ Reported, not silently ignored |

---

## A note about accuracy

The goal is **look migration**, not emulation of Lightroom's rendering engine.

A preset may contain values that look identical on paper but behave differently in another RAW processor. For example:

- Lightroom and RapidRAW may interpret shadows/highlights differently
- camera calibration is not equivalent between engines
- tone curves can be applied at different stages
- camera profiles may contain sensor-specific calibration data
- lens corrections and vignette parameters may not have direct equivalents
- modern XMP presets can contain masks or adaptive functions RapidRAW does not support

The converter therefore uses a combination of:

1. direct mappings where the semantics are close,
2. scaled or approximated mappings where testing showed that this is more appropriate,
3. explicit warnings where a reliable translation is not possible.

**Always compare important migrated presets visually before relying on them in production.**

---

# Quick start

## 1. Download

Download the latest release:

**https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest**

Extract the ZIP file to a normal folder.

Python **3.10 or newer** is required.

No additional Python packages are needed.

---

## Windows

Start:

```text
Start_Converter_Windows.bat
```

Choose a Lightroom preset, folder or ZIP archive.

After conversion, open the generated output folder and start:

```text
Start_Preset_Manager_Windows.bat
```

Before writing presets into RapidRAW, **close RapidRAW completely**.

---

## Linux / Nobara / Flatpak

Make the launchers executable once:

```bash
chmod +x Start_Converter_Linux.sh Start_Preset_Manager_Linux.sh
```

Start the converter:

```bash
./Start_Converter_Linux.sh
```

After conversion, open the generated output folder and start:

```bash
./Start_Preset_Manager_Linux.sh
```

The manager can automatically detect common RapidRAW locations, including the Flatpak installation.

For example, a RapidRAW Flatpak installation typically stores application data below:

```text
~/.var/app/io.github.CyberTimon.RapidRAW/
```

---

# Preset Manager

The converter generates a local HTML-based Preset Manager.

It allows you to:

- search presets
- filter by source folder
- filter `.lrtemplate` and `.xmp`
- select only the presets you actually want
- mark presets as favorites
- select compatible DCP variants
- synchronize the selected presets with RapidRAW
- remove migrated presets again

All presets written by the manager are prefixed with:

```text
[MIG]
```

This allows the manager to distinguish migrated presets from presets created directly in RapidRAW.

Favorites are also mirrored into a dedicated:

```text
[MIG] Favoriten
```

group.

The manager stores its own selection/favorite state separately, so removing `[MIG]` presets from RapidRAW does not erase your favorite selections.

---

# Camera Profile Library

Some Lightroom presets reference a DNG Camera Profile (`.dcp`).

The migrator does **not** ship Adobe, VSCO or other third-party camera profiles.

If you legally own compatible `.dcp` files, copy them into:

```text
CameraProfiles/
```

Subfolders are allowed.

The Preset Manager scans the library and, when a preset references a matching Camera Profile, displays compatible variants in a dropdown.

Example:

```text
Kodak Portra 800 v2C
├── Canon EOS 5D Mark II
├── Canon EOS 5D Mark III
├── Canon EOS 6D
└── ...
```

If several camera-specific profiles exist, the tool deliberately avoids guessing which one you want.

When a DCP variant is selected, the migrator can extract the usable **creative look portion** and generate a companion `.cube` LUT.

Sensor-specific camera calibration matrices are **not blindly transferred to another camera**.

Generated LUTs are cached and reused.

---

## What happens when no DCP is available?

Nothing breaks.

The normal converted RapidRAW preset remains available as a fallback.

You can also add DCP files to `CameraProfiles/` later. There is no need to reconvert the original Lightroom presets just because you found more camera profiles afterwards.

---

# What is migrated?

Typical mappings include:

- Exposure
- Contrast
- Highlights
- Shadows
- Whites
- Blacks
- Texture / Structure
- Clarity
- Dehaze
- Vibrance
- Saturation
- HSL
- Luma / RGB point curves
- Parametric curves where applicable
- Grain
- Split toning / color grading
- black-and-white mixer approximations
- white-balance shifts in supported XMP cases
- selected camera-calibration values as an approximation

For implementation details and known limitations, see:

**[MAPPING.md](MAPPING.md)**

---

# Conversion reports

The output can include reports describing what happened during migration.

Depending on the input, these can contain information such as:

- source format
- referenced Camera Profile
- process version
- color / black-and-white detection
- mapped parameters
- approximated parameters
- unsupported settings
- warnings

This is intentional: settings that cannot be represented safely should be **visible**, not silently discarded.

---

# Safety

The Preset Manager is deliberately conservative.

Before modifying RapidRAW data it:

- creates a backup of `presets.json`
- refuses to write while RapidRAW is running
- only manages entries marked with `[MIG]`
- leaves native RapidRAW presets untouched

Even so, this is an independent community tool.

Keep backups of important Lightroom presets, camera profiles and RapidRAW configuration data.

---

# Privacy

Preset conversion happens locally on your computer.

The tool does not require your Lightroom presets or Camera Profiles to be uploaded anywhere.

---

# Third-party presets and Camera Profiles

This repository does **not** contain:

- commercial Lightroom presets
- VSCO profiles
- Adobe Camera Profiles
- third-party DCP files
- generated LUTs derived from third-party profiles

You are responsible for ensuring that you are allowed to use any presets or Camera Profiles you supply to the tool.

Converting a preset or profile for personal use does not automatically grant redistribution rights.

See:

- [DISCLAIMER.md](DISCLAIMER.md)
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

---

# Project files

```text
RapidRAW-Preset-Migrator/
├── rapidraw_preset_migrator.py
├── lrtemplate_converter.py
├── dcp_support.py
├── preset_manager.py
├── Start_Converter_Windows.bat
├── Start_Converter_Linux.sh
├── Start_Preset_Manager_Windows.bat
├── Start_Preset_Manager_Linux.sh
├── README.md
├── README_DE.md
├── MAPPING.md
├── DISCLAIMER.md
├── THIRD_PARTY_NOTICES.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── LICENSE
└── tests/
```

---

# Testing

The project contains automated smoke and safety tests covering key migration paths, including:

- `.lrtemplate`
- `.xmp`
- black-and-white presets
- tone curves
- Camera Profile matching
- preset-manager safety behavior
- preservation of native RapidRAW presets

Real-world testing has also been performed with a Lightroom archive containing hundreds of legacy presets and hundreds of DCP profiles.

---

# RapidRAW

RapidRAW itself is a separate open-source project by CyberTimon.

RapidRAW:

**https://github.com/CyberTimon/RapidRAW**

Flathub:

**https://flathub.org/apps/io.github.CyberTimon.RapidRAW**

This project is **not affiliated with or endorsed by Adobe or the RapidRAW project**.

Adobe, Lightroom and Camera Raw are trademarks of their respective owners.

---

# Contributing

Bug reports, sample presets that expose mapping problems, documentation improvements and pull requests are welcome.

Please **do not attach commercial presets or proprietary Camera Profiles** to public issues unless you have the right to redistribute them.

See:

**[CONTRIBUTING.md](CONTRIBUTING.md)**

---

# License

RapidRAW Preset Migrator is released under the **MIT License**.

See [LICENSE](LICENSE).

---

## Final reminder

> **A migrated preset is an approximation of the original Lightroom look, not a guaranteed 1:1 reproduction.**

If the migrated version preserves the creative intent and gives you a useful starting point in RapidRAW, the migration has done its job.
