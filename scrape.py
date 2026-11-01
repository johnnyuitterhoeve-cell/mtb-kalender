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
    "BL": (None, "be,nl,de"),
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


# ---------- bron: Fietssport.nl ----------
FS_URL = "https://www.fietssport.nl/toertochten"
FS_HREF_RE = re.compile(r"/toertochten/(\d+)/")
FS_DATE_RE = re.compile(
    r"^(?:(Vandaag)|(Morgen)|(?:Maan|Dins|Woens|Donder|Vrij|Zater|Zon)dag\s+(\d{1,2})\s+([A-Za-z]{3})\.?(?:\s+(\d{4}))?)\s+",
    re.IGNORECASE,
)
MONTHS = {"jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
# Provinciecodes van Fietssport -> codes zoals Mountainbike.be (zo delen ze de coördinaten-cache)
FS_PROV = {"NB": "Nbr", "OV": "Ove", "LB": "Lim", "NH": "Nho", "DR": "Dre", "GD": "Gel",
           "GR": "Gro", "FL": "Fle", "ZL": "Zee", "FR": "Fri", "UT": "Utr", "ZH": "Zho", "BL": "BL"}
PARTICLES = {"de", "den", "het", "ter", "te", "op", "aan", "st.", "sint", "nabij", "'t"}


def fs_date(m, today):
    if m.group(1):
        return today
    if m.group(2):
        return today + timedelta(days=1)
    day, mon, year = int(m.group(3)), MONTHS.get(m.group(4).lower()), m.group(5)
    if not mon:
        return None
    try:
        if year:
            return date(int(year), mon, day)
        d = date(today.year, mon, day)
        return d if d >= today - timedelta(days=1) else date(today.year + 1, mon, day)
    except ValueError:
        return None


def split_name(strings, name_part, prov_code):
    # Eerst proberen met de losse tekstdelen van de link (plaats staat dan los van de titel)
    for i, s in enumerate(strings):
        if "(" + prov_code + ")" in s:
            s2 = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", s).strip()
            if not s2 and i > 0:
                s2 = strings[i - 1].strip()
            if s2 and s2 != name_part and name_part.endswith(s2):
                return name_part[:-len(s2)].strip(), s2
            break
    # Anders: de plaats is het laatste woord (of de laatste twee bij "De Lutte", "Den Hoorn")
    words = name_part.split()
    n = 2 if len(words) >= 3 and words[-2].lower() in PARTICLES else 1
    place = " ".join(words[-n:])
    title = " ".join(words[:-n]) or name_part
    return title, place


def parse_fs_entry(strings, href, today):
    # Geeft een event, "SKIP" (racefiets/recreatief) of None (niet herkend)
    hm = FS_HREF_RE.search(href)
    full = re.sub(r"\s+", " ", " ".join(strings)).strip()
    dm = FS_DATE_RE.match(full)
    if not hm or not dm:
        return None
    d = fs_date(dm, today)
    rest = full[dm.end():]
    if d is None or "•" not in rest:
        return None
    left, right = rest.split("•", 1)
    left = left.strip()
    pm = re.search(r"\(([A-Z]{2})\)\s*$", left)
    if not pm:
        return None
    code = pm.group(1)
    name_part = left[:pm.start()].strip()

    tm = re.match(r"\s*(Mountainbike|Gravelbike|Challenge MTB)", right)
    if not tm:
        return "SKIP"
    kind = "Gravel" if tm.group(1) == "Gravelbike" else "MTB"
    distances = list(dict.fromkeys(int(x) for x in re.findall(r"(\d+)\s*km", right)))
    title, place = split_name(strings, name_part, code)
    return {
        "id": "fs-" + hm.group(1),
        "title": title,
        "date": d.isoformat(),
        "location": place,
        "type": kind,
        "distances": distances,
        "organizer": "Fietssport.nl",
        "sourceUrl": urljoin("https://www.fietssport.nl", href),
        "price": "",
        "source": "Fietssport.nl",
        "_prov": FS_PROV.get(code, code),
    }


def fietssport_nl():
    r = requests.get(FS_URL, headers=BROWSER_HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    today = date.today()
    events, seen, unparsed, skipped = [], set(), [], 0
    for a in soup.select('a[href*="/toertochten/"]'):
        href = a.get("href", "")
        if not FS_HREF_RE.search(href):
            continue
        strings = list(a.stripped_strings)
        ev = parse_fs_entry(strings, href, today)
        if ev == "SKIP":
            skipped += 1
        elif ev is None:
            unparsed.append(" ".join(strings)[:120])
        elif ev["id"] not in seen and ev["date"] >= today.isoformat():
            seen.add(ev["id"])
            events.append(ev)
    print(f"  {len(events)} MTB/gravel-tochten, {skipped} racefiets/recreatief overgeslagen")
    if unparsed:
        print(f"  {len(unparsed)} regels niet herkend, bijvoorbeeld: {unparsed[:3]}")
    return events


SOURCES = {
    "Mountainbike.be": mountainbike_be,
    "Fietssport.nl": fietssport_nl,
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
    place = re.sub(r"^nabij\s+", "", place, flags=re.IGNORECASE)
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

    # Dezelfde tocht op meerdere sites: zelfde dag en plaats, en dezelfde titel of
    # hetzelfde type met een gemeenschappelijke afstand. De eerste bron wint.
    unique = []
    for ev in events:
        dup = any(
            u["date"] == ev["date"] and u["location"].lower() == ev["location"].lower()
            and (u["title"].lower() == ev["title"].lower()
                 or (u["type"] == ev["type"] and set(u["distances"]) & set(ev["distances"])))
            for u in unique
        )
        if not dup:
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
