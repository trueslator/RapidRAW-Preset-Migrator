#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RapidRAW Preset Migrator: legacy Lightroom .lrtemplate -> RapidRAW .rrpreset converter
Compatible with the RapidRAW preset schema tested through RapidRAW v1.6.2 (2026-08-25).
Standard-library only; works as GUI or CLI.

Usage GUI:
    python lrtemplate_converter.py

Usage CLI:
    python lrtemplate_converter.py INPUT --output OUTPUT_DIR
    python lrtemplate_converter.py Templates.zip --output converted --combined

Optional: supply a fresh RapidRAW preset exported by your installed version:
    --template RapidRAW_reference.rrpreset
The converter then uses that preset's adjustment structure as its baseline.
"""
from __future__ import annotations
import argparse, copy, csv, io, json, math, os, pathlib, re, shutil, sys, tempfile, uuid, zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

BUILTIN_BASELINE = {'blacks': -32, 'brightness': 0, 'centré': 0, 'chromaticAberrationBlueYellow': 0, 'chromaticAberrationRedCyan': 0, 'clarity': 0, 'colorCalibration': {'blueHue': 0, 'blueSaturation': 0, 'greenHue': 0, 'greenSaturation': 0, 'redHue': 0, 'redSaturation': 0, 'shadowsTint': 0}, 'colorGrading': {'balance': 0, 'blending': 50, 'global': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'highlights': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'midtones': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'shadows': {'hue': 0, 'luminance': 0, 'saturation': 0}}, 'colorNoiseReduction': 0, 'contrast': 0, 'curveMode': 'point', 'curves': {'blue': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}], 'green': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}], 'luma': [{'x': 0, 'y': 0}, {'x': 98.18181818181816, 'y': 77.72727272727272}, {'x': 167.72727272727272, 'y': 181.36363636363637}, {'x': 255, 'y': 255}], 'red': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}]}, 'dehaze': 0, 'exposure': 0, 'flareAmount': 0, 'glowAmount': 0, 'grainAmount': 0, 'grainRoughness': 50, 'grainSize': 25, 'halationAmount': 0, 'highlights': -42, 'hsl': {'aquas': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'blues': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'greens': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'magentas': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'oranges': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'purples': {'hue': 0, 'luminance': 0, 'saturation': 0}, 'reds': {'hue': 0, 'luminance': 0, 'saturation': -17}, 'yellows': {'hue': 0, 'luminance': 0, 'saturation': 0}}, 'hue': 0, 'lumaNoiseReduction': 0, 'lutData': None, 'lutIntensity': 100, 'lutName': None, 'lutPath': None, 'lutSize': 0, 'parametricCurve': {'blue': {'blackLevel': 0, 'darks': 0, 'highlights': 0, 'lights': 0, 'shadows': 0, 'split1': 25, 'split2': 50, 'split3': 75, 'whiteLevel': 0}, 'green': {'blackLevel': 0, 'darks': 0, 'highlights': 0, 'lights': 0, 'shadows': 0, 'split1': 25, 'split2': 50, 'split3': 75, 'whiteLevel': 0}, 'luma': {'blackLevel': 0, 'darks': 0, 'highlights': 0, 'lights': 0, 'shadows': 0, 'split1': 25, 'split2': 50, 'split3': 75, 'whiteLevel': 0}, 'red': {'blackLevel': 0, 'darks': 0, 'highlights': 0, 'lights': 0, 'shadows': 0, 'split1': 25, 'split2': 50, 'split3': 75, 'whiteLevel': 0}}, 'pointCurves': {'blue': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}], 'green': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}], 'luma': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}], 'red': [{'x': 0, 'y': 0}, {'x': 255, 'y': 255}]}, 'saturation': -5, 'shadows': 23, 'sharpness': 5, 'sharpnessThreshold': 15, 'structure': 0, 'temperature': -0.8771456885564862, 'tint': -3.7248294969164473, 'toneMapper': 'basic', 'vibrance': 7, 'vignetteAmount': 0, 'vignetteFeather': 50, 'vignetteMidpoint': 50, 'vignetteRoundness': 0, 'whites': 6}

SCALAR_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*,?\s*$', re.M)
ARRAY_START_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*\{\s*$', re.M)

COLOR_MAP = {
    'Red':'reds','Orange':'oranges','Yellow':'yellows','Green':'greens',
    'Aqua':'aquas','Blue':'blues','Purple':'purples','Magenta':'magentas'
}

METADATA_KEYS = {
    'EnableCalibration','EnableColorAdjustments','EnableDetail','EnableEffects',
    'EnableGradientBasedCorrections','EnableCircularGradientBasedCorrections',
    'EnableGrayscaleMix','EnableSplitToning','EnableLensCorrections','EnableVignettes',
    'ToneCurveName2012','ToneCurveName','ProcessVersion','CameraProfile','WhiteBalance',
    'AutoBrightness','AutoContrast','AutoExposure','AutoShadows','AutoTone','orientation',
    'LensProfileSetup','LensProfileEnable','CropConstrainToWarp',
}

UNSUPPORTED_ALWAYS = {
    'LensManualDistortionAmount','PerspectiveHorizontal','PerspectiveRotate','PerspectiveScale',
    'PerspectiveVertical','Defringe','PostCropVignetteHighlightContrast','PostCropVignetteStyle',
    'ColorNoiseReductionDetail','ColorNoiseReductionSmoothness',
    'LuminanceNoiseReductionContrast','LuminanceNoiseReductionDetail',
    'SharpenRadius','SharpenDetail', 'AutoLateralCA',
}

@dataclass
class ParsedPreset:
    source: str
    name: str
    settings: Dict[str, Any]
    arrays: Dict[str, List[float]]

@dataclass
class ConversionResult:
    source: str
    name: str
    preset_entry: Dict[str, Any]
    process_version: str = ''
    camera_profile: str = ''
    is_bw: bool = False
    mapped: List[str] = field(default_factory=list)
    approximate: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _find_matching_brace(text: str, open_pos: int) -> int:
    depth=0; in_string=False; esc=False
    for i in range(open_pos, len(text)):
        ch=text[i]
        if in_string:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': in_string=False
            continue
        if ch=='"': in_string=True
        elif ch=='{': depth += 1
        elif ch=='}':
            depth -= 1
            if depth==0: return i
    raise ValueError('Unbalanced braces')


def _parse_value(raw: str) -> Any:
    raw=raw.strip().rstrip(',').strip()
    if raw.startswith('"') and raw.endswith('"'):
        s=raw[1:-1]
        return bytes(s, 'utf-8').decode('unicode_escape', errors='replace') if '\\' in s else s
    low=raw.lower()
    if low=='true': return True
    if low=='false': return False
    if low=='nil': return None
    try:
        if re.fullmatch(r'[-+]?\d+', raw): return int(raw)
        if re.fullmatch(r'[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?', raw): return float(raw)
    except Exception: pass
    return raw


def parse_lrtemplate(text: str, source: str) -> ParsedPreset:
    title_match=re.search(r'^\s*title\s*=\s*"([^"]*)"', text, re.M)
    internal_match=re.search(r'^\s*internalName\s*=\s*"([^"]*)"', text, re.M)
    name=(title_match.group(1) if title_match else (internal_match.group(1) if internal_match else pathlib.Path(source).stem))
    sm=re.search(r'\bsettings\s*=\s*\{', text)
    if not sm: raise ValueError('No settings table found')
    open_pos=text.find('{',sm.start())
    close_pos=_find_matching_brace(text,open_pos)
    block=text[open_pos+1:close_pos]

    arrays={}
    # Capture direct child arrays (tone curves). Remove their ranges before scalar parsing.
    spans=[]
    for m in ARRAY_START_RE.finditer(block):
        key=m.group(1)
        op=block.find('{',m.start())
        try: cl=_find_matching_brace(block,op)
        except ValueError: continue
        raw=block[op+1:cl]
        vals=[]
        for token in re.findall(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',raw):
            try: vals.append(float(token) if any(c in token for c in '.eE') else int(token))
            except: pass
        arrays[key]=vals
        spans.append((m.start(),cl+1))
    chars=list(block)
    for a,b in spans:
        for i in range(a,min(b,len(chars))): chars[i]=' '
    scalar_block=''.join(chars)
    settings={}
    for m in SCALAR_RE.finditer(scalar_block):
        k=m.group(1); raw=m.group(2)
        if '{' in raw or '}' in raw: continue
        settings[k]=_parse_value(raw)
    return ParsedPreset(source=source,name=name,settings=settings,arrays=arrays)


def neutralize_baseline(a: Dict[str,Any]) -> Dict[str,Any]:
    a=copy.deepcopy(a)
    zero_keys=['blacks','brightness','centré','chromaticAberrationBlueYellow','chromaticAberrationRedCyan','clarity',
               'colorNoiseReduction','contrast','dehaze','exposure','flareAmount','glowAmount','grainAmount','halationAmount',
               'highlights','hue','lumaNoiseReduction','saturation','shadows','sharpness','structure','temperature','tint',
               'vibrance','vignetteAmount','vignetteRoundness','whites']
    for k in zero_keys:
        if k in a: a[k]=0
    defaults={'grainRoughness':50,'grainSize':25,'lutIntensity':100,'lutSize':0,'sharpnessThreshold':15,
              'vignetteFeather':50,'vignetteMidpoint':50}
    for k,v in defaults.items():
        if k in a: a[k]=v
    for k in ('lutData','lutName','lutPath'):
        if k in a: a[k]=None
    if 'toneMapper' in a: a['toneMapper']='basic'
    if 'curveMode' in a: a['curveMode']='point'
    if isinstance(a.get('colorCalibration'),dict):
        for k in a['colorCalibration']: a['colorCalibration'][k]=0
    if isinstance(a.get('colorGrading'),dict):
        cg=a['colorGrading']; cg['balance']=0; cg['blending']=50
        for zone in ('global','highlights','midtones','shadows'):
            if isinstance(cg.get(zone),dict):
                for k in cg[zone]: cg[zone][k]=0
    if isinstance(a.get('hsl'),dict):
        for c in a['hsl'].values():
            if isinstance(c,dict):
                for k in c: c[k]=0
    identity=[{'x':0,'y':0},{'x':255,'y':255}]
    for container in ('curves','pointCurves'):
        if isinstance(a.get(container),dict):
            for ch in a[container]: a[container][ch]=copy.deepcopy(identity)
    if isinstance(a.get('parametricCurve'),dict):
        for ch,d in a['parametricCurve'].items():
            if isinstance(d,dict):
                for k in d:
                    d[k] = {'split1':25,'split2':50,'split3':75}.get(k,0)
    return a

def load_baseline(template_path: Optional[str]) -> Dict[str,Any]:
    if not template_path: return neutralize_baseline(BUILTIN_BASELINE)
    data=json.load(open(template_path,encoding='utf-8'))
    try: return neutralize_baseline(data['presets'][0]['preset']['adjustments'])
    except Exception as e: raise ValueError('Template is not a valid RapidRAW .rrpreset with presets[0].preset.adjustments') from e


def clamp(v, lo, hi): return max(lo,min(hi,v))

def num(settings,key,default=None):
    v=settings.get(key,default)
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) else default

def setv(adj:Dict[str,Any], path:Tuple[str,...], value:Any, result:ConversionResult, source_key:str, approx=False):
    cur=adj
    for p in path[:-1]:
        if p not in cur or not isinstance(cur[p],dict): return False
        cur=cur[p]
    if path[-1] not in cur: return False
    cur[path[-1]]=value
    (result.approximate if approx else result.mapped).append(source_key)
    return True

def curve_points(vals: List[float]) -> List[Dict[str,float]]:
    if len(vals)<4 or len(vals)%2: return []
    return [{'x':vals[i],'y':vals[i+1]} for i in range(0,len(vals),2)]


def convert(parsed:ParsedPreset, baseline:Dict[str,Any]) -> ConversionResult:
    s=parsed.settings; a=copy.deepcopy(baseline)
    r=ConversionResult(source=parsed.source,name=parsed.name,preset_entry={})
    r.process_version=str(s.get('ProcessVersion',''))
    r.camera_profile=str(s.get('CameraProfile','') or '')
    r.is_bw=bool(s.get('ConvertToGrayscale',False))

    # Basic modern process mappings
    direct={
        'Exposure2012':('exposure',),'Contrast2012':('contrast',),'Highlights2012':('highlights',),
        'Whites2012':('whites',),'Blacks2012':('blacks',),'Clarity2012':('clarity',),
        'Dehaze':('dehaze',),'Vibrance':('vibrance',),'Saturation':('saturation',),
        'ColorNoiseReduction':('colorNoiseReduction',),'LuminanceSmoothing':('lumaNoiseReduction',),
    }
    for k,p in direct.items():
        v=num(s,k)
        if v is not None: setv(a,p,v,r,k)
    v=num(s,'Shadows2012')
    if v is not None: setv(a,('shadows',),v*1.5,r,'Shadows2012')

    # Legacy PV 2003/2010 approximations
    if num(s,'Exposure2012') is None and num(s,'Exposure') is not None:
        setv(a,('exposure',),num(s,'Exposure'),r,'Exposure',True)
    if num(s,'Contrast2012') is None and num(s,'Contrast') is not None:
        setv(a,('contrast',),num(s,'Contrast'),r,'Contrast',True)
    if num(s,'Clarity2012') is None and num(s,'Clarity') is not None:
        setv(a,('clarity',),num(s,'Clarity'),r,'Clarity',True)
    if num(s,'Brightness') is not None:
        setv(a,('brightness',),num(s,'Brightness')-50,r,'Brightness',True)
    if num(s,'HighlightRecovery') is not None and num(s,'Highlights2012') is None:
        setv(a,('highlights',),-num(s,'HighlightRecovery'),r,'HighlightRecovery',True)
    if num(s,'FillLight') is not None and num(s,'Shadows2012') is None:
        setv(a,('shadows',),num(s,'FillLight')*1.5,r,'FillLight',True)
    if num(s,'Shadows') is not None and num(s,'Blacks2012') is None:
        # Legacy Lightroom calls the Blacks slider "Shadows"; neutral was about 5.
        setv(a,('blacks',),-(num(s,'Shadows')-5),r,'Shadows (legacy Blacks)',True)

    # HSL
    for src_color,dst_color in COLOR_MAP.items():
        hv=num(s,'HueAdjustment'+src_color)
        sv=num(s,'SaturationAdjustment'+src_color)
        lv=num(s,'LuminanceAdjustment'+src_color)
        if hv is not None: setv(a,('hsl',dst_color,'hue'),hv*0.75,r,'HueAdjustment'+src_color)
        if sv is not None: setv(a,('hsl',dst_color,'saturation'),sv,r,'SaturationAdjustment'+src_color)
        if lv is not None: setv(a,('hsl',dst_color,'luminance'),lv,r,'LuminanceAdjustment'+src_color)

    # B&W: reliable fallback without a camera-profile LUT.
    if r.is_bw:
        setv(a,('saturation',),-100,r,'ConvertToGrayscale',True)
        for src_color,dst_color in COLOR_MAP.items():
            gv=num(s,'GrayMixer'+src_color)
            if gv is not None: setv(a,('hsl',dst_color,'luminance'),gv,r,'GrayMixer'+src_color,True)
        r.warnings.append('B&W converted via Saturation -100 + HSL luminance mixer; DCP-aware LUT conversion can be closer for film profiles.')

    # Calibration (present in current RapidRAW schema)
    calmap={'RedHue':'redHue','RedSaturation':'redSaturation','GreenHue':'greenHue','GreenSaturation':'greenSaturation',
            'BlueHue':'blueHue','BlueSaturation':'blueSaturation','ShadowTint':'shadowsTint'}
    for sk,dk in calmap.items():
        v=num(s,sk)
        if v is not None: setv(a,('colorCalibration',dk),v,r,sk)

    # Split toning -> color grading
    cg={'SplitToningBalance':('balance',),
        'SplitToningHighlightHue':('highlights','hue'),'SplitToningHighlightSaturation':('highlights','saturation'),
        'SplitToningShadowHue':('shadows','hue'),'SplitToningShadowSaturation':('shadows','saturation')}
    for sk,tail in cg.items():
        v=num(s,sk)
        if v is not None: setv(a,('colorGrading',)+tail,v,r,sk)

    # Grain
    for sk,dk in [('GrainAmount','grainAmount'),('GrainSize','grainSize'),('GrainFrequency','grainRoughness')]:
        v=num(s,sk)
        if v is not None: setv(a,(dk,),v,r,sk)

    # Sharpness: amount and masking only exist in sampled schema
    v=num(s,'Sharpness')
    if v is not None: setv(a,('sharpness',),v/150*100,r,'Sharpness')
    # SharpenEdgeMasking is deliberately NOT mapped to RapidRAW's current
    # sharpnessThreshold: despite similar names, they are not equivalent.
    # Keeping RapidRAW's baseline threshold produced more reliable migration results in validation tests.
    if num(s,'SharpenEdgeMasking') not in (None,0):
        r.unsupported.append('SharpenEdgeMasking')

    # Vignette: prefer post-crop variant
    vig=num(s,'PostCropVignetteAmount')
    if vig is None: vig=num(s,'VignetteAmount')
    if vig is not None: setv(a,('vignetteAmount',),vig,r,'PostCropVignetteAmount' if 'PostCropVignetteAmount' in s else 'VignetteAmount')
    for sk,dk in [('PostCropVignetteMidpoint','vignetteMidpoint'),('PostCropVignetteFeather','vignetteFeather'),('PostCropVignetteRoundness','vignetteRoundness')]:
        v=num(s,sk)
        if v is not None: setv(a,(dk,),v,r,sk)

    # Chromatic aberration legacy approximation
    v=num(s,'ChromaticAberrationR')
    if v is not None: setv(a,('chromaticAberrationRedCyan',),v,r,'ChromaticAberrationR',True)
    v=num(s,'ChromaticAberrationB')
    if v is not None: setv(a,('chromaticAberrationBlueYellow',),v,r,'ChromaticAberrationB',True)

    # Curves: PV2012 or legacy luma
    ckeys={'ToneCurvePV2012':'luma','ToneCurvePV2012Red':'red','ToneCurvePV2012Green':'green','ToneCurvePV2012Blue':'blue'}
    any_curve=False
    for sk,dk in ckeys.items():
        vals=parsed.arrays.get(sk); pts=curve_points(vals or [])
        if pts and 'curves' in a and dk in a['curves']:
            a['curves'][dk]=copy.deepcopy(pts)
            if 'pointCurves' in a and dk in a['pointCurves']: a['pointCurves'][dk]=copy.deepcopy(pts)
            r.mapped.append(sk); any_curve=True
    if not any_curve:
        pts=curve_points(parsed.arrays.get('ToneCurve',[]))
        if pts and 'curves' in a and 'luma' in a['curves']:
            a['curves']['luma']=copy.deepcopy(pts)
            if 'pointCurves' in a and 'luma' in a['pointCurves']: a['pointCurves']['luma']=copy.deepcopy(pts)
            r.approximate.append('ToneCurve (legacy)'); any_curve=True
    if any_curve and 'curveMode' in a: a['curveMode']='point'

    # Parametric curve: current schema exposes it, so preserve it as well.
    if 'parametricCurve' in a and 'luma' in a['parametricCurve']:
        pcm={'ParametricDarks':'darks','ParametricHighlights':'highlights','ParametricLights':'lights','ParametricShadows':'shadows',
             'ParametricShadowSplit':'split1','ParametricMidtoneSplit':'split2','ParametricHighlightSplit':'split3'}
        for sk,dk in pcm.items():
            v=num(s,sk)
            if v is not None:
                a['parametricCurve']['luma'][dk]=v; r.mapped.append(sk)

    # Absolute legacy WB does not map safely to RapidRAW's relative control.
    for k in ('Temperature','Tint','IncrementalTemperature','IncrementalTint'):
        if k in s and num(s,k) not in (None,0):
            r.unsupported.append(k)
    if any(k in r.unsupported for k in ('Temperature','Tint','IncrementalTemperature','IncrementalTint')):
        r.warnings.append('Legacy white-balance temperature/tint was not applied because RapidRAW stores a relative WB adjustment.')

    if r.camera_profile and r.camera_profile not in ('Adobe Standard','Embedded','ACR 2.4','ACR 3.3','ACR 3.4','ACR 4.4'):
        r.warnings.append('CameraProfile not embedded: '+r.camera_profile)

    # Find meaningful leftovers. Ignore zeros/default-ish metadata.
    handled=set(r.mapped)|set(r.approximate)|METADATA_KEYS|UNSUPPORTED_ALWAYS|{'ConvertToGrayscale'}
    # normalize approximate label for legacy Shadows
    handled.add('Shadows')
    for k,v in s.items():
        if k in handled: continue
        if k.startswith('Enable') or k.startswith('Auto'): continue
        meaningful = (isinstance(v,bool) and v) or (isinstance(v,(int,float)) and abs(v)>1e-12) or (isinstance(v,str) and v not in ('','0','None'))
        if meaningful and k not in r.unsupported:
            r.unsupported.append(k)
    for k in UNSUPPORTED_ALWAYS:
        v=s.get(k)
        meaningful=(isinstance(v,(int,float)) and abs(v)>1e-12) or (isinstance(v,str) and v not in ('','0','None'))
        if meaningful and k not in r.unsupported: r.unsupported.append(k)

    entry={'preset':{
        'id':str(uuid.uuid4()), 'name':parsed.name, 'adjustments':a,
        'includeMasks':False,'includeCropTransform':False,'presetType':'style'
    }}
    r.preset_entry=entry
    return r


def safe_name(name:str)->str:
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).strip().rstrip('.')
    return name or 'Preset'


def iter_inputs(input_path:str) -> Iterable[Tuple[str,str]]:
    p=pathlib.Path(input_path)
    if p.is_dir():
        for f in sorted(p.rglob('*.lrtemplate')):
            yield str(f.relative_to(p)).replace('\\','/'), f.read_text(encoding='utf-8',errors='replace')
    elif p.is_file() and p.suffix.lower()=='.zip':
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith('.lrtemplate') and not n.endswith('/'):
                    yield n, z.read(n).decode('utf-8',errors='replace')
    elif p.is_file() and p.suffix.lower()=='.lrtemplate':
        yield p.name, p.read_text(encoding='utf-8',errors='replace')
    else:
        raise ValueError('Input must be a .lrtemplate file, a folder, or a ZIP containing .lrtemplate files.')


def convert_all(input_path:str, output_dir:str, template_path:Optional[str]=None, individual=True, combined=True, progress=None):
    out=pathlib.Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    baseline=load_baseline(template_path)
    results=[]; errors=[]
    items=list(iter_inputs(input_path))
    for idx,(rel,text) in enumerate(items,1):
        try:
            parsed=parse_lrtemplate(text,rel); res=convert(parsed,baseline); results.append(res)
            if individual:
                relp=pathlib.PurePosixPath(rel)
                parent=out.joinpath(*relp.parts[:-1]); parent.mkdir(parents=True,exist_ok=True)
                fn=safe_name(pathlib.Path(relp.name).stem)+'.rrpreset'
                data={'creator':'Converted from legacy Lightroom lrtemplate','presets':[res.preset_entry]}
                (parent/fn).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:
            errors.append((rel,str(e)))
        if progress: progress(idx,len(items),rel)
    if combined and results:
        data={'creator':'Legacy Lightroom batch conversion','presets':[r.preset_entry for r in results]}
        (out/'ALL_Converted_Lightroom_Presets.rrpreset').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

    # CSV report
    with open(out/'conversion_report.csv','w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,delimiter=';')
        w.writerow(['Source','Preset','ProcessVersion','B&W','CameraProfile','Mapped','Approximate','Unsupported','Warnings'])
        for r in results:
            w.writerow([r.source,r.name,r.process_version,'yes' if r.is_bw else 'no',r.camera_profile,
                        ', '.join(sorted(set(r.mapped))),', '.join(sorted(set(r.approximate))),
                        ', '.join(sorted(set(r.unsupported))),' | '.join(r.warnings)])
        for src,err in errors: w.writerow([src,'ERROR','','','','','','',err])
    profiles={}
    for r in results:
        if r.camera_profile: profiles[r.camera_profile]=profiles.get(r.camera_profile,0)+1
    summary={
        'input':input_path,'converted':len(results),'errors':len(errors),
        'black_and_white':sum(r.is_bw for r in results),
        'presets_with_camera_profile':sum(bool(r.camera_profile) for r in results),
        'unique_camera_profiles':profiles,
        'notes':[
            'Camera profiles (.dcp) are not embedded in .rrpreset.',
            'B&W fallback uses Saturation -100 plus GrayMixer -> HSL luminance.',
            'Legacy PV 5.x/older tone controls are approximate and are marked in conversion_report.csv.',
            'For best future compatibility, export a fresh simple RapidRAW preset and pass it with --template.'
        ]
    }
    (out/'conversion_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return results,errors,summary


def make_gui():
    try:
        import tkinter as tk
        from tkinter import ttk,filedialog,messagebox
    except Exception as e:
        print('Tkinter not available. Use CLI mode.'); return 2
    root=tk.Tk(); root.title('Lightroom lrtemplate → RapidRAW Converter'); root.geometry('820x560')
    frm=ttk.Frame(root,padding=12); frm.pack(fill='both',expand=True)
    inp=tk.StringVar(); out=tk.StringVar(); tmpl=tk.StringVar(); indiv=tk.BooleanVar(value=True); comb=tk.BooleanVar(value=True)
    def pick_input():
        f=filedialog.askopenfilename(title='ZIP oder .lrtemplate wählen',filetypes=[('Lightroom/ZIP','*.zip *.lrtemplate'),('Alle Dateien','*.*')])
        if f: inp.set(f); out.set(str(pathlib.Path(f).with_name(pathlib.Path(f).stem+'_RapidRAW')))
    def pick_folder_input():
        f=filedialog.askdirectory(title='Ordner mit .lrtemplate wählen')
        if f: inp.set(f); out.set(str(pathlib.Path(f).with_name(pathlib.Path(f).name+'_RapidRAW')))
    def pick_out():
        f=filedialog.askdirectory(title='Ausgabeordner wählen')
        if f: out.set(f)
    def pick_tmpl():
        f=filedialog.askopenfilename(title='Optionales RapidRAW Referenz-Preset',filetypes=[('RapidRAW Preset','*.rrpreset'),('Alle Dateien','*.*')])
        if f: tmpl.set(f)
    ttk.Label(frm,text='Lightroom → RapidRAW Batch Converter',font=('Segoe UI',15,'bold')).grid(row=0,column=0,columnspan=4,sticky='w',pady=(0,12))
    ttk.Label(frm,text='Eingabe:').grid(row=1,column=0,sticky='w'); ttk.Entry(frm,textvariable=inp).grid(row=1,column=1,sticky='ew',padx=6)
    ttk.Button(frm,text='ZIP/Datei…',command=pick_input).grid(row=1,column=2); ttk.Button(frm,text='Ordner…',command=pick_folder_input).grid(row=1,column=3,padx=(6,0))
    ttk.Label(frm,text='Ausgabe:').grid(row=2,column=0,sticky='w',pady=6); ttk.Entry(frm,textvariable=out).grid(row=2,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Ordner…',command=pick_out).grid(row=2,column=2)
    ttk.Label(frm,text='RapidRAW Vorlage:').grid(row=3,column=0,sticky='w'); ttk.Entry(frm,textvariable=tmpl).grid(row=3,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Optional…',command=pick_tmpl).grid(row=3,column=2)
    ttk.Label(frm,text='Leer = eingebautes Schema vom 22.08.2026. Bei späteren RapidRAW-Versionen einfach ein frisch exportiertes Test-Preset wählen.').grid(row=4,column=1,columnspan=3,sticky='w')
    ttk.Checkbutton(frm,text='Einzelne .rrpreset + Ordnerstruktur erzeugen',variable=indiv).grid(row=5,column=1,columnspan=2,sticky='w',pady=(12,0))
    ttk.Checkbutton(frm,text='Zusätzlich eine Sammel-.rrpreset erzeugen',variable=comb).grid(row=6,column=1,columnspan=2,sticky='w')
    log=tk.Text(frm,height=18,wrap='word'); log.grid(row=8,column=0,columnspan=4,sticky='nsew',pady=(12,0))
    pb=ttk.Progressbar(frm,mode='determinate'); pb.grid(row=7,column=0,columnspan=4,sticky='ew',pady=(12,0))
    frm.columnconfigure(1,weight=1); frm.rowconfigure(8,weight=1)
    def run():
        if not inp.get() or not out.get(): messagebox.showerror('Fehlt','Bitte Eingabe und Ausgabe wählen.'); return
        log.delete('1.0','end'); pb['value']=0
        def prog(i,total,name):
            pb['maximum']=max(total,1); pb['value']=i
            if i==1 or i==total or i%25==0:
                log.insert('end',f'{i}/{total}: {name}\n'); log.see('end'); root.update_idletasks()
        try:
            results,errors,summary=convert_all(inp.get(),out.get(),tmpl.get() or None,indiv.get(),comb.get(),prog)
            log.insert('end',f"\nFertig: {len(results)} konvertiert, {len(errors)} Fehler.\nBericht: {pathlib.Path(out.get())/'conversion_report.csv'}\n")
            messagebox.showinfo('Fertig',f"{len(results)} Presets konvertiert.\nFehler: {len(errors)}\n\nSiehe conversion_report.csv")
        except Exception as e:
            messagebox.showerror('Fehler',str(e)); log.insert('end','ERROR: '+str(e))
    ttk.Button(frm,text='Konvertieren',command=run).grid(row=9,column=3,sticky='e',pady=(10,0))
    root.mainloop(); return 0


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if not argv: return make_gui()
    ap=argparse.ArgumentParser(description='Batch convert legacy Lightroom .lrtemplate presets to RapidRAW .rrpreset')
    ap.add_argument('input',help='.lrtemplate file, folder, or ZIP')
    ap.add_argument('-o','--output',default='RapidRAW_Converted',help='Output directory')
    ap.add_argument('--template',help='Optional fresh RapidRAW .rrpreset to use as schema/defaults')
    ap.add_argument('--no-individual',action='store_true',help='Do not write individual presets')
    ap.add_argument('--no-combined',action='store_true',help='Do not write combined preset bundle')
    args=ap.parse_args(argv)
    def prog(i,n,name):
        if i==1 or i==n or i%50==0: print(f'[{i}/{n}] {name}')
    results,errors,summary=convert_all(args.input,args.output,args.template,not args.no_individual,not args.no_combined,prog)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 1 if errors else 0

if __name__=='__main__': raise SystemExit(main())
