"""Programm-Update ueber GitHub Pages (gleiches Prinzip wie A.R.I).

Auf GitHub Pages liegt unter UPDATE_BASE:
    version.json     {"version": 2, "name": "1.0.1", "zip": "rsi-overhead.zip", "sha256": "..."}
    rsi-overhead.zip das Programmpaket
    changelog.json   [{"version": 2, "name": "1.0.1", "notes": "..."}]
Ablauf: pruefen -> laden -> SHA-256 pruefen -> Dateiliste pruefen -> neue .py auf Syntaxfehler testen ->
alte Dateien sichern -> nur Programmdateien ersetzen. Einstellungen/Tastenprofile werden NIE angefasst.
(tools/release.py baut das Paket und schreibt diese Dateien; VERSION/VERSION_NAME pflegt das Skript.)
"""
import hashlib
import json
import os
import py_compile
import re
import shutil
import tempfile
import threading
import time
import urllib.request
import zipfile

VERSION = 6
VERSION_NAME = "1.0.5"
UPDATE_BASE = os.environ.get("RSI_UPDATE_URL") or "https://kingshadow1332.github.io/RSI-Overhead/app/pc/"

BASE = os.path.dirname(os.path.abspath(__file__))
NEVER = {"settings.json", "keybinds_user.json", "backups", "__pycache__", "update_applied.json"}   # oberste Ebene
EXT = {".py", ".html", ".js", ".css", ".json", ".svg", ".png", ".ico", ".woff2", ".md", ".txt", ".bat"}
_lock = threading.Lock()
APPLIED = os.path.join(BASE, "update_applied.json")


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "RSI-Overhead", "Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_version():
    with _get(UPDATE_BASE + "version.json?t=" + str(int(time.time()))) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_changelog():
    try:
        with _get(UPDATE_BASE + "changelog.json?t=" + str(int(time.time()))) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


def check():
    """-> {'ok':True,'current':..,'latest':..,'available':bool,'notes':[..]} oder {'ok':False,'error':..}"""
    try:
        d = fetch_version()
        latest = int(d.get("version", 0))
    except Exception as e:
        return {"ok": False, "error": "KEINE VERBINDUNG ZUM UPDATE-SERVER"}
    notes = []
    if latest > VERSION:
        notes = [str(e.get("notes", "")) for e in sorted(fetch_changelog(), key=lambda e: int(e.get("version", 0) or 0))
                 if VERSION < int(e.get("version", 0) or 0) <= latest and e.get("notes")]
    return {"ok": True, "current": VERSION, "name": VERSION_NAME, "latest": latest, "latest_name": str(d.get("name", latest)),
            "available": latest > VERSION, "notes": notes}


def _already_applied(d):
    try:
        with open(APPLIED, encoding="utf-8") as f:
            a = json.load(f)
        return int(a.get("version", 0)) == int(d.get("version", 0)) and str(a.get("sha256", "")).lower() == str(d.get("sha256", "")).lower()
    except Exception:
        return False


def apply():
    """Laedt und installiert das Update. -> {'ok':True,'files':n,'name':..} oder {'ok':False,'error':..}. Neustart macht der Host."""
    if not _lock.acquire(blocking=False):
        return {"ok": False, "error": "UPDATE LAEUFT BEREITS"}
    tmp = tempfile.mkdtemp(prefix="rsi_update_")
    try:
        try:
            d = fetch_version()
        except Exception:
            return {"ok": False, "error": "KEINE VERBINDUNG ZUM UPDATE-SERVER"}
        if int(d.get("version", 0)) <= VERSION:
            return {"ok": False, "error": "SCHON AUF DEM NEUESTEN STAND"}
        zip_name, want = str(d.get("zip", "")), str(d.get("sha256", "")).lower()
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", zip_name) or not re.fullmatch(r"[0-9a-f]{64}", want):
            return {"ok": False, "error": "UPDATE-BESCHREIBUNG UNGUELTIG"}
        if _already_applied(d):
            return {"ok": False, "error": "UPDATE BEREITS INSTALLIERT (WIEDERHOLUNG VERHINDERT)"}
        zpath = os.path.join(tmp, "update.zip")
        with _get(UPDATE_BASE + zip_name, timeout=120) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f)
        h = hashlib.sha256()
        with open(zpath, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != want:
            return {"ok": False, "error": "PRUEFSUMME FALSCH - NICHTS GEAENDERT"}
        stage, files = os.path.join(tmp, "stage"), []
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                parts = name.split("/")
                if (name.startswith("/") or ".." in parts or ":" in parts[0] or parts[0] in NEVER
                        or os.path.splitext(name)[1].lower() not in EXT):
                    return {"ok": False, "error": "UNERLAUBTE DATEI IM UPDATE: " + name[:40]}
                files.append(name)
            z.extractall(stage)
        for py in [f for f in files if f.endswith(".py")]:
            try:
                py_compile.compile(os.path.join(stage, *py.split("/")), cfile=os.path.join(tmp, "x.pyc"), doraise=True)
            except py_compile.PyCompileError as e:
                return {"ok": False, "error": "FEHLERHAFTE DATEI IM UPDATE: " + py}
        backup = os.path.join(BASE, "backups", "update-" + time.strftime("%Y%m%d_%H%M%S"))
        for name in files:
            dst = os.path.join(BASE, *name.split("/"))
            if os.path.isfile(dst):
                os.makedirs(os.path.dirname(os.path.join(backup, *name.split("/"))), exist_ok=True)
                shutil.copy2(dst, os.path.join(backup, *name.split("/")))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(stage, *name.split("/")), dst)
        with open(APPLIED, "w", encoding="utf-8") as f:
            json.dump({"version": int(d["version"]), "sha256": want}, f)
        return {"ok": True, "files": len(files), "name": str(d.get("name", d["version"]))}
    except Exception as e:
        return {"ok": False, "error": "UPDATE FEHLGESCHLAGEN: " + type(e).__name__}
    finally:
        _lock.release()
        shutil.rmtree(tmp, ignore_errors=True)
