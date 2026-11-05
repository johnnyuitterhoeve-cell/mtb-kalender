#!/usr/bin/env python3
"""Haalt toertochten op en schrijft ze naar events.json.

Bronnen staan in SOURCES. Een nieuwe bron toevoegen = een functie schrijven
die een lijst events teruggeeft en die in SOURCES zetten.
"""
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

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
SOURCES_FILE = "sources.json"
ALL_SOURCES = ["Mountainbike.be", "Fietssport.nl", "MTB-You", "GoDare", "Battistrada"]
NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Provinciecode op Mountainbike.be -> (volledige naam, landcodes voor de zoekopdracht)
PROVINCES = {
    "Ant": ("Antwerpen", "be"), "Bru": ("Brussel", "be"), "Hen": ("Henegouwen", "be"),
    "Lux": ("Luxemburg", "be,lu"), "Luik": ("Luik", "be"), "Nam": ("Namen", "be"),
    "Ovl": ("Oost-Vlaanderen", "be"), "Vlb": ("Vlaams-Brabant", "be"),
    "Wbr": ("Waals-Brabant", "be"), "Wvl": ("West-Vlaanderen", "be"),
    "Lim": ("Limburg", "be,nl"),
    "BL": (None, "be,nl,de"),
    "BE": (None, "be"), "NL": (None, "nl"),
    "Lui": ("Luik", "be"), "Bui": (None, "be,nl,de,fr,lu"),
    "Dre": ("Drenthe", "nl"), "Fle": ("Flevoland", "nl"), "Fri": ("Friesland", "nl"),
    "Gel": ("Gelderland", "nl"), "Gdl": ("Gelderland", "nl"), "Gro": ("Groningen", "nl"),
    "Nbr": ("Noord-Brabant", "nl"), "Nho": ("Noord-Holland", "nl"), "Ove": ("Overijssel", "nl"),
    "Utr": ("Utrecht", "nl"), "Zee": ("Zeeland", "nl"), "Zho": ("Zuid-Holland", "nl"),
}

ACRONYMS = {"mtb": "MTB", "vtt": "VTT", "atb": "ATB", "wtc": "WTC", "kwb": "KWB", "bch": "BCH"}

HREF_RE = re.compile(r"/toertochten/(\d{8})-([^/?#]+)")
TEXT_RE = re.compile(
    r"^(?:(?:nl|fr|en|de)\s+)?(?:(?P<prov>[A-Za-z.]{2,4})\s+)?(?P<place>.+?)"
    r"(?:\s+(?P<dist>\d+(?:\s*-\s*\d+)*))?\s+km\b(?P<rest>.*)$",
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

    distances = list(dict.fromkeys(int(x) for x in re.findall(r"\d+", m.group("dist") or "")))
    place = m.group("place").strip()
    prov = (m.group("prov") or "").capitalize()

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
    blocked = None
    for i in range(WEEKS_AHEAD):
        y, w, _ = (monday + timedelta(weeks=i)).isocalendar()
        url = f"https://www.mountainbike.be/toertochten-overzicht/{y}W{w:02d}"
        try:
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  {y}W{w:02d}: mislukt ({e})")
            if getattr(e, "response", None) is not None and e.response.status_code in (401, 403, 429):
                blocked = e.response.status_code
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
    if not events and blocked:
        raise PermissionError(f"toegang geweigerd ({blocked})")
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


# ---------- details per tocht: inschrijfgeld en organisator ----------
DETAIL_FILE = "detailcache.json"
DETAIL_MAX_AGE_DAYS = 21
AMOUNT_RE = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)")


def format_price(amounts):
    vals = sorted({float(a.replace(",", ".")) for a in amounts})
    if not vals:
        return ""
    fmt = lambda v: ("€ %.2f" % v).replace(".", ",")
    return fmt(vals[0]) if len(vals) == 1 else fmt(vals[0]) + " – " + fmt(vals[-1])


