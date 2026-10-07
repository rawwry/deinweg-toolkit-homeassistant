"""Navigation und Schnellsuche (seit 2.0).

Zwei Dinge, die auf JEDER Seite gebraucht werden und deshalb weder in ein
Seitenmodul noch nach main.py gehoeren:

- ``navigation(request)``: die Punkte des Hauptmenues samt Zaehler. Daraus
  bauen base.html die Kopfzeile am Schreibtisch, die Tableiste am Telefon
  und das Blatt „Mehr". ⚠️ Bis 1.61 standen die Bedingungen dreimal im
  Markup (Kopfzeile, Werkzeuge, Schublade) - drei Stellen, die
  auseinanderlaufen konnten. Jetzt gibt es die Liste genau einmal.
- ``GET /schnellsuche.json``: was die Schnellsuche (Strg+K) anbietet -
  Seiten, Handgriffe und die betreuten Personen. Erst beim Oeffnen
  geholt, nicht bei jedem Seitenaufbau.

⚠️⚠️ Beide lesen nur. Es gibt hier keine einzige schreibende Anfrage und
keine neue Spalte - die Datenbank wird nicht angefasst.

⚠️ Rechte: geprueft wird mit DENSELBEN Funktionen wie in der Middleware
(``auth.hat_zugriff``, ``auth.hat_einst_zugriff``). Die Liste blendet nur
aus, was ohnehin ein 403 waere - sie ist Komfort, nicht die Absicherung.

Importiert ``db``, ``auth``, ``rechnen``, ``vorgaenge`` und ``profilbild`` - keines davon
importiert dieses Modul zurueck, es gibt also keinen Ringschluss.
"""

from __future__ import annotations

import datetime as dt
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from . import auth, db, rechnen
from . import profilbild as _profilbild
from . import vorgaenge as _vorgaenge

router = APIRouter()
_umgebung: dict = {}


def setup(templates, umgebung=None) -> None:
    _umgebung["templates"] = templates
    _umgebung.update(umgebung or {})
    templates.env.globals["navigation"] = navigation
    templates.env.globals["tagesgruss"] = rechnen.tagesgruss


# --- Hauptmenue ---------------------------------------------------------------

# (Schluessel, Adresse, Name, Kurzname fuer die Tableiste, Symbol, Bereich,
#  Seiten, auf denen der Punkt als aktiv gilt). Bereich None = jeder.
# ⚠️ Die Reihenfolge ist Timos Reihenfolge aus 1.55: Privatauslagen an
# dritter Stelle, damit sie am Telefon im Daumenbereich liegen.
HAUPTPUNKTE = [
    ("arbeitszeit", "/", "Arbeitszeit", "Zeit", "uhr", None,
     ("zeiterfassung", "eintraege", "auswertung")),
    ("aufgaben", "/vorgaenge", "Aufgaben", "Aufgaben", "aufgaben",
     "verwaltungsvorgaenge", ("vorgaenge",)),
    ("auslagen", "/privatauslagen", "Privatauslagen", "Auslagen", "auslagen",
     "privatauslagen", ("privatauslagen",)),
    ("fuhrpark", "/fuhrpark", "Fuhrpark", "Fuhrpark", "fuhrpark",
     "fuhrpark", ("fuhrpark",)),
    ("dateien", "/dateien", "Dateien", "Dateien", "dateien",
     "dateien", ("dateien",)),
    ("wiki", "/wiki", "Wiki", "Wiki", "wiki", "wiki", ("wiki",)),
]

# Wie viele Punkte die Tableiste am Telefon direkt zeigt. Der fuenfte
# Platz gehoert immer „Mehr" - dort stehen der Rest, das Konto und die
# Darstellung. Fuenf Ziele sind das, was auf 375px mit lesbarer
# Beschriftung nebeneinander passt.
TABLEISTE = 4


def _faellige(con, benutzer) -> dict:
    """Eigene Aufgaben, die ueberfaellig oder heute faellig sind.

    Dieselbe Zahl wie „Was heute draengt" auf der Zeiterfassung - beide
    fragen vorgaenge.faellige_eigene().
    """
    zeile = rechnen.mitarbeiter_zu_benutzer(con, benutzer)
    try:
        eigener = (zeile["name"] or "").strip() if zeile is not None else ""
    except (IndexError, KeyError, TypeError):
        eigener = ""
    if not eigener:
        return {"ueber": 0, "heute": 0}
    return _vorgaenge.faellige_eigene(con, eigener, dt.date.today().isoformat())


