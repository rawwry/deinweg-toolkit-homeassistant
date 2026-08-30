"""E-Mail-Benachrichtigungen: Zugangsdaten, Vorlagen und der Wecker.

Zwei Anlaesse:
1. Ein Verwaltungsvorgang wird ueberfaellig -> Mail an die zustaendige Person.
2. Monatsanfang -> Mail an alle abgabepflichtigen Mitarbeitenden, die fuer
   den abgelaufenen Monat noch keine Zeiten eingereicht haben.

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
import smtplib
import ssl
from email.message import EmailMessage

from . import db

# --- Standardwerte -----------------------------------------------------------

STANDARD = {
    "smtp_absender": "notifications@dein-weg-st.de",
    "smtp_absendername": "Dein Weg Toolkit",
    "smtp_server": "w01cf78c.kasserver.com",
    "smtp_port": "465",
    "smtp_benutzer": "m08149da",
    "smtp_passwort": "",
    "smtp_sicherheit": "ssl",
    "mail_aktiv": "0",
    "vorlage_frist_betreff": "Überfällig: {titel} ({klient})",
    "vorlage_frist_text": (
        "Hallo {name},\n\n"
        "der folgende Vorgang ist seit dem {frist} überfällig:\n\n"
        "  Betreute Person: {klient}\n"
        "  Vorgang:         {titel}\n"
        "  Vorgangsart:     {art}\n"
        "  Status:          {status}\n"
        "  Frist:           {frist} (seit {tage} Tagen überschritten)\n\n"
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
    nachricht.set_content(text)

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

ABGESCHLOSSEN = ("Erledigt", "Abgebrochen")


def pruefe_fristen(con, k: dict) -> list[str]:
    """Ueberfaellige Vorgaenge -> Mail an die zustaendige Person."""
    protokoll = []
    heute = dt.date.today()
    platzhalter = ",".join("?" * len(ABGESCHLOSSEN))
    zeilen = con.execute(
        f"SELECT * FROM vorgang WHERE frist IS NOT NULL AND TRIM(frist) <> '' "
        f"AND frist < ? AND status NOT IN ({platzhalter})",
        [heute.isoformat(), *ABGESCHLOSSEN]).fetchall()

    for v in zeilen:
        # Bezug enthaelt die Frist: wird sie verschoben, darf erneut erinnert
        # werden, ohne dass die alte Mail das blockiert.
        bezug = f"vorgang:{v['id']}:{v['frist']}"
        adresse = adresse_fuer(con, v["zustaendig"])
        if not adresse:
            protokoll.append(
                f"Vorgang {v['id']}: kein Login mit E-Mail für „{v['zustaendig']}“")
            continue
        if schon_gesendet(con, "frist", bezug, adresse):
            continue
        try:
            tage = (heute - dt.date.fromisoformat(v["frist"])).days
        except ValueError:
            tage = 0
        werte = {
            "name": v["zustaendig"], "klient": v["klient"], "titel": v["titel"],
            "art": v["art"], "status": v["status"], "tage": tage,
            "frist": dt.date.fromisoformat(v["frist"]).strftime("%d.%m.%Y")
                     if v["frist"] else "",
            "beschreibung": v["beschreibung"] or "",
        }
        erfolg, meldung = senden(
            adresse, fuellen(k["vorlage_frist_betreff"], werte),
            fuellen(k["vorlage_frist_text"], werte), k)
        vermerken(con, "frist", bezug, adresse, erfolg, meldung)
        protokoll.append(
            f"Vorgang {v['id']} an {adresse}: {'ok' if erfolg else meldung}")
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
    """Wer hat fuer den abgelaufenen Monat nichts eingereicht?"""
    protokoll = []
    if monat is None:
        heute = dt.date.today()
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
              nur_bewilligungen: bool = False) -> list[str]:
    """Ein kompletter Durchlauf aller Pruefungen."""
    k = konfig_lesen()
    if k.get("mail_aktiv") != "1":
        return ["E-Mail-Versand ist ausgeschaltet"]
    einzeln = nur_fristen or nur_abgaben or nur_bewilligungen
    protokoll = []
    with db.db() as con:
        if nur_fristen or not einzeln:
            protokoll += pruefe_fristen(con, k)
        if nur_abgaben or not einzeln:
            protokoll += pruefe_abgaben(con, k)
        if nur_bewilligungen or not einzeln:
            protokoll += pruefe_bewilligungen(con, k)
    return protokoll or ["nichts zu tun"]
