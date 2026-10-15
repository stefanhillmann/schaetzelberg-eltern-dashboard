# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An unofficial, mobile-first parent dashboard for the Schätzelberg-Grundschule (Berlin). It shows contact info, class cancellations (Unterrichtsausfall) and upcoming events. It is a static site on GitHub Pages at https://stefanhillmann.github.io/schaetzelberg-eltern-dashboard/. There is no build step, no framework and no dependencies. User-facing text and code comments are in German.

## Commands

```bash
python3 scripts/fetch_padlet.py     # refresh data/padlet.json (+ data/status.json)
python3 scripts/fetch_website.py    # refresh data/website.json (+ data/status.json)
python3 -m http.server 8765         # serve locally → http://localhost:8765
```

- There are no tests or linters. To check a change, run the scripts and look at the page at 375px width, in both light and dark mode.
- Append `?heute=YYYY-MM-DD` to the URL to simulate another date.
- To test the empty, stale or "cancellation today" states, edit the JSON in `data/`, or call the global `render*` functions from the browser console with modified objects.
- The scripts must stay **Python 3.9-compatible and stdlib-only**. Locally that is the macOS system Python; CI uses 3.12. So: no `X | None` annotations, no `match`, no pip packages.

## Architecture

**Data pipeline (Python, `scripts/`):** each fetcher scrapes one source and writes a JSON file to `data/`. The browser reads those files. It never talks to Padlet or the school website itself.

- `fetch_padlet.py` reads the public Padlet in three steps:
  1. It extracts `board_…` (hashid), `wallId` and the RSS feed token from the Padlet page HTML. Hardcoded fallbacks exist.
  2. It calls Padlet's **undocumented internal JSON API**: `api/5/wall_sections` and `api/10/wishes?wall_hashid=` (paginated via `meta.next`). Only this API maps posts to columns (sections).
  3. If the API fails, it falls back to the RSS feed. That feed has no sections, so `source: "rss"` is set and cancellations are detected by keyword only.
- `fetch_website.py` parses the WordPress/Elementor homepage:
  - events from `.sel-event-item` markup (dates like `15.10.26 | 14 Uhr`, sometimes without a year; `infer_year` handles that);
  - contact info from the header;
  - people from `/schule/schulleitung/` and `/spb/teamleitung/`.
- `common.py` holds shared helpers: fetching, the Europe/Berlin timezone, an allowlist HTML sanitizer, `save_json` (writes only if the content changed, ignoring timestamps) and `write_status`.

**Invariants to keep:**

- **A failed or suspicious fetch never overwrites existing data.** The script exits 1 and only records `ok: false` in `status.json`.
  - An empty events list is valid.
  - A missing `sel-events-list` container is a failure, because it means the page structure changed.
- **Privacy:** never fetch or publish Padlet comments or author names. Comments contain parents' names.
- **Untrusted HTML:** post bodies are sanitized in Python (`sanitize_html`); `app.js` injects only that field as HTML and escapes everything else via `esc()`.
- **Links:** always link Padlet permalinks, never attachment URLs. Those carry expiring tokens, or return 403.
- **Cancellation detection:** keywords are anchored to word starts (`\bvertretung`) so that words like "Elternvertretung" don't match. The cancellation section is found by title keyword, not by ID.
- **Date logic:**
  - Dates are computed in Europe/Berlin.
  - Filtering out past events and setting the "Heute" badges happen client-side in `app.js`, because website data refreshes only daily.
  - Staleness is judged by the age of `last_success`: Padlet after more than 3 h, website after more than 36 h. A single failed check (`ok: false`) does not count as stale.

**Frontend:** `index.html`, `app.js` and `style.css` are vanilla. `app.js` loads the three JSON files and renders four cards: Ausfall, Termine, Kontakt, Padlet. Colors are CSS custom properties on `:root` with a `prefers-color-scheme: dark` override.

**CI (`.github/workflows/update.yml`):** a single job with two crons.

- The hourly cron runs Padlet only. The daily cron `23 3 * * *` also runs the website fetch; it is matched by string against `env.DAILY_CRON`, so **keep the two identical**. `push` and `workflow_dispatch` run both fetchers.
- Order of steps:
  1. Restore `data/status.json` from the live site. Hourly status updates are deployed but not committed.
  2. Run the fetchers. Their failures only produce warnings, so the job never fails.
  3. Commit `data/` only if the content changed. `status.json` is also committed once a day as a heartbeat against GitHub's 60-day inactivity rule.
  4. Build `_site/` and deploy with `actions/deploy-pages`. Pages source is "GitHub Actions".
- **New static files must be added to the `cp` line in the "Seite zusammenstellen" step**, otherwise they won't be deployed.
- The bot pushes data commits to `main`, so run `git pull` before local edits.