def navigation(request: Request) -> dict:
    """Alle Menuepunkte des angemeldeten Kontos, einmal je Anfrage gerechnet.

    ⚠️ Zwischengespeichert an ``request.state``: base.html fragt die Liste
    an mehreren Stellen ab (Kopfzeile, Tableiste, Blatt), die Abfrage nach
    den faelligen Aufgaben soll trotzdem nur einmal laufen.
    """
    schon = getattr(request.state, "_navigation", None)
    if schon is not None:
        return schon
    benutzer = getattr(request.state, "benutzer", None)
    if benutzer is None:
        return {"haupt": [], "leiste": [], "mehr": [], "mehr_seiten": [],
                "konto": [], "name": "", "kuerzel": "", "rolle": "", "bild": ""}

    punkte = []
    for schl, adresse, name, kurz, sym, bereich, seiten in HAUPTPUNKTE:
        if bereich and not auth.hat_zugriff(benutzer, bereich):
            continue
        punkte.append({"schluessel": schl, "adresse": adresse, "name": name,
                       "kurz": kurz, "symbol": sym, "seiten": seiten,
                       "zahl": 0, "dringend": False})

    # Der Zaehler an „Aufgaben": nur die EIGENEN und nur, was heute
    # draengt. Eine Zahl, die jeden Tag dasteht, liest nach einer Woche
    # niemand mehr (dieselbe Regel wie bei „Was heute draengt").
    for p in punkte:
        if p["schluessel"] == "aufgaben":
            try:
                with db.db() as con:
                    f = _faellige(con, benutzer)
                p["zahl"] = f["ueber"] + f["heute"]
                p["dringend"] = f["ueber"] > 0
            except Exception:  # noqa: BLE001 - ein Zaehler darf keine Seite kosten
                pass

    # ⚠️ seiten=() bei den beiden Unterseiten: alle drei laufen unter
    # seite="meinbereich", markiert wird aber nur „Mein Bereich" selbst.
    konto = [{"adresse": "/meinbereich", "name": "Mein Bereich",
              "symbol": "konto", "seiten": ("meinbereich",)},
             {"adresse": "/meinbereich/konto", "name": "Mein Konto",
              "symbol": "profil", "seiten": ()}]
    if auth.hat_zugriff(benutzer, "manuelle_eintraege"):
        konto.append({"adresse": "/meinbereich/vorlagen", "name": "Meine Vorlagen",
                      "symbol": "vorlage", "seiten": ()})
    if auth.hat_zugriff(benutzer, "einstellungen"):
        konto.append({"adresse": "/einstellungen", "name": "Einstellungen",
                      "symbol": "einstellungen",
                      "seiten": ("einstellungen", "datenpflege")})
    if auth.hat_zugriff(benutzer, "ideen"):
        konto.append({"adresse": "/ideen", "name": "Ideen und Rückmeldungen",
                      "symbol": "ideen", "seiten": ("ideen",)})
    konto.append({"adresse": "/changelog", "name": "Was ist neu?",
                  "symbol": "neu", "seiten": ("changelog",)})

    # Am Telefon: die ersten vier Punkte in die Leiste, der Rest ins
    # Blatt „Mehr". Hat ein Konto genau fuenf, braeuchte „Mehr" einen
    # eigenen Platz fuer einen einzigen Punkt - dann stehen eben drei
    # vorn, und das Blatt traegt zwei. Bei vier oder weniger fehlt
    # nichts in der Leiste.
    if len(punkte) <= TABLEISTE:
        leiste, mehr = punkte, []
    else:
        leiste, mehr = punkte[:TABLEISTE - 1], punkte[TABLEISTE - 1:]

    name = ""
    try:
        name = (benutzer["mitarbeiter"] or "").strip()
    except (IndexError, KeyError, TypeError):
        name = ""
    name = name or benutzer["benutzername"]
    teile = [t for t in name.replace("-", " ").split() if t]
    kuerzel = ("".join(t[0] for t in teile[:2]) or "?").upper()
    bild = ""
    try:
        with db.db() as con:
            bild = _profilbild.adresse(con, benutzer["id"])
    except Exception:  # noqa: BLE001 - ein Bild darf keine Seite kosten
        bild = ""

    ergebnis = {"haupt": punkte, "leiste": leiste, "mehr": mehr,
                "mehr_seiten": [s for p in mehr for s in p["seiten"]],
                "konto": konto, "name": name, "kuerzel": kuerzel, "bild": bild,
                "rolle": "Administrator" if benutzer["rolle"] == "admin"
                         else "Benutzer"}
    request.state._navigation = ergebnis
    return ergebnis


# --- Schnellsuche -------------------------------------------------------------

def _eintrag(gruppe, titel, adresse, symbol="pfeil", zusatz="", worte=""):
    return {"gruppe": gruppe, "titel": titel, "adresse": adresse,
            "symbol": symbol, "zusatz": zusatz,
            "worte": (titel + " " + zusatz + " " + worte).lower()}


