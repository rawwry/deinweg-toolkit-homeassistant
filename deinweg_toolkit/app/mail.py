"""E-Mail-Benachrichtigungen: Zugangsdaten, Vorlagen und der Wecker.

Anlaesse:
1. Ein Verwaltungsvorgang wird ueberfaellig -> Mail an die zustaendige Person.
2. Monatsanfang -> Mail an alle abgabepflichtigen Mitarbeitenden, die fuer
   den abgelaufenen Monat noch keine Zeiten eingereicht haben.
3. Bewilligungen laufen aus/fehlen -> eine Sammelmail an feste Empfaenger.
4. Neue Aufgabe zugewiesen -> gesammelte Mail an die zustaendige Person.
   Als einziger Anlass minuten- statt stundengenau (main.zuweisungs_schleife).

Grundgedanken:
* Zugangsdaten und Vorlagen liegen in der Tabelle "konfig" (Datenbank), nicht
  im Code und nicht in strings.txt - sie sollen ueber die Oberflaeche
  pflegbar sein und enthalten ein Passwort.
* Jede verschickte Mail wird in "benachrichtigung" vermerkt. Der Wecker
  laeuft regelmaessig, verschickt aber pro Anlass nur einmal.
* Empfaenger ist die E-Mail-Adresse des Benutzerkontos. Die Zuordnung
  laeuft ueber den Namen: benutzer.benutzername wird mit dem Namen der
  zustaendigen Person bzw. des Mitarbeiters verglichen (Gross-/Kleinschreibung
  egal). Wer keinen passenden Login mit E-Mail-Adresse hat, bekommt keine
  Mail - das wird im Log vermerkt, ist aber kein Fehler.
"""

from __future__ import annotations

import datetime as dt
import re
import smtplib
import ssl
from email.message import EmailMessage

from . import db

# --- Wann am Tag verschickt wird ----------------------------------------------

# ⚠️ Erinnerungen an die Zeiterfassung und an Fristen gehen ab 8 Uhr
# morgens heraus, nicht irgendwann in der Nacht. Der Wecker schaut
# stuendlich vorbei (main.wecker_schleife); vor dieser Stunde tut er
# nichts, ab ihr genau einmal - dafuer sorgt wie bisher der Vermerk in
# "benachrichtigung", nicht die Uhrzeit.
#
# Bewusst "ab 8 Uhr" und nicht "um genau 8 Uhr": war der Pi um acht aus,
# soll die Erinnerung beim naechsten Durchlauf trotzdem noch herausgehen
# statt fuer diesen Tag lautlos auszufallen. Und bewusst die lokale Zeit -
# dafuer steht tzdata im Dockerfile (siehe CLAUDE.md, Abschnitt 2).
VERSANDSTUNDE = 8


def versandzeit_erreicht(jetzt: dt.datetime | None = None) -> bool:
    """Ist es an diesem Tag schon nach der Versandstunde?"""
    return (jetzt or dt.datetime.now()).hour >= VERSANDSTUNDE


# --- Standardwerte -----------------------------------------------------------

