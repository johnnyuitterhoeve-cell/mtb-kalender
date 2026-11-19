"""Stuurt na de wekelijkse update een mailtje met de status van de bronnen.

Gebruik:
  python3 melding.py            -> weekrapport (na een geslaagde update)
  python3 melding.py fout "tekst" -> melding dat er iets misging

De mailgegevens staan NIET in GitHub, maar alleen op de Pi in ~/.mtb_mail.conf:
  [mail]
  server = smtp.gmail.com
  poort = 587
  gebruiker = jouwadres@gmail.com
  wachtwoord = app-wachtwoord-van-16-letters
  naar = webbeheer@tcarendskerke.nl
Ontbreekt dat bestand, dan doet dit script niets (en breekt de update nooit).
"""
import configparser
import datetime
import json
import os
import smtplib
import subprocess
import sys
from email.message import EmailMessage

MAP = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.expanduser("~/.mtb_mail.conf")


def vorige_bronnen():
    """Bronnen van de vorige keer, uit de git-geschiedenis (mislukt dat: geen vergelijking)."""
    try:
        hashes = subprocess.run(["git", "log", "-2", "--format=%H", "--", "sources.json"], cwd=MAP,
                                capture_output=True, text=True, timeout=20).stdout.split()
        if len(hashes) < 2:
            return {}
        tekst = subprocess.run(["git", "show", hashes[1] + ":sources.json"], cwd=MAP,
                               capture_output=True, text=True, timeout=20).stdout
        return {s["name"]: s for s in json.loads(tekst).get("sources", [])}
    except Exception:  # noqa: BLE001
        return {}


def rapport():
    with open(os.path.join(MAP, "sources.json"), encoding="utf-8") as f:
        bronnen = json.load(f).get("sources", [])
    with open(os.path.join(MAP, "events.json"), encoding="utf-8") as f:
        totaal = len(json.load(f))
    eerder = vorige_bronnen()
    regels, problemen = [], []
    for s in bronnen:
        naam, status, aantal = s.get("name", "?"), s.get("status"), s.get("count", 0)
        vorig = eerder.get(naam, {}).get("count")
        verschil = f" (vorige keer {vorig})" if vorig is not None and vorig != aantal else ""
        if status == "ok":
            teken = "OK     "
            if vorig and aantal < vorig * 0.7:
                teken = "LET OP "
                problemen.append(f"{naam}: veel minder tochten dan vorige keer ({aantal} i.p.v. {vorig})")
            regels.append(f"{teken}{naam}: {aantal} tochten{verschil}")
        else:
            reden = s.get("message") or status
            problemen.append(f"{naam}: {reden}")
            regels.append(f"FOUT   {naam}: {aantal} oude tochten ({reden})")
    nu = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    if problemen:
        onderwerp = f"MTB-kalender: let op, {len(problemen)} probleem{'en' if len(problemen) > 1 else ''}"
        kop = "Er is iets om naar te kijken:\n- " + "\n- ".join(problemen)
    else:
        onderwerp = "MTB-kalender: alles in orde"
        kop = "Alle bronnen werken."
    tekst = (f"{kop}\n\nStatus op {nu}\nTotaal in de kalender: {totaal} tochten\n\n" + "\n".join(regels) +
             "\n\nBekijk de site: https://toertochtenkalender.nl\n")
    return onderwerp, tekst


def stuur(onderwerp, tekst):
    cfg = configparser.ConfigParser()
    if not cfg.read(CONF, encoding="utf-8") or "mail" not in cfg:
        print("Geen mailgegevens gevonden (~/.mtb_mail.conf); geen mail verstuurd.")
        return
    m = cfg["mail"]
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = onderwerp, m["gebruiker"], m["naar"]
    msg.set_content(tekst)
    with smtplib.SMTP(m.get("server", "smtp.gmail.com"), int(m.get("poort", "587")), timeout=30) as s:
        s.starttls()
        s.login(m["gebruiker"], m["wachtwoord"])
        s.send_message(msg)
    print("Mail verstuurd naar", m["naar"])


def main():
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "fout":
            stuur("MTB-kalender: de update is mislukt", (sys.argv[2] if len(sys.argv) > 2 else "Onbekende fout") +
                  "\n\nDe oude gegevens blijven op de site staan. Log in op de Pi en draai ./update_pi.sh om de foutmelding te zien.\n")
        else:
            stuur(*rapport())
    except Exception as e:  # noqa: BLE001
        print("Mail versturen mislukt:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
