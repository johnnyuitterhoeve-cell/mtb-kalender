#!/usr/bin/env python3
"""Haalt toertochten op en schrijft ze naar events.json.

Bronnen staan in SOURCES. Een nieuwe bron toevoegen = een functie schrijven
die een lijst events teruggeeft en die in SOURCES zetten.
"""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "mtb-gravel-kalender/1.0 (persoonlijk project, 1 verzoek per seconde)"}  # voor Nominatim
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "nl-NL,nl;q=0.9",
}
WEEKS_AHEAD = 12
EVENTS_FILE = "events.json"
GEO_FILE = "geocache.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Provinciecode op Mountainbike.be -> (volledige naam, landcodes voor de zoekopdracht)
PROVINCES = {
    "Ant": ("Antwerpen", "be"), "Bru": ("Brussel", "be"), "Hen": ("Henegouwen", "be"),
    "Lux": ("Luxemburg", "be,lu"), "Luik": ("Luik", "be"), "Nam": ("Namen", "be"),
    "Ovl": ("Oost-Vlaanderen", "be"), "Vlb": ("Vlaams-Brabant", "be"),
    "Wbr": ("Waals-Brabant", "be"), "Wvl": ("West-Vlaanderen", "be"),
    "Lim": ("Limburg", "be,nl"),
    "Dre": ("Drenthe", "nl"), "Fle": ("Flevoland", "nl"), "Fri": ("Friesland", "nl"),
    "Gel": ("Gelderland", "nl"), "Gdl": ("Gelderland", "nl"), "Gro": ("Groningen", "nl"),
    "Nbr": ("Noord-Brabant", "nl"), "Nho": ("Noord-Holland", "nl"), "Ove": ("Overijssel", "nl"),
    "Utr": ("Utrecht", "nl"), "Zee": ("Zeeland", "nl"), "Zho": ("Zuid-Holland", "nl"),
}

ACRONYMS = {"mtb": "MTB", "vtt": "VTT", "atb": "ATB", "wtc": "WTC", "kwb": "KWB", "bch": "BCH"}

HREF_RE = re.compile(r"/toertochten/(\d{8})-([^/?#]+)")
TEXT_RE = re.compile(
    r"^(?:(?:nl|fr|en|de)\s+)?(?P<prov>[A-Za-z.]{2,4})\s+(?P<place>.+?)\s+"
    r"(?P<dist>\d+(?:\s*-\s*\d+)*)\s*km\b(?P<rest>.*)$",
    re.IGNORECASE,
)


# ---------- hulpfuncties ----------
def ascii_slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_title(slug, place):
    place_slug = ascii_slug(place)
    rest = slug.strip("-")
    if rest.startswith(place_slug + "-"):
        rest = rest[len(place_slug) + 1:]
    elif rest == place_slug:
        rest = ""
    words = ["&" if w == "amp" else ACRONYMS.get(w, w) for w in rest.split("-") if w]
    if not words:
        return f"Toertocht {place}"
    title = " ".join(words)
    title = title[0].upper() + title[1:]
    return title if ascii_slug(place) in ascii_slug(title) else f"{title} {place}"


def parse_entry(datestr, slug, text, href):
    """Zet één link uit het weekoverzicht om naar een event, of None."""
    m = TEXT_RE.match(re.sub(r"\s+", " ", text).strip())
    if not m:
        return None
    try:
        iso = date(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:])).isoformat()
    except ValueError:
        return None

    distances = list(dict.fromkeys(int(x) for x in re.findall(r"\d+", m.group("dist"))))
    place = m.group("place").strip()
    prov = m.group("prov").capitalize()

    gravel = bool(re.search(r"\bgravel\b", m.group("rest"), re.I)) or "gravel" in slug
    mtb = bool(re.search(r"mtb|vtt|mountainbike|atb", slug))
    kind = "Both" if (gravel and mtb) else "Gravel" if gravel else "MTB"

    return {
        "id": f"mb-{datestr}-{slug}"[:90],
        "title": make_title(slug, place),
        "date": iso,
        "location": place,
        "type": kind,
        "distances": distances,
        "organizer": "Mountainbike.be",
        "sourceUrl": urljoin("https://www.mountainbike.be", href),
        "price": "",
        "source": "Mountainbike.be",
        "_prov": prov,
    }


