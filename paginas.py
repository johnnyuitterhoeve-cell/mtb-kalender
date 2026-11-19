#!/usr/bin/env python3
"""Maakt vaste, leesbare pagina's per type (gravel/ en mtb/) en vernieuwt sitemap.xml.

Gebruik (in de map van de kalender):   python3 paginas.py
Leest events.json en schrijft gravel/index.html, mtb/index.html en sitemap.xml.
Alleen standaardbibliotheek van Python nodig. Bij een fout blijft de bestaande site ongewijzigd.
"""
import datetime
import html
import json
import os
import re
import sys

MAP = os.path.dirname(os.path.abspath(__file__))
SITE = "https://toertochtenkalender.nl"
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
LANDEN = {"NL": "Nederland", "BE": "België"}

TYPES = [
    {"pad": "gravel", "types": {"Gravel", "Both"}, "naam": "Gravel", "filter": "Gravel"},
    {"pad": "mtb", "types": {"MTB", "Both"}, "naam": "MTB", "filter": "MTB"},
]
MIN_REGIO = 5          # een regio krijgt pas een eigen pagina vanaf zoveel tochten

# sleutel -> (weergavenaam, slug, land)
GEBIEDEN = {
    "NL": ("Nederland", "nederland", "NL"), "BE": ("België", "belgie", "BE"),
    "Noord-Brabant": ("Noord-Brabant", "noord-brabant", "NL"), "Gelderland": ("Gelderland", "gelderland", "NL"),
    "Overijssel": ("Overijssel", "overijssel", "NL"), "Limburg": ("Limburg (Nederland)", "limburg-nederland", "NL"),
    "Noord-Holland": ("Noord-Holland", "noord-holland", "NL"), "Zuid-Holland": ("Zuid-Holland", "zuid-holland", "NL"),
    "Utrecht": ("Utrecht", "utrecht", "NL"), "Zeeland": ("Zeeland", "zeeland", "NL"), "Friesland": ("Friesland", "friesland", "NL"),
    "Drenthe": ("Drenthe", "drenthe", "NL"), "Groningen": ("Groningen", "groningen", "NL"), "Flevoland": ("Flevoland", "flevoland", "NL"),
    "Antwerpen": ("Antwerpen", "antwerpen", "BE"), "West-Vlaanderen": ("West-Vlaanderen", "west-vlaanderen", "BE"),
    "Oost-Vlaanderen": ("Oost-Vlaanderen", "oost-vlaanderen", "BE"), "Vlaams-Brabant": ("Vlaams-Brabant", "vlaams-brabant", "BE"),
    "Limburg (BE)": ("Limburg (België)", "limburg-belgie", "BE"), "Henegouwen": ("Henegouwen", "henegouwen", "BE"),
    "Luik": ("Luik", "luik", "BE"), "Namen": ("Namen", "namen", "BE"), "Luxemburg (BE)": ("Luxemburg (België)", "luxemburg-belgie", "BE"),
    "Waals-Brabant": ("Waals-Brabant", "waals-brabant", "BE"), "Brussel": ("Brussel", "brussel", "BE"),
}
BE_PC = [(1000, 1299, "Brussel"), (1300, 1499, "Waals-Brabant"), (1500, 1999, "Vlaams-Brabant"), (2000, 2999, "Antwerpen"),
         (3000, 3499, "Vlaams-Brabant"), (3500, 3999, "Limburg (BE)"), (4000, 4999, "Luik"), (5000, 5999, "Namen"),
         (6000, 6599, "Henegouwen"), (6600, 6999, "Luxemburg (BE)"), (7000, 7999, "Henegouwen"), (8000, 8999, "West-Vlaanderen"),
         (9000, 9999, "Oost-Vlaanderen")]
