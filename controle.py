#!/usr/bin/env python3
"""Controleert of de bestanden van de toertochtenkalender nog heel zijn, vóór ze naar GitHub gaan.

Gebruik (in de map van de kalender):   python3 controle.py
Eindcode 0 = alles in orde, 1 = er is iets mis (er staat dan uitleg op het scherm).
Alleen standaardbibliotheek van Python nodig.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

MAP = os.path.dirname(os.path.abspath(__file__))
MIN_TOCHTEN = 100          # er horen er ruim 200 te staan
MIN_BRONNEN_OK = 3         # van de 5 bronnen moeten er minimaal 3 gelukt zijn
fouten = []


def lees(naam):
    with open(os.path.join(MAP, naam), encoding="utf-8") as f:
        return f.read()


# 1. Geen Git-conflicttekst ("<<<<<<<") in de bestanden (dat breekt de pagina)
for naam in ("index.html", "scrape.py", "events.json", "sources.json", "geocache.json", "detailcache.json", "manifest.webmanifest", "gravel/index.html", "mtb/index.html", "sitemap.xml"):
    try:
        tekst = lees(naam)
    except FileNotFoundError:
        if naam.startswith(("gravel", "mtb", "sitemap")):
            continue   # de vaste pagina's zijn nieuw; ontbreken is geen fout
        fouten.append(f"{naam} ontbreekt")
        continue
    if re.search(r"^(<<<<<<<|>>>>>>>)", tekst, re.M) or re.search(r"^=======$", tekst, re.M):
        fouten.append(f"{naam} bevat Git-conflicttekst (<<<<<<<)")

# 2. events.json is geldig en niet (bijna) leeg
events = []
try:
    events = json.loads(lees("events.json"))
    if isinstance(events, dict):
        events = events.get("events", [])
    if not isinstance(events, list) or len(events) < MIN_TOCHTEN:
        fouten.append(f"events.json bevat maar {len(events) if isinstance(events, list) else '?'} tochten (minimaal {MIN_TOCHTEN})")
except Exception as e:  # noqa: BLE001
    fouten.append(f"events.json is niet te lezen: {e}")

# 3. Het aantal mag niet ineens sterk dalen ten opzichte van de laatst bewaarde versie
try:
    oud = subprocess.run(["git", "show", "HEAD:events.json"], cwd=MAP, capture_output=True, text=True, timeout=30)
    if oud.returncode == 0 and events:
        o = json.loads(oud.stdout)
        o = o.get("events", []) if isinstance(o, dict) else o
        if len(o) > 0 and len(events) < 0.7 * len(o):
            fouten.append(f"het aantal tochten daalde van {len(o)} naar {len(events)} (meer dan 30%)")
except Exception:  # noqa: BLE001
    pass  # geen Git of geen vorige versie: overslaan

# 4. Tochten hebben een titel en een datum, en de meeste liggen in de toekomst
if isinstance(events, list) and events:
    zonder = sum(1 for e in events if not (e.get("title") and e.get("date")))
    if zonder > 0.1 * len(events):
        fouten.append(f"{zonder} tochten missen een titel of datum")
    vandaag = datetime.date.today().isoformat()
    toekomst = sum(1 for e in events if str(e.get("date", "")) >= vandaag)
    if toekomst < 0.5 * len(events):
        fouten.append(f"slechts {toekomst} van {len(events)} tochten liggen in de toekomst")

# 5. Genoeg bronnen gelukt
try:
    bronnen = json.loads(lees("sources.json")).get("sources", [])
    ok = sum(1 for b in bronnen if b.get("status") == "ok")
    if ok < MIN_BRONNEN_OK:
        fouten.append(f"maar {ok} van {len(bronnen)} bronnen zijn gelukt (minimaal {MIN_BRONNEN_OK})")
except Exception as e:  # noqa: BLE001
    fouten.append(f"sources.json is niet te lezen: {e}")

# 6. De pagina zelf: moet nog de basisonderdelen hebben en (als Node er is) geldige JavaScript
try:
    html = lees("index.html")
    for onderdeel in ('id="eventsContainer"', "events.json", "</html>"):
        if onderdeel not in html:
            fouten.append(f"index.html mist {onderdeel}")
    node = shutil.which("node")
    if node:
        scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
        for i, code in enumerate(scripts):
            if code.strip().startswith("{") and 'type="application/ld+json"' in html:
                continue
            tmp = os.path.join(MAP, f".controle_{i}.js")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(code)
            r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
            os.remove(tmp)
            if r.returncode != 0:
                regels = [x for x in r.stderr.splitlines() if "Error" in x]
                fouten.append("JavaScript in index.html bevat een fout: " + (regels[0] if regels else "onbekend"))
except FileNotFoundError:
    pass

if fouten:
    print("CONTROLE MISLUKT - niets wordt geupload:")
    for f in fouten:
        print("  -", f)
    sys.exit(1)
print(f"Controle in orde: {len(events)} tochten, pagina en gegevens zien er goed uit.")
