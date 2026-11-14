"""Baut ein Update-Paket fuer GitHub Pages (docs/app/pc/) – wie bei A.R.I.

    python tools/release.py "Was ist neu"                  naechste Version (+1), Name 1.0.0 -> 1.0.1
    python tools/release.py "Was ist neu" --name 1.1.0     eigener Versionsname
    python tools/release.py "Erste Version" --keep-version Version NICHT erhoehen (erste Veroeffentlichung)
    ... --push                                             danach git add/commit/push + GitHub-Release (Download)
    python tools/release.py --github-only                  nur den GitHub-Release der aktuellen Version anlegen

Das Skript setzt VERSION/VERSION_NAME in updater.py, packt NUR Programmdateien in docs/app/pc/rsi-overhead.zip,
schreibt version.json (mit SHA-256) und haengt den Eintrag an changelog.json an.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "app", "pc")
FILES = ["rsi_overhead.py", "updater.py", "uninstall.py", "RSI Overhead.ico", "README.md"]
DIRS = ["ui"]
SKIP_DIRS = {"__pycache__"}


def read_version():
    s = open(os.path.join(ROOT, "updater.py"), encoding="utf-8").read()
    v = int(re.search(r"^VERSION = (\d+)", s, re.M).group(1))
    n = re.search(r'^VERSION_NAME = "([^"]+)"', s, re.M).group(1)
    return s, v, n


EXTRA = ["Setup.py", "Setup.bat", "RSI Overhead.bat"]      # nur im Download-Paket (Installer), nicht im Update


def installer_zip(name):
    """Komplettes Download-Paket fuer GitHub Releases: entpacken, Setup.bat starten."""
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    zpath = os.path.join(ROOT, "dist", "RSI-Overhead-%s.zip" % name)
    entries = [(os.path.join(ROOT, f), f) for f in FILES + EXTRA]
    for d in DIRS:
        for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
            dn[:] = sorted(x for x in dn if x not in SKIP_DIRS)
            for x in sorted(fn):
                full = os.path.join(dp, x)
                entries.append((full, os.path.relpath(full, ROOT).replace("\\", "/")))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in entries:
            z.write(full, "RSI Overhead/" + arc)
    return zpath


def find_gh():
    import shutil
    return shutil.which("gh") or next((p for p in (r"C:\Program Files\GitHub CLI\gh.exe",) if os.path.isfile(p)), None)


def github_release(name, notes):
    """Legt auf GitHub einen Release v<name> mit dem Installer-Paket an (zum Herunterladen)."""
    gh = find_gh()
    if not gh:
        print("gh (GitHub CLI) nicht gefunden - Release uebersprungen.")
        return
    tag = "v" + name
    if subprocess.run([gh, "release", "view", tag], cwd=ROOT, capture_output=True).returncode == 0:
        print("Release %s existiert bereits - uebersprungen." % tag)
        return
    zpath = installer_zip(name)
    subprocess.run([gh, "release", "create", tag, zpath, "--target", "main", "--title", "RSI Overhead " + name, "--notes",
                    notes + "\n\nInstallation: Zip entpacken, `Setup.bat` starten (Python 3 noetig)."], cwd=ROOT, check=True)
    print("GitHub-Release %s veroeffentlicht." % tag)


def main():
    a = sys.argv[1:]
    if "--github-only" in a:                               # nur Release fuer die aktuelle Version (Notizen aus changelog.json)
        _, ver, name = read_version()
        cl = json.load(open(os.path.join(OUT, "changelog.json"), encoding="utf-8"))
        notes = next((e["notes"] for e in cl if int(e["version"]) == ver), "RSI Overhead " + name)
        return github_release(name, notes)
    if not a or a[0].startswith("--"):
        sys.exit(__doc__)
    notes = a[0]
    src, ver, name = read_version()
    if "--keep-version" not in a:
        ver += 1
        if "--name" in a:
            name = a[a.index("--name") + 1]
        else:
            p = name.split(".")
            p[-1] = str(int(p[-1]) + 1)
            name = ".".join(p)
        src = re.sub(r"^VERSION = \d+", "VERSION = %d" % ver, src, flags=re.M)
        src = re.sub(r'^VERSION_NAME = "[^"]+"', 'VERSION_NAME = "%s"' % name, src, flags=re.M)
        open(os.path.join(ROOT, "updater.py"), "w", encoding="utf-8").write(src)

    os.makedirs(OUT, exist_ok=True)
    entries = []
    for f in FILES:
        entries.append((os.path.join(ROOT, f), f))
    for d in DIRS:
        for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
            dn[:] = sorted(x for x in dn if x not in SKIP_DIRS)
            for x in sorted(fn):
                full = os.path.join(dp, x)
                entries.append((full, os.path.relpath(full, ROOT).replace("\\", "/")))
    zpath = os.path.join(OUT, "rsi-overhead.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in entries:
            z.write(full, arc)
    sha = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    json.dump({"version": ver, "name": name, "zip": "rsi-overhead.zip", "sha256": sha},
              open(os.path.join(OUT, "version.json"), "w", encoding="utf-8"), indent=1)

    cl_path = os.path.join(OUT, "changelog.json")
    try:
        cl = json.load(open(cl_path, encoding="utf-8"))
    except (OSError, ValueError):
        cl = []
    cl = [e for e in cl if int(e.get("version", 0)) != ver] + [{"version": ver, "name": name, "notes": notes}]
    cl.sort(key=lambda e: int(e["version"]))
    json.dump(cl, open(cl_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(os.path.join(ROOT, "docs", ".nojekyll"), "w").close()
    print("Version %d (%s) gebaut: %d Dateien, sha256 %s..." % (ver, name, len(entries), sha[:12]))

    if "--push" in a:
        run = lambda *c: subprocess.run(c, cwd=ROOT, check=True)
        run("git", "add", "-A")
        run("git", "commit", "-m", "Release %s: %s" % (name, notes))
        run("git", "push")
        print("Gepusht. GitHub Pages ist in ca. 1 Minute aktuell.")
        github_release(name, notes)
    else:
        print("Naechster Schritt: git add -A && git commit -m \"Release %s\" && git push" % name)


if __name__ == "__main__":
    main()
