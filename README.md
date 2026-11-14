# RSI Overhead

## Installieren (empfohlen, auch auf anderen PCs mit Python)
`Setup.bat` doppelklicken. Der Installer kopiert das Programm nach `Dokumente\RSI Overhead` (wie A.R.I; der Ordner ist waehlbar),
legt Desktop- und Startmenue-Verknuepfung mit dem Logo an (optional: Autostart mit Windows, minimiert) und
traegt es unter "Apps & Features" ein (Deinstallation dort oder ueber `uninstall.py`). Neu installieren = Update,
Einstellungen und Tastenprofile bleiben erhalten. Ohne Fenster: Optionen siehe Kopf von `Setup.py`.

Autostart, Overlay (immer oben + kein Fokusklau), Auto-Update, Theme, Spielordner, Layout und "Launcher beenden"
stehen im Einstellungs-Fenster (Zahnrad oben rechts, Inhalt: `ui/config/settings.json`).

## Ohne Installation starten
`RSI Overhead.bat` (Fenster schliessen = beenden).

## Updates (wie bei A.R.I, ueber GitHub Pages)
* **Im Programm:** SYSTEM › Launcher-Update › "Nach Update suchen". Gibt es eins, wird der Button zu
  "Update installieren" (Download, SHA-256-Pruefung, Backup in `backups/`, Neustart). "Auto-Update" installiert
  neue Versionen von selbst (Standard: aus). Einstellungen und Tastenprofile werden nie ueberschrieben.
* **Neue Version veroeffentlichen** (im Repo-Ordner):
  ```
  python tools/release.py "Was ist neu"            # Version +1, baut docs/app/pc/ (Zip, version.json, changelog.json)
  git add -A && git commit -m "Release" && git push
  ```
  oder in einem Schritt: `python tools/release.py "Was ist neu" --push`. GitHub Pages (Quelle: Branch `main`, Ordner `/docs`)
  ist nach ca. einer Minute aktuell. `UPDATE_BASE` steht in `updater.py`.

## Aufbau (modular)
```
rsi_overhead.py            Host: Fenster, Fokus-Schutz, Hotkey, Tasten, Systemwerte
ui/
  index.html, app.js     Renderer (baut alles aus config/)
  theme.css              Aussehen aller Elemente
  logo.png               optional: ersetzt die Textmarke oben + Fenstersymbol
  art/*.svg              Grafiken der Karten (Farben werden auf das Theme umgefaerbt)
  config/
    app.json             Rahmen: Titel, Statusleiste, Kopf-Buttons, Button->Aktion
    pages.json           Seiten > Spalten > Karten > Elemente
    themes.json          Farbschemata (11 Farben je Theme)
    keybinds.json        Tastenaktionen + Standardtasten
```

## Module (Karten) umbauen
* **Im Programm:** Stift-Symbol oben rechts = Layout-Modus. Karten verschieben (◀ ▲ ▼ ▶), entfernen (✕),
  Module aus allen Seiten unten per "+ ..." hinzufuegen. Gespeichert pro Seite, "Layout zuruecksetzen" stellt `pages.json` wieder her.
* **In der Datei:** Eine Karte in `pages.json` ist `{ "title": "...", "controls": [ ... ] }`.
  Element-Typen: `seg`, `chips`, `toggles`, `range`, `kv`, `key`, `btn`, `btnrow`, `danger`, `start`, `hero`, `art`, `power`, `palette`.
  Neues Element = neuer Eintrag in `RENDER` (app.js), neue Button-Aktion = Eintrag in `ACTIONS` + `labelActions` (app.json).
* **Neue Seite:** Objekt in `pages.json > pages` anhaengen (`id`, `title`, `columns`).
* **Neues Theme:** Block in `themes.json` kopieren; bei Chips mit `"apply":"theme"` den Namen in `options` ergaenzen.

## Einstellungen (settings.json)
`hotkey` (Standard `ctrl+shift+f9`, blendet das Fenster aus/ein), `no_focus` und `always_on_top`
(Klick holt das Spiel nicht aus dem Vordergrund), `window` (Startgroesse), `game_dir` (falls das Spiel nicht gefunden wird).