# ⚠️⚠️ HIER STEHEN KEINE ZUGANGSDATEN. Bis 1.30.1 standen Mailserver,
# Absenderadresse und Kontoname der echten Einrichtung als Standardwerte
# in dieser Datei - und dieses Repository ist oeffentlich. Damit lagen
# zwei Drittel eines Postfachzugangs frei lesbar auf GitHub; es fehlte
# nur das Passwort.
#
# Die Zugangsdaten gehoeren ausschliesslich in die Datenbank
# (Einstellungen -> E-Mail-Versand). Sie stehen dort ohnehin, sobald
# jemand einmal gespeichert hat, und gewinnen gegen diese Standardwerte.
# Wer hier etwas eintraegt, veroeffentlicht es - auch einen Servernamen,
# auch eine Absenderadresse.
STANDARD = {
    "smtp_absender": "",
    "smtp_absendername": "Dein Weg Toolkit",
    "smtp_server": "",
    "smtp_port": "465",
    "smtp_benutzer": "",
    "smtp_passwort": "",
    "smtp_sicherheit": "ssl",
    "mail_aktiv": "0",
    # Fristen aus der Aufgabenverwaltung. Standard an - das war schon
    # immer so, und ein stillschweigend abgeschalteter Anlass waere eine
    # boese Ueberraschung.
    "frist_aktiv": "1",
    "frist_vorlauf": "0",
    "frist_kopie": "",
    # Fehlende Monatsabgaben. Ebenfalls Standard an.
    "abgabe_aktiv": "1",
    "abgabe_tag": "1",
    "vorlage_frist_betreff": "Fristsache: {titel} ({klient})",
    "vorlage_frist_text": (
        "Hallo {name},\n\n"
        "der folgende Vorgang ist {lage}:\n\n"
        "  Betreute Person: {klient}\n"
        "  Vorgang:         {titel}\n"
        "  Vorgangsart:     {art}\n"
        "  Status:          {status}\n"
        "  Frist:           {frist}\n\n"
        "Bitte kümmere dich darum oder setze eine neue Wiedervorlage.\n\n"
        "Diese Nachricht wurde automatisch erstellt."
    ),
    # Erinnerung an auslaufende Bewilligungen. Standard aus - erst wenn
    # jemand die Empfaengerin benennt, ergibt sie Sinn.
    "bewilligung_aktiv": "0",
    "bewilligung_tage": "60",
    "bewilligung_empfaenger": "",
    "vorlage_bewilligung_betreff": "Bewilligungen: {anzahl} Fall/Fälle offen",
    "vorlage_bewilligung_text": (
        "Hallo {name},\n\n"
        "bei den folgenden betreuten Personen läuft die Bewilligung aus, "
        "ist bereits abgelaufen oder fehlt ganz:\n\n"
        "{liste}\n\n"
        "Solange nichts Neues vorliegt, rechnet die Auswertung für diese "
        "Monate ohne Kontingent.\n\n"
        "Diese Nachricht wurde automatisch erstellt."
    ),
    "vorlage_abgabe_betreff": "Erinnerung: Zeiten für {monat} noch offen",
    "vorlage_abgabe_text": (
        "Hallo {name},\n\n"
        "für {monat} liegen von dir noch keine erfassten Zeiten vor.\n\n"
        "Bitte reiche deine Arbeitsliste nach oder trage die Zeiten von Hand "
        "ein.\n\n"
        "Diese Nachricht wurde automatisch erstellt."
    ),
    # Neue Aufgabe zugewiesen -> Mail an die zustaendige Person. Standard
    # aus: erst wenn jemand es einschaltet, ergibt es Sinn. Der Verzug
    # sammelt mehrere kurz nacheinander angelegte Aufgaben in eine Mail.
    "zuweisung_aktiv": "0",
    "zuweisung_verzug": "2",
    "vorlage_zuweisung_betreff": "Neue Aufgabe{mehrzahl} für dich ({anzahl})",
    "vorlage_zuweisung_text": (
        "Hallo {name},\n\n"
        "dir {wurde} folgende Aufgabe{mehrzahl} zugewiesen:\n\n"
        "{liste}\n\n"
        "Du findest sie unter „Aufgaben“.\n\n"
        "Diese Nachricht wurde automatisch erstellt."
    ),
    # Aufgabe erledigt -> Mail an die Person, die sie angelegt hat.
    # Standard aus, wie bei jedem Anlass, den es vorher nicht gab.
    "erledigt_aktiv": "0",
    "vorlage_erledigt_betreff": "Erledigt: {titel}",
    "vorlage_erledigt_text": (
        "Hallo {name},\n\n"
        "die von dir angelegte Aufgabe wurde als **{status}** markiert:\n\n"
        "  Aufgabe:         {titel}\n"
        "  Betreute Person: {klient}\n"
        "  Aufgabenart:     {art}\n"
        "  Zuständig:       {zustaendig}\n"
        "  Abgeschlossen:   {erledigt_am} von {wer}\n\n"
        "Diese Nachricht wurde automatisch erstellt."
    ),
}

# Diese Schluessel werden in der Oberflaeche nie im Klartext zurueckgegeben
GEHEIM = {"smtp_passwort"}


def konfig_lesen(con=None) -> dict:
    """Alle Einstellungen, fehlende Schluessel mit Standardwert aufgefuellt."""
    def holen(c):
        werte = dict(STANDARD)
        for r in c.execute("SELECT schluessel, wert FROM konfig"):
            if r["wert"] is not None:
                werte[r["schluessel"]] = r["wert"]
        return werte

    if con is not None:
        return holen(con)
    with db.db() as c:
        return holen(c)


def konfig_schreiben(con, werte: dict) -> None:
    jetzt = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    for schluessel, wert in werte.items():
        con.execute(
            "INSERT INTO konfig (schluessel, wert, geaendert_am) VALUES (?,?,?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert, "
            "geaendert_am=excluded.geaendert_am",
            (schluessel, wert, jetzt))


def fuellen(vorlage: str, werte: dict) -> str:
    """Platzhalter ersetzen, ohne bei unbekannten Klammern abzustuerzen."""
    text = vorlage
    for schluessel, wert in werte.items():
        text = text.replace("{" + schluessel + "}", str(wert))
    return text


# --- Einfache Textformatierung in den Vorlagen -------------------------------
#
# ⚠️ Seit 1.30 duerfen die Vorlagen ein paar Markierungen tragen -
# **fett**, *kursiv*, „# Ueberschrift", „- Aufzaehlung" und nackte Links.
# Verschickt wird die Nachricht daraufhin ZWEIFACH: als Klartext (die
# Markierungen sind dort herausgeraeumt) und als HTML. Jedes Mailprogramm
# nimmt sich, was es kann.
#
# ⚠️ Bewusst ein eigener, winziger Wandler und nicht markdown.zu_html():
# der baut Wiki-HTML mit Klassen, und ein Mailprogramm kennt unser
# Stylesheet nicht. Hier stehen die paar Angaben deshalb direkt am Tag.
# Aus demselben Grund bewusst nur diese fuenf Formen - alles darueber
# hinaus sieht in Outlook ohnehin anders aus als gedacht.

_FETT = re.compile(r"\*\*(.+?)\*\*", re.S)
_KURSIV = re.compile(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.S)
_LINK = re.compile(r"(https?://[^\s<>\"']+)")


def klartext(text: str) -> str:
    """Die Markierungen herausraeumen - fuer die Nur-Text-Fassung."""
    zeilen = []
    for zeile in (text or "").split("\n"):
        blank = zeile.strip()
        if blank.startswith("#"):
            zeile = blank.lstrip("#").strip()
        elif blank.startswith(("- ", "* ")):
            zeile = "  • " + blank[2:].strip()
        zeile = _FETT.sub(r"\1", zeile)
        zeile = _KURSIV.sub(r"\1", zeile)
        zeilen.append(zeile)
    return "\n".join(zeilen)


