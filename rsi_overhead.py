"""RSI Overhead: Host-Programm (nur Python-Standardbibliothek, Windows).

Aufgaben:
  * stellt ui/ lokal bereit (127.0.0.1) und liefert Daten (CPU/RAM/Ping, Spielordner, Tasten)
  * oeffnet die Oberflaeche als eigenes Edge-App-Fenster
  * setzt das Fenster auf 'immer oben' + 'nicht aktivieren': ein Klick auf das Overhead holt
    das Spiel NICHT aus dem Vordergrund (Fokus bleibt im Spiel)
  * globaler Hotkey zum Ein-/Ausblenden (settings.json -> "hotkey")
  * liest Star-Citizen-Tasten aus der actionmaps.xml; Tasten per Klick neu aufnehmen (ohne Fokus)
Beendet sich selbst, sobald das Fenster geschlossen wird.
"""
import ctypes
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import winreg
import xml.etree.ElementTree as ET
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)                      # noetig, wenn mit python -I gestartet
import updater  # noqa: E402  (Programm-Update ueber GitHub Pages)

UI = os.path.join(BASE, "ui")
SETTINGS = os.path.join(BASE, "settings.json")
KEYS_USER = os.path.join(BASE, "keybinds_user.json")
WINDOW_TITLE = "RSI Overhead"          # Teilstring des Fenstertitels (siehe ui/config/app.json)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

DEFAULTS = {"ui": {}, "game_dir": "", "hotkey": "ctrl+shift+f9", "no_focus": True, "always_on_top": True,
            "window": [1000, 1030], "auto_update": False, "start_minimized": True}
WIN_SIZES = [[820, 840], [1000, 1030], [1300, 1330]]          # klein / mittel / gross
UPDATE_STATE = {"available": False, "latest_name": "", "checked": 0}


def auto_update_on():
    """Auto-Update ist standardmaessig AN; erst wenn der Nutzer den Schalter bedient hat, zaehlt dessen Wert."""
    return bool(CFG.get("auto_update")) if CFG.get("auto_update_set") else True
lock = threading.Lock()
STATUS_URL = "https://status.robertsspaceindustries.com"


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


CFG = {**DEFAULTS, **load_json(SETTINGS, {})}
NOTICE = {"name": CFG.pop("just_updated", None)}       # einmalige Meldung "aktualisiert auf ..." nach einem Auto-Update
if NOTICE["name"] is not None:
    save_json(SETTINGS, CFG)

# ------------------------------------------------------------ Autostart (Registry, pro Benutzer)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "RSI Overhead"


def launch_command(minimized=False):
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.isfile(pw):
        exe = pw
    return '"%s" "%s"%s' % (exe, os.path.join(BASE, "rsi_overhead.py"), " --minimized" if minimized else "")


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, launch_command(bool(CFG.get("start_minimized", True))))
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except OSError:
                pass


# ------------------------------------------------------------ Spielordner
def find_game_dir():
    if CFG.get("game_dir") and os.path.isdir(CFG["game_dir"]):
        return CFG["game_dir"]
    rel = [r"Program Files\Roberts Space Industries\StarCitizen\LIVE", r"Roberts Space Industries\StarCitizen\LIVE",
           r"StarCitizen\StarCitizen\LIVE", r"StarCitizen\LIVE", r"Games\StarCitizen\LIVE", r"Games\Roberts Space Industries\StarCitizen\LIVE"]
    for d in "CDEFGHIJ":
        for r in rel:
            p = f"{d}:\\{r}"
            if os.path.isdir(p):
                return p
    return ""


GAME = find_game_dir()


