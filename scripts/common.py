"""Gemeinsame Hilfsfunktionen für die Abruf-Skripte (nur Python-Standardbibliothek)."""
import html
import json
import os
import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
USER_AGENT = "Mozilla/5.0 (compatible; SchaetzelbergElternDashboard/1.0)"


def now_iso():
    return datetime.now(BERLIN).isoformat(timespec="seconds")


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "de"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url):
    return json.loads(fetch(url))


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(name, data):
    """Schreibt nur, wenn sich der Inhalt (ohne Zeitstempel) geändert hat.

    Gibt True zurück, wenn die Datei neu geschrieben wurde.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    old = load_json(name)

    def strip(d):
        return {k: v for k, v in (d or {}).items() if k not in ("checked_at",)}

    if old is not None and strip(old) == strip(data):
        return False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


def write_status(key, ok, error=None):
    """Hält fest, wann eine Quelle zuletzt geprüft wurde (status.json)."""
    status = load_json("status.json") or {}
    entry = status.get(key, {})
    entry["checked_at"] = now_iso()
    entry["ok"] = ok
    if ok:
        entry["last_success"] = entry["checked_at"]
        entry.pop("error", None)
    else:
        entry["error"] = str(error)[:300]
    status[key] = entry
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write("\n")


class _Sanitizer(HTMLParser):
    """Erlaubt nur eine kleine Menge harmloser Tags; alles andere wird zu Text."""

    ALLOWED = {"p", "br", "strong", "b", "em", "i", "ul", "ol", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in self.ALLOWED:
            self.out.append("<%s>" % tag)

    def handle_endtag(self, tag):
        if tag in self.ALLOWED and tag != "br":
            self.out.append("</%s>" % tag)

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))


def sanitize_html(raw):
    if not raw:
        return ""
    p = _Sanitizer()
    p.feed(raw)
    p.close()
    out = "".join(p.out)
    out = re.sub(r"<p>\s*</p>", "", out)
    return out.strip()


def html_to_text(raw):
    if not raw:
        return ""
    t = re.sub(r"<(br|/p|/li)[^>]*>", "\n", raw)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return "\n".join(l.strip() for l in t.splitlines() if l.strip())
