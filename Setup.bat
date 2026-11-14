@echo off
setlocal
cd /d "%~dp0"
rem Startet den Installer von RSI Overhead (benoetigt Python 3).

set "RUN="
py -3 -c "import sys" >nul 2>&1 && set "RUN=pyw -3"
if not defined RUN python -c "import sys" >nul 2>&1 && set "RUN=pythonw"

if defined RUN (
    start "" %RUN% "%~dp0Setup.py"
    exit /b 0
)

echo.
echo  RSI Overhead braucht Python 3 (kostenlos), das auf diesem PC fehlt.
echo.
choice /c JN /n /m " Jetzt automatisch installieren (winget)?  [J] Ja  [N] Nein, ich mache es selbst: "
if errorlevel 2 (
    start "" https://www.python.org/downloads/windows/
    echo.
    echo  Beim Installieren "Add python.exe to PATH" anhaken. Danach diese Datei erneut starten.
    pause
    exit /b 1
)
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo  Fertig. Bitte Setup.bat jetzt noch einmal starten.
pause