def game_paths():
    if not GAME:
        return {}
    user = os.path.join(GAME, "user", "client", "0")
    return {"game": GAME, "logs": os.path.join(GAME, "logs"), "screens": os.path.join(GAME, "screenshots"),
            "config": os.path.join(user, "Profiles", "default"),
            "cache": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Star Citizen")}


def win_size_index():
    w = (CFG.get("window") or WIN_SIZES[1])[0]
    return min(range(len(WIN_SIZES)), key=lambda i: abs(WIN_SIZES[i][0] - w))


def game_info():
    info = {"version": "—", "build": "—", "channel": os.path.basename(GAME) if GAME else "—", "device": "—",
            "paths": game_paths(), "game_running": game_running(),
            "app_version": updater.VERSION_NAME, "update": dict(UPDATE_STATE),
            "settings": {"autostart": autostart_enabled(), "autoupdate": auto_update_on(),
                         "overlay": bool(CFG.get("no_focus", True) and CFG.get("always_on_top", True)),
                         "ontop": bool(CFG.get("always_on_top", True)), "nofocus": bool(CFG.get("no_focus", True)),
                         "startmin": bool(CFG.get("start_minimized", True)), "winsize": win_size_index()}}
    m = load_json(os.path.join(GAME, "build_manifest.id"), None) if GAME else None
    if isinstance(m, dict):
        d = m.get("Data", m)
        info["version"] = str(d.get("Version") or d.get("Branch") or "—")
        info["build"] = str(d.get("RequestedP4ChangeNum") or d.get("BuildId") or d.get("BuildTimeStamp") or "—")
    am = os.path.join(game_paths().get("config", ""), "actionmaps.xml")
    try:
        prods = [o.get("Product") for o in ET.parse(am).getroot().iter("options") if o.get("Product")]
        if prods:
            info["device"] = re.sub(r"\s*\{[0-9A-Fa-f-]+\}", "", prods[-1]).strip() or "—"
    except (OSError, ET.ParseError):
        pass
    return info


_running = {"t": 0, "v": False}


def game_running():
    if time.time() - _running["t"] > 5:
        _running["t"] = time.time()
        try:
            raw = subprocess.run(["tasklist", "/FI", "IMAGENAME eq StarCitizen.exe", "/NH"], capture_output=True,
                                 timeout=4, creationflags=0x08000000).stdout or b""
            _running["v"] = b"StarCitizen.exe" in raw          # Bytes: Ausgabe liegt je nach Sprache in OEM-Codepage vor
        except (OSError, subprocess.SubprocessError):
            pass
    return _running["v"]


# ------------------------------------------------------------ Tasten
MODS = {"lalt": "Left Alt", "ralt": "Right Alt", "lctrl": "Left Ctrl", "rctrl": "Right Ctrl", "lshift": "Left Shift",
        "rshift": "Right Shift", "space": "Space", "tab": "Tab", "enter": "Enter", "escape": "Esc", "backspace": "Backspace",
        "capslock": "Caps Lock", "insert": "Insert", "delete": "Delete", "home": "Home", "end": "End", "pgup": "Page Up",
        "pgdn": "Page Down", "up": "Up", "down": "Down", "left": "Left", "right": "Right"}


def pretty_input(i):
    m = re.match(r"^(kb|mo|js|gp)(\d+)_(.*)$", i or "")
    if not m:
        return i
    dev, n, rest = m.groups()
    if dev == "mo":
        b = {"button1": "Left Mouse Button", "button2": "Right Mouse Button", "button3": "Middle Mouse Button"}
        return b.get(rest, "Mouse " + rest.replace("button", ""))
    if dev in ("js", "gp"):
        return f"{'Joystick' if dev == 'js' else 'Gamepad'} {n} {rest.replace('_', ' ')}".strip()
    out = []
    for p in rest.split("+"):
        if p in MODS:
            out.append(MODS[p])
        elif p.startswith("np_"):
            out.append("Num " + p[3:])
        else:
            out.append(p.replace("_", " ").upper() if len(p) > 1 else p.upper())
    return " + ".join(out)


def read_rebinds():
    """Vom Spieler geaenderte Tasten aus der actionmaps.xml: {aktionsname: [taste, ...]}."""
    res = {}
    am = os.path.join(game_paths().get("config", ""), "actionmaps.xml")
    try:
        for a in ET.parse(am).getroot().iter("action"):
            ins = [pretty_input(r.get("input")) for r in a.iter("rebind") if r.get("input") and r.get("input").split("_", 1)[-1]]
            if ins:
                res[a.get("name")] = ins
    except (OSError, ET.ParseError):
        pass
    return res


VK = {0x01: "Left Mouse Button", 0x02: "Right Mouse Button", 0x04: "Middle Mouse Button", 0x05: "Mouse 4", 0x06: "Mouse 5",
      0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x14: "Caps Lock", 0x1B: "Esc", 0x20: "Space", 0x21: "Page Up",
      0x22: "Page Down", 0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
      0x2D: "Insert", 0x2E: "Delete", 0xA0: "Left Shift", 0xA1: "Right Shift", 0xA2: "Left Ctrl", 0xA3: "Right Ctrl",
      0xA4: "Left Alt", 0xA5: "Right Alt", 0x6A: "Num *", 0x6B: "Num +", 0x6D: "Num -", 0x6E: "Num .", 0x6F: "Num /",
      0xBA: "Ü", 0xBB: "+", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "#", 0xC0: "Ö", 0xDB: "ß", 0xDC: "^", 0xDD: "´", 0xDE: "Ä",
      0xE2: "<"}
VK.update({c: chr(c) for c in range(0x30, 0x3A)})
VK.update({c: chr(c) for c in range(0x41, 0x5B)})
VK.update({0x60 + i: f"Num {i}" for i in range(10)})
VK.update({0x70 + i: f"F{i + 1}" for i in range(12)})
MOD_ORDER = [0xA2, 0xA3, 0xA4, 0xA5, 0xA0, 0xA1]
NAME_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, **{f"f{i + 1}": 0x70 + i for i in range(24)},
           **{chr(c).lower(): c for c in range(0x41, 0x5B)}, **{chr(c): c for c in range(0x30, 0x3A)}}


