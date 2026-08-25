import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lrtemplate_converter as lc
import dcp_support as ds
import preset_manager as pm


class ConverterSmokeTests(unittest.TestCase):
    def test_parse_and_convert_basic_lrtemplate(self):
        text = r'''s = {
            title = "Synthetic Test",
            type = "Develop",
            value = { settings = {
                Exposure2012 = 1,
                Shadows2012 = 10,
                Saturation = -5,
                ToneCurvePV2012 = { 0, 0, 255, 255, },
            }, },
        }'''
        parsed = lc.parse_lrtemplate(text, "Synthetic.lrtemplate")
        baseline = lc.neutralize_baseline(lc.BUILTIN_BASELINE)
        result = lc.convert(parsed, baseline)
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertEqual(result.name, "Synthetic Test")
        self.assertEqual(adj["exposure"], 1)
        self.assertEqual(adj["shadows"], 15)
        self.assertEqual(adj["saturation"], -5)
        self.assertEqual(result.preset_entry["preset"]["presetType"], "style")

    def test_parse_and_convert_modern_xmp(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/">
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
            crs:PresetType="Normal" crs:Version="15.0" crs:ProcessVersion="11.0"
            crs:Exposure2012="+0.50" crs:Highlights2012="-20" crs:Shadows2012="+10"
            crs:Texture="12" crs:ConvertToGrayscale="True" crs:GrayMixerRed="20"
            crs:ColorGradeMidtoneHue="35" crs:ColorGradeMidtoneSat="15"
            crs:CameraProfile="Embedded">
            <crs:Name><rdf:Alt><rdf:li xml:lang="x-default">Modern XMP Test</rdf:li></rdf:Alt></crs:Name>
            <crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>128, 140</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012>
          </rdf:Description>
        </rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "Modern.xmp")
        self.assertEqual(parsed.name, "Modern XMP Test")
        self.assertEqual(parsed.source_format, "xmp")
        self.assertEqual(parsed.settings["Exposure2012"], 0.5)
        self.assertEqual(parsed.arrays["ToneCurvePV2012"], [0, 0, 128, 140, 255, 255])
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertTrue(result.is_bw)
        self.assertEqual(adj["exposure"], 0.5)
        self.assertEqual(adj["shadows"], 15)
        self.assertEqual(adj["structure"], 12)
        self.assertEqual(adj["saturation"], -100)
        self.assertEqual(adj["hsl"]["reds"]["luminance"], 20)
        self.assertEqual(adj["colorGrading"]["midtones"]["hue"], 35)
        self.assertEqual(adj["colorGrading"]["midtones"]["saturation"], 15)
        self.assertEqual(adj["curves"]["luma"][1], {"x": 128, "y": 140})


    def test_xmp_white_balance_uses_as_shot_relative_mapping(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:Temperature="7327" crs:Tint="13" crs:AsShotTemperature="5450" crs:AsShotTint="1" /></rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "WB.xmp")
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertAlmostEqual(adj["temperature"], 31.336487850850347, places=5)
        self.assertAlmostEqual(adj["tint"], 8.0, places=5)
        self.assertTrue(any("White balance converted" in w for w in result.warnings))

    def test_xmp_meaningful_parametric_curve_wins_over_point_curve(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:ParametricDarks="23" crs:ParametricShadowSplit="10" crs:ParametricMidtoneSplit="59" crs:ParametricHighlightSplit="90"><crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>128, 150</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012></rdf:Description></rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "Curve.xmp")
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertEqual(adj["curveMode"], "parametric")
        self.assertEqual(adj["parametricCurve"]["luma"]["darks"], 23)
        self.assertEqual(adj["parametricCurve"]["luma"]["split1"], 10)
        self.assertEqual(adj["pointCurves"]["luma"], [{"x":0,"y":0},{"x":255,"y":255}])
        self.assertTrue(any("both point and parametric" in w for w in result.warnings))

    def test_xmp_camera_calibration_is_explicit_approximation(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:RedHue="40" crs:BlueSaturation="20" /></rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "Cal.xmp")
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertAlmostEqual(adj["colorCalibration"]["redHue"], 22.0)
        self.assertAlmostEqual(adj["colorCalibration"]["blueSaturation"], 11.0)
        self.assertIn("RedHue", result.approximate)
        self.assertTrue(any("Camera Calibration scaled" in w for w in result.warnings))

    def test_xmp_manual_vignette_is_not_mapped_as_post_crop_vignette(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:VignetteAmount="-69" crs:VignetteMidpoint="17" crs:PostCropVignetteAmount="-1" /></rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "Vig.xmp")
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        adj = result.preset_entry["preset"]["adjustments"]
        self.assertEqual(adj["vignetteAmount"], -1)
        self.assertIn("VignetteAmount", result.unsupported)

    def test_xmp_masking_is_reported_not_silently_dropped(self):
        text = r'''<x:xmpmeta xmlns:x="adobe:ns:meta/">
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:ProcessVersion="11.0" crs:Exposure2012="1">
            <crs:Name><rdf:Alt><rdf:li xml:lang="x-default">Masked</rdf:li></rdf:Alt></crs:Name>
            <crs:Masking><rdf:Seq><rdf:li><rdf:Description crs:MaskValue="1" /></rdf:li></rdf:Seq></crs:Masking>
          </rdf:Description>
        </rdf:RDF></x:xmpmeta>'''
        parsed = lc.parse_xmp(text, "Masked.xmp")
        self.assertIn("Masking/local adjustments", parsed.features)
        result = lc.convert(parsed, lc.neutralize_baseline(lc.BUILTIN_BASELINE))
        self.assertIn("Masking/local adjustments", result.unsupported)
        self.assertTrue(any("not migrated" in w for w in result.warnings))

    def test_mixed_folder_scans_lrtemplate_and_xmp(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "A.lrtemplate").write_text('s={title="A",value={settings={Exposure2012=1,},},}', encoding="utf-8")
            (root / "B.xmp").write_text('''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" crs:Exposure2012="2"><crs:Name><rdf:Alt><rdf:li xml:lang="x-default">B</rdf:li></rdf:Alt></crs:Name></rdf:Description></rdf:RDF></x:xmpmeta>''', encoding="utf-8")
            items = list(lc.iter_inputs(str(root)))
            self.assertEqual([x[0] for x in items], ["A.lrtemplate", "B.xmp"])

    def test_dcp_auto_does_not_guess_conflicting_camera_looks(self):
        a = ds.DCPProfile(source="a.dcp", camera="Camera A", name="Film X", hsm_dims=(1, 1, 1), hsm1=(0.0, 1.0, 1.0))
        b = ds.DCPProfile(source="b.dcp", camera="Camera B", name="Film X", hsm_dims=(1, 1, 1), hsm1=(5.0, 1.0, 1.0))
        self.assertIsNone(ds.choose_profile([a, b], "Auto"))
        self.assertIs(ds.choose_profile([a, b], "Camera A"), a)

    def test_dcp_auto_accepts_identical_creative_data(self):
        a = ds.DCPProfile(source="a.dcp", camera="Camera A", name="Film X", hsm_dims=(1, 1, 1), hsm1=(0.0, 1.0, 1.0))
        b = ds.DCPProfile(source="b.dcp", camera="Camera B", name="Film X", hsm_dims=(1, 1, 1), hsm1=(0.0, 1.0, 1.0))
        chosen = ds.choose_profile([a, b], "Auto")
        self.assertIsNotNone(chosen)