def als_html(text: str) -> str:
    """Denselben Text als schlichtes HTML, mit Angaben direkt am Tag."""
    raus, liste = [], False

    def zeichen(t: str) -> str:
        t = (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        t = _FETT.sub(r"<strong>\1</strong>", t)
        t = _KURSIV.sub(r"<em>\1</em>", t)
        return _LINK.sub(r'<a href="\1">\1</a>', t)

    for zeile in (text or "").split("\n"):
        blank = zeile.strip()
        if blank.startswith(("- ", "* ")):
            if not liste:
                raus.append("<ul style=\"margin:8px 0;padding-left:20px\">")
                liste = True
            raus.append(f"<li>{zeichen(blank[2:].strip())}</li>")
            continue
        if liste:
            raus.append("</ul>")
            liste = False
        if blank.startswith("#"):
            stufe = min(3, len(blank) - len(blank.lstrip("#")))
            inhalt = zeichen(blank.lstrip("#").strip())
            groesse = {1: "19px", 2: "16px", 3: "14px"}[stufe]
            raus.append(f'<div style="font-size:{groesse};font-weight:700;'
                        f'margin:16px 0 6px">{inhalt}</div>')
        elif not blank:
            raus.append("<div style=\"height:10px\"></div>")
        else:
            # ⚠️ Fuehrende Leerzeichen bleiben stehen: die
            # Auslieferungsvorlagen richten damit ihre Wertetabellen aus.
            vor = len(zeile) - len(zeile.lstrip(" "))
            raus.append("<div>" + "&nbsp;" * vor + zeichen(blank) + "</div>")
    if liste:
        raus.append("</ul>")
    return ('<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,'
            'sans-serif;font-size:14px;line-height:1.55;color:#272827">'
            + "".join(raus) + "</div>")


# --- Versand -----------------------------------------------------------------

def senden(empfaenger: str, betreff: str, text: str,
           konfig: dict | None = None) -> tuple[bool, str]:
    """Verschickt eine Mail. Gibt (erfolg, meldung) zurueck."""
    k = konfig or konfig_lesen()
    server = (k.get("smtp_server") or "").strip()
    # Falls jemand die Adresse mit http:// davor eintraegt - das ist ein
    # Mailserver, kein Webserver, also Schema wegschneiden.
    for praefix in ("https://", "http://", "smtp://", "smtps://"):
        if server.lower().startswith(praefix):
            server = server[len(praefix):]
    server = server.rstrip("/")

    if not server or not empfaenger:
        return False, "Server oder Empfänger fehlt"
    try:
        port = int(k.get("smtp_port") or 465)
    except ValueError:
        return False, "Port ist keine Zahl"

    nachricht = EmailMessage()
    absender = (k.get("smtp_absender") or "").strip()
    name = (k.get("smtp_absendername") or "").strip()
    nachricht["From"] = f"{name} <{absender}>" if name else absender
    nachricht["To"] = empfaenger
    nachricht["Subject"] = betreff
    # ⚠️ Zweifach: Klartext fuer alles, HTML fuer die Programme, die es
    # koennen. set_content zuerst, add_alternative danach - dann steht der
    # Klartext als Rueckfall an erster Stelle, wie es die Norm verlangt.
    nachricht.set_content(klartext(text))
    nachricht.add_alternative(als_html(text), subtype="html")

    benutzer = (k.get("smtp_benutzer") or "").strip()
    passwort = k.get("smtp_passwort") or ""
    sicherheit = (k.get("smtp_sicherheit") or "ssl").lower()

    try:
        if sicherheit == "ssl":
            umgebung = ssl.create_default_context()
            with smtplib.SMTP_SSL(server, port, context=umgebung, timeout=20) as s:
                if benutzer:
                    s.login(benutzer, passwort)
                s.send_message(nachricht)
        else:
            with smtplib.SMTP(server, port, timeout=20) as s:
                if sicherheit == "starttls":
                    s.starttls(context=ssl.create_default_context())
                if benutzer:
                    s.login(benutzer, passwort)
                s.send_message(nachricht)
        return True, "gesendet"
    except Exception as e:  # bewusst breit: der Wecker darf nie abstuerzen
        return False, f"{type(e).__name__}: {e}"


def schon_gesendet(con, art: str, bezug: str, empfaenger: str) -> bool:
    return con.execute(
        "SELECT 1 FROM benachrichtigung WHERE art=? AND bezug=? AND empfaenger=? "
        "AND erfolg=1", (art, bezug, empfaenger)).fetchone() is not None


def vermerken(con, art: str, bezug: str, empfaenger: str,
              erfolg: bool, meldung: str) -> None:
    con.execute(
        "INSERT INTO benachrichtigung (art, bezug, empfaenger, gesendet_am, "
        "erfolg, meldung) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(art, bezug, empfaenger) DO UPDATE SET "
        "gesendet_am=excluded.gesendet_am, erfolg=excluded.erfolg, "
        "meldung=excluded.meldung",
        (art, bezug, empfaenger, dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
         1 if erfolg else 0, meldung))


def adresse_fuer(con, name: str) -> str | None:
    """E-Mail-Adresse des Benutzerkontos, das zu 'name' gehoert.

    Zwei Wege, in dieser Reihenfolge:
    1. Das Konto ist ausdruecklich diesem Mitarbeiter zugeordnet
       (benutzer.mitarbeiter). Das ist der verlaessliche Weg.
    2. Rueckfall auf Namensgleichheit mit dem Benutzernamen - fuer Konten,
       bei denen noch keine Zuordnung gepflegt wurde. Beruecksichtigt nur
       Konten ohne gesetzte Zuordnung, damit eine bewusst auf jemand anderen
       gesetzte Zuordnung nicht heimlich umgangen wird.
    """
    if not name:
        return None
    name = name.strip()
    r = con.execute(
        "SELECT email FROM benutzer WHERE aktiv=1 AND email IS NOT NULL "
        "AND TRIM(email) <> '' AND mitarbeiter IS NOT NULL "
        "AND LOWER(TRIM(mitarbeiter))=LOWER(?)", (name,)).fetchone()
    if r:
        return r["email"]
    r = con.execute(
        "SELECT email FROM benutzer WHERE aktiv=1 AND email IS NOT NULL "
        "AND TRIM(email) <> '' AND (mitarbeiter IS NULL OR TRIM(mitarbeiter)='') "
        "AND LOWER(benutzername)=LOWER(?)", (name,)).fetchone()
    return r["email"] if r else None


# ⚠️ Hier haengt main.py seine Funktion ein, die den Bewilligungsstand
# ausrechnet. mail.py darf main.py nicht importieren (Ringschluss), und
# dieselbe Regel zweimal zu schreiben waere schlimmer als dieser Haken -
# die beiden Fassungen liefen frueher oder spaeter auseinander.
bewilligungen_holen = None


# --- Die Anlaesse -------------------------------------------------------------

# ⚠️ Muss zu vorgaenge.ABGESCHLOSSEN passen; bewusst eine eigene
# Kopie, weil mail.py vorgaenge.py nicht importieren darf.
ABGESCHLOSSEN = ("Erledigt",)


def pruefe_fristen(con, k: dict) -> list[str]:
    """Fristen aus der Aufgabenverwaltung -> Mail an die Zustaendige.

    Mit einem Vorlauf gibt es zwei Anlaesse je Frist: einmal die
    Vorwarnung, sobald sie in den Vorlauf faellt, und einmal die Meldung,
    wenn sie tatsaechlich ueberschritten ist.

    ⚠️ Deshalb traegt der Bezug bei der Vorwarnung ein ``:vor``. Ohne das
    haette die Vorwarnung die spaetere Meldung mitgesperrt - man wuerde
    drei Tage vorher erinnert und danach nie wieder.
    """
    if k.get("frist_aktiv") != "1":
        return []
    # ⚠️ Erst ab der Versandstunde. Sonst laege die Erinnerung morgens um
    # halb vier im Postfach - der Wecker schaut stuendlich vorbei.
    if not versandzeit_erreicht():
        return []
    protokoll = []
    heute = dt.date.today()
    try:
        vorlauf = max(0, min(365, int(k.get("frist_vorlauf") or 0)))
    except ValueError:
        vorlauf = 0
    grenze = (heute + dt.timedelta(days=vorlauf)).isoformat()
    platzhalter = ",".join("?" * len(ABGESCHLOSSEN))
    zeilen = con.execute(
        f"SELECT * FROM vorgang WHERE frist IS NOT NULL AND TRIM(frist) <> '' "
        f"AND frist <= ? AND status NOT IN ({platzhalter})",
        [grenze, *ABGESCHLOSSEN]).fetchall()

    kopie = empfaengerliste(k.get("frist_kopie"))

    for v in zeilen:
        try:
            tage = (heute - dt.date.fromisoformat(v["frist"])).days
        except ValueError:
            tage = 0
        ueberfaellig = tage > 0
        # Bezug enthaelt die Frist: wird sie verschoben, darf erneut erinnert
        # werden, ohne dass die alte Mail das blockiert.
        bezug = f"vorgang:{v['id']}:{v['frist']}"
        if not ueberfaellig:
            bezug += ":vor"
        # ⚠️ Seit 1.30 koennen mehrere Personen zustaendig sein - jede
        # bekommt die Fristmeldung. Ein Aufruf mit dem ganzen Feld
        # („Anna, Bruno") fände nie eine Adresse.
        adressen = []
        for name in empfaengerliste(v["zustaendig"]):
            a = adresse_fuer(con, name)
            if a and a not in adressen:
                adressen.append(a)
        if not adressen:
            protokoll.append(
                f"Vorgang {v['id']}: kein Login mit E-Mail für „{v['zustaendig']}“")
            continue
        if ueberfaellig:
            lage = f"seit {tage} Tag{'en' if tage != 1 else ''} überfällig"
        elif tage == 0:
            lage = "heute fällig"
        else:
            lage = f"in {-tage} Tag{'en' if tage != -1 else ''} fällig"
        werte = {
            "name": v["zustaendig"], "klient": v["klient"], "titel": v["titel"],
            "art": v["art"], "status": v["status"], "tage": abs(tage),
            "lage": lage,
            "frist": dt.date.fromisoformat(v["frist"]).strftime("%d.%m.%Y")
                     if v["frist"] else "",
            "beschreibung": v["beschreibung"] or "",
        }
        betreff = fuellen(k["vorlage_frist_betreff"], werte)
        text = fuellen(k["vorlage_frist_text"], werte)

        # Die Zustaendige zuerst, dann alle, die mitlesen sollen. Dieselbe
        # Nachricht, derselbe Bezug - der Sperrvermerk haengt an der
        # Adresse, also bekommt jede Person ihre Mail genau einmal.
        ziele = list(adressen)
        for name in kopie:
            weitere = adresse_fuer(con, name)
            if weitere and weitere not in ziele:
                ziele.append(weitere)

        for ziel in ziele:
            if schon_gesendet(con, "frist", bezug, ziel):
                continue
            erfolg, meldung = senden(ziel, betreff, text, k)
            vermerken(con, "frist", bezug, ziel, erfolg, meldung)
            protokoll.append(
                f"Vorgang {v['id']} an {ziel}: {'ok' if erfolg else meldung}")
    return protokoll


def monatswort(monat: str) -> str:
    namen = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]
    try:
        jahr, nr = monat.split("-")
        return f"{namen[int(nr) - 1]} {jahr}"
    except (ValueError, IndexError):
        return monat


