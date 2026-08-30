"""Anmeldung, Benutzerverwaltung und Zugriffskontrolle.

Grundgedanken:
* "Mitarbeiter" (Team fuer die Abgabeuebersicht) und "Benutzer" (Login-Konten)
  sind bewusst getrennte Tabellen. Ein Mitarbeiter braucht keinen Login, ein
  Login muss keinem Mitarbeiter entsprechen.
* Sitzungen stehen in der Datenbank (Tabelle "sitzung"), das Cookie traegt nur
  einen zufaelligen Token. Eine Zeile loeschen meldet sofort ab - z.B. wenn
  ein Konto deaktiviert wird oder der "Abmelden"-Knopf gedrueckt wird.
* Rollen: "admin" hat immer vollen Zugriff. "benutzer" hat vollen Zugriff,
  AUSSER die Spalte benutzer.berechtigungen enthaelt eine kommagetrennte
  Liste erlaubter Bereichs-Schluessel - dann nur auf die dort genannten.
  Leer/NULL bedeutet also "alles", nicht "nichts"; das haelt neue,
  noch unbekannte Bereiche automatisch zugaenglich fuer bereits bestehende
  Benutzer ohne Einschraenkung.
* Die eigentliche Durchsetzung passiert zentral in der Middleware anhand des
  URL-Pfads (siehe BEREICH_PFADE) - nicht verstreut in jeder einzelnen Route.
  Das ist der tatsaechliche Zugriffspunkt: ein direkter Aufruf der URL wird
  genauso geprueft wie ein Klick in der Navigation.
"""

from __future__ import annotations

import datetime as dt
import secrets
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from . import db

router = APIRouter()

COOKIE_NAME = "dwt_sitzung"

# Einfache Bremse gegen das Durchprobieren von Passwoertern. Bewusst nur im
# Arbeitsspeicher: nach einem Neustart ist die Sperre weg, das ist bei einem
# Werkzeug fuer ein Sechs-Personen-Team vertretbar und spart eine Tabelle.
_FEHLVERSUCHE: dict[str, list] = {}
_MAX_VERSUCHE = 8
_SPERRE_MINUTEN = 10


def _gesperrt(kennung: str) -> bool:
    versuche = _FEHLVERSUCHE.get(kennung, [])
    grenze = dt.datetime.now() - dt.timedelta(minutes=_SPERRE_MINUTEN)
    versuche = [z for z in versuche if z > grenze]
    _FEHLVERSUCHE[kennung] = versuche
    return len(versuche) >= _MAX_VERSUCHE


def _fehlversuch(kennung: str) -> None:
    _FEHLVERSUCHE.setdefault(kennung, []).append(dt.datetime.now())


def _zuruecksetzen(kennung: str) -> None:
    _FEHLVERSUCHE.pop(kennung, None)

_umgebung: dict = {}


def setup(templates, sitzung_tage: int) -> None:
    _umgebung["templates"] = templates
    _umgebung["sitzung_tage"] = sitzung_tage
    templates.env.globals["hat_zugriff"] = hat_zugriff
    templates.env.globals["hat_einst_zugriff"] = hat_einst_zugriff
    templates.env.globals["darf_wiki_schreiben"] = darf_wiki_schreiben
    templates.env.globals["darf_bewilligungen_sehen"] = darf_bewilligungen_sehen
    templates.env.globals["darf_fremde_loeschen"] = darf_fremde_loeschen
    templates.env.globals["darf_fremde_bearbeiten"] = darf_fremde_bearbeiten


# --- Bereiche ----------------------------------------------------------------
#
# Genau die Funktionsbereiche, die in der Anforderung genannt wurden. Die
# Reihenfolge bestimmt die Anzeige in der Checkbox-Liste der Benutzerverwaltung.

BEREICHE = {
    "listenimport": "Listenimport",
    "manuelle_eintraege": "Manuelle Einträge",
    "datensaetze": "Übersicht (Datensätze)",
    "auswertung": "Auswertung",
    "verwaltungsvorgaenge": "Aufgaben",
    "fuhrpark": "Fuhrpark",
    "wiki": "Wiki",
    "dateien": "Dateien",
    "ideen": "Ideen",
    "einstellungen": "Einstellungen",
}

# Was gespeichert wird, wenn NICHTS angehakt ist. Ein leerer String hiesse
# nach der Regel oben "alles" - genau verkehrt herum. Der Strich ist kein
# gueltiger Schluessel, passt also auf keinen Bereich und bedeutet damit
# "nichts". Ohne ihn haette ein Formular ohne einen einzigen Haken vollen
# Zugriff erteilt.
KEINE = "-"


