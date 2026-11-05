@echo off
rem Start de kalender op http://localhost:8000 (openen via dubbelklikken op index.html werkt niet).
cd /d "%~dp0"
start "" /b python -m http.server 8000
timeout /t 2 /nobreak >nul
start "" http://localhost:8000
echo De kalender draait op http://localhost:8000
echo Sluit dit venster om te stoppen.
pause >nul
