"""Liest das Eltern-Padlet aus und schreibt data/padlet.json.

Primärquelle ist die (inoffizielle) JSON-API, die auch die Padlet-Webseite nutzt –
nur sie liefert die Spalten (z. B. „Stundenausfall/Vertretungsplan“).
Fällt sie aus, wird der öffentliche RSS-Feed genutzt (ohne Spalten-Zuordnung).
Kommentare und Autorennamen werden bewusst NICHT übernommen (Datenschutz).
"""
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from common import (
    fetch,
    fetch_json,
    html_to_text,
    load_json,
    now_iso,
    sanitize_html,
    save_json,
    write_status,
)
from vertretungsplan import read_plan

PADLET_URL = "https://padlet.com/veerchristina/padlet-schatzelberg-gs-eltern-7w4dic7m9gbtmex7"
# Fallbacks, falls sich die IDs nicht mehr aus der Seite lesen lassen
FALLBACK_BOARD = "N1gMAXdGNL5lA2G7"
FALLBACK_WALL_ID = "245293710"
FALLBACK_FEED = "https://padlet.com/padlets/7w4dic7m9gbtmex7/exports/feed.xml?token=1b449603c86f13c096c7cf1b3effdb92"

AUSFALL_SECTION = re.compile(r"\bausfall|\bvertretung", re.I)
AUSFALL_TEXT = re.compile(r"\bausfall|\bausfallen|f[äa]llt aus|\bvertretung|entf[äa]llt|kein unterricht|unterrichtsschluss", re.I)


def page_ids(page):
    board = re.search(r"board_([A-Za-z0-9]+)", page)
    wall = re.search(r'"wallId"\s*:\s*"?(\d+)', page)
    feed = re.search(r'https://padlet\.com/padlets/[^"\s]+/exports/feed\.xml\?token=[A-Za-z0-9]+', page)
    return (
        board.group(1) if board else FALLBACK_BOARD,
        wall.group(1) if wall else FALLBACK_WALL_ID,
        feed.group(0).replace("&amp;", "&") if feed else FALLBACK_FEED,
    )


def attachment_name(url):
    if not url:
        return None
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return name or None


def is_ausfall(post):
    return bool(
        AUSFALL_SECTION.search(post.get("section") or "")
        or AUSFALL_TEXT.search(post["title"] or "")
        or AUSFALL_TEXT.search(post["text"] or "")
    )


def from_api(board, wall_id):
    sections_raw = fetch_json("https://padlet.com/api/5/wall_sections?wall_id=%s" % wall_id)["data"]
    sections = sorted(
        (
            {
                "id": s["attributes"]["id"],
                "title": s["attributes"]["title"],
                "sort": s["attributes"].get("sort_index") or 0,
            }
            for s in sections_raw
        ),
        key=lambda s: s["sort"],
    )
    by_id = {s["id"]: s["title"] for s in sections}

    wishes, page_start, guard = [], "", 0
    while guard < 20:
        guard += 1
        url = "https://padlet.com/api/10/wishes?wall_hashid=%s&page_start=%s" % (
            board,
            urllib.parse.quote(str(page_start)),
        )
        res = fetch_json(url)
        wishes.extend(res.get("data", []))
        nxt = (res.get("meta") or {}).get("next")
        if not nxt:
            break
        page_start = nxt

    posts = []
    for w in wishes:
        a = w.get("attributes", {})
        if not a.get("published", True) or a.get("visibility", "everyone") != "everyone":
            continue
        if a.get("is_content_hidden"):
            continue
        body = a.get("body") or ""
        post = {
            "id": str(a.get("id")),
            "title": (a.get("subject") or a.get("headline") or "").strip(),
            "html": sanitize_html(body),
            "text": html_to_text(body),
            "section": by_id.get(a.get("wall_section_id")),
            "url": a.get("permalink") or PADLET_URL,
            "attachment": attachment_name(a.get("attachment")),
            "created_at": a.get("published_at") or a.get("created_at"),
            "updated_at": a.get("content_updated_at") or a.get("updated_at"),
            "pinned": bool(a.get("pinned_at")),
            "_attachment_url": a.get("attachment"),  # signiert, läuft ab → wird nicht gespeichert
        }
        posts.append(post)
    return [s["title"] for s in sections], posts


def from_rss(feed_url):
    root = ET.fromstring(fetch(feed_url))
    posts = []
    for item in root.iter("item"):
        body = item.findtext("description") or ""
        enc = item.find("enclosure")
        date = item.findtext("pubDate") or ""
        try:
            iso = datetime.strptime(date, "%Y-%m-%d %H:%M:%S UTC").isoformat() + "Z"
        except ValueError:
            iso = None
        link = item.findtext("link") or PADLET_URL
        posts.append(
            {
                "id": link.rsplit("/", 1)[-1],
                "title": (item.findtext("title") or "").strip(),
                "html": sanitize_html(body),
                "text": html_to_text(body),
                "section": None,
                "url": link,
                "attachment": attachment_name(enc.get("url") if enc is not None else None),
                "created_at": iso,
                "updated_at": iso,
                "pinned": False,
            }
        )
    return [], posts


def main():
    source = "api"
    try:
        page = fetch(PADLET_URL)
        board, wall_id, feed = page_ids(page)
    except Exception as e:  # Seite nicht erreichbar → Fallback-IDs
        print("Padlet-Seite nicht lesbar:", e, file=sys.stderr)
        board, wall_id, feed = FALLBACK_BOARD, FALLBACK_WALL_ID, FALLBACK_FEED

    try:
        sections, posts = from_api(board, wall_id)
    except Exception as e:
        print("Padlet-API fehlgeschlagen, nutze RSS:", e, file=sys.stderr)
        source = "rss"
        try:
            sections, posts = from_rss(feed)
        except Exception as e2:
            print("Auch RSS fehlgeschlagen – behalte alte Daten:", e2, file=sys.stderr)
            write_status("padlet", False, e2)
            return 1

    if not posts and not sections:
        # Verdächtig leer: lieber alte Daten behalten
        write_status("padlet", False, "Keine Beiträge gefunden")
        return 1

    ausfall_section = next((s for s in sections if AUSFALL_SECTION.search(s)), None)
    recent = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    for p in posts:
        p["ausfall"] = is_ausfall(p)
        url = p.pop("_attachment_url", None)
        p["plan"] = None
        is_plan_post = ausfall_section and p["section"] == ausfall_section
        if is_plan_post and url and (p["attachment"] or "").lower().endswith(".pdf") and (p["created_at"] or "") >= recent:
            try:
                p["plan"] = read_plan(url)
            except Exception as e:
                print("Vertretungsplan-PDF nicht lesbar (%s): %s" % (p["attachment"], e), file=sys.stderr)
    posts.sort(key=lambda p: p["created_at"] or "", reverse=True)

    data = {
        "source": source,
        "padlet_url": PADLET_URL,
        "sections": sections,
        "ausfall_section": ausfall_section,
        "posts": posts,
        "content_changed_at": now_iso(),
    }
    # Zeitpunkt der letzten inhaltlichen Änderung beibehalten, wenn sich nichts geändert hat
    old = load_json("padlet.json") or {}
    if old.get("content_changed_at") and all(old.get(k) == v for k, v in data.items() if k != "content_changed_at"):
        data["content_changed_at"] = old["content_changed_at"]

    changed = save_json("padlet.json", data)
    write_status("padlet", True)
    print("Padlet: %d Beiträge über %s, %s" % (len(posts), source, "GEÄNDERT" if changed else "unverändert"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