# Pfadanfang -> Bereichs-Schluessel. Reihenfolge unwichtig, da Praefixe sich
# hier nicht ueberschneiden. "/" (Startseite) ist bewusst NICHT gelistet: sie
# zeigt die Abgabeuebersicht und dient als allgemeine Startseite nach dem
# Login und bleibt daher fuer jeden angemeldeten Benutzer erreichbar - nur
# die tatsaechlichen Aktionen (Hochladen, Vorschau, manuelles Erfassen)
# sind geschuetzt.
BEREICH_PFADE = [
    ("/vorgaenge", "verwaltungsvorgaenge"),
    ("/fuhrpark", "fuhrpark"),
    ("/wiki", "wiki"),
    ("/dateien", "dateien"),
    ("/eintraege", "datensaetze"),
    ("/export", "datensaetze"),
    ("/erfassung", "manuelle_eintraege"),
    ("/auswertung", "auswertung"),
    ("/einstellungen", "einstellungen"),
    ("/ideen", "ideen"),
    ("/upload", "listenimport"),
    ("/vorschau", "listenimport"),
    ("/import", "listenimport"),
]

# --- Punkte innerhalb der Einstellungen ---------------------------------------
#
# Eine zweite Ebene unter dem Bereich "einstellungen": wer die Einstellungen
# ueberhaupt sehen darf, muss deshalb noch lange nicht jeden Punkt darin
# sehen. Gespeichert in benutzer.einst_bereiche, nach derselben Regel wie
# berechtigungen - leer/NULL heisst "alle".
#
# "oberflaeche" steht bewusst NICHT in dieser Liste: Darkmode und
# Inhaltsbreite gehoeren jedem selbst und bleiben immer erreichbar. Sonst
# koennte man ein Konto in den Einstellungen landen lassen, in denen es
# nichts zu sehen gibt. Die drei Admin-Punkte (Benutzerverwaltung,
# E-Mail-Versand, E-Mail-Vorlagen) fehlen ebenfalls - sie haengen an der
# Rolle und nicht an dieser Liste.
EINST_IMMER = "oberflaeche"

EINST_BEREICHE = {
    "quotes": "Sprüche",
    "betreute": "Betreute Personen",
    "mitarbeiter": "Mitarbeiter",
    "kfz": "Fahrzeuge",
    "vorgangsarten": "Aufgabenarten",
    "leistungen": "Leistungsbeschreibungen",
    "system": "System und Sicherung",
}

# Pfadanfang -> Punkt in den Einstellungen. Deckt die POST-Routen ab, damit
# ein direkt abgeschicktes Formular genauso geprueft wird wie die Ansicht.
# Die Ansicht selbst ist nur ein Abfrageparameter auf /einstellungen und
# wird in einstellungen.py geprueft.
EINST_PFADE = [
    ("/einstellungen/spruch", "quotes"),
    ("/einstellungen/person", "betreute"),
    ("/einstellungen/mitarbeiter", "mitarbeiter"),
    ("/einstellungen/fahrzeug", "kfz"),
    ("/einstellungen/vorgangsart", "vorgangsarten"),
    ("/einstellungen/leistung", "leistungen"),
    ("/einstellungen/sicherung", "system"),
]


def einst_bereich_fuer_pfad(pfad: str) -> str | None:
    for praefix, punkt in EINST_PFADE:
        if pfad == praefix or pfad.startswith(praefix + "/"):
            return punkt
    return None


def hat_einst_zugriff(benutzer, punkt: str) -> bool:
    """True, wenn der Benutzer diesen Punkt in den Einstellungen sehen darf.

    Setzt den Bereich "einstellungen" voraus - ohne den kommt man gar nicht
    erst auf die Seite, das erledigt die Middleware eine Stufe hoeher.
    """
    if not benutzer:
        return False
    if punkt == EINST_IMMER:
        return True
    if benutzer["rolle"] == "admin":
        return True
    try:
        roh = (benutzer["einst_bereiche"] or "").strip()
    except (IndexError, KeyError, TypeError):
        # Sitzung von vor der Migration: der sichere Rueckfall ist hier
        # "alles", genau wie bei einem leeren Feld.
        return True
    if not roh:
        return True
    return punkt in {b.strip() for b in roh.split(",") if b.strip()}


def einst_bereiche_speichern(gewaehlt: list[str]) -> str:
    """Kommaliste der angeklickten Punkte - leer, wenn wirklich alle
    angeklickt sind (das steht dann fuer "alle", siehe oben).
    """
    gewaehlt = [b for b in gewaehlt if b in EINST_BEREICHE]
    if len(gewaehlt) >= len(EINST_BEREICHE):
        return ""
    return ",".join(gewaehlt) if gewaehlt else KEINE


