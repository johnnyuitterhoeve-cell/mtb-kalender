@echo off
rem Haalt de toertochten op en bewaart ze in events.json (naast dit bestand).
rem PUSH=1: de nieuwe gegevens worden na het ophalen ook naar GitHub geupload (voor je pagina op GitHub Pages).
set PUSH=1

cd /d "%~dp0"

rem Eerst de nieuwste gegevens van GitHub ophalen
rem Lokale wijzigingen aan de pagina zelf weggooien: die komt altijd van GitHub (voorkomt botsingen)
git checkout -- index.html scrape.py >nul 2>&1
git pull --rebase --autostash -X theirs >nul 2>&1

echo Pakketten controleren...
python -m pip install -q requests beautifulsoup4
if errorlevel 1 goto fout

echo Toertochten ophalen (de eerste keer duurt dit enkele minuten)...
python scrape.py
if errorlevel 1 goto fout

python controle.py
if errorlevel 1 (
    echo.
    echo De controle is mislukt: de nieuwe gegevens worden NIET geupload.
    git checkout -- events.json geocache.json sources.json detailcache.json
    goto fout
)

if not "%PUSH%"=="1" goto klaar

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo.
    echo De gegevens staan klaar in deze map, maar uploaden naar GitHub lukt niet:
    echo deze map is geen kopie van je GitHub-repository ^(of Git is niet geinstalleerd^).
    echo Kopieer de bestanden naar een gekloonde map, of upload ze via de GitHub-website.
    goto klaar
)

python paginas.py
if errorlevel 1 echo Let op: de vaste paginas ^(gravel/mtb^) maken mislukte; de rest gaat gewoon door.
python controle.py
if errorlevel 1 (
    echo De tweede controle is mislukt: niets wordt geupload.
    git checkout -- events.json geocache.json sources.json detailcache.json gravel mtb sitemap.xml
    goto fout
)

git add events.json geocache.json sources.json detailcache.json gravel mtb sitemap.xml
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Lokale update van toertochten"
    git pull --rebase --autostash -X theirs
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