def pruefe_abgaben(con, k: dict, monat: str | None = None) -> list[str]:
    """Wer hat fuer den abgelaufenen Monat nichts eingereicht?

    ``abgabe_tag`` verschiebt den Stichtag: viele Teams haben bis zum
    fuenften Zeit, und eine Erinnerung am Ersten waere dann nur laestig.
    Vorher ging sie in der Nacht zum Ersten heraus.
    """
    protokoll = []
    if k.get("abgabe_aktiv") != "1":
        return []
    # ⚠️ Wie bei den Fristen: erst ab der Versandstunde. Die Pruefung
    # steht innerhalb von "monat is None", damit ein ausdruecklich
    # angefordeter Probeversand aus den Einstellungen jederzeit geht -
    # da drueckt jemand bewusst auf den Knopf.
    if monat is None:
        if not versandzeit_erreicht():
            return []
        heute = dt.date.today()
        try:
            stichtag = max(1, min(28, int(k.get("abgabe_tag") or 1)))
        except ValueError:
            stichtag = 1
        if heute.day < stichtag:
            return []
        letzter = heute.replace(day=1) - dt.timedelta(days=1)
        monat = letzter.strftime("%Y-%m")

    team = con.execute(
        "SELECT name FROM mitarbeiter WHERE aktiv=1 AND abgabepflicht=1").fetchall()
    for m in team:
        vorhanden = con.execute(
            "SELECT 1 FROM eintrag WHERE mitarbeiter=? AND monat=? LIMIT 1",
            (m["name"], monat)).fetchone()
        if vorhanden:
            continue
        bezug = f"abgabe:{monat}"
        adresse = adresse_fuer(con, m["name"])
        if not adresse:
            protokoll.append(f"{m['name']}: kein Login mit E-Mail hinterlegt")
            continue
        if schon_gesendet(con, "abgabe", bezug, adresse):
            continue
        werte = {"name": m["name"], "monat": monatswort(monat),
                 "monat_kurz": monat}
        erfolg, meldung = senden(
            adresse, fuellen(k["vorlage_abgabe_betreff"], werte),
            fuellen(k["vorlage_abgabe_text"], werte), k)
        vermerken(con, "abgabe", bezug, adresse, erfolg, meldung)
        protokoll.append(f"{m['name']} an {adresse}: {'ok' if erfolg else meldung}")
    return protokoll


