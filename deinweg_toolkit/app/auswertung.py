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
from .rechnen import (auswahllisten, bereichsfilter, kontingent_im_monat,
                      monat_wort, monatsgrenzen, monatsliste, soll_minuten,
                      zeitraeume_lesen)

router = APIRouter()

# von setup() gefuellt - dieses Modul braucht nur die Templates
_u: dict = {}


def setup(templates, umgebung=None) -> None:
    _u["templates"] = templates
    _u.update(umgebung or {})


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
    # Zwei verschiedene Dinge, die beide "kein Zeitraum" heissen: beim
    # Selbstzahler ist das der Normalfall (er braucht keinen Bescheid),
    # beim Kostentraeger-Fall ist es eine Luecke - dort wurde gearbeitet,
    # ohne dass etwas bewilligt war. Seit 1.20 werden sie getrennt
    # gezaehlt und in der Seitenspalte verschieden benannt; vorher lief
    # beides unter "Grundwert" und sah damit gleich harmlos aus.
    selbst_monate: dict[str, int] = {}
    ohne_bescheid_monate: dict[str, int] = {}
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
            if not aus_zeitraum:
                if p and p["selbstzahler"]:
                    selbst_monate[klient] = selbst_monate.get(klient, 0) + 1
                elif ist:
                    # Gearbeitet, aber nichts bewilligt. Genau die Monate
                    # muessen in der Seitenspalte auffallen - in der
                    # Tabelle stehen sie nur als drei Striche da.
                    ohne_bescheid_monate[klient] = (
                        ohne_bescheid_monate.get(klient, 0) + 1)
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

    # --- Welche Bescheide liegen dem Ganzen zugrunde? -----------------------
    # Steht in der Seitenspalte und beantwortet die Frage, die beim Lesen
    # der Zahlen als naechstes kommt: woher kommt dieser Stundensatz?
    # Nur die Zeitraeume, die den gefilterten Bereich ueberhaupt beruehren.
    filterbeginn = monatsgrenzen(monate[0])[0] if monate else ""
    filterende = monatsgrenzen(monate[-1])[1] if monate else ""
    zeitraum_liste = []
    for r in je_klient:
        treffer = [z for z in zeitraeume.get(r["klient"], [])
                   if z["von"] <= filterende
                   and (not z["bis"] or z["bis"] >= filterbeginn)]
        selbst = selbst_monate.get(r["klient"], 0)
        offen = ohne_bescheid_monate.get(r["klient"], 0)
        p_stamm = stamm.get(r["klient"])
        selbstzahler = bool(p_stamm["selbstzahler"]) if p_stamm else False
        if treffer or selbst or offen:
            zeitraum_liste.append({
                "klient": r["klient"],
                # aufsteigend lesen, so wie die Bescheide aufeinander folgen
                "zeitraeume": list(reversed(treffer)),
                "selbst_monate": selbst,
                "ohne_bescheid": offen,
                "selbstzahler": selbstzahler,
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
        "zeitraum_liste": zeitraum_liste,
        "zeitraum_wort": filter_["wort"], "aktive_filter": filter_["aktive"],
        "f": filter_["f"], "seite": "auswertung", **zusatz})
