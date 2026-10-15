"""Liest Termine und Kontaktdaten von schaetzelberg-gs.de und schreibt data/website.json.

Schlägt das Parsen fehl (Seite umgebaut, nicht erreichbar, keine Termine gefunden),
bleiben die alten Daten erhalten und status.json markiert die Quelle als veraltet.
"""
import html
import re
import sys
from datetime import date, datetime

from common import BERLIN, fetch, load_json, now_iso, save_json, write_status

BASE = "https://schaetzelberg-gs.de"


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def infer_year(day, month, today):
    """Für Daten ohne Jahr (z. B. „19.11.“): nächstes Vorkommen, max. ~2 Monate zurück."""
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if (today - d).days > 60:
        year += 1
    elif (d - today).days > 300:
        year -= 1
    return year


def parse_events(page, today):
    events = []
    for item in re.findall(r'<div class="sel-event-item">(.*?)</div>', page, re.S):
        m_date = re.search(r'class="sel-event-date"[^>]*>(.*?)</span>', item, re.S)
        m_title = re.search(r'class="sel-event-title[^"]*"[^>]*>(.*?)</(?:a|span)>', item, re.S)
        if not m_date or not m_title:
            continue
        raw_date = text(m_date.group(1)).rstrip(":").strip()
        title = text(m_title.group(1))
        link = re.search(r'<a[^>]+href="([^"]+)"', item)

        m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?\s*(?:\|\s*(.*))?$", raw_date)
        iso, time_txt = None, None
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            year = m.group(3)
            if year:
                year = int(year) + (2000 if len(year) == 2 else 0)
            else:
                year = infer_year(day, month, today)
            try:
                iso = date(year, month, day).isoformat()
            except (TypeError, ValueError):
                iso = None
            time_txt = (m.group(4) or "").strip() or None
        events.append(
            {
                "date": iso,
                "date_text": raw_date,
                "time": time_txt,
                "title": title,
                "url": html.unescape(link.group(1)) if link else None,
            }
        )
    return events


def parse_header_contact(page):
    tel = re.search(r"Tel:?\s*([0-9 /+()-]{6,})", text(page))
    mails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@schaetzelberg[A-Za-z0-9.-]*\.de", page)))
    sekretariat = next((m for m in mails if m.lower().startswith("sekretariat")), None)
    krank = next((m for m in mails if m.lower().startswith("krankmeldung")), None)
    return {
        "phone": tel.group(1).strip() if tel else None,
        "email": sekretariat,
        "sick_email": krank,
    }


def parse_people(url):
    """Liest Seiten im Muster „Rolle / Name / E-Mail: …“ (Schulleitung, SpB-Leitung)."""
    page = fetch(url)
    body = re.search(r"<main.*?</main>", page, re.S)
    body = body.group(0) if body else page
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)
    lines = [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", body)).splitlines() if l.strip()]
    people = []
    for i, line in enumerate(lines):
        m = re.match(r"E-?Mail:?\s*(\S+@\S+)", line, re.I)
        # Seitenkopf („Tel: … / EMail: sekretariat@…“) überspringen
        if m and i >= 2 and not re.match(r"Tel", lines[i - 1], re.I):
            people.append({"role": lines[i - 2], "name": lines[i - 1], "email": m.group(1)})
    return people


def main():
    today = datetime.now(BERLIN).date()
    old = load_json("website.json") or {}
    try:
        home = fetch(BASE + "/")
        if "sel-events-list" not in home:
            raise RuntimeError("Terminliste auf der Startseite nicht gefunden – Seitenstruktur geändert?")
        events = parse_events(home, today)  # leere Liste ist gültig (z. B. in den Ferien)
        contact = parse_header_contact(home)
        if not contact["phone"] and not contact["email"]:
            raise RuntimeError("Keine Kontaktdaten im Seitenkopf gefunden")
    except Exception as e:
        print("Website-Abruf fehlgeschlagen – behalte alte Daten:", e, file=sys.stderr)
        write_status("website", False, e)
        return 1

    groups = []
    for label, path in (("Schulleitung", "/schule/schulleitung/"), ("Schulbezogene Betreuung (SpB)", "/spb/teamleitung/")):
        try:
            people = parse_people(BASE + path)
        except Exception as e:
            print("Konnte %s nicht lesen: %s" % (path, e), file=sys.stderr)
            people = None
        if not people:  # einzelne Unterseite kaputt → alten Stand dieser Gruppe behalten
            people = next((g["people"] for g in old.get("contact_groups", []) if g["label"] == label), [])
        groups.append({"label": label, "url": BASE + path, "people": people})

    data = {
        "site_url": BASE,
        "contact": contact,
        "contact_groups": groups,
        "events": events,
        "content_changed_at": now_iso(),
    }
    if old.get("content_changed_at") and all(old.get(k) == v for k, v in data.items() if k != "content_changed_at"):
        data["content_changed_at"] = old["content_changed_at"]

    changed = save_json("website.json", data)
    write_status("website", True)
    print("Website: %d Termine, %s" % (len(events), "GEÄNDERT" if changed else "unverändert"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
