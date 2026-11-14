"""Programm-Update ueber GitHub Pages (gleiches Prinzip wie A.R.I).

Auf GitHub Pages liegt unter UPDATE_BASE:
    version.json     {"version": 2, "name": "1.0.1", "zip": "rsi-overhead.zip", "sha256": "..."}
    rsi-overhead.zip das Programmpaket
    changelog.json   [{"version": 2, "name": "1.0.1", "notes": "..."}]
Ablauf: pruefen -> laden -> SHA-256 pruefen -> Dateiliste pruefen -> neue .py auf Syntaxfehler testen ->
alte Dateien sichern -> nur Programmdateien ersetzen (die Versionsdatei updater.py ZULETZT; bei einem Fehler wird alles
zurueckgerollt). Einstellungen/Tastenprofile werden NIE angefasst.
Ein halb durchgefuehrtes Update (Stempel update_applied.json passt nicht zur Version) wird beim naechsten Pruefen als
"Reparatur" erkannt und nachgeholt.
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

VERSION = 14
VERSION_NAME = "1.0.13"
UPDATE_BASE = os.environ.get("RSI_UPDATE_URL") or "https://kingshadow1332.github.io/RSI-Overhead/app/pc/"

BASE = os.path.dirname(os.path.abspath(__file__))
NEVER = {"settings.json", "keybinds_user.json", "backups", "__pycache__", "update_applied.json"}   # oberste Ebene
EXT = {".py", ".html", ".js", ".css", ".json", ".svg", ".png", ".ico", ".woff2", ".md", ".txt", ".bat"}
_lock = threading.Lock()
APPLIED = os.path.join(BASE, "update_applied.json")
PROGRESS = {"step": "", "pct": 0}          # fuer die Update-Animation (laden, pruefen, installieren, fertig)


def _progress(step, pct):
    PROGRESS["step"], PROGRESS["pct"] = step, int(pct)


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


def needs_repair():
    """True, wenn ein frueheres Update nicht bis zum Ende lief: der Stempel (wird erst GANZ AM ENDE geschrieben) nennt eine
    andere Version als die jetzt installierte updater.py. Fehlt der Stempel (Neuinstallation), gilt der Stand als vollstaendig."""
    try:
        with open(APPLIED, encoding="utf-8") as f:
            return int(json.load(f).get("version", 0)) != VERSION
    except Exception:
        return False


def check():
    """-> {'ok':True,'current':..,'latest':..,'available':bool,'repair':bool,'notes':[..]} oder {'ok':False,'error':..}"""
    try:
        d = fetch_version()
        latest = int(d.get("version", 0))
    except Exception:
        return {"ok": False, "error": "KEINE VERBINDUNG ZUM UPDATE-SERVER"}
    notes = []
    if latest > VERSION:
        notes = [str(e.get("notes", "")) for e in sorted(fetch_changelog(), key=lambda e: int(e.get("version", 0) or 0))
                 if VERSION < int(e.get("version", 0) or 0) <= latest and e.get("notes")]
    repair = latest == VERSION and needs_repair()
    return {"ok": True, "current": VERSION, "name": VERSION_NAME, "latest": latest, "latest_name": str(d.get("name", latest)),
            "available": latest > VERSION or repair, "repair": repair, "notes": notes}


def _already_applied(d):
    try:
        with open(APPLIED, encoding="utf-8") as f:
            a = json.load(f)
        return int(a.get("version", 0)) == int(d.get("version", 0)) and str(a.get("sha256", "")).lower() == str(d.get("sha256", "")).lower()
    except Exception:
        return False


def apply(force=False):
    """Laedt und installiert das Update (force=True: gleiche Version erneut, fuer die Reparatur).
    -> {'ok':True,'files':n,'name':..} oder {'ok':False,'error':..}. Neustart macht der Host."""
    if not _lock.acquire(blocking=False):
        return {"ok": False, "error": "UPDATE LAEUFT BEREITS"}
    tmp = tempfile.mkdtemp(prefix="rsi_update_")
    done = []                                   # (Ziel, Sicherung|None) fuer das Zurueckrollen
    try:
        _progress("pruefen", 5)
        try:
            d = fetch_version()
        except Exception:
            return {"ok": False, "error": "KEINE VERBINDUNG ZUM UPDATE-SERVER"}
        if int(d.get("version", 0)) < VERSION or (int(d.get("version", 0)) == VERSION and not force):
            return {"ok": False, "error": "SCHON AUF DEM NEUESTEN STAND"}
        zip_name, want = str(d.get("zip", "")), str(d.get("sha256", "")).lower()
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", zip_name) or not re.fullmatch(r"[0-9a-f]{64}", want):
            return {"ok": False, "error": "UPDATE-BESCHREIBUNG UNGUELTIG"}
        if not force and _already_applied(d):
            return {"ok": False, "error": "UPDATE BEREITS INSTALLIERT (WIEDERHOLUNG VERHINDERT)"}
        zpath = os.path.join(tmp, "update.zip")
        _progress("laden", 10)
        with _get(UPDATE_BASE + zip_name, timeout=120) as r, open(zpath, "wb") as f:
            total, got = int(r.headers.get("Content-Length") or 0), 0
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    _progress("laden", 10 + 45 * got / total)
        _progress("pruefen", 60)
        h = hashlib.sha256()
        with open(zpath, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != want:
            return {"ok": False, "error": "PRUEFSUMME FALSCH - NICHTS GEAENDERT"}
        _progress("entpacken", 65)
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
            except py_compile.PyCompileError:
                return {"ok": False, "error": "FEHLERHAFTE DATEI IM UPDATE: " + py}
        _progress("installieren", 70)
        backup = os.path.join(BASE, "backups", "update-" + time.strftime("%Y%m%d_%H%M%S"))
        order = [n for n in files if n != "updater.py"] + [n for n in files if n == "updater.py"]   # Versionsdatei ZULETZT
        for i, name in enumerate(order):
            dst, bk = os.path.join(BASE, *name.split("/")), None
            if os.path.isfile(dst):
                bk = os.path.join(backup, *name.split("/"))
                os.makedirs(os.path.dirname(bk), exist_ok=True)
                shutil.copy2(dst, bk)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            done.append((dst, bk))
            shutil.copy2(os.path.join(stage, *name.split("/")), dst)
            _progress("installieren", 70 + 25 * (i + 1) / len(order))
        with open(APPLIED, "w", encoding="utf-8") as f:                  # Stempel ganz am Ende = "Update ist vollstaendig"
            json.dump({"version": int(d["version"]), "sha256": want}, f)
        _progress("fertig", 100)
        return {"ok": True, "files": len(files), "name": str(d.get("name", d["version"]))}
    except Exception as e:
        for dst, bk in reversed(done):                                   # nie einen halben Stand zuruecklassen
            try:
                if bk and os.path.isfile(bk):
                    shutil.copy2(bk, dst)
                elif not bk and os.path.isfile(dst):
                    os.remove(dst)
            except OSError:
                pass
        _progress("", 0)
        return {"ok": False, "error": "UPDATE FEHLGESCHLAGEN: " + type(e).__name__}
    finally:
        _lock.release()
        shutil.rmtree(tmp, ignore_errors=True)