def is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def capture_key(timeout=12):
    """Wartet auf die naechste Taste/Kombination (ohne Fenster-Fokus, per Abfrage). Esc = abbrechen."""
    scan = list(VK)
    t0 = time.time()
    while any(is_down(v) for v in scan) and time.time() - t0 < 3:
        time.sleep(0.01)
    seen = []
    while time.time() - t0 < timeout:
        cur = [v for v in scan if is_down(v)]
        for v in cur:
            if v not in seen:
                seen.append(v)
        if seen and not cur:
            break
        time.sleep(0.01)
    if not seen or seen == [0x1B]:
        return None
    mods = [v for v in MOD_ORDER if v in seen]
    rest = [v for v in seen if v not in MOD_ORDER]
    return " + ".join(VK[v] for v in mods + rest)


# ------------------------------------------------------------ Systemwerte
class _MEM(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + \
               [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "ave")]


def _cpu_times():
    idle, kern, usr = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(usr))
    f = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime
    return f(idle), f(kern) + f(usr)


class Stats:
    def __init__(self):
        self.cpu, self.ram, self.ping, self._last = 0, 0, None, _cpu_times()
        threading.Thread(target=self._ping, daemon=True).start()

    def _ping(self):
        while True:
            try:
                t = time.perf_counter()
                socket.create_connection(("1.1.1.1", 443), timeout=2).close()
                self.ping = int((time.perf_counter() - t) * 1000)
            except OSError:
                self.ping = None
            time.sleep(3)

    def snapshot(self):
        idle, tot = _cpu_times()
        di, dt = idle - self._last[0], tot - self._last[1]
        self._last = (idle, tot)
        if dt:
            self.cpu = int(100 * (1 - di / dt))
        m = _MEM()
        m.dwLength = ctypes.sizeof(_MEM)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        self.ram = int(m.dwMemoryLoad)
        return {"cpu": self.cpu, "ram": self.ram, "ping": self.ping}


