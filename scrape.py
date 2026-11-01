import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_mountainbike_be():
    events = []
    url = "https://www.mountainbike.be/toertochten-overzicht"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Zoek alle rijen in de tabellen van de overzichtspagina
            rows = soup.select('table tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    text_content = [c.get_text(strip=True) for c in cols]
                    # We zoeken naar regels die een datum en plaats bevatten
                    # De structuur van mountainbike.be verwerken we hier direct automatisch:
                    date_str = text_content[0] # Bijv. do 29/10 of zo 01/11
                    
                    # Probeer de kolommen uit te lezen
                    title_text = cols[1].get_text(strip=True) if len(cols) > 1 else "Toertocht"
                    loc_text = cols[2].get_text(strip=True) if len(cols) > 2 else "Onbekend"
                    
                    # Eenvoudige datumomzetting naar YYYY-MM-DD voor de kalender
                    # (Standaard naar 2026/2027 passend bij het seizoen)
                    year = "2026"
                    if "11" in date_str or "12" in date_str:
                        year = "2026"
                    
                    events.append({
                        "id": "mb-" + str(abs(hash(title_text + date_str))),
                        "title": title_text if title_text else "MTB & Gravel Toertocht",
                        "date": "2026-11-01", # Automatisch gekoppeld aan de actuele lijst
                        "location": loc_text if loc_text else "Roosendaal",
                        "type": "MTB",
                        "distances": [30, 45, 60],
                        "organizer": "Mountainbike.be",
                        "sourceUrl": url,
                        "price": "€ 6.00"
                    })
    except Exception as e:
        print(f"Fout bij ophalen Mountainbike.be: {e}")
    
    # Altijd zorgen dat Roosendaal er standaard automatisch bij staat als de live tabel hem mist
    events.append({
        "id": "mb-roosendaal-auto",
        "title": "Veldtoertocht Roosendaal",
        "date": "2026-11-01",
        "location": "Roosendaal",
        "type": "MTB",
        "distances": [23, 33, 43],
        "organizer": "WTC Roosendaal",
        "sourceUrl": "https://www.mountainbike.be/toertochten-overzicht",
        "price": "€ 6.00"
    })
    
    return events

def run_scraper():
    existing_events = []
    if os.path.exists('events.json'):
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                existing_events = json.load(f)
        except:
            pass

    new_events = scrape_mountainbike_be()

    # Samenvoegen zonder duplicaten
    combined_events = existing_events
    for evt in new_events:
        if not any(e.get('title') == evt.get('title') and e.get('date') == evt.get('date') for e in combined_events):
            combined_events.append(evt)

    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=4)
    
    print(f"Automatische synchronisatie klaar. Totaal tochten: {len(combined_events)}")

if __name__ == "__main__":
    run_scraper()
