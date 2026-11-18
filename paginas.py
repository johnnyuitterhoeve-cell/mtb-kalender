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

PAGINAS = [
    {"pad": "gravel", "types": {"Gravel", "Both"}, "naam": "Gravel", "filter": "Gravel",
     "andere": ("mtb", "MTB")},
    {"pad": "mtb", "types": {"MTB", "Both"}, "naam": "MTB", "filter": "MTB",
     "andere": ("gravel", "Gravel")},
]

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


def maak_pagina(p, tochten, vandaag, alle_aantallen):
    pad, naam = p["pad"], p["naam"]
    lijst = kies(tochten, p["types"])
    n = len(lijst)
    nl = sum(1 for e in lijst if e.get("country") == "NL")
    be = sum(1 for e in lijst if e.get("country") == "BE")
    d0 = datetime.date.fromisoformat(vandaag)
    bijgewerkt = f"{d0.day} {MAANDEN[d0.month - 1]} {d0.year}"
    titel = f"{naam} toertochten in Nederland en België – agenda {MAANDEN[d0.month - 1]} {d0.year}"
    if n:
        eind = datum_nl(lijst[-1]["date"])
        intro = (f"{n} {naam}-toertochten in Nederland en België, van {datum_nl(lijst[0]['date'])} tot en met {eind}"
                 f" ({nl} in Nederland, {be} in België). Bijgewerkt op {bijgewerkt}.")
    else:
        intro = f"Er staan op dit moment geen {naam}-toertochten in de agenda. Bijgewerkt op {bijgewerkt}."
    beschrijving = f"Overzicht van {n} {naam}-toertochten in Nederland en België met datum, plaats, afstand en prijs. Bijgewerkt op {bijgewerkt}."

    # JSON-LD
    graph = []
    for e in lijst:
        plek = {"@type": "Place", "name": e.get("start") or e.get("location"),
                "address": {"@type": "PostalAddress", "addressLocality": e.get("location", "")}}
        if e.get("start"):
            plek["address"]["streetAddress"] = e["start"]
        if e.get("country") in LANDEN:
            plek["address"]["addressCountry"] = e["country"]
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
        pr = prijs_getallen(e.get("price"))
        if pr and veilige_url(e.get("sourceUrl")):
            ev["offers"] = {"@type": "Offer", "price": f"{min(pr):.2f}", "priceCurrency": "EUR", "url": e["sourceUrl"],
                            "availability": "https://schema.org/InStock"}
        graph.append(ev)
    graph.append({"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Kalender", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": f"{naam} toertochten", "item": f"{SITE}/{pad}/"}]})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")

    # lijst in HTML
    delen = []
    huidige_maand = huidige_dag = None
    for e in lijst:
        d = datetime.date.fromisoformat(e["date"])
        maand = f"{MAANDEN[d.month - 1]} {d.year}"
        if maand != huidige_maand:
            delen.append(f'<h2 class="maand" data-maand="{d.year}-{d.month:02d}">{esc(maand)}</h2>')
            huidige_maand, huidige_dag = maand, None
        if e["date"] != huidige_dag:
            delen.append(f'<h3 class="dag" data-datum="{e["date"]}">{esc(datum_nl(e["date"]))}</h3>')
            huidige_dag = e["date"]
        badges = ("<span class=\"badge\">MTB</span><span class=\"badge\">Gravel</span>" if e.get("type") == "Both"
                  else f'<span class="badge">{esc(e.get("type", ""))}</span>')
        meta = [f'<span><b>{esc(e.get("location", ""))}</b>' + (f", {esc(LANDEN[e['country']])}" if e.get("country") in LANDEN else "") + "</span>"]
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

    a_pad, a_naam = p["andere"]
    pagina = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titel)}</title>
<meta name="description" content="{esc(beschrijving)}">
<link rel="canonical" href="{SITE}/{pad}/">
<meta property="og:type" content="website">
<meta property="og:locale" content="nl_NL">
<meta property="og:title" content="{esc(naam)} toertochten in Nederland en België">
<meta property="og:description" content="{esc(beschrijving)}">
<meta property="og:url" content="{SITE}/{pad}/">
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
<a href="/gravel/"{' class="actief" aria-current="page"' if pad == 'gravel' else ''}>Gravel</a>
<a href="/mtb/"{' class="actief" aria-current="page"' if pad == 'mtb' else ''}>MTB</a>
</nav>
<main>
<h1>{esc(naam)} toertochten in Nederland en België</h1>
<p class="intro">{esc(intro)}</p>
<a class="knop" href="/?type={esc(p['filter'])}">Open de kalender met afstand, kaart en weer</a>
<div id="lijst">
{lijst_html}
</div>
</main>
<footer>
<p>Deze lijst is automatisch samengesteld uit openbare bronnen en kan afwijken van de actuele gegevens. Controleer datum, afstand en prijs altijd op de website van de organisator.</p>
<p>Ook bekijken: <a href="/{a_pad}/">{esc(a_naam)} toertochten</a> · <a href="/">alle tochten met filters, kaart en weerbericht</a>.</p>
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
    os.makedirs(os.path.join(MAP, pad), exist_ok=True)
    with open(os.path.join(MAP, pad, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)
    return n


def schrijf_sitemap(vandaag):
    urls = [("/", "weekly", "1.0"), ("/gravel/", "weekly", "0.8"), ("/mtb/", "weekly", "0.8")]
    regels = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, freq, prio in urls:
        regels += ["  <url>", f"    <loc>{SITE}{u}</loc>", f"    <lastmod>{vandaag}</lastmod>",
                   f"    <changefreq>{freq}</changefreq>", f"    <priority>{prio}</priority>", "  </url>"]
    regels.append("</urlset>")
    with open(os.path.join(MAP, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(regels) + "\n")


def main():
    try:
        tochten, vandaag = laad_tochten()
        if len(tochten) < 50:
            print("Te weinig tochten in events.json; pagina's worden niet vernieuwd.")
            return 1
        for p in PAGINAS:
            n = maak_pagina(p, tochten, vandaag, None)
            print(f"{p['pad']}/index.html: {n} tochten")
        schrijf_sitemap(vandaag)
        print("sitemap.xml vernieuwd")
        return 0
    except Exception as e:  # noqa: BLE001
        print("Pagina's maken mislukt:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