# Innerhalb von /einstellungen zusaetzlich admin-pflichtig, unabhaengig von
# der allgemeinen "einstellungen"-Berechtigung - Benutzerverwaltung darf
# niemand ohne Administratorrolle sehen oder aufrufen, sonst koennte sich
# ein eingeschraenkter Benutzer selbst hochstufen.
ADMIN_NUR_PFADE = ("/einstellungen/benutzer",)

# Oeffentlich ohne Anmeldung erreichbar
OEFFENTLICHE_PFADE = ("/gesundheit", "/login")


def bereich_fuer_pfad(pfad: str) -> str | None:
    for praefix, bereich in BEREICH_PFADE:
        if pfad == praefix or pfad.startswith(praefix + "/"):
            return bereich
    return None


def hat_zugriff(benutzer, bereich: str) -> bool:
    """True, wenn der Benutzer den angegebenen Bereich nutzen darf.

    Nimmt bewusst auch None entgegen (z.B. wenn in einem Template aus
    Versehen ohne Anmeldung gerendert wuerde) und verweigert dann - sicherer
    Rueckfall statt eines Fehlers.
    """
    if not benutzer:
        return False
    if benutzer["rolle"] == "admin":
        return True
    roh = (benutzer["berechtigungen"] or "").strip()
    if not roh:
        return True
    erlaubt = {b.strip() for b in roh.split(",") if b.strip()}
    return bereich in erlaubt


# --- Einzelrechte -------------------------------------------------------------
#
# Neben den Bereichen (oben) gibt es zwei Rechte, die kein eigener Bereich
# sind, sondern eine Einschraenkung INNERHALB eines Bereichs. Sie stehen
# deshalb als eigene Spalten an "benutzer" und nicht in der Kommaliste:
# * fremde_loeschen   - Zeiteintraege anderer Leute loeschen
# * fremde_bearbeiten - Zeiteintraege anderer Leute aendern
# * wiki_schreiben    - Wiki-Seiten aendern statt nur lesen
#
# Beide Funktionen nehmen bewusst auch None entgegen und verweigern dann,
# und beide lesen die Spalte defensiv: eine Sitzung, die noch vor der
# Migration entstanden ist, traegt das Feld nicht mit.

def _schalter(benutzer, spalte: str, standard: bool) -> bool:
    if not benutzer:
        return False
    if benutzer["rolle"] == "admin":
        return True
    try:
        wert = benutzer[spalte]
    except (IndexError, KeyError, TypeError):
        return standard
    if wert is None:
        return standard
    return bool(wert)


def darf_fremde_loeschen(benutzer) -> bool:
    """Darf Zeiteintraege loeschen, die auf andere Mitarbeitende laufen.

    Die eigenen darf ohnehin jeder loeschen - das haengt nicht an diesem
    Recht, sondern wird beim Loeschen selbst geprueft.
    """
    return _schalter(benutzer, "fremde_loeschen", False)


def darf_fremde_bearbeiten(benutzer) -> bool:
    """Darf Zeiteintraege aendern, die auf andere Mitarbeitende laufen.

    Eigenstaendig neben darf_fremde_loeschen: das eine ist nicht das
    andere. Wer nur eine Schreibweise richtigstellen soll, braucht kein
    Loeschrecht; wer aufraeumen darf, muss nicht auch Inhalte umschreiben
    duerfen.
    """
    return _schalter(benutzer, "fremde_bearbeiten", False)


def darf_wiki_schreiben(benutzer) -> bool:
    """Darf Wiki-Seiten anlegen, aendern, verschieben und loeschen.

    Lesen deckt der Bereich "wiki" ab; dieses Recht sitzt eine Stufe
    darunter. Ohne es bleibt das Wiki vollstaendig lesbar.
    """
    return _schalter(benutzer, "wiki_schreiben", True)


def darf_bewilligungen_sehen(benutzer) -> bool:
    """Darf die Karte "Bewilligungen im Blick" in Mein Bereich sehen.

    Standard 1: das ist eine Erinnerung fuers ganze Team ("hier muss ein
    Folgeantrag raus"), keine heikle Auskunft. Wer sie nicht braucht,
    bekommt sie ausdruecklich abgeschaltet.
    """
    return _schalter(benutzer, "bewilligungen_sehen", True)


