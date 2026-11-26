"""Telt hoeveel tochten alleen bij Mountainbike.be staan (en dus wegvallen als die bron wegblijft).

Draait alle andere bronnen opnieuw, zonder iets op te slaan of te uploaden, en vergelijkt ze met de
Mountainbike.be-tochten in events.json. Duurt een paar minuten.   Gebruik:  python3 telling_mountainbike.py
"""
import collections
import datetime
import json
import re
import unicodedata

import scrape


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def zelfde(a, b):
    la, lb = norm(a["location"]), norm(b["location"])
    if la and lb and (la == lb or la in lb or lb in la):
        return True
    return len(set(norm(a["title"]).split()) & set(norm(b["title"]).split())) >= 2


vandaag = datetime.date.today().isoformat()
with open("events.json", encoding="utf-8") as f:
    mb = [e for e in json.load(f) if e.get("source") == "Mountainbike.be" and e["date"] >= vandaag]
print(f"Mountainbike.be-tochten in je kalender: {len(mb)}\n")

andere = {}
for naam, haal in scrape.SOURCES.items():
    if naam == "Mountainbike.be":
        continue
    try:
        print(f"{naam} ophalen...")
        andere[naam] = [e for e in haal() if e["date"] >= vandaag]
    except Exception as e:  # noqa: BLE001
        print(f"  mislukt: {e}")
        andere[naam] = []

per_datum = collections.defaultdict(list)
for naam, lijst in andere.items():
    for e in lijst:
        per_datum[e["date"]].append((naam, e))

alleen = []
gedekt = collections.Counter()
for e in mb:
    treffers = {naam for naam, o in per_datum[e["date"]] if zelfde(e, o)}
    if treffers:
        for t in treffers:
            gedekt[t] += 1
    else:
        alleen.append(e)

print("\n==== UITKOMST ====")
print(f"Ook bij een andere bron: {len(mb) - len(alleen)} van {len(mb)}")
for naam, n in gedekt.most_common():
    print(f"  {naam}: {n}")
print(f"\nALLEEN bij Mountainbike.be: {len(alleen)}")
print("per land:", dict(collections.Counter(e.get("country") or "?" for e in alleen)))
print("per maand:", sorted(collections.Counter(e["date"][:7] for e in alleen).items()))
for e in sorted(alleen, key=lambda e: e["date"]):
    print(f"  {e['date']}  {e['location']} | {e['title'][:50]}")
