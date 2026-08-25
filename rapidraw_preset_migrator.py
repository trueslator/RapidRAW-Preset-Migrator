#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RapidRAW Preset Migrator 1.0.0.

Converts legacy Lightroom .lrtemplate presets once, then lets the local HTML
manager discover user-owned DCP files dynamically from CameraProfiles/.
Companion LUTs are generated only when a matching profile is selected.
No third-party Python packages required.
"""
from __future__ import annotations

APP_NAME = "RapidRAW Preset Migrator"
APP_VERSION = "1.0.0"
import argparse, collections, copy, csv, hashlib, json, os, pathlib, re, shutil, sys, tempfile, zipfile
from typing import Dict, Iterable, List, Optional, Tuple
import lrtemplate_converter as core
from dcp_support import *
from preset_manager import generate_catalog

GRAY_KEYS=['Red','Orange','Yellow','Green','Aqua','Blue','Purple','Magenta']

def iter_dcp_bytes(path:str):
    p=pathlib.Path(path)
    if not p.exists(): return
    if p.is_dir():
        for f in sorted(p.rglob('*.dcp')):
            yield str(f.relative_to(p)).replace('\\','/'),f.read_bytes()
    elif p.is_file() and p.suffix.lower()=='.zip':
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith('.dcp') and not n.endswith('/'):
                    yield n,z.read(n)
    elif p.is_file() and p.suffix.lower()=='.dcp':
        yield p.name,p.read_bytes()


def load_dcps(paths:List[str]):
    profiles=[]; errors=[]; seen=set()
    for path in paths:
        if not path: continue
        try:
            for src,data in iter_dcp_bytes(path) or []:
                key=(path,src)
                if key in seen: continue
                seen.add(key)
                try: profiles.append(profile_from_bytes(data,src))
                except Exception as e: errors.append((src,str(e)))
        except Exception as e: errors.append((path,str(e)))
    return profiles,errors


def index_profiles(profiles):
    idx=collections.defaultdict(list)
    for p in profiles:
        idx[norm_profile_name(p.name)].append(p)
    return idx


def gray_values(parsed:core.ParsedPreset):
    return {c:float(parsed.settings.get('GrayMixer'+c,0) or 0) for c in GRAY_KEYS}


def make_dcp_bw_adjustments(res:core.ConversionResult, parsed:core.ParsedPreset):
    """Turn v1 B&W fallback back into color so companion LUT can do B&W after DCP color."""
    entry=copy.deepcopy(res.preset_entry)
    a=entry['preset']['adjustments']
    a['saturation']=float(parsed.settings.get('Saturation',0) or 0)
    for c,dst in core.COLOR_MAP.items():
        # Restore ordinary Lightroom HSL luminance; don't leave GrayMixer fallback in HSL.
        lv=parsed.settings.get('LuminanceAdjustment'+c)
        a['hsl'][dst]['luminance']=float(lv) if isinstance(lv,(int,float)) and not isinstance(lv,bool) else 0
    entry['preset']['name']=res.name+' [DCP]'
    return entry


def lut_key(profile:DCPProfile,is_bw:bool,gray:Dict[str,float]):
    base=profile.name+'|'+profile.camera+'|'+('bw' if is_bw else 'color')
    if is_bw: base+='|'+','.join(f'{k}:{gray[k]:g}' for k in GRAY_KEYS)
    return hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]


def safe_lut_name(profile:DCPProfile,is_bw:bool,key:str):
    stem=core.safe_name(profile.name)
    return f'{stem}__{"BW" if is_bw else "COLOR"}__{key}.cube'

def dcp_prep_metadata(parsed: core.ParsedPreset | None):
    """Metadata needed to build a DCP-aware variant later in the HTML manager.

    This is deliberately stored with the converted catalog so users can add/remove
    DCP files later without re-running the legacy .lrtemplate conversion.
    """
    if parsed is None:
        return {"saturation": 0.0, "hslLuminance": {}, "grayMixer": {}}
    s=parsed.settings
    sat=s.get('Saturation',0)
    if not isinstance(sat,(int,float)) or isinstance(sat,bool): sat=0.0
    hsl={}; gray={}
    for src,dst in core.COLOR_MAP.items():
        lv=s.get('LuminanceAdjustment'+src,0)
        gv=s.get('GrayMixer'+src,0)
        hsl[dst]=float(lv) if isinstance(lv,(int,float)) and not isinstance(lv,bool) else 0.0
        gray[src]=float(gv) if isinstance(gv,(int,float)) and not isinstance(gv,bool) else 0.0
    return {"saturation": float(sat), "hslLuminance": hsl, "grayMixer": gray}


def _copy_dcps_to_library(paths:List[str], dest:pathlib.Path):
    dest.mkdir(parents=True,exist_ok=True); copied=0; skipped=0; errors=[]
    for src_path in paths:
        if not src_path: continue
        try:
            for rel,data in iter_dcp_bytes(src_path) or []:
                pp=pathlib.PurePosixPath(rel)
                parts=list(pp.parts)
                if parts and parts[0].casefold() in ('cameraprofile','cameraprofiles','camera profile','camera profiles'):
                    parts=parts[1:]
                if not parts: parts=[pathlib.Path(rel).name]
                clean=[core.safe_name(x) for x in parts[:-1]]+[core.safe_name(pathlib.Path(parts[-1]).stem)+'.dcp']
                target=dest.joinpath(*clean); target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():
                    if target.read_bytes()==data: skipped+=1; continue
                    target=target.with_name(target.stem+'__'+hashlib.sha1(data).hexdigest()[:8]+target.suffix)
                target.write_bytes(data); copied+=1
        except Exception as e: errors.append((src_path,str(e)))
    return copied,skipped,errors


def convert_migration(input_path:str,output_dir:str,template_path=None,dcp_path=None,preferred_camera='Auto',grid=33,progress=None):
    """Convert legacy presets once; CameraProfiles remain a live manager-side library.

    No DCP is permanently chosen here.  This is intentional: users can add, remove or
    switch their own .dcp files later without converting the .lrtemplate collection again.
    """
    out=pathlib.Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    fallback_dir=out/'Presets_Fallback'; fallback_dir.mkdir(exist_ok=True)
    results,errors,_=core.convert_all(input_path,str(fallback_dir),template_path,True,True,progress)
    parsed_by_source={}
    for rel,text in core.iter_inputs(input_path):
        try: parsed_by_source[rel]=core.parse_lrtemplate(text,rel)
        except Exception: pass
    prep={res.source:dcp_prep_metadata(parsed_by_source.get(res.source)) for res in results}
    (out/'migration_dcp_prep.json').write_text(json.dumps(prep,ensure_ascii=False,indent=2),encoding='utf-8')

    profile_library=out/'CameraProfiles'; profile_library.mkdir(exist_ok=True)
    (profile_library/'README.txt').write_text(
        'Place your own .dcp camera profiles here. Subfolders are supported. The HTML Preset Manager scans this folder automatically.\n',encoding='utf-8')
    seed_paths=[input_path]
    if dcp_path and pathlib.Path(dcp_path).resolve()!=pathlib.Path(input_path).resolve(): seed_paths.append(dcp_path)
    copied,skipped,dcp_copy_errors=_copy_dcps_to_library(seed_paths,profile_library)

    # Compatibility report consumed by preset_manager.generate_catalog().  It records
    # requirements only; matching happens dynamically against CameraProfiles/.
    rows=[]; builtin=0; external=0
    for res in results:
        cp=res.camera_profile or ''
        if cp and is_builtin_profile(cp): builtin+=1
        elif cp: external+=1
        rows.append({'Source':res.source,'Preset':res.name,'BW':'yes' if res.is_bw else 'no','CameraProfile':cp,
                     'Mode':'dynamic CameraProfiles library' if cp and not is_builtin_profile(cp) else 'builtin/no DCP needed',
                     'MatchedProfile':'','MatchedCamera':'','MatchedDCP':'','CompanionLUT':'','CandidateCameras':'','SuggestedProfile':'','SuggestionScore':''})
    with (out/'dcp_match_report.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=list(rows[0].keys()) if rows else ['Source']; w=csv.DictWriter(f,fieldnames=fields,delimiter=';'); w.writeheader(); w.writerows(rows)
    counts=collections.Counter(res.camera_profile for res in results if res.camera_profile and not is_builtin_profile(res.camera_profile))
    with (out/'camera_profile_requirements.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,delimiter=';'); w.writerow(['CameraProfile','PresetCount'])
        for name,count in sorted(counts.items(),key=lambda x:x[0].casefold()): w.writerow([name,count])

    catalog=generate_catalog(out)
    catalog['lutGrid']=grid
    (out/'migration_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'input':input_path,'presets':len(results),'conversion_errors':len(errors),'external_camera_profile_references':external,
             'builtin_profile_references':builtin,'unique_external_camera_profiles':len(counts),'camera_profiles_seeded':copied,
             'camera_profiles_seed_duplicates':skipped,'camera_profile_copy_errors':len(dcp_copy_errors),'lut_grid':grid,
             'dcp_strategy':'CameraProfiles are selected dynamically in the HTML manager; companion LUTs are generated on demand.',
             'color_recipe':'DCP creative color tables + tone curve, applied as a subtle 1% companion LUT.',
             'bw_recipe':'DCP creative color tables 25% + Lightroom GrayMixer -> B&W + DCP tone curve 1%.',
             'migration_catalog_presets':catalog['stats']['total'],'migration_manager':'RapidRAW_Preset_Manager.html'}
    (out/'migration_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary,rows,dcp_copy_errors


def make_gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk(); root.title(f'{APP_NAME} {APP_VERSION}'); root.geometry('900x640')
    frm=ttk.Frame(root,padding=12); frm.pack(fill='both',expand=True)
    inp=tk.StringVar(); out=tk.StringVar(); dcp=tk.StringVar(); tmpl=tk.StringVar(); cam=tk.StringVar(value='Auto')
    def pick_input():
        f=filedialog.askopenfilename(title='ZIP mit Templates (und optional CameraProfile) wählen',filetypes=[('ZIP','*.zip'),('Alle','*.*')])
        if f: inp.set(f); out.set(str(pathlib.Path(f).with_name(pathlib.Path(f).stem+'_RapidRAW_Migrated')))
    def pick_dcp():
        f=filedialog.askdirectory(title='Optional: separater Ordner mit DCP-Dateien')
        if f: dcp.set(f)
    def pick_out():
        f=filedialog.askdirectory(title='Ausgabeordner');
        if f: out.set(f)
    def pick_tmpl():
        f=filedialog.askopenfilename(title='Optionales frisches RapidRAW Test-Preset',filetypes=[('RapidRAW','*.rrpreset'),('Alle','*.*')]);
        if f: tmpl.set(f)
    ttk.Label(frm,text=f'{APP_NAME} {APP_VERSION}',font=('Segoe UI',16,'bold')).grid(row=0,column=0,columnspan=4,sticky='w',pady=(0,12))
    ttk.Label(frm,text='Templates ZIP:').grid(row=1,column=0,sticky='w'); ttk.Entry(frm,textvariable=inp).grid(row=1,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Wählen…',command=pick_input).grid(row=1,column=2)
    ttk.Label(frm,text='DCP-Ordner optional:').grid(row=2,column=0,sticky='w',pady=5); ttk.Entry(frm,textvariable=dcp).grid(row=2,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Wählen…',command=pick_dcp).grid(row=2,column=2)
    ttk.Label(frm,text='Ausgabe:').grid(row=3,column=0,sticky='w'); ttk.Entry(frm,textvariable=out).grid(row=3,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Wählen…',command=pick_out).grid(row=3,column=2)
    ttk.Label(frm,text='CameraProfiles optional vorbefüllen:').grid(row=4,column=0,sticky='w',pady=5); ttk.Label(frm,text='DCPs können auch später einfach in CameraProfiles/ kopiert werden.').grid(row=4,column=1,columnspan=2,sticky='w',padx=6)
    ttk.Label(frm,text='RapidRAW Vorlage optional:').grid(row=5,column=0,sticky='w'); ttk.Entry(frm,textvariable=tmpl).grid(row=5,column=1,sticky='ew',padx=6); ttk.Button(frm,text='Wählen…',command=pick_tmpl).grid(row=5,column=2)
    ttk.Label(frm,text='Es werden sichere Fallback-Presets erzeugt. CameraProfiles werden im HTML-Manager dynamisch ausgewählt; neue DCPs erfordern keine Neukonvertierung.').grid(row=6,column=0,columnspan=4,sticky='w',pady=(8,0))
    pb=ttk.Progressbar(frm,mode='determinate'); pb.grid(row=7,column=0,columnspan=4,sticky='ew',pady=(12,0))
    log=tk.Text(frm,height=22,wrap='word'); log.grid(row=8,column=0,columnspan=4,sticky='nsew',pady=(8,0))
    frm.columnconfigure(1,weight=1); frm.rowconfigure(8,weight=1)
    def run():
        if not inp.get() or not out.get(): messagebox.showerror('Fehlt','Bitte Templates-ZIP und Ausgabe wählen.'); return
        log.delete('1.0','end')
        def prog(i,n,name):
            pb['maximum']=max(n,1); pb['value']=i
            if i==1 or i==n or i%50==0: log.insert('end',f'{i}/{n}: {name}\n'); log.see('end'); root.update_idletasks()
        try:
            s,_,de=convert_migration(inp.get(),out.get(),tmpl.get() or None,dcp.get() or None,cam.get().strip() or 'Auto',33,prog)
            log.insert('end','\n'+json.dumps(s,ensure_ascii=False,indent=2)+'\n')
            messagebox.showinfo('Fertig',f"{s['presets']} Presets verarbeitet.\n{s['camera_profiles_seeded']} CameraProfiles vorbefüllt.\n\nHTML Preset Manager wurde im Ausgabeordner erstellt.")
        except Exception as e: messagebox.showerror('Fehler',str(e)); log.insert('end','ERROR: '+repr(e))
    ttk.Button(frm,text='Konvertieren',command=run).grid(row=9,column=3,sticky='e',pady=(10,0))
    root.mainloop()


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if not argv: return make_gui()
    ap=argparse.ArgumentParser(description=f'{APP_NAME} {APP_VERSION}: DCP-aware legacy Lightroom preset migration with cross-platform HTML manager')
    ap.add_argument('input',help='Templates folder/ZIP; DCPs inside are auto-detected')
    ap.add_argument('-o','--output',default='RapidRAW_Migrated_Presets')
    ap.add_argument('--dcp',help='Optional additional DCP folder/ZIP/file')
    ap.add_argument('--template',help='Optional fresh RapidRAW .rrpreset schema')
    ap.add_argument('--camera',default='Auto',help='Deprecated compatibility option; profile selection now happens in the HTML manager.')
    ap.add_argument('--grid',type=int,default=33,choices=(17,33,65),help='Cube LUT grid size')
    a=ap.parse_args(argv)
    def prog(i,n,name):
        if i==1 or i==n or i%50==0: print(f'[{i}/{n}] {name}')
    s,_,de=convert_migration(a.input,a.output,a.template,a.dcp,a.camera,a.grid,prog)
    print(json.dumps(s,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
