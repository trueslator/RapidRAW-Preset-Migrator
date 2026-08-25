#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RapidRAW Preset Migrator local HTML preset manager.

The manager intentionally edits only presets whose names/folders begin with [MIG].
Native RapidRAW presets are preserved byte-for-structure as JSON objects.
No third-party Python packages are required.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import http.server
import json
import os
import pathlib
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import uuid
import webbrowser
from typing import Any, Dict, Iterable, List, Tuple, Optional

from dcp_support import profile_from_bytes, norm_profile_name, is_builtin_profile, make_color_lut, make_bw_lut, DCPProfile

APP_VERSION = "1.0.0"
MIG_PREFIX = "[MIG] "
APP_DIR_NAME = "io.github.CyberTimon.RapidRAW"
CATALOG_FILE = "migration_catalog.json"
HTML_FILE = "RapidRAW_Preset_Manager.html"
LUT_SUBDIR = "migration_luts"
FAVORITES_STATE_FILE = "migration_manager_state.json"
FAVORITES_FOLDER = "Favoriten"
CAMERA_PROFILES_DIR = "CameraProfiles"
DCP_PREP_FILE = "migration_dcp_prep.json"
PROFILE_SCAN_INTERVAL_MS = 4000
_PROFILE_CACHE: Dict[str, Any] = {}


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip().rstrip('.')
    return name or 'Preset'