NL_PC = [(1000, 1299, "Noord-Holland"), (1300, 1379, "Flevoland"), (1380, 2199, "Noord-Holland"), (2200, 3399, "Zuid-Holland"),
         (3400, 3999, "Utrecht"), (4000, 4199, "Gelderland"), (4200, 4299, "Zuid-Holland"), (4300, 4599, "Zeeland"),
         (4600, 5299, "Noord-Brabant"), (5300, 5399, "Gelderland"), (5400, 5799, "Noord-Brabant"), (5800, 6499, "Limburg"),
         (6500, 7399, "Gelderland"), (7400, 7799, "Overijssel"), (7800, 7999, "Drenthe"), (8000, 8299, "Overijssel"),
         (8300, 8399, "Flevoland"), (8400, 9299, "Friesland"), (9300, 9499, "Drenthe"), (9500, 9999, "Groningen")]
# plaatsen waarvan de bron geen postcode geeft (aanvullen als er nieuwe bijkomen; onbekende plaatsen worden via de dichtstbijzijnde tocht ingedeeld)
PLAATS_PROVINCIE = {
    "Terlet": "Gelderland", "Katwijk": "Zuid-Holland", "Soest": "Utrecht", "Gassel": "Noord-Brabant", "Nabij Vasse": "Overijssel",
    "Prinsenbeek": "Noord-Brabant", "Boekel": "Noord-Brabant", "Rijk van Nijmegen": "Gelderland", "Apeldoorn": "Gelderland",
    "Hattem": "Gelderland", "Markelo": "Overijssel", "Borgloon": "Limburg (BE)", "Schaijk": "Noord-Brabant", "Ursem": "Noord-Holland",
    "Wageningen": "Gelderland", "Rheeze": "Overijssel", "Surhuizum": "Friesland", "Hellendoorn": "Overijssel", "Nijkerk": "Gelderland",
    "Norg": "Drenthe", "Heesch": "Noord-Brabant", "Scherpenzeel": "Gelderland", "Hattemerbroek": "Gelderland", "Escharen": "Noord-Brabant",
    "Rijssen": "Overijssel", "Volkel": "Noord-Brabant", "Staphorst": "Overijssel", "Rhenoy": "Gelderland", "Lemelerveld": "Overijssel",
    "Steenwijk": "Overijssel", "Uden": "Noord-Brabant", "Winkel": "Noord-Holland", "Jistrum": "Friesland", "Hulst": "Zeeland",
    "Nijverdal": "Overijssel", "Berlicum": "Noord-Brabant", "Surhuisterveen": "Friesland",
}

TYPE_WOORDEN = re.compile(r"\b(mtb|atb|vtt|gravelbike|gravelride|graveltocht|gravel|grvl)\b", re.I)


def titelsleutel(t):
    t = TYPE_WOORDEN.sub(" ", str(t).lower())
    t = re.sub(r"\b(vwb|cyclo)\b", " ", t)
    t = re.sub(r"\b20\d\d\b", " ", t)
    t = re.sub(r"(toer)?tocht\b", " ", t)
    return re.sub(r"[^a-z0-9À-ɏ]+", " ", t).strip()


def esc(x):
    return html.escape(str(x), quote=True)


def datum_nl(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month - 1]} {d.year}"


def schoon_adres(t):
    """Haalt losse knoppen uit de bron (Registreer, Facebook, ...) uit een startadres."""
    t = re.split(r",?\s*(?:Registreer|Facebook|Website|Inschrijven|Inschrijving|Meer info)\b", str(t or ""), maxsplit=1, flags=re.I)[0]
    return t.strip(" ,;")


def veilige_url(u):
    u = str(u or "")
    return u if re.match(r"^https?://", u, re.I) else ""


def prijs_getallen(txt):
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", str(txt or ""))]


def laad_tochten():
    with open(os.path.join(MAP, "events.json"), encoding="utf-8") as f:
        data = json.load(f)
    lijst = data.get("events", []) if isinstance(data, dict) else data
    vandaag = datetime.date.today().isoformat()
    uit = []
    for e in lijst:
        if e.get("date") and e["date"] >= vandaag and e.get("title"):
            e = dict(e)
            if e.get("start"):
                e["start"] = schoon_adres(e["start"])
            uit.append(e)
    return uit, vandaag