def pruefe_bewilligungen(con, k: dict) -> list[str]:
    """Auslaufende, abgelaufene und fehlende Bewilligungen -> eine Mail.

    Bewusst EINE Sammelmail statt einer je Person: es geht um eine Liste,
    die man einmal durchgeht, nicht um zwanzig einzelne Vorgaenge. Und
    bewusst hoechstens einmal je Woche - taeglich dieselbe Liste zu
    bekommen, bis der Bescheid da ist, waere nach drei Tagen Rauschen.
    """
    if k.get("bewilligung_aktiv") != "1":
        return []
    if bewilligungen_holen is None:
        return ["Bewilligungen: Rechenfunktion nicht eingehängt"]

    namen = empfaengerliste(k.get("bewilligung_empfaenger"))
    if not namen:
        return ["Bewilligungen: niemand als Empfänger eingetragen"]

    try:
        vorlauf = int(k.get("bewilligung_tage") or 60)
    except ValueError:
        vorlauf = 60

    # ⚠️ "grundwert" bleibt aussen vor, obwohl die Lage seit 1.20 eine
    # echte Luecke ist (der Grundwert rechnet nicht mehr mit). Grund: das
    # sind Altbestaende, und die erste Mail nach dem Update haette den
    # gesamten Bestand auf einmal gemeldet. Aufgeraeumt wird ueber die
    # Umzugshilfe in den Einstellungen; die zeigt sie deutlich genug.
    # Sobald dort nichts mehr steht, kann diese Zeile weg.
    faelle = [b for b in bewilligungen_holen(con, vorlauf)
              if b["art"] != "grundwert"]
    if not faelle:
        return []

    # Ein Bezug je Kalenderwoche: dieselbe Liste kommt nicht taeglich.
    # ⚠️ Der Bezug traegt den Namen mit. Ohne ihn haette eine bereits an
    # die erste Person verschickte Mail alle weiteren Empfaenger fuer
    # diese Woche mitgesperrt.
    jahr, woche, _ = dt.date.today().isocalendar()
    grundbezug = f"bewilligung:{jahr}-KW{woche:02d}"

    zeilen = []
    for b in faelle:
        if b["art"] == "abgelaufen":
            wann = b.get("seit") or ""
            wort = ("abgelaufen seit " + _datum(wann)) if wann else "abgelaufen"
        elif b["art"] == "laeuft_aus":
            wort = f"läuft am {_datum(b.get('bis'))} aus (noch {b.get('tage')} Tage)"
        elif b["art"] == "kuenftig":
            wort = f"gilt erst ab {_datum(b.get('ab'))}"
        else:
            wort = "keine Bewilligung hinterlegt"
        zeilen.append(f"  {b['name']}: {wort}")

    liste = "\n".join(zeilen)
    protokoll = []
    for name in namen:
        adresse = adresse_fuer(con, name)
        if not adresse:
            protokoll.append(f"Bewilligungen: kein Login mit E-Mail für „{name}“")
            continue
        bezug = f"{grundbezug}:{name}"
        if schon_gesendet(con, "bewilligung", bezug, adresse):
            continue
        werte = {"name": name, "anzahl": len(faelle), "liste": liste}
        erfolg, meldung = senden(
            adresse, fuellen(k["vorlage_bewilligung_betreff"], werte),
            fuellen(k["vorlage_bewilligung_text"], werte), k)
        vermerken(con, "bewilligung", bezug, adresse, erfolg, meldung)
        protokoll.append(f"Bewilligungen ({len(faelle)}) an {adresse}: "
                         f"{'ok' if erfolg else meldung}")
    return protokoll


