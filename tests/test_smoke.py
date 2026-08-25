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