def kies(tochten, types):
    """Selecteert op type en voegt dubbele varianten (zelfde dag, plaats en titel) samen."""
    groepen = {}
    for e in sorted(tochten, key=lambda x: (x["date"], str(x.get("location", "")).lower(), x["title"].lower())):
        if e.get("type", "") not in types:
            continue
        sleutel = (e["date"], str(e.get("location", "")).lower(), titelsleutel(e["title"]))
        g = groepen.get(sleutel)
        if g is None:
            groepen[sleutel] = dict(e, distances=list(e.get("distances") or []))
        else:
            for d in e.get("distances") or []:
                if d not in g["distances"]:
                    g["distances"].append(d)
            for k in ("price", "start", "organizer", "country"):
                if not g.get(k) and e.get(k):
                    g[k] = e[k]
    uit = list(groepen.values())
    for g in uit:
        g["distances"] = sorted(g["distances"])
    uit.sort(key=lambda x: (x["date"], str(x.get("location", "")).lower(), x["title"].lower()))
    return uit


CSS = """
:root{--bg:#020617;--tekst:#f1f5f9;--zacht:#94a3b8;--kaart:#0f172a;--rand:#1e293b;--groen:#34d399;--groen-d:#059669;--blauw:#7dd3fc}
@media (prefers-color-scheme: light){:root{}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tekst);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blauw)}
.wrap{max-width:900px;margin:0 auto;padding:24px 16px 48px}
header.top{display:flex;gap:16px;align-items:center;padding-bottom:20px;border-bottom:1px solid var(--rand);margin-bottom:20px}
header.top img{width:56px;height:56px;border-radius:14px;flex:none}
header.top .naam{font-size:1.5rem;font-weight:700;letter-spacing:-.01em;color:var(--tekst);text-decoration:none}
header.top .naam span{color:var(--groen)}
header.top p{margin:2px 0 0;color:var(--zacht);font-size:.9rem}
nav.keuze{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
nav.keuze a{padding:6px 14px;border-radius:10px;background:#1e293b;color:#cbd5e1;text-decoration:none;font-size:.9rem}
nav.keuze a.actief{background:var(--groen-d);color:#fff}
h1{font-size:1.75rem;line-height:1.2;margin:0 0 8px;letter-spacing:-.01em}
.intro{color:#cbd5e1;margin:0 0 16px}
.knop{display:inline-block;padding:10px 18px;border-radius:10px;background:var(--groen-d);color:#fff;text-decoration:none;font-weight:600;margin:0 0 8px}
.knop:hover{background:#047857}
h2.maand{font-size:1.15rem;margin:28px 0 4px;color:var(--groen)}
h2.maand::first-letter,h3.dag::first-letter{text-transform:uppercase}
h3.dag{font-size:.95rem;font-weight:600;margin:16px 0 8px;color:#cbd5e1}
article{background:var(--kaart);border:1px solid var(--rand);border-radius:14px;padding:14px 16px;margin:0 0 10px}
article h4{margin:6px 0 6px;font-size:1.05rem;line-height:1.3}
article .meta{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--zacht);font-size:.9rem}
article .meta b{color:#e2e8f0;font-weight:500}
.badge{display:inline-block;padding:1px 9px;border-radius:7px;background:#022c22;border:1px solid #065f46;color:#6ee7b7;font-size:.75rem;font-weight:600;margin-right:6px}
article .bron{margin-top:8px;font-size:.9rem}
footer{margin-top:40px;padding-top:20px;border-top:1px solid var(--rand);color:#64748b;font-size:.8rem}
footer p{margin:6px 0}
.leeg{color:var(--zacht);padding:20px 0}
""".strip()


