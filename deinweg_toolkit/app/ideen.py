"""Ideen – das kleine Ticketsystem.

Eigener Router nach demselben Muster wie vorgaenge.py und wiki.py:
main.py reicht ueber setup() nur, was hier gebraucht wird (den Pfad der
Ideendatei und die Templates). So gibt es keinen Ringschluss beim Import.

Die Eintraege stehen im Klartext in ideen.txt - bewusst keine Tabelle:
es sind ein paar Zeilen im Jahr, und Timo kann sie ueber die
Dateifreigabe genauso lesen wie im Browser.
"""

from __future__ import annotations

import datetime as dt
import os
import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlencode

router = APIRouter()

# von setup() gefuellt
_u: dict = {}


def setup(templates, umgebung=None) -> None:
    _u["templates"] = templates
    _u.update(umgebung or {})


IDEEN_ARTEN = ["Idee", "Kritik", "Fehler", "Frage"]


def bloecke_lesen(pfad: str) -> list[dict]:
    """Liest eine Datei im Format '## Kopfzeile' plus folgenden Textzeilen.

    Gibt die Blöcke in Dateireihenfolge zurück, jeweils mit Kopfzeile und
    den restlichen Zeilen als Text.
    """
    try:
        with open(pfad, encoding="utf-8") as f:
            roh = f.read()
    except OSError:
        return []

    # Kommentarzeilen ganz am Zeilenanfang mit einzelnem # entfernen,
    # damit der Dateikopf nicht als Block auftaucht. ## bleibt Trenner.
    roh = "\n".join(z for z in roh.splitlines()
                    if not (z.startswith("#") and not z.startswith("##")))

    ergebnis = []
    for teil in roh.split("\n## "):
        teil = teil.strip()
        if not teil:
            continue
        if teil.startswith("## "):
            teil = teil[3:]
        zeilen = teil.splitlines()
        ergebnis.append({"kopf": zeilen[0].strip(),
                         "text": "\n".join(zeilen[1:]).strip()})
    return ergebnis


def idee_saeubern(art: str, wer: str, text: str):
    """Prüft und entschärft eine Eingabe. Gibt (art, wer, text, fehler) zurück."""
    text = text.strip()
    if not text:
        return None, None, None, "Da war noch nichts geschrieben."
    if len(text) > 4000:
        return None, None, None, "Bitte auf 4000 Zeichen kürzen."

    art = art if art in IDEEN_ARTEN else "Idee"
    wer = re.sub(r"[|\n\r]", " ", wer).strip()[:60] or "anonym"
    # Zeilen, die wie eine Blocktrennung aussehen, entschärfen
    text = "\n".join(
        ("#\u200b# " + z.lstrip("# ").rstrip()) if z.lstrip().startswith("##") else z
        for z in text.splitlines())
    return art, wer, text, None


def ideen_kopfzeilen() -> list[str]:
    """Die Kommentarzeilen am Dateianfang, damit sie beim Umschreiben bleiben."""
    try:
        with open(_u["IDEEN_DATEI"], encoding="utf-8") as f:
            zeilen = f.read().splitlines()
    except OSError:
        return []
    kopf = []
    for z in zeilen:
        if z.lstrip().startswith("##"):
            break
        kopf.append(z)
    return kopf


def ideen_laden() -> list[dict]:
    """Alle Einträge in Dateireihenfolge, mit Nummer als Schlüssel."""
    gesammelt = []
    for nr, b in enumerate(bloecke_lesen(_u["IDEEN_DATEI"])):
        # Kopfzeile: "17.08.2026 09:45 | Idee | Name"
        teile = [t.strip() for t in b["kopf"].split("|")]
        gesammelt.append({
            "nr": nr,
            "zeit": teile[0] if teile else "",
            "art": teile[1] if len(teile) > 1 else "Idee",
            "wer": teile[2] if len(teile) > 2 else "",
            "text": b["text"],
        })
    return gesammelt


def ideen_schreiben(eintraege: list[dict]) -> str | None:
    """Schreibt die ganze Datei neu. Gibt eine Fehlermeldung zurück oder None."""
    text = "\n".join(ideen_kopfzeilen()).rstrip()
    for e in eintraege:
        text += (f"\n\n## {e['zeit']} | {e['art']} | {e['wer']}\n{e['text']}")
    try:
        os.makedirs(os.path.dirname(_u["IDEEN_DATEI"]) or ".", exist_ok=True)
        with open(_u["IDEEN_DATEI"], "w", encoding="utf-8") as f:
            f.write(text.lstrip("\n") + "\n")
    except OSError as e:
        return f"Konnte nicht gespeichert werden: {e}"
    return None


def ideen_zurueck(**werte):
    return RedirectResponse("/ideen?" + urlencode(werte) if werte else "/ideen",
                            status_code=303)


@router.get("/ideen", response_class=HTMLResponse)
def ideen(request: Request, hinweis: str = "", fehler: str = "",
          bearbeiten: int = -1):
    eintraege = ideen_laden()
    eintraege.reverse()  # neueste zuerst, Nummer bleibt die aus der Datei
    return _u["templates"].TemplateResponse(request=request, name="ideen.html", context={
        "eintraege": eintraege, "arten": IDEEN_ARTEN, "hinweis": hinweis,
        "fehler": fehler, "datei": _u["IDEEN_DATEI"], "bearbeiten": bearbeiten,
        "seite": "ideen"})


@router.post("/ideen")
def idee_anlegen(art: str = Form("Idee"), wer: str = Form(""),
                 text: str = Form("")):
    art, wer, text, fehler = idee_saeubern(art, wer, text)
    if fehler:
        return ideen_zurueck(fehler=fehler)

    satz = (f"\n## {dt.datetime.now().strftime('%d.%m.%Y %H:%M')} | {art} | {wer}\n"
            f"{text}\n")
    try:
        os.makedirs(os.path.dirname(_u["IDEEN_DATEI"]) or ".", exist_ok=True)
        with open(_u["IDEEN_DATEI"], "a", encoding="utf-8") as f:
            f.write(satz)
    except OSError as e:
        return ideen_zurueck(fehler=f"Konnte nicht gespeichert werden: {e}")

    return ideen_zurueck(hinweis="Danke, ist notiert.")


@router.post("/ideen/{nr}/bearbeiten")
def idee_bearbeiten(nr: int, art: str = Form("Idee"), wer: str = Form(""),
                    text: str = Form("")):
    eintraege = ideen_laden()
    if not 0 <= nr < len(eintraege):
        return ideen_zurueck(fehler="Der Eintrag existiert nicht mehr.")

    art, wer, text, fehler = idee_saeubern(art, wer, text)
    if fehler:
        return ideen_zurueck(fehler=fehler, bearbeiten=nr)

    eintraege[nr].update({"art": art, "wer": wer, "text": text})
    problem = ideen_schreiben(eintraege)
    if problem:
        return ideen_zurueck(fehler=problem)
    return ideen_zurueck(hinweis="Eintrag geändert.")


@router.post("/ideen/{nr}/loeschen")
def idee_loeschen(nr: int):
    eintraege = ideen_laden()
    if not 0 <= nr < len(eintraege):
        return ideen_zurueck(fehler="Der Eintrag existiert nicht mehr.")
    weg = eintraege.pop(nr)
    problem = ideen_schreiben(eintraege)
    if problem:
        return ideen_zurueck(fehler=problem)
    return ideen_zurueck(hinweis=f"Eintrag von {weg['wer']} entfernt.")