# ---------- bron: Mountainbike.be ----------
def mountainbike_be():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    events, unparsed = [], []
    for i in range(WEEKS_AHEAD):
        y, w, _ = (monday + timedelta(weeks=i)).isocalendar()
        url = f"https://www.mountainbike.be/toertochten-overzicht/{y}W{w:02d}"
        try:
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  {y}W{w:02d}: mislukt ({e})")
            if getattr(e, "response", None) is not None and e.response.status_code in (401, 403, 429):
                print("  De site weigert de toegang; verdere weken worden overgeslagen.")
                break
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        count = 0
        for a in soup.select('a[href*="/toertochten/"]'):
            href = a.get("href", "")
            hm = HREF_RE.search(href)
            if not hm:
                continue
            text = a.get_text(" ", strip=True)
            ev = parse_entry(hm.group(1), hm.group(2), text, href)
            if ev is None:
                unparsed.append(text)
            elif ev["date"] >= today.isoformat():
                events.append(ev)
                count += 1
        print(f"  {y}W{w:02d}: {count} tochten")
        time.sleep(1)
    if unparsed:
        print(f"  {len(unparsed)} regels niet herkend, bijvoorbeeld: {unparsed[:3]}")
    return events


SOURCES = {
    "Mountainbike.be": mountainbike_be,
    # "Fietssport.nl": fietssport_nl,   # nog te bouwen
    # "MTB-You": mtb_you,               # nog te bouwen
    # "GoDare": godare,                 # nog te bouwen
    # "GravelBike.nl": gravelbike_nl,   # nog te bouwen
}


# ---------- coördinaten ----------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


GEO = load_json(GEO_FILE, {})


def geocode(place, prov):
    key = f"{place}|{prov}"
    if key in GEO:
        return GEO[key]
    full, countries = PROVINCES.get(prov, (None, "be,nl,de,fr,lu"))
    queries = ([f"{place}, {full}"] if full else []) + [place]
    for q in queries:
        time.sleep(1.1)  # Nominatim: maximaal 1 verzoek per seconde
        try:
            r = requests.get(
                NOMINATIM,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": countries},
                headers=HEADERS, timeout=20,
            )
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  geocoding mislukt voor {q}: {e}")
            continue
        if data:
            GEO[key] = [round(float(data[0]["lat"]), 4), round(float(data[0]["lon"]), 4)]
            return GEO[key]
    print(f"  geen coördinaten voor {place} ({prov})")
    return None


# ---------- hoofdprogramma ----------
def main():
    events = []
    for name, fetch in SOURCES.items():
        print(f"{name}:")
        try:
            found = fetch()
        except Exception as e:  # een kapotte bron mag de rest niet stoppen
            print(f"  FOUT: {e}")
            found = []
        print(f"  totaal {len(found)}")
        events += found

    if not events:
        sys.exit("Geen enkele tocht opgehaald; events.json blijft ongewijzigd.")

    seen, unique = set(), []
    for ev in events:
        key = (ev["title"].lower(), ev["date"], ev["location"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    for ev in unique:
        coords = geocode(ev["location"], ev.pop("_prov", ""))
        if coords:
            ev["lat"], ev["lon"] = coords

    unique.sort(key=lambda e: (e["date"], e["location"]))

    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    with open(GEO_FILE, "w", encoding="utf-8") as f:
        json.dump(GEO, f, ensure_ascii=False, indent=2, sort_keys=True)

    missing = sum(1 for e in unique if "lat" not in e)
    print(f"Klaar: {len(unique)} tochten, {missing} zonder coördinaten.")


if __name__ == "__main__":
    main()