def page_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip()]
    return soup, lines


def line_after(lines, label):
    for i, line in enumerate(lines):
        if line.lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1]
    return ""


def detail_fietssport(html):
    soup, lines = page_lines(html)
    nxt = line_after(lines, "Kosten deelname")
    amounts = AMOUNT_RE.findall(nxt)
    if amounts:
        price = format_price(amounts)
    elif nxt.lower().startswith(("gratis", "vrije", "gratuit")):
        price = "Gratis"
    else:
        price = ""
    org = line_after(lines, "Organisatie")
    return {"price": price, "organizer": org if 0 < len(org) < 80 and org != "Website" else ""}


def detail_mountainbike(html):
    soup, lines = page_lines(html)
    cells = " ".join(td.get_text(" ", strip=True) for td in soup.select("td"))
    org = line_after(lines, "Organisatie")
    h1 = soup.find("h1")
    return {
        "price": format_price(AMOUNT_RE.findall(cells)),
        "organizer": org if 0 < len(org) < 80 else "",
        "title": h1.get_text(" ", strip=True) if h1 else "",
    }


DETAIL_PARSERS = {"Fietssport.nl": detail_fietssport, "Mountainbike.be": detail_mountainbike}


def enrich_details(events, skip=()):
    cache = load_json(DETAIL_FILE, {})
    today = date.today()
    failures = fetched = 0
    need = sum(1 for ev in events if ev.get("source") in DETAIL_PARSERS
               and ev.get("source") not in skip and ev["id"] not in cache)
    print(f"Details ophalen voor {need} tochten (circa {need * 1.5 / 60:.0f} minuten)...")
    for ev in events:
        parser = DETAIL_PARSERS.get(ev.get("source"))
        if not parser or ev.get("source") in skip:
            continue
        entry = cache.get(ev["id"])
        age = (today - date.fromisoformat(entry["fetched"])).days if entry else None
        if (entry is None or age >= DETAIL_MAX_AGE_DAYS) and failures < 5:
            try:
                time.sleep(1)
                r = requests.get(ev["sourceUrl"], headers=BROWSER_HEADERS, timeout=30)
                r.raise_for_status()
                entry = parser(r.text)
                entry["fetched"] = today.isoformat()
                cache[ev["id"]] = entry
                fetched += 1
                failures = 0
                if fetched % 25 == 0:
                    print(f"  {fetched} details opgehaald...")
            except (requests.RequestException, ValueError) as e:
                failures += 1
                print(f"  details mislukt voor {ev['id']}: {e}")
                if failures >= 5:
                    print("  Te veel mislukte verzoeken; details worden deze run overgeslagen.")
        if entry:
            for key in ("price", "organizer", "title"):
                if entry.get(key):
                    ev[key] = entry[key]
    keep = {ev["id"] for ev in events}
    cache = {k: v for k, v in cache.items() if k in keep}
    with open(DETAIL_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Details: {fetched} nieuw opgehaald, {len(cache)} in de cache")


# ---------- hulpfuncties voor extra bronnen ----------
def infer_date(day, month_abbr, today):
    mon = MONTHS.get(month_abbr.lower()[:3])
    if not mon:
        return None
    try:
        d = date(today.year, mon, day)
        return d if d >= today - timedelta(days=1) else date(today.year + 1, mon, day)
    except ValueError:
        return None


def next_page_url(soup, current_url):
    for a in soup.find_all("a", href=True):
        if "volgende" in a.get_text(" ", strip=True).lower() and not a["href"].startswith("#"):
            nxt = urljoin(current_url, a["href"])
            if nxt != current_url:
                return nxt
    return None


def unique_ints(text):
    return list(dict.fromkeys(int(x) for x in re.findall(r"(\d+)(?:[.,]\d+)?\s*km", text)))


def kind_from_title(title, default="MTB"):
    tl = title.lower()
    gravel = "gravel" in tl
    mtb = bool(re.search(r"mtb|atb|vtt|mountainbike", tl))
    if gravel and mtb:
        return "Both"
    return "Gravel" if gravel else default


# ---------- bron: MTB-You ----------
MY_BASE = "https://mtb-you.com/calendar"
MY_HREF_RE = re.compile(r"/calendar/tour/(\d+)/")
MY_DATE_RE = re.compile(r"^(?:ma|di|wo|do|vr|za|zo)\.?\s+(\d{1,2})\s+([A-Za-z]{3})\.?\s+", re.IGNORECASE)
MY_RE = re.compile(r"^(?P<title>.+)\s+(?P<pc>\d{4}(?:\s?[A-Z]{2})?)\s+(?P<place>.+?),\s*(?P<cc>BE|NL|DE|FR|LU)\b(?P<rest>.*)$")
BE_PROVINCES = ["Vlaams-Brabant", "West-Vlaanderen", "Oost-Vlaanderen", "Brabant Wallon", "Antwerpen",
                "Hainaut", "Luxembourg", "Limburg", "Liège", "Namur", "Brussels", "Brussel", "Bruxelles"]


def parse_my_entry(text, href, today):
    # Geeft een event, "SKIP" (geannuleerd, geen toertocht) of None (niet herkend)
    hm = MY_HREF_RE.search(href)
    text = re.sub(r"\s+", " ", re.sub(r"image/svg\+xml", " ", text)).strip()
    dm = MY_DATE_RE.match(text)
    if not hm or not dm:
        return None
    if "Geannuleerd" in text or "Toertocht" not in text:
        return "SKIP"
    d = infer_date(int(dm.group(1)), dm.group(2), today)
    m = MY_RE.match(text[dm.end():])
    if d is None or not m:
        return None
    place_str, cc, rest = m.group("place").strip(), m.group("cc"), m.group("rest")
    if cc == "BE":
        city = place_str
        for prov in BE_PROVINCES:
            if place_str.endswith(prov) and len(place_str) > len(prov):
                city = place_str[:-len(prov)].strip()
                break
    else:
        words = place_str.split()
        city = " ".join(words[:-1]) if len(words) >= 2 else place_str
    rest2 = re.sub(r"\s*(?:MTB|Gravel)?\s*Toertocht\b.*$", "", rest)
    mo = re.search(r"\bClub\s+(.+)$", rest2)
    title = m.group("title").strip()
    kind = "Gravel" if re.search(r"Gravel\s+Toertocht", rest) else kind_from_title(title)
    return {
        "id": "my-" + hm.group(1),
        "title": title,
        "date": d.isoformat(),
        "location": city,
        "type": kind,
        "distances": unique_ints(rest2),
        "organizer": mo.group(1).strip() if mo else "MTB-You",
        "sourceUrl": urljoin("https://mtb-you.com", href),
        "price": "",
        "source": "MTB-You",
        "_pc": (m.group("pc"), cc),
        "_prov": cc,
    }


def mtb_you():
    today = date.today()
    events, seen, unparsed, skipped = [], set(), [], 0
    url = MY_BASE
    for page in range(1, 9):
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        new = 0
        for a in soup.select('a[href*="/calendar/tour/"]'):
            href = a.get("href", "")
            hm = MY_HREF_RE.search(href)
            if not hm or hm.group(1) in seen:
                continue
            seen.add(hm.group(1))
            new += 1
            ev = parse_my_entry(a.get_text(" ", strip=True), href, today)
            if ev == "SKIP":
                skipped += 1
            elif ev is None:
                unparsed.append(a.get_text(" ", strip=True)[:120])
            elif ev["date"] >= today.isoformat():
                events.append(ev)
        print(f"  pagina {page}: {new} nieuwe tochten")
        if new == 0:
            break
        url = next_page_url(soup, url) or f"{MY_BASE}?page={page + 1}"
        time.sleep(1)
    print(f"  {len(events)} tochten, {skipped} geannuleerd of geen toertocht overgeslagen")
    if unparsed:
        print(f"  {len(unparsed)} regels niet herkend, bijvoorbeeld: {unparsed[:3]}")
    return events


# ---------- bron: GoDare ----------
GD_CALENDARS = [("Gravel", "https://www.godare.events/nl/events/gravel-ride-kalender"),
                ("MTB", "https://www.godare.events/nl/events/mountainbikekalender")]
GD_MONTHS = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
             "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12}
GD_DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(GD_MONTHS) + r")\s+(\d{4})", re.IGNORECASE)
GD_LOC_RE = re.compile(r"^(.+?)\s+-\s+(België|Nederland|Duitsland|Frankrijk|Luxemburg)$")
GD_COUNTRY = {"België": "BE", "Nederland": "NL"}


