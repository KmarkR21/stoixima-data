#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Τρέχει μέσα στο GitHub Action. Αντλεί αγώνες από το football-data.org (v4) για
τις 8 λίγκες και τα αποθηκεύει σε data/<slug>.json με ΤΗΝ ΙΔΙΑ δομή που ήδη
χρησιμοποιεί το stoixima_report.py (ώστε να μη χρειάζεται καμία άλλη αλλαγή
εκεί, μόνο το URL της πηγής):
    {"matches": [{"team1":..,"team2":..,"date":"YYYY-MM-DD","time":"HH:MM",
                  "score": {"ft": [home, away]}  # μόνο αν έχει τελειώσει
                 }, ...]}
"""

import os
import json
import time
import urllib.request
import urllib.error
from datetime import date, datetime

TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]


def current_season_year():
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


SEASON = os.environ.get("SEASON") or str(current_season_year())

# (κωδικός football-data.org, slug συμβατό με το stoixima_report.py)
COMPETITIONS = [
    ("PL", "en.1"),
    ("ELC", "en.2"),
    ("PD", "es.1"),
    ("BL1", "de.1"),
    ("SA", "it.1"),
    ("FL1", "fr.1"),
    ("DED", "nl.1"),
    ("PPL", "pt.1"),
]


def fetch(code, season):
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?season={season}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def convert(raw):
    out = []
    for m in raw.get("matches", []):
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if not home or not away:
            continue
        utc = m.get("utcDate") or ""
        d = utc[:10] if len(utc) >= 10 else None
        t = utc[11:16] if len(utc) >= 16 else None
        row = {"team1": home, "team2": away, "date": d, "time": t}
        status = m.get("status")
        score = (m.get("score") or {}).get("fullTime") or {}
        h, a = score.get("home"), score.get("away")
        if status == "FINISHED" and h is not None and a is not None:
            row["score"] = {"ft": [h, a]}
        out.append(row)
    return {"matches": out}


def main():
    os.makedirs("data", exist_ok=True)
    errors = []
    summary = []
    for code, slug in COMPETITIONS:
        try:
            raw = fetch(code, SEASON)
            converted = convert(raw)
            with open(f"data/{slug}.json", "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)
            n = len(converted["matches"])
            finished = sum(1 for m in converted["matches"] if "score" in m)
            summary.append(f"{slug}: {n} αγώνες ({finished} με σκορ)")
            print(f"OK {slug}: {n} matches, {finished} finished")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            errors.append(f"{slug}: HTTP {e.code} {body[:200]}")
            print(f"ERROR {slug}: HTTP {e.code} {body[:200]}")
        except Exception as e:
            errors.append(f"{slug}: {e}")
            print(f"ERROR {slug}: {e}")
        time.sleep(7)  # μένουμε καλά κάτω από το όριο 10 requests/min

    with open("data/_status.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_run_utc": datetime.utcnow().isoformat() + "Z",
            "season": SEASON,
            "summary": summary,
            "errors": errors,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