def _load_rrpreset(path: pathlib.Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    presets = data.get("presets")
    if not isinstance(presets, list) or not presets:
        raise ValueError(f"No presets in {path}")
    return data


def _first_preset_entry(path: pathlib.Path) -> Dict[str, Any]:
    data = _load_rrpreset(path)
    for item in data["presets"]:
        if isinstance(item, dict) and isinstance(item.get("preset"), dict):
            return item
    raise ValueError(f"No preset entry in {path}")


def _source_to_fallback_rel(source: str) -> str:
    pp = pathlib.PurePosixPath(source)
    parent = pathlib.PurePosixPath(*pp.parts[:-1]) if len(pp.parts) > 1 else pathlib.PurePosixPath()
    filename = safe_name(pathlib.Path(pp.name).stem) + ".rrpreset"
    return str(pathlib.PurePosixPath("Presets_Fallback") / parent / filename)


def _find_dcp_preset(output_dir: pathlib.Path, source: str) -> str:
    pp = pathlib.PurePosixPath(source)
    parent = output_dir / "Presets_DCP_Aware" / pathlib.Path(*pp.parts[:-1])
    stem = safe_name(pathlib.Path(pp.name).stem)
    candidates = [parent / f"{stem} [DCP].rrpreset", parent / f"{stem}.rrpreset"]
    for c in candidates:
        if c.exists():
            return c.relative_to(output_dir).as_posix()
    # Last-resort exact directory scan for generated name variants.
    if parent.exists():
        hits = sorted(parent.glob(stem + "*DCP*.rrpreset"))
        if hits:
            return hits[0].relative_to(output_dir).as_posix()
    return ""


def _catalog_id(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def generate_catalog(output_dir: str | pathlib.Path) -> Dict[str, Any]:
    """Create migration_catalog.json and the generated HTML UI in a converted output folder."""
    out = pathlib.Path(output_dir).resolve()
    report = out / "dcp_match_report.csv"
    if not report.exists():
        raise FileNotFoundError(f"Missing {report.name} in {out}")

    prep_path = out / DCP_PREP_FILE
    try:
        prep_by_source = json.loads(prep_path.read_text(encoding="utf-8")) if prep_path.exists() else {}
    except Exception:
        prep_by_source = {}
    (out / CAMERA_PROFILES_DIR).mkdir(exist_ok=True)
    cp_readme = out / CAMERA_PROFILES_DIR / "README.txt"
    if not cp_readme.exists():
        cp_readme.write_text("Place your own .dcp camera profiles here. Subfolders are supported. The Preset Manager scans this folder automatically.\n", encoding="utf-8")

    rows: List[Dict[str, Any]] = []
    with report.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            source = (r.get("Source") or "").replace("\\", "/")
            if not source:
                continue
            fallback_rel = _source_to_fallback_rel(source)
            fallback_abs = out / pathlib.Path(*pathlib.PurePosixPath(fallback_rel).parts)
            if not fallback_abs.exists():
                # The report may include a source that failed later; skip rather than emit a broken row.
                continue
            dcp_rel = _find_dcp_preset(out, source) if (r.get("Mode") == "exact DCP match") else ""
            lut_rel = (r.get("CompanionLUT") or "").replace("\\", "/")
            if lut_rel and not (out / pathlib.Path(*pathlib.PurePosixPath(lut_rel).parts)).exists():
                lut_rel = ""
            if dcp_rel and not lut_rel:
                # DCP-aware presets without the companion LUT are not exposed as selectable DCP variants.
                dcp_rel = ""
            src_parent = pathlib.PurePosixPath(source).parent.as_posix()
            group = src_parent if src_parent not in ("", ".") else "Lightroom Migration"
            rows.append({
                "id": _catalog_id(source),
                "source": source,
                "name": r.get("Preset") or pathlib.Path(source).stem,
                "group": group,
                "bw": (r.get("BW") or "").lower() == "yes",
                "cameraProfile": r.get("CameraProfile") or "",
                "cameraProfileKey": norm_profile_name(r.get("CameraProfile") or ""),
                "mode": r.get("Mode") or "fallback",
                "matchedProfile": r.get("MatchedProfile") or "",
                "matchedCamera": r.get("MatchedCamera") or "",
                "fallbackPreset": fallback_rel,
                "dcpPreset": dcp_rel,
                "companionLUT": lut_rel,
                "dcpPrep": prep_by_source.get(source, {}),
                "defaultVariant": "fallback",
            })

    rows.sort(key=lambda x: (x["group"].casefold(), x["name"].casefold(), x["source"].casefold()))
    catalog = {
        "version": 1,
        "generatedAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "migPrefix": MIG_PREFIX.rstrip(),
        "outputRoot": str(out),
        "presets": rows,
        "stats": {
            "total": len(rows),
            "bw": sum(1 for x in rows if x["bw"]),
            "color": sum(1 for x in rows if not x["bw"]),
            "dcpAvailable": sum(1 for x in rows if x["dcpPreset"]),
            "cameraProfileRequested": sum(1 for x in rows if x["cameraProfile"] and not is_builtin_profile(x["cameraProfile"])),
            "groups": len({x["group"] for x in rows}),
        },
    }
    (out / CATALOG_FILE).write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / HTML_FILE).write_text(_html_page(), encoding="utf-8")

    # Put launchable manager files directly next to the generated HTML/catalog when available.
    here = pathlib.Path(__file__).resolve().parent
    mgr_src = here / "preset_manager.py"
    if mgr_src.exists() and mgr_src.resolve() != (out / "preset_manager.py").resolve():
        shutil.copy2(mgr_src, out / "preset_manager.py")
    dcp_src = here / "dcp_support.py"
    if dcp_src.exists() and dcp_src.resolve() != (out / "dcp_support.py").resolve():
        shutil.copy2(dcp_src, out / "dcp_support.py")
    bat_src = here / "Start_Preset_Manager_Windows.bat"
    if bat_src.exists():
        shutil.copy2(bat_src, out / "Start_Preset_Manager_Windows.bat")
    sh_src = here / "Start_Preset_Manager_Linux.sh"
    if sh_src.exists():
        target = out / "Start_Preset_Manager_Linux.sh"
        shutil.copy2(sh_src, target)
        try:
            target.chmod(target.stat().st_mode | 0o111)
        except Exception:
            pass
    return catalog


def _flatpak_installed() -> bool:
    if os.name == "nt" or sys.platform == "darwin":
        return False
    app_root = pathlib.Path.home() / ".var" / "app" / APP_DIR_NAME
    if app_root.exists():
        return True
    try:
        r = subprocess.run(["flatpak", "info", APP_DIR_NAME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


def rapidraw_storage_info() -> Dict[str, str]:
    """Resolve RapidRAW's live presets.json location across Windows/macOS/Linux/Flatpak.

    Tauri's app_data_dir on Linux is $XDG_DATA_HOME/<bundle-id>. Flatpak sets
    XDG_DATA_HOME to ~/.var/app/<bundle-id>/data, so the canonical Flatpak path is:
      ~/.var/app/<bundle-id>/data/<bundle-id>/presets/presets.json
    Existing files always win so we also support older/alternate layouts conservatively.
    """
    override = os.environ.get("RAPIDRAW_PRESETS_JSON")
    if override:
        path = pathlib.Path(override).expanduser().resolve()
        return {"path": str(path), "mode": "Manueller Override", "platform": sys.platform}

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA environment variable is missing")
        path = pathlib.Path(appdata) / APP_DIR_NAME / "presets" / "presets.json"
        return {"path": str(path), "mode": "Windows", "platform": "Windows"}

    if sys.platform == "darwin":
        path = pathlib.Path.home() / "Library" / "Application Support" / APP_DIR_NAME / "presets" / "presets.json"
        return {"path": str(path), "mode": "macOS", "platform": "macOS"}

    home = pathlib.Path.home()
    flatpak_root = home / ".var" / "app" / APP_DIR_NAME
    flatpak_candidates = [
        flatpak_root / "data" / APP_DIR_NAME / "presets" / "presets.json",
        flatpak_root / "data" / "presets" / "presets.json",
    ]
    xdg = pathlib.Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    native_candidates = [
        xdg / APP_DIR_NAME / "presets" / "presets.json",
        home / ".local" / "share" / APP_DIR_NAME / "presets" / "presets.json",
    ]

    # Never choose a guessed location over a real presets.json.
    for candidate in flatpak_candidates:
        if candidate.exists():
            return {"path": str(candidate), "mode": "Linux Flatpak", "platform": "Linux"}
    for candidate in native_candidates:
        if candidate.exists():
            return {"path": str(candidate), "mode": "Linux nativ", "platform": "Linux"}

    # If the Flatpak is installed (or its app root exists), prefer the canonical Tauri path.
    if _flatpak_installed():
        return {"path": str(flatpak_candidates[0]), "mode": "Linux Flatpak", "platform": "Linux"}
    return {"path": str(native_candidates[0]), "mode": "Linux nativ", "platform": "Linux"}


def rapidraw_presets_path() -> pathlib.Path:
    return pathlib.Path(rapidraw_storage_info()["path"]).expanduser().resolve()


def favorites_state_path(root: pathlib.Path) -> pathlib.Path:
    return root / FAVORITES_STATE_FILE


def _read_manager_state(root: pathlib.Path) -> Dict[str, Any]:
    path=favorites_state_path(root)
    if not path.exists(): return {"version":2,"favoriteIds":[],"profileSelections":{}}
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data,dict): data={}
    except Exception:
        data={}
    data.setdefault("version",2); data.setdefault("favoriteIds",[]); data.setdefault("profileSelections",{})
    return data


def _write_manager_state(root:pathlib.Path, data:Dict[str,Any]) -> None:
    path=favorites_state_path(root)
    data=dict(data); data["version"]=2; data["updatedAt"]=_dt.datetime.now().astimezone().isoformat(timespec="seconds")
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)


def load_favorites(root: pathlib.Path, catalog: Dict[str, Any]) -> set[str]:
    valid={str(p.get("id")) for p in catalog.get("presets",[]) if p.get("id")}
    ids=_read_manager_state(root).get("favoriteIds",[])
    return {str(x) for x in ids if str(x) in valid}


def save_favorites(root: pathlib.Path, catalog: Dict[str, Any], favorite_ids: Iterable[str]) -> set[str]:
    valid={str(p.get("id")) for p in catalog.get("presets",[]) if p.get("id")}
    fav={str(x) for x in favorite_ids if str(x) in valid}
    data=_read_manager_state(root); data["favoriteIds"]=sorted(fav); _write_manager_state(root,data)
    return fav


def load_profile_selections(root:pathlib.Path, catalog:Dict[str,Any]) -> Dict[str,str]:
    valid={str(p.get("id")) for p in catalog.get("presets",[]) if p.get("id")}
    raw=_read_manager_state(root).get("profileSelections",{})
    if not isinstance(raw,dict): return {}
    return {str(k):str(v) for k,v in raw.items() if str(k) in valid and v}


def save_profile_selections(root:pathlib.Path, catalog:Dict[str,Any], selections:Dict[str,str], merge:bool=True) -> Dict[str,str]:
    valid={str(p.get("id")) for p in catalog.get("presets",[]) if p.get("id")}
    data=_read_manager_state(root)
    current=data.get("profileSelections",{}) if merge else {}
    if not isinstance(current,dict): current={}
    for k,v in selections.items():
        k=str(k); v=str(v or "")
        if k not in valid: continue
        if v: current[k]=v
        else: current.pop(k,None)
    data["profileSelections"]=current; _write_manager_state(root,data)
    return {str(k):str(v) for k,v in current.items()}


def _profile_library_dir(root:pathlib.Path)->pathlib.Path:
    p=root/CAMERA_PROFILES_DIR; p.mkdir(parents=True,exist_ok=True); return p


def _profile_snapshot(folder:pathlib.Path)->Tuple[Tuple[str,int,int],...]:
    rows=[]
    for f in sorted(folder.rglob("*.dcp"),key=lambda x:x.as_posix().casefold()):
        try:
            st=f.stat(); rows.append((f.relative_to(folder).as_posix(),int(st.st_size),int(st.st_mtime_ns)))
        except OSError: pass
    return tuple(rows)


def scan_camera_profiles(root:pathlib.Path, force:bool=False)->Dict[str,Any]:
    """Scan CameraProfiles recursively with per-file incremental parsing cache."""
    folder=_profile_library_dir(root); key=str(folder.resolve()); snap=_profile_snapshot(folder); cached=_PROFILE_CACHE.get(key)
    if cached and not force and cached.get("snapshot")==snap: return cached
    old_files=(cached or {}).get("fileCache",{}) if not force else {}
    file_cache={}; profiles=[]; internal={}; errors=[]; seen_content=set()
    for rel,size,mtime in snap:
        sig=(size,mtime); old=old_files.get(rel)
        try:
            if old and old.get("sig")==sig:
                content_hash=old["hash"]; prof=old["profile"]
            else:
                raw=(folder/pathlib.PurePosixPath(rel)).read_bytes(); content_hash=hashlib.sha256(raw).hexdigest(); prof=profile_from_bytes(raw,rel)
            file_cache[rel]={"sig":sig,"hash":content_hash,"profile":prof}
            if content_hash in seen_content: continue
            seen_content.add(content_hash); pid=content_hash[:20]; internal[pid]=prof
            profiles.append({"id":pid,"name":prof.name,"nameKey":norm_profile_name(prof.name),"camera":prof.camera or "Unbekannte Kamera",
                             "file":rel,"hasHueSatMap":bool(prof.hsm1 or prof.hsm2),"hasLookTable":bool(prof.look_data),
                             "hasToneCurve":bool(prof.tone_curve),"size":size})
        except Exception as e: errors.append({"file":rel,"error":str(e)})
    profiles.sort(key=lambda x:(x["name"].casefold(),x["camera"].casefold(),x["file"].casefold()))
    result={"snapshot":snap,"profiles":profiles,"internal":internal,"errors":errors,"folder":str(folder.resolve()),"fileCache":file_cache,
            "scanToken":hashlib.sha1(repr(snap).encode()).hexdigest()[:12],"scannedAt":_dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    _PROFILE_CACHE[key]=result; return result


def public_profile_library(root:pathlib.Path, catalog:Dict[str,Any], force:bool=False)->Dict[str,Any]:
    lib=scan_camera_profiles(root,force)
    usage={p["id"]:0 for p in lib["profiles"]}
    exact_by_key={}
    for p in lib["profiles"]: exact_by_key.setdefault(p["nameKey"],[]).append(p["id"])
    requested={}
    for row in catalog.get("presets",[]):
        key=row.get("cameraProfileKey") or norm_profile_name(row.get("cameraProfile", ""))
        ids=exact_by_key.get(key,[]) if key and not is_builtin_profile(row.get("cameraProfile", "")) else []
        requested[row["id"]]=ids
        for pid in ids: usage[pid]=usage.get(pid,0)+1
    return {"profiles":[dict(p,usedBy=usage.get(p["id"],0)) for p in lib["profiles"]],"matchesByPreset":requested,
            "errors":lib["errors"],"folder":lib["folder"],"scanToken":lib["scanToken"],"scannedAt":lib["scannedAt"],"count":len(lib["profiles"])}


def rapidraw_running() -> bool:
    try:
        if os.name == "nt":
            out = subprocess.check_output(["tasklist"], text=True, errors="ignore", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            low = out.casefold()
            return "rapidraw.exe" in low or "rapidraw " in low
        # Flatpak exposes a reliable application id even though the actual process
        # may be wrapped by bwrap/xdg-dbus-proxy. Prefer that signal when available.
        try:
            fp = subprocess.check_output(["flatpak", "ps", "--columns=application"], text=True, errors="ignore", timeout=3)
            if any(line.strip() == APP_DIR_NAME for line in fp.splitlines()):
                return True
        except Exception:
            pass
        out = subprocess.check_output(["ps", "-eo", "pid=,comm=,args="], text=True, errors="ignore")
        me = os.getpid()
        for line in out.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if pid == me:
                continue
            comm = parts[1].casefold()
            args = parts[2].casefold() if len(parts) > 2 else ""
            # Match the actual application executable, not paths/catalog names containing RapidRAW.
            if comm in ("rapidraw", "rapidraw.exe") or re.search(r"(^|[/\\])rapidraw(?:\.exe)?(?:\s|$)", args):
                return True
        return False
    except Exception:
        return False


def load_live_presets(path: pathlib.Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("RapidRAW presets.json must contain a JSON array")
    return data


def _name_of_preset_item(item: Dict[str, Any]) -> str:
    if isinstance(item.get("preset"), dict):
        return str(item["preset"].get("name", ""))
    if isinstance(item.get("folder"), dict):
        return str(item["folder"].get("name", ""))
    return ""


def _is_mig_name(name: str) -> bool:
    return name.startswith(MIG_PREFIX) or name == MIG_PREFIX.rstrip()


def strip_migrated(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Remove only [MIG] folders/presets, including MIG children in native folders."""
    cleaned: List[Dict[str, Any]] = []
    removed = 0
    for item in items:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue
        if isinstance(item.get("preset"), dict):
            if _is_mig_name(str(item["preset"].get("name", ""))):
                removed += 1
                continue
            cleaned.append(item)
            continue
        if isinstance(item.get("folder"), dict):
            folder = item["folder"]
            if _is_mig_name(str(folder.get("name", ""))):
                removed += 1 + len(folder.get("children") or [])
                continue
            new_item = json.loads(json.dumps(item))
            children = new_item["folder"].get("children")
            if isinstance(children, list):
                kept = []
                for child in children:
                    if isinstance(child, dict) and _is_mig_name(str(child.get("name", ""))):
                        removed += 1
                    else:
                        kept.append(child)
                new_item["folder"]["children"] = kept
            cleaned.append(new_item)
            continue
        cleaned.append(item)
    return cleaned, removed


def _preset_uuid(catalog_id: str, variant: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rapidraw-migration:preset:{catalog_id}:{variant}"))


def _favorite_preset_uuid(catalog_id: str, variant: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rapidraw-migration:favorite:{catalog_id}:{variant}"))


def _folder_uuid(group: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rapidraw-migration:folder:{group}"))


def _collect_live_ids(items: Iterable[Dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("preset"), dict):
            if item["preset"].get("id"):
                ids.add(str(item["preset"]["id"]))
        elif isinstance(item.get("folder"), dict):
            f = item["folder"]
            if f.get("id"):
                ids.add(str(f["id"]))
            for p in f.get("children") or []:
                if isinstance(p, dict) and p.get("id"):
                    ids.add(str(p["id"]))
    return ids


def _count_presets(items: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("preset"), dict):
            count += 1
        elif isinstance(item.get("folder"), dict):
            count += len(item["folder"].get("children") or [])
    return count


def backup_and_write(path: pathlib.Path, items: List[Dict[str, Any]]) -> pathlib.Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup_dir = path.parent / "migration_backups"
        backup_dir.mkdir(exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = backup_dir / f"presets-before-MIG-{stamp}.json"
        shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    # Validate the bytes we are about to swap in.
    parsed = json.loads(tmp.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        tmp.unlink(missing_ok=True)
        raise ValueError("Generated presets.json is not a JSON array")
    os.replace(tmp, path)
    return backup


def _resolve_catalog_file(root: pathlib.Path, rel_posix: str) -> pathlib.Path:
    pp = pathlib.PurePosixPath(rel_posix)
    p = root.joinpath(*pp.parts).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Catalog path escapes output directory")
    return p


def _cleanup_manager_luts(lut_dir:pathlib.Path, used:set[pathlib.Path]) -> None:
    lut_dir.mkdir(parents=True,exist_ok=True)
    used_resolved={p.resolve() for p in used}
    for p in lut_dir.glob("*.cube"):
        try:
            if p.resolve() not in used_resolved: p.unlink(missing_ok=True)
        except Exception: pass


def _prepare_dynamic_dcp_entry(entry:Dict[str,Any], row:Dict[str,Any]) -> Dict[str,Any]:
    """For B&W legacy presets, restore color before the companion LUT performs B&W."""
    entry=json.loads(json.dumps(entry))
    if not row.get("bw"): return entry
    prep=row.get("dcpPrep") or {}; adj=entry["preset"].setdefault("adjustments",{})
    adj["saturation"]=float(prep.get("saturation",0.0) or 0.0)
    hsl=adj.get("hsl")
    lum=prep.get("hslLuminance") or {}
    if isinstance(hsl,dict):
        for color,val in lum.items():
            if color in hsl and isinstance(hsl[color],dict): hsl[color]["luminance"]=float(val or 0.0)
    return entry


def _dynamic_lut(root:pathlib.Path, live_path:pathlib.Path, row:Dict[str,Any], profile_id:str, profile:DCPProfile, grid:int=33)->Tuple[pathlib.Path,bool]:
    lut_dir=live_path.parent/LUT_SUBDIR; lut_dir.mkdir(parents=True,exist_ok=True)
    prep=row.get("dcpPrep") or {}; gray=prep.get("grayMixer") or {}
    recipe={"profile":profile_id,"bw":bool(row.get("bw")),"gray":gray if row.get("bw") else {},"grid":grid,"recipe":"bw25-curve1" if row.get("bw") else "color1"}
    key=hashlib.sha1(json.dumps(recipe,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()[:14]
    fn=f"{safe_name(profile.name)}__{'BW' if row.get('bw') else 'COLOR'}__{key}.cube"
    dest=lut_dir/fn; created=False
    if not dest.exists():
        if row.get("bw"):
            vals={k:float(gray.get(k,0.0) or 0.0) for k in ("Red","Orange","Yellow","Green","Aqua","Blue","Purple","Magenta")}
            make_bw_lut(dest,profile,vals,0.25,0.01,grid)
        else:
            make_color_lut(dest,profile,0.01,grid)
        created=True
    return dest,created


def build_migrated_items(catalog: Dict[str, Any], root: pathlib.Path, selections: List[Dict[str, str]], live_path: pathlib.Path, favorite_ids: Iterable[str] = ()) -> Tuple[List[Dict[str, Any]], int, int, set[pathlib.Path]]:
    by_id={p["id"]:p for p in catalog.get("presets",[])}
    groups:Dict[str,List[Dict[str,Any]]]={}; favorites=[]; favorite_set={str(x) for x in favorite_ids}
    lib=scan_camera_profiles(root); profile_map=lib["internal"]
    grid=int(catalog.get("lutGrid",33) or 33)
    generated_luts=0; used_luts:set[pathlib.Path]=set()

    for sel in selections:
        cid=str(sel.get("id","")); row=by_id.get(cid)
        if not row: raise ValueError(f"Unknown catalog id: {cid}")
        profile_id=str(sel.get("profileId") or "")
        preset_path=_resolve_catalog_file(root,row.get("fallbackPreset") or "")
        entry=json.loads(json.dumps(_first_preset_entry(preset_path)))
        variant="fallback"; suffix=""
        if profile_id:
            profile=profile_map.get(profile_id)
            if not profile: raise ValueError(f"Selected CameraProfile is no longer present: {row.get('name')}")
            wanted=row.get("cameraProfile") or ""
            if not wanted or is_builtin_profile(wanted) or norm_profile_name(profile.name)!=norm_profile_name(wanted):
                raise ValueError(f"CameraProfile '{profile.name}' does not exactly match preset requirement '{wanted}'")
            entry=_prepare_dynamic_dcp_entry(entry,row)
            lut,created=_dynamic_lut(root,live_path,row,profile_id,profile,grid)
            generated_luts+=int(created); used_luts.add(lut)
            adj=entry["preset"].setdefault("adjustments",{})
            adj["lutPath"]=str(lut.resolve()); adj["lutName"]=lut.name; adj["lutIntensity"]=100
            if "lutData" in adj: adj["lutData"]=None
            variant=f"profile:{profile_id}"; suffix=" [DCP]"
        p=entry["preset"]
        p["id"]=_preset_uuid(cid,variant); p["name"]=MIG_PREFIX+str(row.get("name") or "Preset")+suffix; p["presetType"]="style"
        group=str(row.get("group") or "Lightroom Migration"); groups.setdefault(group,[]).append(p)
        if cid in favorite_set:
            fav=json.loads(json.dumps(p)); fav["id"]=_favorite_preset_uuid(cid,variant); favorites.append(fav)

    out_items=[]
    if favorites:
        out_items.append({"folder":{"id":_folder_uuid(FAVORITES_FOLDER),"name":MIG_PREFIX+FAVORITES_FOLDER,
                                    "children":sorted(favorites,key=lambda p:str(p.get("name","")).casefold())}})
    for group in sorted(groups,key=str.casefold):
        out_items.append({"folder":{"id":_folder_uuid(group),"name":MIG_PREFIX+group,
                                    "children":sorted(groups[group],key=lambda p:str(p.get("name","")).casefold())}})
    return out_items,generated_luts,len(favorites),used_luts


def sync_to_rapidraw(catalog: Dict[str, Any], root: pathlib.Path, selections: List[Dict[str, str]], favorite_ids: Iterable[str] = ()) -> Dict[str, Any]:
    if rapidraw_running(): raise RuntimeError("RapidRAW is currently running. Please close RapidRAW before updating presets.json.")
    path=rapidraw_presets_path(); current=load_live_presets(path); native,removed=strip_migrated(current)
    fav=save_favorites(root,catalog,favorite_ids)
    # Remember DCP dropdown choices independently from RapidRAW's current import state.
    choices={str(s.get("id")):str(s.get("profileId") or "") for s in selections}
    save_profile_selections(root,catalog,choices,merge=True)
    mig_items,generated_luts,favorite_copies,used_luts=build_migrated_items(catalog,root,selections,path,fav)
    final=native+mig_items; backup=backup_and_write(path,final)
    _cleanup_manager_luts(path.parent/LUT_SUBDIR,used_luts)
    return {"ok":True,"path":str(path),"selected":len(selections),"favorites":len(fav),"favoriteCopies":favorite_copies,
            "removedOldMigrated":removed,"generatedLUTs":generated_luts,"nativePresetCount":_count_presets(native),
            "finalPresetCount":_count_presets(final),"backup":str(backup) if backup else ""}


def remove_all_migrated() -> Dict[str, Any]:
    if rapidraw_running():
        raise RuntimeError("RapidRAW is currently running. Please close RapidRAW before updating presets.json.")
    path = rapidraw_presets_path()
    current = load_live_presets(path)
    cleaned, removed = strip_migrated(current)
    backup = backup_and_write(path, cleaned)
    lut_dir = path.parent / LUT_SUBDIR
    if lut_dir.exists():
        shutil.rmtree(lut_dir, ignore_errors=True)
    return {"ok": True, "path": str(path), "removed": removed, "backup": str(backup) if backup else ""}


def state_for_catalog(catalog: Dict[str, Any], root: pathlib.Path) -> Dict[str, Any]:
    path=rapidraw_presets_path(); current=load_live_presets(path); ids=_collect_live_ids(current)
    lib=scan_camera_profiles(root); profile_map=lib["internal"]
    imported:Dict[str,str]={}
    for row in catalog.get("presets",[]):
        cid=row["id"]
        if _preset_uuid(cid,"fallback") in ids:
            imported[cid]="fallback"; continue
        wanted=norm_profile_name(row.get("cameraProfile", ""))
        for pid,profile in profile_map.items():
            if wanted and norm_profile_name(profile.name)==wanted and _preset_uuid(cid,f"profile:{pid}") in ids:
                imported[cid]=pid; break
    stripped,removed=strip_migrated(current); favorites=load_favorites(root,catalog); storage=rapidraw_storage_info()
    return {"path":str(path),"exists":path.exists(),"platform":storage.get("platform",sys.platform),"storageMode":storage.get("mode",""),
            "rapidrawRunning":rapidraw_running(),"imported":imported,"importedCount":len(imported),
            "nativePresetCount":_count_presets(stripped),"migratedItemCount":removed,"favorites":sorted(favorites),
            "favoriteCount":len(favorites),"profileSelections":load_profile_selections(root,catalog)}


class _ManagerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "RapidRAWMigrationManager/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep console useful without logging every asset request.
        if self.path.startswith("/api/"):
            super().log_message(fmt, *args)

    @property
    def app(self):
        return self.server.app  # type: ignore[attr-defined]

    def _send_json(self, obj: Any, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Any:
        n = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/" + HTML_FILE):
            data = (self.app["root"] / HTML_FILE).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(data); return
        if path == "/api/catalog":
            self._send_json(self.app["catalog"]); return
        if path == "/api/state":
            try: self._send_json(state_for_catalog(self.app["catalog"], self.app["root"]))
            except Exception as e: self._send_json({"ok": False, "error": str(e)}, 500)
            return
        if path == "/api/profiles":
            try: self._send_json(public_profile_library(self.app["root"], self.app["catalog"], False))
            except Exception as e: self._send_json({"ok": False, "error": str(e)}, 500)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/sync":
                body = self._read_json(); sels = body.get("selections", []); favs = body.get("favorites", [])
                if not isinstance(sels, list): raise ValueError("selections must be an array")
                if not isinstance(favs, list): raise ValueError("favorites must be an array")
                self._send_json(sync_to_rapidraw(self.app["catalog"], self.app["root"], sels, favs)); return
            if path == "/api/favorites":
                body = self._read_json(); favs = body.get("favorites", [])
                if not isinstance(favs, list): raise ValueError("favorites must be an array")
                saved = save_favorites(self.app["root"], self.app["catalog"], favs)
                self._send_json({"ok": True, "favorites": sorted(saved), "favoriteCount": len(saved)}); return
            if path == "/api/profile-preferences":
                body=self._read_json(); choices=body.get("profileSelections",{})
                if not isinstance(choices,dict): raise ValueError("profileSelections must be an object")
                saved=save_profile_selections(self.app["root"],self.app["catalog"],choices,True)
                self._send_json({"ok":True,"profileSelections":saved}); return
            if path == "/api/rescan-profiles":
                self._send_json(public_profile_library(self.app["root"],self.app["catalog"],True)); return
            if path == "/api/remove-migrated":
                self._send_json(remove_all_migrated()); return
            if path == "/api/shutdown":
                self._send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send_error(404)
        except RuntimeError as e:
            self._send_json({"ok": False, "error": str(e)}, 409)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)


def serve_manager(catalog_path: str | pathlib.Path, port: int = 0, open_browser: bool = True) -> int:
    cp = pathlib.Path(catalog_path).resolve()
    if cp.is_dir(): cp = cp / CATALOG_FILE
    if not cp.exists(): raise FileNotFoundError(cp)
    root = cp.parent
    if not (root / HTML_FILE).exists():
        (root / HTML_FILE).write_text(_html_page(), encoding="utf-8")
    catalog = json.loads(cp.read_text(encoding="utf-8"))

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    srv = Server(("127.0.0.1", port), _ManagerHandler)
    srv.app = {"catalog": catalog, "root": root}  # type: ignore[attr-defined]
    actual_port = srv.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"RapidRAW Preset Manager: {url}")
    print(f"Catalog: {cp}")
    storage = rapidraw_storage_info()
    print(f"RapidRAW Speicher: {storage.get('mode', '')}")
    print(f"RapidRAW presets.json: {storage.get('path', rapidraw_presets_path())}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


def choose_catalog() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        f = filedialog.askopenfilename(title="migration_catalog.json auswählen", filetypes=[("Migration catalog", "migration_catalog.json"), ("JSON", "*.json"), ("Alle", "*.*")])
        root.destroy()
        return f
    except Exception:
        return ""


def _html_page() -> str:
    # Static shell; catalog/state/profile library are fetched from the local Python server.
    return r'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RapidRAW Preset Migrator - Preset Manager</title>
<style>
:root{font-family:Segoe UI,system-ui,sans-serif;color-scheme:dark;background:#111318;color:#e7eaf0}*{box-sizing:border-box}body{margin:0;background:#111318}.wrap{max-width:1650px;margin:auto;padding:22px}.top{position:sticky;top:0;z-index:5;background:rgba(17,19,24,.96);backdrop-filter:blur(10px);padding:8px 0 14px;border-bottom:1px solid #2a2f39}h1{font-size:24px;margin:0 0 5px}.muted{color:#9ba6b5;font-size:13px}.status{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.pill{background:#20252e;border:1px solid #333a46;border-radius:999px;padding:5px 9px;font-size:12px}.danger{color:#ff9c9c}.ok{color:#91e5aa}.warn{color:#f2cd72}.controls{display:grid;grid-template-columns:minmax(260px,1fr) 190px 190px auto;gap:8px;margin:12px 0}input[type=search],select,button{background:#20252e;color:#eef1f5;border:1px solid #353c49;border-radius:8px;padding:9px 11px}button{cursor:pointer;font-weight:600}button.primary{background:#2d6cdf;border-color:#3b7bf0}button.dangerBtn{background:#4a2025;border-color:#6a3038}.bulk{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px}.tableWrap{border:1px solid #2b313b;border-radius:10px;overflow:auto;max-height:64vh}table{width:100%;border-collapse:collapse;font-size:13px}th{position:sticky;top:0;background:#1b1f27;text-align:left;padding:9px;border-bottom:1px solid #333a46;white-space:nowrap}td{padding:7px 9px;border-bottom:1px solid #242a33;vertical-align:middle}tr:hover{background:#181c23}.name{font-weight:600}.small{font-size:12px;color:#9ba6b5}.profileSelect{min-width:280px;max-width:430px;width:100%}.imported{color:#8ee3a5}.favBtn{border:0;background:transparent;padding:0 4px;font-size:23px;line-height:1;color:#6d7684}.favBtn.on{color:#ffd45b;text-shadow:0 0 8px rgba(255,212,91,.25)}.favBtn:hover{transform:scale(1.1)}.footer{margin-top:12px;font-size:12px;color:#929cab}.profilePanel{margin:12px 0;border:1px solid #2b313b;border-radius:10px;background:#171a21}.profilePanel summary{cursor:pointer;padding:11px 13px;font-weight:700}.profilePanelInner{padding:0 13px 12px}.profileActions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 9px}.profileTableWrap{max-height:240px;overflow:auto;border:1px solid #2b313b;border-radius:8px}.profileTableWrap th{top:0}.tag{display:inline-block;border:1px solid #3a4250;border-radius:999px;padding:2px 6px;font-size:11px;color:#aeb8c6}.hidden{display:none!important}@media(max-width:950px){.controls{grid-template-columns:1fr 1fr}.hideSmall{display:none}.profileSelect{min-width:220px}}
</style></head><body><div class="wrap"><div class="top">
<h1>RapidRAW Preset Migrator <span class="small">v1.0.0</span></h1>
<div class="muted">Nur Einträge mit <b>[MIG]</b> werden angelegt oder gelöscht. Eigene <code>.dcp</code>-Profile einfach in <b>CameraProfiles/</b> legen – der Manager erkennt sie automatisch und bietet exakt passende Profile im Dropdown an.</div>
<div id="status" class="status"></div>
<div class="controls"><input id="q" type="search" placeholder="Preset, Ordner oder Profil suchen…"><select id="group"><option value="">Alle Ordner</option></select><select id="type"><option value="">Farbe + B&W</option><option value="color">Farbe</option><option value="bw">B&W</option><option value="dcp">CameraProfile verfügbar</option><option value="missing">CameraProfile fehlt</option><option value="favorite">Nur Favoriten</option><option value="selected">Nur ausgewählt</option></select><button id="refresh">Aktualisieren</button></div>
<div class="bulk"><button id="all">Alle sichtbaren</button><button id="none">Keine sichtbaren</button><button id="invert">Sichtbare umkehren</button><button id="favAll">★ Sichtbare favorisieren</button><button id="favNone">☆ Sichtbare entfavorisieren</button><button id="apply" class="primary">START – Auswahl in RapidRAW übernehmen</button><button id="remove" class="dangerBtn">Alle [MIG] aus RapidRAW löschen</button></div>
</div>
<details class="profilePanel"><summary id="profileSummary">Camera Profile Library</summary><div class="profilePanelInner"><div class="profileActions"><button id="rescanProfiles">🔄 CameraProfiles neu einlesen</button><span class="small" id="profileFolder"></span></div><div class="profileTableWrap"><table><thead><tr><th>Profil</th><th>Kamera</th><th>Verwendung</th><th>Datei</th><th>Inhalt</th></tr></thead><tbody id="profileBody"></tbody></table></div><div class="small" id="profileErrors"></div></div></details>
<div class="tableWrap"><table><thead><tr><th>★</th><th>✓</th><th>Preset</th><th>Ordner</th><th>Typ</th><th>Camera Profile / Variante</th><th class="hideSmall">Lightroom erwartet</th><th>Status</th></tr></thead><tbody id="body"></tbody></table></div>
<div class="footer" id="footer"></div></div>
<script>
let catalog=null,state=null,profilesData={profiles:[],matchesByPreset:{},errors:[]},selection=new Map(),favorites=new Set(),favSaveTimer=null,profileSaveTimer=null,lastProfileToken='';
const $=s=>document.querySelector(s); const esc=s=>(s??'').toString().replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function jget(u){let r=await fetch(u,{cache:'no-store'});let j=await r.json();if(!r.ok)throw new Error(j.error||r.statusText);return j}
async function jpost(u,b={}){let r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});let j=await r.json();if(!r.ok)throw new Error(j.error||r.statusText);return j}
function profileById(id){return profilesData.profiles.find(p=>p.id===id)}
function matches(p){return profilesData.matchesByPreset?.[p.id]||[]}
function defaults(){selection.clear();for(const p of catalog.presets)selection.set(p.id,{on:false,profileId:''})}
function visible(p){let q=$('#q').value.trim().toLowerCase(),g=$('#group').value,t=$('#type').value;if(g&&p.group!==g)return false;let ps=matches(p).map(id=>profileById(id)).filter(Boolean);let hay=`${p.name} ${p.group} ${p.cameraProfile} ${ps.map(x=>x.camera+' '+x.name).join(' ')}`.toLowerCase();if(q&&!hay.includes(q))return false;let s=selection.get(p.id);if(t==='bw'&&!p.bw)return false;if(t==='color'&&p.bw)return false;if(t==='dcp'&&!ps.length)return false;if(t==='missing'&&(!p.cameraProfile||ps.length))return false;if(t==='favorite'&&!favorites.has(p.id))return false;if(t==='selected'&&!s?.on)return false;return true}
function profileOptions(p,s){let ids=matches(p),opts='<option value="">Standard / ohne DCP</option>';for(const id of ids){let cp=profileById(id);if(!cp)continue;let label=`${cp.camera} — ${cp.name}`;opts+=`<option value="${esc(id)}" ${s?.profileId===id?'selected':''}>${esc(label)}</option>`}return opts}
function render(){let b=$('#body');b.innerHTML='';let shown=0,selected=0;for(const p of catalog.presets){let s=selection.get(p.id);if(s?.on)selected++;if(!visible(p))continue;shown++;let tr=document.createElement('tr'),imp=state?.imported?.[p.id],fav=favorites.has(p.id),ps=matches(p),chosen=profileById(s?.profileId),impProf=imp&&imp!=='fallback'?profileById(imp):null;let profStatus=ps.length?`${ps.length} passend`:(p.cameraProfile?'kein DCP':'—');tr.innerHTML=`<td><button class="favBtn ${fav?'on':''}" data-id="${p.id}" title="${fav?'Favorit entfernen':'Als Favorit markieren'}">${fav?'★':'☆'}</button></td><td><input class="pick" data-id="${p.id}" type="checkbox" ${s?.on?'checked':''}></td><td><div class="name">${esc(p.name)}</div><div class="small">${esc(p.source)}</div></td><td>${esc(p.group)}</td><td>${p.bw?'B&W':'Farbe'}</td><td><select class="profileSelect" data-id="${p.id}">${profileOptions(p,s)}</select><div class="small ${ps.length?'ok':(p.cameraProfile?'warn':'')}">${esc(chosen?('gewählt: '+chosen.camera):profStatus)}</div></td><td class="hideSmall">${esc(p.cameraProfile||'—')}</td><td class="${imp?'imported':''}">${imp?(imp==='fallback'?'In RapidRAW · Standard':`In RapidRAW · DCP${impProf?' · '+esc(impProf.camera):''}`):'—'}</td>`;b.appendChild(tr)}
for(const e of document.querySelectorAll('.pick'))e.onchange=()=>{let s=selection.get(e.dataset.id);s.on=e.checked;render()};for(const e of document.querySelectorAll('.profileSelect'))e.onchange=()=>{let s=selection.get(e.dataset.id);s.profileId=e.value;if(e.value)s.on=true;scheduleProfileSave(e.dataset.id,e.value);render()};for(const e of document.querySelectorAll('.favBtn'))e.onclick=()=>toggleFavorite(e.dataset.id);renderStatus(shown,selected)}
function renderStatus(shown,selected){let run=state?.rapidrawRunning,errs=profilesData.errors?.length||0;$('#status').innerHTML=`<span class="pill">Katalog: ${catalog.stats.total}</span><span class="pill">Ausgewählt: ${selected}</span><span class="pill">Favoriten: ${favorites.size}</span><span class="pill">CameraProfiles: ${profilesData.count||0}</span>${errs?`<span class="pill danger">DCP-Fehler: ${errs}</span>`:''}<span class="pill">In RapidRAW: ${state?.importedCount??0}</span><span class="pill">Native: ${state?.nativePresetCount??0}</span><span class="pill">${esc(state?.storageMode||state?.platform||'')}</span><span class="pill ${run?'danger':'ok'}">RapidRAW: ${run?'läuft – bitte schließen':'geschlossen'}</span>`;$('#footer').textContent=`presets.json: ${state?.path||''} · Profile: ${profilesData.folder||''} · Profilwahl und Favoriten: migration_manager_state.json`}
function renderProfiles(){let b=$('#profileBody');b.innerHTML='';for(const p of profilesData.profiles||[]){let tr=document.createElement('tr');let bits=[p.hasHueSatMap?'HueSat':'',p.hasLookTable?'LookTable':'',p.hasToneCurve?'ToneCurve':''].filter(Boolean).join(', ')||'Basis';tr.innerHTML=`<td><b>${esc(p.name)}</b></td><td>${esc(p.camera)}</td><td>${p.usedBy||0} Presets</td><td class="small">${esc(p.file)}</td><td><span class="tag">${esc(bits)}</span></td>`;b.appendChild(tr)}$('#profileSummary').textContent=`Camera Profile Library – ${profilesData.count||0} Profile`;$('#profileFolder').textContent=profilesData.folder||'';let errs=profilesData.errors||[];$('#profileErrors').textContent=errs.length?`${errs.length} Datei(en) konnten nicht gelesen werden: `+errs.slice(0,3).map(e=>e.file).join(', '):''}
function scheduleFavoriteSave(){clearTimeout(favSaveTimer);favSaveTimer=setTimeout(async()=>{try{let r=await jpost('/api/favorites',{favorites:[...favorites]});state.favoriteCount=r.favoriteCount}catch(e){alert('Favoriten konnten nicht gespeichert werden:\n'+e.message)}},180)}
function scheduleProfileSave(id,value){clearTimeout(profileSaveTimer);profileSaveTimer=setTimeout(async()=>{try{await jpost('/api/profile-preferences',{profileSelections:{[id]:value}})}catch(e){alert('Profilwahl konnte nicht gespeichert werden:\n'+e.message)}},180)}
function toggleFavorite(id){if(favorites.has(id))favorites.delete(id);else{favorites.add(id);let s=selection.get(id);if(s)s.on=true}scheduleFavoriteSave();render()}
async function refresh(keep=true){catalog=await jget('/api/catalog');profilesData=await jget('/api/profiles');lastProfileToken=profilesData.scanToken||'';state=await jget('/api/state');if(!keep||!selection.size)defaults();favorites=new Set(state.favorites||[]);let saved=state.profileSelections||{};for(const p of catalog.presets){let s=selection.get(p.id);let valid=new Set(matches(p));let pref=saved[p.id]||s.profileId||'';if(pref&&valid.has(pref))s.profileId=pref;else if(pref&&!valid.has(pref))s.profileId='';let imp=state.imported?.[p.id];if(imp){s.on=true;s.profileId=imp==='fallback'?'':(valid.has(imp)?imp:s.profileId)}}let groups=[...new Set(catalog.presets.map(p=>p.group))].sort((a,b)=>a.localeCompare(b));let cur=$('#group').value;$('#group').innerHTML='<option value="">Alle Ordner</option>'+groups.map(g=>`<option>${esc(g)}</option>`).join('');$('#group').value=groups.includes(cur)?cur:'';renderProfiles();render()}
async function pollProfiles(){try{let p=await jget('/api/profiles');if((p.scanToken||'')!==lastProfileToken){profilesData=p;lastProfileToken=p.scanToken||'';renderProfiles();render()}}catch(e){}}
$('#q').oninput=render;$('#group').onchange=render;$('#type').onchange=render;$('#refresh').onclick=()=>refresh(true);$('#rescanProfiles').onclick=async()=>{try{profilesData=await jpost('/api/rescan-profiles');lastProfileToken=profilesData.scanToken||'';renderProfiles();render()}catch(e){alert(e.message)}};
function bulk(mode){for(const p of catalog.presets)if(visible(p)){let s=selection.get(p.id);s.on=mode==='all'?true:mode==='none'?false:!s.on}render()}
function bulkFav(on){for(const p of catalog.presets)if(visible(p)){if(on){favorites.add(p.id);let s=selection.get(p.id);if(s)s.on=true}else favorites.delete(p.id)}scheduleFavoriteSave();render()}
$('#all').onclick=()=>bulk('all');$('#none').onclick=()=>bulk('none');$('#invert').onclick=()=>bulk('invert');$('#favAll').onclick=()=>bulkFav(true);$('#favNone').onclick=()=>bulkFav(false);
$('#apply').onclick=async()=>{let sels=[];for(const [id,s] of selection)if(s.on)sels.push({id,profileId:s.profileId||''});let dcp=sels.filter(x=>x.profileId).length,favSelected=sels.filter(x=>favorites.has(x.id)).length;if(!confirm(`${sels.length} ausgewählte Presets als [MIG] in RapidRAW synchronisieren?\n${dcp} davon mit CameraProfile/DCP, ${favSelected} zusätzlich in [MIG] Favoriten.\n\nVorhandene [MIG]-Einträge werden ersetzt. Native Presets bleiben erhalten.`))return;try{let r=await jpost('/api/sync',{selections:sels,favorites:[...favorites]});alert(`Fertig. ${r.selected} Presets eingetragen.\n${r.favoriteCopies} Favoriten gespiegelt.\n${r.generatedLUTs} neue Companion-LUT(s) erzeugt.\nBackup: ${r.backup||'keins (Datei war neu)'}`);await refresh(false)}catch(e){alert('Nicht geschrieben:\n'+e.message)}};
$('#remove').onclick=async()=>{if(!confirm('Wirklich ALLE [MIG]-Presets aus RapidRAW entfernen?\nNative Presets bleiben erhalten.\n\nFavoriten und gewählte CameraProfiles bleiben im Manager gespeichert.'))return;try{let r=await jpost('/api/remove-migrated');alert(`${r.removed} [MIG]-Einträge entfernt.\nBackup: ${r.backup||'keins'}`);await refresh(false)}catch(e){alert('Nicht gelöscht:\n'+e.message)}};
refresh(false).then(()=>setInterval(pollProfiles,4000)).catch(e=>alert(e.message));
</script></body></html>'''

def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="RapidRAW [MIG] HTML preset manager")
    ap.add_argument("catalog", nargs="?", help="migration_catalog.json or its directory")
    ap.add_argument("--generate", metavar="OUTPUT_DIR", help="Generate/refresh catalog + HTML in an existing converted output folder")
    ap.add_argument("--port", type=int, default=0, help="Local web server port (0 = automatic)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if a.generate:
        c = generate_catalog(a.generate)
        print(json.dumps(c["stats"], ensure_ascii=False, indent=2))
        return 0
    cp = a.catalog or choose_catalog()
    if not cp:
        print("No catalog selected.")
        return 2
    p = pathlib.Path(cp)
    if p.is_dir(): p = p / CATALOG_FILE
    return serve_manager(p, a.port, not a.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