STATS = Stats()


# ------------------------------------------------------------ Fenster (Fokus-Schutz, Hotkey)
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x08000000, 0x8
HWND_TOPMOST = -1
SWP = 0x0001 | 0x0002 | 0x0010 | 0x0020          # NOMOVE | NOSIZE | NOACTIVATE | FRAMECHANGED
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window():
    found = []

    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if WINDOW_TITLE in buf.value and cls.value.startswith("Chrome_WidgetWin"):
                found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def window_guard():
    """Haelt das Fenster 'immer oben' und nicht-aktivierend (Chromium setzt Stile gern zurueck)."""
    while True:
        hwnd = find_window()
        if hwnd:
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            want = ex
            for flag, on in ((WS_EX_NOACTIVATE, CFG.get("no_focus", True)), (WS_EX_TOPMOST, CFG.get("always_on_top", True))):
                want = (want | flag) if on else (want & ~flag)
            if want != ex:
                user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, want)
                user32.SetWindowPos(hwnd, HWND_TOPMOST if CFG.get("always_on_top", True) else -2, 0, 0, 0, 0, SWP)
        time.sleep(1.5)


def resize_window(w, h):
    """Fenstergroesse sofort aendern (ohne Fokus, ohne Position/Reihenfolge anzufassen)."""
    hwnd = find_window()
    if hwnd:
        user32.SetWindowPos(hwnd, 0, 0, 0, int(w), int(h), 0x0002 | 0x0004 | 0x0010)   # NOMOVE | NOZORDER | NOACTIVATE


def combo_to_hotkey(combo):
    """'Left Ctrl + Left Shift + F9' -> 'ctrl+shift+f9'. None, wenn nicht als Hotkey nutzbar."""
    toks = []
    for part in combo.split(" + "):
        pl = part.lower()
        t = {"left ctrl": "ctrl", "right ctrl": "ctrl", "left shift": "shift", "right shift": "shift",
             "left alt": "alt", "right alt": "alt"}.get(pl, pl)
        if t not in NAME_VK or t in toks:
            return None
        toks.append(t)
    mods = [t for t in toks if t in ("ctrl", "shift", "alt")]
    keys = [t for t in toks if t not in ("ctrl", "shift", "alt")]
    if len(keys) != 1 or (not mods and not keys[0].startswith("f")):
        return None                                        # eine Taste + mind. ein Modifikator (F-Tasten auch allein)
    return "+".join(mods + keys)


def hotkey_loop():
    was, hidden, last, vks = False, False, None, []
    while True:
        hk = CFG.get("hotkey", "")
        if hk != last:                                     # Hotkey kann im Programm geaendert werden
            last = hk
            vks = [NAME_VK[t] for t in hk.lower().replace(" ", "").split("+") if t in NAME_VK]
            was = False
        now = bool(vks) and all(is_down(v) for v in vks)
        if now and not was:
            hwnd = find_window() if not hidden else HIDDEN.get("h")
            if hwnd:
                if not hidden:
                    HIDDEN["h"] = hwnd
                    user32.ShowWindow(hwnd, 0)          # SW_HIDE
                else:
                    user32.ShowWindow(hwnd, 4)          # SW_SHOWNOACTIVATE
                hidden = not hidden
                HIDDEN["on"] = hidden
        was = now
        time.sleep(0.04)


HIDDEN = {}


# ------------------------------------------------------------ Server
state = {"last_seen": 0.0, "seen": False, "port": 0}


