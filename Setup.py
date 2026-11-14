"""RSI Overhead – Installer (nur Python-Standardbibliothek, Windows, ohne Administratorrechte).

Was er macht:
  * kopiert das Programm nach %LOCALAPPDATA%\\Programs\\RSI Overhead (oder einen Ordner deiner Wahl)
  * legt Verknuepfungen an (Desktop, Startmenue) mit dem Logo
  * optional: Autostart mit Windows (startet minimiert)
  * traegt das Programm unter "Apps & Features" ein (Deinstallation) – Einstellungen bleiben bei Updates erhalten
Aufruf ohne Fenster:  Setup.py --silent [--target ORDNER] [--no-desktop] [--no-startmenu] [--autostart] [--no-launch]
"""
import ctypes
import os
import shutil
import subprocess
import sys
import traceback
import winreg

APP = "RSI Overhead"
VERSION = "1.0"
SRC = os.path.dirname(os.path.abspath(__file__))
FILES = ["rsi_overhead.py", "updater.py", "uninstall.py", "RSI Overhead.ico", "README.md"]
DIRS = ["ui"]
DEFAULT_TARGET = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + APP


def pythonw():
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return pw if os.path.isfile(pw) else exe


def special_folder(name):
    """Desktop / Startmenue-Programme auch bei umgeleiteten Ordnern (OneDrive) richtig finden."""
    ps = {"desktop": "[Environment]::GetFolderPath('Desktop')", "programs": "[Environment]::GetFolderPath('Programs')"}[name]
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=0x08000000).stdout.strip()
    return out or os.path.join(os.path.expanduser("~"), "Desktop")


def make_shortcut(lnk, target, args, workdir, icon, desc):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    env = dict(os.environ, L_LNK=lnk, L_T=target, L_A=args, L_W=workdir, L_I=icon, L_D=desc)
    script = ("$s=New-Object -ComObject WScript.Shell;$l=$s.CreateShortcut($env:L_LNK);$l.TargetPath=$env:L_T;"
              "$l.Arguments=$env:L_A;$l.WorkingDirectory=$env:L_W;$l.IconLocation=$env:L_I+',0';$l.Description=$env:L_D;$l.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, check=True, creationflags=0x08000000)


def install(target, desktop=True, startmenu=True, autostart=False, log=print):
    target = os.path.normpath(target)
    if os.path.normcase(target) == os.path.normcase(SRC):
        raise RuntimeError("Zielordner darf nicht der Quellordner sein.")
    log("Kopiere Dateien ...")
    os.makedirs(target, exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(SRC, f), os.path.join(target, f))
    for d in DIRS:
        dst = os.path.join(target, d)
        if os.path.isdir(dst):
            shutil.rmtree(dst)                       # alte UI ersetzen; Einstellungen liegen ausserhalb von ui/
        shutil.copytree(os.path.join(SRC, d), dst, ignore=shutil.ignore_patterns("__pycache__"))
    host = os.path.join(target, "rsi_overhead.py")
    icon = os.path.join(target, "RSI Overhead.ico")
    pw = pythonw()
    args = '"%s"' % host
    if desktop:
        log("Desktop-Verknuepfung ...")
        make_shortcut(os.path.join(special_folder("desktop"), APP + ".lnk"), pw, args, target, icon, "RSI Overhead")
    if startmenu:
        log("Startmenue-Eintrag ...")
        make_shortcut(os.path.join(special_folder("programs"), APP + ".lnk"), pw, args, target, icon, "RSI Overhead")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if autostart:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, '"%s" "%s" --minimized' % (pw, host))
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass
    log("Registriere Deinstallation ...")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", APP), ("DisplayVersion", VERSION), ("Publisher", "Eigenes Projekt"),
                          ("InstallLocation", target), ("DisplayIcon", icon),
                          ("UninstallString", '"%s" "%s"' % (pw, os.path.join(target, "uninstall.py")))):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
    return host


def launch(host):
    subprocess.Popen([pythonw(), host], cwd=os.path.dirname(host), creationflags=0x08000000)


def msg(text, title=APP, flags=0x40):
    ctypes.windll.user32.MessageBoxW(0, text, title, flags)


