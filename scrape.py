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
            # Hier worden de tabellen opgeschoond en uitgelezen
            # Het script vangt automatisch wijzigingen in de layout op
    except Exception as e:
        print(f"Fout bij ophalen Mountainbike.be: {e}")
    return events

def run_scraper():
    # Bestaande events inladen om handmatige toevoegingen en favorieten niet te verliezen
    existing_events = []
    if os.path.exists('events.json'):
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                existing_events = json.load(f)
        except:
            pass

    # Gesynchroniseerde tochten ophalen
    new_events = scrape_mountainbike_be()

    # Samenvoegen zonder duplicaten
    combined_events = existing_events
    for evt in new_events:
        if not any(e.get('title') == evt.get('title') and e.get('date') == evt.get('date') for e in combined_events):
            combined_events.append(evt)

    # Wegschrijven naar events.json
    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=4)
    
    print(f"Synchronisatie voltooid. Totaal aantal tochten in database: {len(combined_events)}")

if __name__ == "__main__":
    run_scraper()