def afstand_km(a, b):
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def provincie_uit_postcode(e):
    start = e.get("start") or ""
    land = e.get("country")
    m = re.search(r"\b(\d{4})\s?[A-Z]{2}\b", start)
    if m and land in ("NL", "", None):
        n, tabel = int(m.group(1)), NL_PC
    else:
        m = re.search(r"\b(\d{4})\b", start)
        if not m or land not in ("NL", "BE"):
            return None
        n, tabel = int(m.group(1)), (BE_PC if land == "BE" else NL_PC)
    for a, b, p in tabel:
        if a <= n <= b:
            return p
    return None


def deel_in(tochten):
    """Geeft per tocht-id de provinciesleutel. Eerst postcode, dan plaatsnaam, dan dichtstbijzijnde tocht (max 12 km)."""
    uit, referentie = {}, []
    for e in tochten:
        p = provincie_uit_postcode(e)
        if p:
            uit[e["id"]] = p
            if isinstance(e.get("lat"), (int, float)) and isinstance(e.get("lon"), (int, float)):
                referentie.append(((e["lat"], e["lon"]), p, GEBIEDEN[p][2]))
    for e in tochten:
        if e["id"] in uit:
            continue
        if e.get("location") in PLAATS_PROVINCIE:
            uit[e["id"]] = PLAATS_PROVINCIE[e["location"]]
            continue
        if isinstance(e.get("lat"), (int, float)) and isinstance(e.get("lon"), (int, float)):
            beste = None
            for pos, p, land in referentie:
                if e.get("country") and land != e["country"]:
                    continue
                d = afstand_km((e["lat"], e["lon"]), pos)
                if beste is None or d < beste[0]:
                    beste = (d, p)
            if beste and beste[0] <= 12:
                uit[e["id"]] = beste[1]
    return uit


def land_van(e, indeling):
    p = indeling.get(e["id"])
    if p:
        return GEBIEDEN[p][2]
    return e.get("country") if e.get("country") in LANDEN else None


