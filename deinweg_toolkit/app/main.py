"""Dein Weg Toolkit

Zeitlisten aus xlsx/csv zusammenfuehren, pruefen und als Nachweis exportieren.
Eingang ausschliesslich ueber den Upload in der Weboberflaeche.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import os
import random
import re
from urllib.parse import urlencode

from fastapi import (FastAPI, File, Form, HTTPException, Query, Request,
                     UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from . import db
from . import mail
from .parser import (dauer_aus_spanne, fingerprint, hhmm, lies_datei, norm,
                     parse_datum, parse_dauer, parse_zeit, NICHT_ABRECHENBAR)
from . import auth
from . import wiki as _wiki
# ⚠️ Reine Rechen- und Formatfunktionen, seit 1.32 in einem eigenen Modul.
# Es importiert nur db und parser, kennt also weder App noch Templates -
# deshalb duerfen main.py und die Seitenmodule daneben es gleichermassen
# importieren, ohne Ringschluss. Die Namen werden hier ausdruecklich
# hereingeholt statt ueber "rechnen.x": sie stehen in Vorlagen, in
# anderen Modulen und in der Pruefung als main.x.
from .rechnen import (  # noqa: F401
    BEWILLIGUNG_HANDLUNG, auswahllisten, bereichsfilter,
    bewilligungen_pruefen, bewilligungslage, deutsch, euro, gesamtstunden,
    jetzt, klientenauswahl, mitarbeiter_zu_benutzer, mitarbeiterauswahl,
    monat_verschieben, monat_wort, stunden, tage, zahl)

BASIS = os.path.dirname(__file__)

APP_NAME = os.environ.get("APP_NAME", "Dein Weg Toolkit")
VERSION = "1.32.1"

# Änderungsprotokoll, chronologisch von alt nach neu. Die Seite dreht die
# Reihenfolge selbst. Bewusst hier im Code und nicht in einer Textdatei, damit
# es beim Austausch des app-Ordners automatisch mitkommt.
from .changelog import CHANGELOG  # noqa: E402

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
SPRUCH_DATEI = os.environ.get("SPRUCH_DATEI", "/texte/quotes.txt")
IDEEN_DATEI = os.environ.get("IDEEN_DATEI", "/texte/ideen.txt")
STRINGS_DATEI = os.environ.get("STRINGS_DATEI", "/texte/strings.txt")
SICHERUNG_PFAD = os.environ.get("SICHERUNG_PFAD", "/sicherungen")
# Wie viele automatische Sicherungen aufgehoben werden. Fuenf Wochen sind
# lang genug, um einen Fehler zu bemerken, und kurz genug, dass die
# Dateien nicht unbemerkt den Speicher fuellen.
SICHERUNGEN_BEHALTEN = 5
WIKI_PFAD = os.environ.get("WIKI_PFAD", "/wiki")
FILES_PFAD = os.environ.get("FILES_PFAD", "/files")
# Sekunden zwischen zwei Pruefungen auf faellige E-Mail-Erinnerungen.
# 0 = Wecker aus. Standard: einmal pro Stunde.
WECKER_INTERVALL = int(os.environ.get("WECKER_INTERVALL", "3600"))
# Sekunden zwischen zwei Pruefungen auf neu zugewiesene Aufgaben. Deutlich
# haeufiger als der Stundenwecker, weil der Sammelverzug in Minuten misst
# (siehe mail.pruefe_zuweisungen). Laeuft nur, wenn auch der Wecker laeuft.
ZUWEISUNG_INTERVALL = int(os.environ.get("ZUWEISUNG_INTERVALL", "60"))

ENDUNGEN = ("xlsx", "xlsm", "csv")

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(BASIS, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASIS, "templates"))
templates.env.filters["hhmm"] = hhmm
templates.env.globals["APP_NAME"] = APP_NAME
templates.env.globals["VERSION"] = VERSION
templates.env.globals["t"] = lambda *a, **k: t(*a, **k)
templates.env.globals["fusstext"] = lambda: fusstext()


# --- Anmeldung ---------------------------------------------------------------
#
# Ersetzt das frühere gemeinsame APP_PASSWORT (HTTP-Basic-Auth ohne einzelne
# Konten) durch echte Benutzerkonten mit Login, Rollen und Bereichsrechten.
# Die eigentliche Middleware, Sitzungsverwaltung und Zugriffsprüfung steckt
# in auth.py; hier wird sie nur eingebunden.

SITZUNG_TAGE = int(os.environ.get("SITZUNG_TAGE", "30"))

auth.setup(templates, SITZUNG_TAGE)
app.add_middleware(auth.SessionAuth)
app.include_router(auth.router)


# --- Hilfsfunktionen --------------------------------------------------------

templates.env.filters["deutsch"] = deutsch


# --- Texte für die Oberfläche ------------------------------------------------
#
# Alle erklärenden Texte stehen in strings.txt im Stammverzeichnis und können
# dort geändert werden, ohne den Code anzufassen. Fehlt ein Schlüssel oder die
# ganze Datei, greift der Standardtext von hier. Die Datei wird beim Start
# angelegt, falls sie noch nicht existiert.

from .texte_standard import TEXTE_STANDARD  # noqa: E402

_texte_zwischenspeicher: dict = {"stand": None, "werte": {}}


def texte() -> dict:
    """Liest strings.txt, sobald sie sich geändert hat."""
    try:
        stand = os.path.getmtime(STRINGS_DATEI)
    except OSError:
        stand = None

    if stand != _texte_zwischenspeicher["stand"]:
        werte = dict(TEXTE_STANDARD)
        if stand is not None:
            schluessel = None
            teile: list[str] = []
            try:
                with open(STRINGS_DATEI, encoding="utf-8") as f:
                    for zeile in f:
                        roh = zeile.rstrip("\n")
                        if roh.startswith("#") and not schluessel:
                            continue
                        kopf = re.fullmatch(r"\[([\w.]+)\]\s*", roh)
                        if kopf:
                            if schluessel:
                                werte[schluessel] = " ".join(" ".join(teile).split())
                            schluessel, teile = kopf.group(1), []
                        elif schluessel is not None:
                            teile.append(roh)
                if schluessel:
                    werte[schluessel] = " ".join(" ".join(teile).split())
            except OSError:
                pass
        _texte_zwischenspeicher.update({"stand": stand, "werte": werte})
    return _texte_zwischenspeicher["werte"]


def t(schluessel: str, **platzhalter) -> str:
    """Gibt den Text zurück, mit eingesetzten Platzhaltern."""
    text = texte().get(schluessel, "")
    if platzhalter:
        # Der Text selbst darf HTML enthalten (Links, <strong> in
        # strings.txt) und wird deshalb als Markup zurueckgegeben. Die
        # eingesetzten Werte stammen dagegen aus der Datenbank - etwa ein
        # Mitarbeitername - und werden vorher entschaerft, damit dort
        # kein HTML einschleusbar ist.
        try:
            text = text.format(**{k: escape(str(v))
                                  for k, v in platzhalter.items()})
        except (KeyError, IndexError, ValueError):
            pass
    return Markup(text)


# Was in der Fusszeile steht, wenn nichts gepflegt wurde.
# ⚠️ Der Schluessel "satz" ist mit 1.17.1 entfallen: der Satz unter dem Logo
# steht nicht mehr in der Fusszeile, das Logo hat seinen Platz bekommen.
FUSS_STANDARD = {
    "recht": ('© 2026 <a href="https://timovorwald.de" target="_blank" '
              'rel="noopener noreferrer">timovorwald.de</a>. '
              'Alle Rechte vorbehalten.'),
}


def fusstext() -> Markup:
    """Die Fusszeile: links die Marke, rechts die Angaben.

    ⚠️ Sie wird aus der Konfiguration gebaut und NICHT aus ``footer.text``:
    eine schon vorhandene ``strings.txt`` gewinnt gegen die Standardtexte,
    eine Änderung dort wäre also bei einer bestehenden Installation nie
    angekommen. Über die Einstellungen ist der Text jetzt ohnehin
    pflegbar.

    Bis 1.16 standen hier drei mittige Zeilen untereinander, darüber das
    Logo mit viel Luft - zusammen fast zweihundert Pixel für eine
    Angabe, die niemand liest. Jetzt sind es zwei Halften nebeneinander:
    links die Marke, rechts Fassung und Recht. Beides steht damit dort,
    wo es hingehört, und die Fusszeile ist halb so hoch. Unterhalb von
    620px stapelt sie wieder mittig.

    ⚠️ Der Satz unter dem Logo ist mit 1.17.1 entfallen (Timos Wunsch), und
    mit ihm das Feld dafür in den Einstellungen - ein Eingabefeld, dessen
    Wert nirgends mehr erscheint, ist schlimmer als keines. Das Logo hat
    den frei gewordenen Platz bekommen und steht jetzt deutlich groesser
    da. Der Wortlaut selbst steht ohnehin im Logo.

    ⚠️ Auch die beiden Logos stehen hier und nicht mehr in ``base.html``:
    die Fusszeile ist ein Stück und wird an einer Stelle gepflegt. Der
    Anhang ``?v=`` an den Bilddateien muss dabei bleiben, sonst hängt der
    Browser nach einem Bildtausch am alten Stand.
    """
    with db.db() as con:
        k = mail.konfig_lesen(con)
    recht = (k.get("fusszeile_recht") or "").strip() or FUSS_STANDARD["recht"]
    name, v = escape(APP_NAME), escape(VERSION)
    return Markup(
        '<div class="fussband">'
        '<div class="fussmarke">'
        f'<img class="nur-dunkel" src="/static/logo-fuer-dunkel.svg?v={v}" alt="{name}">'
        f'<img class="nur-hell" src="/static/logo-fuer-hell.svg?v={v}" alt="{name}">'
        '</div>'
        '<div class="fussangaben">'
        f'<p class="fuss-zeile fuss-fassung">{name}'
        f'<span class="version">{v}</span>'
        f'<a href="/changelog">Changelog</a></p>'
        f'<p class="fuss-zeile fuss-recht">{recht}</p>'
        '</div></div>')


def strings_anlegen() -> None:
    """Schreibt strings.txt mit allen Standardtexten, falls sie fehlt."""
    if os.path.exists(STRINGS_DATEI):
        return
    zeilen = [
        "# Texte der Oberfläche. Änderungen wirken sofort, ohne Neustart.",
        "# Aufbau: [schluessel] in eckigen Klammern, darunter der Text.",
        "# Ein Text darf über mehrere Zeilen gehen, Umbrüche werden zu Leerzeichen.",
        "# Einfaches HTML wie <strong> oder <a href=\"...\"> ist erlaubt.",
        "# Geschweifte Klammern wie {zeitraum} sind Platzhalter und bleiben stehen.",
        "# Wird ein Schlüssel gelöscht, greift wieder der eingebaute Standardtext.",
        "",
    ]
    for schluessel, text in TEXTE_STANDARD.items():
        zeilen.append(f"[{schluessel}]")
        zeilen.append(text)
        zeilen.append("")
    try:
        os.makedirs(os.path.dirname(STRINGS_DATEI) or ".", exist_ok=True)
        with open(STRINGS_DATEI, "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))
        print(f"[start] {STRINGS_DATEI} angelegt", flush=True)
    except OSError as e:
        print(f"[start] strings.txt nicht schreibbar: {e}", flush=True)


def spruch() -> dict:
    """Zufälliger Block aus quotes.txt, getrennt in Zitat und Quelle.

    Die Blöcke sind durch eine Zeile mit ## voneinander getrennt. Beginnt die
    letzte Zeile eines Blocks mit einem Gedankenstrich, gilt sie als Quelle und
    wird kleiner gesetzt. Fehlt die Datei oder ist sie leer, kommt ein leerer
    Satz zurück und die Zeile auf der Startseite entfällt.
    """
    leer = {"text": "", "quelle": ""}
    try:
        with open(SPRUCH_DATEI, encoding="utf-8") as f:
            roh = f.read()
    except OSError:
        return leer

    bloecke = [b.strip("\n").strip() for b in re.split(r"^[ \t]*##[ \t]*$",
                                                       roh, flags=re.MULTILINE)]
    bloecke = [b for b in bloecke if b]
    if not bloecke:
        return leer

    zeilen = random.choice(bloecke).splitlines()
    quelle = ""
    if len(zeilen) > 1 and zeilen[-1].lstrip().startswith(("–", "—", "-", "~")):
        quelle = zeilen.pop().lstrip("–—-~ ").strip()
    return {"text": "\n".join(zeilen).strip(), "quelle": quelle}




# Die Formatfunktionen selbst stehen in rechnen.py; angemeldet werden sie
# hier, weil es die Templates nur hier gibt.
templates.env.globals["monat_wort"] = monat_wort
templates.env.filters["euro"] = euro
templates.env.filters["zahl"] = zahl
templates.env.filters["stunden"] = stunden
templates.env.filters["gesamtstunden"] = gesamtstunden
templates.env.filters["tage"] = tage


# --- Kern: Datei einlesen ---------------------------------------------------

def verarbeite(dateiname: str, inhalt: bytes, mitarbeiter: str = "",
               erzwingen: bool = False, quelle: str = "Upload") -> int:
    """Liest eine Datei und legt Import samt Vorschauzeilen an.

    Die Originaldatei wird bewusst nicht aufgehoben: die Zeilen stehen
    anschliessend in der Datenbank, die Dateikopie waere nur Ballast. In
    "quelldatei" bleibt lediglich ein Vermerk mit Pruefsumme stehen.
    """
    zeilen, statistik = lies_datei(dateiname, inhalt, mitarbeiter, erzwingen)
    quell_hash = hashlib.sha256(inhalt).hexdigest()

    with db.db() as con:
        cur = con.execute(
            "INSERT INTO import (dateiname, mitarbeiter, hochgeladen_am, status, "
            "zeilen_gesamt, quelle, notiz) "
            "VALUES (?,?,?,'vorschau',?,?,?)",
            (dateiname, zeilen[0]["mitarbeiter"], jetzt(), len(zeilen), quelle,
             "Spalten: " + ", ".join(
                 f"{k}={v}" for k, v in statistik["spalten"].items())))
        import_id = cur.lastrowid

        gesehen: set[str] = set()
        neu = dubl = 0
        for z in zeilen:
            dublette = None
            if z["fingerprint"] in gesehen:
                dublette = "in dieser Datei doppelt"
            elif con.execute("SELECT 1 FROM eintrag WHERE fingerprint=?",
                             (z["fingerprint"],)).fetchone():
                dublette = "bereits in der Datenbank"
            gesehen.add(z["fingerprint"])
            if dublette:
                dubl += 1
            else:
                neu += 1
            con.execute(
                "INSERT INTO vorschau (import_id, mitarbeiter, datum, monat, start, "
                "ende, klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "dublette, warnung) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (import_id, z["mitarbeiter"], z["datum"], z["monat"], z["start"],
                 z["ende"], z["klient"], z["beschreibung"], z["dauer_min"],
                 z["abrechenbar"], z["fingerprint"], dublette, z["warnung"]))
        con.execute("UPDATE import SET zeilen_neu=?, zeilen_dubletten=? WHERE id=?",
                    (neu, dubl, import_id))
        con.execute(
            "INSERT OR REPLACE INTO quelldatei (hash, dateiname, quelle, "
            "verarbeitet_am, import_id) VALUES (?,?,?,?,?)",
            (quell_hash, dateiname, quelle, jetzt(), import_id))
    return import_id


def uebernehmen_intern(import_id: int, mit_dubletten: bool = False) -> int:
    with db.db() as con:
        imp = con.execute("SELECT * FROM import WHERE id=?", (import_id,)).fetchone()
        if not imp or imp["status"] != "vorschau":
            raise HTTPException(400, "Import bereits abgeschlossen oder unbekannt")
        bedingung = "" if mit_dubletten else " AND dublette IS NULL"
        zeilen = con.execute(
            f"SELECT * FROM vorschau WHERE import_id=?{bedingung}",
            (import_id,)).fetchall()
        for z in zeilen:
            con.execute(
                "INSERT INTO eintrag (import_id, mitarbeiter, datum, monat, start, "
                "ende, klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "angelegt_am) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (import_id, z["mitarbeiter"], z["datum"], z["monat"], z["start"],
                 z["ende"], z["klient"], z["beschreibung"], z["dauer_min"],
                 z["abrechenbar"], z["fingerprint"], jetzt()))
        con.execute("DELETE FROM vorschau WHERE import_id=?", (import_id,))
        con.execute("UPDATE import SET status='uebernommen', zeilen_neu=? WHERE id=?",
                    (len(zeilen), import_id))
    return len(zeilen)


def datenbank_kopieren(zielpfad: str) -> None:
    """Sichere Kopie der Datenbank, auch waehrend geschrieben wird.

    sqlite3.backup() statt einfachem Kopieren: im WAL-Modus liegen Teile
    der Daten sonst in Nebendateien und die Kopie waere unvollstaendig.
    """
    import sqlite3 as _sqlite
    ziel = _sqlite.connect(zielpfad)
    with db.db() as con, ziel:
        con.backup(ziel)
    ziel.close()


def sicherungsdateien() -> list[str]:
    """Namen der abgelegten Sicherungen, unsortiert.

    Eine Stelle fuer die Frage "was zaehlt als Sicherung": das Aufraeumen
    im Wecker und die Liste in den Einstellungen duerfen sich nicht
    unterschiedlich entscheiden.
    """
    try:
        return [d for d in os.listdir(SICHERUNG_PFAD)
                if d.startswith("sicherung-") and d.endswith(".db")]
    except OSError:
        return []


def sicherung_anlegen(grund: str) -> str | None:
    """Eine Sicherung ausserhalb des Wochenrhythmus, mit Grund im Namen.

    Wird vor einer Sammelaenderung gerufen. Der Name folgt demselben
    Muster wie die woechentliche Sicherung, damit die Liste in den
    Einstellungen sie mit anzeigt - und damit sie beim Aufraeumen mit
    unter die fuenf juengsten faellt.
    """
    try:
        os.makedirs(SICHERUNG_PFAD, exist_ok=True)
        stempel = dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
        name = f"sicherung-{stempel}-{grund}.db"
        ziel = os.path.join(SICHERUNG_PFAD, name)
        vorlaeufig = ziel + ".teil"
        datenbank_kopieren(vorlaeufig)
        os.replace(vorlaeufig, ziel)
        return name
    except OSError as fehler:
        # ⚠️ Eine fehlgeschlagene Sicherung darf die Aenderung nicht
        # verhindern - aber der Aufrufer muss davon erfahren.
        print(f"[sicherung] fehlgeschlagen: {fehler}", flush=True)
        return None


def automatische_sicherung(heute: dt.date | None = None) -> str | None:
    """Legt sonntags eine Sicherung an und raeumt alte weg.

    Der Wecker laeuft stuendlich und ruft das hier jedes Mal auf; gesichert
    wird trotzdem hoechstens einmal je Sonntag. Der Dateiname traegt das
    Datum, und liegt fuer diesen Tag schon eine Datei, passiert nichts.
    Damit ist es egal, ob der Rechner nachts aus war oder ob der Wecker
    zwanzigmal vorbeikommt.

    Gibt den Dateinamen zurueck, wenn etwas geschrieben wurde, sonst None.
    """
    heute = heute or dt.date.today()
    if heute.weekday() != 6:          # 6 = Sonntag
        return None
    os.makedirs(SICHERUNG_PFAD, exist_ok=True)
    name = f"sicherung-{heute:%Y-%m-%d}.db"
    ziel = os.path.join(SICHERUNG_PFAD, name)
    if os.path.exists(ziel):
        return None

    # Erst neben die endgueltige Datei schreiben, dann umbenennen: bricht
    # der Vorgang ab, liegt dort keine halbe Sicherung, die wie eine
    # gueltige aussieht.
    vorlaeufig = ziel + ".teil"
    datenbank_kopieren(vorlaeufig)
    os.replace(vorlaeufig, ziel)

    # Aufraeumen: nur die juengsten behalten.
    vorhanden = sorted(sicherungsdateien(),
        reverse=True)
    for alt in vorhanden[SICHERUNGEN_BEHALTEN:]:
        try:
            os.remove(os.path.join(SICHERUNG_PFAD, alt))
        except OSError:
            pass
    return name


async def wecker_schleife() -> None:
    """Prueft regelmaessig, ob Erinnerungen faellig sind.

    Stuendlich statt einmal taeglich: so wird eine Frist auch dann bemerkt,
    wenn der Container ueber Nacht aus war. Doppelte Mails verhindert der
    Vermerk in der Tabelle "benachrichtigung", nicht das Intervall.
    """
    await asyncio.sleep(30)
    while True:
        try:
            gesichert = await asyncio.to_thread(automatische_sicherung)
            if gesichert:
                print(f"[sicherung] {gesichert} geschrieben", flush=True)
        except Exception as e:
            print(f"[sicherung] {type(e).__name__}: {e}", flush=True)
        try:
            zeilen = await asyncio.to_thread(mail.durchlauf)
            for zeile in zeilen:
                if zeile not in ("nichts zu tun", "E-Mail-Versand ist ausgeschaltet"):
                    print(f"[wecker] {zeile}", flush=True)
        except Exception as e:
            print(f"[wecker] {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(WECKER_INTERVALL)


async def zuweisungs_schleife() -> None:
    """Verschickt die Mails, die nicht bis zur naechsten vollen Stunde
    warten sollen: neu zugewiesene Aufgaben und abgeschlossene Aufgaben.

    Eigene Schleife statt im Stundenwecker: der Sammelverzug misst in
    Minuten, ein Stundentakt waere dafuer zu grob. Der Verzug selbst
    steckt in mail.pruefe_zuweisungen; hier wird nur oft genug
    nachgesehen, ob ein Sammelfenster inzwischen zu ist. Die
    Erledigt-Meldung (seit 1.30) haengt aus demselben Grund hier mit
    drin - sie soll kommen, solange man noch am Schreibtisch sitzt.
    """
    await asyncio.sleep(20)
    while True:
        try:
            zeilen = await asyncio.to_thread(mail.durchlauf, False, False,
                                             False, True)
            for zeile in zeilen:
                if zeile not in ("nichts zu tun",
                                 "E-Mail-Versand ist ausgeschaltet"):
                    print(f"[zuweisung] {zeile}", flush=True)
        except Exception as e:
            print(f"[zuweisung] {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(ZUWEISUNG_INTERVALL)


@app.on_event("startup")
async def start() -> None:
    initialer_admin = db.init()
    if initialer_admin:
        print("[start] " + "=" * 60, flush=True)
        print("[start] Erster Administrator angelegt:", flush=True)
        print(f"[start]   Benutzername: {initialer_admin['benutzername']}", flush=True)
        if initialer_admin["generiert"]:
            print(f"[start]   Passwort:     {initialer_admin['passwort']}", flush=True)
            print("[start]   (zufällig erzeugt, bitte nach dem ersten Login "
                  "unter Einstellungen ändern)", flush=True)
        else:
            print("[start]   Passwort:     wie in ADMIN_PASSWORT hinterlegt", flush=True)
        print("[start] " + "=" * 60, flush=True)
    strings_anlegen()
    _wiki.wiki_anlegen()
    try:
        os.makedirs(FILES_PFAD, exist_ok=True)
    except OSError as e:
        print(f"[start] {FILES_PFAD} nicht verfuegbar: {e}", flush=True)
    if WECKER_INTERVALL > 0:
        asyncio.create_task(wecker_schleife())
        if ZUWEISUNG_INTERVALL > 0:
            asyncio.create_task(zuweisungs_schleife())
    print(f"[start] {APP_NAME} {VERSION} bereit · E-Mail-Wecker "
          f"{'alle ' + str(WECKER_INTERVALL) + 's' if WECKER_INTERVALL else 'aus'}",
          flush=True)


# --- Startseite -------------------------------------------------------------

def fehlerseite(text: str):
    return RedirectResponse("/?" + urlencode({"fehler": text}), status_code=303)


def zurueck_mit_hinweis(ziel: str, text: str):
    """Haengt einen Hinweis an eine Rueckkehradresse, die schon Filter traegt."""
    trenner = "&" if "?" in ziel else "?"
    return RedirectResponse(f"{ziel}{trenner}" + urlencode({"hinweis": text}),
                            status_code=303)


def abgabe_uebersicht(monat: str) -> dict:
    """Wer hat für diesen Monat schon Zeiten abgegeben und wer nicht.

    Abgegeben heißt: es liegen Datensätze für den Monat vor, egal ob importiert
    oder von Hand getippt. Der Abgleich läuft über die normalisierte Schreibweise
    des Namens, damit "timo" und "Timo " nicht auseinanderfallen.
    """
    with db.db() as con:
        team = con.execute(
            "SELECT * FROM mitarbeiter WHERE aktiv=1 "
            "ORDER BY abgabepflicht DESC, name").fetchall()
        zeilen = con.execute(
            "SELECT mitarbeiter, COUNT(*) n, SUM(dauer_min) m, "
            "MAX(angelegt_am) zuletzt, "
            "SUM(CASE WHEN import_id IS NULL THEN 1 ELSE 0 END) manuell "
            "FROM eintrag WHERE monat=? GROUP BY mitarbeiter", (monat,)).fetchall()

    nach_name = {norm(r["mitarbeiter"]): r for r in zeilen}
    zugeordnet = set()

    stand = []
    for m in team:
        treffer = nach_name.get(norm(m["name"]))
        if treffer:
            zugeordnet.add(norm(m["name"]))
        stand.append({
            "name": m["name"],
            "pflicht": bool(m["abgabepflicht"]),
            "da": bool(treffer),
            "n": treffer["n"] if treffer else 0,
            "m": treffer["m"] if treffer else 0,
            "zuletzt": treffer["zuletzt"] if treffer else "",
            "art": ("von Hand" if treffer and treffer["manuell"] == treffer["n"]
                    else ("importiert" if treffer and not treffer["manuell"]
                          else "gemischt" if treffer else "")),
        })

    # Namen, die in den Daten stehen, aber zu keinem Teammitglied passen
    fremd = [r["mitarbeiter"] for r in zeilen
             if norm(r["mitarbeiter"]) not in zugeordnet]

    pflichtige = [s for s in stand if s["pflicht"]]
    fertig = [s for s in pflichtige if s["da"]]
    return {
        "monat": monat,
        "wort": monat_wort(monat),
        "stand": stand,
        "fremd": sorted(fremd),
        "soll": len(pflichtige),
        "ist": len(fertig),
        "fehlend": [s["name"] for s in pflichtige if not s["da"]],
        "prozent": round(len(fertig) / len(pflichtige) * 100) if pflichtige else 0,
        "summe": sum(s["m"] for s in stand),
    }



@app.get("/", response_class=HTMLResponse)
def startseite(request: Request, fehler: str = "", hinweis: str = "",
               alle: str = "", monat: str = "", mitarbeiter: str = "",
               datum: str = ""):
    """Zeiterfassung: manueller Eintrag und Listenimport auf einer Seite.

    Bis 2.6 waren das zwei getrennte Menuepunkte. Beide Wege fuehren zum
    selben Ergebnis - ein Datensatz in "eintrag" -, deshalb stehen sie
    jetzt untereinander auf einer Seite. Die Kaesten "Bestand" und
    "Abgaben" daneben bleiben unveraendert.
    """
    heute = dt.date.today()
    if not re.fullmatch(r"\d{4}-\d{2}", monat or ""):
        monat = heute.strftime("%Y-%m")
    mitarbeiter = mitarbeiter.strip()
    with db.db() as con:
        # Nur noch die Importe, die auf eine Pruefung warten. Die frueher
        # hier gezeigte Liste aller vergangenen Importe ist entfallen - die
        # Daten stehen in der Datenbank, die Dateiliste war nur Ballast.
        # Diese Auswahl bleibt aber noetig, sonst fuehrt kein Weg mehr zu
        # einer offenen Vorschau.
        importe = con.execute(
            "SELECT i.*, (SELECT COUNT(*) FROM vorschau v WHERE v.import_id=i.id) "
            "AS zeilen FROM import i WHERE i.status='vorschau' "
            "ORDER BY i.id DESC").fetchall()
        summe = con.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(dauer_min),0) m FROM eintrag").fetchone()
        leute = [r["mitarbeiter"] for r in con.execute(
            "SELECT DISTINCT mitarbeiter FROM eintrag ORDER BY 1")]
        klienten = [r["klient"] for r in con.execute(
            "SELECT DISTINCT klient FROM eintrag ORDER BY 1")]
        leistungen = [r["name"] for r in con.execute(
            "SELECT name FROM leistung WHERE aktiv=1 ORDER BY name COLLATE NOCASE")]
        mitarbeiterliste = mitarbeiterauswahl(con)
        klientliste = klientenauswahl(con)
        offene = con.execute(
            "SELECT COUNT(*) c FROM import WHERE status='vorschau'").fetchone()["c"]

        # ⚠️ Der eigene Name ist die Vorgabe (seit 1.25). Im Regelfall
        # traegt jeder seine eigenen Zeiten ein; ein Pflichtfeld, dessen
        # Antwort immer dieselbe ist, ist nur ein Handgriff mehr. Fuer
        # jemand anderen zu erfassen bleibt moeglich, muss in der
        # Oberflaeche aber ausdruecklich aufgeklappt werden.
        #
        # Hat das Konto keinen Mitarbeiter zugeordnet, gibt es keine
        # Vorgabe - dann steht dort weiter das offene Auswahlfeld.
        benutzer = getattr(request.state, "benutzer", None)
        eigener = eigener_mitarbeitername(con, benutzer) if benutzer else ""
        if not mitarbeiter and eigener:
            mitarbeiter = eigener
        fremd = bool(eigener and mitarbeiter and norm(mitarbeiter) != norm(eigener))

        if mitarbeiter:
            letzte = con.execute(
                "SELECT * FROM eintrag WHERE mitarbeiter=? AND import_id IS NULL "
                "ORDER BY id DESC LIMIT 12", (mitarbeiter,)).fetchall()
            # ⚠️ Ohne eigene Angabe der heutige Tag (seit 1.30). Vorher
            # stand hier nur das gerade gespeicherte Datum aus der
            # Adresse; beim ersten Aufruf war das leer, und die Zahl in
            # der Kopfzeile blieb dauerhaft aus.
            tag = parse_datum(datum) or heute
            tagessumme = con.execute(
                "SELECT COALESCE(SUM(dauer_min),0) m, COUNT(*) n FROM eintrag "
                "WHERE mitarbeiter=? AND datum=?",
                (mitarbeiter, tag.isoformat())).fetchone()
            summentag = tag
        else:
            letzte, tagessumme, summentag = [], {"m": 0, "n": 0}, heute
    return templates.TemplateResponse(request=request, name="index.html", context={
        "importe": importe, "summe": summe, "leute": leute,
        "klienten": klienten, "leistungen": leistungen, "letzte": letzte,
        "mitarbeiterliste": mitarbeiterliste, "klientliste": klientliste,
        "tagessumme": tagessumme, "mitarbeiter": mitarbeiter, "datum": datum,
        "eigener": eigener, "fremd": fremd,
        "summentag": summentag, "ist_heute": summentag == heute,
        "fehler": fehler, "hinweis": hinweis, "seite": "zeiterfassung",
        "offene": offene, "spruch": spruch(),
        "alle": bool(alle),
        "abgabe": abgabe_uebersicht(monat),
        "monat_vor": monat_verschieben(monat, -1),
        "monat_zurueck": monat_verschieben(monat, 1),
        "ist_laufender": monat == heute.strftime("%Y-%m")})


@app.post("/upload")
async def hochladen(datei: list[UploadFile] = File(...),
                    mitarbeiter: str = Form(""),
                    erzwingen: str = Form("")):
    letzte_id = None
    for f in datei:
        if not f.filename:
            continue
        inhalt = await f.read()
        if len(inhalt) > MAX_UPLOAD_MB * 1024 * 1024:
            return fehlerseite(f"{f.filename} ist größer als {MAX_UPLOAD_MB} MB.")
        try:
            letzte_id = verarbeite(f.filename, inhalt, mitarbeiter,
                                   bool(erzwingen), "Upload")
        except Exception as e:
            return fehlerseite(f"{f.filename}: {e}")
    if letzte_id is None:
        return fehlerseite("Keine Datei ausgewählt.")
    return RedirectResponse(f"/vorschau/{letzte_id}", status_code=303)


# --- Vorschau ---------------------------------------------------------------

@app.get("/vorschau/{import_id}", response_class=HTMLResponse)
def vorschau(request: Request, import_id: int):
    with db.db() as con:
        imp = con.execute("SELECT * FROM import WHERE id=?", (import_id,)).fetchone()
        if not imp:
            raise HTTPException(404, "Import nicht gefunden")
        zeilen = con.execute(
            "SELECT * FROM vorschau WHERE import_id=? ORDER BY datum, start",
            (import_id,)).fetchall()
        offene = con.execute(
            "SELECT id, dateiname FROM import WHERE status='vorschau' AND id<>?",
            (import_id,)).fetchall()
    return templates.TemplateResponse(request=request, name="vorschau.html", context={
        "imp": imp, "zeilen": zeilen, "offene": offene, "seite": "zeiterfassung",
        "summe_neu": sum(z["dauer_min"] for z in zeilen if not z["dublette"])})


@app.post("/vorschau/{import_id}/uebernehmen")
def uebernehmen(import_id: int, dubletten: str = Form("")):
    uebernehmen_intern(import_id, bool(dubletten))
    return RedirectResponse(f"/eintraege?import_id={import_id}", status_code=303)


@app.post("/vorschau/{import_id}/verwerfen")
def verwerfen(import_id: int):
    with db.db() as con:
        con.execute("DELETE FROM vorschau WHERE import_id=?", (import_id,))
        con.execute("DELETE FROM import WHERE id=? AND status='vorschau'", (import_id,))
    return RedirectResponse("/?" + urlencode(
        {"hinweis": "Import verworfen. Die Originaldatei bleibt im Archiv."}),
        status_code=303)


@app.post("/import/{import_id}/ruecknahme")
def ruecknahme(import_id: int):
    with db.db() as con:
        anzahl = con.execute("SELECT COUNT(*) c FROM eintrag WHERE import_id=?",
                             (import_id,)).fetchone()["c"]
        con.execute("DELETE FROM eintrag WHERE import_id=?", (import_id,))
        con.execute("UPDATE import SET status='zurueckgenommen' WHERE id=?",
                    (import_id,))
    return RedirectResponse("/?" + urlencode(
        {"hinweis": f"{anzahl} Einträge wieder entfernt."}), status_code=303)


# --- Eintraege --------------------------------------------------------------


# --- Wer darf welchen Zeiteintrag loeschen? ---------------------------------
#
# Regel: die eigenen Eintraege darf jeder loeschen, immer. Fuer die
# Eintraege anderer braucht es das ausdrueckliche Recht "fremde_loeschen"
# (Einstellungen -> Benutzerverwaltung); Administratoren haben es ohnehin.
#
# "Eigen" heisst: eintrag.mitarbeiter entspricht dem Mitarbeiter, der zum
# angemeldeten Konto gehoert. Die Zuordnung laeuft ueber dieselbe Regel wie
# beim E-Mail-Versand und in "Mein Bereich" (mitarbeiter_zu_benutzer), der
# Vergleich ueber norm() - Schreibweisen aus Fremdexporten stimmen nicht
# immer aufs Zeichen ueberein.

def eigener_mitarbeitername(con, benutzer) -> str:
    """Der Mitarbeitername des angemeldeten Kontos, oder "" wenn keiner passt."""
    zeile = mitarbeiter_zu_benutzer(con, benutzer)
    if zeile is None:
        return ""
    try:
        return (zeile["name"] or "").strip()
    except (IndexError, KeyError, TypeError):
        return ""


# --- Logbuch der Datensaetze -------------------------------------------------
#
# Wer hat wann an den erfassten Zeiten etwas geaendert oder geloescht?
# Append-only in "eintrag_log", einsehbar nur fuer Administratoren
# (/eintraege/logbuch, abgesichert ueber auth.ADMIN_NUR_PFADE).
#
# ⚠️ Angelegte Eintraege stehen nicht drin: wer etwas erfasst hat, steht
# im Eintrag selbst ("mitarbeiter", "angelegt_am"). Protokolliert wird,
# was hinterher daran veraendert wurde - genau das ist sonst nicht mehr
# nachvollziehbar.

# Welche Felder verglichen werden, und wie sie im Klartext heissen.
LOG_FELDER = (
    ("datum", "Datum"), ("start", "Beginn"), ("ende", "Ende"),
    ("dauer_min", "Dauer"), ("klient", "Betreute Person"),
    ("mitarbeiter", "Mitarbeiter"), ("beschreibung", "Leistung"),
    ("abrechenbar", "Abrechenbar"),
)


def _logwert(feld: str, wert) -> str:
    """Ein Feldwert so, wie er im Logbuch lesbar ist."""
    if wert is None or wert == "":
        return "—"
    if feld == "dauer_min":
        return hhmm(wert)
    if feld == "datum":
        return deutsch(str(wert))
    if feld == "abrechenbar":
        return "ja" if wert else "nein"
    return str(wert)


def log_unterschied(vorher, nachher: dict) -> str:
    """Was hat sich geaendert? Als ein Satz, oder "" wenn nichts."""
    teile = []
    for feld, wort in LOG_FELDER:
        try:
            alt = vorher[feld]
        except (IndexError, KeyError, TypeError):
            continue
        if feld not in nachher:
            continue
        neu = nachher[feld]
        # Zahlen und Text vergleichbar machen - aus dem Formular kommt
        # alles als str, aus der Datenbank nicht.
        if str(alt or "") == str(neu or ""):
            continue
        teile.append(f"{wort}: {_logwert(feld, alt)} → {_logwert(feld, neu)}")
    return " · ".join(teile)


def log_eintrag(con, aktion: str, zeile, wer: str, aenderung: str = "") -> None:
    """Schreibt eine Zeile ins Logbuch der Datensaetze.

    ``zeile`` ist der Eintrag VOR der Aenderung - so steht im Logbuch,
    was betroffen war, auch wenn es ihn hinterher nicht mehr gibt.
    """
    def feld(name):
        try:
            return zeile[name]
        except (IndexError, KeyError, TypeError):
            return None

    con.execute(
        "INSERT INTO eintrag_log (eintrag_id, zeitpunkt, wer, aktion, datum, "
        "klient, mitarbeiter, dauer_min, beschreibung, aenderung) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (feld("id"), jetzt(), wer or "unbekannt", aktion, feld("datum"),
         feld("klient"), feld("mitarbeiter"), feld("dauer_min"),
         feld("beschreibung"), aenderung or None))


def wer_handelt(request) -> str:
    """Wer fuehrt diese Aktion aus? Immer aus der Anmeldung.

    Bevorzugt den Mitarbeiternamen des Kontos - so steht im Logbuch
    derselbe Name wie in den Zeiten -, sonst den Benutzernamen. Dieselbe
    Regel wie in vorgaenge.handelnde_person; eine eingetippte Angabe
    taugt als Nachweis nicht.
    """
    benutzer = getattr(request.state, "benutzer", None)
    if not benutzer:
        return "unbekannt"
    with db.db() as con:
        name = eigener_mitarbeitername(con, benutzer)
    if name:
        return name
    try:
        return benutzer["benutzername"] or "unbekannt"
    except (IndexError, KeyError, TypeError):
        return "unbekannt"


def _ist_eigener(eintrag_mitarbeiter: str, eigener_name: str) -> bool:
    if not eigener_name:
        return False
    return norm(eintrag_mitarbeiter) == norm(eigener_name)


def darf_eintrag_loeschen(benutzer, eintrag_mitarbeiter: str,
                          eigener_name: str) -> bool:
    return (auth.darf_fremde_loeschen(benutzer)
            or _ist_eigener(eintrag_mitarbeiter, eigener_name))


def darf_eintrag_bearbeiten(benutzer, eintrag_mitarbeiter: str,
                            eigener_name: str) -> bool:
    return (auth.darf_fremde_bearbeiten(benutzer)
            or _ist_eigener(eintrag_mitarbeiter, eigener_name))


@app.get("/eintraege", response_class=HTMLResponse)
def eintraege(request: Request, von_jahr: str = "", von_monat: str = "",
              bis_jahr: str = "", bis_monat: str = "",
              mitarbeiter: list[str] = Query([]),
              klient: list[str] = Query([]), q: str = "", import_id: int = 0,
              nur_abrechenbar: str = "", seite_nr: int = 1, hinweis: str = ""):
    filter_ = bereichsfilter(von_jahr, von_monat, bis_jahr, bis_monat,
                             mitarbeiter, klient, q, import_id, nur_abrechenbar)
    wo, werte = filter_["wo"], filter_["werte"]
    pro_seite = 200

    with db.db() as con:
        kopf = con.execute(
            f"SELECT COUNT(*) n, COALESCE(SUM(dauer_min),0) m FROM eintrag WHERE {wo}",
            werte).fetchone()
        # Seitenzahl vor der Abfrage begrenzen, sonst kommt eine leere Seite
        seiten_gesamt = max(1, -(-kopf["n"] // pro_seite))
        seite_nr = min(max(1, seite_nr), seiten_gesamt)
        zeilen = con.execute(
            f"SELECT * FROM eintrag WHERE {wo} ORDER BY datum DESC, start DESC "
            f"LIMIT {pro_seite} OFFSET {(seite_nr - 1) * pro_seite}", werte).fetchall()
        eigener = eigener_mitarbeitername(con, request.state.benutzer)

    # Welche der angezeigten Zeilen darf dieses Konto loeschen? Einmal hier
    # gerechnet statt in der Vorlage - dieselbe Funktion entscheidet auch
    # serverseitig beim Loeschen, so koennen Ansicht und Durchsetzung nicht
    # auseinanderlaufen.
    darf_fremde = auth.darf_fremde_loeschen(request.state.benutzer)
    darf_fremde_bearb = auth.darf_fremde_bearbeiten(request.state.benutzer)
    loeschbar = {z["id"] for z in zeilen
                 if darf_eintrag_loeschen(request.state.benutzer,
                                          z["mitarbeiter"], eigener)}
    bearbeitbar = {z["id"] for z in zeilen
                   if darf_eintrag_bearbeiten(request.state.benutzer,
                                              z["mitarbeiter"], eigener)}

    zusatz = auswahllisten()
    return templates.TemplateResponse(request=request, name="eintraege.html", context={
        "zeilen": zeilen, "kopf": kopf, "f": filter_["f"], "seite_nr": seite_nr,
        "loeschbar": loeschbar, "bearbeitbar": bearbeitbar,
        "darf_fremde": darf_fremde, "darf_fremde_bearb": darf_fremde_bearb,
        "eigener": eigener,
        "hinweis": hinweis, "aktive_filter": filter_["aktive"],
        "zeitraum_wort": filter_["wort"], "query": filter_["query"],
        "mehr": kopf["n"] > seite_nr * pro_seite,
        "seiten_gesamt": seiten_gesamt, "pro_seite": pro_seite,
        "erste_nr": (seite_nr - 1) * pro_seite + 1,
        "letzte_nr": min(seite_nr * pro_seite, kopf["n"]),
        "seite": "eintraege", **zusatz})


@app.post("/eintraege/loeschen")
def eintraege_sammelloeschen(request: Request, ids: list[int] = Form([]),
                             zurueck: str = Form("/eintraege")):
    """Loescht mehrere angekreuzte Datensaetze auf einmal.

    Die Sicherheitsabfrage sitzt im Browser (siehe eintraege.html); hier
    wird geprueft, dass ueberhaupt etwas angekreuzt war - und dass jeder
    einzelne Datensatz auch geloescht werden darf. Die Kaestchen fehlender
    Rechte blendet die Vorlage zwar aus, ein von Hand abgeschicktes
    Formular kaeme sonst aber trotzdem durch. Die Obergrenze entspricht
    einer vollen Seite der Datensatzliste.
    """
    ids = ids[:500]
    if not ids:
        return zurueck_mit_hinweis(zurueck, "Es war nichts angekreuzt.")
    benutzer = request.state.benutzer
    with db.db() as con:
        eigener = eigener_mitarbeitername(con, benutzer)
        platzhalter = ",".join("?" * len(ids))
        # ⚠️ Alle Felder holen, nicht nur id und mitarbeiter: das Logbuch
        # soll hinterher noch sagen koennen, WAS geloescht wurde.
        vorhanden = con.execute(
            f"SELECT * FROM eintrag WHERE id IN ({platzhalter})", ids).fetchall()
        loeschbar = [z for z in vorhanden
                     if darf_eintrag_loeschen(benutzer, z["mitarbeiter"], eigener)]
        erlaubt = [z["id"] for z in loeschbar]
        verweigert = len(vorhanden) - len(erlaubt)
        if erlaubt:
            wer = wer_handelt(request)
            for z in loeschbar:
                log_eintrag(con, "geloescht", z, wer, "Sammellöschung")
            platzhalter = ",".join("?" * len(erlaubt))
            con.execute(f"DELETE FROM eintrag WHERE id IN ({platzhalter})", erlaubt)

    if not erlaubt:
        return zurueck_mit_hinweis(
            zurueck, "Nichts gelöscht: Das waren ausschließlich Einträge "
                     "anderer Personen. Dafür fehlt dir die Berechtigung.")
    wort = "Eintrag" if len(erlaubt) == 1 else "Einträge"
    text = f"{len(erlaubt)} {wort} gelöscht."
    if verweigert:
        wort2 = "Eintrag" if verweigert == 1 else "Einträge"
        text += (f" {verweigert} {wort2} von anderen Personen "
                 "blieben stehen – dafür fehlt dir die Berechtigung.")
    return zurueck_mit_hinweis(zurueck, text)


# ⚠️ Diese Route muss VOR /eintraege/{eintrag_id}/loeschen stehen -
# sonst schluckt der Platzhalter das Wort „logbuch" und FastAPI
# versucht, es als Zahl zu lesen. Dieselbe Falle wie beim GET darauf
# und bei den Wiki-Aktionen; sie ist mir beim Bauen prompt
# untergekommen.
@app.post("/eintraege/logbuch/loeschen")
def logbuch_loeschen(request: Request, ids: list[int] = Form([]),
                     zurueck: str = Form("/eintraege/logbuch")):
    """Ausgewaehlte Logzeilen entfernen.

    ⚠️ Das Logbuch ist sonst append-only, und das aus gutem Grund: es
    beantwortet die Frage, wer an den erfassten Zeiten etwas geaendert
    hat. Auf Timos Wunsch laesst es sich seit 1.26 aufraeumen - nur von
    Administratoren, und die Seite ist ohnehin nur fuer sie erreichbar
    (auth.ADMIN_NUR_PFADE).

    ⚠️ Das Aufraeumen selbst hinterlaesst eine Zeile: wer wann wie viele
    entfernt hat. Ohne das waere die Luecke im Logbuch nicht mehr von
    "da war nie etwas" zu unterscheiden - und genau das soll ein Logbuch
    unterscheidbar machen. Eine Zeile fuer den ganzen Vorgang, nicht eine
    je geloeschter Zeile; sonst waere nach dem Aufraeumen mehr drin als
    vorher.
    """
    ziel = zurueck if zurueck.startswith("/eintraege/logbuch") \
        else "/eintraege/logbuch"
    ids = ids[:500]          # dieselbe Obergrenze wie bei den Datensaetzen
    if not ids:
        return zurueck_mit_hinweis(ziel, "Es war nichts ausgewählt.")

    platzhalter = ",".join("?" for _ in ids)
    with db.db() as con:
        weg = con.execute(
            f"SELECT COUNT(*) c FROM eintrag_log WHERE id IN ({platzhalter})",
            ids).fetchone()["c"]
        con.execute(f"DELETE FROM eintrag_log WHERE id IN ({platzhalter})", ids)
        if weg:
            con.execute(
                "INSERT INTO eintrag_log (eintrag_id, zeitpunkt, wer, aktion, "
                "aenderung) VALUES (NULL, ?, ?, 'aufgeräumt', ?)",
                (jetzt(), wer_handelt(request),
                 f"{weg} {'Zeile' if weg == 1 else 'Zeilen'} "
                 "aus dem Logbuch entfernt"))

    if not weg:
        return zurueck_mit_hinweis(ziel, "Es war nichts mehr da zum Entfernen.")
    return zurueck_mit_hinweis(
        ziel, f"{weg} {'Zeile' if weg == 1 else 'Zeilen'} entfernt. "
              "Dass hier aufgeräumt wurde, steht als eigene Zeile im Logbuch.")


# Dieselbe Route zusaetzlich unter /meinbereich: „Mein Bereich" haengt
# an keiner Bereichsberechtigung, jeder soll dort seine eigenen Zeiten
# aendern und loeschen koennen - auch ohne den Bereich „Übersicht
# (Datensätze)". Die Pruefung bleibt dieselbe: darf_eintrag_loeschen
# entscheidet ueber den Eintrag, nicht ueber den Pfad. Ein fremder
# Eintrag wird hier also genauso abgewiesen wie dort.
@app.post("/eintraege/{eintrag_id}/loeschen")
@app.post("/meinbereich/eintrag/{eintrag_id}/loeschen")
def eintrag_loeschen(request: Request, eintrag_id: int,
                     zurueck: str = Form("/eintraege")):
    benutzer = request.state.benutzer
    with db.db() as con:
        z = con.execute("SELECT * FROM eintrag WHERE id=?",
                        (eintrag_id,)).fetchone()
        if z is None:
            return zurueck_mit_hinweis(zurueck, "Diesen Eintrag gibt es nicht mehr.")
        eigener = eigener_mitarbeitername(con, benutzer)
        if not darf_eintrag_loeschen(benutzer, z["mitarbeiter"], eigener):
            return zurueck_mit_hinweis(
                zurueck, f"„{z['mitarbeiter']}“ ist nicht dein Eintrag. "
                         "Zum Löschen fremder Einträge fehlt dir die Berechtigung.")
        log_eintrag(con, "geloescht", z, wer_handelt(request))
        con.execute("DELETE FROM eintrag WHERE id=?", (eintrag_id,))
    return RedirectResponse(zurueck, status_code=303)


# ⚠️ Diese Route MUSS vor "/eintraege/{eintrag_id}/..." stehen - sonst
# schluckt der Platzhalter das Wort "logbuch" und FastAPI versucht, es
# als Zahl zu lesen. Dieselbe Falle wie bei den Wiki-Aktionen.
def log_baum(zeilen) -> list[dict]:
    """Aus der flachen Logliste eine zweistufige Gliederung machen.

    Oben der Tag, darunter je DATENSATZ ein Block mit allem, was an ihm
    passiert ist. Vorher war es eine durchlaufende Liste, und bei drei
    Aenderungen an derselben Zeile stand dreimal fast dasselbe
    untereinander, ohne dass zu sehen war, dass es dieselbe Zeile ist.

    ⚠️ Gruppiert wird innerhalb eines Tages, nicht ueber alle Tage: die
    Zeitachse ist die eigentliche Ordnung eines Logbuchs. Wer die
    vollstaendige Geschichte eines Datensatzes sehen will, klickt den
    Kopf des Blocks an - das filtert auf genau diese Kennung.

    ⚠️ Zeilen ohne Datensatzbezug (die Sammelaenderung der Datenpflege)
    bekommen jede ihren eigenen Block. Sie zusammenzufassen waere falsch:
    sie haengen an nichts, was man aufklappen koennte.
    """
    tage = []
    for gruppe in _vorgaenge.nach_tagen(zeilen):
        bloecke: list[dict] = []
        nach_id: dict[int, dict] = {}
        for z in gruppe["zeilen"]:
            kennung = z["eintrag_id"]
            # ⚠️ Zusammengefasst wird ueber den ganzen Tag, nicht nur bei
            # unmittelbar aufeinanderfolgenden Zeilen: zwei Aenderungen an
            # derselben Zeile sind oft von einer dritten an einer anderen
            # unterbrochen, und dann waeren es wieder drei lose Bloecke.
            # Die Reihenfolge der Bloecke richtet sich nach ihrem ersten
            # (also neuesten) Schritt - die Zeitachse bleibt lesbar.
            if kennung is None:
                bloecke.append({"eintrag_id": None, "zeilen": [z], "kopf": z})
                continue
            if kennung not in nach_id:
                nach_id[kennung] = {"eintrag_id": kennung, "zeilen": [],
                                    "kopf": z}
                bloecke.append(nach_id[kennung])
            nach_id[kennung]["zeilen"].append(z)
        for b in bloecke:
            b["anzahl"] = len(b["zeilen"])
        tage.append({"wort": gruppe["wort"], "bloecke": bloecke})
    return tage


@app.get("/eintraege/logbuch", response_class=HTMLResponse)
def eintraege_logbuch(request: Request, wer: str = "", q: str = "",
                      eintrag: int = 0, seite: int = 1, hinweis: str = ""):
    """Wer hat an den Datensaetzen etwas geaendert oder geloescht?

    Administratoren vorbehalten (auth.ADMIN_NUR_PFADE). Der Knopf dorthin
    steht in der Uebersicht und ist fuer alle anderen gar nicht da.
    """
    seite = max(1, seite)
    pro_seite = 100
    wo, werte = ["1=1"], []
    if wer.strip():
        wo.append("wer = ?")
        werte.append(wer.strip())
    if q.strip():
        wo.append("(klient LIKE ? OR mitarbeiter LIKE ? OR beschreibung LIKE ? "
                  "OR aenderung LIKE ?)")
        werte += [f"%{q.strip()}%"] * 4
    if eintrag > 0:
        # Die ganze Geschichte eines einzelnen Datensatzes - ueber alle
        # Tage hinweg. Der Weg dorthin ist der Kopf eines Blocks.
        wo.append("eintrag_id = ?")
        werte.append(eintrag)
    bedingung = " AND ".join(wo)

    with db.db() as con:
        gesamt = con.execute(
            f"SELECT COUNT(*) c FROM eintrag_log WHERE {bedingung}",
            werte).fetchone()["c"]
        zeilen = con.execute(
            f"SELECT * FROM eintrag_log WHERE {bedingung} "
            "ORDER BY zeitpunkt DESC, id DESC LIMIT ? OFFSET ?",
            werte + [pro_seite, (seite - 1) * pro_seite]).fetchall()
        # Wer taucht im Logbuch ueberhaupt auf? Grundlage fuer den Filter.
        leute = [r["wer"] for r in con.execute(
            "SELECT DISTINCT wer FROM eintrag_log ORDER BY wer COLLATE NOCASE")]

    seiten = max(1, -(-gesamt // pro_seite))
    return templates.TemplateResponse(
        request=request, name="eintraege_logbuch.html", context={
            "seite_name": "eintraege", "gruppen": log_baum(zeilen),
            "gesamt": gesamt, "leute": leute, "wer": wer.strip(), "q": q.strip(),
            "eintrag": eintrag,
            "seite": seite, "seiten": seiten, "hinweis": hinweis,
            # Nach dem Aufräumen zurück auf denselben Ausschnitt.
            "zurueck": "/eintraege/logbuch?" + urlencode(
                {k: v for k, v in (("wer", wer.strip()), ("q", q.strip()),
                                   ("eintrag", eintrag or ""),
                                   ("seite", seite if seite > 1 else "")) if v}),
            "uhrzeit": _vorgaenge.uhrzeit})


@app.get("/eintraege/{eintrag_id}/bearbeiten", response_class=HTMLResponse)
@app.get("/meinbereich/eintrag/{eintrag_id}/bearbeiten", response_class=HTMLResponse)
def eintrag_formular(request: Request, eintrag_id: int,
                     zurueck: str = "/eintraege", fehler: str = ""):
    with db.db() as con:
        z = con.execute("SELECT * FROM eintrag WHERE id=?", (eintrag_id,)).fetchone()
        if not z:
            raise HTTPException(404, "Eintrag nicht gefunden")
        # Gleiche Regel wie beim Loeschen: die eigenen immer, fremde nur mit
        # dem Recht. Schon hier und nicht erst beim Speichern - sonst tippt
        # man erst einen Text und bekommt danach die Abfuhr.
        if not darf_eintrag_bearbeiten(request.state.benutzer,
                                       z["mitarbeiter"],
                                       eigener_mitarbeitername(
                                           con, request.state.benutzer)):
            return zurueck_mit_hinweis(
                zurueck, f"„{z['mitarbeiter']}“ ist nicht dein Eintrag. "
                         "Zum Bearbeiten fremder Einträge fehlt dir die "
                         "Berechtigung.")
        leute = [r["mitarbeiter"] for r in con.execute(
            "SELECT DISTINCT mitarbeiter FROM eintrag ORDER BY 1")]
        klienten = [r["klient"] for r in con.execute(
            "SELECT DISTINCT klient FROM eintrag ORDER BY 1")]
    return templates.TemplateResponse(request=request, name="bearbeiten.html", context={
        "z": z, "leute": leute, "klienten": klienten, "zurueck": zurueck,
        "fehler": fehler,
        "seite": "meinbereich" if request.url.path.startswith("/meinbereich")
                 else "eintraege"})


@app.post("/eintraege/{eintrag_id}/bearbeiten")
@app.post("/meinbereich/eintrag/{eintrag_id}/bearbeiten")
def eintrag_speichern(request: Request, eintrag_id: int,
                      datum: str = Form(...), start: str = Form(""),
                      ende: str = Form(""), dauer: str = Form(""),
                      klient: str = Form(...), beschreibung: str = Form(""),
                      mitarbeiter: str = Form(...), abrechenbar: str = Form(""),
                      zurueck: str = Form("/eintraege")):

    def zurueck_mit_fehler(text: str):
        return RedirectResponse(
            request.url.path + "?" +
            urlencode({"zurueck": zurueck, "fehler": text}), status_code=303)

    try:
        tag = dt.date.fromisoformat(datum.strip())
    except ValueError:
        return zurueck_mit_fehler("Das Datum ist nicht gültig.")

    beginn = parse_zeit(start) if start.strip() else None
    schluss = parse_zeit(ende) if ende.strip() else None

    minuten = parse_dauer(dauer) if dauer.strip() else None
    if minuten is None:
        minuten = dauer_aus_spanne(beginn, schluss)
    if minuten is None:
        return zurueck_mit_fehler(
            "Die Dauer fehlt. Trag sie als Stunden:Minuten ein, "
            "zum Beispiel 01:30, oder gib Beginn und Ende an.")
    if minuten <= 0:
        return zurueck_mit_fehler("Die Dauer muss größer als null sein.")

    klient = klient.strip() or "Ohne Zuordnung"
    mitarbeiter = mitarbeiter.strip()
    if not mitarbeiter:
        return zurueck_mit_fehler("Ohne Mitarbeiter geht es nicht.")

    neu = {"mitarbeiter": mitarbeiter, "datum": tag.isoformat(), "start": beginn,
           "ende": schluss, "klient": klient,
           "beschreibung": beschreibung.strip(), "dauer_min": int(minuten)}

    with db.db() as con:
        # Gegen den Stand in der Datenbank pruefen, nicht gegen das Formular:
        # der Mitarbeitername steht als aenderbares Feld darin, sonst koennte
        # man ihn beim Speichern einfach auf den eigenen umbiegen.
        vorher = con.execute("SELECT * FROM eintrag WHERE id=?",
                             (eintrag_id,)).fetchone()
        if vorher is None:
            return zurueck_mit_hinweis(zurueck, "Diesen Eintrag gibt es nicht mehr.")
        eigener = eigener_mitarbeitername(con, request.state.benutzer)
        if not darf_eintrag_bearbeiten(request.state.benutzer,
                                       vorher["mitarbeiter"], eigener):
            return zurueck_mit_hinweis(
                zurueck, f"„{vorher['mitarbeiter']}“ ist nicht dein Eintrag. "
                         "Zum Bearbeiten fremder Einträge fehlt dir die "
                         "Berechtigung.")
        # Ebenso wenig darf man ihn auf jemand anderen umschreiben, wenn
        # man fremde Eintraege gar nicht anfassen duerfte.
        if not darf_eintrag_bearbeiten(request.state.benutzer, mitarbeiter,
                                       eigener):
            return zurueck_mit_hinweis(
                zurueck, "Du kannst den Eintrag nicht auf "
                         f"„{mitarbeiter}“ umschreiben – dafür fehlt dir "
                         "die Berechtigung.")
        # ⚠️ Vor dem UPDATE protokollieren, sonst gaebe es nichts mehr zu
        # vergleichen. Aendert sich gar nichts, wird auch nichts notiert -
        # ein Logbuch voller "nichts passiert" liest niemand.
        unterschied = log_unterschied(
            vorher, dict(neu, abrechenbar=1 if abrechenbar else 0))
        if unterschied:
            log_eintrag(con, "geaendert", vorher, wer_handelt(request),
                        unterschied)
        con.execute(
            "UPDATE eintrag SET mitarbeiter=?, datum=?, monat=?, start=?, ende=?, "
            "klient=?, beschreibung=?, dauer_min=?, abrechenbar=?, fingerprint=? "
            "WHERE id=?",
            (mitarbeiter, neu["datum"], tag.strftime("%Y-%m"), beginn, schluss,
             klient, neu["beschreibung"], int(minuten),
             1 if abrechenbar else 0, fingerprint(neu), eintrag_id))

    trenner = "&" if "?" in zurueck else "?"
    return RedirectResponse(
        f"{zurueck}{trenner}" + urlencode({"hinweis": "Eintrag gespeichert."}),
        status_code=303)


# --- Manuelle Zeiterfassung -------------------------------------------------

def zeit_locker(text: str) -> str | None:
    """Nimmt 14:30, 14.30 und 1430 gleichermassen an."""
    text = (text or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{3,4}", text):
        text = text.zfill(4)[:-2] + ":" + text.zfill(4)[-2:]
    return parse_zeit(text)


@app.get("/erfassung")
def erfassung_umleitung(mitarbeiter: str = "", datum: str = ""):
    """Die manuelle Erfassung wohnt seit 0.6.10 auf der Startseite.

    Die Adresse bleibt bestehen, damit gespeicherte Lesezeichen und die
    Rueckverweise aus dem Bearbeiten-Formular nicht ins Leere laufen.
    """
    werte = {k: v for k, v in (("mitarbeiter", mitarbeiter), ("datum", datum)) if v}
    return RedirectResponse("/" + ("?" + urlencode(werte) if werte else ""),
                            status_code=303)


@app.post("/erfassung")
def erfassung_speichern(mitarbeiter: str = Form(""),
                        datum: list[str] = Form([]),
                        klient: list[str] = Form([]),
                        start: list[str] = Form([]),
                        ende: list[str] = Form([]),
                        leistung: list[str] = Form([]),
                        beschreibung: list[str] = Form([])):
    """Legt einen oder mehrere Eintraege an.

    Die Felder kommen als parallele Listen an: jede Zeile des Formulars
    schickt genau einen Wert je Feld, in Dokumentreihenfolge - damit
    stehen die Listen zeilenweise untereinander. Bei nur einer Zeile ist
    das dieselbe Sache wie frueher, nur eben mit einem Element.

    Entweder alles oder nichts: Findet sich in irgendeiner Zeile ein
    Fehler, wird gar nichts gespeichert und die Meldung nennt die
    Zeilennummer. Halb gespeicherte Stapel waeren schlimmer als ein
    Abbruch - man wuesste hinterher nicht, was schon drin steht.
    """
    mitarbeiter = mitarbeiter.strip()
    erstes_datum = (datum[0].strip() if datum else "")

    def zurueck(**mehr):
        werte = {"mitarbeiter": mitarbeiter, "datum": erstes_datum}
        werte.update(mehr)
        # Die Sprungmarke haelt die Seite beim Formular stehen, statt nach
        # dem Speichern wieder ganz oben zu landen.
        return RedirectResponse("/?" + urlencode(werte) + "#erfassen",
                                status_code=303)

    if not mitarbeiter:
        return zurueck(fehler="Wähl oben aus, wer die Zeiten erfasst.")

    # Die Listen auf gleiche Laenge bringen. leistung fehlt ganz, solange
    # keine Leistungsbeschreibungen gepflegt sind - dann gibt es das
    # Auswahlfeld gar nicht.
    anzahl = max(len(datum), len(klient), len(start), len(ende))
    if not anzahl:
        return zurueck(fehler="Es war keine Zeile ausgefüllt.")

    def feld(liste: list[str], nr: int) -> str:
        return (liste[nr] if nr < len(liste) else "").strip()

    # ⚠️ Der Name der betreuten Person kommt aus einem Auswahlfeld und
    # darf deshalb nur einer aus der Liste sein. Das Feld allein reicht
    # als Schutz nicht - ein abgeschicktes Formular kann alles enthalten,
    # und ein Tippfehler legte hier frueher stillschweigend eine zweite
    # "Person" an, die in keiner Auswertung mehr auftauchte.
    with db.db() as con:
        wahl = klientenauswahl(con)
    erlaubt = {norm(n): n for n in wahl["personen"] + wahl["weitere"]}

    saetze = []
    for nr in range(anzahl):
        d, k = feld(datum, nr), feld(klient, nr)
        a, e = feld(start, nr), feld(ende, nr)
        l, b = feld(leistung, nr), feld(beschreibung, nr)
        zeile = nr + 1

        # Vollstaendig leere Zeilen einfach ueberspringen. Sie entstehen,
        # wenn jemand eine Zeile hinzufuegt und dann doch nicht braucht.
        if not any((d, k, a, e, l, b)):
            continue

        fehlt = [name for name, wert in
                 (("Datum", d), ("die betreute Person", k),
                  ("Startzeit", a), ("Endzeit", e))
                 if not wert]
        if fehlt:
            return zurueck(fehler=f"Zeile {zeile}: Es fehlt noch "
                                  f"{' und '.join(fehlt)}.")

        if norm(k) not in erlaubt:
            return zurueck(fehler=f"Zeile {zeile}: „{k}“ steht nicht in der "
                                  "Liste der betreuten Personen. Neue Personen "
                                  "legst du unter Einstellungen an.")
        k = erlaubt[norm(k)]     # immer die gepflegte Schreibweise

        tag = parse_datum(d)
        if tag is None:
            return zurueck(fehler=f"Zeile {zeile}: Das Datum passt nicht. "
                                  "Schreib es als TT.MM.JJJJ.")
        beginn, schluss = zeit_locker(a), zeit_locker(e)
        if beginn is None or schluss is None:
            return zurueck(fehler=f"Zeile {zeile}: Start- und Endzeit "
                                  "brauchen die Form HH:MM.")
        minuten = dauer_aus_spanne(beginn, schluss)
        if not minuten:
            return zurueck(fehler=f"Zeile {zeile}: Start und Ende sind gleich – "
                                  "da kommt keine Dauer heraus.")
        if minuten > 12 * 60:
            return zurueck(fehler=f"Zeile {zeile}: Das wären {hhmm(minuten)} "
                                  "am Stück. Bitte Start und Ende prüfen.")

        # ⚠️ Leistung und Erlaeuterung sind einzeln keine Pflichtfelder,
        # zusammen aber schon: ein Eintrag ohne jede Beschreibung ist im
        # Nachweis wertlos - man sieht die Stunden und weiss nicht mehr,
        # wofuer. Geprueft wird hier und nicht nur im Browser: ein
        # abgeschicktes Formular kann alles enthalten.
        if not l and not b:
            return zurueck(fehler=f"Zeile {zeile}: Wähl eine Leistung oder "
                                  "schreib eine Erläuterung – ganz ohne "
                                  "Angabe lässt sich später nicht mehr "
                                  "nachvollziehen, worum es ging.")

        # Vordefinierte Leistung und freier Text ergaenzen einander: ist
        # beides ausgefuellt, steht die einheitliche Bezeichnung vorn und
        # der eigene Zusatz dahinter. So geht nie eine Eingabe verloren.
        text = ": ".join(teil for teil in (l, b) if teil)
        satz = {"mitarbeiter": mitarbeiter, "datum": tag.isoformat(),
                "start": beginn, "ende": schluss,
                "klient": k or "Ohne Zuordnung",
                "beschreibung": text, "dauer_min": int(minuten)}
        satz["fingerprint"] = fingerprint(satz)
        satz["zeile"] = zeile
        satz["tag"] = tag
        saetze.append(satz)

    if not saetze:
        return zurueck(fehler="Es war keine Zeile ausgefüllt.")

    # Bis 0.8.8 wurde hier gegen den Bestand auf Dubletten geprueft, mit
    # einem Haken zum Uebergehen. Der ist auf Timos Wunsch entfallen: wer
    # von Hand erfasst, weiss, was er tut, und derselbe Besuch am selben Tag
    # zur selben Uhrzeit kommt in der Praxis auch echt vor. Der Fingerprint
    # wird weiter mitgeschrieben - der Listenimport braucht ihn fuer seine
    # eigene Dublettenerkennung in der Vorschau.
    with db.db() as con:
        for satz in saetze:
            con.execute(
                "INSERT INTO eintrag (import_id, mitarbeiter, datum, monat, start, "
                "ende, klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "angelegt_am) VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?)",
                (mitarbeiter, satz["datum"], satz["tag"].strftime("%Y-%m"),
                 satz["start"], satz["ende"], satz["klient"], satz["beschreibung"],
                 satz["dauer_min"],
                 0 if norm(satz["klient"]) in NICHT_ABRECHENBAR else 1,
                 satz["fingerprint"], jetzt()))

    gesamt = sum(satz["dauer_min"] for satz in saetze)
    if len(saetze) == 1:
        return zurueck(hinweis=f"{hhmm(gesamt)} für {saetze[0]['klient']} "
                               "gespeichert.")
    return zurueck(hinweis=f"{len(saetze)} Einträge gespeichert · "
                           f"{hhmm(gesamt)} gesamt.")






def neuigkeiten(request) -> dict | None:
    """Der jüngste Changelog-Eintrag, solange das Konto ihn nicht kennt.

    Wird von base.html bei jedem Seitenaufbau gefragt - deshalb steht
    hier kein Datenbankzugriff, wenn es nichts zu zeigen gibt: der
    Vergleich laeuft gegen das Feld, das die Anmeldung ohnehin schon
    geladen hat.

    ⚠️ Bewusst nicht nur direkt nach dem Login: wer den Hinweis dort
    wegklickt oder das Fenster schliesst, bekaeme ihn sonst nie wieder.
    So steht er, bis er einmal ausdruecklich zur Kenntnis genommen wurde.
    """
    benutzer = getattr(request.state, "benutzer", None)
    if not benutzer:
        return None
    try:
        gesehen = benutzer["gesehen_version"]
    except (KeyError, IndexError):
        return None            # Datenbank noch ohne die Spalte
    if gesehen == VERSION or not CHANGELOG:
        return None
    stand = CHANGELOG[-1]
    if stand["version"] != VERSION:
        return None            # Version und Changelog laufen auseinander
    return stand


templates.env.globals["neuigkeiten"] = neuigkeiten


@app.post("/neuigkeiten/gelesen")
def neuigkeiten_gelesen(request: Request, weiter: str = Form("/")):
    """Merkt sich, dass dieses Konto die Fassung kennt."""
    with db.db() as con:
        con.execute("UPDATE benutzer SET gesehen_version=? WHERE id=?",
                    (VERSION, request.state.benutzer["id"]))
    # ⚠️ Nur eigene Pfade, kein fremdes Ziel: sonst waere das Formular
    # eine offene Weiterleitung.
    ziel = weiter if weiter.startswith("/") and not weiter.startswith("//") else "/"
    return RedirectResponse(ziel, status_code=303)


@app.get("/changelog", response_class=HTMLResponse)
def changelog(request: Request):
    # Neueste Version oben, die Liste selbst ist chronologisch gepflegt
    return templates.TemplateResponse(request=request, name="changelog.html", context={
        "staende": list(reversed(CHANGELOG)), "seite": "changelog"})



@app.get("/gesundheit")
def gesundheit():
    with db.db() as con:
        con.execute("SELECT 1")
    return {"status": "ok", "zeit": jetzt(), "version": VERSION}

# --- Verwaltungsvorgaenge ---------------------------------------------------
#
# Das Modul steckt in vorgaenge.py. Erst hier eingebunden, damit die Templates
# und Filter oben schon fertig eingerichtet sind.

from . import vorgaenge as _vorgaenge  # noqa: E402

def _eigener_name(request) -> str:
    """Mitarbeitername des angemeldeten Kontos - fuer Vorbelegungen."""
    with db.db() as con:
        return eigener_mitarbeitername(con, request.state.benutzer)


_vorgaenge.setup(templates, {"eigener_name": _eigener_name})

# ⚠️ mail.py darf main.py nicht importieren (Ringschluss), braucht aber
# den Bewilligungsstand. Deshalb haengt die Funktion hier ein - dieselbe
# Rechnung fuer die Karte in "Mein Bereich" und fuer die Erinnerungsmail.
mail.bewilligungen_holen = bewilligungen_pruefen
app.include_router(_vorgaenge.router)

# --- Datenpflege ------------------------------------------------------------
#
# ⚠️ Nach demselben Modulmuster wie die uebrigen (Abschnitt 3). Sie
# bekommt nur, was sie braucht: die Sicherungsfunktion.

from . import datenpflege as _datenpflege  # noqa: E402
_datenpflege.setup(templates, {"sicherung_anlegen": sicherung_anlegen,
                               "log_eintrag": log_eintrag,
                               "wer_handelt": wer_handelt})
app.include_router(_datenpflege.router)


# --- Einstellungen ----------------------------------------------------------
#
# Ebenfalls ein eigenes Modul (einstellungen.py). Es bekommt hier die Werte
# gereicht, die es aus main.py braucht - so gibt es keinen Ringschluss beim
# Import, und main.py bleibt die einzige Stelle, an der Pfade und
# Umgebungsvariablen gelesen werden.

from . import einstellungen as _einstellungen  # noqa: E402

_einstellungen.setup(templates, {
    "jetzt": jetzt,
    "heute": lambda: dt.date.today().isoformat(),
    "bewilligungslage": bewilligungslage,
    "BEWILLIGUNG_HANDLUNG": BEWILLIGUNG_HANDLUNG,
    "monat_wort": monat_wort,
    "VERSION": VERSION,
    "MAX_UPLOAD_MB": MAX_UPLOAD_MB,
    "WECKER_INTERVALL": WECKER_INTERVALL,
    "SPRUCH_DATEI": SPRUCH_DATEI,
    "IDEEN_DATEI": IDEEN_DATEI,
    "STRINGS_DATEI": STRINGS_DATEI,
    "TEXTE_STANDARD": TEXTE_STANDARD,
    "SICHERUNG_PFAD": SICHERUNG_PFAD,
    "sicherungsdateien": sicherungsdateien,
    "sicherung_anlegen": sicherung_anlegen,
    "FUSS_STANDARD": FUSS_STANDARD,
})
app.include_router(_einstellungen.router)


# --- Fuhrpark ---------------------------------------------------------------
#
# Fahrzeuge, ihre Ereignisse und die Auswertung stecken in kfz.py. Dasselbe
# Muster wie oben: eigener Router, eingebunden erst hier, wenn die Templates
# stehen. Das Modul braucht nichts aus main.py ausser den Templates.

from . import kfz as _kfz  # noqa: E402

_kfz.setup(templates)
app.include_router(_kfz.router)


# --- Wiki -------------------------------------------------------------------
#
# Die Wissensbasis liegt als Markdown-Dateien im Ordner /wiki, das Modul
# steckt in wiki.py. Wie bei einstellungen.py bekommt es den Pfad hier
# gereicht, damit main.py die einzige Stelle bleibt, an der
# Umgebungsvariablen gelesen werden.

_wiki.setup(templates, {"WIKI_PFAD": WIKI_PFAD})
app.include_router(_wiki.router)


# --- Dateien ----------------------------------------------------------------
#
# Bilder, PDFs und Office-Dateien im Ordner /files, damit sich im Wiki
# etwas verlinken laesst, ohne die Datei ueber die Freigabe dorthin legen
# zu muessen. Wie beim Wiki ist der Ordner selbst der Bestand - keine
# Tabelle, damit derselbe Ordner auch ueber die Dateifreigabe nutzbar
# bleibt.

from . import dateien as _dateien  # noqa: E402

_dateien.setup(templates, {"FILES_PFAD": FILES_PFAD,
                           "MAX_UPLOAD_MB": MAX_UPLOAD_MB})
app.include_router(_dateien.router)


# --- Ideen ------------------------------------------------------------------
#
# Das kleine Ticketsystem, seit 1.32 ein eigenes Modul. Es braucht von
# hier nur den Pfad der Ideendatei.

from . import ideen as _ideen  # noqa: E402

_ideen.setup(templates, {"IDEEN_DATEI": IDEEN_DATEI})
app.include_router(_ideen.router)


# --- Export -----------------------------------------------------------------
#
# xlsx und csv der gefilterten Zeiten, seit 1.32 ein eigenes Modul. Es
# bekommt gar nichts gereicht: den Filter holt es sich aus rechnen.py,
# also aus derselben Funktion wie Auswertung und Uebersicht.

from . import export as _export  # noqa: E402

app.include_router(_export.router)


# --- Auswertung -------------------------------------------------------------
#
# Soll-Ist-Vergleich je betreuter Person und Monat, seit 1.32 ein eigenes
# Modul. Den gemeinsamen Filter holt es sich aus rechnen.py.

from . import auswertung as _auswertung  # noqa: E402

_auswertung.setup(templates)
app.include_router(_auswertung.router)


# --- Mein Bereich -----------------------------------------------------------
#
# Die eigenen Zahlen jeder angemeldeten Person, seit 1.32 ein eigenes
# Modul. Es braucht von hier nur den Spruch der Startseite.
#
# ⚠️ Die drei Routen /meinbereich/eintrag/... bleiben oben in main.py -
# es sind dieselben Funktionen wie unter /eintraege/..., nur mit einem
# zweiten Decorator darueber (siehe dort).

from . import meinbereich as _meinbereich  # noqa: E402

_meinbereich.setup(templates, {"spruch": spruch})
app.include_router(_meinbereich.router)
