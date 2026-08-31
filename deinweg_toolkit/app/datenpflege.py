"""Sammeländerung von Beschreibungen und Namen.

⚠️ Dieses Modul schreibt quer durch die Datenbank. Es ist die einzige
Stelle im Programm, an der eine einzige Aktion hunderte Zeilen auf einmal
ändert - entsprechend eng ist es abgesichert:

* eigener Berechtigungsbereich ``datenpflege`` UND fest auf die Rolle
  ``admin`` begrenzt (``auth.ADMIN_NUR_PFADE``),
* zwei Schritte: erst eine Vorschau mit Zahlen je betroffener Stelle und
  Beispielzeilen, dann das Anwenden,
* das Anwenden verlangt, dass das Wort ``ÄNDERN`` eingetippt wird,
* unmittelbar davor legt das Tool eine Sicherung der Datenbank an.

⚠️ **Kein Stammeintrag wird gelöscht.** Wird auf einen Namen umbenannt,
den es schon gibt, ist das eine Zusammenführung: der alte Stammeintrag
wird nur stillgelegt (``aktiv=0``). So gehen weder bewilligte Zeiträume
noch Urlaubstage verloren, und der Schritt bleibt rückgängig zu machen.

Verglichen wird über ``parser.norm()``, wie überall im Programm - sonst
fände die Aktion „ Timo" und „timo" nicht zusammen.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth, db, mail
from .parser import norm

router = APIRouter()
templates = None
_u: dict = {}


def setup(vorlagen, umgebung: dict) -> None:
    global templates
    templates = vorlagen
    _u.update(umgebung)


# Welche Felder lassen sich ändern? Der Schlüssel ist zugleich der Wert im
# Formular, dahinter steht die Spalte in ``eintrag``.
FELDER = {
    "beschreibung": {"spalte": "beschreibung", "wort": "Beschreibung",
                     "global": False},
    "mitarbeiter": {"spalte": "mitarbeiter", "wort": "Mitarbeiter",
                    "global": True},
    "klient": {"spalte": "klient", "wort": "Betreute Person",
               "global": True},
}

SUCHARTEN = {"genau": "ist genau", "enthaelt": "enthält"}

# Wie viele Beispielzeilen die Vorschau zeigt.
BEISPIELE = 8


def werte_lesen(con, feld: str) -> list[str]:
    """Alle vorkommenden Werte eines Feldes, alphabetisch."""
    spalte = FELDER[feld]["spalte"]
    return [r[0] for r in con.execute(
        f"SELECT DISTINCT {spalte} FROM eintrag "
        f"WHERE {spalte} IS NOT NULL AND TRIM({spalte}) <> '' "
        f"ORDER BY 1 COLLATE NOCASE") if r[0]]


def treffer_werte(con, feld: str, suchart: str, suchwert: str) -> list[str]:
    """Welche vorhandenen Werte passen auf die Suche?

    ⚠️ Gefiltert wird in Python über ``norm()`` und nicht in SQL. SQLite
    vergleicht ``LIKE`` nur bei ASCII ohne Rücksicht auf Groß- und
    Kleinschreibung - „Krank" und „krank" fänden sich, „Ärztin" und
    „ärztin" nicht. Die Listen sind ein paar Dutzend Werte lang, das
    kostet nichts.
    """
    gesucht = norm(suchwert)
    if not gesucht:
        return []
    treffer = []
    for wert in werte_lesen(con, feld):
        gefunden = norm(wert)
        if (gefunden == gesucht if suchart == "genau" else gesucht in gefunden):
            treffer.append(wert)
    return treffer


def _in(werte: list[str]) -> tuple[str, list[str]]:
    return ",".join("?" * len(werte)), list(werte)


def _konfig_namen(con, alt: list[str], neu: str) -> list[tuple[str, str, str]]:
    """Namenslisten in der Konfiguration, in denen ein alter Name steht.

    Gibt (Schlüssel, alter Wert, neuer Wert) zurück - berechnet, aber noch
    nicht geschrieben, damit die Vorschau dieselbe Rechnung benutzt.
    """
    alt_norm = {norm(a) for a in alt}
    k = mail.konfig_lesen(con)
    ergebnis = []
    for schluessel in ("frist_kopie", "bewilligung_empfaenger"):
        namen = mail.empfaengerliste(k.get(schluessel))
        if not any(norm(n) in alt_norm for n in namen):
            continue
        gewandelt: list[str] = []
        for n in namen:
            ziel = neu if norm(n) in alt_norm else n
            if ziel not in gewandelt:
                gewandelt.append(ziel)
        ergebnis.append((schluessel, k.get(schluessel) or "",
                         ", ".join(gewandelt)))
    return ergebnis


def vorschau_bauen(con, feld: str, suchart: str, suchwert: str,
                   neuer_wert: str, ueberall: bool) -> dict:
    """Was würde die Änderung anfassen? Zählt, ändert nichts."""
    werte = treffer_werte(con, feld, suchart, suchwert)
    spalte = FELDER[feld]["spalte"]
    stellen: list[dict] = []
    hinweise: list[str] = []

    if not werte:
        return {"werte": [], "stellen": [], "beispiele": [], "gesamt": 0,
                "hinweise": ["Kein einziger Eintrag passt auf diese Suche."]}

    platz, args = _in(werte)
    anzahl = con.execute(
        f"SELECT COUNT(*) FROM eintrag WHERE {spalte} IN ({platz})",
        args).fetchone()[0]
    stellen.append({"wo": "Zeiteinträge", "anzahl": anzahl})

    beispiele = con.execute(
        f"SELECT datum, mitarbeiter, klient, beschreibung, dauer_min "
        f"FROM eintrag WHERE {spalte} IN ({platz}) "
        f"ORDER BY datum DESC LIMIT {BEISPIELE}", args).fetchall()

    # Offene Import-Vorschauen tragen dieselben Spalten.
    if feld in ("mitarbeiter", "klient"):
        offen = con.execute(
            f"SELECT COUNT(*) FROM vorschau WHERE {spalte} IN ({platz})",
            args).fetchone()[0]
        if offen:
            stellen.append({"wo": "Zeilen in offenen Vorschauen",
                            "anzahl": offen})

    if ueberall and FELDER[feld]["global"]:
        stellen += _globale_stellen(con, feld, werte, neuer_wert, hinweise)

    return {"werte": werte, "stellen": stellen, "beispiele": beispiele,
            "gesamt": sum(s["anzahl"] for s in stellen), "hinweise": hinweise}


def _globale_stellen(con, feld: str, werte: list[str], neu: str,
                     hinweise: list[str]) -> list[dict]:
    """Alle Stellen außerhalb der Zeiteinträge, an denen der Name steht."""
    platz, args = _in(werte)
    stellen = []

    if feld == "mitarbeiter":
        tabelle, spalte_stamm, wort = "mitarbeiter", "name", "Team-Eintrag"
        weitere = [
            ("import", "mitarbeiter", "Vermerke zu eingelesenen Dateien"),
            ("benutzer", "mitarbeiter", "Zuordnung am Benutzerkonto"),
            ("vorgang", "zustaendig", "Aufgaben (zuständig)"),
            ("vorgang_log", "wer", "Logbuchzeilen"),
        ]
    else:
        tabelle, spalte_stamm, wort = "person", "name", "Stammeintrag"
        weitere = [
            ("import", "klient", None),          # gibt es dort nicht
            ("vorgang", "klient", "Aufgaben (betreute Person)"),
            ("vorgang_log", "klient", "Logbuchzeilen"),
        ]

    for tab, sp, beschriftung in weitere:
        if beschriftung is None:
            continue
        anzahl = con.execute(
            f"SELECT COUNT(*) FROM {tab} WHERE {sp} IN ({platz})",
            args).fetchone()[0]
        if anzahl:
            stellen.append({"wo": beschriftung, "anzahl": anzahl})

    # Der Stammeintrag: umbenennen oder zusammenführen?
    stamm = con.execute(
        f"SELECT id, {spalte_stamm} FROM {tabelle} "
        f"WHERE {spalte_stamm} IN ({platz})", args).fetchall()
    ziel = con.execute(
        f"SELECT id FROM {tabelle} WHERE {spalte_stamm} = ?", (neu,)).fetchone()
    if stamm:
        stellen.append({"wo": wort, "anzahl": len(stamm)})
        if ziel:
            hinweise.append(
                f"„{neu}“ gibt es schon. Der bisherige {wort} wird deshalb "
                f"nicht umbenannt, sondern stillgelegt – nichts geht "
                f"verloren, der Name verschwindet nur aus den Auswahlfeldern.")
        elif len(stamm) > 1:
            hinweise.append(
                f"Es passen mehrere {wort}e auf die Suche. Der erste wird "
                f"umbenannt, die übrigen werden stillgelegt.")

    for schluessel, _alt, _neu in _konfig_namen(con, werte, neu):
        stellen.append({"wo": f"E-Mail-Empfängerliste ({schluessel})",
                        "anzahl": 1})
    return stellen


def anwenden(con, feld: str, suchart: str, suchwert: str, neuer_wert: str,
             ueberall: bool) -> dict:
    """Führt die Änderung aus. Der Aufrufer sorgt für die Sicherung."""
    werte = treffer_werte(con, feld, suchart, suchwert)
    if not werte:
        return {"gesamt": 0, "werte": []}
    spalte = FELDER[feld]["spalte"]
    platz, args = _in(werte)
    gezaehlt = 0

    gezaehlt += con.execute(
        f"UPDATE eintrag SET {spalte} = ? WHERE {spalte} IN ({platz})",
        [neuer_wert, *args]).rowcount

    if feld in ("mitarbeiter", "klient"):
        gezaehlt += con.execute(
            f"UPDATE vorschau SET {spalte} = ? WHERE {spalte} IN ({platz})",
            [neuer_wert, *args]).rowcount

    if ueberall and FELDER[feld]["global"]:
        gezaehlt += _global_anwenden(con, feld, werte, neuer_wert)

    return {"gesamt": gezaehlt, "werte": werte}


def _global_anwenden(con, feld: str, werte: list[str], neu: str) -> int:
    platz, args = _in(werte)
    gezaehlt = 0

    if feld == "mitarbeiter":
        tabelle, spalte_stamm = "mitarbeiter", "name"
        weitere = [("import", "mitarbeiter"), ("benutzer", "mitarbeiter"),
                   ("vorgang", "zustaendig"), ("vorgang_log", "wer")]
    else:
        tabelle, spalte_stamm = "person", "name"
        weitere = [("vorgang", "klient"), ("vorgang_log", "klient")]

    for tab, sp in weitere:
        gezaehlt += con.execute(
            f"UPDATE {tab} SET {sp} = ? WHERE {sp} IN ({platz})",
            [neu, *args]).rowcount

    # ⚠️ Stammeintrag: NIE löschen. Gibt es das Ziel schon, wird der alte
    # Eintrag stillgelegt - so bleiben bewilligte Zeiträume, Urlaubstage
    # und Wochenstunden erhalten und der Schritt lässt sich zurücknehmen.
    stamm = con.execute(
        f"SELECT id, {spalte_stamm} FROM {tabelle} "
        f"WHERE {spalte_stamm} IN ({platz}) ORDER BY id", args).fetchall()
    ziel = con.execute(
        f"SELECT id FROM {tabelle} WHERE {spalte_stamm} = ?", (neu,)).fetchone()
    for nr, zeile in enumerate(stamm):
        if ziel is None and nr == 0:
            con.execute(f"UPDATE {tabelle} SET {spalte_stamm} = ? WHERE id = ?",
                        (neu, zeile["id"]))
        else:
            con.execute(f"UPDATE {tabelle} SET aktiv = 0 WHERE id = ?",
                        (zeile["id"],))
        gezaehlt += 1

    for schluessel, _alt, neu_wert in _konfig_namen(con, werte, neu):
        mail.konfig_schreiben(con, {schluessel: neu_wert})
        gezaehlt += 1
    return gezaehlt


# --- Seiten -------------------------------------------------------------

def _seite(request: Request, **werte):
    with db.db() as con:
        auswahl = {f: werte_lesen(con, f) for f in FELDER}
    grund = {
        "feld": "beschreibung", "suchart": "genau", "suchwert": "",
        "neuer_wert": "", "ueberall": False, "vorschau": None,
        "fehler": "", "hinweis": "",
    }
    grund.update(werte)
    return templates.TemplateResponse(
        request=request, name="datenpflege.html",
        context={"FELDER": FELDER, "SUCHARTEN": SUCHARTEN,
                 "auswahl": auswahl, "seite": "datenpflege", **grund})


@router.get("/datenpflege", response_class=HTMLResponse)
def datenpflege(request: Request, hinweis: str = "", fehler: str = ""):
    return _seite(request, hinweis=hinweis, fehler=fehler)


def _pruefen(feld: str, suchart: str, suchwert: str, neuer_wert: str) -> str:
    if feld not in FELDER:
        return "Unbekanntes Feld."
    if suchart not in SUCHARTEN:
        return "Unbekannte Suchart."
    if not suchwert.strip():
        return "Trag ein, was gesucht werden soll."
    if not neuer_wert.strip():
        return "Trag ein, was stattdessen stehen soll."
    if norm(suchwert) == norm(neuer_wert) and suchart == "genau":
        return "Alter und neuer Wert sind derselbe – da gibt es nichts zu tun."
    return ""


@router.post("/datenpflege/vorschau", response_class=HTMLResponse)
def vorschau(request: Request, feld: str = Form("beschreibung"),
             suchart: str = Form("genau"), suchwert: str = Form(""),
             neuer_wert: str = Form(""), ueberall: str = Form("")):
    """Schritt 1: nur rechnen, nichts ändern."""
    fehler = _pruefen(feld, suchart, suchwert, neuer_wert)
    daten = {"feld": feld, "suchart": suchart, "suchwert": suchwert,
             "neuer_wert": neuer_wert, "ueberall": bool(ueberall)}
    if fehler:
        return _seite(request, fehler=fehler, **daten)
    with db.db() as con:
        bild = vorschau_bauen(con, feld, suchart, suchwert.strip(),
                              neuer_wert.strip(), bool(ueberall))
    return _seite(request, vorschau=bild, **daten)


@router.post("/datenpflege/anwenden")
def anwenden_route(request: Request, feld: str = Form("beschreibung"),
                   suchart: str = Form("genau"), suchwert: str = Form(""),
                   neuer_wert: str = Form(""), ueberall: str = Form(""),
                   bestaetigung: str = Form("")):
    """Schritt 2: Sicherung anlegen, dann ändern."""
    fehler = _pruefen(feld, suchart, suchwert, neuer_wert)
    daten = {"feld": feld, "suchart": suchart, "suchwert": suchwert,
             "neuer_wert": neuer_wert, "ueberall": bool(ueberall)}
    if fehler:
        return _seite(request, fehler=fehler, **daten)

    # ⚠️ Das Wort muss getippt werden. Ein Knopf allein liesse sich zu
    # leicht im Vorbeigehen treffen - und diese Aktion nimmt niemand
    # zurueck, ausser ueber die Sicherung.
    if bestaetigung.strip().upper() != "ÄNDERN":
        with db.db() as con:
            bild = vorschau_bauen(con, feld, suchart, suchwert.strip(),
                                  neuer_wert.strip(), bool(ueberall))
        return _seite(request, vorschau=bild, **daten,
                      fehler="Zum Anwenden muss das Wort ÄNDERN im Feld stehen.")

    # Erst sichern, dann anfassen.
    sicherung = _u["sicherung_anlegen"]("datenpflege")
    with db.db() as con:
        ergebnis = anwenden(con, feld, suchart, suchwert.strip(),
                            neuer_wert.strip(), bool(ueberall))

    if not ergebnis["gesamt"]:
        return RedirectResponse(
            "/datenpflege?fehler=Nichts+gefunden%2C+nichts+ge%C3%A4ndert.",
            status_code=303)

    from urllib.parse import urlencode
    quelle = " / ".join(ergebnis["werte"][:4])
    text = (f"{ergebnis['gesamt']} Stellen geändert: „{quelle}“ heißt jetzt "
            f"„{neuer_wert.strip()}“.")
    if sicherung:
        text += f" Sicherung vorher: {sicherung}"
    return RedirectResponse("/datenpflege?" + urlencode({"hinweis": text}),
                            status_code=303)
