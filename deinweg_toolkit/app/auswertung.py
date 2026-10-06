"""Die Auswertung - Soll-Ist-Vergleich je betreuter Person und Monat.

Seit 1.32 ein eigenes Modul. Bis dahin stand sie in main.py, mit der
Begruendung, sie teile sich ``bereichsfilter()`` mit der Uebersicht -
das stimmt, aber dieser Filter steht jetzt in rechnen.py und ist damit
von beiden Seiten erreichbar, ohne dass eine die andere importieren
muss.

Gerechnet wird Monat fuer Monat (siehe rechnen.kontingent_im_monat):
Wochenstunden und Stundensatz koennen sich innerhalb eines Zeitraums
aendern, weil der Kostentraeger immer nur befristet zusagt.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from . import db
from .parser import norm
from .rechnen import (STAND_GRUPPEN, auswahllisten, bereichsfilter,
                      bewilligungsstand, kontingent_im_monat,
                      monat_wort, monatsliste, soll_minuten,
                      zeitraeume_lesen)

router = APIRouter()

# von setup() gefuellt - dieses Modul braucht nur die Templates
_u: dict = {}


def setup(templates, umgebung=None) -> None:
    _u["templates"] = templates
    _u.update(umgebung or {})


# ⚠️ Abschnitte der Karte (seit dem Umbau 2.1, Timos „deutlich zu
# unruhig“): statt einer Farbe je Zeile eine Ordnung nach Dringlichkeit -
# dieselbe Reihenfolge wie vereinbart (rot, orange, gelb, gruen,
# Selbstzahler). Die Farbe traegt danach nur noch der Stand selbst.
STAND_ABSCHNITTE = (
    ("rueckstand", "Im Rückstand"),
    ("ohne", "Ohne gültige Bewilligung"),
    ("vorlaeufig", "Vorläufig – Bescheid steht aus"),
    ("offen", "Diesen Monat noch offen"),
    ("plan", "Im Plan"),
    ("selbst", "Selbstzahler"),
)


def _abschnitt(z: dict) -> str:
    if z["art"] == "selbstzahler":
        return "selbst"
    if z["art"] in ("fehlt", "kuenftig", "abgelaufen"):
        return "ohne"
    if z["art"] == "beantragt":
        return "vorlaeufig"
    return {"rot": "rueckstand", "gelb": "offen"}.get(z["ampel"], "plan")


def _balken(z: dict) -> dict:
    """Ein Balken je Person: Spur = Kontingent, Fuellung = Ist, Strich = Soll.

    Bei einem unbefristeten Bescheid gibt es kein Kontingent; dann reicht
    die Spur bis zum groesseren von Ist und Soll (plus Luft), damit Ist und
    Soll trotzdem gegeneinander stehen.
    """
    basis = z["gesamt"] or max(z["ist"], z["soll"], 1) * 1.15
    def anteil(wert):
        return round(min(wert / basis * 100, 100), 1) if basis else 0
    return {"ist": anteil(z["ist"]), "soll": anteil(z["soll"]),
            "befristet": bool(z["gesamt"])}


def _verlauf(z: dict) -> dict:
    """Soll und Ist aufsummiert als zwei Linien (Detailansicht).

    Gerechnet in einem Feld 0..100 x 0..40; gezeichnet wird mit
    preserveAspectRatio="none" und vector-effect, damit die Linien in
    jeder Breite gleich dick bleiben.
    """
    monate = z["monate"]
    hoechst = max([m["soll_kum"] for m in monate]
                  + [m.get("ist_kum", 0) for m in monate] + [1])
    schritt = 100 / max(len(monate) - 1, 1)
    def y(wert):
        return round(40 - wert / hoechst * 36, 2)
    soll = " ".join(f"{round(i * schritt, 2)},{y(m['soll_kum'])}"
                    for i, m in enumerate(monate))
    ist = " ".join(f"{round(i * schritt, 2)},{y(m['ist_kum'])}"
                   for i, m in enumerate(monate) if "ist_kum" in m)
    heute_x = next((round(i * schritt, 2) for i, m in enumerate(monate)
                    if m["laufend"]), None)
    return {"soll": soll, "ist": ist, "heute": heute_x}


def monatsdiagramm(bloecke: list[dict]) -> dict | None:
    """Saeulen je Monat fuer die Kachel „Monate“ (seit 2.1).

    Reines HTML/CSS: je Monat eine Spalte mit dem Soll als Umriss und dem
    Ist als Fuellung, Hoehen in Prozent einer gemeinsamen Skala. Keine
    Diagrammbibliothek (Abschnitt 13). Die Skala endet auf einer runden
    Stundenzahl, damit die Hilfslinien glatte Werte tragen.
    """
    if not bloecke:
        return None
    hoechst = max(max(b["ist"], b["soll"] or 0) for b in bloecke) / 60
    if hoechst <= 0:
        return None
    for schritt in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
        if hoechst / schritt <= 4:
            break
    oben = schritt * (int(hoechst // schritt) + 1)
    linien = [{"wert": w, "pos": round(w / oben * 100, 2)}
              for w in range(0, oben + 1, schritt)]
    jetzt = dt.date.today().strftime("%Y-%m")
    saeulen = []
    for b in bloecke:
        saeulen.append({
            "zeit": ("kuenftig" if b["monat"] > jetzt else
                     "laufend" if b["monat"] == jetzt else "vorbei"),
            **b,
            "kurz": f"{MONATSKURZ[int(b['monat'][5:7])]} {b['monat'][2:4]}",
            "h_ist": round(b["ist"] / 60 / oben * 100, 2),
            "h_soll": round((b["soll"] or 0) / 60 / oben * 100, 2),
            "lage": ("ohne" if not b["soll"] else
                     "voll" if b["ist"] >= b["soll"] else
                     "knapp" if b["prozent"] < 90 else "nah"),
        })
    # ⚠️ Stärkster und schwächster Monat nur unter den ABGESCHLOSSENEN:
    # ein künftiger Monat stuende sonst mit 0 % als „schwächster“ da, und
    # der laufende ist noch nicht vorbei (gemessen am Kalenderjahr 2026).
    mit_soll = [b for b in bloecke if b["soll"] and b["monat"] < jetzt]
    return {
        "saeulen": saeulen, "linien": linien,
        "staerkster": max(mit_soll, key=lambda b: b["prozent"]) if mit_soll else None,
        "schwaechster": min(mit_soll, key=lambda b: b["prozent"]) if mit_soll else None,
    }


MONATSKURZ = ("", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug",
              "Sep", "Okt", "Nov", "Dez")


def stand_der_bewilligungen(con, heute: str | None = None) -> dict:
    """Die Karte "Stand der Bewilligungen" (seit 2.1).

    ⚠️ Bewusst UNABHAENGIG vom Filter der Seite: die Frage ist "wie steht
    jede Person heute gegen ihren laufenden Bescheid", und die hat genau
    eine Antwort. Ein Mitarbeiterfilter etwa liesse das Ist schrumpfen und
    jede Person im Rueckstand aussehen.

    Alle AKTIVEN Personen, auch ohne erfasste Zeiten (dann sieht man genau
    den Rueckstand, um den es geht). Sortiert nach Dringlichkeit:
    rot, orange (beantragt), gelb, gruen, Selbstzahler - darin nach Namen.
    """
    heute = heute or dt.date.today().isoformat()
    personen = con.execute(
        "SELECT id, name, selbstzahler FROM person WHERE aktiv=1").fetchall()
    zeitraeume = zeitraeume_lesen(con)
    # ⚠️ Zugeordnet ueber parser.norm() und nicht ueber den exakten Namen:
    # Schreibweisen aus Fremdexporten weichen ab (Abschnitt 4).
    ist: dict[str, dict[str, int]] = {}
    for r in con.execute(
            "SELECT klient, monat, SUM(dauer_min) m FROM eintrag "
            "WHERE datum <= ? GROUP BY klient, monat", (heute,)):
        je = ist.setdefault(norm(r["klient"]), {})
        je[r["monat"]] = je.get(r["monat"], 0) + (r["m"] or 0)

    zeilen = []
    for p in personen:
        stand = bewilligungsstand(zeitraeume.get(p["name"], []),
                                  ist.get(norm(p["name"]), {}), heute,
                                  selbstzahler=bool(p["selbstzahler"]))
        zeile = {"id": p["id"], "name": p["name"], **stand}
        zeile["abschnitt"] = _abschnitt(zeile)
        if zeile.get("monate"):
            zeile["balken"] = _balken(zeile)
            zeile["verlauf"] = _verlauf(zeile)
        zeilen.append(zeile)
    zeilen.sort(key=lambda z: (STAND_GRUPPEN.index(z["gruppe"]),
                               z["name"].casefold()))
    # Abschnitte in fester Reihenfolge, leere fallen weg. Innerhalb eines
    # Abschnitts bleibt die Sortierung von oben (Dringlichkeit, Name).
    abschnitte = []
    for schluessel, titel in STAND_ABSCHNITTE:
        teil = [z for z in zeilen if z["abschnitt"] == schluessel]
        if teil:
            abschnitte.append({"schluessel": schluessel, "titel": titel,
                               "zeilen": teil})

    gerechnet = [z for z in zeilen if z["art"] in ("laufend", "beantragt")]
    befristet = [z for z in gerechnet if z["gesamt"]]
    soll = sum(z["soll"] for z in gerechnet)
    ist_summe = sum(z["ist"] for z in gerechnet)
    gesamt = sum(z["gesamt"] for z in befristet)
    ist_befristet = sum(z["ist"] for z in befristet)
    return {
        "heute": heute,
        "zeilen": zeilen,
        "abschnitte": abschnitte,
        "summe": {
            "ist": ist_summe, "soll": soll, "abweichung": ist_summe - soll,
            "personen": len(gerechnet),
            "rot": sum(1 for z in gerechnet if z["ampel"] == "rot"),
            "gelb": sum(1 for z in gerechnet if z["ampel"] == "gelb"),
            "gesamt": gesamt,
            "prozent": round(ist_befristet / gesamt * 100) if gesamt else None,
            "ohne": sum(1 for z in zeilen
                        if z["art"] in ("fehlt", "kuenftig", "abgelaufen")),
        },
    }


@router.get("/auswertung", response_class=HTMLResponse)
def auswertung(request: Request, von_jahr: str = "", von_monat: str = "",
               bis_jahr: str = "", bis_monat: str = "",
               mitarbeiter: list[str] = Query([]),
               klient: list[str] = Query([]), q: str = "",
               nur_abrechenbar: str = ""):
    # ⚠️ Ohne jede Angabe steht das LAUFENDE JAHR da, nicht die gesamte
    # Zeit. Bei vierzehn Monatsblöcken war die Seite sonst schon beim
    # Aufschlagen unlesbar lang.
    #
    # Erkannt wird das an der leeren Abfrage, nicht an leeren Feldern:
    # das Filterformular schickt immer alle Felder mit, auch die leeren.
    # Wer dort ausdrücklich „alle" wählt, bekommt damit weiterhin alles -
    # sonst gäbe es keinen Weg mehr zur Gesamtansicht.
    if not request.query_params:
        von_jahr = bis_jahr = str(dt.date.today().year)

    filter_ = bereichsfilter(von_jahr, von_monat, bis_jahr, bis_monat,
                             mitarbeiter, klient, q, nur_abrechenbar=nur_abrechenbar)

    with db.db() as con:
        roh = con.execute(
            f"SELECT klient, COUNT(*) n, SUM(dauer_min) m, "
            f"COUNT(DISTINCT mitarbeiter) anzahl_leute, "
            f"GROUP_CONCAT(DISTINCT mitarbeiter) leute "
            f"FROM eintrag WHERE {filter_['wo']} GROUP BY klient ORDER BY klient",
            filter_["werte"]).fetchall()
        # Zusaetzlich monatsweise: Wochenstunden und Stundensatz koennen sich
        # innerhalb des Auswertungszeitraums geaendert haben, der Verdienst
        # muss deshalb Monat fuer Monat gerechnet werden. Dieselben Zahlen
        # tragen weiter unten die Monatsbloecke.
        je_monat: dict[str, dict[str, dict]] = {}
        for r in con.execute(
                f"SELECT klient, monat, COUNT(*) n, SUM(dauer_min) m, "
                f"GROUP_CONCAT(DISTINCT mitarbeiter) leute FROM eintrag "
                f"WHERE {filter_['wo']} GROUP BY klient, monat",
                filter_["werte"]):
            je_monat.setdefault(r["klient"], {})[r["monat"]] = {
                "n": r["n"], "m": r["m"] or 0, "leute": r["leute"] or ""}
        stamm = {r["name"]: r for r in con.execute(
            "SELECT name, wochenstunden, stundensatz, selbstzahler "
            "FROM person WHERE aktiv=1")}
        stand = stand_der_bewilligungen(con)
        zeitraeume = zeitraeume_lesen(con)
        # Welche Monate deckt die Auswahl tatsächlich ab? Grundlage für das Soll.
        vorhandene = [r["monat"] for r in con.execute(
            f"SELECT DISTINCT monat FROM eintrag WHERE {filter_['wo']} ORDER BY monat",
            filter_["werte"])]

    if filter_["von"] and filter_["bis"]:
        # Fest umrissener Zeitraum: auch Monate ohne Daten zählen zum Soll
        monate = monatsliste(filter_["von"], filter_["bis"])
    else:
        # Offener oder monatsweiser Filter: nur die Monate, in denen etwas steht
        monate = vorhandene or [dt.date.today().strftime("%Y-%m")]

    # Bis 1.4 standen dieselben Personen in drei Boxen nebeneinander:
    # Stundentabelle, Kontingentbalken, Verdienstliste. Das erzeugte drei
    # verschieden hohe Kaesten und damit die Luecken im Raster - und man
    # musste dreimal denselben Namen suchen. Jetzt traegt eine Zeile
    # alles, was zu einer Person zu sagen ist.
    je_klient, verdienst_gesamt = [], 0.0
    gestaffelt = False
    for r in roh:
        namen = sorted({t.strip() for t in (r["leute"] or "").split(",") if t.strip()})
        p = stamm.get(r["klient"])
        zr = zeitraeume.get(r["klient"], [])
        grund_std = p["wochenstunden"] if p else 0
        grund_satz = p["stundensatz"] if p else 0
        # Nur fuer einen Selbstzahler zaehlen die Grundwerte ueberhaupt -
        # siehe kontingent_im_monat().
        selbst = bool(p["selbstzahler"]) if p else False

        # Soll: Monat fuer Monat mit den Werten, die in diesem Monat galten.
        # Fuer die Anzeige wird zusaetzlich festgehalten, welche
        # Wochenstunden und Saetze dabei ueberhaupt vorkamen - stehen dort
        # zwei verschiedene, waere eine einzelne Zahl in der Spalte
        # irrefuehrend.
        soll, std_stufen = 0, set()
        for monat in monate:
            std, _satz, _ = kontingent_im_monat(monat, zr, grund_std, grund_satz,
                                                selbst)
            if std:
                std_stufen.add(std)
                soll += soll_minuten(std, monat) or 0
        soll = soll or None

        # Verdienst: die Minuten JEDES Monats mit dem Satz dieses Monats.
        betrag, satz_stufen = 0.0, set()
        for monat, daten in (je_monat.get(r["klient"]) or {}).items():
            _std, satz, _ = kontingent_im_monat(monat, zr, grund_std, grund_satz,
                                                selbst)
            if satz and daten["m"]:
                satz_stufen.add(satz)
                betrag += daten["m"] / 60 * satz
        if len(std_stufen) > 1 or len(satz_stufen) > 1:
            gestaffelt = True

        # Bewusst nicht an das Soll geknuepft: mit gestaffelten Zeitraeumen
        # kann ein Monat einen Stundensatz tragen, ohne dass fuer denselben
        # Zeitraum Wochenstunden hinterlegt sind. Vorher fiel dieser
        # Verdienst stillschweigend unter den Tisch.
        verdienst_gesamt += betrag

        je_klient.append({
            "klient": r["klient"], "n": r["n"], "m": r["m"],
            "leute": namen, "anzahl_leute": r["anzahl_leute"],
            "soll": soll,
            "abweichung": (r["m"] - soll) if soll else None,
            "prozent": round(r["m"] / soll * 100) if soll else None,
            "stufen": len(std_stufen),
            "betrag": betrag,
            "satz": min(satz_stufen) if len(satz_stufen) == 1 else None,
            "saetze": sorted(satz_stufen),
        })

    # --- Monat für Monat ----------------------------------------------------
    #
    # Die Boxen oben fassen den ganzen Zeitraum zusammen. Fuer einen
    # Nachweis gegenueber dem Kostentraeger braucht es aber den einzelnen
    # Monat: was wurde geleistet, was ist daraus verdient, und mit welchem
    # Satz - der kann sich mitten im Zeitraum geaendert haben.
    #
    # Bewusst chronologisch aufsteigend: so liest sich der Block wie ein
    # Nachweis und nicht wie ein Postfach.
    #
    # Monate ohne erfasste Zeiten bleiben stehen, solange fuer sie ein Soll
    # gilt. Genau die will man sehen - eine Luecke faellt sonst nicht auf.
    monatsbloecke = []
    for monat in monate:
        zeilen, m_ist, m_soll, m_betrag, m_n = [], 0, 0, 0.0, 0
        for r in roh:
            klient = r["klient"]
            p = stamm.get(klient)
            zr = zeitraeume.get(klient, [])
            std, satz, aus_zeitraum = kontingent_im_monat(
                monat, zr, p["wochenstunden"] if p else 0,
                p["stundensatz"] if p else 0,
                bool(p["selbstzahler"]) if p else False)
            daten = (je_monat.get(klient) or {}).get(monat)
            ist = daten["m"] if daten else 0
            anzahl = daten["n"] if daten else 0
            soll = soll_minuten(std, monat) or 0
            if not ist and not soll:
                # Weder gearbeitet noch beauftragt - diese Zeile traegt nichts.
                continue
            zeilenbetrag = ist / 60 * satz if (satz and ist) else 0.0
            leute = sorted({t.strip() for t in (daten["leute"] if daten else "").split(",")
                            if t.strip()})
            zeilen.append({
                "klient": klient, "n": anzahl, "m": ist, "soll": soll or None,
                "abweichung": (ist - soll) if soll else None,
                "satz": satz, "wochenstunden": std,
                "aus_zeitraum": aus_zeitraum,
                "betrag": zeilenbetrag, "leute": leute,
            })
            m_ist += ist
            m_soll += soll
            m_betrag += zeilenbetrag
            m_n += anzahl
        if not zeilen:
            continue
        monatsbloecke.append({
            "monat": monat, "wort": monat_wort(monat), "zeilen": zeilen,
            "ist": m_ist, "soll": m_soll or None, "betrag": m_betrag, "n": m_n,
            "abweichung": (m_ist - m_soll) if m_soll else None,
            "prozent": round(m_ist / m_soll * 100) if m_soll else None,
            "leer": m_ist == 0,
        })

    gesamt_ist = sum(r["m"] for r in je_klient)
    gesamt_soll = sum(b["soll"] or 0 for b in monatsbloecke)
    zusammenfassung = {
        "ist": gesamt_ist,
        "soll": gesamt_soll or None,
        "abweichung": (gesamt_ist - gesamt_soll) if gesamt_soll else None,
        "prozent": round(gesamt_ist / gesamt_soll * 100) if gesamt_soll else None,
        "betrag": verdienst_gesamt,
        "n": sum(r["n"] for r in je_klient),
        "monate": len(monate),
        "monate_mit": sum(1 for b in monatsbloecke if not b["leer"]),
        "personen": len(je_klient),
    }

    zusatz = auswahllisten()
    return _u["templates"].TemplateResponse(request=request, name="auswertung.html", context={
        "je_klient": je_klient, "verdienst_gesamt": verdienst_gesamt,
        "monate_anzahl": len(monate),
        "gesamt": sum(r["m"] for r in je_klient),
        "soll_aktiv": any(r["soll"] for r in je_klient),
        "gestaffelt": gestaffelt,
        "monatsbloecke": monatsbloecke, "zusammenfassung": zusammenfassung,
        "stand": stand, "diagramm": monatsdiagramm(monatsbloecke),
        "zeitraum_wort": filter_["wort"], "aktive_filter": filter_["aktive"],
        "f": filter_["f"], "seite": "auswertung", **zusatz})
