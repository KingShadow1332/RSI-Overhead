# RSI Overhead

**Download:** [Neueste Version (Zip)](https://github.com/KingShadow1332/RSI-Overhead/releases/latest) – entpacken, `Setup.bat` starten.

## Installieren (empfohlen, auch auf anderen PCs mit Python)
`Setup.bat` doppelklicken. Der Installer kopiert das Programm nach `Dokumente\RSI Overhead` (wie A.R.I; der Ordner ist waehlbar),
legt Desktop- und Startmenue-Verknuepfung mit dem Logo an (optional: Autostart mit Windows, minimiert) und
traegt es unter "Apps & Features" ein (Deinstallation dort oder ueber `uninstall.py`). Neu installieren = Update,
Einstellungen und Tastenprofile bleiben erhalten. Ohne Fenster: Optionen siehe Kopf von `Setup.py`.

Autostart, Overlay (immer oben + kein Fokusklau), Auto-Update, Theme, Spielordner, Layout und "Launcher beenden"
stehen im Einstellungs-Fenster (Zahnrad "Einstellungen" oben rechts, Inhalt: `ui/config/settings.json`).

## Ohne Installation starten
`RSI Overhead.bat` (Fenster schliessen = beenden).

## Updates (wie bei A.R.I, ueber GitHub Pages)
* **Automatisch (Standard: an):** Das Programm prueft beim Start und danach alle 30 Minuten und installiert neue
  Versionen selbst (Download, SHA-256-Pruefung, Backup in `backups/`, Neustart mit Meldung) - aber nie, waehrend
  Star Citizen laeuft; dann wartet es bis zum Spielende. Abschalten: Zahnrad › "Auto-Update".
* **Von Hand:** Zahnrad › Update › "Nach Update suchen"; ist eins da, wird der Button zu "Update installieren".
  Einstellungen und Tastenprofile werden nie ueberschrieben.
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
* **Im Programm:** Stift-Symbol oben rechts (oder Zahnrad › Module › Layout bearbeiten) = Layout-Modus. Module am Griff ⠿
  mit der Maus in jede Spalte und Position ziehen (oder mit ◀ ▲ ▼ ▶), mit ✕ entfernen und ueber "+ Modul hinzufuegen"
  aus allen Seiten wieder holen. **Groesse:** den Balken unten an einer Karte ziehen (Hoehe), die Linie zwischen den Spalten
  ziehen (Breite); Doppelklick = automatisch. **Tasten/Buttons pro Modul:** in Karten mit Tasten oder Buttons gibt es ✕ je Eintrag
  und "+ Taste/Button hinzufuegen". Gespeichert pro Seite, "Layout zuruecksetzen" stellt `pages.json` wieder her.
* **In der Datei:** Eine Karte in `pages.json` ist `{ "title": "...", "controls": [ ... ] }`.
  Element-Typen: `seg`, `chips`, `toggles`, `range`, `kv`, `key`, `btn`, `btnrow`, `danger`, `start`, `hero`, `art`, `power`, `palette`.
  Neues Element = neuer Eintrag in `RENDER` (app.js), neue Button-Aktion = Eintrag in `ACTIONS` + `labelActions` (app.json).
* **Neue Seite:** Objekt in `pages.json > pages` anhaengen (`id`, `title`, `columns`).
* **Neues Theme:** Block in `themes.json` kopieren; bei Chips mit `"apply":"theme"` den Namen in `options` ergaenzen.

## Einstellungen (settings.json)
`hotkey` (Standard `ctrl+shift+f9`, blendet das Fenster aus/ein), `no_focus` und `always_on_top`
(Klick holt das Spiel nicht aus dem Vordergrund), `window` (Startgroesse), `game_dir` (falls das Spiel nicht gefunden wird).