def parse_gd_card(h3, default_kind):
    link = h3.find("a", href=True)
    if link is None:
        return None
    node = h3
    for _ in range(6):
        node = node.parent
        if node is None or len(node.select("h3")) > 1:
            return None
        if GD_DATE_RE.search(node.get_text(" ", strip=True)):
            break
    else:
        return None
    lines = [l.strip() for l in node.get_text("\n", strip=True).split("\n") if l.strip()]
    dm = GD_DATE_RE.search(" ".join(lines))
    loc = next((GD_LOC_RE.match(l) for l in lines if GD_LOC_RE.match(l)), None)
    dist_line = next((l for l in lines if re.match(r"^\d+(?:[.,]\d+)?\s*km\b", l)), "")
    if not dm or not loc:
        return None
    try:
        d = date(int(dm.group(3)), GD_MONTHS[dm.group(2).lower()], int(dm.group(1)))
    except ValueError:
        return None
    title = link.get_text(" ", strip=True)
    slug = link["href"].rstrip("/").split("/")[-1]
    return {
        "id": "gd-" + slug,
        "title": title,
        "date": d.isoformat(),
        "location": loc.group(1).strip(),
        "type": kind_from_title(title, default_kind),
        "distances": unique_ints(dist_line),
        "organizer": "GoDare",
        "sourceUrl": urljoin("https://www.godare.events", link["href"]),
        "price": "",
        "source": "GoDare",
        "_prov": GD_COUNTRY.get(loc.group(2), ""),
    }