def maak_pagina(spec, lijst, vandaag, regio_links, ander_link, indeling):
    """spec: {'pad','naam','filter','gebied':(weergavenaam, slug) of None}"""
    pad, naam, gebied = spec["pad"], spec["naam"], spec.get("gebied")
    n = len(lijst)
    nl = sum(1 for e in lijst if land_van(e, indeling) == "NL")
    be = sum(1 for e in lijst if land_van(e, indeling) == "BE")
    d0 = datetime.date.fromisoformat(vandaag)
    bijgewerkt = f"{d0.day} {MAANDEN[d0.month - 1]} {d0.year}"
    waar = gebied[0] if gebied else "Nederland en België"
    h1 = f"{naam} toertochten in {waar}"
    titel = f"{h1} – agenda {MAANDEN[d0.month - 1]} {d0.year}"
    if n:
        verdeling = f" ({nl} in Nederland, {be} in België)" if not gebied and (nl or be) else ""
        intro = (f"{n} {naam}-toertochten in {waar}, van {datum_nl(lijst[0]['date'])} tot en met {datum_nl(lijst[-1]['date'])}"
                 f"{verdeling}. Bijgewerkt op {bijgewerkt}.")
    else:
        intro = f"Er staan op dit moment geen {naam}-toertochten in de agenda. Bijgewerkt op {bijgewerkt}."
    beschrijving = f"Overzicht van {n} {naam}-toertochten in {waar} met datum, plaats, afstand en prijs. Bijgewerkt op {bijgewerkt}."
    canoniek = f"{SITE}/{pad}/"

    graph = []
    for e in lijst:
        plek = {"@type": "Place", "name": e.get("start") or e.get("location"),
                "address": {"@type": "PostalAddress", "addressLocality": e.get("location", "")}}
        if e.get("start"):
            plek["address"]["streetAddress"] = e["start"]
        lnd = land_van(e, indeling)
        if lnd:
            plek["address"]["addressCountry"] = lnd
        if isinstance(e.get("lat"), (int, float)) and isinstance(e.get("lon"), (int, float)):
            plek["geo"] = {"@type": "GeoCoordinates", "latitude": e["lat"], "longitude": e["lon"]}
        ev = {"@type": "Event", "name": e["title"], "startDate": e["date"],
              "eventStatus": "https://schema.org/EventScheduled",
              "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
              "location": plek, "image": f"{SITE}/icons/icon-512.png",
              "description": f"{naam}-toertocht in {e.get('location', '')} op {datum_nl(e['date'])}."
                             + (f" Afstanden: {', '.join(str(int(d) if float(d).is_integer() else d) for d in e['distances'])} km." if e["distances"] else "")}
        if veilige_url(e.get("sourceUrl")):
            ev["sameAs"] = e["sourceUrl"]
        if e.get("organizer"):
            ev["organizer"] = {"@type": "Organization", "name": e["organizer"]}
            if veilige_url(e.get("sourceUrl")):
                ev["organizer"]["url"] = e["sourceUrl"]
        pr = prijs_getallen(e.get("price"))
        if pr and veilige_url(e.get("sourceUrl")):
            ev["offers"] = {"@type": "Offer", "price": f"{min(pr):.2f}", "priceCurrency": "EUR", "url": e["sourceUrl"],
                            "availability": "https://schema.org/InStock"}
        graph.append(ev)
    kruimels = [{"@type": "ListItem", "position": 1, "name": "Kalender", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": f"{naam} toertochten", "item": f"{SITE}/{spec['type_pad']}/"}]
    if gebied:
        kruimels.append({"@type": "ListItem", "position": 3, "name": gebied[0], "item": canoniek})
    graph.append({"@type": "BreadcrumbList", "itemListElement": kruimels})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")

    delen = []
    huidige_maand = huidige_dag = None
    for e in lijst:
        d = datetime.date.fromisoformat(e["date"])
        maand = f"{MAANDEN[d.month - 1]} {d.year}"
        if maand != huidige_maand:
            delen.append(f'<h2 class="maand">{esc(maand)}</h2>')
            huidige_maand, huidige_dag = maand, None
        if e["date"] != huidige_dag:
            delen.append(f'<h3 class="dag" data-datum="{e["date"]}">{esc(datum_nl(e["date"]))}</h3>')
            huidige_dag = e["date"]
        badges = ("<span class=\"badge\">MTB</span><span class=\"badge\">Gravel</span>" if e.get("type") == "Both"
                  else f'<span class="badge">{esc(e.get("type", ""))}</span>')
        lnd = land_van(e, indeling)
        meta = [f'<span><b>{esc(e.get("location", ""))}</b>' + (f", {esc(LANDEN[lnd])}" if lnd else "") + "</span>"]
        if e["distances"]:
            meta.append("<span>" + " · ".join(str(int(x) if float(x).is_integer() else x) for x in e["distances"]) + " km</span>")
        if e.get("price"):
            meta.append(f'<span>{esc(e["price"])}</span>')
        if e.get("organizer"):
            meta.append(f'<span>{esc(e["organizer"])}</span>')
        if e.get("start"):
            meta.append(f'<span>Start: {esc(e["start"])}</span>')
        bron = (f'<div class="bron"><a href="{esc(e["sourceUrl"])}" target="_blank" rel="noopener">Meer informatie en inschrijven</a></div>'
                if veilige_url(e.get("sourceUrl")) else "")
        delen.append(f'<article data-datum="{e["date"]}">{badges}<h4>{esc(e["title"])}</h4><div class="meta">{"".join(meta)}</div>{bron}</article>')
    lijst_html = "\n".join(delen) if delen else '<p class="leeg">Geen tochten gevonden.</p>'

    regio_html = ""
    if regio_links:
        links = " · ".join(f'<a href="/{p}/"' + (' aria-current="page"' if p == pad else "") + f'>{esc(t)}</a>' for p, t in regio_links)
        regio_html = f'<p class="regios"><b>{esc(naam)} per regio:</b> {links}</p>'
    ander_html = (f' · <a href="/{ander_link[0]}/">{esc(ander_link[1])}</a>' if ander_link else "")
    tp = spec["type_pad"]

    pagina = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titel)}</title>
