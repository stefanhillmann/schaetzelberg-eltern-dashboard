# Schätzelberg Eltern-Info

Mobiles Dashboard für Eltern der Schätzelberg-Grundschule: Kontakt, Unterrichtsausfall und anstehende Termine auf einen Blick. Inoffiziell – maßgeblich bleiben [Schulwebsite](https://schaetzelberg-gs.de) und [Eltern-Padlet](https://padlet.com/veerchristina/padlet-schatzelberg-gs-eltern-7w4dic7m9gbtmex7).

## So funktioniert es

| Quelle | Was | Wie oft |
|---|---|---|
| Eltern-Padlet | Spalte „Stundenausfall/Vertretungsplan“ inkl. ausgelesener Vertretungsplan-PDFs, alle Beiträge | stündlich |
| Schulwebsite | Termine (Startseite), Kontakt, Schulleitung, SpB-Leitung | täglich |

- `scripts/fetch_padlet.py` und `scripts/fetch_website.py` (nur Python-Standardbibliothek) schreiben `data/*.json`.
- `.github/workflows/update.yml` führt die Skripte per Zeitplan aus, committet nur echte Änderungen und veröffentlicht die Seite über GitHub Pages.
- Schlägt ein Abruf fehl, bleiben die alten Daten erhalten; das Dashboard zeigt dann „Daten möglicherweise veraltet“.
- Kommentare und Autor:innen aus dem Padlet werden bewusst **nicht** übernommen.

## Einrichtung

1. Repository auf GitHub anlegen und diesen Ordner pushen (Branch `main`).
2. **Settings → Pages → Build and deployment → Source: „GitHub Actions“** wählen.
3. Unter **Actions** den Workflow „Daten aktualisieren & veröffentlichen“ einmal per **Run workflow** starten.

## Lokal testen

Für die Vertretungsplan-PDFs wird `pdftotext` benötigt (`brew install poppler`).

```bash
python3 scripts/fetch_padlet.py && python3 scripts/fetch_website.py
python3 -m http.server 8765
```

Dann http://localhost:8765 öffnen. Mit `?heute=2026-11-19` lässt sich ein anderes Datum simulieren.