class ManagerSafetyTests(unittest.TestCase):
    def test_strip_migrated_preserves_native_entries(self):
        native = {"preset": {"id": "native", "name": "Native", "adjustments": {}}}
        migrated = {"preset": {"id": "mig", "name": "[MIG] Imported", "adjustments": {}}}
        folder = {"folder": {"id": "f", "name": "[MIG] Group", "children": [migrated]}}
        kept, removed = pm.strip_migrated([native, migrated, folder])
        self.assertEqual(kept, [native])
        self.assertEqual(removed, 3)

    def test_profile_selection_state_persists_with_favorites(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            catalog={"presets":[{"id":"abc"}]}
            pm.save_favorites(root,catalog,["abc"])
            pm.save_profile_selections(root,catalog,{"abc":"profile123"})
            self.assertEqual(pm.load_favorites(root,catalog),{"abc"})
            self.assertEqual(pm.load_profile_selections(root,catalog),{"abc":"profile123"})

    def test_dynamic_dcp_variant_uses_exact_profile_and_keeps_fallback_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); (root/"Presets_Fallback").mkdir()
            rr={"presets":[{"preset":{"id":"old","name":"Film","adjustments":{"saturation":-100,"hsl":{"red":{"luminance":10}}}}}]}
            (root/"Presets_Fallback"/"Film.rrpreset").write_text(json.dumps(rr),encoding="utf-8")
            row={"id":"cid","name":"Film","group":"Test","bw":True,"cameraProfile":"Film X","fallbackPreset":"Presets_Fallback/Film.rrpreset",
                 "dcpPrep":{"saturation":0,"hslLuminance":{"red":-5},"grayMixer":{"Red":10}}}
            catalog={"presets":[row]}
            profile=ds.DCPProfile(source="x.dcp",camera="Camera A",name="Film X")
            old_scan,old_lut=pm.scan_camera_profiles,pm._dynamic_lut
            try:
                pm.scan_camera_profiles=lambda root: {"internal":{"pid":profile}}
                def fake_lut(root,live,row,profile_id,profile,grid=33):
                    d=live.parent/pm.LUT_SUBDIR; d.mkdir(parents=True,exist_ok=True); f=d/"x.cube"; f.write_text("dummy",encoding="utf-8"); return f,True
                pm._dynamic_lut=fake_lut
                live=root/"live"/"presets.json"; live.parent.mkdir()
                items,created,_,_=pm.build_migrated_items(catalog,root,[{"id":"cid","profileId":"pid"}],live)
                child=items[0]["folder"]["children"][0]
                self.assertTrue(child["name"].startswith("[MIG] Film [DCP]"))
                self.assertEqual(child["adjustments"]["saturation"],0)
                self.assertEqual(child["adjustments"]["hsl"]["red"]["luminance"],-5)
                self.assertEqual(child["adjustments"]["lutName"],"x.cube")
                self.assertEqual(created,1)
            finally:
                pm.scan_camera_profiles,pm._dynamic_lut=old_scan,old_lut


if __name__ == "__main__":
    unittest.main()