@router.get("/schnellsuche.json")
def schnellsuche(request: Request):
    """Alles, wohin die Schnellsuche fuehren kann - fuer DIESES Konto.

    ⚠️ Liefert nur Adressen, keine Inhalte. Wer eine Seite oeffnet, geht
    durch dieselbe Middleware wie bei einem Klick; die Liste kann also
    nichts freigeben, was nicht ohnehin erreichbar waere.
    """
    b = request.state.benutzer
    darf = lambda bereich: auth.hat_zugriff(b, bereich)  # noqa: E731
    liste = []

    # Seiten
    liste.append(_eintrag("Seiten", "Zeiterfassung", "/", "uhr", "Arbeitszeit",
                          "erfassen startseite heute"))
    if darf("datensaetze"):
        liste.append(_eintrag("Seiten", "Übersicht", "/eintraege", "uebersicht",
                              "Arbeitszeit", "datensätze einträge liste"))
    if darf("auswertung"):
        liste.append(_eintrag("Seiten", "Bewilligungen", "/auswertung", "auswertung",
                              "Auswertung", "stand soll ist kontingent rückstand im plan"))
        liste.append(_eintrag("Seiten", "Zeitraum & Nachweis", "/auswertung/zeitraum",
                              "auswertung", "Auswertung",
                              "zeitraum monate nachweis kostenträger verdienst"))
    if darf("verwaltungsvorgaenge"):
        liste.append(_eintrag("Seiten", "Aufgaben", "/vorgaenge", "aufgaben",
                              "", "vorgänge fristen"))
        liste.append(_eintrag("Seiten", "Logbuch der Aufgaben", "/vorgaenge/logbuch",
                              "aufgaben", "Aufgaben", "verlauf"))
    if darf("privatauslagen"):
        liste.append(_eintrag("Seiten", "Privatauslagen", "/privatauslagen",
                              "auslagen", "", "bons belege geld"))
    if darf("fuhrpark"):
        liste.append(_eintrag("Seiten", "Fuhrpark · Erfassung", "/fuhrpark",
                              "fuhrpark", "", "auto tanken km"))
        liste.append(_eintrag("Seiten", "Fuhrpark · Auswertung",
                              "/fuhrpark/auswertung", "fuhrpark", "",
                              "kosten verbrauch tüv"))
    if darf("dateien"):
        liste.append(_eintrag("Seiten", "Dateien", "/dateien", "dateien"))
    if darf("wiki"):
        liste.append(_eintrag("Seiten", "Wiki", "/wiki", "wiki", "", "wissen"))
    liste.append(_eintrag("Seiten", "Mein Bereich", "/meinbereich", "konto",
                          "", "konto saldo urlaub passwort"))
    if darf("ideen"):
        liste.append(_eintrag("Seiten", "Ideen und Rückmeldungen", "/ideen", "ideen"))
    liste.append(_eintrag("Seiten", "Was ist neu?", "/changelog", "neu",
                          "", "changelog versionen"))

    # Einstellungen - jeder Punkt einzeln, mit denselben Pruefungen wie im
    # Menue der Einstellungen (_einstellungen_menue.html).
    if darf("einstellungen"):
        ist_admin = b["rolle"] == "admin"
        punkte = [("oberflaeche", "Darstellung und Oberfläche", True,
                   "theme farbe dunkel hell akzent schrift")]
        for schl, titel in (("quotes", "Sprüche"),
                            ("betreute", "Betreute Personen"),
                            ("mitarbeiter", "Mitarbeiter"),
                            ("kfz", "Fahrzeuge"),
                            ("vorgangsarten", "Aufgabenarten"),
                            ("leistungen", "Leistungen")):
            punkte.append((schl, titel, auth.hat_einst_zugriff(b, schl), ""))
        for schl, titel in (("benutzer", "Benutzerverwaltung"),
                            ("email", "E-Mail"),
                            ("system", "System und Sicherung"),
                            ("hinweistexte", "Texte und Bezeichnungen")):
            punkte.append((schl, titel, ist_admin, ""))
        for schl, titel, ok, worte in punkte:
            if ok:
                liste.append(_eintrag("Einstellungen", titel,
                                      f"/einstellungen?bereich={schl}#punkt",
                                      "einstellungen", "Einstellungen", worte))
        if darf("datenpflege") and ist_admin:
            liste.append(_eintrag("Einstellungen", "Datenpflege",
                                  "/einstellungen/datenpflege#punkt",
                                  "einstellungen", "Einstellungen"))

    # Handgriffe
    if darf("manuelle_eintraege"):
        liste.append(_eintrag("Handgriffe", "Zeit erfassen", "/#erfassen", "plus",
                              "", "neuer eintrag stunden"))
    if darf("verwaltungsvorgaenge"):
        liste.append(_eintrag("Handgriffe", "Neue Aufgabe anlegen",
                              "/vorgaenge?neu=1#neu", "plus", "",
                              "vorgang frist"))
    if darf("privatauslagen"):
        liste.append(_eintrag("Handgriffe", "Auslage erfassen", "/privatauslagen",
                              "plus", "", "bon beleg"))

    # Betreute Personen: Sprung zu ihren Zeiten und Aufgaben.
    if darf("datensaetze") or darf("verwaltungsvorgaenge"):
        with db.db() as con:
            namen = [r["name"] for r in con.execute(
                "SELECT name FROM person WHERE aktiv=1 ORDER BY name")]
        for n in namen:
            if darf("datensaetze"):
                liste.append(_eintrag("Betreute Personen", n,
                                      "/eintraege?klient=" + quote(n), "person",
                                      "Zeiten ansehen"))
            if darf("verwaltungsvorgaenge"):
                liste.append(_eintrag("Betreute Personen", n,
                                      "/vorgaenge/person?name=" + quote(n),
                                      "aufgaben", "Aufgaben und Verlauf"))

    return JSONResponse(liste, headers={"Cache-Control": "no-store"})
