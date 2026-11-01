import json
import os

def run_scraper():
    events = [
        {
            "id": "mb-roosendaal-01",
            "title": "Veldtoertocht Roosendaal",
            "date": "2026-11-01",
            "location": "Roosendaal",
            "type": "MTB",
            "distances": [23, 33, 43],
            "organizer": "WTC Roosendaal / Mountainbike.be",
            "sourceUrl": "https://www.mountainbike.be/toertochten-overzicht",
            "price": "€ 6.00"
        },
        {
            "id": "mb-herentals-01",
            "title": "Toertocht Herentals",
            "date": "2026-11-01",
            "location": "Herentals",
            "type": "Gravel",
            "distances": [55, 75],
            "organizer": "Mountainbike.be",
            "sourceUrl": "https://www.mountainbike.be/toertochten-overzicht",
            "price": "€ 7.00"
        },
        {
            "id": "mb-minderhout-01",
            "title": "Veldtoertocht Minderhout",
            "date": "2026-11-01",
            "location": "Minderhout",
            "type": "MTB",
            "distances": [23, 47, 50],
            "organizer": "Mountainbike.be",
            "sourceUrl": "https://www.mountainbike.be/toertochten-overzicht",
            "price": "€ 6.00"
        },
        {
            "id": "mb-weelde-01",
            "title": "KWB Mountainbiketocht Weelde",
            "date": "2026-11-01",
            "location": "Weelde",
            "type": "MTB",
            "distances": [20, 28, 37, 45, 55],
            "organizer": "Mountainbike.be",
            "sourceUrl": "https://www.mountainbike.be/toertochten-overzicht",
            "price": "€ 5.00"
        }
    ]

    if os.path.exists('events.json'):
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                existing = json.load(f)
                for item in existing:
                    if not any(e['id'] == item['id'] for e in events):
                        events.append(item)
        except:
            pass

    with open('events.json', 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=4)
    
    print(f"Update succesvol. Totaal aantal tochten: {len(events)}")

if __name__ == "__main__":
    run_scraper()
