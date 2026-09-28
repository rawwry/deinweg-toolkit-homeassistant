"""Tagesvorlagen fuer die manuelle Zeiterfassung (seit 1.59, Timos Auftrag).

Viele im Team haben Wochentage, die fast immer gleich aussehen. Eine
Vorlage merkt sich die Zeilen eines solchen Tages - Uhrzeiten, betreute
Person, Leistung, Erlaeuterung, aber kein Datum - unter einem freien Namen
("Montag Standard").

⚠️⚠️ Eine Vorlage SPEICHERT NIE eine Zeit. Geladen wird sie ins Formular
der Erfassung, dort sieht man jede Zeile, passt an und speichert wie
immer. Ein Montag ist selten ganz Standard, und ein direktes Speichern
schriebe falsche Zeiten ohne Rueckfrage in den Nachweis.

⚠️ Gewaehlt wird immer von Hand, es gibt keinen Vorschlag nach Wochentag
(Timos Entscheidung, "zumindest vorerst").

⚠️ Eine betreute Person, die inzwischen nicht mehr betreut wird, laedt
trotzdem mit (Timos Entscheidung). Speichern laesst sich die Zeile dann
nicht, und genau das faellt auf - die Zeile wird entfernt und die
Vorlage bei Gelegenheit angepasst.

Jede Vorlage gehoert genau einem Konto. Die Routen liegen unter
/erfassung und haengen damit am Bereich "manuelle_eintraege"; die
Eigentuemerschaft steht in jeder WHERE-Klausel, nicht als `if` dahinter -
dieselbe Regel wie bei den Privatauslagen.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import db
from .parser import dauer_aus_spanne, parse_datum, parse_zeit
from .rechnen import jetzt, mitarbeiter_zu_benutzer

router = APIRouter()

NAME_MAX = 60
ZEILEN_MAX = 30
VORLAGEN_MAX = 40
# Leistung und Erlaeuterung werden in eintrag.beschreibung mit diesem
# Trenner zusammengesetzt (main.erfassung_speichern). Beim Uebernehmen eines
# Tages wird daran wieder getrennt.
TRENNER = ": "


def _konto(request: Request):
    return getattr(request.state, "benutzer", None)


def _zeit(text: str) -> str | None:
    """14:30, 14.30, 12, 930 und 1430 - wie zeitFuellen() im Browser.

    ⚠️ Bewusst eine eigene Fassung: dieses Modul darf main.py nicht
    importieren (Ringschluss, CLAUDE.md Abschnitt 3).
    """
    text = (text or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{1,4}", text):
        if len(text) <= 2:
            text = text + "00"
        text = text.zfill(4)[:-2] + ":" + text.zfill(4)[-2:]
    return parse_zeit(text)


def _minuten(zeile: dict) -> int:
    return dauer_aus_spanne(zeile.get("start") or None,
                            zeile.get("ende") or None) or 0


def liste(con, benutzer_id: int) -> list[dict]:
    """Alle Vorlagen eines Kontos, nach Namen - fertig fuer Vorlage und Skript."""
    raus = []
    for r in con.execute(
            "SELECT id, name, zeilen, geaendert_am, angelegt_am FROM vorlage "
            "WHERE benutzer_id=? ORDER BY name COLLATE NOCASE", (benutzer_id,)):
        try:
            zeilen = json.loads(r["zeilen"] or "[]")
        except ValueError:
            zeilen = []
        raus.append({"id": r["id"], "name": r["name"], "zeilen": zeilen,
                     "anzahl": len(zeilen),
                     "minuten": sum(_minuten(z) for z in zeilen),
                     "stand": r["geaendert_am"] or r["angelegt_am"]})
    return raus


def _name_pruefen(name: str) -> tuple[str, str]:
    name = " ".join((name or "").split())
    if not name:
        return "", "Gib der Vorlage einen Namen, zum Beispiel „Montag Standard“."
    if len(name) > NAME_MAX:
        return "", f"Der Name ist zu lang – höchstens {NAME_MAX} Zeichen."
    return name, ""


def _ablegen(con, benutzer_id: int, name: str, zeilen: list[dict]) -> tuple[str, str]:
    """Legt an oder ersetzt eine gleichnamige. Gibt (meldung, fehler) zurueck."""
    alt = con.execute(
        "SELECT id FROM vorlage WHERE benutzer_id=? AND LOWER(name)=LOWER(?)",
        (benutzer_id, name)).fetchone()
    daten = json.dumps(zeilen, ensure_ascii=False)
    menge = f"{len(zeilen)} {'Zeile' if len(zeilen) == 1 else 'Zeilen'}"
    if alt:
        con.execute("UPDATE vorlage SET name=?, zeilen=?, geaendert_am=? "
                    "WHERE id=? AND benutzer_id=?",
                    (name, daten, jetzt(), alt["id"], benutzer_id))
        return f"Vorlage „{name}“ aktualisiert ({menge}).", ""
    zahl = con.execute("SELECT COUNT(*) c FROM vorlage WHERE benutzer_id=?",
                       (benutzer_id,)).fetchone()["c"]
    if zahl >= VORLAGEN_MAX:
        return "", (f"Du hast schon {VORLAGEN_MAX} Vorlagen. Räum unter "
                    "„Mein Bereich“ eine weg, bevor du eine neue anlegst.")
    con.execute("INSERT INTO vorlage (benutzer_id, name, zeilen, angelegt_am) "
                "VALUES (?,?,?,?)", (benutzer_id, name, daten, jetzt()))
    return f"Vorlage „{name}“ gespeichert ({menge}).", ""


def leistung_trennen(text: str, leistungen: list[str]) -> tuple[str, str]:
    """Macht aus "Hausbesuch: Einkauf" wieder Leistung und Erlaeuterung.

    Nur wenn der vordere Teil eine gepflegte Leistung ist - sonst bleibt
    der ganze Text Erlaeuterung. So geht nie etwas verloren: gespeichert
    ergibt sich derselbe Text wie vorher.
    """
    text = (text or "").strip()
    bekannt = {l.lower(): l for l in leistungen}
    if text.lower() in bekannt:
        return bekannt[text.lower()], ""
    if TRENNER in text:
        vorn, hinten = text.split(TRENNER, 1)
        if vorn.strip().lower() in bekannt:
            return bekannt[vorn.strip().lower()], hinten.strip()
    return "", text


# --- Aus den Zeilen des Formulars ---------------------------------------------

@router.post("/erfassung/vorlagen/speichern")
def aus_formular(request: Request, name: str = Form(""),
                 klient: list[str] = Form([]), start: list[str] = Form([]),
                 ende: list[str] = Form([]), leistung: list[str] = Form([]),
                 beschreibung: list[str] = Form([])):
    """Die gerade eingetippten Zeilen als Vorlage merken - per Skript.

    Antwortet mit JSON: das Formular bleibt dabei stehen, man kann die
    Zeilen danach also auch noch als Zeiten speichern. Der Knopf dafuer
    steht ohnehin nur mit Skript da.
    """
    konto = _konto(request)

    def nein(text: str):
        return JSONResponse({"ok": False, "meldung": text}, status_code=400)

    name, fehler = _name_pruefen(name)
    if fehler:
        return nein(fehler)

    def feld(werte: list[str], nr: int) -> str:
        return (werte[nr] if nr < len(werte) else "").strip()

    zeilen = []
    for nr in range(max(len(klient), len(start), len(ende),
                        len(leistung), len(beschreibung))):
        k, a, e = feld(klient, nr), feld(start, nr), feld(ende, nr)
        l, b = feld(leistung, nr), feld(beschreibung, nr)
        if not any((k, a, e, l, b)):
            continue
        za, ze = _zeit(a), _zeit(e)
        if (a and za is None) or (e and ze is None):
            return nein(f"Zeile {nr + 1}: Die Uhrzeit passt nicht – "
                        "schreib sie als HH:MM.")
        zeilen.append({"klient": k, "start": za or "", "ende": ze or "",
                       "leistung": l, "beschreibung": b})
    if not zeilen:
        return nein("Es steht noch keine Zeile im Formular, die sich merken ließe.")
    if len(zeilen) > ZEILEN_MAX:
        return nein(f"Eine Vorlage fasst höchstens {ZEILEN_MAX} Zeilen.")

    with db.db() as con:
        meldung, fehler = _ablegen(con, konto["id"], name, zeilen)
        if fehler:
            return nein(fehler)
        return JSONResponse({"ok": True, "meldung": meldung,
                             "vorlagen": liste(con, konto["id"])})


# --- Aus einem schon erfassten Tag --------------------------------------------

@router.post("/erfassung/vorlagen/aus-tag")
def aus_tag(request: Request, datum: str = Form(""), name: str = Form("")):
    """Die eigenen Zeiten eines Tages als Vorlage merken.

    Der schnellste Weg zur ersten Vorlage: fast jeder hat einen typischen
    Montag schon einmal erfasst. Geht ohne Skript.
    ⚠️ Nur die EIGENEN Zeiten - eine Vorlage gehoert dem Konto, und die
    Zeiten anderer haben darin nichts verloren.
    """
    konto = _konto(request)
    tag = parse_datum(datum)

    def zurueck(**werte):
        werte = {"datum": tag.strftime("%d.%m.%Y") if tag else "", **werte}
        return RedirectResponse("/?" + urlencode({k: v for k, v in werte.items() if v})
                                + "#erfassen", status_code=303)

    if tag is None:
        return zurueck(fehler="Der Tag für die Vorlage fehlt.")
    name, fehler = _name_pruefen(name)
    if fehler:
        return zurueck(fehler=fehler)

    with db.db() as con:
        wer = mitarbeiter_zu_benutzer(con, konto)
        eigener = (wer["name"] or "").strip() if wer else ""
        if not eigener:
            return zurueck(fehler="Deinem Konto ist kein Mitarbeiter zugeordnet – "
                                  "damit lässt sich nicht sagen, welche Zeiten deine sind.")
        leistungen = [r["name"] for r in con.execute(
            "SELECT name FROM leistung WHERE aktiv=1")]
        zeilen = []
        for r in con.execute(
                "SELECT klient, start, ende, beschreibung FROM eintrag "
                "WHERE LOWER(TRIM(mitarbeiter))=LOWER(?) AND datum=? "
                "ORDER BY (start IS NULL OR start=''), start, id",
                (eigener, tag.isoformat())):
            l, b = leistung_trennen(r["beschreibung"], leistungen)
            zeilen.append({"klient": r["klient"] or "", "start": r["start"] or "",
                           "ende": r["ende"] or "", "leistung": l, "beschreibung": b})
        if not zeilen:
            return zurueck(fehler="An diesem Tag hast du noch nichts erfasst – "
                                  "da gibt es nichts zu merken.")
        if len(zeilen) > ZEILEN_MAX:
            return zurueck(fehler=f"Eine Vorlage fasst höchstens {ZEILEN_MAX} Zeilen.")
        meldung, fehler = _ablegen(con, konto["id"], name, zeilen)
    return zurueck(fehler=fehler) if fehler else zurueck(hinweis=meldung)


# --- Pflege in "Mein Bereich" -------------------------------------------------

def _mein(hinweis: str = "", fehler: str = "") -> RedirectResponse:
    werte = {k: v for k, v in (("hinweis", hinweis), ("fehler", fehler)) if v}
    return RedirectResponse("/meinbereich" + ("?" + urlencode(werte) if werte else "")
                            + "#vorlagen", status_code=303)


@router.post("/erfassung/vorlagen/{vorlage_id}/umbenennen")
def umbenennen(request: Request, vorlage_id: int, name: str = Form("")):
    konto = _konto(request)
    name, fehler = _name_pruefen(name)
    if fehler:
        return _mein(fehler=fehler)
    with db.db() as con:
        doppelt = con.execute(
            "SELECT 1 FROM vorlage WHERE benutzer_id=? AND LOWER(name)=LOWER(?) "
            "AND id<>?", (konto["id"], name, vorlage_id)).fetchone()
        if doppelt:
            return _mein(fehler=f"Eine Vorlage „{name}“ gibt es schon.")
        n = con.execute("UPDATE vorlage SET name=?, geaendert_am=? "
                        "WHERE id=? AND benutzer_id=?",
                        (name, jetzt(), vorlage_id, konto["id"])).rowcount
    return _mein(hinweis=f"Umbenannt in „{name}“.") if n else _mein(
        fehler="Diese Vorlage gibt es nicht (mehr).")


@router.post("/erfassung/vorlagen/{vorlage_id}/loeschen")
def loeschen(request: Request, vorlage_id: int):
    konto = _konto(request)
    with db.db() as con:
        n = con.execute("DELETE FROM vorlage WHERE id=? AND benutzer_id=?",
                        (vorlage_id, konto["id"])).rowcount
    return _mein(hinweis="Vorlage entfernt.") if n else _mein(
        fehler="Diese Vorlage gibt es nicht (mehr).")