def godare():
    today = date.today().isoformat()
    events, seen, unparsed = [], set(), []
    for default_kind, base in GD_CALENDARS:
        url = base
        for page in range(1, 7):
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            new = 0
            for h3 in soup.select("h3"):
                link = h3.find("a", href=True)
                if link is None or "/events/" not in link["href"]:
                    continue
                slug = link["href"].rstrip("/").split("/")[-1]
                if slug in seen:
                    continue
                seen.add(slug)
                new += 1
                ev = parse_gd_card(h3, default_kind)
                if ev is None:
                    unparsed.append(link.get_text(" ", strip=True)[:80])
                elif ev["date"] >= today:
                    events.append(ev)
            print(f"  {default_kind} pagina {page}: {new} nieuwe tochten")
            if new == 0:
                break
            url = next_page_url(soup, url) or f"{base}?page={page + 1}"
            time.sleep(1)
    print(f"  {len(events)} tochten")
    if unparsed:
        print(f"  {len(unparsed)} kaarten niet herkend, bijvoorbeeld: {unparsed[:3]}")
    return events


# ---------- bron: Battistrada ----------
# {d} wordt vervangen door de datum van vandaag (zoals de site die zelf gebruikt, bijv. 4-Nov-26)
BS_URLS = [
    "https://battistrada.com/nl/cyclo-kalender/mountainbike/?eventdate={d}&biketype=2",
    "https://battistrada.com/nl/cyclo-kalender/gravel/?eventdate={d}&biketype=4",
    "https://battistrada.com/nl/cyclo-kalender/nederland/gravel/?biketype=4",
]
BS_COUNTRIES = {"Nederland": "NL", "België": "BE"}
BS_ID_RE = re.compile(r"/edition/[^/]+/(\d+)/")
BS_MONTHS = dict(MONTHS, mar=3, may=5, oct=10)
EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def with_page(url, n):
    parts = urlparse(url)
    q = parse_qs(parts.query)
    q["page"] = [str(n)]
    return urlunparse(parts._replace(query=urlencode(q, doseq=True)))