def pruefe_zuweisungen(con, k: dict) -> list[str]:
    """Neu zugewiesene Aufgaben -> eine gesammelte Mail je Zustaendiger.

    ⚠️ Gesammelt, nicht je Aufgabe: wer in fuenf Minuten drei Aufgaben
    bekommt, soll eine Mail mit drei Zeilen erhalten, nicht drei Mails.
    Dafuer der Verzug ``zuweisung_verzug`` (Minuten): verschickt wird
    erst, wenn seit der ZULETZT angelegten offenen Zuweisung dieser Person
    so lange nichts Neues mehr kam (Ruhephase). So schliesst sich das
    Sammelfenster von selbst, sobald der Schwung Aufgaben durch ist.

    ⚠️ Welche Aufgaben noch nicht gemeldet sind, steht an ``vorgang``
    selbst (``zuweis_gemeldet``), nicht in ``benachrichtigung``: nur so
    laesst sich in einem Rutsch abfragen, was fuer eine Person aussteht.
    Der Vermerk wird erst nach erfolgreichem Versand gesetzt - schlaegt
    der SMTP-Versand fehl, bleibt die Aufgabe offen und wird beim
    naechsten Durchlauf erneut versucht.
    """
    if k.get("zuweisung_aktiv") != "1":
        return []
    try:
        verzug = max(0, min(1440, int(k.get("zuweisung_verzug") or 0)))
    except ValueError:
        verzug = 0
    grenze = (dt.datetime.now() - dt.timedelta(minutes=verzug)).strftime(
        "%Y-%m-%d %H:%M")

    zeilen = con.execute(
        "SELECT id, klient, titel, art, prioritaet, frist, zustaendig, "
        "angelegt_am FROM vorgang WHERE zuweis_gemeldet = 0 "
        "AND TRIM(zustaendig) <> '' "
        "ORDER BY zustaendig COLLATE NOCASE, angelegt_am").fetchall()

    # ⚠️ Seit 1.30 koennen mehrere Personen zustaendig sein - die Spalte
    # traegt dann eine kommagetrennte Liste. Jede von ihnen bekommt ihre
    # eigene Sammelmail, sonst ginge die Nachricht an einen Namen, den es
    # gar nicht gibt („Anna, Bruno").
    nach_person: dict[str, list] = {}
    for z in zeilen:
        for name in empfaengerliste(z["zustaendig"]):
            nach_person.setdefault(name, []).append(z)

    protokoll = []
    # ⚠️ Eine Aufgabe gilt erst als gemeldet, wenn jede zustaendige Person
    # dran war. Sonst blieben bei zwei Zustaendigen die Aufgaben nach der
    # ersten Mail als erledigt vermerkt und die zweite Person bekaeme nie
    # etwas. Deshalb wird hier gezaehlt und erst ganz am Ende geschrieben.
    offen_je_id: dict[int, int] = {}
    for aufgaben in nach_person.values():
        for a in aufgaben:
            offen_je_id[a["id"]] = offen_je_id.get(a["id"], 0) + 1
    fertig_je_id: dict[int, int] = {}

    def abhaken(ids):
        for i in ids:
            fertig_je_id[i] = fertig_je_id.get(i, 0) + 1

    for name, aufgaben in nach_person.items():
        # Ruhephase noch nicht vorbei? Dann weiter sammeln.
        neueste = max(a["angelegt_am"] for a in aufgaben)
        if neueste > grenze:
            continue
        ids = [a["id"] for a in aufgaben]
        adresse = adresse_fuer(con, name)
        if not adresse:
            # Kein Login mit E-Mail: nicht ewig wiederholen, sonst bliebe
            # die Aufgabe fuer immer "offen" und blockierte kuenftige
            # Sammelmails dieser Person.
            abhaken(ids)
            protokoll.append(
                f"Zuweisung: kein Login mit E-Mail für „{name}“ "
                f"({len(ids)} Aufgabe(n))")
            continue

        eintraege = []
        for a in aufgaben:
            teil = f"  • {a['titel']} (Art: {a['art']}, Person: {a['klient']}"
            if a["prioritaet"] and a["prioritaet"] != "Mittel":
                teil += f", Priorität: {a['prioritaet']}"
            if a["frist"]:
                teil += f", Frist: {_datum(a['frist'])}"
            teil += ")"
            eintraege.append(teil)
        mehrere = len(aufgaben) != 1
        werte = {
            "name": name, "anzahl": len(aufgaben),
            "liste": "\n".join(eintraege),
            "mehrzahl": "n" if mehrere else "",
            "wurde": "wurden" if mehrere else "wurde",
        }
        erfolg, meldung = senden(
            adresse, fuellen(k["vorlage_zuweisung_betreff"], werte),
            fuellen(k["vorlage_zuweisung_text"], werte), k)
        if erfolg:
            abhaken(ids)
        protokoll.append(
            f"Zuweisung ({len(ids)}) an {adresse}: "
            f"{'ok' if erfolg else meldung}")

    durch = [i for i, n in offen_je_id.items() if fertig_je_id.get(i, 0) >= n]
    if durch:
        con.execute("UPDATE vorgang SET zuweis_gemeldet = 1 WHERE id IN (%s)"
                    % ",".join("?" * len(durch)), durch)
    return protokoll


