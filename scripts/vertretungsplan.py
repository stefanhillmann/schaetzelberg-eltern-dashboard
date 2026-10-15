"""Liest Vertretungsplan-PDFs aus dem Padlet („Ausfall der Randstunden“).

Benötigt das Kommandozeilenwerkzeug `pdftotext` (poppler). Fehlt es oder lässt sich
das PDF nicht lesen, wird None zurückgegeben – das Dashboard verlinkt dann nur den Beitrag.
"""
import re
import shutil
import subprocess
import tempfile
import urllib.request

from common import USER_AGENT

DATE_RE = re.compile(r"(Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
# Stunde (z. B. „1./2.“, „ab 3.St.“, „5.+6.“), Klasse (z. B. „4b“, „3a/3b“, „alle“), Info
ROW_RE = re.compile(
    r"^\s*(?P<stunde>(?:ab\s*)?\d[\d.\s/+\-–]*(?:\s*St\.?)?)\s{2,}"
    r"(?P<klasse>(?:\d[a-zA-Z]?(?:\s*[/,+&]\s*\d?[a-zA-Z])*|alle|Alle|JÜL\S*))\s{2,}"
    r"(?P<info>\S.*)$"
)
NOTES_RE = re.compile(r"^\s*Aktuelles", re.I)
BULLET_RE = re.compile(r"^\s*[•●▪\-–]\s*(.*)$")


def pdf_bytes_to_text(data):
    if not shutil.which("pdftotext") or not data.startswith(b"%PDF"):
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", f.name, "-"], capture_output=True, timeout=60)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def pdf_to_text(url):
    if not shutil.which("pdftotext"):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return pdf_bytes_to_text(resp.read())


def parse(text):
    """Zerlegt den Text in Datum, Zeilen (Stunde/Klasse/Info) und Hinweise."""
    if not text or not text.strip():
        return None
    lines = text.replace("\f", "\n").splitlines()
    plan = {"title": None, "date": None, "weekday": None, "rows": [], "notes": []}

    first = next((l for l in lines if l.strip()), "")
    plan["title"] = re.split(r"\s{2,}", first.strip())[0] or None
    m = DATE_RE.search(text)
    if m:
        y = int(m.group(4))
        y += 2000 if y < 100 else 0
        plan["weekday"] = m.group(1)
        plan["date"] = "%04d-%02d-%02d" % (y, int(m.group(3)), int(m.group(2)))

    in_notes = False
    info_col = None
    for line in lines:
        if not line.strip():
            continue
        if NOTES_RE.match(line):
            in_notes = True
            continue
        if in_notes:
            b = BULLET_RE.match(line)
            txt = (b.group(1) if b else line).strip()
            if not txt:
                continue
            if b or not plan["notes"]:
                plan["notes"].append(txt)
            else:
                plan["notes"][-1] += " " + txt
            continue
        row = ROW_RE.match(line)
        if row:
            info_col = row.start("info")
            plan["rows"].append(
                {
                    "stunde": re.sub(r"\s+", " ", row.group("stunde")).strip(),
                    "klasse": re.sub(r"\s+", "", row.group("klasse")),
                    "info": re.sub(r"\s+", " ", row.group("info")).strip(),
                }
            )
            continue
        indent = len(line) - len(line.lstrip())
        if plan["rows"] and info_col and indent >= info_col - 2:
            # Fortsetzung der Info-Spalte aus der vorherigen Zeile
            plan["rows"][-1]["info"] += " " + line.strip()
        # sonstige Zeilen (Überschrift, Zwischenüberschriften wie „Tagesbeginn“) ignorieren

    if not plan["rows"] and not plan["notes"]:
        return None
    return plan


def read_plan(url):
    text = pdf_to_text(url)
    plan = parse(text)
    if plan is None and text and text.strip():
        # Unbekanntes Layout: Rohtext mitgeben, damit wenigstens etwas angezeigt wird
        return {"title": None, "date": None, "weekday": None, "rows": [], "notes": [], "raw": text.strip()[:3000]}
    return plan


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1], encoding="utf-8") as f:
        print(json.dumps(parse(f.read()), ensure_ascii=False, indent=2))