def keys_user():
    return load_json(KEYS_USER, {"profiles": {}})


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _ok_origin(self):
        ok = self.headers.get("Host", "") == f"127.0.0.1:{state['port']}"
        if ok and self.command == "POST":
            ok = self.headers.get("Origin") in (None, f"http://127.0.0.1:{state['port']}")
        if not ok:
            self.close_connection = True        # Body nicht lesen: Verbindung sauber beenden
        return ok

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._ok_origin():
            return self._send(403, {"ok": False})
        path = self.path.split("?")[0]
        if path == "/api/state":
            state["last_seen"], state["seen"] = time.time(), True
            return self._send(200, {"ok": True, "ui": CFG["ui"], "stats": STATS.snapshot(), "info": game_info(),
                                    "keys": keys_user(), "rebinds": read_rebinds(), "hotkey": CFG.get("hotkey"),
                                    "notice": NOTICE.pop("name", None)})
        rel = "index.html" if path == "/" else path.lstrip("/")
        full = os.path.normpath(os.path.join(UI, rel))
        if not full.startswith(UI + os.sep) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain")
        with open(full, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".json"):
            ctype = "application/json"
        self._send(200, data, ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("json") or ctype.endswith("javascript") else ""))

    def do_POST(self):
        global GAME
        if not self._ok_origin():
            return self._send(403, {"ok": False})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            body = {}
        p = self.path
        if p == "/api/bye":
            state["last_seen"] = time.time() - 7        # kurze Gnadenfrist (Seite neu laden)
            return self._send(200, {"ok": True})
        if p == "/api/set":
            with lock:
                CFG["ui"].update(body.get("ui", {}))
                save_json(SETTINGS, CFG)
            return self._send(200, {"ok": True})
        if p == "/api/reset":
            with lock:
                CFG["ui"] = {}
                save_json(SETTINGS, CFG)
            return self._send(200, {"ok": True})
        if p == "/api/open":
            what = body.get("what")
            if what == "status":                                   # feste Adresse, nichts vom Client
                import webbrowser
                webbrowser.open(STATUS_URL)
                return self._send(200, {"ok": True})
            d = os.path.join(GAME, "Game.log") if (what == "gamelog" and GAME) else game_paths().get(what)
            if d and os.path.exists(d):
                os.startfile(d)
                return self._send(200, {"ok": True})
            return self._send(200, {"ok": False, "error": "NICHT GEFUNDEN"})
        if p == "/api/hotkey":
            combo = capture_key()
            if not combo:
                return self._send(200, {"ok": False, "error": "ABGEBROCHEN"})
            hk = combo_to_hotkey(combo)
            if not hk:
                return self._send(200, {"ok": False, "error": "UNGUELTIG: " + combo[:30]})
            with lock:
                CFG["hotkey"] = hk
                save_json(SETTINGS, CFG)
            return self._send(200, {"ok": True, "hotkey": hk})
        if p == "/api/setting":
            key, raw = body.get("key"), body.get("value")
            val = bool(raw)
            if key == "autostart":
                try:
                    set_autostart(val)
                except OSError:
                    return self._send(200, {"ok": False, "error": "AUTOSTART FEHLGESCHLAGEN"})
            elif key in ("overlay", "ontop", "nofocus", "autoupdate", "startmin"):
                names = {"overlay": ("no_focus", "always_on_top"), "ontop": ("always_on_top",), "nofocus": ("no_focus",),
                         "autoupdate": ("auto_update",), "startmin": ("start_minimized",)}[key]
                with lock:
                    for n in names:
                        CFG[n] = val
                    if key == "autoupdate":
                        CFG["auto_update_set"] = True          # ab jetzt zaehlt die Wahl des Nutzers (Standard ist AN)
                    save_json(SETTINGS, CFG)
                if key == "startmin" and autostart_enabled():
                    try:
                        set_autostart(True)                # Eintrag mit/ohne --minimized neu schreiben
                    except OSError:
                        pass
            elif key == "winsize":
                try:
                    i = max(0, min(len(WIN_SIZES) - 1, int(raw)))
                except (TypeError, ValueError):
                    return self._send(200, {"ok": False})
                with lock:
                    CFG["window"] = WIN_SIZES[i]
                    save_json(SETTINGS, CFG)
                resize_window(*WIN_SIZES[i])
            else:
                return self._send(200, {"ok": False})
            return self._send(200, {"ok": True})
        if p == "/api/update/check":
            r = updater.check()
            if r.get("ok"):
                UPDATE_STATE.update(available=r["available"], latest_name=r["latest_name"], checked=time.time())
            return self._send(200, r)
        if p == "/api/update/apply":
            r = updater.apply()
            self._send(200, r)
            if r.get("ok"):
                threading.Timer(1.0, restart_app).start()
            return
        if p == "/api/quit":
            self._send(200, {"ok": True})
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return
        if p == "/api/pickdir":
            exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
            exe = exe if os.path.isfile(exe) else sys.executable
            code = ("import tkinter as t;from tkinter import filedialog as f;r=t.Tk();r.withdraw();r.attributes('-topmost',True);"
                    "print(f.askdirectory(title='Star-Citizen-Ordner (LIVE) waehlen'))")
            try:
                out = subprocess.run([exe, "-c", code], capture_output=True, text=True, timeout=300, creationflags=0x08000000).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return self._send(200, {"ok": False, "error": "DIALOG NICHT VERFUEGBAR"})
            if not out:
                return self._send(200, {"ok": False, "error": "ABGEBROCHEN"})
            out = os.path.normpath(out)
            if not (os.path.isdir(os.path.join(out, "Bin64")) or os.path.isfile(os.path.join(out, "Data.p4k"))):
                return self._send(200, {"ok": False, "error": "KEIN STAR-CITIZEN-ORDNER"})
            with lock:
                CFG["game_dir"] = out
                save_json(SETTINGS, CFG)
            GAME = out
            return self._send(200, {"ok": True})
        if p == "/api/backup":
            src = os.path.join(game_paths().get("config", ""), "actionmaps.xml")
            if not os.path.isfile(src):
                return self._send(200, {"ok": False, "error": "ACTIONMAPS NICHT GEFUNDEN"})
            dst_dir = os.path.join(BASE, "backups")
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, "actionmaps_%s.xml" % time.strftime("%Y%m%d_%H%M%S")))
            return self._send(200, {"ok": True})
        if p == "/api/launch":
            exe = os.path.join(GAME, "StarCitizen_Launcher.exe") if GAME else ""
            if not os.path.isfile(exe):
                return self._send(200, {"ok": False, "error": "SPIEL NICHT GEFUNDEN"})
            subprocess.Popen([exe], cwd=GAME)
            return self._send(200, {"ok": True})
        if p == "/api/capture":
            return self._send(200, {"ok": True, "key": capture_key()})
        if p == "/api/keys/save":
            prof, m = str(body.get("profile", "")), body.get("map", {})
            if not prof or not isinstance(m, dict):
                return self._send(200, {"ok": False, "error": "UNGUELTIG"})
            with lock:
                k = keys_user()
                k.setdefault("profiles", {})[prof] = {str(a): str(b) for a, b in m.items()}
                save_json(KEYS_USER, k)
            return self._send(200, {"ok": True})
        self._send(404, {"ok": False})


