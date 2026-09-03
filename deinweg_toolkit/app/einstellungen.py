"""Einstellungen: betreute Personen, Team, Vorgangsarten,
Leistungsbeschreibungen, Benutzer, E-Mail-Zugang und -Vorlagen sowie die
Datensicherung.

Aus main.py ausgelagert, weil dieser Bereich der mit Abstand groesste
zusammenhaengende Teil war. Eingebunden wird das Modul am Ende von main.py
ueber setup() und include_router() - dasselbe Muster wie bei auth.py und
vorgaenge.py, damit es keinen Ringschluss beim Import gibt.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import re
import shutil
import tempfile
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from . import auth, db, kfz, mail, wiki
from .parser import norm, NICHT_ABRECHENBAR

router = APIRouter()

# Von setup() gefuellt: alles, was aus main.py gebraucht wird.
_u: dict = {}


def setup(templates, werte: dict) -> None:
    _u["templates"] = templates
    _u.update(werte)


# Anfuehrungszeichen, die als "schon vorhanden" gelten und beim Einlesen
# abgeraeumt werden - gerade und typografische, deutsche wie englische.
ZITATZEICHEN = '"\'\u201e\u201c\u201d\u201a\u2018\u2019\u00ab\u00bb\u203a\u2039'


def zitat_blank(text: str) -> str:
    """Nimmt einem Spruch die Anfuehrungszeichen ab.

    Die Oberflaeche zeigt und speichert den blanken Text; die Zeichen
    setzt die App beim Schreiben selbst (siehe zitat_gesetzt). So muss
    niemand daran denken, und es steht nie ein doppeltes Paar da.
    """
    text = (text or "").strip()
    while text and text[0] in ZITATZEICHEN:
        text = text[1:].lstrip()
    while text and text[-1] in ZITATZEICHEN:
        text = text[:-1].rstrip()
    return text


def zitat_gesetzt(text: str) -> str:
    """Legt die deutschen Anfuehrungszeichen um einen blanken Spruch."""
    text = zitat_blank(text)
    return f"\u201e{text}\u201c" if text else ""


def sprueche_lesen() -> list[dict]:
    """Alle Sprüche aus quotes.txt, mit Nummer als Schlüssel für Bearbeiten
    und Löschen. Fehlt die Datei, kommt eine leere Liste zurück."""
    try:
        with open(_u["SPRUCH_DATEI"], encoding="utf-8") as f:
            roh = f.read()
    except OSError:
        return []
    bloecke = [b.strip("\n").strip() for b in
              re.split(r"^[ \t]*##[ \t]*$", roh, flags=re.MULTILINE)]
    ergebnis = []
    for nr, block in enumerate(b for b in bloecke if b):
        zeilen = block.splitlines()
        quelle = ""
        if len(zeilen) > 1 and zeilen[-1].lstrip().startswith(("–", "—", "-", "~")):
            quelle = zeilen.pop().lstrip("–—-~ ").strip()
        ergebnis.append({"nr": nr, "text": zitat_blank("\n".join(zeilen)),
                         "quelle": quelle})
    return ergebnis


def sprueche_schreiben(liste: list[dict]) -> str | None:
    """Schreibt quotes.txt komplett neu. Gibt eine Fehlermeldung zurück,
    sonst None."""
    bloecke = []
    for s in liste:
        text = zitat_gesetzt(s["text"])
        if s["quelle"].strip():
            text += f"\n– {s['quelle'].strip()}"
        bloecke.append(text)
    inhalt = "\n##\n".join(bloecke)
    try:
        pfad = _u["SPRUCH_DATEI"]
        os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(inhalt.strip() + "\n" if inhalt.strip() else "")
    except OSError as e:
        return f"Konnte nicht gespeichert werden: {e}"
    return None


def sprueche_zurueck(**werte):
    werte.setdefault("bereich", "quotes")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/spruch")
def spruch_anlegen(text: str = Form(""), quelle: str = Form("")):
    text = zitat_blank(text)
    if not text:
        return sprueche_zurueck(fehler="Ohne Text geht es nicht.")
    if len(text) > 2000:
        return sprueche_zurueck(fehler="Bitte auf 2000 Zeichen kürzen.")
    liste = sprueche_lesen()
    liste.append({"text": text, "quelle": quelle.strip()})
    problem = sprueche_schreiben(liste)
    if problem:
        return sprueche_zurueck(fehler=problem)
    return sprueche_zurueck(hinweis="Spruch gespeichert.")


@router.post("/einstellungen/spruch/{nr}/bearbeiten")
def spruch_bearbeiten(nr: int, text: str = Form(""), quelle: str = Form("")):
    text = zitat_blank(text)
    liste = sprueche_lesen()
    if not 0 <= nr < len(liste):
        return sprueche_zurueck(fehler="Dieser Spruch existiert nicht mehr.")
    if not text:
        return sprueche_zurueck(fehler="Ohne Text geht es nicht.",
                                spruch_bearbeiten=nr)
    if len(text) > 2000:
        return sprueche_zurueck(fehler="Bitte auf 2000 Zeichen kürzen.",
                                spruch_bearbeiten=nr)
    liste[nr] = {"text": text, "quelle": quelle.strip()}
    problem = sprueche_schreiben(liste)
    if problem:
        return sprueche_zurueck(fehler=problem)
    return sprueche_zurueck(hinweis="Spruch geändert.")


@router.post("/einstellungen/spruch/{nr}/loeschen")
def spruch_loeschen(nr: int):
    liste = sprueche_lesen()
    if not 0 <= nr < len(liste):
        return sprueche_zurueck(fehler="Dieser Spruch existiert nicht mehr.")
    liste.pop(nr)
    problem = sprueche_schreiben(liste)
    if problem:
        return sprueche_zurueck(fehler=problem)
    return sprueche_zurueck(hinweis="Spruch entfernt.")


# --- Einstellungen: betreute Personen und Kontingente ------------------------

@router.get("/einstellungen", response_class=HTMLResponse)
def einstellungen(request: Request, bereich: str = "oberflaeche",
                  hinweis: str = "", fehler: str = "",
                  spruch_bearbeiten: int = -1, offen: int = 0):
    ist_admin = request.state.benutzer["rolle"] == "admin"
    if bereich not in ("oberflaeche", "quotes", "betreute", "mitarbeiter",
                       "vorgangsarten", "leistungen", "kfz", "benutzer",
                       "email", "vorlagen", "system"):
        bereich = "oberflaeche"
    # Benutzerverwaltung ist unabhaengig von der allgemeinen
    # "einstellungen"-Berechtigung ausschliesslich Administratoren
    # vorbehalten - sonst koennte sich ein eingeschraenktes Konto selbst
    # Adminrechte erteilen. Die Middleware prueft das bereits fuer die
    # POST-Routen; hier zusaetzlich fuer die Ansicht selbst, weil "bereich"
    # nur ein Abfrageparameter auf derselben Route ist.
    if bereich in ("benutzer", "email", "vorlagen") and not ist_admin:
        bereich = "oberflaeche"
    # Zweite Ebene: einzelne Punkte lassen sich je Konto abschalten.
    # "oberflaeche" bleibt immer erreichbar - deshalb ist das hier auch
    # der Rueckfall. Die POST-Routen deckt die Middleware ab.
    if not auth.hat_einst_zugriff(request.state.benutzer, bereich):
        bereich = auth.EINST_IMMER
    with db.db() as con:
        personen = con.execute(
            "SELECT p.*, "
            "(SELECT COUNT(*) FROM eintrag e WHERE e.klient = p.name) AS eintraege, "
            "(SELECT COALESCE(SUM(dauer_min),0) FROM eintrag e WHERE e.klient = p.name) AS minuten "
            "FROM person p ORDER BY p.aktiv DESC, p.name").fetchall()
        # Die bewilligten Zeitraeume je Person, neueste zuerst - dieselbe
        # Reihenfolge, in der main.kontingent_im_monat() sie auswertet.
        zeitraeume: dict[int, list] = {}
        for z in con.execute(
                "SELECT * FROM person_zeitraum ORDER BY von DESC, id DESC"):
            zeitraeume.setdefault(z["person_id"], []).append(z)
        bekannt = {p["name"] for p in personen}
        ungepflegt = [r["klient"] for r in con.execute(
            "SELECT klient, COUNT(*) c FROM eintrag GROUP BY klient ORDER BY c DESC")
            if r["klient"] not in bekannt and norm(r["klient"]) not in NICHT_ABRECHENBAR]
        team = con.execute(
            "SELECT m.*, "
            "(SELECT COUNT(*) FROM eintrag e WHERE e.mitarbeiter = m.name) AS eintraege, "
            "(SELECT MAX(monat) FROM eintrag e WHERE e.mitarbeiter = m.name) AS letzter_monat "
            "FROM mitarbeiter m ORDER BY m.aktiv DESC, m.name").fetchall()
        team_namen = {norm(m["name"]) for m in team}
        team_offen = [r["mitarbeiter"] for r in con.execute(
            "SELECT mitarbeiter, COUNT(*) c FROM eintrag GROUP BY mitarbeiter ORDER BY c DESC")
            if norm(r["mitarbeiter"]) not in team_namen]
        vorgangsarten = con.execute(
            "SELECT va.*, "
            "(SELECT COUNT(*) FROM vorgang v WHERE v.art = va.name) AS verwendungen "
            "FROM vorgangsart va ORDER BY va.aktiv DESC, va.name COLLATE NOCASE").fetchall()
        arten_bekannt = {a["name"] for a in vorgangsarten}
        arten_offen = [r["art"] for r in con.execute(
            "SELECT art, COUNT(*) c FROM vorgang GROUP BY art ORDER BY c DESC")
            if r["art"] not in arten_bekannt]
        leistungen = con.execute(
            "SELECT l.*, "
            "(SELECT COUNT(*) FROM eintrag e WHERE e.beschreibung = l.name) "
            "AS verwendungen "
            "FROM leistung l ORDER BY l.aktiv DESC, l.name COLLATE NOCASE").fetchall()
        leistungen_bekannt = {le["name"] for le in leistungen}
        # Was in den Daten tatsaechlich schon als Beschreibung steht und
        # sich per Knopfdruck in die Liste uebernehmen laesst - so entsteht
        # die Auswahl aus der eigenen Schreibweise statt aus Erfundenem.
        leistungen_offen = [r["beschreibung"] for r in con.execute(
            "SELECT beschreibung, COUNT(*) c FROM eintrag "
            "WHERE beschreibung IS NOT NULL AND TRIM(beschreibung) <> '' "
            "GROUP BY beschreibung ORDER BY c DESC, beschreibung LIMIT 40")
            if r["beschreibung"] not in leistungen_bekannt][:15]
        # Fuhrpark: aktive und archivierte Fahrzeuge in einer Liste, dazu
        # je Fahrzeug der Umfang seiner Historie - so ist beim Archivieren
        # oder Loeschen sichtbar, woran etwas haengt.
        fahrzeuge = con.execute(
            "SELECT f.*, "
            "(SELECT COUNT(*) FROM fahrzeug_ereignis e WHERE e.fahrzeug_id=f.id) "
            "AS eintraege, "
            "(SELECT MAX(e.datum) FROM fahrzeug_ereignis e "
            " WHERE e.fahrzeug_id=f.id) AS zuletzt "
            "FROM fahrzeug f ORDER BY f.aktiv DESC, f.marke COLLATE NOCASE, "
            "f.modell COLLATE NOCASE, f.kennzeichen COLLATE NOCASE").fetchall()
        km_staende = kfz.km_staende(con)
        benutzerliste = con.execute(
            "SELECT * FROM benutzer ORDER BY aktiv DESC, benutzername COLLATE NOCASE"
        ).fetchall()
        benutzer_zahlen = {
            "aktiv": sum(1 for b in benutzerliste if b["aktiv"]),
            "inaktiv": sum(1 for b in benutzerliste if not b["aktiv"]),
            "admin": sum(1 for b in benutzerliste if b["aktiv"] and b["rolle"] == "admin"),
        }
        # Geschuetzte Wiki-Ordner: die gepflegte Liste und alle Ordner,
        # die im Wiki ueberhaupt zur Wahl stehen. Beides braucht die
        # Benutzerverwaltung - einmal zum Pflegen der Liste, einmal fuer
        # die Haekchen je Konto.
        wiki_geschuetzt = auth.geschuetzte_ordner(con)
        wiki_alle_ordner = [o["pfad"] for o in wiki.ordnerliste()]
        mailkonfig = mail.konfig_lesen(con)
        # Das Passwort verlaesst die Anwendung nicht im Klartext - in der
        # Oberflaeche steht nur, ob eines hinterlegt ist.
        passwort_gesetzt = bool(mailkonfig.get("smtp_passwort"))
        mailkonfig = {k: v for k, v in mailkonfig.items() if k not in mail.GEHEIM}
        letzte_mails = con.execute(
            "SELECT * FROM benachrichtigung ORDER BY gesendet_am DESC, id DESC "
            "LIMIT 15").fetchall()
        zahlen = con.execute(
            "SELECT (SELECT COUNT(*) FROM eintrag) datensaetze, "
            "(SELECT COALESCE(SUM(dauer_min),0) FROM eintrag) minuten, "
            "(SELECT COUNT(*) FROM import) importe, "
            "(SELECT COUNT(*) FROM vorschau) offen, "
            "(SELECT COUNT(DISTINCT mitarbeiter) FROM eintrag) mitarbeiter, "
            "(SELECT COUNT(DISTINCT klient) FROM eintrag) klienten").fetchone()
        aeltester = con.execute("SELECT MIN(monat) m FROM eintrag").fetchone()["m"]
        neuester = con.execute("SELECT MAX(monat) m FROM eintrag").fetchone()["m"]

    def groesse(pfad):
        try:
            bytes_ = os.path.getsize(pfad)
        except OSError:
            return "—"
        for einheit in ("B", "KB", "MB", "GB"):
            if bytes_ < 1024 or einheit == "GB":
                return f"{bytes_:.0f} {einheit}" if einheit == "B" else f"{bytes_:.1f} {einheit}"
            bytes_ /= 1024

    def dateistand(pfad):
        if not os.path.exists(pfad):
            return "fehlt"
        if os.path.getsize(pfad) == 0:
            return "vorhanden, aber leer"
        return f"vorhanden ({groesse(pfad)})"

    def anmeldung_zusammenfassung(zahlen: dict) -> str:
        teile = [f"{zahlen['aktiv']} aktive Konten"]
        if zahlen["admin"]:
            wort = "Administrator" if zahlen["admin"] == 1 else "Administratoren"
            teile.append(f"{zahlen['admin']} davon {wort}")
        if zahlen["inaktiv"]:
            teile.append(f"{zahlen['inaktiv']} deaktiviert")
        return " · ".join(teile)

    system = {
        "version": _u["VERSION"],
        "datensaetze": zahlen["datensaetze"],
        "stunden": zahlen["minuten"],
        "importe": zahlen["importe"],
        "offen": zahlen["offen"],
        "mitarbeiter": zahlen["mitarbeiter"],
        "klienten": zahlen["klienten"],
        "personen": len(personen),
        "fahrzeuge": sum(1 for f in fahrzeuge if f["aktiv"]),
        "fahrzeuge_archiv": sum(1 for f in fahrzeuge if not f["aktiv"]),
        "fahrzeug_eintraege": sum(f["eintraege"] for f in fahrzeuge),
        "zeitraum": (f"{_u["monat_wort"](aeltester)} bis {_u["monat_wort"](neuester)}"
                     if aeltester else "noch keine Daten"),
        "db_pfad": db.DB_PFAD,
        "db_groesse": groesse(db.DB_PFAD),
        "wecker": (f"alle {_u["WECKER_INTERVALL"]} s"
                   if _u["WECKER_INTERVALL"] else "aus"),
        "anmeldung": anmeldung_zusammenfassung(benutzer_zahlen),
        "max_upload": f"{_u["MAX_UPLOAD_MB"]} MB",
        "sicherung_pfad": _u["SICHERUNG_PFAD"],
        "dateien": [
            ("quotes.txt", _u["SPRUCH_DATEI"], dateistand(_u["SPRUCH_DATEI"])),
            ("ideen.txt", _u["IDEEN_DATEI"], dateistand(_u["IDEEN_DATEI"])),
        ],
    }

    # Die woechentlich abgelegten Sicherungen, jüngste zuerst.
    sicherungen = []
    if bereich == "system":
        for name in sorted(_u["sicherungsdateien"](), reverse=True):
            pfad = os.path.join(_u["SICHERUNG_PFAD"], name)
            sicherungen.append({"name": name,
                                "datum": name[11:-3],
                                "groesse": groesse(pfad)})

    # Welcher Zeitraum gilt heute? Nach derselben Regel wie in der
    # Auswertung: der zuletzt begonnene, der heute noch laeuft. Bewusst
    # hier und nicht in der Vorlage - dort muesste man ueber ein leeres
    # "bis" stolpern, und die Regel stuende dann an zwei Stellen.
    # Wie steht jede Person heute da? Gerechnet wird in
    # main.bewilligungslage() - dieselbe Funktion, die auch "Mein
    # Bereich" benutzt, damit beide Seiten nie auseinanderlaufen.
    heute_wert = _u["heute"]()
    aktuell, lage = {}, {}
    for p in personen:
        stand = _u["bewilligungslage"](zeitraeume.get(p["id"], []),
                                       p["wochenstunden"], p["stundensatz"],
                                       heute_wert,
                                       selbstzahler=p["selbstzahler"])
        lage[p["id"]] = stand
        if stand["art"] in ("laufend", "laeuft_aus"):
            aktuell[p["id"]] = stand["zeitraum"]
    # Fuer die Ueberschrift: bei wie vielen aktiven Personen ist etwas zu
    # tun?
    ohne_bewilligung = sum(
        1 for p in personen
        if p["aktiv"] and lage.get(p["id"], {}).get("art") in
        _u["BEWILLIGUNG_HANDLUNG"])

    return _u["templates"].TemplateResponse(
        request=request, name="einstellungen.html", context={
            "personen": personen, "ungepflegt": ungepflegt, "system": system,
            "zeitraeume": zeitraeume, "zeitraum_aktuell": aktuell,
            "zeitraum_lage": lage, "ohne_bewilligung": ohne_bewilligung,
            "offen": offen, "heute": heute_wert,
            "team": team, "team_offen": team_offen,
            "vorgangsarten": vorgangsarten, "arten_offen": arten_offen,
            "leistungen": leistungen, "leistungen_offen": leistungen_offen,
            "fahrzeuge": fahrzeuge, "km_staende": km_staende,
            "kfz_bezeichnung": kfz.bezeichnung,
            "benutzerliste": benutzerliste, "ist_admin": ist_admin,
            "BEREICHE": auth.BEREICHE, "EINST_BEREICHE": auth.EINST_BEREICHE,
            "wiki_geschuetzt": wiki_geschuetzt,
            "wiki_alle_ordner": wiki_alle_ordner,
            "wiki_ordner_lesen": auth.ordnerliste_lesen,
            "NUR_AUSDRUECKLICH": auth.NUR_AUSDRUECKLICH,
            "eigene_id": request.state.benutzer["id"],
            "mailkonfig": mailkonfig, "passwort_gesetzt": passwort_gesetzt,
            "bewilligung_empfaenger":
                mail.empfaengerliste(mailkonfig.get("bewilligung_empfaenger")),
            "frist_kopie": mail.empfaengerliste(mailkonfig.get("frist_kopie")),
            "letzte_mails": letzte_mails,
            "sprueche": sprueche_lesen() if bereich == "quotes" else [],
            "spruch_bearbeiten": spruch_bearbeiten,
            "sicherungen": sicherungen, "fuss_standard": _u["FUSS_STANDARD"],
            "bereich": bereich, "hinweis": hinweis, "fehler": fehler,
            "seite": "einstellungen"})


def einstellungen_zurueck(**werte):
    werte.setdefault("bereich", "betreute")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


def stunden_lesen(wert: str):
    """Nimmt 7,5 und 7.5 gleichermassen an."""
    try:
        zahl = float(str(wert).replace(",", ".").strip() or 0)
    except ValueError:
        return None
    return zahl if 0 <= zahl <= 168 else None


def betrag_lesen(wert: str):
    """Stundensatz in Euro, Komma oder Punkt, optional mit Euro-Zeichen."""
    roh = str(wert or "").replace("€", "").replace(",", ".").strip()
    try:
        zahl = float(roh or 0)
    except ValueError:
        return None
    return round(zahl, 2) if 0 <= zahl <= 10000 else None


@router.post("/einstellungen/person")
def person_anlegen(name: str = Form(""), wochenstunden: str = Form("0"),
                   stundensatz: str = Form("0"), abrechenbar: str = Form(""),
                   selbstzahler: str = Form("")):
    name = name.strip()
    if not name:
        return einstellungen_zurueck(fehler="Ohne Namen geht es nicht.")
    stunden = stunden_lesen(wochenstunden)
    if stunden is None:
        return einstellungen_zurueck(
            fehler="Die Wochenstunden müssen eine Zahl zwischen 0 und 168 sein.")
    satz = betrag_lesen(stundensatz)
    if satz is None:
        return einstellungen_zurueck(
            fehler="Der Stundensatz muss ein Betrag sein, zum Beispiel 42,50.")
    with db.db() as con:
        vorhanden = con.execute("SELECT id FROM person WHERE name=?", (name,)).fetchone()
        if vorhanden:
            return einstellungen_zurueck(
                fehler=f"{name} ist bereits angelegt.")
        con.execute(
            "INSERT INTO person (name, wochenstunden, stundensatz, aktiv, "
            "abrechenbar, selbstzahler, angelegt_am) VALUES (?,?,?,1,?,?,?)",
            (name, stunden, satz, 1 if abrechenbar else 0,
             1 if selbstzahler else 0, _u["jetzt"]()))
    return einstellungen_zurueck(hinweis=f"{name} angelegt.")


@router.post("/einstellungen/person/{person_id}")
def person_speichern(person_id: int, name: str = Form(""),
                     wochenstunden: str = Form("0"), stundensatz: str = Form("0"),
                     abrechenbar: str = Form(""), aktiv: str = Form(""),
                     selbstzahler: str = Form("")):
    name = name.strip()
    if not name:
        return einstellungen_zurueck(fehler="Ohne Namen geht es nicht.")
    stunden = stunden_lesen(wochenstunden)
    if stunden is None:
        return einstellungen_zurueck(
            fehler="Die Wochenstunden müssen eine Zahl zwischen 0 und 168 sein.")
    satz = betrag_lesen(stundensatz)
    if satz is None:
        return einstellungen_zurueck(
            fehler="Der Stundensatz muss ein Betrag sein, zum Beispiel 42,50.")
    with db.db() as con:
        doppelt = con.execute("SELECT id FROM person WHERE name=? AND id<>?",
                              (name, person_id)).fetchone()
        if doppelt:
            return einstellungen_zurueck(fehler=f"{name} ist bereits angelegt.")
        con.execute(
            "UPDATE person SET name=?, wochenstunden=?, stundensatz=?, "
            "abrechenbar=?, aktiv=?, selbstzahler=? WHERE id=?",
            (name, stunden, satz, 1 if abrechenbar else 0, 1 if aktiv else 0,
             1 if selbstzahler else 0, person_id))
    return einstellungen_zurueck(hinweis=f"{name} gespeichert.")


# --- Bewilligte Zeitraeume je betreuter Person -------------------------------
#
# Der Kostentraeger sagt Wochenstunden und Stundensatz nur befristet zu.
# Die beiden Felder an "person" bleiben daneben als Grundwert bestehen und
# gelten fuer jeden Monat, den kein Zeitraum abdeckt - sonst haetten alle
# bisher gepflegten Personen mit einem Schlag kein Kontingent mehr.
# Gerechnet wird in main.kontingent_im_monat().

def zeitraum_zurueck(person_id: int, **werte):
    """Zurueck zur Personenliste, mit der bearbeiteten Person aufgeklappt."""
    werte.setdefault("bereich", "betreute")
    werte["offen"] = person_id
    return RedirectResponse(
        "/einstellungen?" + urlencode(werte) + f"#person-{person_id}",
        status_code=303)


def datum_lesen(wert: str) -> str | None:
    """YYYY-MM-DD aus dem Datumsfeld, oder None wenn unbrauchbar."""
    roh = str(wert or "").strip()
    if not roh:
        return None
    try:
        return dt.date.fromisoformat(roh).isoformat()
    except ValueError:
        return None


def zeitraum_pruefen(von: str, bis: str, wochenstunden: str, stundensatz: str):
    """Gemeinsame Pruefung fuers Anlegen und fuers Speichern.

    Gibt entweder ``(werte, None)`` oder ``(None, Fehlertext)`` zurueck.
    """
    von_datum = datum_lesen(von)
    if not von_datum:
        return None, "Ohne Beginn geht es nicht – trag ein Datum ein."
    bis_datum = datum_lesen(bis)
    if bis and bis_datum is None:
        return None, "Das Ende ist kein gültiges Datum."
    if bis_datum and bis_datum < von_datum:
        return None, "Das Ende liegt vor dem Beginn."
    stunden = stunden_lesen(wochenstunden)
    if stunden is None:
        return None, "Die Wochenstunden müssen eine Zahl zwischen 0 und 168 sein."
    satz = betrag_lesen(stundensatz)
    if satz is None:
        return None, "Der Stundensatz muss ein Betrag sein, zum Beispiel 65,00."
    return (von_datum, bis_datum, stunden, satz), None


@router.post("/einstellungen/person/{person_id}/zeitraum")
def zeitraum_anlegen(person_id: int, von: str = Form(""), bis: str = Form(""),
                     wochenstunden: str = Form("0"),
                     stundensatz: str = Form("0"), notiz: str = Form("")):
    werte, fehler = zeitraum_pruefen(von, bis, wochenstunden, stundensatz)
    if fehler:
        return zeitraum_zurueck(person_id, fehler=fehler)
    von_datum, bis_datum, stunden, satz = werte
    with db.db() as con:
        person = con.execute("SELECT name FROM person WHERE id=?",
                             (person_id,)).fetchone()
        if not person:
            return einstellungen_zurueck(fehler="Diese Person gibt es nicht mehr.")
        con.execute(
            "INSERT INTO person_zeitraum (person_id, von, bis, wochenstunden, "
            "stundensatz, notiz, angelegt_am) VALUES (?,?,?,?,?,?,?)",
            (person_id, von_datum, bis_datum, stunden, satz,
             notiz.strip() or None, _u["jetzt"]()))
    return zeitraum_zurueck(
        person_id, hinweis=f"Zeitraum für {person['name']} angelegt.")


@router.post("/einstellungen/person/zeitraum/{zeitraum_id}")
def zeitraum_speichern(zeitraum_id: int, von: str = Form(""), bis: str = Form(""),
                       wochenstunden: str = Form("0"),
                       stundensatz: str = Form("0"), notiz: str = Form("")):
    with db.db() as con:
        satz_alt = con.execute("SELECT person_id FROM person_zeitraum WHERE id=?",
                               (zeitraum_id,)).fetchone()
    if not satz_alt:
        return einstellungen_zurueck(fehler="Diesen Zeitraum gibt es nicht mehr.")
    person_id = satz_alt["person_id"]
    werte, fehler = zeitraum_pruefen(von, bis, wochenstunden, stundensatz)
    if fehler:
        return zeitraum_zurueck(person_id, fehler=fehler)
    von_datum, bis_datum, stunden, satz = werte
    with db.db() as con:
        con.execute(
            "UPDATE person_zeitraum SET von=?, bis=?, wochenstunden=?, "
            "stundensatz=?, notiz=? WHERE id=?",
            (von_datum, bis_datum, stunden, satz, notiz.strip() or None,
             zeitraum_id))
    return zeitraum_zurueck(person_id, hinweis="Zeitraum gespeichert.")


@router.post("/einstellungen/person/zeitraum/{zeitraum_id}/loeschen")
def zeitraum_loeschen(zeitraum_id: int):
    with db.db() as con:
        satz = con.execute("SELECT person_id FROM person_zeitraum WHERE id=?",
                           (zeitraum_id,)).fetchone()
        if not satz:
            return einstellungen_zurueck(fehler="Diesen Zeitraum gibt es nicht mehr.")
        con.execute("DELETE FROM person_zeitraum WHERE id=?", (zeitraum_id,))
    return zeitraum_zurueck(satz["person_id"], hinweis="Zeitraum entfernt.")


@router.post("/einstellungen/person/{person_id}/loeschen")
def person_loeschen(person_id: int):
    with db.db() as con:
        satz = con.execute("SELECT name FROM person WHERE id=?", (person_id,)).fetchone()
        con.execute("DELETE FROM person WHERE id=?", (person_id,))
    name = satz["name"] if satz else "Der Eintrag"
    return einstellungen_zurueck(
        hinweis=f"{name} aus den Stammdaten entfernt. Erfasste Zeiten bleiben bestehen.")


# --- Mitarbeiterverwaltung ---------------------------------------------------

def team_zurueck(**werte):
    werte.setdefault("bereich", "mitarbeiter")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/mitarbeiter")
def mitarbeiter_anlegen(name: str = Form(""), notiz: str = Form(""),
                        monatsstunden: str = Form("0"),
                        urlaubstage: str = Form("0"),
                        abgabepflicht: str = Form("1")):
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return team_zurueck(fehler="Ohne Namen geht es nicht.")
    soll = betrag_lesen(monatsstunden)
    if soll is None:
        return team_zurueck(fehler="Die Monatsstunden sind keine gültige Zahl.")
    urlaub = betrag_lesen(urlaubstage)
    if urlaub is None:
        return team_zurueck(fehler="Die Urlaubstage sind keine gültige Zahl.")
    with db.db() as con:
        schon_da = con.execute(
            "SELECT name FROM mitarbeiter").fetchall()
        if any(norm(r["name"]) == norm(name) for r in schon_da):
            return team_zurueck(fehler=f"{name} steht bereits im Team.")
        con.execute(
            "INSERT INTO mitarbeiter (name, aktiv, abgabepflicht, monatsstunden, "
            "urlaubstage, notiz, angelegt_am) VALUES (?,1,?,?,?,?,?)",
            (name, 1 if abgabepflicht else 0, soll, urlaub, notiz.strip(), _u["jetzt"]()))
    return team_zurueck(hinweis=f"{name} ins Team aufgenommen.")


@router.post("/einstellungen/mitarbeiter/{person_id}")
def mitarbeiter_speichern(person_id: int, name: str = Form(""),
                          notiz: str = Form(""), aktiv: str = Form(""),
                          monatsstunden: str = Form("0"),
                          urlaubstage: str = Form("0"),
                          abgabepflicht: str = Form("")):
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return team_zurueck(fehler="Ohne Namen geht es nicht.")
    soll = betrag_lesen(monatsstunden)
    if soll is None:
        return team_zurueck(fehler="Die Monatsstunden sind keine gültige Zahl.")
    urlaub = betrag_lesen(urlaubstage)
    if urlaub is None:
        return team_zurueck(fehler="Die Urlaubstage sind keine gültige Zahl.")
    with db.db() as con:
        andere = con.execute("SELECT name FROM mitarbeiter WHERE id<>?",
                             (person_id,)).fetchall()
        if any(norm(r["name"]) == norm(name) for r in andere):
            return team_zurueck(fehler=f"{name} steht bereits im Team.")
        con.execute(
            "UPDATE mitarbeiter SET name=?, notiz=?, aktiv=?, abgabepflicht=?, "
            "monatsstunden=?, urlaubstage=? WHERE id=?",
            (name, notiz.strip(), 1 if aktiv else 0,
             1 if abgabepflicht else 0, soll, urlaub, person_id))
    return team_zurueck(hinweis=f"{name} gespeichert.")


@router.post("/einstellungen/mitarbeiter/{person_id}/loeschen")
def mitarbeiter_loeschen(person_id: int):
    with db.db() as con:
        satz = con.execute("SELECT name FROM mitarbeiter WHERE id=?",
                           (person_id,)).fetchone()
        con.execute("DELETE FROM mitarbeiter WHERE id=?", (person_id,))
    name = satz["name"] if satz else "Der Eintrag"
    return team_zurueck(
        hinweis=f"{name} aus dem Team entfernt. Erfasste Zeiten bleiben bestehen.")


# --- Vorgangsarten (Verwaltungsvorgänge) -------------------------------------
#
# Ersetzt seit dieser Version die frueher fest im Code hinterlegte Liste in
# vorgaenge.py. Deaktivieren statt Loeschen ist hier besonders wichtig, weil
# vorgang.art ein reines Textfeld ist: eine geloeschte Art wuerde an
# bestehenden Vorgaengen einfach als "nicht mehr in der Liste" stehen bleiben,
# eine deaktivierte bleibt dagegen im Bearbeiten-Formular auswaehlbar
# (siehe vorgaenge.vorgangsarten_liste).

def vorgangsarten_zurueck(**werte):
    werte.setdefault("bereich", "vorgangsarten")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/vorgangsart")
def vorgangsart_anlegen(name: str = Form("")):
    name = name.strip()
    if not name:
        return vorgangsarten_zurueck(fehler="Ohne Bezeichnung geht es nicht.")
    with db.db() as con:
        vorhanden = con.execute(
            "SELECT id FROM vorgangsart WHERE name=?", (name,)).fetchone()
        if vorhanden:
            return vorgangsarten_zurueck(fehler=f"„{name}“ ist bereits angelegt.")
        con.execute(
            "INSERT INTO vorgangsart (name, aktiv, angelegt_am) VALUES (?,1,?)",
            (name, _u["jetzt"]()))
    return vorgangsarten_zurueck(hinweis=f"„{name}“ angelegt.")


@router.post("/einstellungen/vorgangsart/{art_id}")
def vorgangsart_speichern(art_id: int, name: str = Form(""),
                          aktiv: str = Form("")):
    name = name.strip()
    if not name:
        return vorgangsarten_zurueck(fehler="Ohne Bezeichnung geht es nicht.")
    with db.db() as con:
        doppelt = con.execute(
            "SELECT id FROM vorgangsart WHERE name=? AND id<>?",
            (name, art_id)).fetchone()
        if doppelt:
            return vorgangsarten_zurueck(fehler=f"„{name}“ ist bereits angelegt.")
        con.execute(
            "UPDATE vorgangsart SET name=?, aktiv=? WHERE id=?",
            (name, 1 if aktiv else 0, art_id))
    return vorgangsarten_zurueck(hinweis=f"„{name}“ gespeichert.")


@router.post("/einstellungen/vorgangsart/{art_id}/loeschen")
def vorgangsart_loeschen(art_id: int):
    with db.db() as con:
        satz = con.execute(
            "SELECT name FROM vorgangsart WHERE id=?", (art_id,)).fetchone()
        verwendet = 0
        if satz:
            verwendet = con.execute(
                "SELECT COUNT(*) c FROM vorgang WHERE art=?",
                (satz["name"],)).fetchone()["c"]
        con.execute("DELETE FROM vorgangsart WHERE id=?", (art_id,))
    name = satz["name"] if satz else "Der Eintrag"
    if verwendet:
        return vorgangsarten_zurueck(
            hinweis=f"„{name}“ entfernt. Betroffene Vorgänge ({verwendet}) "
                   "behalten die Bezeichnung unverändert.")
    return vorgangsarten_zurueck(hinweis=f"„{name}“ entfernt.")


# --- Leistungsbeschreibungen (manuelle Erfassung) -----------------------------
#
# Reine Schreibhilfe: die Eintraege stehen auf der Seite "Manueller Eintrag"
# als Auswahl zur Verfuegung, damit dieselbe Leistung im Team nicht in fuenf
# Schreibweisen im Bestand landet. Gespeichert wird weiterhin nur der
# Klartext in eintrag.beschreibung - eine geaenderte oder geloeschte
# Bezeichnung wirkt sich deshalb nie rueckwirkend auf bestehende Zeiten aus.

def leistungen_zurueck(**werte):
    werte.setdefault("bereich", "leistungen")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/leistung")
def leistung_anlegen(name: str = Form("")):
    name = " ".join(name.split())
    if not name:
        return leistungen_zurueck(fehler="Ohne Bezeichnung geht es nicht.")
    with db.db() as con:
        vorhanden = con.execute(
            "SELECT id FROM leistung WHERE name=?", (name,)).fetchone()
        if vorhanden:
            return leistungen_zurueck(fehler=f"„{name}“ ist bereits angelegt.")
        con.execute(
            "INSERT INTO leistung (name, aktiv, angelegt_am) VALUES (?,1,?)",
            (name, _u["jetzt"]()))
    return leistungen_zurueck(hinweis=f"„{name}“ angelegt.")


@router.post("/einstellungen/leistung/{leistung_id}")
def leistung_speichern(leistung_id: int, name: str = Form(""),
                       aktiv: str = Form("")):
    name = " ".join(name.split())
    if not name:
        return leistungen_zurueck(fehler="Ohne Bezeichnung geht es nicht.")
    with db.db() as con:
        doppelt = con.execute(
            "SELECT id FROM leistung WHERE name=? AND id<>?",
            (name, leistung_id)).fetchone()
        if doppelt:
            return leistungen_zurueck(fehler=f"„{name}“ ist bereits angelegt.")
        con.execute(
            "UPDATE leistung SET name=?, aktiv=? WHERE id=?",
            (name, 1 if aktiv else 0, leistung_id))
    return leistungen_zurueck(hinweis=f"„{name}“ gespeichert.")


@router.post("/einstellungen/leistung/{leistung_id}/loeschen")
def leistung_loeschen(leistung_id: int):
    with db.db() as con:
        satz = con.execute(
            "SELECT name FROM leistung WHERE id=?", (leistung_id,)).fetchone()
        con.execute("DELETE FROM leistung WHERE id=?", (leistung_id,))
    name = satz["name"] if satz else "Der Eintrag"
    return leistungen_zurueck(
        hinweis=f"„{name}“ aus der Auswahl entfernt. Bereits erfasste Zeiten "
                "behalten ihre Beschreibung.")


# --- Benutzerverwaltung -------------------------------------------------------
#
# Zugriff auf diese Routen ist bereits durch auth.SessionAuth auf die Rolle
# "admin" beschraenkt (siehe auth.ADMIN_NUR_PFADE) - hier wird das bewusst
# nicht nochmal einzeln geprueft, um genau eine Stelle fuer diese Regel zu
# haben statt sie an mehreren Stellen synchron halten zu muessen.
#
# "mitarbeiter" (Team fuer die Abgabeuebersicht) und "benutzer" (Login-Konten)
# bleiben getrennt: ein neues Konto hier legt keinen Mitarbeiter an und
# umgekehrt.

def benutzer_zurueck(**werte):
    werte.setdefault("bereich", "benutzer")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


def aktive_admins(con, ausser_id: int | None = None) -> int:
    if ausser_id is None:
        return con.execute(
            "SELECT COUNT(*) c FROM benutzer WHERE rolle='admin' AND aktiv=1"
        ).fetchone()["c"]
    return con.execute(
        "SELECT COUNT(*) c FROM benutzer WHERE rolle='admin' AND aktiv=1 AND id<>?",
        (ausser_id,)).fetchone()["c"]


@router.post("/einstellungen/wiki-geschuetzt")
def wiki_geschuetzt_speichern(ordner: list[str] = Form([])):
    """Welche Wiki-Ordner sind geschuetzt?

    ⚠️ Steht bewusst in der Benutzerverwaltung und nicht bei den
    Einstellungen zum Wiki: es ist eine Frage von Rechten, keine von
    Darstellung, und die Seite ist ohnehin schon Administratoren
    vorbehalten (auth.ADMIN_NUR_PFADE).

    ⚠️ Wird ein Ordner aus der Liste genommen, bleiben die Freigaben der
    einzelnen Konten stehen. Das ist Absicht: wer ihn versehentlich
    herausnimmt und wieder hineinsetzt, findet seine Zuteilung
    unveraendert vor. Gespeichert wird ohnehin nur, was in der Liste
    steht (auth.wiki_ordner_speichern).
    """
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "wiki_geschuetzt": ",".join(auth.ordnerliste_lesen(",".join(ordner))),
        })
    return benutzer_zurueck(hinweis="Geschützte Wiki-Ordner gespeichert.")


@router.post("/einstellungen/benutzer")
def benutzer_anlegen(benutzername: str = Form(""), passwort: str = Form(""),
                     rolle: str = Form("benutzer"), email: str = Form(""),
                     mitarbeiter: str = Form(""),
                     fremde_loeschen: str = Form(""),
                     fremde_bearbeiten: str = Form(""),
                     wiki_schreiben: str = Form(""),
                     bewilligungen_sehen: str = Form(""),
                     bereiche: list[str] = Form([]),
                     einst_bereiche: list[str] = Form([]),
                     wiki_ordner: list[str] = Form([])):
    benutzername = benutzername.strip()
    email = email.strip()
    mitarbeiter = mitarbeiter.strip()
    rolle = rolle if rolle in ("admin", "benutzer") else "benutzer"
    if not benutzername:
        return benutzer_zurueck(fehler="Ohne Benutzernamen geht es nicht.")
    if not passwort:
        return benutzer_zurueck(fehler="Ohne Passwort geht es nicht.")
    with db.db() as con:
        vorhanden = con.execute(
            "SELECT id FROM benutzer WHERE benutzername=?", (benutzername,)).fetchone()
        if vorhanden:
            return benutzer_zurueck(fehler=f"„{benutzername}“ ist bereits vergeben.")
        # ⚠️ Die laufende Version gilt fuer ein neues Konto als gesehen -
        # sonst begruesste die Anwendung eine neue Kollegin mit dem
        # Changelog einer Fassung, die sie nie anders kannte.
        con.execute(
            "INSERT INTO benutzer (benutzername, passwort_hash, rolle, "
            "berechtigungen, email, mitarbeiter, fremde_loeschen, "
            "fremde_bearbeiten, wiki_schreiben, bewilligungen_sehen, "
            "einst_bereiche, wiki_ordner, gesehen_version, angelegt_am) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (benutzername, db.passwort_hashen(passwort), rolle,
             auth.berechtigungen_speichern(bereiche), email or None,
             mitarbeiter or None, 1 if fremde_loeschen else 0,
             1 if fremde_bearbeiten else 0,
             1 if wiki_schreiben else 0, 1 if bewilligungen_sehen else 0,
             auth.einst_bereiche_speichern(einst_bereiche),
             auth.wiki_ordner_speichern(wiki_ordner,
                                        auth.geschuetzte_ordner(con)),
             _u["VERSION"], _u["jetzt"]()))
    return benutzer_zurueck(hinweis=f"„{benutzername}“ angelegt.")


@router.post("/einstellungen/benutzer/{benutzer_id}")
def benutzer_speichern(benutzer_id: int, benutzername: str = Form(""),
                       rolle: str = Form("benutzer"), email: str = Form(""),
                       mitarbeiter: str = Form(""),
                       aktiv: str = Form(""), neues_passwort: str = Form(""),
                       fremde_loeschen: str = Form(""),
                       fremde_bearbeiten: str = Form(""),
                       wiki_schreiben: str = Form(""),
                       bewilligungen_sehen: str = Form(""),
                       bereiche: list[str] = Form([]),
                       einst_bereiche: list[str] = Form([]),
                       wiki_ordner: list[str] = Form([])):
    benutzername = benutzername.strip()
    email = email.strip()
    mitarbeiter = mitarbeiter.strip()
    rolle = rolle if rolle in ("admin", "benutzer") else "benutzer"
    aktiv_neu = bool(aktiv)
    if not benutzername:
        return benutzer_zurueck(fehler="Ohne Benutzernamen geht es nicht.")

    with db.db() as con:
        satz = con.execute("SELECT * FROM benutzer WHERE id=?", (benutzer_id,)).fetchone()
        if not satz:
            return benutzer_zurueck(fehler="Dieses Konto gibt es nicht mehr.")
        doppelt = con.execute(
            "SELECT id FROM benutzer WHERE benutzername=? AND id<>?",
            (benutzername, benutzer_id)).fetchone()
        if doppelt:
            return benutzer_zurueck(fehler=f"„{benutzername}“ ist bereits vergeben.")

        wird_kein_aktiver_admin = (rolle != "admin" or not aktiv_neu) and satz["rolle"] == "admin"
        if wird_kein_aktiver_admin and aktive_admins(con, ausser_id=benutzer_id) == 0:
            return benutzer_zurueck(fehler=(
                "Das war der letzte aktive Administrator. Mindestens ein "
                "aktives Administratorkonto muss erhalten bleiben."))

        felder = {"benutzername": benutzername, "rolle": rolle,
                  "email": email or None, "aktiv": 1 if aktiv_neu else 0,
                  "mitarbeiter": mitarbeiter or None,
                  "fremde_loeschen": 1 if fremde_loeschen else 0,
                  "fremde_bearbeiten": 1 if fremde_bearbeiten else 0,
                  "wiki_schreiben": 1 if wiki_schreiben else 0,
                  "bewilligungen_sehen": 1 if bewilligungen_sehen else 0,
                  "berechtigungen": auth.berechtigungen_speichern(bereiche),
                  "einst_bereiche": auth.einst_bereiche_speichern(einst_bereiche),
                  "wiki_ordner": auth.wiki_ordner_speichern(
                      wiki_ordner, auth.geschuetzte_ordner(con))}
        if neues_passwort:
            felder["passwort_hash"] = db.passwort_hashen(neues_passwort)
        satzstueck = ", ".join(f"{k}=?" for k in felder)
        con.execute(f"UPDATE benutzer SET {satzstueck} WHERE id=?",
                    [*felder.values(), benutzer_id])
        if not aktiv_neu:
            con.execute("DELETE FROM sitzung WHERE benutzer_id=?", (benutzer_id,))
    text = f"„{benutzername}“ gespeichert."
    if neues_passwort:
        text += " Neues Passwort gesetzt."
    return benutzer_zurueck(hinweis=text)


@router.post("/einstellungen/benutzer/{benutzer_id}/loeschen")
def benutzer_loeschen(request: Request, benutzer_id: int):
    if benutzer_id == request.state.benutzer["id"]:
        return benutzer_zurueck(fehler="Das eigene Konto kann nicht gelöscht werden.")
    with db.db() as con:
        satz = con.execute("SELECT * FROM benutzer WHERE id=?", (benutzer_id,)).fetchone()
        if not satz:
            return benutzer_zurueck(fehler="Dieses Konto gibt es nicht mehr.")
        if (satz["rolle"] == "admin" and satz["aktiv"]
                and aktive_admins(con, ausser_id=benutzer_id) == 0):
            return benutzer_zurueck(fehler=(
                "Das war der letzte aktive Administrator. Mindestens ein "
                "aktives Administratorkonto muss erhalten bleiben."))
        con.execute("DELETE FROM benutzer WHERE id=?", (benutzer_id,))
    return benutzer_zurueck(hinweis=f"„{satz['benutzername']}“ gelöscht.")


# --- E-Mail-Einstellungen und Vorlagen ---------------------------------------
#
# Nur fuer Administratoren (auth.ADMIN_NUR_PFADE). Das SMTP-Passwort wird
# beim Speichern nur ueberschrieben, wenn tatsaechlich eines eingegeben
# wurde - so kann man Server oder Absender aendern, ohne das Passwort
# jedes Mal neu eintippen zu muessen.

def email_zurueck(bereich: str = "email", **werte):
    werte.setdefault("bereich", bereich)
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/email")
def email_speichern(smtp_absender: str = Form(""), smtp_absendername: str = Form(""),
                    smtp_server: str = Form(""), smtp_port: str = Form("465"),
                    smtp_benutzer: str = Form(""), smtp_passwort: str = Form(""),
                    smtp_sicherheit: str = Form("ssl"), mail_aktiv: str = Form("")):
    werte = {
        "smtp_absender": smtp_absender.strip(),
        "smtp_absendername": smtp_absendername.strip(),
        "smtp_server": smtp_server.strip(),
        "smtp_port": smtp_port.strip() or "465",
        "smtp_benutzer": smtp_benutzer.strip(),
        "smtp_sicherheit": smtp_sicherheit if smtp_sicherheit in
                           ("ssl", "starttls", "keine") else "ssl",
        "mail_aktiv": "1" if mail_aktiv else "0",
    }
    if smtp_passwort:
        werte["smtp_passwort"] = smtp_passwort
    with db.db() as con:
        mail.konfig_schreiben(con, werte)
    return email_zurueck(hinweis="Zugangsdaten gespeichert.")


def namensliste(werte: list[str]) -> list[str]:
    """Aus mehreren Kaestchenfeldern eine Namensliste ohne Dubletten.

    Eine Stelle fuer alle drei E-Mail-Anlaesse - sonst stuende dieselbe
    Schleife dreimal da und liefe frueher oder spaeter auseinander.
    """
    namen: list[str] = []
    for wert in werte:
        for teil in wert.split(","):
            teil = teil.strip()
            if teil and teil not in namen:
                namen.append(teil)
    return namen


@router.post("/einstellungen/bewilligungsmail")
def bewilligungsmail_speichern(bewilligung_aktiv: str = Form(""),
                               bewilligung_tage: str = Form("60"),
                               bewilligung_empfaenger: list[str] = Form([])):
    """Mehrere Empfaenger, kommagetrennt gespeichert.

    Die Namen kommen als Kaestchenliste herein, also als mehrere Felder
    desselben Namens. Gespeichert wird daraus ein Klartextfeld - dieselbe
    Form wie bei ``berechtigungen``; eine eigene Tabelle waere fuer eine
    Handvoll Namen zu viel.
    """
    try:
        tage = max(1, min(365, int(bewilligung_tage or 60)))
    except ValueError:
        return email_zurueck(fehler="Der Vorlauf muss eine Zahl in Tagen sein.")
    namen = namensliste(bewilligung_empfaenger)
    if bewilligung_aktiv and not namen:
        return email_zurueck(fehler=(
            "Ohne Empfänger kann die Erinnerung nicht verschickt werden."))
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "bewilligung_aktiv": "1" if bewilligung_aktiv else "0",
            "bewilligung_tage": str(tage),
            "bewilligung_empfaenger": ", ".join(namen),
        })
    return email_zurueck(hinweis="Erinnerung an Bewilligungen gespeichert.")


@router.post("/einstellungen/fristmail")
def fristmail_speichern(frist_aktiv: str = Form(""),
                        frist_vorlauf: str = Form("0"),
                        frist_kopie: list[str] = Form([])):
    """Erinnerungen aus der Aufgabenverwaltung."""
    try:
        vorlauf = max(0, min(365, int(frist_vorlauf or 0)))
    except ValueError:
        return email_zurueck(fehler="Der Vorlauf muss eine Zahl in Tagen sein.")
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "frist_aktiv": "1" if frist_aktiv else "0",
            "frist_vorlauf": str(vorlauf),
            "frist_kopie": ", ".join(namensliste(frist_kopie)),
        })
    return email_zurueck(hinweis="Erinnerung an Fristen gespeichert.")


@router.post("/einstellungen/abgabemail")
def abgabemail_speichern(abgabe_aktiv: str = Form(""),
                         abgabe_tag: str = Form("1")):
    """Erinnerung an die fehlende Monatsabgabe."""
    try:
        tag = max(1, min(28, int(abgabe_tag or 1)))
    except ValueError:
        return email_zurueck(fehler="Der Stichtag muss ein Tag zwischen 1 und 28 sein.")
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "abgabe_aktiv": "1" if abgabe_aktiv else "0",
            "abgabe_tag": str(tag),
        })
    return email_zurueck(hinweis="Erinnerung an die Zeiterfassung gespeichert.")


@router.post("/einstellungen/zuweisungsmail")
def zuweisungsmail_speichern(zuweisung_aktiv: str = Form(""),
                             zuweisung_verzug: str = Form("2")):
    """Mail an die zustaendige Person bei neu zugewiesenen Aufgaben.

    Der Verzug sammelt mehrere kurz nacheinander angelegte Aufgaben in
    eine Mail (siehe mail.pruefe_zuweisungen).
    """
    try:
        verzug = max(0, min(1440, int(zuweisung_verzug or 0)))
    except ValueError:
        return email_zurueck(fehler=(
            "Der Sammelverzug muss eine Zahl zwischen 0 und 1440 Minuten sein."))
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "zuweisung_aktiv": "1" if zuweisung_aktiv else "0",
            "zuweisung_verzug": str(verzug),
        })
    return email_zurueck(hinweis="Erinnerung an neue Aufgaben gespeichert.")


@router.post("/einstellungen/email/test")
def email_test(request: Request, empfaenger: str = Form("")):
    empfaenger = empfaenger.strip() or (request.state.benutzer["email"] or "")
    if not empfaenger:
        return email_zurueck(fehler=(
            "Keine Empfängeradresse. Trage eine Adresse ein oder hinterlege "
            "eine E-Mail-Adresse bei deinem eigenen Benutzerkonto."))
    erfolg, meldung = mail.senden(
        empfaenger, "Testnachricht aus dem Dein Weg Toolkit",
        "Diese Testnachricht bestätigt, dass der E-Mail-Versand funktioniert.\n\n"
        "Wenn du sie erhalten hast, sind die Zugangsdaten korrekt hinterlegt.")
    if erfolg:
        return email_zurueck(hinweis=f"Testnachricht an {empfaenger} verschickt.")
    return email_zurueck(fehler=f"Versand fehlgeschlagen – {meldung}")


@router.post("/einstellungen/email/pruefen")
def email_pruefen():
    """Beide Prüfungen sofort ausführen, statt auf den Wecker zu warten."""
    zeilen = mail.durchlauf()
    return email_zurueck(hinweis="Prüfung gelaufen: " + " · ".join(zeilen[:4]))


@router.post("/einstellungen/vorlagen")
def vorlagen_speichern(vorlage_frist_betreff: str = Form(""),
                       vorlage_frist_text: str = Form(""),
                       vorlage_abgabe_betreff: str = Form(""),
                       vorlage_abgabe_text: str = Form(""),
                       vorlage_bewilligung_betreff: str = Form(""),
                       vorlage_bewilligung_text: str = Form(""),
                       vorlage_zuweisung_betreff: str = Form(""),
                       vorlage_zuweisung_text: str = Form("")):
    werte = {
        "vorlage_frist_betreff": vorlage_frist_betreff.strip(),
        "vorlage_frist_text": vorlage_frist_text.replace("\r\n", "\n").strip(),
        "vorlage_abgabe_betreff": vorlage_abgabe_betreff.strip(),
        "vorlage_abgabe_text": vorlage_abgabe_text.replace("\r\n", "\n").strip(),
        "vorlage_bewilligung_betreff": vorlage_bewilligung_betreff.strip(),
        "vorlage_bewilligung_text":
            vorlage_bewilligung_text.replace("\r\n", "\n").strip(),
        "vorlage_zuweisung_betreff": vorlage_zuweisung_betreff.strip(),
        "vorlage_zuweisung_text":
            vorlage_zuweisung_text.replace("\r\n", "\n").strip(),
    }
    leer = [k for k, v in werte.items() if not v]
    if leer:
        return email_zurueck("vorlagen", fehler=(
            "Betreff und Text dürfen nicht leer sein."))
    with db.db() as con:
        mail.konfig_schreiben(con, werte)
    return email_zurueck("vorlagen", hinweis="Vorlagen gespeichert.")


@router.post("/einstellungen/vorlagen/zuruecksetzen")
def vorlagen_zuruecksetzen():
    with db.db() as con:
        mail.konfig_schreiben(con, {
            k: v for k, v in mail.STANDARD.items() if k.startswith("vorlage_")})
    return email_zurueck("vorlagen", hinweis="Vorlagen auf den Auslieferungsstand "
                                             "zurückgesetzt.")


# --- Datenbank sichern und zurückspielen --------------------------------------

@router.get("/einstellungen/sicherung")
def sicherung_herunterladen():
    """Sichere Kopie der Datenbank, auch wenn gerade geschrieben wird.

    sqlite3.backup() statt einfachem Kopieren der Datei: bei aktivem
    WAL-Modus liegen Teile der Daten sonst in Nebendateien und die Kopie
    waere unvollstaendig.
    """
    import sqlite3 as _sqlite
    puffer = io.BytesIO()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
        ziel = _sqlite.connect(tmp.name)
        with db.db() as con, ziel:
            con.backup(ziel)
        ziel.close()
        with open(tmp.name, "rb") as f:
            puffer.write(f.read())
    puffer.seek(0)
    name = f"deinweg-toolkit-sicherung-{dt.datetime.now():%Y%m%d-%H%M}.db"
    return StreamingResponse(
        puffer, media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/einstellungen/fusszeile")
def fusszeile_speichern(fusszeile_recht: str = Form("")):
    """Nur noch die Rechtezeile.

    ⚠️ Der Satz unter dem Logo ist mit 1.17.1 aus der Fusszeile entfallen;
    das Feld dafuer musste deshalb mit weg. Ein Eingabefeld, dessen Wert
    nirgends mehr erscheint, ist schlimmer als gar keines. Der alte Wert
    bleibt in ``konfig`` unangetastet stehen - falls der Satz je
    zurueckkommt, ist er nicht verloren.
    """
    with db.db() as con:
        mail.konfig_schreiben(con, {
            "fusszeile_recht": fusszeile_recht.strip(),
        })
    return systemseite(hinweis="Fußzeile gespeichert.")


@router.post("/einstellungen/texte")
def texte_nachziehen(modus: str = Form("fehlende")):
    """Schreibt die Standardtexte in die vorhandene strings.txt.

    ⚠️ Ohne das hier erreicht jede Textänderung, die mit einer neuen
    Fassung kommt, eine bestehende Installation NIE: strings.txt gewinnt
    gegen die Standardtexte, und angelegt wird sie nur, wenn sie fehlt.
    Das ist der stillste Fehler im ganzen System - man sieht ihm nicht an,
    dass etwas fehlt.

    "fehlende" ergaenzt nur, was noch nicht drinsteht - eigene Formu-
    lierungen bleiben dabei unangetastet. "alle" setzt auf den
    Auslieferungsstand zurueck.
    """
    pfad = _u["STRINGS_DATEI"]
    standard = _u["TEXTE_STANDARD"]
    vorhanden: dict[str, str] = {}
    try:
        with open(pfad, encoding="utf-8") as f:
            for zeile in f:
                if zeile.startswith("#") or "=" not in zeile:
                    continue
                schluessel, wert = zeile.split("=", 1)
                vorhanden[schluessel.strip()] = wert.strip()
    except OSError:
        vorhanden = {}

    if modus == "alle":
        neu = dict(standard)
        zahl = len(neu)
    else:
        fehlend = {k: v for k, v in standard.items() if k not in vorhanden}
        neu = {**vorhanden, **fehlend}
        zahl = len(fehlend)

    if not zahl:
        return systemseite(hinweis="Es fehlte nichts – alle Texte sind vorhanden.")
    try:
        os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("# Texte der Oberfläche. Eine Zeile je Schlüssel.\n")
            f.write("# Was hier steht, gewinnt gegen die eingebauten Texte.\n\n")
            for schluessel in sorted(neu):
                f.write(f"{schluessel} = {neu[schluessel]}\n")
    except OSError as e:
        return systemseite(fehler=f"Konnte {pfad} nicht schreiben: {e}")

    return systemseite(hinweis=(
        f"{zahl} Texte auf den Auslieferungsstand gesetzt."
        if modus == "alle" else f"{zahl} fehlende Texte ergänzt."))


def systemseite(**werte):
    werte.setdefault("bereich", "system")
    return RedirectResponse("/einstellungen?" + urlencode(werte), status_code=303)


@router.post("/einstellungen/sicherung")
async def sicherung_einspielen(datei: UploadFile = File(...),
                               bestaetigt: str = Form("")):
    if not bestaetigt:
        return RedirectResponse(
            "/einstellungen?" + urlencode({
                "bereich": "system",
                "fehler": "Bitte das Kästchen zur Bestätigung ankreuzen."}),
            status_code=303)

    roh = await datei.read()
    if not roh:
        return RedirectResponse(
            "/einstellungen?" + urlencode({
                "bereich": "system", "fehler": "Die Datei ist leer."}),
            status_code=303)

    # Vor dem Einspielen pruefen, ob es ueberhaupt eine Toolkit-Datenbank
    # ist - sonst steht man hinterher ohne Daten da.
    import sqlite3 as _sqlite
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(roh)
        pruefpfad = tmp.name
    try:
        pruef = _sqlite.connect(pruefpfad)
        tabellen = {r[0] for r in pruef.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        anzahl = pruef.execute("SELECT COUNT(*) FROM eintrag").fetchone()[0]
        pruef.close()
    except Exception as e:
        os.unlink(pruefpfad)
        return RedirectResponse(
            "/einstellungen?" + urlencode({
                "bereich": "system",
                "fehler": f"Das ist keine lesbare SQLite-Datenbank ({e})."}),
            status_code=303)

    fehlend = {"eintrag", "person", "mitarbeiter"} - tabellen
    if fehlend:
        os.unlink(pruefpfad)
        return RedirectResponse(
            "/einstellungen?" + urlencode({
                "bereich": "system",
                "fehler": "Die Datei sieht nicht nach einer Timetool-Sicherung "
                          f"aus (fehlende Tabellen: {', '.join(sorted(fehlend))})."}),
            status_code=303)

    # Die bisherige Datenbank zur Sicherheit daneben legen, nicht ueberschreiben
    stempel = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    beiseite = f"{db.DB_PFAD}.vor-import-{stempel}"
    try:
        import shutil
        shutil.copy2(db.DB_PFAD, beiseite)
        for anhang in ("-wal", "-shm"):
            if os.path.exists(db.DB_PFAD + anhang):
                os.remove(db.DB_PFAD + anhang)
        shutil.move(pruefpfad, db.DB_PFAD)
    except OSError as e:
        if os.path.exists(pruefpfad):
            os.unlink(pruefpfad)
        return RedirectResponse(
            "/einstellungen?" + urlencode({
                "bereich": "system", "fehler": f"Einspielen fehlgeschlagen: {e}"}),
            status_code=303)

    db.init()
    return RedirectResponse(
        "/einstellungen?" + urlencode({
            "bereich": "system",
            "hinweis": f"Sicherung eingespielt ({anzahl} Datensätze). Die "
                       f"vorherige Datenbank liegt als {os.path.basename(beiseite)} "
                       "daneben. Bitte neu anmelden."}),
        status_code=303)


