"""Passwort vergessen: ein neues Passwort ueber einen Link per E-Mail.

Seit 1.49. Der Ablauf ist der uebliche, und jede seiner Eigenheiten hat
einen Grund:

1. Auf dem Anmeldebildschirm steht „Passwort vergessen?". Dort gibt man
   Benutzernamen ODER E-Mail-Adresse ein.
2. Die Antwort ist IMMER dieselbe - egal, ob es das Konto gibt, ob es eine
   Adresse hat oder ob die Bremse gegriffen hat. Sonst liesse sich mit dem
   Formular abfragen, welche Namen und Adressen es im Haus gibt.
3. Gehoert die Angabe zu einem aktiven Konto mit E-Mail-Adresse, geht an
   GENAU DIESE Adresse ein Link. Er traegt 32 Zufallsbytes, gilt 30
   Minuten und nur einmal. In der Datenbank steht nur sein SHA-256 - wer
   die Datenbank oder eine Sicherung liest, kann damit nichts anfangen.
4. Ueber den Link legt man ein neues Passwort fest. Danach sind ALLE
   Sitzungen des Kontos beendet und alle offenen Links verbraucht, und an
   dieselbe Adresse geht eine Bestaetigung - so faellt ein fremder Zugriff
   der Inhaberin auf.

⚠️⚠️ Die Adresse im Link kommt aus den Einstellungen (``app_adresse``),
NIE aus der Anfrage. Der Host-Kopf ist frei waehlbar: wer ihn faelscht und
fuer ein fremdes Konto einen Link anfordert, bekaeme sonst eine echte Mail
mit einem echten Schluessel verschickt, die auf SEINEN Server zeigt - ein
Klick der Inhaberin, und der Schluessel liegt bei ihm. Ohne eingetragene
Adresse bleibt die Funktion deshalb aus. Nicht auf die Adresse der
Anfrage umbauen.

⚠️ Nachschlagen und Versand laufen als Hintergrundaufgabe NACH der
Antwort. Ein SMTP-Versand dauert Sekunden; liefe er vorher, verriete
schon die Antwortzeit, ob es das Konto gibt.

Das Modul folgt dem Muster aus Abschnitt 3: eigener Router, ``setup()``,
kein Import von ``main.py``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth
from . import db
from . import mail

router = APIRouter()
_umgebung: dict = {}

GUELTIG_MINUTEN = 30
MINDESTLAENGE = 8

# Bremse, bewusst im Arbeitsspeicher wie die Anmeldebremse in auth.py:
# je Angabe drei Anfragen in 15 Minuten, je Rechner zehn in der Stunde.
# Die erste verhindert, dass jemand einer Kollegin das Postfach
# vollschreibt, die zweite das Abklappern vieler Namen.
_ANFRAGEN_ANGABE: dict[str, list] = {}
_ANFRAGEN_RECHNER: dict[str, list] = {}
_MAX_JE_ANGABE, _FENSTER_ANGABE = 3, 15
_MAX_JE_RECHNER, _FENSTER_RECHNER = 10, 60


def setup(templates) -> None:
    _umgebung["templates"] = templates
    templates.env.globals["passwortlink_bereit"] = lambda: bereit(mail.konfig_lesen())
    # ⚠️ uvicorn schreibt jede Adresse samt Abfrageteil ins Protokoll -
    # also auch den Schluessel aus dem Link. Das Protokoll des Add-ons
    # liest jede Administratorin in Home Assistant mit. Der Filter
    # schwaerzt ihn, bevor die Zeile geschrieben wird.
    logging.getLogger("uvicorn.access").addFilter(_Schwaerzen())


class _Schwaerzen(logging.Filter):
    _MUSTER = re.compile(r"([?&]token=)[^&\s\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                self._MUSTER.sub(r"\1…", a) if isinstance(a, str) else a
                for a in record.args)
        return True


# --- Hilfen ------------------------------------------------------------------

def _jetzt() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


def _zeit(z: dt.datetime) -> str:
    return z.strftime("%Y-%m-%d %H:%M:%S")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def adresse_pruefen(wert: str) -> str | None:
    """Die Adresse der Anwendung, wie sie im Link steht - oder None.

    Nur http und https, ohne Abfrage und Anker, ohne Schraegstrich am
    Ende. Aus einem Formular kommt sie trotzdem nur von einer
    Administratorin (Route in ADMIN_NUR_PFADE).
    """
    wert = (wert or "").strip().rstrip("/")
    if not re.fullmatch(r"https?://[^\s/?#]+(/[^\s?#]*)?", wert, re.I):
        return None
    return wert


def bereit(k: dict) -> bool:
    """Ist „Passwort vergessen?" eingeschaltet UND benutzbar?

    Bewusst unabhaengig von ``mail_aktiv``: der Schalter meint die
    automatischen Erinnerungen, nicht eine Mail, die jemand selbst
    anfordert. Ohne Server, Absender oder eigene Adresse ginge aber kein
    brauchbarer Link heraus - dann steht der Verweis gar nicht erst da.
    """
    return (k.get("passwortlink_aktiv") == "1"
            and bool((k.get("smtp_server") or "").strip())
            and bool((k.get("smtp_absender") or "").strip())
            and adresse_pruefen(k.get("app_adresse", "")) is not None)


def _gebremst(speicher: dict, schluessel: str, maximum: int,
              minuten: int) -> bool:
    grenze = dt.datetime.now() - dt.timedelta(minutes=minuten)
    liste = [z for z in speicher.get(schluessel, []) if z > grenze]
    liste.append(dt.datetime.now())
    speicher[schluessel] = liste
    return len(liste) > maximum


def aufraeumen(con) -> None:
    """Abgelaufene Links fallen weg - sie koennen nichts mehr."""
    con.execute("DELETE FROM passwort_link WHERE gueltig_bis < ?",
                (_zeit(_jetzt()),))


def links_verwerfen(con, benutzer_id: int) -> None:
    """Alle offenen Links eines Kontos ungueltig machen.

    Aufgerufen, sobald sich das Passwort oder die E-Mail-Adresse auf
    einem anderen Weg aendert - ein Link, der vorher angefordert wurde,
    darf danach nichts mehr ueberschreiben.
    """
    con.execute("DELETE FROM passwort_link WHERE benutzer_id=?", (benutzer_id,))


def link_pruefen(con, token: str):
    """Die Kontozeile zu einem gueltigen Link, sonst None."""
    if not token or len(token) > 200:
        return None
    aufraeumen(con)
    return con.execute(
        "SELECT b.id, b.benutzername, b.email FROM passwort_link l "
        "JOIN benutzer b ON b.id = l.benutzer_id "
        "WHERE l.token_hash=? AND l.gueltig_bis >= ? AND b.aktiv=1",
        (_hash(token), _zeit(_jetzt()))).fetchone()


def _seite(request: Request, modus: str, **werte):
    werte.update(modus=modus, weiter="/", fehler=werte.get("fehler", ""))
    antwort = _umgebung["templates"].TemplateResponse(
        request=request, name="login.html", context=werte)
    # Der Schluessel steht in der Adresse dieser Seite. Kein Verweis und
    # kein Zwischenspeicher soll ihn weitertragen.
    antwort.headers["Referrer-Policy"] = "no-referrer"
    antwort.headers["Cache-Control"] = "no-store"
    return antwort


# --- Versand (Hintergrund) ----------------------------------------------------

def _anfrage_bearbeiten(angabe: str) -> None:
    """Sucht das Konto und verschickt den Link. Laeuft NACH der Antwort."""
    k = mail.konfig_lesen()
    if not bereit(k):
        return
    adresse = adresse_pruefen(k.get("app_adresse", ""))
    klein = angabe.lower()
    with db.db() as con:
        aufraeumen(con)
        konto = con.execute(
            "SELECT id, benutzername, email FROM benutzer WHERE aktiv=1 "
            "AND email IS NOT NULL AND TRIM(email) <> '' "
            "AND (LOWER(benutzername)=? OR LOWER(TRIM(email))=?)",
            (klein, klein)).fetchall()
        # Passt eine Adresse auf mehrere Konten, ist nicht klar, welches
        # gemeint ist - dann lieber keins als das falsche.
        if len(konto) != 1:
            return
        konto = konto[0]
        # Ein Link je Minute reicht. Wer zweimal klickt, bekommt nicht
        # zwei Mails, von denen die erste gleich wieder ungueltig ist.
        juengst = con.execute(
            "SELECT MAX(erstellt_am) AS z FROM passwort_link WHERE benutzer_id=?",
            (konto["id"],)).fetchone()["z"]
        if juengst and juengst > _zeit(_jetzt() - dt.timedelta(minutes=1)):
            return
        token = secrets.token_urlsafe(32)
        links_verwerfen(con, konto["id"])
        con.execute(
            "INSERT INTO passwort_link (token_hash, benutzer_id, erstellt_am, "
            "gueltig_bis) VALUES (?,?,?,?)",
            (_hash(token), konto["id"], _zeit(_jetzt()),
             _zeit(_jetzt() + dt.timedelta(minutes=GUELTIG_MINUTEN))))

    link = f"{adresse}/passwort-neu?" + urlencode({"token": token})
    text = (
        f"Hallo {konto['benutzername']},\n\n"
        "für dein Konto im Dein Weg Toolkit wurde ein neues Passwort "
        "angefordert. Über diesen Link legst du eines fest:\n\n"
        f"{link}\n\n"
        f"Der Link gilt {GUELTIG_MINUTEN} Minuten und lässt sich nur einmal "
        "benutzen.\n\n"
        "Wenn du das nicht angefordert hast, musst du nichts tun – dein "
        "bisheriges Passwort bleibt gültig. Kommt so eine Nachricht öfter, "
        "sag bitte der Verwaltung Bescheid.\n\n"
        "Diese Nachricht wurde automatisch erstellt.")
    erfolg, meldung = mail.senden(konto["email"].strip(),
                                  "Neues Passwort festlegen", text, k)
    with db.db() as con:
        # ⚠️ Der Link steht NICHT im Protokoll - nur, dass einer
        # verschickt wurde.
        mail.vermerken(con, "passwort", f"link:{konto['id']}:{_zeit(_jetzt())}",
                       konto["email"].strip(), erfolg,
                       meldung if not erfolg else "Link verschickt")


def _bestaetigung(benutzername: str, email: str) -> None:
    k = mail.konfig_lesen()
    text = (
        f"Hallo {benutzername},\n\n"
        "das Passwort deines Kontos im Dein Weg Toolkit wurde soeben über "
        "„Passwort vergessen“ neu festgelegt. Alle bisherigen Anmeldungen "
        "sind damit beendet.\n\n"
        "Warst du das nicht, sag bitte sofort der Verwaltung Bescheid.\n\n"
        "Diese Nachricht wurde automatisch erstellt.")
    erfolg, meldung = mail.senden(email, "Dein Passwort wurde geändert", text, k)
    with db.db() as con:
        mail.vermerken(con, "passwort", f"geaendert:{benutzername}:{_zeit(_jetzt())}",
                       email, erfolg, meldung if not erfolg else "Bestätigung")


# --- Routen ------------------------------------------------------------------

@router.get("/passwort-vergessen", response_class=HTMLResponse)
def vergessen_formular(request: Request, gesendet: str = ""):
    return _seite(request, "vergessen", bereit=bereit(mail.konfig_lesen()),
                  gesendet=gesendet == "1")


@router.post("/passwort-vergessen")
def vergessen_absenden(request: Request, hintergrund: BackgroundTasks,
                       angabe: str = Form("")):
    angabe = angabe.strip()[:200]
    rechner = request.client.host if request.client else "?"
    # ⚠️ Beide Bremsen zaehlen, bevor irgendetwas nachgeschlagen wird, und
    # ihr Greifen aendert die Antwort nicht.
    zu_viel = _gebremst(_ANFRAGEN_RECHNER, rechner, _MAX_JE_RECHNER,
                        _FENSTER_RECHNER)
    if angabe:
        zu_viel = _gebremst(_ANFRAGEN_ANGABE, angabe.lower(), _MAX_JE_ANGABE,
                            _FENSTER_ANGABE) or zu_viel
    if angabe and not zu_viel:
        hintergrund.add_task(_anfrage_bearbeiten, angabe)
    return RedirectResponse("/passwort-vergessen?gesendet=1", status_code=303)


@router.get("/passwort-neu", response_class=HTMLResponse)
def neu_formular(request: Request, token: str = ""):
    with db.db() as con:
        konto = link_pruefen(con, token)
    if konto is None:
        return _seite(request, "ungueltig")
    return _seite(request, "neu", token=token, name=konto["benutzername"])


@router.post("/passwort-neu", response_class=HTMLResponse)
def neu_speichern(request: Request, hintergrund: BackgroundTasks,
                  token: str = Form(""), passwort: str = Form(""),
                  passwort2: str = Form("")):
    with db.db() as con:
        konto = link_pruefen(con, token)
        if konto is None:
            return _seite(request, "ungueltig")
        # ⚠️ Bei einem Fehler wird die Seite direkt neu gezeigt, NICHT
        # auf die Adresse mit dem Schluessel umgeleitet - die landete
        # sonst ein zweites Mal im Protokoll und im Verlauf.
        fehler = ""
        if len(passwort) < MINDESTLAENGE:
            fehler = f"Das Passwort braucht mindestens {MINDESTLAENGE} Zeichen."
        elif passwort != passwort2:
            fehler = "Die beiden Passwörter sind nicht gleich."
        if fehler:
            return _seite(request, "neu", token=token,
                          name=konto["benutzername"], fehler=fehler)

        con.execute("UPDATE benutzer SET passwort_hash=? WHERE id=?",
                    (db.passwort_hashen(passwort), konto["id"]))
        links_verwerfen(con, konto["id"])
        # Wer ein vergessenes Passwort ersetzt, will jede andere Anmeldung
        # los sein - genau die koennte die fremde sein.
        con.execute("DELETE FROM sitzung WHERE benutzer_id=?", (konto["id"],))
    auth._zuruecksetzen(konto["benutzername"].lower())
    if (konto["email"] or "").strip():
        hintergrund.add_task(_bestaetigung, konto["benutzername"],
                             konto["email"].strip())
    return RedirectResponse("/login?geaendert=1", status_code=303)