def parse_bs_card(card, today):
    # Geeft een event, "SKIP" (geen MTB/gravel-toertocht), "ABROAD" (ander land) of None (niet herkend)
    link = card.select_one("a.event-title") or card.select_one('a[href*="/cyclo-kalender/edition/"]')
    im = BS_ID_RE.search(link.get("href", "")) if link else None
    icon = card.select_one("i.fa-bicycle")
    if not im or icon is None:
        return None
    text = lambda sel: card.select_one(sel).get_text(" ", strip=True) if card.select_one(sel) else ""
    mon_txt, day_txt, wk_txt = text(".ai1ec-month"), text(".ai1ec-day"), text(".ai1ec-weekday")
    year = None
    if re.fullmatch(r"\d{4}", mon_txt):          # toekomstige jaren: jaar bovenaan, maand eronder
        year, mon_txt = int(mon_txt), wk_txt
    mon = BS_MONTHS.get(mon_txt.lower()[:3])
    if not mon or not day_txt.isdigit():
        return None
    try:
        if year:
            d = date(year, mon, int(day_txt))
        else:
            d = date(today.year, mon, int(day_txt))
            if d < today - timedelta(days=1):
                d = date(today.year + 1, mon, int(day_txt))
    except ValueError:
        return None
    flag = card.select_one("img[alt]")
    country = BS_COUNTRIES.get(flag.get("alt", "").strip()) if flag else None
    if country is None:
        return "ABROAD"
    bikes, _, activity = icon.parent.get_text(" ", strip=True).partition(" - ")
    bikes = bikes.lower()
    if "toertocht" not in activity.lower() or not ("gravel" in bikes or "mtb" in bikes):
        return "SKIP"
    loc_span = icon.parent.find_previous_sibling("span")
    place = loc_span.get_text(" ", strip=True) if loc_span else ""
    tip = loc_span.select_one(".tooltip-custom") if loc_span else None
    if tip:
        place = place.replace(tip.get_text(" ", strip=True), "", 1).strip()
    if not place:
        return None
    dist_div = card.select_one("div.col-sm-5")
    distances = list(dict.fromkeys(int(x) for x in re.findall(r"\d+", dist_div.get_text(" ", strip=True)))) if dist_div else []
    kind = "Both" if ("gravel" in bikes and "mtb" in bikes) else "Gravel" if "gravel" in bikes else "MTB"
    return {
        "id": "bs-" + im.group(1),
        "title": link.get_text(" ", strip=True),
        "date": d.isoformat(),
        "location": place,
        "type": kind,
        "distances": distances,
        "organizer": "Battistrada",
        "sourceUrl": urljoin("https://battistrada.com", link.get("href", "")),
        "price": "",
        "source": "Battistrada",
        "_prov": country,
    }


def diagnose_battistrada(r, soup, n):
    name = f"debug_battistrada_{n}.html"
    with open(name, "w", encoding="utf-8") as f:
        f.write(r.text)
    title = soup.title.get_text(strip=True) if soup.title else "(geen titel)"
    print(f"  Diagnose: status {r.status_code}, {len(r.text)} tekens, titel: {title}")
    print(f"  De ontvangen pagina is opgeslagen in {name}")


