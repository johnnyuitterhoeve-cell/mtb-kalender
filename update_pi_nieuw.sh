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
git add events.json geocache.json sources.json detailcache.json
if git diff --cached --quiet; then
    echo "Geen wijzigingen om te uploaden."
else
    git commit -m "Wekelijkse update van toertochten (Raspberry Pi)"
    git pull --rebase --autostash -X theirs
    git push
fi
echo "Klaar."
