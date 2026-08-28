"""Fuhrpark – Fahrzeuge, Ereignisse, Faelligkeiten und Auswertung.

Eigenes Modul mit eigenem Router, eingebunden am Ende von main.py ueber
setup() und include_router() – dasselbe Muster wie vorgaenge.py,
einstellungen.py und wiki.py.

Grundgedanken:

* Ein Fahrzeug hat Stammdaten (Tabelle "fahrzeug", gepflegt unter
  Einstellungen -> KFZ) und eine Historie (Tabelle "fahrzeug_ereignis").
* Alle Erfassungsarten teilen sich eine Ereignistabelle. Tanken,
  Inspektion, Wartung, Reparatur, Reifenwechsel, TUEV, Kilometerstand und
  sonstige Kosten unterscheiden sich nur darin, welche Felder sie fuellen.
  Das spart sieben fast gleiche Tabellen und macht die Auswertung zu einer
  einzigen Abfrage.
* Der Kilometerstand steckt an jedem Ereignis. Wer ihn beim Tanken
  eintraegt, hat ihn damit auch in der Kilometerhistorie – es gibt keine
  zweite Erfassung fuer dasselbe.
* Faelligkeiten (naechster TUEV, naechste Wartung) werden beim Speichern
  ausgerechnet und in faellig_datum / faellig_km mitgeschrieben. Ein
  spaeteres Erinnerungssystem kann sie damit abfragen, ohne die Rechnung
  zu kennen – dafuer gibt es faelligkeiten() weiter unten.
* Unvollstaendige Daten ergeben keine Zahl statt einer falschen: ein
  Verbrauch entsteht nur zwischen zwei Volltankungen, Kosten je Kilometer
  nur, wenn die gefahrene Strecke bekannt ist.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import db

router = APIRouter()

# von setup() gefuellt, damit dieses Modul main.py nicht importieren muss
_umgebung: dict = {}


# --- Festlegungen -----------------------------------------------------------
#
# Die Reihenfolge bestimmt die Anordnung der Kacheln unter "+ Erfassen"
# und die Reihenfolge in der Kostenauswertung.

# "haupt" markiert die beiden Handgriffe, die staendig vorkommen. Sie
# stehen in der Erfassung oben und etwas groesser; der Rest faellt ein
# paarmal im Jahr an. Bis 0.8.6 stand hier stattdessen "platz" mit einer
# Rasterangabe - das band die Darstellung an eine bestimmte Spaltenzahl und
# hinterliess bei jeder anderen Breite Luecken. Wer eine neunte Art
# ergaenzt, entscheidet hier nur noch "haeufig oder nicht"; das Aussehen
# regelt allein das Stylesheet.
#
# Die Symbole zeichnet das Makro kfz_zeichen() in _kfz_teile.html. Das
# frueher hier stehende Emoji-Feld ist mit 0.8.9 entfallen - es wurde nach
# der Umstellung auf Strichsymbole in keiner Vorlage mehr verwendet.
ARTEN: dict[str, dict] = {
    "tanken":     {"wort": "Tanken", "kosten": True,
                   "haupt": True},
    "inspektion": {"wort": "Inspektion", "kosten": True,
                   "haupt": False},
    "wartung":    {"wort": "Wartung", "kosten": True,
                   "haupt": False},
    "reparatur":  {"wort": "Reparatur", "kosten": True,
                   "haupt": False},
    "reifen":     {"wort": "Reifenwechsel", "kosten": True,
                   "haupt": False},
    "tuev":       {"wort": "TÜV / HU", "kosten": True,
                   "haupt": False},
    "sonstiges":  {"wort": "Sonstige Kosten", "kosten": True,
                   "haupt": False},
    "km":         {"wort": "Kilometerstand", "kosten": False,
                   "haupt": True},
}

# Arten, die eine Faelligkeit nach Zeit und/oder Kilometern tragen koennen.
# Inspektion laeuft dabei als Wartung mit fester Bezeichnung – so gibt es
# nur eine Faelligkeitsrechnung statt zweier fast gleicher.
MIT_INTERVALL = ("inspektion", "wartung", "tuev")

KRAFTSTOFFE = ["Benzin", "Diesel", "Elektro", "Hybrid (Benzin)",
               "Hybrid (Diesel)", "Autogas (LPG)", "Erdgas (CNG)"]

GETRIEBE = ["Schaltgetriebe", "Automatik"]

REIFENWECHSEL = ["Sommer → Winter", "Winter → Sommer", "Neue Reifen"]

# Was als "bald faellig" gilt
BALD_TAGE = 30
BALD_KM = 1000

# Aussortiert, bevor daraus eine Statistik wird: Werte ausserhalb dieser
# Grenzen stammen erfahrungsgemaess aus einem Tippfehler und wuerden den
# Schnitt verderben.
VERBRAUCH_MIN, VERBRAUCH_MAX = 0.5, 60.0


def setup(templates) -> None:
    """Wird von main.py aufgerufen, sobald die Templates bereitstehen."""
    _umgebung["templates"] = templates
    templates.env.globals.update({
        "KFZ_ARTEN": ARTEN,
        "KFZ_KRAFTSTOFFE": KRAFTSTOFFE,
        "KFZ_GETRIEBE": GETRIEBE,
        "KFZ_REIFENWECHSEL": REIFENWECHSEL,
    })
    templates.env.filters["km"] = km_wort
    templates.env.filters["liter"] = liter_wort


def seite(request: Request, vorlage: str, **kontext):
    return _umgebung["templates"].TemplateResponse(
        request=request, name=vorlage, context={"seite": "fuhrpark", **kontext})


# --- kleine Helfer ----------------------------------------------------------

def jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def heute() -> str:
    return dt.date.today().isoformat()


def deutsch(datum: str) -> str:
    try:
        return dt.date.fromisoformat(str(datum)).strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(datum or "")


def km_wort(wert) -> str:
    """148000 wird zu '148.000 km'. Nichts Bekanntes wird zum Gedankenstrich."""
    if wert is None or wert == "":
        return "—"
    try:
        return f"{int(wert):,}".replace(",", ".") + " km"
    except (TypeError, ValueError):
        return "—"


def liter_wort(wert) -> str:
    """42.35 wird zu '42,35'."""
    if wert is None or wert == "":
        return "—"
    try:
        return f"{float(wert):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def komma(wert, stellen: int = 1) -> str:
    try:
        return f"{float(wert):.{stellen}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def sauber(text: str, laenge: int = 200) -> str:
    return " ".join((text or "").split())[:laenge]


def mehrzeilig(text: str, laenge: int = 2000) -> str:
    zeilen = [z.rstrip() for z in (text or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(zeilen).strip()[:laenge]


def datum_lesen(text: str) -> str:
    """Nimmt 2026-09-02 und 02.09.2026 und gibt ISO zurueck, sonst ''."""
    text = (text or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            dt.date.fromisoformat(text)
            return text
        except ValueError:
            return ""
    treffer = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", text)
    if treffer:
        tag, monat, jahr = (int(x) for x in treffer.groups())
        if jahr < 100:
            jahr += 2000
        try:
            return dt.date(jahr, monat, tag).isoformat()
        except ValueError:
            return ""
    return ""


def zahl_lesen(wert, hoechstens: float = 10_000_000) -> float | None:
    """Nimmt 42,5 und 42.5 gleichermassen an. Leer ergibt None."""
    roh = str(wert or "").replace("€", "").replace(" ", "")
    roh = roh.replace(".", "") if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", roh) else roh
    roh = roh.replace(",", ".").strip()
    if not roh:
        return None
    try:
        zahl = float(roh)
    except ValueError:
        return False  # ausdruecklich falsch, nicht bloss leer
    if zahl < 0 or zahl > hoechstens:
        return False
    return zahl


def ganzzahl_lesen(wert, hoechstens: int = 10_000_000) -> int | None:
    zahl = zahl_lesen(wert, hoechstens)
    if zahl is None or zahl is False:
        return zahl
    return int(round(zahl))


def monate_dazu(datum: str, monate: int) -> str:
    """Legt eine Anzahl Monate auf ein Datum. Der 31. wird im kuerzeren
    Monat auf dessen letzten Tag gesetzt."""
    try:
        d = dt.date.fromisoformat(datum)
    except (ValueError, TypeError):
        return ""
    gesamt = d.year * 12 + (d.month - 1) + int(monate)
    jahr, monat = gesamt // 12, gesamt % 12 + 1
    letzter = [31, 29 if (jahr % 4 == 0 and (jahr % 100 or jahr % 400 == 0)) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1]
    return dt.date(jahr, monat, min(d.day, letzter)).isoformat()


def bezeichnung(f) -> str:
    """Wie ein Fahrzeug in Listen heisst: 'BMW 320d', sonst das Kennzeichen."""
    teile = [(f["marke"] or "").strip(), (f["modell"] or "").strip()]
    name = " ".join(t for t in teile if t)
    return name or (f["kennzeichen"] or "").strip() or f"Fahrzeug {f['id']}"


def verbrauchseinheit(f) -> str:
    """Elektroautos verbrauchen kWh, alles andere Liter."""
    return "kWh" if (f["kraftstoff"] or "").startswith("Elektro") else "l"


# --- Fahrzeuge und Kilometerstaende -----------------------------------------

def fahrzeugliste(con, mit_archiv: bool = False):
    bedingung = "" if mit_archiv else " WHERE aktiv=1"
    return con.execute(
        f"SELECT * FROM fahrzeug{bedingung} "
        "ORDER BY aktiv DESC, marke COLLATE NOCASE, modell COLLATE NOCASE, "
        "kennzeichen COLLATE NOCASE").fetchall()


def fahrzeug_holen(con, fahrzeug_id: int):
    f = con.execute("SELECT * FROM fahrzeug WHERE id=?", (fahrzeug_id,)).fetchone()
    if not f:
        raise HTTPException(404, "Fahrzeug nicht gefunden")
    return f


def km_staende(con) -> dict[int, int]:
    """Aktueller Kilometerstand je Fahrzeug.

    Der hoechste erfasste Wert, mindestens aber der Anfangsstand aus den
    Stammdaten. So steht auch bei einem Fahrzeug ohne jedes Ereignis eine
    sinnvolle Zahl da.
    """
    stand = {r["id"]: int(r["km_start"] or 0)
             for r in con.execute("SELECT id, km_start FROM fahrzeug")}
    for r in con.execute(
            "SELECT fahrzeug_id, MAX(km) hoch FROM fahrzeug_ereignis "
            "WHERE km IS NOT NULL GROUP BY fahrzeug_id"):
        if r["hoch"] is not None:
            stand[r["fahrzeug_id"]] = max(stand.get(r["fahrzeug_id"], 0),
                                          int(r["hoch"]))
    return stand


def km_pruefen(con, fahrzeug_id: int, datum: str, km: int,
               ausser_id: int = 0) -> str | None:
    """Meldet einen offensichtlich falschen Kilometerstand.

    Ein Tacho laeuft nur vorwaerts: der Wert darf weder unter dem
    Anfangsstand liegen noch unter einem frueher erfassten Stand, und er
    darf einen spaeter erfassten Stand nicht ueberholen. Gibt den Text der
    Fehlermeldung zurueck oder None, wenn alles stimmt.
    """
    if km is None:
        return None
    f = fahrzeug_holen(con, fahrzeug_id)
    if km < int(f["km_start"] or 0):
        return (f"{km_wort(km)} liegt unter dem Anfangskilometerstand "
                f"({km_wort(f['km_start'])}) aus den Stammdaten.")

    vorher = con.execute(
        "SELECT MAX(km) hoch FROM fahrzeug_ereignis WHERE fahrzeug_id=? "
        "AND km IS NOT NULL AND datum<=? AND id<>?",
        (fahrzeug_id, datum, ausser_id)).fetchone()["hoch"]
    if vorher is not None and km < vorher:
        return (f"{km_wort(km)} ist weniger als der bis zum {deutsch(datum)} "
                f"bereits erfasste Stand ({km_wort(vorher)}).")

    nachher = con.execute(
        "SELECT MIN(km) tief FROM fahrzeug_ereignis WHERE fahrzeug_id=? "
        "AND km IS NOT NULL AND datum>=? AND id<>?",
        (fahrzeug_id, datum, ausser_id)).fetchone()["tief"]
    if nachher is not None and km > nachher:
        return (f"{km_wort(km)} ist mehr als ein später erfasster Stand "
                f"({km_wort(nachher)}).")
    return None


def strecke(con, fahrzeug_id: int, von: str = "", bis: str = "") -> int | None:
    """Gefahrene Kilometer in einem Zeitraum, oder None wenn unbekannt.

    Als Startpunkt zaehlt der letzte Stand vor dem Zeitraum – sonst
    verschenkt man die Strecke zwischen der letzten Ablesung davor und der
    ersten darin.
    """
    wo, werte = ["fahrzeug_id=?", "km IS NOT NULL"], [fahrzeug_id]
    if von:
        wo.append("datum>=?"); werte.append(von)
    if bis:
        wo.append("datum<=?"); werte.append(bis)
    zeile = con.execute(
        f"SELECT MIN(km) tief, MAX(km) hoch, COUNT(*) n FROM fahrzeug_ereignis "
        f"WHERE {' AND '.join(wo)}", werte).fetchone()
    if not zeile["n"]:
        return None
    start = zeile["tief"]
    if von:
        davor = con.execute(
            "SELECT MAX(km) hoch FROM fahrzeug_ereignis WHERE fahrzeug_id=? "
            "AND km IS NOT NULL AND datum<?", (fahrzeug_id, von)).fetchone()["hoch"]
        if davor is not None:
            start = davor
    gefahren = int(zeile["hoch"]) - int(start)
    return gefahren if gefahren > 0 else None


# --- Verbrauch ---------------------------------------------------------------

def verbrauchsreihe(con, fahrzeug_id: int, von: str = "", bis: str = "") -> list[dict]:
    """Verbrauchswerte zwischen je zwei Volltankungen.

    Ein Messpunkt ist eine Tankung, die *voll* ist und einen
    *Kilometerstand* traegt - nur dort ist beides bekannt: der Fuellstand
    (naemlich randvoll) und der Zaehlerstand. Zwischen zwei solchen
    Punkten gilt: alles, was in der Zwischenzeit getankt wurde, ist auf
    dieser Strecke verfahren worden.

    Deshalb zaehlen die Liter *jeder* Tankung dazwischen mit - auch die
    einer Teiltankung und auch die einer Tankung ohne Kilometerstand.
    Sie liefern keinen eigenen Wert, aber ihr Sprit ist mitgefahren.
    Wuerde man sie weglassen, kaeme ein zu niedriger Verbrauch heraus.

    Vor der ersten Volltankung mit Kilometerstand gibt es keinen
    Bezugspunkt; diese Tankungen bleiben aussen vor, ihr Sprit wurde vor
    dem Beginn der Messung verbraucht.
    """
    zeilen = con.execute(
        "SELECT datum, monat, km, liter, voll, kosten FROM fahrzeug_ereignis "
        "WHERE fahrzeug_id=? AND art='tanken' "
        "AND liter IS NOT NULL AND liter>0 ORDER BY datum, id",
        (fahrzeug_id,)).fetchall()

    def messpunkt(z) -> bool:
        return bool(z["voll"]) and z["km"] is not None

    ergebnis: list[dict] = []
    bezug_km = None
    liter_seit = 0.0
    for z in zeilen:
        if bezug_km is None:
            if messpunkt(z):
                bezug_km = int(z["km"])
            continue
        liter_seit += float(z["liter"])
        if not messpunkt(z):
            continue
        gefahren = int(z["km"]) - bezug_km
        if gefahren > 0 and liter_seit > 0:
            wert = liter_seit / gefahren * 100
            if VERBRAUCH_MIN <= wert <= VERBRAUCH_MAX:
                ergebnis.append({
                    "datum": z["datum"], "monat": z["monat"],
                    "km": int(z["km"]), "strecke": gefahren,
                    "liter": round(liter_seit, 2), "verbrauch": wert,
                })
        bezug_km = int(z["km"])
        liter_seit = 0.0

    if von:
        ergebnis = [e for e in ergebnis if e["datum"] >= von]
    if bis:
        ergebnis = [e for e in ergebnis if e["datum"] <= bis]
    return ergebnis


def schnittverbrauch(reihe: list[dict]) -> float | None:
    """Gesamtliter durch Gesamtstrecke – nicht der Mittelwert der
    Einzelwerte, der wuerde kurze Strecken zu stark gewichten."""
    liter = sum(e["liter"] for e in reihe)
    weg = sum(e["strecke"] for e in reihe)
    return liter / weg * 100 if weg > 0 and liter > 0 else None


# --- Faelligkeiten ------------------------------------------------------------

def naechste_faelligkeit(datum: str, km, intervall_monate, intervall_km):
    """Rechnet aus Datum, Kilometerstand und Intervallen die naechste
    Faelligkeit aus. Beide Werte sind unabhaengig – faellig ist, was
    zuerst eintritt."""
    faellig_datum = monate_dazu(datum, intervall_monate) if intervall_monate else ""
    faellig_km = (int(km) + int(intervall_km)) if (intervall_km and km) else None
    return faellig_datum, faellig_km


def _lage(tage: int | None, km_rest: int | None) -> str:
    """'ueberfaellig', 'bald' oder 'offen' – der schlimmere Wert gewinnt."""
    if (tage is not None and tage < 0) or (km_rest is not None and km_rest < 0):
        return "ueberfaellig"
    if (tage is not None and tage <= BALD_TAGE) or \
       (km_rest is not None and km_rest <= BALD_KM):
        return "bald"
    return "offen"


def faelligkeiten(con, fahrzeug_id: int = 0) -> list[dict]:
    """Alles, worum sich jemand kuemmern muss – je Fahrzeug und Anlass.

    Grundlage ist jeweils der juengste Eintrag einer Sache: der letzte TUEV,
    die letzte Inspektion, die letzte Wartung dieser Bezeichnung. Aeltere
    Eintraege sind Historie und stehen hier nicht mehr.

    Diese Funktion ist bewusst frei von Oberflaeche: sie liefert nur Daten
    und ist damit die Stelle, an der ein spaeterer E-Mail-Wecker ansetzen
    kann, ohne die Rechnung noch einmal zu bauen.
    """
    tag = dt.date.today()
    staende = km_staende(con)
    wo = " AND e.fahrzeug_id=?" if fahrzeug_id else ""
    werte = [fahrzeug_id] if fahrzeug_id else []

    # Je Fahrzeug und Bezeichnung nur der neueste Eintrag. Bei gleichem
    # Datum entscheidet die hoehere id, also der zuletzt erfasste.
    zeilen = con.execute(
        f"""SELECT e.*, f.kennzeichen, f.marke, f.modell, f.kraftstoff
            FROM fahrzeug_ereignis e JOIN fahrzeug f ON f.id = e.fahrzeug_id
            WHERE f.aktiv=1 AND e.art IN ('inspektion','wartung','tuev'){wo}
              AND (e.faellig_datum IS NOT NULL AND e.faellig_datum <> ''
                   OR e.faellig_km IS NOT NULL)
              AND e.id = (SELECT z.id FROM fahrzeug_ereignis z
                          WHERE z.fahrzeug_id = e.fahrzeug_id
                            AND z.art = e.art
                            AND IFNULL(z.wartungsart,'') = IFNULL(e.wartungsart,'')
                          ORDER BY z.datum DESC, z.id DESC LIMIT 1)
            ORDER BY e.faellig_datum""", werte).fetchall()

    offen: list[dict] = []
    for z in zeilen:
        tage = km_rest = None
        if z["faellig_datum"]:
            try:
                tage = (dt.date.fromisoformat(z["faellig_datum"]) - tag).days
            except ValueError:
                tage = None
        if z["faellig_km"] is not None:
            km_rest = int(z["faellig_km"]) - staende.get(z["fahrzeug_id"], 0)

        lage = _lage(tage, km_rest)
        if lage == "offen":
            continue

        anlass = ARTEN[z["art"]]["wort"]
        if z["art"] == "wartung" and z["wartungsart"]:
            anlass = z["wartungsart"]
        elif z["art"] == "inspektion":
            anlass = "Inspektion"

        offen.append({
            "fahrzeug_id": z["fahrzeug_id"],
            "fahrzeug": bezeichnung(z),
            "kennzeichen": z["kennzeichen"],
            "art": z["art"], "anlass": anlass,
            "lage": lage, "tage": tage, "km_rest": km_rest,
            "faellig_datum": z["faellig_datum"] or "",
            "faellig_km": z["faellig_km"],
            "text": _faelligkeitstext(tage, km_rest),
        })

    offen += _reifenhinweise(con, fahrzeug_id)
    rang = {"ueberfaellig": 0, "bald": 1, "hinweis": 2}
    offen.sort(key=lambda e: (rang[e["lage"]],
                              e["tage"] if e["tage"] is not None else 9999,
                              e["fahrzeug"]))
    return offen


def _faelligkeitstext(tage: int | None, km_rest: int | None) -> str:
    """Der Satz, der neben dem Fahrzeug steht. Nennt beide Groessen, wenn
    beide bekannt sind – zuerst die dringendere."""
    teile = []
    if tage is not None:
        if tage < 0:
            teile.append(f"seit {abs(tage)} Tag{'en' if abs(tage) != 1 else ''} fällig")
        elif tage == 0:
            teile.append("heute fällig")
        else:
            teile.append(f"in {tage} Tag{'en' if tage != 1 else ''}")
    if km_rest is not None:
        if km_rest < 0:
            teile.append(f"seit {km_wort(abs(km_rest))} überfällig")
        else:
            teile.append(f"in {km_wort(km_rest)}")
    if not teile:
        return ""
    # Stehen beide Groessen da, kommt die ueberschrittene zuerst - sie ist
    # der Grund, warum der Eintrag ueberhaupt in der Liste steht.
    if len(teile) == 2 and (tage is None or tage >= 0) and \
            km_rest is not None and km_rest < 0:
        teile.reverse()
    return " · ".join(teile)


# Ab wann welcher Reifensatz gehoert – die alte Regel "von O bis O".
_AUF_WINTER = (10, 11)
_AUF_SOMMER = (3, 4)


def _reifenhinweise(con, fahrzeug_id: int = 0) -> list[dict]:
    """Saisonaler Hinweis auf den faelligen Reifenwechsel.

    Bewusst nur ein Hinweis und nie "überfällig": ob gewechselt werden
    muss, haengt am Wetter und an der Bereifung, nicht an einem Datum.
    """
    monat = dt.date.today().month
    if monat in _AUF_WINTER:
        ziel, wort = "Winter", "Winterreifen"
    elif monat in _AUF_SOMMER:
        ziel, wort = "Sommer", "Sommerreifen"
    else:
        return []

    wo = " AND f.id=?" if fahrzeug_id else ""
    werte = [fahrzeug_id] if fahrzeug_id else []
    grenze = (dt.date.today() - dt.timedelta(days=120)).isoformat()

    zeilen = con.execute(
        f"""SELECT f.*, (SELECT e.wechsel_art FROM fahrzeug_ereignis e
                         WHERE e.fahrzeug_id=f.id AND e.art='reifen'
                           AND e.datum>=? ORDER BY e.datum DESC, e.id DESC
                         LIMIT 1) letzter
            FROM fahrzeug f WHERE f.aktiv=1{wo}""",
        [grenze, *werte]).fetchall()

    hinweise = []
    for f in zeilen:
        if (f["letzter"] or "").endswith(ziel):
            continue  # in dieser Saison schon gewechselt
        hinweise.append({
            "fahrzeug_id": f["id"], "fahrzeug": bezeichnung(f),
            "kennzeichen": f["kennzeichen"],
            "art": "reifen", "anlass": "Reifenwechsel",
            "lage": "hinweis",
            "tage": None, "km_rest": None, "faellig_datum": "", "faellig_km": None,
            "text": f"Zeit für {wort}",
        })
    return hinweise


# --- Filter -------------------------------------------------------------------

# Die Schnellwahl über der Auswertung. "Benutzerdefiniert" steht hier
# bewusst NICHT mehr drin: die beiden Datumsfelder daneben sind der eigene
# Zeitraum. Ein Punkt in einer Liste, der nur beschreibt, dass man
# nebenan etwas ausfüllen soll, ist ein Umweg - und es war nie zu sehen,
# welche der beiden Angaben gerade gilt.
ZEITRAEUME = {
    "dieser_monat": "Dieser Monat",
    "letzter_monat": "Letzter Monat",
    "dieses_jahr": "Dieses Jahr",
    "letztes_jahr": "Letztes Jahr",
    "alles": "Alle Zeiträume",
}

STANDARD_ZEITRAUM = "dieses_jahr"


def zeitraum_grenzen(zeitraum: str, von: str, bis: str) -> tuple[str, str, str, str]:
    """Gibt (von, bis, Beschriftung, gewaehlte Schnellwahl) zurueck.

    Ein eingetragenes Datum gewinnt: sobald "von" oder "bis" gefuellt ist,
    gilt der eigene Zeitraum und keiner der Schnellwahl-Punkte. Die
    Oberflaeche hebt dann auch keinen davon hervor - so ist immer zu
    sehen, welche Angabe gerade wirkt. Wer zurueck zur Schnellwahl will,
    leert die Datumsfelder; der Klick auf einen Punkt tut das selbst.
    """
    v, b = datum_lesen(von), datum_lesen(bis)
    if v or b:
        if v and b and v > b:
            v, b = b, v
        if v and b:
            wort = f"{deutsch(v)} bis {deutsch(b)}"
        elif v:
            wort = f"ab {deutsch(v)}"
        else:
            wort = f"bis {deutsch(b)}"
        return v, b, wort, ""

    heute_ = dt.date.today()
    erster = heute_.replace(day=1)
    if zeitraum == "dieser_monat":
        letzter = monate_dazu(erster.isoformat(), 1)
        return (erster.isoformat(),
                (dt.date.fromisoformat(letzter) - dt.timedelta(days=1)).isoformat(),
                "Dieser Monat", zeitraum)
    if zeitraum == "letzter_monat":
        anfang = dt.date.fromisoformat(monate_dazu(erster.isoformat(), -1))
        return (anfang.isoformat(), (erster - dt.timedelta(days=1)).isoformat(),
                "Letzter Monat", zeitraum)
    if zeitraum == "dieses_jahr":
        return (f"{heute_.year}-01-01", f"{heute_.year}-12-31",
                f"Jahr {heute_.year}", zeitraum)
    if zeitraum == "letztes_jahr":
        j = heute_.year - 1
        return (f"{j}-01-01", f"{j}-12-31", f"Jahr {j}", zeitraum)
    return "", "", "alle Zeiträume", "alles"


def filter_bauen(zeitraum: str, von: str, bis: str, fahrzeug: str,
                 kategorie: str, fahrzeuge) -> dict:
    if zeitraum not in ZEITRAEUME:
        zeitraum = STANDARD_ZEITRAUM
    von_iso, bis_iso, wort, gewaehlt = zeitraum_grenzen(zeitraum, von, bis)

    fahrzeug_id = 0
    try:
        fahrzeug_id = int(fahrzeug or 0)
    except ValueError:
        fahrzeug_id = 0
    if fahrzeug_id and not any(f["id"] == fahrzeug_id for f in fahrzeuge):
        fahrzeug_id = 0
    if kategorie not in ARTEN:
        kategorie = ""

    wo, werte = ["1=1"], []
    if von_iso:
        wo.append("e.datum>=?"); werte.append(von_iso)
    if bis_iso:
        wo.append("e.datum<=?"); werte.append(bis_iso)
    if fahrzeug_id:
        wo.append("e.fahrzeug_id=?"); werte.append(fahrzeug_id)
    if kategorie:
        wo.append("e.art=?"); werte.append(kategorie)

    aktive = [("Zeitraum", wort)]
    if fahrzeug_id:
        treffer = next((f for f in fahrzeuge if f["id"] == fahrzeug_id), None)
        if treffer:
            aktive.append(("Fahrzeug", bezeichnung(treffer)))
    if kategorie:
        aktive.append(("Kategorie", ARTEN[kategorie]["wort"]))

    # "zeitraum" traegt hier die tatsaechlich wirkende Schnellwahl - leer,
    # wenn ein eigener Zeitraum gilt. Die Vorlage hebt danach hervor.
    #
    # "von"/"bis" sind ausdruecklich nur die selbst eingetragenen Daten und
    # NICHT die Grenzen, die aus einer Schnellwahl herausfallen. Stuende
    # dort "01.01.2026 bis 31.12.2026", weil gerade "Dieses Jahr" gewaehlt
    # ist, dann waere schon der naechste Klick auf "Filtern" ein eigener
    # Zeitraum - die Regel "ein Datum gewinnt" wuerde gegen den Benutzer
    # arbeiten. Die aufgeloesten Grenzen stehen weiter unten unter "von"
    # und "bis" des Filters selbst, dort wo die Abfrage sie braucht.
    felder = {"zeitraum": gewaehlt,
              "von": von_iso if not gewaehlt else "",
              "bis": bis_iso if not gewaehlt else "",
              "fahrzeug": str(fahrzeug_id or ""), "kategorie": kategorie}
    return {"wo": " AND ".join(wo), "werte": werte, "f": felder,
            "von": von_iso, "bis": bis_iso, "wort": wort,
            "fahrzeug_id": fahrzeug_id, "kategorie": kategorie,
            "aktive": aktive,
            "query": urlencode({k: v for k, v in felder.items() if v})}


# --- Erfassung ---------------------------------------------------------------

def zurueck_zu(pfad: str, **werte) -> RedirectResponse:
    frage = urlencode({k: v for k, v in werte.items() if v not in ("", None)})
    if not frage:
        return RedirectResponse(pfad, status_code=303)
    trenner = "&" if "?" in pfad else "?"
    return RedirectResponse(f"{pfad}{trenner}{frage}", status_code=303)


@router.get("/fuhrpark", response_class=HTMLResponse)
def erfassung(request: Request, fahrzeug: str = "", was: str = "",
              bearbeiten: int = 0, hinweis: str = "", fehler: str = "",
              alle: str = ""):
    """Fuhrpark → Erfassung: Fahrzeug waehlen, Ereignis erfassen, Historie."""
    if was not in ARTEN:
        was = ""

    with db.db() as con:
        liste = fahrzeugliste(con)
        gewaehlt = None
        try:
            fahrzeug_id = int(fahrzeug or 0)
        except ValueError:
            fahrzeug_id = 0
        if fahrzeug_id:
            gewaehlt = next((f for f in liste if f["id"] == fahrzeug_id), None)
        if gewaehlt is None and liste:
            gewaehlt = liste[0]

        historie, offene, stand, wartungsarten, zahlen = [], [], None, [], {}
        satz = None
        if gewaehlt:
            grenze = "" if alle else " LIMIT 40"
            historie = con.execute(
                f"SELECT * FROM fahrzeug_ereignis WHERE fahrzeug_id=? "
                f"ORDER BY datum DESC, id DESC{grenze}",
                (gewaehlt["id"],)).fetchall()
            gesamt = con.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(kosten),0) k FROM fahrzeug_ereignis "
                "WHERE fahrzeug_id=?", (gewaehlt["id"],)).fetchone()
            zahlen = {"n": gesamt["n"], "kosten": gesamt["k"]}
            stand = km_staende(con).get(gewaehlt["id"])
            offene = faelligkeiten(con, gewaehlt["id"])
            wartungsarten = [r["wartungsart"] for r in con.execute(
                "SELECT DISTINCT wartungsart FROM fahrzeug_ereignis "
                "WHERE art='wartung' AND wartungsart IS NOT NULL "
                "AND TRIM(wartungsart) <> '' ORDER BY 1 COLLATE NOCASE")]
            if bearbeiten:
                satz = con.execute(
                    "SELECT * FROM fahrzeug_ereignis WHERE id=? AND fahrzeug_id=?",
                    (bearbeiten, gewaehlt["id"])).fetchone()
                if satz:
                    was = satz["art"]

    return seite(request, "kfz_erfassung.html",
                 unterseite="erfassung", fahrzeuge=liste, gewaehlt=gewaehlt,
                 historie=historie, zahlen=zahlen, stand=stand, offene=offene,
                 wartungsarten=wartungsarten, was=was, satz=satz,
                 alle=bool(alle), heute_iso=heute(), hinweis=hinweis,
                 fehler=fehler, bezeichnung=bezeichnung,
                 einheit=verbrauchseinheit(gewaehlt) if gewaehlt else "l")


def _ereignis_lesen(art: str, datum: str, km: str, kosten: str, liter: str,
                    voll: str, wartungsart: str, wechsel_art: str,
                    beschreibung: str, werkstatt: str, notiz: str,
                    faellig_datum: str, intervall_monate: str,
                    intervall_km: str) -> tuple[dict | None, str]:
    """Prueft die Eingaben eines Erfassungsformulars.

    Gibt (Werte, Fehlertext) zurueck – genau eines von beiden ist gefuellt.
    """
    if art not in ARTEN:
        return None, "Unbekannte Art der Erfassung."

    tag = datum_lesen(datum)
    if not tag:
        return None, "Das Datum fehlt oder passt nicht. Schreib es als TT.MM.JJJJ."
    if tag > (dt.date.today() + dt.timedelta(days=1)).isoformat():
        return None, "Das Datum liegt in der Zukunft."

    km_wert = ganzzahl_lesen(km, 3_000_000)
    if km_wert is False:
        return None, "Der Kilometerstand muss eine ganze Zahl sein."
    if art == "km" and km_wert is None:
        return None, "Ohne Kilometerstand geht es bei dieser Erfassung nicht."

    betrag = zahl_lesen(kosten, 100_000)
    if betrag is False:
        return None, "Der Preis muss ein Betrag sein, zum Beispiel 68,40."

    menge = zahl_lesen(liter, 2000)
    if menge is False:
        return None, "Die Menge muss eine Zahl sein, zum Beispiel 42,35."

    # Der Kilometerstand ist beim Tanken ausdruecklich freiwillig. Ohne ihn
    # zaehlt die Tankfuellung bei den Kosten mit, ist aber kein Messpunkt
    # fuer den Verbrauch - ihre Liter gehen trotzdem nicht verloren, sie
    # zaehlen zur naechsten Volltankung mit Stand (siehe verbrauchsreihe).
    # Aus getrennt erfassten Kilometerstaenden laesst sich der Stand an der
    # Zapfsaeule nicht ableiten: dazwischen liegen unbekannt viele
    # Kilometer, und geschaetzte Werte waeren erfundene Statistik.
    if art == "tanken" and not menge:
        return None, "Ohne getankte Menge lässt sich kein Verbrauch rechnen."

    monate = ganzzahl_lesen(intervall_monate, 240)
    if monate is False:
        return None, "Das Intervall in Monaten muss eine ganze Zahl sein."
    strecke_km = ganzzahl_lesen(intervall_km, 500_000)
    if strecke_km is False:
        return None, "Das Intervall in Kilometern muss eine ganze Zahl sein."

    if art not in MIT_INTERVALL:
        monate = strecke_km = None

    naechster = datum_lesen(faellig_datum)
    if faellig_datum.strip() and not naechster:
        return None, "Der nächste Termin ist kein gültiges Datum."

    # Aus den Intervallen rechnen, wenn kein Termin von Hand gesetzt wurde.
    # Beide Wege schreiben in dieselben Felder, damit die Faelligkeitsliste
    # nur eine Quelle kennt.
    gerechnet_datum, gerechnet_km = naechste_faelligkeit(tag, km_wert, monate,
                                                         strecke_km)
    if not naechster:
        naechster = gerechnet_datum

    if art == "reifen" and wechsel_art not in REIFENWECHSEL:
        return None, "Bitte angeben, worauf gewechselt wurde."

    if art == "reparatur" and not sauber(beschreibung):
        return None, "Bitte kurz beschreiben, was repariert wurde."

    return {
        "art": art, "datum": tag, "monat": tag[:7], "km": km_wert,
        "kosten": betrag, "liter": menge if art == "tanken" else None,
        "voll": 1 if (art != "tanken" or voll) else 0,
        "wartungsart": (sauber(wartungsart, 120) if art == "wartung"
                        else ("Inspektion" if art == "inspektion" else None)),
        "wechsel_art": sauber(wechsel_art, 60) if art == "reifen" else None,
        "beschreibung": sauber(beschreibung, 300),
        "werkstatt": sauber(werkstatt, 120),
        "notiz": mehrzeilig(notiz, 2000),
        "faellig_datum": naechster,
        "faellig_km": gerechnet_km,
        "intervall_monate": monate, "intervall_km": strecke_km,
    }, ""


@router.post("/fuhrpark/erfassen")
def erfassen(fahrzeug_id: int = Form(0), art: str = Form(""),
             datum: str = Form(""), km: str = Form(""), kosten: str = Form(""),
             liter: str = Form(""), voll: str = Form(""),
             wartungsart: str = Form(""), wechsel_art: str = Form(""),
             beschreibung: str = Form(""), werkstatt: str = Form(""),
             notiz: str = Form(""), faellig_datum: str = Form(""),
             intervall_monate: str = Form(""), intervall_km: str = Form(""),
             eintrag_id: int = Form(0), wer: str = Form("")):
    """Legt ein Ereignis an oder speichert die Aenderung eines bestehenden."""
    ziel = f"/fuhrpark?fahrzeug={fahrzeug_id}"

    werte, fehler = _ereignis_lesen(
        art, datum, km, kosten, liter, voll, wartungsart, wechsel_art,
        beschreibung, werkstatt, notiz, faellig_datum, intervall_monate,
        intervall_km)
    if fehler:
        return zurueck_zu(ziel, was=art, bearbeiten=eintrag_id or "", fehler=fehler)

    with db.db() as con:
        f = con.execute("SELECT * FROM fahrzeug WHERE id=?",
                        (fahrzeug_id,)).fetchone()
        if not f:
            return zurueck_zu("/fuhrpark", fehler="Dieses Fahrzeug gibt es nicht.")
        if not f["aktiv"]:
            return zurueck_zu(ziel, fehler=(
                "Dieses Fahrzeug ist archiviert. Zum Erfassen bitte unter "
                "Einstellungen → KFZ wieder aktiv setzen."))

        problem = km_pruefen(con, fahrzeug_id, werte["datum"], werte["km"],
                             eintrag_id)
        if problem:
            return zurueck_zu(ziel, was=art, bearbeiten=eintrag_id or "",
                              fehler=problem)

        spalten = list(werte.keys())
        if eintrag_id:
            vorhanden = con.execute(
                "SELECT id FROM fahrzeug_ereignis WHERE id=? AND fahrzeug_id=?",
                (eintrag_id, fahrzeug_id)).fetchone()
            if not vorhanden:
                return zurueck_zu(ziel, fehler="Dieser Eintrag existiert nicht mehr.")
            satz = ", ".join(f"{s}=?" for s in spalten)
            con.execute(f"UPDATE fahrzeug_ereignis SET {satz} WHERE id=?",
                        [*werte.values(), eintrag_id])
            text = f"{ARTEN[art]['wort']} vom {deutsch(werte['datum'])} geändert."
        else:
            felder = ", ".join(["fahrzeug_id", *spalten, "angelegt_am",
                                "angelegt_von"])
            platz = ",".join("?" * (len(spalten) + 3))
            con.execute(
                f"INSERT INTO fahrzeug_ereignis ({felder}) VALUES ({platz})",
                [fahrzeug_id, *werte.values(), jetzt(), sauber(wer, 80)])
            text = f"{ARTEN[art]['wort']} vom {deutsch(werte['datum'])} gespeichert."

    return zurueck_zu(ziel, hinweis=text)


@router.post("/fuhrpark/ereignis/{eintrag_id}/loeschen")
def ereignis_loeschen(eintrag_id: int, zurueck: str = Form("/fuhrpark")):
    with db.db() as con:
        z = con.execute("SELECT * FROM fahrzeug_ereignis WHERE id=?",
                        (eintrag_id,)).fetchone()
        if not z:
            return zurueck_zu(zurueck, fehler="Dieser Eintrag existiert nicht mehr.")
        con.execute("DELETE FROM fahrzeug_ereignis WHERE id=?", (eintrag_id,))
    return zurueck_zu(zurueck, hinweis=(
        f"{ARTEN.get(z['art'], {}).get('wort', 'Eintrag')} vom "
        f"{deutsch(z['datum'])} gelöscht."))


# --- Auswertung ---------------------------------------------------------------

def _monatsliste(von: str, bis: str, vorhandene: list[str]) -> list[str]:
    """Alle Monate des Zeitraums. Ohne Grenzen die tatsaechlich belegten."""
    if not von or not bis:
        return sorted(set(vorhandene))
    lauf, ende = von[:7], bis[:7]
    monate = []
    while lauf <= ende and len(monate) < 120:
        monate.append(lauf)
        lauf = monate_dazu(lauf + "-01", 1)[:7]
    return monate


@router.get("/fuhrpark/auswertung", response_class=HTMLResponse)
def auswertung(request: Request, zeitraum: str = "dieses_jahr", von: str = "",
               bis: str = "", fahrzeug: str = "", kategorie: str = ""):
    """Fuhrpark → Auswertung: das Cockpit ueber alle Fahrzeuge."""
    heute_ = dt.date.today()
    monat_von = heute_.replace(day=1).isoformat()
    jahr_von = f"{heute_.year}-01-01"

    with db.db() as con:
        alle_fahrzeuge = fahrzeugliste(con)
        filter_ = filter_bauen(zeitraum, von, bis, fahrzeug, kategorie,
                               alle_fahrzeuge)
        wo, werte = filter_["wo"], filter_["werte"]

        zeilen = con.execute(
            f"SELECT e.*, f.kennzeichen, f.marke, f.modell, f.kraftstoff "
            f"FROM fahrzeug_ereignis e JOIN fahrzeug f ON f.id=e.fahrzeug_id "
            f"WHERE f.aktiv=1 AND {wo} ORDER BY e.datum DESC, e.id DESC",
            werte).fetchall()

        offen = faelligkeiten(con, filter_["fahrzeug_id"])
        staende = km_staende(con)

        betroffen = ([f for f in alle_fahrzeuge if f["id"] == filter_["fahrzeug_id"]]
                     if filter_["fahrzeug_id"] else list(alle_fahrzeuge))
        je_fahrzeug = []
        for f in betroffen:
            eigene = [z for z in zeilen if z["fahrzeug_id"] == f["id"]]
            gefahren = strecke(con, f["id"], filter_["von"], filter_["bis"])
            reihe = verbrauchsreihe(con, f["id"], filter_["von"], filter_["bis"])
            kosten = sum(float(z["kosten"] or 0) for z in eigene)
            je_fahrzeug.append({
                "id": f["id"], "name": bezeichnung(f),
                "kennzeichen": f["kennzeichen"],
                "stand": staende.get(f["id"]),
                "kosten": kosten,
                "je_art": {a: sum(float(z["kosten"] or 0) for z in eigene
                                  if z["art"] == a) for a in ARTEN},
                "strecke": gefahren,
                "je_km": (kosten / gefahren) if (gefahren and kosten) else None,
                "verbrauch": schnittverbrauch(reihe),
                "einheit": verbrauchseinheit(f),
                "messungen": len(reihe),
                "eintraege": len(eigene),
                "reihe": reihe,
            })

        # Die beiden festen Kennzahlen oben stehen bewusst ausserhalb des
        # Filters: sie beantworten "was kostet der Fuhrpark gerade", nicht
        # "was kostet der gewaehlte Ausschnitt".
        monatskosten = con.execute(
            "SELECT COALESCE(SUM(e.kosten),0) k FROM fahrzeug_ereignis e "
            "JOIN fahrzeug f ON f.id=e.fahrzeug_id WHERE f.aktiv=1 AND e.datum>=?",
            (monat_von,)).fetchone()["k"]
        jahreskosten = con.execute(
            "SELECT COALESCE(SUM(e.kosten),0) k FROM fahrzeug_ereignis e "
            "JOIN fahrzeug f ON f.id=e.fahrzeug_id WHERE f.aktiv=1 AND e.datum>=?",
            (jahr_von,)).fetchone()["k"]

    # --- Kennzahlen ---------------------------------------------------------
    gesamtkosten = sum(float(z["kosten"] or 0) for z in zeilen)
    gesamtstrecke = sum(f["strecke"] or 0 for f in je_fahrzeug)
    je_km = (gesamtkosten / gesamtstrecke) if gesamtstrecke and gesamtkosten else None

    liter_gesamt = sum(e["liter"] for f in je_fahrzeug for e in f["reihe"])
    weg_gesamt = sum(e["strecke"] for f in je_fahrzeug for e in f["reihe"])
    schnitt = (liter_gesamt / weg_gesamt * 100) if weg_gesamt and liter_gesamt else None
    # Liter und Kilowattstunden lassen sich nicht zu einer Zahl addieren.
    # Sind beide Sorten dabei, bleibt die Einheit weg statt falsch zu sein.
    einheiten = {f["einheit"] for f in je_fahrzeug if f["reihe"]}
    einheit_gesamt = einheiten.pop() if len(einheiten) == 1 else ""

    kennzahlen = {
        "fahrzeuge": len(alle_fahrzeuge),
        "monat": monatskosten,
        "jahr": jahreskosten,
        "zeitraum_kosten": gesamtkosten,
        "je_km": je_km,
        "strecke": gesamtstrecke,
        "verbrauch": schnitt, "einheit": einheit_gesamt,
        "ueberfaellig": sum(1 for e in offen if e["lage"] == "ueberfaellig"),
        "bald": sum(1 for e in offen if e["lage"] == "bald"),
        "hinweise": sum(1 for e in offen if e["lage"] == "hinweis"),
    }

    # --- Kosten nach Kategorie ----------------------------------------------
    je_art = []
    for schluessel, angaben in ARTEN.items():
        if not angaben["kosten"]:
            continue
        betrag = sum(float(z["kosten"] or 0) for z in zeilen if z["art"] == schluessel)
        if betrag:
            je_art.append({"art": schluessel, "wort": angaben["wort"],
                           "betrag": betrag,
                           "anteil": betrag / gesamtkosten * 100 if gesamtkosten else 0})
    je_art.sort(key=lambda r: -r["betrag"])

    # --- Kosten je Monat ----------------------------------------------------
    vorhandene = sorted({z["monat"] for z in zeilen})
    monate = _monatsliste(filter_["von"], filter_["bis"], vorhandene)
    if len(monate) > 24:
        monate = monate[-24:]
    je_monat = []
    for m in monate:
        stapel = {a: sum(float(z["kosten"] or 0) for z in zeilen
                         if z["monat"] == m and z["art"] == a) for a in ARTEN}
        je_monat.append({"monat": m, "summe": sum(stapel.values()),
                         "stapel": stapel})

    je_fahrzeug.sort(key=lambda r: -r["kosten"])
    letzte = zeilen[:12]

    return seite(request, "kfz_auswertung.html",
                 unterseite="auswertung", fahrzeuge=alle_fahrzeuge,
                 f=filter_["f"], aktive_filter=filter_["aktive"],
                 zeitraum_wort=filter_["wort"], query=filter_["query"],
                 ZEITRAEUME=ZEITRAEUME,
                 offen=offen, kennzahlen=kennzahlen, je_art=je_art,
                 je_fahrzeug=je_fahrzeug, letzte=letzte,
                 kostendiagramm=kostendiagramm(je_monat, je_art),
                 kuchen=kuchendiagramm(je_art),
                 verbrauchsdiagramm=verbrauchsdiagramm(je_fahrzeug),
                 bezeichnung=bezeichnung, komma=komma,
                 monate_anzahl=len(monate))


# --- Diagramme ----------------------------------------------------------------
#
# Wie das Stundendiagramm in "Mein Bereich": fertig gerechnetes SVG statt
# einer Diagramm-Bibliothek. Die Anwendung laedt zur Laufzeit nichts aus dem
# Internet nach, und ein Balken ist eine Rechenaufgabe, kein Grund fuer ein
# weiteres Paket im pip-Aufruf der Compose-Datei.

MONATSKURZ = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
              "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _monatskurz(monat: str) -> str:
    try:
        return MONATSKURZ[int(monat[5:7]) - 1]
    except (ValueError, IndexError):
        return monat


def kostendiagramm(je_monat: list[dict], je_art: list[dict]) -> dict | None:
    """Kosten je Monat, nach Kategorie gestapelt.

    Beantwortet: Wofuer ging das Geld drauf, und wann?
    """
    je_monat = [m for m in je_monat if m["summe"] > 0]
    if len(je_monat) < 2:
        return None

    arten = [a["art"] for a in je_art] or ["sonstiges"]
    breite, hoehe = 640, 220
    oben, unten, links, rechts = 14, 30, 46, 10
    flaeche = hoehe - oben - unten
    spalte = (breite - links - rechts) / len(je_monat)
    spitze = max(m["summe"] for m in je_monat) * 1.15 or 1

    saeulen = []
    for i, m in enumerate(je_monat):
        x = links + i * spalte + spalte * 0.2
        balkenbreite = min(spalte * 0.6, 46)
        unterkante = oben + flaeche
        teile = []
        for art in arten:
            betrag = m["stapel"].get(art, 0)
            if betrag <= 0:
                continue
            h = flaeche * (betrag / spitze)
            unterkante -= h
            teile.append({"y": round(unterkante, 1), "h": round(max(h, 1), 1),
                          "art": art, "wort": ARTEN[art]["wort"],
                          "betrag": betrag})
        saeulen.append({
            "x": round(x, 1), "b": round(balkenbreite, 1),
            "mitte": round(x + balkenbreite / 2, 1),
            "teile": teile, "summe": m["summe"],
            "kurz": _monatskurz(m["monat"]), "jahr": m["monat"][:4],
            "oben": round(unterkante, 1),
        })

    return {"breite": breite, "hoehe": hoehe, "links": links,
            "grundlinie": oben + flaeche, "rechts_x": breite - rechts,
            "saeulen": saeulen, "spitze": spitze,
            "arten": [a for a in je_art]}


def kuchendiagramm(je_art: list[dict]) -> dict | None:
    """Kostenverteilung als Ring.

    Beantwortet: Welcher Anteil der Kosten faellt auf welche Kategorie?
    """
    gesamt = sum(a["betrag"] for a in je_art)
    if not gesamt or len(je_art) < 2:
        return None
    radius, dicke = 54, 22
    umfang = 2 * 3.141592653589793 * radius
    stuecke, versatz = [], 0.0
    for a in je_art:
        laenge = umfang * (a["betrag"] / gesamt)
        stuecke.append({
            "art": a["art"], "wort": a["wort"], "betrag": a["betrag"],
            "anteil": a["anteil"],
            "laenge": round(laenge, 2), "rest": round(umfang - laenge, 2),
            "versatz": round(-versatz, 2),
        })
        versatz += laenge
    return {"radius": radius, "dicke": dicke, "umfang": round(umfang, 2),
            "stuecke": stuecke, "gesamt": gesamt}


def verbrauchsdiagramm(je_fahrzeug: list[dict]) -> dict | None:
    """Verbrauchsentwicklung als Linie, eine je Fahrzeug.

    Beantwortet: Wird das Fahrzeug durstiger?
    """
    mit_werten = [f for f in je_fahrzeug if len(f["reihe"]) >= 2][:5]
    if not mit_werten:
        return None

    alle = [e["datum"] for f in mit_werten for e in f["reihe"]]
    von, bis = min(alle), max(alle)
    try:
        tag_von = dt.date.fromisoformat(von)
        spanne = max((dt.date.fromisoformat(bis) - tag_von).days, 1)
    except ValueError:
        return None

    werte = [e["verbrauch"] for f in mit_werten for e in f["reihe"]]
    tief, hoch = min(werte), max(werte)
    if hoch - tief < 1:
        tief, hoch = tief - 0.5, hoch + 0.5
    rand = (hoch - tief) * 0.15
    tief, hoch = max(0, tief - rand), hoch + rand

    breite, hoehe = 640, 210
    oben, unten, links, rechts = 14, 30, 44, 12
    flaeche = hoehe - oben - unten
    weite = breite - links - rechts

    linien = []
    for nr, f in enumerate(mit_werten):
        punkte = []
        for e in f["reihe"]:
            try:
                versatz = (dt.date.fromisoformat(e["datum"]) - tag_von).days
            except ValueError:
                continue
            x = links + weite * (versatz / spanne)
            y = oben + flaeche - flaeche * ((e["verbrauch"] - tief) / (hoch - tief))
            punkte.append({"x": round(x, 1), "y": round(y, 1),
                           "wert": komma(e["verbrauch"], 1),
                           "datum": deutsch(e["datum"])})
        if len(punkte) >= 2:
            linien.append({"name": f["name"], "nr": nr % 5,
                           "einheit": f["einheit"],
                           "pfad": " ".join(f"{p['x']},{p['y']}" for p in punkte),
                           "punkte": punkte,
                           "schnitt": komma(f["verbrauch"], 1) if f["verbrauch"] else "—"})
    if not linien:
        return None

    return {"breite": breite, "hoehe": hoehe, "links": links, "oben": oben,
            "grundlinie": oben + flaeche, "rechts_x": breite - rechts,
            "linien": linien, "tief": komma(tief, 1), "hoch": komma(hoch, 1),
            "von": deutsch(von), "bis": deutsch(bis)}


# --- Fahrzeugstammdaten (Einstellungen -> KFZ) --------------------------------
#
# Die Routen liegen hier und nicht in einstellungen.py, weil alles rund um
# Fahrzeuge in einem Modul stehen soll. Die Anzeige des Reiters selbst sitzt
# dagegen in einstellungen.py, damit die Einstellungsseite eine Seite bleibt.
# Geschuetzt sind diese Routen ueber das Pfadpraefix /einstellungen
# (siehe auth.BEREICH_PFADE) - wie alle anderen Einstellungen auch.

def kfz_zurueck(**werte):
    werte.setdefault("bereich", "kfz")
    return RedirectResponse("/einstellungen?" + urlencode(
        {k: v for k, v in werte.items() if v not in ("", None)}), status_code=303)


def kennzeichen_norm(text: str) -> str:
    """Vergleichsform eines Kennzeichens: ohne Leerzeichen und Bindestriche,
    in Grossbuchstaben. So gilt 'ST-AB 123' als dasselbe wie 'STAB123'."""
    return re.sub(r"[\s\-·.]", "", (text or "")).upper()


def _stammdaten_lesen(kennzeichen: str, marke: str, modell: str, baujahr: str,
                      erstzulassung: str, km_start: str, kraftstoff: str,
                      leistung: str, hubraum: str, getriebe: str, farbe: str,
                      notiz: str) -> tuple[dict | None, str]:
    kennzeichen = sauber(kennzeichen, 20).upper()
    if not kennzeichen:
        return None, "Ohne Kennzeichen geht es nicht."

    jahr = ganzzahl_lesen(baujahr, 2200)
    if jahr is False or (jahr is not None and not 1900 <= jahr <= dt.date.today().year + 1):
        return None, (f"Das Baujahr muss eine Jahreszahl zwischen 1900 und "
                      f"{dt.date.today().year + 1} sein.")

    zulassung = datum_lesen(erstzulassung)
    if erstzulassung.strip() and not zulassung:
        return None, "Die Erstzulassung ist kein gültiges Datum."

    anfang = ganzzahl_lesen(km_start, 3_000_000)
    if anfang is False:
        return None, "Der Kilometerstand muss eine ganze Zahl sein."

    kw = ganzzahl_lesen(leistung, 2000)
    if kw is False:
        return None, "Die Leistung muss eine ganze Zahl in kW sein."

    ccm = ganzzahl_lesen(hubraum, 20000)
    if ccm is False:
        return None, "Der Hubraum muss eine ganze Zahl in cm³ sein."

    return {
        "kennzeichen": kennzeichen,
        "marke": sauber(marke, 60), "modell": sauber(modell, 80),
        "baujahr": jahr, "erstzulassung": zulassung,
        "km_start": anfang or 0,
        "kraftstoff": kraftstoff if kraftstoff in KRAFTSTOFFE else "",
        "leistung": kw, "hubraum": ccm,
        "getriebe": getriebe if getriebe in GETRIEBE else "",
        "farbe": sauber(farbe, 40), "notiz": mehrzeilig(notiz, 1000),
    }, ""


@router.post("/einstellungen/fahrzeug")
def fahrzeug_anlegen(kennzeichen: str = Form(""), marke: str = Form(""),
                     modell: str = Form(""), baujahr: str = Form(""),
                     erstzulassung: str = Form(""), km_start: str = Form(""),
                     kraftstoff: str = Form(""), leistung: str = Form(""),
                     hubraum: str = Form(""), getriebe: str = Form(""),
                     farbe: str = Form(""), notiz: str = Form("")):
    werte, fehler = _stammdaten_lesen(kennzeichen, marke, modell, baujahr,
                                      erstzulassung, km_start, kraftstoff,
                                      leistung, hubraum, getriebe, farbe, notiz)
    if fehler:
        return kfz_zurueck(fehler=fehler)

    with db.db() as con:
        vergeben = kennzeichen_norm(werte["kennzeichen"])
        if any(kennzeichen_norm(r["kennzeichen"]) == vergeben
               for r in con.execute("SELECT kennzeichen FROM fahrzeug")):
            return kfz_zurueck(
                fehler=f"„{werte['kennzeichen']}“ ist bereits angelegt.")
        spalten = list(werte.keys())
        con.execute(
            f"INSERT INTO fahrzeug ({', '.join(spalten)}, aktiv, angelegt_am, "
            f"geaendert_am) VALUES ({','.join('?' * len(spalten))},1,?,?)",
            [*werte.values(), jetzt(), jetzt()])
    name = " ".join(t for t in (werte["marke"], werte["modell"]) if t) \
           or werte["kennzeichen"]
    return kfz_zurueck(hinweis=f"{name} angelegt.")


@router.post("/einstellungen/fahrzeug/{fahrzeug_id}")
def fahrzeug_speichern(fahrzeug_id: int, kennzeichen: str = Form(""),
                       marke: str = Form(""), modell: str = Form(""),
                       baujahr: str = Form(""), erstzulassung: str = Form(""),
                       km_start: str = Form(""), kraftstoff: str = Form(""),
                       leistung: str = Form(""), hubraum: str = Form(""),
                       getriebe: str = Form(""), farbe: str = Form(""),
                       notiz: str = Form(""), aktiv: str = Form("")):
    werte, fehler = _stammdaten_lesen(kennzeichen, marke, modell, baujahr,
                                      erstzulassung, km_start, kraftstoff,
                                      leistung, hubraum, getriebe, farbe, notiz)
    if fehler:
        return kfz_zurueck(fehler=fehler)

    with db.db() as con:
        vergeben = kennzeichen_norm(werte["kennzeichen"])
        if any(kennzeichen_norm(r["kennzeichen"]) == vergeben for r in con.execute(
                "SELECT kennzeichen FROM fahrzeug WHERE id<>?", (fahrzeug_id,))):
            return kfz_zurueck(
                fehler=f"„{werte['kennzeichen']}“ ist bereits angelegt.")
        # Ein nachtraeglich erhoehter Anfangsstand darf nicht ueber einem
        # bereits erfassten Kilometerstand liegen - sonst stimmt die
        # Historie nicht mehr.
        tiefster = con.execute(
            "SELECT MIN(km) tief FROM fahrzeug_ereignis WHERE fahrzeug_id=? "
            "AND km IS NOT NULL", (fahrzeug_id,)).fetchone()["tief"]
        if tiefster is not None and werte["km_start"] > tiefster:
            return kfz_zurueck(fehler=(
                f"Der Anfangskilometerstand kann nicht über dem bereits "
                f"erfassten Stand von {km_wort(tiefster)} liegen."))

        satz = ", ".join(f"{s}=?" for s in werte)
        con.execute(
            f"UPDATE fahrzeug SET {satz}, aktiv=?, geaendert_am=? WHERE id=?",
            [*werte.values(), 1 if aktiv else 0, jetzt(), fahrzeug_id])
    name = " ".join(t for t in (werte["marke"], werte["modell"]) if t) \
           or werte["kennzeichen"]
    return kfz_zurueck(hinweis=f"{name} gespeichert.")


@router.post("/einstellungen/fahrzeug/{fahrzeug_id}/archivieren")
def fahrzeug_archivieren(fahrzeug_id: int, aktiv: str = Form("")):
    """Legt ein Fahrzeug still oder holt es zurueck.

    Bewusst kein Loeschen: die Historie eines ausgemusterten Fahrzeugs
    bleibt fuer die Kostenauswertung vergangener Jahre erhalten.
    """
    with db.db() as con:
        f = con.execute("SELECT * FROM fahrzeug WHERE id=?",
                        (fahrzeug_id,)).fetchone()
        if not f:
            return kfz_zurueck(fehler="Dieses Fahrzeug gibt es nicht mehr.")
        neu = 1 if aktiv else 0
        con.execute("UPDATE fahrzeug SET aktiv=?, geaendert_am=? WHERE id=?",
                    (neu, jetzt(), fahrzeug_id))
    return kfz_zurueck(hinweis=(
        f"{bezeichnung(f)} ist wieder im Fuhrpark." if neu
        else f"{bezeichnung(f)} archiviert. Die Historie bleibt erhalten."))


@router.post("/einstellungen/fahrzeug/{fahrzeug_id}/loeschen")
def fahrzeug_loeschen(fahrzeug_id: int):
    """Entfernt ein Fahrzeug endgueltig - samt seiner ganzen Historie."""
    with db.db() as con:
        f = con.execute("SELECT * FROM fahrzeug WHERE id=?",
                        (fahrzeug_id,)).fetchone()
        if not f:
            return kfz_zurueck(fehler="Dieses Fahrzeug gibt es nicht mehr.")
        anzahl = con.execute(
            "SELECT COUNT(*) c FROM fahrzeug_ereignis WHERE fahrzeug_id=?",
            (fahrzeug_id,)).fetchone()["c"]
        con.execute("DELETE FROM fahrzeug WHERE id=?", (fahrzeug_id,))
    zusatz = f" Mit {anzahl} Einträgen aus der Historie." if anzahl else ""
    return kfz_zurueck(hinweis=f"{bezeichnung(f)} gelöscht.{zusatz}")