def pruefe_erledigte(con, k: dict) -> list[str]:
    """Abgeschlossene Aufgaben -> Mail an die Person, die sie angelegt hat.

    ⚠️ Der Empfaenger ist ``vorgang.angelegt_von`` und damit die Angabe
    aus der Anmeldung, nicht aus einem Formular - dieselbe Regel wie beim
    Loeschen (Abschnitt 12). Wer eine Aufgabe verteilt, will wissen, wann
    sie fertig ist; alle anderen nicht.

    ⚠️ Meldet sich nicht selbst: hat dieselbe Person die Aufgabe angelegt
    UND abgeschlossen, geht keine Mail heraus. Eine Nachricht ueber die
    eigene Handlung ist nur Laerm.

    Der Vermerk ``erledigt_gemeldet`` funktioniert wie ``zuweis_gemeldet``
    und aus demselben Grund: er wird erst nach erfolgreichem Versand
    gesetzt, ein SMTP-Fehler laesst die Aufgabe also offen.
    """
    if k.get("erledigt_aktiv") != "1":
        return []

    platz = ",".join("?" * len(ABGESCHLOSSEN))
    zeilen = con.execute(
        f"SELECT id, klient, titel, art, status, zustaendig, angelegt_von, "
        f"datum_erledigt, geaendert_am FROM vorgang "
        f"WHERE erledigt_gemeldet = 0 AND status IN ({platz}) "
        f"AND TRIM(angelegt_von) <> '' ORDER BY id", list(ABGESCHLOSSEN)).fetchall()

    protokoll, fertig = [], []
    for v in zeilen:
        ersteller = (v["angelegt_von"] or "").strip()
        # Wer selbst abgeschlossen hat, braucht keine Nachricht darüber.
        # Wer das war, steht in der jüngsten Logzeile zu diesem Vorgang.
        letzte = con.execute(
            "SELECT wer FROM vorgang_log WHERE vorgang_id=? "
            "ORDER BY zeitpunkt DESC, id DESC LIMIT 1", (v["id"],)).fetchone()
        wer = (letzte["wer"] if letzte else "") or "jemand"
        if wer.strip().casefold() == ersteller.casefold():
            fertig.append(v["id"])
            protokoll.append(f"Erledigt {v['id']}: selbst abgeschlossen, "
                             "keine Nachricht")
            continue

        adresse = adresse_fuer(con, ersteller)
        if not adresse:
            fertig.append(v["id"])
            protokoll.append(
                f"Erledigt {v['id']}: kein Login mit E-Mail für „{ersteller}“")
            continue

        werte = {
            "name": ersteller, "titel": v["titel"], "klient": v["klient"],
            "art": v["art"], "status": v["status"],
            "zustaendig": v["zustaendig"] or "niemand",
            "wer": wer,
            "erledigt_am": _datum(v["datum_erledigt"]) or (
                (v["geaendert_am"] or "")[:10] and
                _datum((v["geaendert_am"] or "")[:10])) or "heute",
        }
        erfolg, meldung = senden(
            adresse, fuellen(k["vorlage_erledigt_betreff"], werte),
            fuellen(k["vorlage_erledigt_text"], werte), k)
        if erfolg:
            fertig.append(v["id"])
        protokoll.append(f"Erledigt {v['id']} an {adresse}: "
                         f"{'ok' if erfolg else meldung}")

    if fertig:
        con.execute("UPDATE vorgang SET erledigt_gemeldet = 1 WHERE id IN (%s)"
                    % ",".join("?" * len(fertig)), fertig)
    return protokoll


def empfaengerliste(wert: str | None) -> list[str]:
    """Aus dem gespeicherten Feld eine Namensliste machen.

    Gespeichert wird kommagetrennt, wie ueberall sonst im Programm auch
    (``berechtigungen``, ``einst_bereiche``). Eine eigene Tabelle waere
    fuer eine Handvoll Namen zu viel Aufwand, und die Namen stehen als
    Klartext ohnehin schon so in ``vorgang.zustaendig``.
    """
    return [t.strip() for t in (wert or "").split(",") if t.strip()]


def _datum(iso: str | None) -> str:
    try:
        return dt.date.fromisoformat(iso or "").strftime("%d.%m.%Y")
    except ValueError:
        return iso or ""


