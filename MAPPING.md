# Legacy Lightroom → RapidRAW mapping notes

This document summarizes the main mappings used by RapidRAW Preset Migrator v1.0.0. They are intentionally conservative and may evolve with RapidRAW.

## Direct or near-direct mappings

| Legacy Lightroom key | RapidRAW target | Notes |
|---|---|---|
| `Exposure2012` | `exposure` | direct |
| `Contrast2012` | `contrast` | direct |
| `Highlights2012` | `highlights` | direct |
| `Shadows2012` | `shadows` | empirical scale ×1.5 |
| `Whites2012` | `whites` | direct |
| `Blacks2012` | `blacks` | direct |
| `Clarity2012` | `clarity` | direct |
| `Vibrance` | `vibrance` | direct |
| `Saturation` | `saturation` | direct |
| HSL saturation/luminance | RapidRAW HSL | direct |
| HSL hue | RapidRAW HSL hue | empirical scale ×0.75 |
| `ToneCurvePV2012*` | point curves | luma/R/G/B |
| `GrainAmount` | grain amount | direct |
| `GrainSize` | grain size | direct |
| `GrainFrequency` | grain roughness | approximate semantic mapping |
| `Sharpness` | sharpness | 0–150 mapped to 0–100 |
| Split Toning | Color Grading | highlights/shadows + balance |
| RGB calibration | color calibration | where RapidRAW exposes an equivalent |

## Black and white fallback

Without a selected DCP, `ConvertToGrayscale` is represented as saturation -100 and Lightroom `GrayMixer*` values are approximated through RapidRAW HSL luminance controls.

## Camera Profile Library and DCP-aware mode

The initial `.lrtemplate` conversion never permanently selects a DCP. Instead, v1.0 stores the Lightroom CameraProfile requirement plus the original color/B&W preparation metadata in the migration catalog.

The HTML manager scans `CameraProfiles/` recursively. A DCP is offered only if its internal `ProfileName` exactly matches the CameraProfile requested by that preset. Camera-specific files with the same ProfileName remain separate dropdown choices.

When a DCP is selected, the manager generates the companion LUT on demand.

For color presets, the companion is deliberately subtle and uses the creative DCP tables/tone contribution rather than the camera input matrices.

For B&W presets, color is restored before the LUT stage and the companion combines:

1. a conservative fraction of the DCP creative color tables;
2. the legacy Lightroom GrayMixer response;
3. monochrome conversion;
4. a very small contribution from the DCP profile tone curve.

This workflow was tuned empirically for preservation of legacy film-preset intent; it is not an Adobe DCP rendering clone.

## Camera matrices

The migrator intentionally does **not** transplant DCP `ColorMatrix`/`ForwardMatrix` input-camera calibration into LUTs for unrelated cameras. RapidRAW remains responsible for rendering the actual camera RAW.

## Intentionally unsupported / unsafe mappings

Examples include settings whose semantics do not match RapidRAW closely enough, such as some lens/perspective controls, detailed sharpening sub-controls and absolute legacy white-balance temperature/tint values.

These appear in the conversion report rather than being silently forced into an unrelated RapidRAW control.
