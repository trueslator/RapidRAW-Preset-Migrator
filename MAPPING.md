# Lightroom (.lrtemplate / .xmp) → RapidRAW mapping notes

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
| `Texture` | `structure` | near-direct semantic mapping |
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
| `ColorGrade*` | Color Grading | shadows/midtones/highlights/global + blending/balance where present |
| RGB calibration | color calibration | where RapidRAW exposes an equivalent |


## Approximation policy

RapidRAW and Lightroom/Adobe Camera Raw do not share the same RAW engine or rendering pipeline. Mapping values with the same label therefore does not guarantee the same pixels. The project treats conversion as **best-effort look migration**, not as a 1:1 renderer clone. Empirical mappings are documented and flagged in `conversion_report.csv`.

## Modern XMP parsing

`.xmp` presets are parsed from Adobe Camera Raw's `crs` namespace. Scalar settings and `ToneCurvePV2012`, `ToneCurvePV2012Red`, `ToneCurvePV2012Green` and `ToneCurvePV2012Blue` RDF sequences are normalized into the same internal model used for `.lrtemplate`. This means both formats share the same RapidRAW mapping and DCP/GrayMixer handling.

The following XMP structures are deliberately not guessed when no safe equivalent exists:

- AI/adaptive and local masks;
- gradient/brush/radial local corrections;
- Point Color structures;
- custom Creative XMP profile/look references that are not DCP CameraProfile references.

They are surfaced in `conversion_report.csv`.

### XMP white balance

When an XMP contains both target `Temperature` / `Tint` and `AsShotTemperature` / `AsShotTint`, the migrator converts the change to RapidRAW's relative white-balance controls using a mired-based temperature delta and relative tint delta. This is explicitly marked as an approximation. If the needed As-Shot values are absent, no absolute Kelvin value is forced into an unrelated RapidRAW control.

### XMP curve mode

RapidRAW renders one tone-curve mode at a time. If non-zero Lightroom parametric tone values (`ParametricDarks`, `ParametricShadows`, `ParametricLights`, `ParametricHighlights`) are present, v1.0 selects RapidRAW's parametric mode, transfers the split points, and neutralizes competing point curves. If both Lightroom curve systems carry meaningful edits, omitted point-curve data is reported. Otherwise normal Lightroom point curves are used.

### XMP Camera Calibration

Modern XMP Camera Calibration values are not copied 1:1. Cross-engine A/B validation showed that direct values can over-apply the look in RapidRAW, so v1.0 uses a conservative empirical scale and marks those controls as approximate. Legacy `.lrtemplate` calibration remains on the legacy mapping path.

### Vignette distinction

Only Lightroom's **Post-Crop Vignette** is mapped to RapidRAW's creative vignette. Lightroom `VignetteAmount` from the lens/manual correction area is intentionally not mapped 1:1 because it is not semantically equivalent and produced strongly incorrect results in validation.

## Black and white fallback

Without a selected DCP, `ConvertToGrayscale` is represented as saturation -100 and Lightroom `GrayMixer*` values are approximated through RapidRAW HSL luminance controls.

## Camera Profile Library and DCP-aware mode

The initial Lightroom preset conversion never permanently selects a DCP. Instead, v1.0 stores the Lightroom CameraProfile requirement plus the original color/B&W preparation metadata in the migration catalog.

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

Examples include settings whose semantics do not match RapidRAW closely enough, such as some lens/perspective controls and detailed sharpening sub-controls. Absolute white balance is only converted when a safe relative XMP target-vs-As-Shot delta can be derived; otherwise it is reported rather than forced.

These appear in the conversion report rather than being silently forced into an unrelated RapidRAW control.
