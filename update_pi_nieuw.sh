#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "=== $(date '+%Y-%m-%d %H:%M') ==="
git pull --rebase --autostash -X theirs || echo "Let op: ophalen van GitHub mislukte, ga toch door"
python3 scrape.py || { echo "De scraper is mislukt"; exit 1; }
python3 controle.py || {
    echo "De controle is mislukt: de nieuwe gegevens worden NIET geupload."
    git checkout -- events.json geocache.json sources.json detailcache.json
    exit 1
}
python3 paginas.py || echo "Let op: de vaste pagina's (gravel/mtb) maken mislukte; de rest gaat gewoon door."
python3 controle.py || {
    echo "De tweede controle is mislukt: niets wordt geupload."
    git checkout -- events.json geocache.json sources.json detailcache.json gravel mtb sitemap.xml
    exit 1
}
git add events.json geocache.json sources.json detailcache.json gravel mtb sitemap.xml
if git diff --cached --quiet; then
    echo "Geen wijzigingen om te uploaden."
else
    git commit -m "Wekelijkse update van toertochten (Raspberry Pi)"
    git pull --rebase --autostash -X theirs
    git push
fi
echo "Klaar."