def durchlauf(nur_fristen: bool = False, nur_abgaben: bool = False,
              nur_bewilligungen: bool = False,
              nur_zuweisungen: bool = False,
              nur_erledigte: bool = False) -> list[str]:
    """Ein kompletter Durchlauf aller Pruefungen.

    ⚠️ Die Zuweisungsmail wird bewusst NICHT im stuendlichen Wecker
    mitgeprueft, sondern in einer eigenen, schnelleren Schleife
    (main.zuweisungs_schleife): ihr Verzug misst in Minuten, ein
    Stundentakt waere dafuer zu grob. ``nur_zuweisungen`` ist der Haken
    fuer diese Schleife.
    """
    k = konfig_lesen()
    if k.get("mail_aktiv") != "1":
        return ["E-Mail-Versand ist ausgeschaltet"]
    einzeln = (nur_fristen or nur_abgaben or nur_bewilligungen
               or nur_zuweisungen or nur_erledigte)
    protokoll = []
    with db.db() as con:
        # ⚠️ Zuweisungen laufen NUR ausdruecklich (nur_zuweisungen), nicht
        # im vollen Lauf. Sonst pruefte sie sowohl die schnelle
        # Zuweisungs-Schleife als auch der stuendliche Wecker - und wenn
        # beide zufaellig gleichzeitig liefen, koennte dieselbe Aufgabe
        # zweimal gemeldet werden (beide lesen zuweis_gemeldet=0, beide
        # senden). Die schnelle Schleife ist die eine zustaendige Stelle.
        if nur_zuweisungen:
            protokoll += pruefe_zuweisungen(con, k)
        # ⚠️ Dieselbe Ueberlegung wie bei den Zuweisungen: die Erledigt-
        # Meldung soll unmittelbar kommen, nicht erst zur naechsten vollen
        # Stunde. Sie laeuft deshalb in derselben schnellen Schleife und
        # ausdruecklich NICHT im vollen Lauf - sonst pruefen zwei Stellen
        # denselben Anlass und koennten ihn doppelt melden.
        if nur_zuweisungen or nur_erledigte:
            protokoll += pruefe_erledigte(con, k)
        if nur_fristen or not einzeln:
            protokoll += pruefe_fristen(con, k)
        if nur_abgaben or not einzeln:
            protokoll += pruefe_abgaben(con, k)
        if nur_bewilligungen or not einzeln:
            protokoll += pruefe_bewilligungen(con, k)
        protokoll_kuerzen(con)
    return protokoll or ["nichts zu tun"]


# Wie viele verschickte Nachrichten bleiben im Protokoll stehen. Die
# Einstellungsseite zeigt ohnehin nur diese Zahl - laenger aufzuheben
# hilft niemandem.
PROTOKOLL_LAENGE = 15


def protokoll_kuerzen(con, behalten: int = PROTOKOLL_LAENGE) -> int:
    """Raeumt die Tabelle ``benachrichtigung`` auf und gibt zurueck, wie
    viele Zeilen weggefallen sind.

    ⚠️⚠️ Diese Tabelle ist zweierlei zugleich: Protokoll UND Sperre gegen
    Doppelversand (siehe schon_gesendet). Einfach „alles ausser den 15
    juengsten loeschen" waere deshalb ein Fehler mit Folgen - faellt der
    Vermerk einer Erinnerung heraus, die noch aussteht, verschickt der
    naechste Weckerlauf sie ein zweites Mal.

    Geloescht wird darum nur, was BEIDES nicht mehr ist: nicht unter den
    juengsten und auch nicht mehr als Sperre gebraucht. Gebraucht wird ein
    Vermerk noch, solange sein Bezug ueberhaupt wieder entstehen kann:

    * ``frist``  – die Aufgabe gibt es noch, sie ist offen, und ihre Frist
      steht unveraendert. Eine verschobene Frist ergibt einen neuen Bezug,
      der alte kann also niemandem mehr im Weg stehen.
    * ``abgabe`` – nur der abgelaufene Monat wird je geprueft, alles
      Aeltere ist erledigt.
    * ``bewilligung`` – gedeckelt auf eine Mail je Kalenderwoche, also
      zaehlt nur die laufende.
    """
    heute = dt.date.today()
    # Der Monat, den pruefe_abgaben() betrachtet: der abgelaufene.
    erster = heute.replace(day=1)
    vormonat = (erster - dt.timedelta(days=1)).strftime("%Y-%m")
    jahr, woche, _ = heute.isocalendar()

    lebendig = set()
    for v in con.execute(
            "SELECT id, frist FROM vorgang "
            "WHERE frist IS NOT NULL AND frist <> '' "
            "AND status NOT IN ('Erledigt')"):
        lebendig.add(f"vorgang:{v['id']}:{v['frist']}")
        lebendig.add(f"vorgang:{v['id']}:{v['frist']}:vor")

    weg = []
    zeilen = con.execute(
        "SELECT id, art, bezug FROM benachrichtigung "
        "ORDER BY gesendet_am DESC, id DESC").fetchall()
    for z in zeilen[behalten:]:
        art, bezug = z["art"], z["bezug"] or ""
        if art == "frist" and bezug in lebendig:
            continue
        if art == "abgabe" and bezug >= f"abgabe:{vormonat}":
            continue
        if art == "bewilligung" and bezug.startswith(
                f"bewilligung:{jahr}-KW{woche:02d}:"):
            continue
        weg.append(z["id"])
    if weg:
        con.executemany("DELETE FROM benachrichtigung WHERE id=?",
                        [(i,) for i in weg])
    return len(weg)