def restart_app():
    """Nach einem Update: neue Instanz auf DEMSELBEN Port starten und diese beenden. Das offene Fenster bleibt bestehen
    (kein neuer Edge-Start, kein Wettlauf um das Profil); die Seite merkt den Ausfall und laedt sich selbst neu."""
    if HIDDEN.get("on") and HIDDEN.get("h"):
        user32.ShowWindow(HIDDEN["h"], 4)                # per Hotkey versteckt? Dann wieder einblenden
    keep, skip = [], False
    for a in sys.argv[1:]:
        if skip:
            skip = False
        elif a == "--port":
            skip = True
        elif a not in ("--minimized", "--reuse-window"):
            keep.append(a)
    subprocess.Popen([sys.executable, os.path.join(BASE, "rsi_overhead.py"), "--port", str(state["port"]), "--reuse-window"] + keep,
                     cwd=BASE, creationflags=0x08000000)
    time.sleep(0.6)
    os._exit(0)


def make_server():
    """HTTP-Server; mit --port (Neustart nach Update) wird derselbe Port wieder belegt (wartet, bis er frei ist)."""
    want = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 0
    for _ in range(60):
        try:
            return ThreadingHTTPServer(("127.0.0.1", want), H)
        except OSError:
            if not want:
                raise
            time.sleep(0.25)
    return ThreadingHTTPServer(("127.0.0.1", 0), H)