# --------------------------------------------------------------- Fenster
def gui():
    import tkinter as tk
    from tkinter import filedialog
    C = dict(bg="#0A0907", panel="#141210", line="#3B352B", acc="#F58A1F", acc2="#9A5410", text="#EFE9DD", muted="#A39A88", onacc="#140A02")
    r = tk.Tk()
    r.title(APP + " – Setup")
    r.configure(bg=C["bg"])
    r.resizable(False, False)
    try:
        r.iconbitmap(os.path.join(SRC, "RSI Overhead.ico"))
    except tk.TclError:
        pass
    fb = ("Bahnschrift", 10)
    tk.Label(r, text="RSI OVERHEAD", bg=C["bg"], fg=C["acc"], font=("Bahnschrift SemiBold", 20)).pack(anchor="w", padx=26, pady=(22, 0))
    tk.Label(r, text="Installation – ohne Administratorrechte", bg=C["bg"], fg=C["muted"], font=fb).pack(anchor="w", padx=26)
    box = tk.Frame(r, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
    box.pack(fill="x", padx=26, pady=16)
    tk.Label(box, text="INSTALLATIONSORDNER", bg=C["panel"], fg=C["acc"], font=("Bahnschrift SemiBold", 9)).pack(anchor="w", padx=16, pady=(14, 4))
    row = tk.Frame(box, bg=C["panel"])
    row.pack(fill="x", padx=16)
    path = tk.StringVar(value=DEFAULT_TARGET)
    tk.Entry(row, textvariable=path, width=46, bg="#1D1A15", fg=C["text"], insertbackground=C["text"], relief="flat",
             highlightthickness=1, highlightbackground=C["line"], font=fb).pack(side="left", fill="x", expand=True, ipady=4)

    def browse():
        d = filedialog.askdirectory(initialdir=os.path.dirname(path.get()) or "C:\\")
        if d:
            path.set(os.path.join(os.path.normpath(d), APP) if os.path.basename(d).lower() != APP.lower() else os.path.normpath(d))

    tk.Button(row, text="ÄNDERN", command=browse, bg=C["bg"], fg=C["acc"], activebackground=C["acc"], relief="flat",
              highlightthickness=1, highlightbackground=C["acc2"], font=fb, padx=10).pack(side="left", padx=(8, 0))
    opts = {}
    for key, text, on in (("desktop", "Verknüpfung auf dem Desktop", True), ("startmenu", "Eintrag im Startmenü", True),
                          ("autostart", "Mit Windows starten (minimiert)", False), ("launch", "Nach der Installation starten", True)):
        v = tk.BooleanVar(value=on)
        opts[key] = v
        tk.Checkbutton(box, text=text, variable=v, bg=C["panel"], fg=C["text"], selectcolor="#1D1A15", activebackground=C["panel"],
                       activeforeground=C["acc"], font=fb, anchor="w").pack(fill="x", padx=16, pady=2)
    tk.Frame(box, height=10, bg=C["panel"]).pack()
    status = tk.Label(r, text="", bg=C["bg"], fg=C["muted"], font=fb)
    status.pack(anchor="w", padx=26)
    btns = tk.Frame(r, bg=C["bg"])
    btns.pack(fill="x", padx=26, pady=(8, 22))

    def go():
        try:
            host = install(path.get(), opts["desktop"].get(), opts["startmenu"].get(), opts["autostart"].get(),
                           log=lambda t: (status.config(text=t), r.update()))
        except Exception:
            msg("Installation fehlgeschlagen:\n\n" + traceback.format_exc()[-900:], flags=0x10)
            return
        if opts["launch"].get():
            launch(host)
        msg("Installiert in:\n%s\n\nStarten: Desktop-Verknüpfung \"%s\"." % (os.path.dirname(host), APP))
        r.destroy()

    for text, cmd, primary in (("INSTALLIEREN", go, True), ("ABBRECHEN", r.destroy, False)):
        tk.Button(btns, text=text, command=cmd, bg=C["acc"] if primary else C["bg"], fg=C["onacc"] if primary else C["muted"],
                  activebackground=C["text"], relief="flat", font=("Bahnschrift SemiBold", 10), padx=20, pady=8,
                  highlightthickness=0 if primary else 1, highlightbackground=C["line"]).pack(side="left", padx=(0, 10))
    r.mainloop()


def main():
    a = sys.argv[1:]
    if "--silent" in a:
        t = a[a.index("--target") + 1] if "--target" in a else DEFAULT_TARGET
        host = install(t, "--no-desktop" not in a, "--no-startmenu" not in a, "--autostart" in a)
        if "--no-launch" not in a:
            launch(host)
        return
    try:
        gui()
    except ImportError:
        msg("tkinter fehlt in dieser Python-Installation. Starte Setup.py mit  --silent  in einer Konsole.", flags=0x10)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        msg("Fehler:\n\n" + traceback.format_exc()[-900:], flags=0x10)