def berechtigungen_speichern(gewaehlt: list[str]) -> str:
    """Kommaliste aus den angeklickten Bereichen - oder leer, wenn wirklich
    alle angeklickt sind (das steht dann fuer "alles", siehe Moduldoku).
    """
    gewaehlt = [b for b in gewaehlt if b in BEREICHE]
    if len(gewaehlt) >= len(BEREICHE):
        return ""
    return ",".join(gewaehlt) if gewaehlt else KEINE


def jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# --- Sitzungen ---------------------------------------------------------------

def sitzung_anlegen(con, benutzer_id: int) -> str:
    token = secrets.token_urlsafe(32)
    con.execute(
        "INSERT INTO sitzung (token, benutzer_id, erstellt_am) VALUES (?,?,?)",
        (token, benutzer_id, jetzt()))
    return token


def sitzung_loeschen(con, token: str) -> None:
    con.execute("DELETE FROM sitzung WHERE token=?", (token,))


def sitzung_benutzer(con, token: str, sitzung_tage: int):
    """Liefert die Benutzerzeile zu einem Sitzungstoken, oder None - auch
    wenn der Token unbekannt, die Sitzung abgelaufen oder das Konto
    inzwischen deaktiviert wurde.
    """
    if not token:
        return None
    zeile = con.execute(
        "SELECT s.erstellt_am, b.id, b.benutzername, b.rolle, "
        "b.berechtigungen, b.email, b.mitarbeiter, b.aktiv, "
        "b.fremde_loeschen, b.fremde_bearbeiten, b.wiki_schreiben, "
        "b.bewilligungen_sehen, b.einst_bereiche "
        "FROM sitzung s JOIN benutzer b ON b.id = s.benutzer_id "
        "WHERE s.token = ?", (token,)).fetchone()
    if not zeile or not zeile["aktiv"]:
        return None
    try:
        alter = dt.datetime.now() - dt.datetime.strptime(zeile["erstellt_am"], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    if alter.days > sitzung_tage:
        sitzung_loeschen(con, token)
        return None
    return zeile


# --- Middleware ---------------------------------------------------------------

# --- Schutz gegen fremd abgeschickte Formulare (CSRF) -------------------------
#
# Eine fremde Seite kann ein Formular auf unseren Server abschicken; das
# Sitzungs-Cookie geht dabei mit. samesite=lax faengt den Standardfall ab,
# ist aber kein vollwertiger Ersatz - genau der offene Punkt aus
# Abschnitt 15.
#
# ⚠️ Geprueft wird die HERKUNFT der Anfrage, nicht ein Token im Formular.
# Beides ist gleich wirksam; der Unterschied ist der Aufwand. Ein Token
# muesste in jedes einzelne der rund fuenfzig Formulare, und wer eines
# vergisst, merkt es erst, wenn ein Benutzer davorsteht. Die Herkunft
# steht dagegen in jeder Anfrage und wird an einer Stelle geprueft.
#
# Sec-Fetch-Site setzt der Browser selbst; eine Webseite kann den Kopf
# nicht faelschen. Fehlt er (sehr alte Browser), greift der Rueckfall auf
# Origin bzw. Referer. Fehlt auch der, wird durchgelassen: ein Browser,
# der gar nichts davon schickt, schickt auch bei einem fremden Formular
# nichts - dann waere die Pruefung nur eine Sperre gegen den eigenen
# Benutzer.
SICHERE_METHODEN = ("GET", "HEAD", "OPTIONS", "TRACE")


def herkunft_stimmt(request: Request) -> bool:
    ziel = request.headers.get("sec-fetch-site")
    if ziel:
        # "none" = direkt eingegeben oder Lesezeichen, "same-origin" = wir.
        return ziel in ("same-origin", "none")

    herkunft = request.headers.get("origin") or request.headers.get("referer")
    if not herkunft:
        return True
    eigene = f"{request.url.scheme}://{request.url.netloc}"
    return herkunft == eigene or herkunft.startswith(eigene + "/")


class SessionAuth(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        pfad = request.url.path

        # Vor allem anderen: kommt das Formular von uns? Auch die Anmeldung
        # wird geprueft - sonst koennte eine fremde Seite jemanden
        # unbemerkt auf ein anderes Konto umschalten.
        if request.method not in SICHERE_METHODEN and not herkunft_stimmt(request):
            return Response(
                "Diese Anfrage kam nicht von dieser Seite und wurde deshalb "
                "abgewiesen. Bitte die Seite neu laden und noch einmal "
                "versuchen.", status_code=403)

        if pfad in OEFFENTLICHE_PFADE or pfad.startswith("/static/"):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME, "")
        with db.db() as con:
            benutzer = sitzung_benutzer(con, token, _umgebung["sitzung_tage"])

        if benutzer is None:
            frage = urlencode({"weiter": pfad + (f"?{request.url.query}" if request.url.query else "")})
            antwort = RedirectResponse(f"/login?{frage}", status_code=303)
            antwort.delete_cookie(COOKIE_NAME)
            return antwort

        ist_admin = benutzer["rolle"] == "admin"
        if pfad.startswith(ADMIN_NUR_PFADE) and not ist_admin:
            return Response(
                "Kein Zugriff. Diese Funktion ist Administratoren vorbehalten.",
                status_code=403)

        bereich = bereich_fuer_pfad(pfad)
        if bereich and not hat_zugriff(benutzer, bereich):
            return Response(
                f"Kein Zugriff auf diesen Bereich ({BEREICHE.get(bereich, bereich)}).",
                status_code=403)

        # Zweite Ebene innerhalb der Einstellungen. Greift erst, nachdem
        # der Bereich "einstellungen" oben durchgelassen hat.
        punkt = einst_bereich_fuer_pfad(pfad)
        if punkt and not hat_einst_zugriff(benutzer, punkt):
            return Response(
                "Kein Zugriff auf diesen Punkt in den Einstellungen "
                f"({EINST_BEREICHE.get(punkt, punkt)}).", status_code=403)

        # Schreibrecht im Wiki. Bewusst hier und nicht in wiki.py: es ist
        # dieselbe Stelle, an der auch die Bereiche durchgesetzt werden,
        # und damit greift es auch bei einem direkt abgeschickten Formular.
        # Geprueft wird ueber die Methode, nicht ueber den Pfad allein -
        # /wiki/aktion/suche und /wiki/aktion/herunterladen sind GET und
        # gehoeren zum Lesen.
        if (pfad.startswith("/wiki/aktion/") and request.method == "POST"
                and not darf_wiki_schreiben(benutzer)):
            return Response(
                "Kein Schreibrecht im Wiki. Du kannst alle Seiten lesen, "
                "aber nicht ändern.", status_code=403)

        request.state.benutzer = benutzer
        return await call_next(request)


# --- Login / Logout -----------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_formular(request: Request, weiter: str = "/", fehler: str = ""):
    token = request.cookies.get(COOKIE_NAME, "")
    if token:
        with db.db() as con:
            if sitzung_benutzer(con, token, _umgebung["sitzung_tage"]):
                return RedirectResponse(weiter or "/", status_code=303)
    return _umgebung["templates"].TemplateResponse(
        request=request, name="login.html",
        context={"weiter": weiter or "/", "fehler": fehler})


@router.post("/login")
def login_absenden(request: Request, benutzername: str = Form(""),
                   passwort: str = Form(""), weiter: str = Form("/")):
    benutzername = benutzername.strip()
    fehlgeschlagen = RedirectResponse(
        "/login?" + urlencode({"weiter": weiter or "/",
                               "fehler": "Benutzername oder Passwort ist falsch."}),
        status_code=303)
    if not benutzername or not passwort:
        return fehlgeschlagen

    kennung = benutzername.lower()
    if _gesperrt(kennung):
        return RedirectResponse(
            "/login?" + urlencode({
                "weiter": weiter or "/",
                "fehler": f"Zu viele Fehlversuche. Bitte {_SPERRE_MINUTEN} "
                          "Minuten warten."}),
            status_code=303)

    with db.db() as con:
        zeile = con.execute(
            "SELECT * FROM benutzer WHERE benutzername=? AND aktiv=1",
            (benutzername,)).fetchone()
        if not zeile or not db.passwort_pruefen(passwort, zeile["passwort_hash"]):
            _fehlversuch(kennung)
            return fehlgeschlagen
        _zuruecksetzen(kennung)
        token = sitzung_anlegen(con, zeile["id"])
        con.execute("UPDATE benutzer SET letzter_login=? WHERE id=?",
                    (jetzt(), zeile["id"]))

    ziel = weiter if weiter and weiter.startswith("/") else "/"
    antwort = RedirectResponse(ziel, status_code=303)
    antwort.set_cookie(COOKIE_NAME, token, max_age=_umgebung["sitzung_tage"] * 86400,
                       httponly=True, samesite="lax")
    return antwort


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(COOKIE_NAME, "")
    if token:
        with db.db() as con:
            sitzung_loeschen(con, token)
    antwort = RedirectResponse("/login", status_code=303)
    antwort.delete_cookie(COOKIE_NAME)
    return antwort
