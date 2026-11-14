"""RSI Overhead – Deinstallation (wird auch von 'Apps & Features' aufgerufen)."""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import winreg

APP = "RSI Overhead"
BASE = os.path.dirname(os.path.abspath(__file__))
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + APP
KEEP = ("settings.json", "keybinds_user.json")


def ask(text, flags):
    return ctypes.windll.user32.MessageBoxW(0, text, APP + " – Deinstallation", flags)


def folder(name):
    ps = {"desktop": "[Environment]::GetFolderPath('Desktop')", "programs": "[Environment]::GetFolderPath('Programs')"}[name]
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=0x08000000).stdout.strip()


def main():
    if ask("RSI Overhead wirklich deinstallieren?", 0x24) != 6:          # YESNO + Fragezeichen
        return
    wipe = ask("Einstellungen und Tastenprofile auch löschen?\n\nNein = behalten (praktisch für eine spätere Neuinstallation).", 0x24) == 6
    for n in ("desktop", "programs"):
        try:
            p = os.path.join(folder(n), APP + ".lnk")
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    for key, val in ((RUN_KEY, APP),):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, val)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    os.chdir(tempfile.gettempdir())
    shutil.rmtree(os.path.join(os.environ.get("LOCALAPPDATA", ""), "RSIOverhead"), ignore_errors=True)   # Edge-Profil des Fensters
    for name in os.listdir(BASE):
        if not wipe and name in KEEP:
            continue
        p = os.path.join(BASE, name)
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.path.exists(p) and os.remove(p)
    if wipe:
        try:
            os.rmdir(BASE)
        except OSError:
            pass
    ask("RSI Overhead wurde entfernt.", 0x40)


if __name__ == "__main__":
    main()
