"""Prüft den Vertretungsplan-Parser an lokalen Test-PDFs.

Die PDFs liegen in testdata/vertretungsplaene/ (per .gitignore nicht im Repo).
Zu jedem PDF kann eine geprüfte Erwartung <name>.expected.json daneben liegen;
dann wird das Ergebnis damit verglichen (Regressionstest).

    python3 scripts/check_plans.py              # alle PDFs prüfen
    python3 scripts/check_plans.py --show X.pdf # Ergebnis für ein PDF ausgeben
    python3 scripts/check_plans.py --accept X.pdf  # aktuelles Ergebnis als Erwartung speichern
"""
import glob
import json
import os
import sys

from common import ROOT
from vertretungsplan import parse, pdf_bytes_to_text

TEST_DIR = os.path.join(ROOT, "testdata", "vertretungsplaene")


def result_for(pdf):
    with open(pdf, "rb") as f:
        text = pdf_bytes_to_text(f.read())
    if text is None:
        return None, None
    return text, parse(text)


def expected_path(pdf):
    return os.path.splitext(pdf)[0] + ".expected.json"


def resolve(name):
    return name if os.path.exists(name) else os.path.join(TEST_DIR, name)


def main(argv):
    if len(argv) == 2 and argv[0] in ("--show", "--accept"):
        pdf = resolve(argv[1])
        text, plan = result_for(pdf)
        if argv[0] == "--show":
            print(text)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            with open(expected_path(pdf), "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print("Erwartung gespeichert:", expected_path(pdf))
        return 0

    pdfs = sorted(glob.glob(os.path.join(TEST_DIR, "*.pdf")))
    if not pdfs:
        print("Keine PDFs in", TEST_DIR)
        return 1
    failed = 0
    for pdf in pdfs:
        name = os.path.basename(pdf)
        text, plan = result_for(pdf)
        if text is None:
            status = "KEIN TEXT (Scan oder pdftotext fehlt)"
        elif plan is None:
            status = "NICHT ERKANNT (Dashboard zeigt Rohtext)"
        else:
            status = "%s, %d Zeilen, %d Hinweise" % (plan["date"] or "ohne Datum", len(plan["rows"]), len(plan["notes"]))
        exp = expected_path(pdf)
        if os.path.exists(exp):
            with open(exp, encoding="utf-8") as f:
                ok = json.load(f) == plan
            status += " · Erwartung " + ("OK" if ok else "ABWEICHUNG")
            failed += 0 if ok else 1
        else:
            status += " · noch keine Erwartung"
        print("%-40s %s" % (name, status))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
