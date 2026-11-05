@echo off
rem Haalt de toertochten op en bewaart ze in events.json (naast dit bestand).
rem PUSH=1: de nieuwe gegevens worden na het ophalen ook naar GitHub geupload (voor je pagina op GitHub Pages).
set PUSH=1

cd /d "%~dp0"

echo Pakketten controleren...
python -m pip install -q requests beautifulsoup4
if errorlevel 1 goto fout

echo Toertochten ophalen (de eerste keer duurt dit enkele minuten)...
python scrape.py
if errorlevel 1 goto fout

if not "%PUSH%"=="1" goto klaar

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo.
    echo De gegevens staan klaar in deze map, maar uploaden naar GitHub lukt niet:
    echo deze map is geen kopie van je GitHub-repository ^(of Git is niet geinstalleerd^).
    echo Kopieer de bestanden naar een gekloonde map, of upload ze via de GitHub-website.
    goto klaar
)

git add events.json geocache.json sources.json detailcache.json
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Lokale update van toertochten"
    git pull --rebase -X theirs
    git push
) else (
    echo Geen wijzigingen om te uploaden.
)

:klaar
echo Klaar.
pause
exit /b 0

:fout
echo.
echo Er ging iets mis. Lees de melding hierboven.
pause
exit /b 1