def battistrada():
    today_d = date.today()
    today = today_d.isoformat()
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    try:
        session.get("https://battistrada.com/nl/home/", timeout=30)
        time.sleep(1)
    except requests.RequestException:
        pass
    events, seen, other, unparsed = [], set(), {"SKIP": 0, "ABROAD": 0}, []
    date_param = f"{today_d.day}-{EN_MONTHS[today_d.month - 1]}-{today_d:%y}"
    for n, template in enumerate(BS_URLS, 1):
        base = template.format(d=date_param)
        print(f"  lijst {n}: {base}")
        url = base
        try:
            for page in range(1, 9):
                r = session.get(url, timeout=30, headers={"Referer": "https://battistrada.com/nl/home/"})
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                canon = soup.select_one("link[rel=canonical]")
                canon = canon.get("href", "") if canon else ""
                if page == 1:
                    print(f"  adres volgens de pagina: {canon or '(onbekend)'}")
                if canon.rstrip("/").endswith("/home"):
                    print("  Doorgestuurd naar de homepage: dit adres geeft geen kalender.")
                    diagnose_battistrada(r, soup, n)
                    break
                new = kept = 0
                for card in soup.select("div.shadow-sm.border"):
                    link = card.select_one('a[href*="/cyclo-kalender/edition/"]')
                    im = BS_ID_RE.search(link.get("href", "")) if link else None
                    if not im or im.group(1) in seen:
                        continue
                    seen.add(im.group(1))
                    new += 1
                    ev = parse_bs_card(card, today_d)
                    if isinstance(ev, str):
                        other[ev] += 1
                    elif ev is None:
                        unparsed.append(link.get_text(" ", strip=True)[:60])
                    elif ev["date"] >= today:
                        events.append(ev)
                        kept += 1
                print(f"  pagina {page}: {new} tochten gezien, {kept} bruikbaar")
                if new == 0:
                    if page == 1:
                        diagnose_battistrada(r, soup, n)
                    break
                url = next_page_url(soup, url) or with_page(base, page + 1)
                time.sleep(1)
        except requests.RequestException as e:
            print(f"  mislukt: {e}")
    print(f"  {len(events)} tochten; overgeslagen: {other['ABROAD']} buitenlands, {other['SKIP']} racefiets/geen toertocht")
    if unparsed:
        print(f"  {len(unparsed)} tochten niet herkend, bijvoorbeeld: {unparsed[:3]}")
    return events