def update_loop():
    """Auto-Update: prueft beim Start (nach 8 s) und danach alle 30 Minuten. Installiert wird nur, wenn Auto-Update an ist
    UND Star Citizen nicht laeuft (der Neustart schliesst das Fenster) - sonst wird spaeter erneut versucht."""
    time.sleep(8)
    while True:
        if UPDATE_STATE["available"] or time.time() - UPDATE_STATE["checked"] > 30 * 60:
            r = updater.check()
            if r.get("ok"):
                UPDATE_STATE.update(available=r["available"], latest_name=r["latest_name"], checked=time.time())
            else:
                UPDATE_STATE["checked"] = time.time()
        if UPDATE_STATE["available"] and auto_update_on() and not game_running():
            res = updater.apply()
            if res.get("ok"):
                with lock:
                    CFG["just_updated"] = res.get("name", "")
                    save_json(SETTINGS, CFG)
                restart_app()
            UPDATE_STATE.update(available=False, checked=time.time())      # Fehlschlag: erst in 30 Min. erneut versuchen
        time.sleep(300)


def find_edge():
    for p in (shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if p and os.path.isfile(p):
            return p
    return None


def main():
    srv = make_server()
    srv.daemon_threads = True
    state["port"] = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{state['port']}/"
    use_window = False
    if "--no-window" in sys.argv:
        print(url, flush=True)
    elif "--reuse-window" in sys.argv:
        use_window = True                              # das bestehende Fenster weiterverwenden (Neustart nach Update)
    else:
        edge, w = find_edge(), CFG.get("window", [1000, 1030])
        profile_dir = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "RSIOverhead")
        if edge:
            args = [edge, f"--app={url}", f"--user-data-dir={profile_dir}", f"--window-size={w[0]},{w[1]}",
                    "--no-first-run", "--disable-extensions", "--disable-features=Translate"]
            if "--minimized" in sys.argv:
                args.append("--start-minimized")
            subprocess.Popen(args)
            use_window = True
        else:
            import webbrowser
            webbrowser.open(url)
    threading.Thread(target=window_guard, daemon=True).start()
    threading.Thread(target=hotkey_loop, daemon=True).start()
    if "--no-update-check" not in sys.argv:
        threading.Thread(target=update_loop, daemon=True).start()
    t0 = time.time()
    seen_win, missing = False, 0
    while True:
        time.sleep(1)
        if use_window:
            # Beenden, wenn das FENSTER weg ist - nicht am Heartbeat der Seite: minimiert oder hinter dem Spiel verdeckt
            # drosselt der Browser die Seite stark, das Programm wuerde sich sonst selbst beenden.
            if HIDDEN.get("on") or find_window():
                seen_win, missing = seen_win or not HIDDEN.get("on"), 0
            else:
                missing += 1
            if seen_win and missing > 10:
                break
            if not seen_win and time.time() - t0 > 60:
                break
            continue
        if HIDDEN.get("on"):                      # (nur ohne eigenes Fenster) versteckt: kein Heartbeat erwartet
            state["last_seen"] = time.time()
        if state["seen"] and time.time() - state["last_seen"] > 10:
            break
        if not state["seen"] and time.time() - t0 > 40:
            break
    # Fenster bei Beenden wieder sichtbar machen, falls per Hotkey versteckt
    if HIDDEN.get("h"):
        user32.ShowWindow(HIDDEN["h"], 4)


if __name__ == "__main__":
    main()
