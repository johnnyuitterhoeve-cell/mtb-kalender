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
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Hier worden de tabellen van Mountainbike.be uitgelezen
            rows = soup.select('table tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    # Logica voor parsen kolommen (datum, plaats, type, etc.)
                    pass
    except Exception as e:
        print(f"Fout bij ophalen Mountainbike.be: {e}")
    return events

def scrape_fietssport_nl():
    events = []
    url = "https://fietssport.nl/tochten"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Logica voor Fietssport.nl kaarten/lijsten
    except Exception as e:
        print(f"Fout bij ophalen Fietssport.nl: {e}")
    return events

def scrape_mtb_you():
    events = []
    # Logica voor MTB-You
    return events

def scrape_godare():
    events = []
    # Logica voor GoDare
    return events

def scrape_gravelbike():
    events = []
    # Logica voor GravelBike.be
    return events

def run_scraper():
    # 1. Bestaande events inladen (zodat handmatige toevoegingen behouden blijven)
    existing_events = []
    if os.path.exists('events.json'):
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                existing_events = json.load(f)
        except:
            pass

    # 2. Tochten ophalen van alle gekozen platforms
    new_events = []
    new_events.extend(scrape_mountainbike_be())
    new_events.extend(scrape_fietssport_nl())
    new_events.extend(scrape_mtb_you())
    new_events.extend(scrape_godare())
    new_events.extend(scrape_gravelbike())

    # 3. Samenvoegen zonder dubbele tochten
    combined_events = existing_events
    for evt in new_events:
        if not any(e.get('title') == evt.get('title') and e.get('date') == evt.get('date') for e in combined_events):
            combined_events.append(evt)

    # 4. Opslaan naar events.json
    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=4)
    
    print(f"Synchronisatie voltooid. Totaal aantal tochten in database: {len(combined_events)}")

if __name__ == "__main__":
    run_scraper()