# ---------- afstanden en coördinaten via postcode ----------
def km_between(lat1, lon1, lat2, lon2):
    rad = lambda x: x * 3.141592653589793 / 180
    a = (math.sin(rad(lat2 - lat1) / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def geocode_postcode(pc, cc):
    clean = pc.replace(" ", "").upper()
    key = f"pc:{cc}:{clean}"
    if key in GEO:
        return GEO[key]
    coords = None
    if cc == "NL" and re.fullmatch(r"\d{4}[A-Z]{2}", clean):
        try:
            time.sleep(0.3)
            r = requests.get("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free",
                             params={"rows": 1, "fq": "type:postcode", "q": clean}, headers=HEADERS, timeout=20)
            docs = r.json()["response"]["docs"]
            m = docs and re.search(r"POINT\(([-\d.]+) ([-\d.]+)\)", docs[0].get("centroide_ll", ""))
            if m:
                coords = [round(float(m.group(2)), 4), round(float(m.group(1)), 4)]
        except (requests.RequestException, ValueError, KeyError):
            pass
    if coords is None:
        try:
            time.sleep(1.1)
            r = requests.get(NOMINATIM, params={"postalcode": clean[:4], "countrycodes": cc.lower(),
                                                "format": "json", "limit": 1}, headers=HEADERS, timeout=20)
            data = r.json()
            if data:
                coords = [round(float(data[0]["lat"]), 4), round(float(data[0]["lon"]), 4)]
        except (requests.RequestException, ValueError):
            pass
    if coords:
        GEO[key] = coords
        print(f"  coördinaten gevonden: postcode {pc}")
    return coords


SOURCES = {
    "Mountainbike.be": mountainbike_be,
    "Fietssport.nl": fietssport_nl,
    "MTB-You": mtb_you,
    "GoDare": godare,
    # "Battistrada": battistrada,   # uitgeschakeld: de site stuurt scripts door naar de homepage
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
            print(f"  coördinaten gevonden: {place}")
            return GEO[key]
    print(f"  geen coördinaten voor {place} ({prov})")
    return None


# ---------- hoofdprogramma ----------
def main():
    events, errors, stale = [], {}, {}
    previous = load_json(EVENTS_FILE, [])
    if not isinstance(previous, list):
        previous = []
    for name, fetch in SOURCES.items():
        print(f"{name}:")
        try:
            found = fetch()
        except Exception as e:  # een kapotte bron mag de rest niet stoppen
            print(f"  FOUT: {e}")
            errors[name] = str(e)[:120]
            found = []
        print(f"  totaal {len(found)}")
        if not found:
            old = [e for e in previous if e.get("source") == name and e.get("date", "") >= date.today().isoformat()]
            if old:
                print(f"  oude gegevens bewaard: {len(old)} tochten")
                stale[name] = len(old)
                found = old
        events += found

    if not events:
        sys.exit("Geen enkele tocht opgehaald; events.json blijft ongewijzigd.")

    print("Coördinaten zoeken (alleen voor nieuwe plaatsen)...")
    for ev in events:
        prov = ev.pop("_prov", "")
        pc = ev.pop("_pc", None)
        if "lat" not in ev:
            coords = geocode_postcode(*pc) if pc else None
            if not coords:
                coords = geocode(ev["location"], prov)
            if coords:
                ev["lat"], ev["lon"] = coords

    # Dezelfde tocht op meerdere sites: zelfde dag, dezelfde plaats (of binnen 5 km) en
    # dezelfde titel, of (bij verschillende bronnen) een gemeenschappelijke afstand bij hetzelfde type.
    # De eerste bron in SOURCES wint.
    def same_place(x, y):
        if x["location"].lower() == y["location"].lower():
            return True
        if "lat" in x and "lat" in y:
            return km_between(x["lat"], x["lon"], y["lat"], y["lon"]) <= 5
        return False

    unique = []
    for ev in events:
        dup = any(
            u["date"] == ev["date"] and same_place(u, ev)
            and (u["title"].lower() == ev["title"].lower()
                 or (u.get("source") != ev.get("source") and set(u["distances"]) & set(ev["distances"])
                     and (u["type"] == ev["type"] or "Both" in (u["type"], ev["type"]))))
            for u in unique
        )
        if not dup:
            unique.append(ev)

    enrich_details(unique, skip=set(stale))

    unique.sort(key=lambda e: (e["date"], e["location"]))

    counts = {}
    for ev in unique:
        counts[ev["source"]] = counts.get(ev["source"], 0) + 1
    info = []
    for name in ALL_SOURCES:
        if name not in SOURCES:
            info.append({"name": name, "status": "niet gekoppeld", "count": 0, "message": ""})
        elif name in stale:
            info.append({"name": name, "status": "oud", "count": counts.get(name, 0),
                         "message": errors.get(name, "geen nieuwe tochten opgehaald")})
        elif name in errors:
            info.append({"name": name, "status": "fout", "count": 0, "message": errors[name]})
        else:
            info.append({"name": name, "status": "ok", "count": counts.get(name, 0), "message": ""})
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": info},
                  f, ensure_ascii=False, indent=2)

    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    with open(GEO_FILE, "w", encoding="utf-8") as f:
        json.dump(GEO, f, ensure_ascii=False, indent=2, sort_keys=True)

    missing = sum(1 for e in unique if "lat" not in e)
    print(f"Klaar: {len(unique)} tochten, {missing} zonder coördinaten.")


if __name__ == "__main__":
    main()