<meta name="description" content="{esc(beschrijving)}">
<link rel="canonical" href="{canoniek}">
<meta property="og:type" content="website">
<meta property="og:locale" content="nl_NL">
<meta property="og:title" content="{esc(h1)}">
<meta property="og:description" content="{esc(beschrijving)}">
<meta property="og:url" content="{canoniek}">
<meta property="og:image" content="{SITE}/icons/icon-512.png">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#14532d">
<link rel="icon" type="image/png" href="/icons/icon-192.png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<style>{CSS}</style>
<script type="application/ld+json">{ld}</script>
</head>
<body>
<div class="wrap">
<header class="top">
<a href="/"><img src="/icons/icon-192.png" alt="" width="56" height="56"></a>
<div><a class="naam" href="/">MTB <span>&amp;</span> Gravel Kalender</a><p>Alle MTB- en gravel-toertochten in Nederland, België en omgeving op één plek</p></div>
</header>
<nav class="keuze" aria-label="Soort tochten">
<a href="/">Alle tochten</a>
<a href="/gravel/"{' class="actief" aria-current="page"' if tp == 'gravel' else ''}>Gravel</a>
<a href="/mtb/"{' class="actief" aria-current="page"' if tp == 'mtb' else ''}>MTB</a>
</nav>
<main>
<h1>{esc(h1)}</h1>
<p class="intro">{esc(intro)}</p>
<a class="knop" href="/?type={esc(spec['filter'])}">Open de kalender met afstand, kaart en weer</a>
{regio_html}
<div id="lijst">
{lijst_html}
</div>
</main>
<footer>
<p>Deze lijst is automatisch samengesteld uit openbare bronnen en kan afwijken van de actuele gegevens. Controleer datum, afstand en prijs altijd op de website van de organisator.</p>
<p>Ook bekijken: <a href="/">alle tochten met filters, kaart en weerbericht</a>{ander_html}.</p>
</footer>
</div>
<script>
(function () {{
  var d = new Date(), t = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  document.querySelectorAll('article[data-datum], h3[data-datum]').forEach(function (el) {{ if (el.getAttribute('data-datum') < t) el.style.display = 'none'; }});
  document.querySelectorAll('h2.maand').forEach(function (h) {{
    var n = h.nextElementSibling, zichtbaar = false;
    while (n && n.tagName !== 'H2') {{ if (n.tagName === 'ARTICLE' && n.style.display !== 'none') zichtbaar = true; n = n.nextElementSibling; }}
    if (!zichtbaar) h.style.display = 'none';
  }});
}})();
</script>
</body>
</html>
"""
    doel = os.path.join(UIT, *pad.split("/"))
    os.makedirs(doel, exist_ok=True)
    with open(os.path.join(doel, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)
    return n


UIT = MAP


def schrijf_sitemap(vandaag, paden):
    regels = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, prio in [("/", "1.0")] + [("/" + p + "/", "0.8" if p.count("/") == 0 else "0.6") for p in paden]:
        regels += ["  <url>", f"    <loc>{SITE}{u}</loc>", f"    <lastmod>{vandaag}</lastmod>",
                   "    <changefreq>weekly</changefreq>", f"    <priority>{prio}</priority>", "  </url>"]
    regels.append("</urlset>")
    with open(os.path.join(UIT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(regels) + "\n")


def main():
    global UIT
    try:
        if len(sys.argv) > 1:
            UIT = os.path.abspath(sys.argv[1])
        tochten, vandaag = laad_tochten()
        if len(tochten) < 50:
            print("Te weinig tochten in events.json; pagina's worden niet vernieuwd.")
            return 1
        indeling = deel_in(tochten)
        onbekend = [e for e in tochten if e["id"] not in indeling]
        if onbekend:
            print("Niet ingedeeld (komen wel op de landen-pagina's als het land bekend is):", sorted({e.get("location", "?") for e in onbekend}))
        gemaakt = []
        for t in TYPES:
            basis = kies(tochten, t["types"])
            # welke gebieden komen in aanmerking
            gebieden = {}
            for e in basis:
                for sleutel in {land_van(e, indeling), indeling.get(e["id"])} - {None}:
                    gebieden.setdefault(sleutel, []).append(e)
            keuzes = []
            for sleutel, items in gebieden.items():
                slug = GEBIEDEN[sleutel][1]
                bestaat = os.path.exists(os.path.join(UIT, t["pad"], slug, "index.html"))
                if len(items) >= MIN_REGIO or bestaat:
                    keuzes.append((sleutel, items))
            # volgorde: landen eerst, dan op aantal
            keuzes.sort(key=lambda k: (k[0] not in ("NL", "BE"), -len(k[1])))
            regio_links = [(f"{t['pad']}/{GEBIEDEN[k][1]}", GEBIEDEN[k][0]) for k, _ in keuzes]
            spec = {"pad": t["pad"], "type_pad": t["pad"], "naam": t["naam"], "filter": t["filter"], "gebied": None}
            n = maak_pagina(spec, basis, vandaag, regio_links, (("mtb" if t["pad"] == "gravel" else "gravel"), ("MTB toertochten" if t["pad"] == "gravel" else "Gravel toertochten")), indeling)
            print(f"{t['pad']}/: {n} tochten")
            gemaakt.append(t["pad"])
            for sleutel, items in keuzes:
                naam_g, slug, _ = GEBIEDEN[sleutel]
                pad = f"{t['pad']}/{slug}"
                andere_pad = f"{'mtb' if t['pad'] == 'gravel' else 'gravel'}/{slug}"
                ander = (andere_pad, f"{'MTB' if t['pad'] == 'gravel' else 'Gravel'} tochten in {naam_g}") if os.path.exists(os.path.join(UIT, andere_pad, "index.html")) or True else None
                spec = {"pad": pad, "type_pad": t["pad"], "naam": t["naam"], "filter": t["filter"], "gebied": (naam_g, slug)}
                m = maak_pagina(spec, sorted(items, key=lambda x: (x["date"], str(x.get("location", "")).lower(), x["title"].lower())), vandaag, regio_links, None, indeling)
                print(f"  {pad}/: {m} tochten")
                gemaakt.append(pad)
        # 'andere type in deze regio'-links alleen laten staan als die pagina echt bestaat: opschonen
        for pad in gemaakt:
            if pad.count("/") == 1:
                t, slug = pad.split("/")
                tegen = ("mtb" if t == "gravel" else "gravel") + "/" + slug
                bestand = os.path.join(UIT, *pad.split("/"), "index.html")
                with open(bestand, encoding="utf-8") as f:
                    tekst = f.read()
                if tegen in gemaakt:
                    naam_g = next(v[0] for v in GEBIEDEN.values() if v[1] == slug)
                    tekst = tekst.replace("</a>.</p>\n</footer>", f'</a> · <a href="/{tegen}/">{"MTB" if t == "gravel" else "Gravel"} toertochten in {naam_g}</a>.</p>\n</footer>', 1)
                    with open(bestand, "w", encoding="utf-8") as f:
                        f.write(tekst)
        schrijf_sitemap(vandaag, gemaakt)
        print(f"sitemap.xml vernieuwd ({len(gemaakt) + 1} adressen)")
        return 0
    except Exception as e:  # noqa: BLE001
        print("Pagina's maken mislukt:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
