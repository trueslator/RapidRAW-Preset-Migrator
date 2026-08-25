#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal DCP reader + camera-profile-look to .cube helpers.
Standard-library only. Reads the TIFF-like DCP container (IIRC/MMRC).
This intentionally ignores ColorMatrix/ForwardMatrix for LUT generation: the LUTs
are creative look companions for RapidRAW, not replacement camera input profiles.
"""
from __future__ import annotations
import colorsys, dataclasses, difflib, math, pathlib, re, struct
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# DNG/DCP tag IDs we use.
TAG_CAMERA=50708
TAG_ILL1=50778
TAG_ILL2=50779
TAG_PROFILE_NAME=50936
TAG_HSM_DIMS=50937
TAG_HSM_1=50938
TAG_HSM_2=50939
TAG_TONE=50940
TAG_LOOK_DIMS=50981
TAG_LOOK_DATA=50982
TAG_HSM_ENCODING=51107
TAG_LOOK_ENCODING=51108

TYPE_SIZES={1:1,2:1,3:2,4:4,5:8,6:1,7:1,8:2,9:4,10:8,11:4,12:8}


def parse_dcp_tags(data: bytes) -> Dict[int, object]:
    if data[:2]==b'II': endian='<'
    elif data[:2]==b'MM': endian='>'
    else: raise ValueError('Not a DCP/TIFF byte stream')
    magic=struct.unpack(endian+'H',data[2:4])[0]
    # DCP commonly uses IIRC/MMRC rather than TIFF's 42 magic.
    if magic not in (42,0x4352):
        raise ValueError(f'Unsupported DCP/TIFF magic: 0x{magic:04x}')
    ifd=struct.unpack(endian+'I',data[4:8])[0]
    if ifd+2>len(data): raise ValueError('Invalid IFD offset')
    n=struct.unpack(endian+'H',data[ifd:ifd+2])[0]
    tags={}
    for i in range(n):
        off=ifd+2+i*12
        if off+12>len(data): break
        tag,typ,count=struct.unpack(endian+'HHI',data[off:off+8])
        sz=TYPE_SIZES.get(typ)
        if not sz: continue
        total=sz*count
        if total<=4:
            raw=data[off+8:off+8+total]
        else:
            voff=struct.unpack(endian+'I',data[off+8:off+12])[0]
            if voff+total>len(data): continue
            raw=data[voff:voff+total]
        try:
            if typ in (1,7): v=raw if count>1 else raw[0]
            elif typ==2: v=raw.split(b'\0',1)[0].decode('utf-8','replace')
            elif typ==3: v=struct.unpack(endian+str(count)+'H',raw)
            elif typ==4: v=struct.unpack(endian+str(count)+'I',raw)
            elif typ==5:
                a=struct.unpack(endian+str(count*2)+'I',raw); v=tuple(a[j]/a[j+1] if a[j+1] else 0 for j in range(0,len(a),2))
            elif typ==6: v=struct.unpack(endian+str(count)+'b',raw)
            elif typ==8: v=struct.unpack(endian+str(count)+'h',raw)
            elif typ==9: v=struct.unpack(endian+str(count)+'i',raw)
            elif typ==10:
                a=struct.unpack(endian+str(count*2)+'i',raw); v=tuple(a[j]/a[j+1] if a[j+1] else 0 for j in range(0,len(a),2))
            elif typ==11: v=struct.unpack(endian+str(count)+'f',raw)
            elif typ==12: v=struct.unpack(endian+str(count)+'d',raw)
            else: continue
            if isinstance(v,tuple) and len(v)==1: v=v[0]
            tags[tag]=v
        except Exception:
            continue
    return tags

@dataclasses.dataclass
class DCPProfile:
    source: str
    camera: str
    name: str
    illuminant1: Optional[int]=None
    illuminant2: Optional[int]=None
    hsm_dims: Optional[Tuple[int,int,int]]=None
    hsm1: Optional[Tuple[float,...]]=None
    hsm2: Optional[Tuple[float,...]]=None
    hsm_encoding: int=0
    look_dims: Optional[Tuple[int,int,int]]=None
    look_data: Optional[Tuple[float,...]]=None
    look_encoding: int=0
    tone_curve: Optional[Tuple[float,...]]=None

    @property
    def has_color_tables(self): return bool((self.hsm_dims and self.hsm1) or (self.look_dims and self.look_data))
    @property
    def has_tone_curve(self): return bool(self.tone_curve and len(self.tone_curve)>=4)


def profile_from_bytes(data: bytes, source='') -> DCPProfile:
    t=parse_dcp_tags(data)
    def tup(tag, cast=float):
        v=t.get(tag)
        if v is None: return None
        if not isinstance(v,tuple): v=(v,)
        return tuple(cast(x) for x in v)
    dims=tup(TAG_HSM_DIMS,int); ldims=tup(TAG_LOOK_DIMS,int)
    return DCPProfile(
        source=source,
        camera=str(t.get(TAG_CAMERA,'') or ''),
        name=str(t.get(TAG_PROFILE_NAME,'') or pathlib.Path(source).stem),
        illuminant1=int(t[TAG_ILL1]) if TAG_ILL1 in t else None,
        illuminant2=int(t[TAG_ILL2]) if TAG_ILL2 in t else None,
        hsm_dims=dims if dims and len(dims)==3 else None,
        hsm1=tup(TAG_HSM_1,float), hsm2=tup(TAG_HSM_2,float),
        hsm_encoding=int(t.get(TAG_HSM_ENCODING,0) or 0),
        look_dims=ldims if ldims and len(ldims)==3 else None,
        look_data=tup(TAG_LOOK_DATA,float), look_encoding=int(t.get(TAG_LOOK_ENCODING,0) or 0),
        tone_curve=tup(TAG_TONE,float),
    )


def norm_profile_name(s: str) -> str:
    s=(s or '').casefold().replace('\u00a0',' ')
    s=re.sub(r'\s+',' ',s).strip()
    return s

BUILTIN_PROFILES={'adobe standard','embedded','acr 2.4','acr 3.3','acr 3.4','acr 4.4'}


def is_builtin_profile(name:str)->bool:
    return norm_profile_name(name) in BUILTIN_PROFILES


def profile_candidate_key(s: str) -> str:
    """Loose key used only for suggestions, never automatic matching."""
    x=(s or '').casefold()
    repl={'⁺':'+','⁻':'-','¹':'1','²':'2','³':'3'}
    for a,b in repl.items(): x=x.replace(a,b)
    x=x.replace('kodak',' ').replace('fuji',' ').replace('fujifilm',' ').replace('ilford',' ')
    x=re.sub(r'\bv2[cn]\b',' ',x)
    x=re.sub(r'\s[-+]\s*[cn]\b',' ',x)
    x=re.sub(r'\s+[cn]\b$',' ',x)
    x=re.sub(r'[^a-z0-9+.-]+',' ',x)
    return re.sub(r'\s+',' ',x).strip()


def suggest_profile_name(name: str, available: Sequence[str]) -> Tuple[str,float]:
    q=profile_candidate_key(name)
    best=('',0.0)
    for p in available:
        score=difflib.SequenceMatcher(None,q,profile_candidate_key(p)).ratio()
        if score>best[1]: best=(p,score)
    return best


def creative_signature(profile: DCPProfile) -> tuple:
    """Signature of the creative DCP data used for companion LUT generation.

    Camera ColorMatrix/ForwardMatrix data is intentionally not part of this signature
    because it is not used by this tool.
    """
    return (
        profile.hsm_dims, profile.hsm1, profile.hsm2, profile.hsm_encoding,
        profile.look_dims, profile.look_data, profile.look_encoding, profile.tone_curve,
    )


def choose_profile(candidates: Sequence[DCPProfile], preferred_camera='Auto') -> Optional[DCPProfile]:
    """Choose a DCP conservatively.

    - With an explicit camera name, only that camera is accepted.
    - In Auto mode, a single candidate is accepted.
    - Multiple candidates are accepted only when their creative look data is identical.
    - Otherwise no profile is chosen; the caller reports the ambiguity instead of guessing.
    """
    if not candidates:
        return None
    pref=(preferred_camera or 'Auto').strip()
    if pref and pref.casefold() != 'auto':
        for p in candidates:
            if p.camera.casefold()==pref.casefold():
                return p
        # If the requested body is unavailable, still accept a truly unambiguous
        # creative profile. Never fall through to a different conflicting body.
        if len(candidates)==1:
            return candidates[0]
        sigs={creative_signature(p) for p in candidates}
        if len(sigs)==1:
            return sorted(candidates,key=lambda p:(p.camera.casefold(),p.source.casefold()))[0]
        return None
    if len(candidates)==1:
        return candidates[0]
    sigs={creative_signature(p) for p in candidates}
    if len(sigs)==1:
        return sorted(candidates,key=lambda p:(p.camera.casefold(),p.source.casefold()))[0]
    return None

# Linear sRGB D65 -> linear ProPhoto RGB D50 (sRGB->XYZ D65, Bradford D65->D50, XYZ D50->ProPhoto).
M_SRGB_TO_PRO=((0.52934582,0.33007279,0.14058125),
               (0.09837436,0.87346104,0.02816469),
               (0.01688319,0.11767247,0.86544430))
M_PRO_TO_SRGB=((2.03407636,-0.72733433,-0.30674171),
               (-0.22881341,1.23173017,-0.00291690),
               (-0.00856976,-0.15328660,1.16185642))

def mm(m,v): return (m[0][0]*v[0]+m[0][1]*v[1]+m[0][2]*v[2],m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2],m[2][0]*v[0]+m[2][1]*v[1]+m[2][2]*v[2])
def clip01(x): return 0.0 if x<0 else (1.0 if x>1 else x)

def tf_encode(x: float) -> float:
    x=max(0.0,x)
    return 12.92*x if x<=0.0031308 else 1.055*(x**(1/2.4))-0.055

def tf_decode(x: float) -> float:
    x=max(0.0,x)
    return x/12.92 if x<=0.04045 else ((x+0.055)/1.055)**2.4


def _table_triplet(data: Tuple[float,...], dims: Tuple[int,int,int], h:int,s:int,v:int):
    H,S,V=dims
    # DNG profile tables are Hue-major, then Saturation, then Value, with 3 floats per entry.
    i=((h*S+s)*V+v)*3
    return (data[i],data[i+1],data[i+2])


def apply_hsv_table(rgb: Tuple[float,float,float], data: Tuple[float,...], dims: Tuple[int,int,int], encoding=0):
    """Apply a DCP HueSatMap/LookTable to ProPhoto RGB.
    rgb is linear ProPhoto. Encoding 1 uses an sRGB-like transfer for the table coordinates.
    """
    if not data or not dims: return rgb
    H,S,V=dims
    if H<1 or S<1 or V<1: return rgb
    work=tuple(tf_encode(max(0.0,c)) for c in rgb) if encoding==1 else rgb
    mx=max(work); mn=min(work); d=mx-mn
    if mx<=1e-15: return rgb
    sat=d/mx if mx else 0.0
    if d<=1e-15: hue=0.0
    elif mx==work[0]: hue=(((work[1]-work[2])/d)%6.0)/6.0
    elif mx==work[1]: hue=(((work[2]-work[0])/d)+2.0)/6.0
    else: hue=(((work[0]-work[1])/d)+4.0)/6.0
    hue%=1.0
    hf=hue*H; hb=math.floor(hf); h0=int(hb)%H; h1=(h0+1)%H; wh=hf-hb
    sf=clip01(sat)*(S-1); sb=math.floor(sf); s0=int(sb); s1=min(s0+1,S-1); ws=sf-sb
    # DCP tables address Value in [0,1]. For HDR-ish values, clamp the lookup coordinate but preserve transformed scale.
    vf=clip01(mx)*(V-1) if V>1 else 0.0; vb=math.floor(vf); v0=int(vb); v1=min(v0+1,V-1); wv=vf-vb
    delta=[0.0,0.0,0.0]
    for hi,ah in ((h0,1-wh),(h1,wh)):
      for si,as_ in ((s0,1-ws),(s1,ws)):
       for vi,av in ((v0,1-wv),(v1,wv)):
        w=ah*as_*av
        q=_table_triplet(data,dims,hi,si,vi)
        delta[0]+=q[0]*w; delta[1]+=q[1]*w; delta[2]+=q[2]*w
    h2=(hue+delta[0]/360.0)%1.0
    s2=max(0.0,sat*delta[1]); v2=max(0.0,mx*delta[2])
    out=colorsys.hsv_to_rgb(h2,s2,v2)
    if encoding==1: out=tuple(tf_decode(max(0.0,c)) for c in out)
    return out


def daylight_hsm(profile:DCPProfile):
    # Many legacy dual-illuminant DCPs use Illuminant1=A and Illuminant2=D65. If Data2 is absent, Data1 is shared.
    if profile.hsm2: return profile.hsm2
    return profile.hsm1


def apply_profile_color(rgb: Tuple[float,float,float], profile:DCPProfile, include_look=True):
    p=mm(M_SRGB_TO_PRO,rgb)
    hsm=daylight_hsm(profile)
    if hsm and profile.hsm_dims:
        p=apply_hsv_table(p,hsm,profile.hsm_dims,profile.hsm_encoding)
    if include_look and profile.look_data and profile.look_dims:
        p=apply_hsv_table(p,profile.look_data,profile.look_dims,profile.look_encoding)
    o=mm(M_PRO_TO_SRGB,p)
    return tuple(clip01(x) for x in o)


def _interp_curve(x:float, curve:Tuple[float,...]):
    if not curve or len(curve)<4: return clip01(x)
    x=clip01(x); n=len(curve)//2
    if x<=curve[0]: return clip01(curve[1])
    for i in range(1,n):
        x1,y1=curve[2*i],curve[2*i+1]; x0,y0=curve[2*i-2],curve[2*i-1]
        if x<=x1:
            t=0.0 if x1==x0 else (x-x0)/(x1-x0)
            return clip01(y0+(y1-y0)*t)
    return clip01(curve[-1])


def apply_tone_hue_preserving(rgb, curve):
    if not curve: return rgb
    m=max(rgb)
    if m<=1e-12: return rgb
    m2=_interp_curve(m,curve); scale=m2/m
    return tuple(clip01(c*scale) for c in rgb)

# RapidRAW HSL ranges as used by its current shader.  The widths deliberately
# overlap; influences are normalized before the luminance adjustments are mixed.
HSL_RANGES={
    'Red':(358.0,35.0),
    'Orange':(25.0,45.0),
    'Yellow':(60.0,40.0),
    'Green':(115.0,90.0),
    'Aqua':(180.0,60.0),
    'Blue':(225.0,60.0),
    'Purple':(280.0,55.0),
    'Magenta':(330.0,50.0),
}

def _circular_hue_distance(a:float,b:float)->float:
    d=abs(a-b)%360.0
    return min(d,360.0-d)

def _smoothstep01(x:float)->float:
    t=clip01(x)
    return t*t*(3.0-2.0*t)

def gray_mixer_value(rgb, gray:Dict[str,float]):
    """Reproduce RapidRAW's HSL-panel luminance mixing, then desaturate.

    Legacy Lightroom GrayMixer values are represented in the v1 converter as
    RapidRAW HSL luminance sliders.  RapidRAW combines overlapping color ranges
    with Gaussian-like weights and fades the luminance effect toward neutrals.
    Matching that math here makes the DCP-aware B&W LUT agree with the already
    validated fallback preset before the DCP contribution is added.
    """
    r,g,b=(max(0.0,float(rgb[0])),max(0.0,float(rgb[1])),max(0.0,float(rgb[2])))
    y=0.2126*r+0.7152*g+0.0722*b
    mx=max(r,g,b); mn=min(r,g,b); d=mx-mn
    if mx<=1e-15:
        return 0.0
    sat=d/mx if mx else 0.0
    if d<=1e-15:
        hue=0.0
    elif mx==r:
        hue=60.0*(((g-b)/d)%6.0)
    elif mx==g:
        hue=60.0*(((b-r)/d)+2.0)
    else:
        hue=60.0*(((r-g)/d)+4.0)
    hue%=360.0

    weights={}
    total=0.0
    for name,(center,width) in HSL_RANGES.items():
        dist=_circular_hue_distance(hue,center)
        half=max(width*0.5,1e-9)
        w=math.exp(-1.5*(dist/half)**2)
        weights[name]=w
        total+=w
    if total<=1e-15:
        return clip01(y)

    luminance_weight=_smoothstep01(sat)
    total_lum_adjust=0.0
    for name,w in weights.items():
        slider=float(gray.get(name,0.0))/100.0
        total_lum_adjust+=(w/total)*luminance_weight*slider
    return clip01(y*(1.0+total_lum_adjust))


def write_cube(path, title, transform, size=33):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'TITLE "{title.replace(chr(34),chr(39))}"\n')
        f.write(f'LUT_3D_SIZE {size}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        den=size-1
        # .cube convention: R varies fastest, then G, then B.
        for b in range(size):
          bv=b/den
          for g in range(size):
            gv=g/den
            for r in range(size):
              rv=r/den
              o=transform((rv,gv,bv))
              f.write(f'{clip01(o[0]):.8f} {clip01(o[1]):.8f} {clip01(o[2]):.8f}\n')


def make_color_lut(path, profile:DCPProfile, strength=0.01, size=33):
    strength=max(0.0,min(1.0,strength))
    def fn(rgb):
        o=apply_profile_color(rgb,profile,True)
        o=apply_tone_hue_preserving(o,profile.tone_curve)
        return tuple(rgb[i]+strength*(o[i]-rgb[i]) for i in range(3))
    write_cube(path,f'{profile.name} - DCP full profile baked {strength*100:.2f}%',fn,size)


def apply_profile_color_bw_companion(rgb: Tuple[float,float,float], profile:DCPProfile):
    """Empirical RapidRAW companion transform for legacy B&W profiles.

    This intentionally applies the creative DCP HSV tables directly in the LUT's
    RGB working coordinates instead of emulating Adobe's full DCP input-profile
    pipeline.  That transform matched the visually validated black-and-white reference workflow used during development.  Camera ColorMatrix/ForwardMatrix tags are
    still ignored: RapidRAW remains responsible for camera input rendering.
    """
    out=rgb
    hsm=daylight_hsm(profile)
    if hsm and profile.hsm_dims:
        out=apply_hsv_table(out,hsm,profile.hsm_dims,profile.hsm_encoding)
    if profile.look_data and profile.look_dims:
        out=apply_hsv_table(out,profile.look_data,profile.look_dims,profile.look_encoding)
    return tuple(float(x) for x in out)

def make_bw_lut(path, profile:DCPProfile, gray:Dict[str,float], dcp_strength=0.25, curve_strength=0.01, size=33):
    dcp_strength=max(0.0,min(1.0,dcp_strength)); curve_strength=max(0.0,min(1.0,curve_strength))
    def fn(rgb):
        d=apply_profile_color_bw_companion(rgb,profile)
        c=tuple(rgb[i]+dcp_strength*(d[i]-rgb[i]) for i in range(3))
        g=gray_mixer_value(c,gray)
        if profile.tone_curve:
            gc=_interp_curve(g,profile.tone_curve)
            g=g+curve_strength*(gc-g)
        g=clip01(g); return (g,g,g)
    write_cube(path,f'{profile.name} - DCP {dcp_strength*100:.0f}% + BW mixer + curve {curve_strength*100:.1f}%',fn,size)
