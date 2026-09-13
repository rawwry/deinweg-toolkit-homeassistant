"""Mein Bereich - die eigenen Zahlen jeder angemeldeten Person.

Seit 1.32 ein eigenes Modul, sonst unveraendert. Bewusst an KEINE
Bereichsberechtigung geknuepft: es sind die eigenen Daten, die darf
jeder sehen. Wer keinem Mitarbeiter zugeordnet ist, bekommt stattdessen
eine Erklaerung.

Hier liegt auch die kleine Selbstbedienung fuer das eigene Konto
(POST /meinbereich/konto): eigenes Passwort, eigene E-Mail-Adresse,
sonst nichts. Rolle, Bereiche und die Zuordnung zu einem Mitarbeiter
bleiben Sache der Administration - sonst koennte sich jeder selbst
hochstufen.

⚠️ Die drei Routen /meinbereich/eintrag/... stehen NICHT hier, sondern
weiterhin in main.py: es sind dieselben Funktionen wie unter
/eintraege/..., nur mit einem zweiten Decorator darueber. Sie zu
trennen hiesse, dieselbe Pruefung zweimal zu pflegen.
"""

from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth
from . import db
from .parser import hhmm
from .rechnen import (ABWESEND_SQL, ARBEITSTAGE_MONAT, MONATSNAMEN,
                      abwesenheitstage,
                      bewilligungen_pruefen, mitarbeiter_zu_benutzer,
                      monat_wort, soll_mit_abwesenheit, urlaubstage_zaehlen)

router = APIRouter()

# von setup() gefuellt: Templates und spruch() aus main.py
_u: dict = {}


def setup(templates, umgebung=None) -> None:
    _u["templates"] = templates
    _u.update(umgebung or {})


def _spruch(benutzer) -> dict:
    """Der Spruch - oder nichts, wenn dieses Konto ihn abgestellt hat.

    Die Vorlage prueft `spruch.text`; ein leeres Dict laesst den ganzen
    Zitatblock weg statt ihn leer stehen zu lassen.
    """
    if not auth.zeigt_sprueche(benutzer):
        return {}
    return _u["spruch"]()


# --- Persönlicher Bereich -----------------------------------------------------
#
# Jede angemeldete Person sieht hier ausschliesslich die eigenen Zahlen.
# Bewusst nicht an eine Bereichsberechtigung geknuepft: es sind die eigenen
# Daten, die darf jeder sehen. Wer keinem Mitarbeiter zugeordnet ist, bekommt
# stattdessen eine Erklaerung.

# Wieviele eigene Zeiten "Mein Bereich" hoechstens auf einmal zeigt, wenn
# kein Monat gewaehlt ist. Die Liste ist zum Nachbessern gedacht, nicht als
# zweite Uebersicht - wer weiter zurueck will, waehlt den Monat.
MEINE_ZEITEN_MAX = 300


@router.get("/meinbereich", response_class=HTMLResponse)
def meinbereich(request: Request, alle: str = "", hinweis: str = "",
                fehler: str = "", zeiten: str = "", pw: str = ""):
    benutzer = request.state.benutzer
    with db.db() as con:
        person = mitarbeiter_zu_benutzer(con, benutzer)
        if not person:
            # Auch ohne Mitarbeiterzuordnung: der Hinweis auf fehlende
            # Bewilligungen gilt dem Team, nicht der einzelnen Person.
            return _u["templates"].TemplateResponse(
                request=request, name="meinbereich.html",
                context={"seite": "meinbereich", "person": None,
                         "monate": [], "benutzer": benutzer,
                         "spruch": _spruch(benutzer), "eigene_aufgaben": [],
                         "passwort_offen": bool(pw),
                         "bewilligungen": [
                             b for b in (bewilligungen_pruefen(con)
                                         if auth.darf_bewilligungen_sehen(benutzer)
                                         else [])
                             if b["art"] != "grundwert"],
                         "bewilligungen_grundwert": [
                             b for b in (bewilligungen_pruefen(con)
                                         if auth.darf_bewilligungen_sehen(benutzer)
                                         else [])
                             if b["art"] == "grundwert"],
                         "hinweis": hinweis, "fehler": fehler})

        name = person["name"]
        soll_std = float(person["monatsstunden"] or 0)
        # ⚠️⚠️ Urlaub und Krankmeldung zaehlen seit 1.37 NICHT mehr als
        # geleistete Zeit - dafuer senken sie das Soll (siehe unten). Nur
        # beides zusammen ergibt ein stimmiges Bild: wer eine Woche krank
        # war, hat in dieser Woche weder gearbeitet noch etwas
        # schuldig bleiben koennen. Wuerde man nur das Soll senken, aber
        # eine mit acht Stunden gebuchte Urlaubszeile weiter als Ist
        # zaehlen, stuende der Monat ploetzlich im PLUS.
        zeilen = con.execute(
            "SELECT monat, COUNT(*) n, COALESCE(SUM(dauer_min),0) m "
            f"FROM eintrag WHERE mitarbeiter=? AND NOT {ABWESEND_SQL} "
            "GROUP BY monat ORDER BY monat",
            (name,)).fetchall()
        # Die freien Tage je Monat. Dieselbe Vorauswahl wie beim Urlaub -
        # entschieden wird in Python (abwesenheitswert), weil ein halber
        # Tag 0,5 traegt und SQLite das nicht unterscheiden kann.
        frei_je_monat = abwesenheitstage(con.execute(
            f"SELECT datum, beschreibung FROM eintrag WHERE mitarbeiter=? "
            f"AND {ABWESEND_SQL}", (name,)).fetchall())
        offene_vorgaenge = con.execute(
            "SELECT COUNT(*) c FROM vorgang WHERE LOWER(TRIM(zustaendig))=LOWER(?) "
            "AND status <> 'Erledigt'", (name,)).fetchone()["c"]
        ueberfaellig = con.execute(
            "SELECT COUNT(*) c FROM vorgang WHERE LOWER(TRIM(zustaendig))=LOWER(?) "
            "AND status <> 'Erledigt' AND frist <> '' "
            "AND frist < ?", (name, dt.date.today().isoformat())).fetchone()["c"]
        # Nicht nur zaehlen, sondern zeigen: die naechsten eigenen
        # Aufgaben stehen mit Titel, betreuter Person und Frist da.
        # Fristlose ganz nach hinten - sonst stuenden sie vor allem, was
        # wirklich draengt.
        eigene_aufgaben = con.execute(
            "SELECT id, titel, klient, art, status, prioritaet, frist "
            "FROM vorgang WHERE LOWER(TRIM(zustaendig))=LOWER(?) "
            "AND status <> 'Erledigt' "
            "ORDER BY CASE WHEN frist IS NULL OR frist='' THEN 1 ELSE 0 END, "
            "frist, id LIMIT 6", (name,)).fetchall()

        # Urlaub. ⚠️ Gezaehlt wird in Python (urlaubstage_zaehlen), nicht
        # in SQL: ein halber Tag traegt 0.5, und SQLites LIKE vergleicht
        # nur bei ASCII ohne Ruecksicht auf Gross-/Kleinschreibung. Die
        # Vorauswahl per LIKE bleibt trotzdem stehen - sie holt nur die
        # wenigen Urlaubszeilen aus der Datenbank statt aller Eintraege.
        urlaubsjahre = urlaubstage_zaehlen(con.execute(
            "SELECT datum, beschreibung FROM eintrag "
            "WHERE mitarbeiter=? AND beschreibung LIKE 'Urlaub%'",
            (name,)).fetchall())

        # Die eigenen Zeiten. Bewusst ohne jede Bereichspruefung: sie
        # gehoeren dem angemeldeten Konto, und "Mein Bereich" ist die eine
        # Seite, die jeder sehen darf. Der Monatsfilter ist nur Bequem-
        # lichkeit - "alle" zeigt alles, gedeckelt auf MEINE_ZEITEN_MAX.
        # Fehlende und auslaufende Bewilligungen - dieselbe Rechnung wie
        # in den Einstellungen (main.bewilligungslage). Steht hier, weil
        # "Mein Bereich" die Seite ist, die jeder taeglich sieht: ein
        # Folgeantrag faellt sonst erst auf, wenn der Bescheid weg ist.
        alle_lagen = (bewilligungen_pruefen(con)
                      if auth.darf_bewilligungen_sehen(benutzer) else [])

        zeitmonate = [r["monat"] for r in con.execute(
            "SELECT DISTINCT monat FROM eintrag WHERE mitarbeiter=? "
            "ORDER BY monat DESC", (name,))]
        if zeiten == "alle":
            gewaehlter_monat = "alle"
        elif zeiten in zeitmonate:
            gewaehlter_monat = zeiten
        else:
            gewaehlter_monat = zeitmonate[0] if zeitmonate else "alle"
        if gewaehlter_monat == "alle":
            eigene_zeiten = con.execute(
                "SELECT * FROM eintrag WHERE mitarbeiter=? "
                "ORDER BY datum DESC, start DESC, id DESC LIMIT ?",
                (name, MEINE_ZEITEN_MAX + 1)).fetchall()
        else:
            eigene_zeiten = con.execute(
                "SELECT * FROM eintrag WHERE mitarbeiter=? AND monat=? "
                "ORDER BY datum DESC, start DESC, id DESC",
                (name, gewaehlter_monat)).fetchall()
        zeiten_gekappt = len(eigene_zeiten) > MEINE_ZEITEN_MAX
        eigene_zeiten = list(eigene_zeiten[:MEINE_ZEITEN_MAX])
        zeiten_summe = sum(z["dauer_min"] or 0 for z in eigene_zeiten)
        # Fuer den Balken hinter der Dauer: laengste Einheit der Liste als
        # Bezugsgroesse. Zwanzig HH:MM-Werte untereinander sagen nicht, was
        # lang und was kurz war - ein Balken schon.
        zeiten_laengste = max((z["dauer_min"] or 0 for z in eigene_zeiten),
                              default=0)

    ist_je_monat = {r["monat"]: {"m": r["m"], "n": r["n"]} for r in zeilen}
    dieser_monat = dt.date.today().strftime("%Y-%m")

    # Von der ersten erfassten Zeit bis heute jeden Monat auffuellen, damit
    # ein Monat ohne Eintraege sichtbar als Luecke erscheint statt zu fehlen.
    monate = []
    if ist_je_monat:
        start = min(ist_je_monat)
        lauf = dt.date(int(start[:4]), int(start[5:7]), 1)
        ende = dt.date.today().replace(day=1)
        while lauf <= ende:
            schluessel = lauf.strftime("%Y-%m")
            daten = ist_je_monat.get(schluessel, {"m": 0, "n": 0})
            voll = int(round(soll_std * 60))
            frei = frei_je_monat.get(schluessel, 0.0)
            soll_min = soll_mit_abwesenheit(voll, frei)
            monate.append({
                "monat": schluessel,
                "wort": monat_wort(schluessel),
                "ist": daten["m"],
                "n": daten["n"],
                "soll": soll_min,
                # Beide Zahlen mitgeben, nicht nur die gesenkte: ein Soll,
                # das ohne Erklaerung von 160 auf 123 faellt, sieht wie ein
                # Fehler aus. Die Vorlage schreibt es dazu.
                "soll_voll": voll,
                "frei": frei,
                "saldo": daten["m"] - soll_min if soll_min else 0,
                "laufend": schluessel == dieser_monat,
            })
            lauf = (lauf + dt.timedelta(days=32)).replace(day=1)
        monate.reverse()

    # Der laufende Monat ist noch nicht vorbei - er wuerde den Saldo
    # kuenstlich ins Minus ziehen und wird deshalb getrennt ausgewiesen.
    abgeschlossen = [m for m in monate if not m["laufend"]]
    gesamt = {
        "ist": sum(m["ist"] for m in abgeschlossen),
        "soll": sum(m["soll"] for m in abgeschlossen),
        "monate": len(abgeschlossen),
    }
    gesamt["saldo"] = gesamt["ist"] - gesamt["soll"]
    laufend = next((m for m in monate if m["laufend"]), None)

    # Der zuletzt abgeschlossene Monat und der Schnitt der letzten drei -
    # daraus laesst sich ablesen, ob man gerade regelmaessig ueber oder
    # unter dem Soll liegt. Ein ueber Jahre aufsummierter Gesamtsaldo waere
    # dagegen kaum interpretierbar.
    letzter = abgeschlossen[0] if abgeschlossen else None
    dreimonate = abgeschlossen[:3]
    trend = None
    if dreimonate and soll_std:
        schnitt_ist = sum(m["ist"] for m in dreimonate) / len(dreimonate)
        schnitt_soll = sum(m["soll"] for m in dreimonate) / len(dreimonate)
        trend = {
            "monate": len(dreimonate),
            "schnitt": int(round(schnitt_ist)),
            "saldo": int(round(schnitt_ist - schnitt_soll)),
            "reihe": list(reversed(dreimonate)),
        }

    if not alle:
        monate = monate[:13]

    # --- Diagrammdaten ------------------------------------------------------
    # Bewusst als fertig gerechnetes SVG statt einer Diagramm-Bibliothek:
    # das Projekt laedt keine externen Skripte, und ein Balkendiagramm
    # braucht keine.
    letzte = list(reversed(monate[:12]))  # chronologisch, aelteste links
    diagramm = None
    if letzte:
        # ⚠️⚠️ Das Seitenverhaeltnis ist der ganze Punkt (seit 1.39).
        # Bis 1.38 stand hier 460x220 - also 2,09:1. Das SVG waechst auf
        # die volle Kartenbreite, und bei 965px Breite wurde es dadurch
        # **462px hoch**: ein Zwoelf-Monats-Balkendiagramm, das mehr
        # Platz einnahm als die Tabelle darunter, und dessen Achsenschrift
        # (9,5 Einheiten x Faktor 2,1) bei 20px ankam. Timos Wort dafuer:
        # "albern".
        # Jetzt 640x215, also 2,98:1 - zusammen mit der Zahlenspalte
        # daneben (siehe verlauf_zahlen) rund 265px hoch statt 462.
        # ⚠️ Das Verhaeltnis ist ein Kompromiss und keine freie Wahl: das
        # SVG hat EIN viewBox fuer alle Bildschirme. Noch flacher sah am
        # Schreibtisch besser aus, liess am Telefon aber nur noch rund
        # 60px Balkenflaeche uebrig - dort ist das Bild nur 289px breit.
        # ⚠️ Wer diese Zahlen anfasst, muss die Schriftgroessen im
        # Stylesheet mitziehen: sie stehen in Einheiten des viewBox und
        # werden mit der Karte mitskaliert. Bei 640 Einheiten auf rund
        # 786px liegt der Faktor bei 1,23 - eine Einheit ist also etwa
        # ein Pixel. Vorher war er 2,1, und 9,5 Einheiten Achsenschrift
        # kamen als 20px an.
        breite, hoehe = 640, 215
        # ⚠️ Die oberen 26px sind das Band fuer die Wertmarke und gehoeren
        # NICHT zur Zeichenflaeche. Bis 1.17 hing die Marke 7px ueber
        # ihrem Balken - und weil sie mit "12:30 · +2:15" gut dreimal so
        # breit ist wie ihre Spalte, ragte sie regelmaessig in die
        # Nachbarspalten hinein und lag dort mitten im Balken. Ein
        # Umrandungsstrich in der Kartenfarbe half dagegen nicht.
        # Jetzt steht sie immer in diesem Band, also ueber allem: kein
        # Balken reicht dort hinauf (die Skala hat 20% Luft nach oben),
        # und die Saldolinie auch nicht.
        marke_band = 26
        oben, unten, links, rechts = marke_band, 34, 12, 12
        # Halbe Breite der Wertmarke in Einheiten des viewBox. Sie
        # entscheidet nur darueber, ob sich die Marke am Rand an die Kante
        # haengt statt sich zu zentrieren. ⚠️ Bis 1.38 stand hier 58 - bei
        # einem Faktor von 2,1 war das die halbe Breite von
        # "12:30 · +2:15". Mit dem flacheren Bild ist eine Einheit rund
        # ein Pixel, und 58 haette die Marken an den Raendern grundlos
        # angeheftet.
        marke_halb = 40
        flaeche = hoehe - oben - unten
        grundlinie = oben + flaeche
        spalte = (breite - links - rechts) / max(len(letzte), 1)
        soll_min = int(round(soll_std * 60))
        spitze = max([m["ist"] for m in letzte] + [soll_min, 60]) * 1.2

        def hoch(minuten: float) -> float:
            """Minuten in Balkenhoehe."""
            return flaeche * (minuten / spitze)

        balken, saldopunkte, summe = [], [], 0
        for i, m in enumerate(letzte):
            b = spalte * 0.54
            x = links + i * spalte + (spalte - b) / 2
            h_ist = hoch(m["ist"])

            # Der Balken zerfaellt in bis zu zwei Stuecke. Das ist der
            # eigentliche Punkt dieser Darstellung: nicht "wie viel war
            # es", sondern "wie viel fehlt oder ist zu viel" - und das
            # sieht man nur, wenn der Unterschied selbst eine Flaeche
            # bekommt. Ein einzelner Balken neben einer Soll-Linie laesst
            # einen die Differenz schaetzen.
            h_ueber = h_fehlt = 0.0
            # ⚠️ Gerechnet wird gegen das Soll DIESES Monats, nicht gegen
            # das volle Monatssoll (seit 1.37): ein Monat mit zwei Wochen
            # Urlaub hat ein kleineres Soll, und der gestrichelte Umriss
            # muesste sonst eine Luecke zeigen, die es nicht gibt. Die
            # waagerechte Soll-Linie im Bild bleibt dagegen beim vollen
            # Wert - sie ist der vereinbarte Massstab, und eine Treppe
            # waere dort nicht mehr als Bezugsgroesse zu lesen.
            monatssoll = m["soll"]
            if monatssoll and not m["laufend"]:
                if m["ist"] >= monatssoll:
                    h_basis = hoch(monatssoll)
                    h_ueber = h_ist - h_basis
                    klasse = "saeule-gut"
                else:
                    h_basis = h_ist
                    h_fehlt = hoch(monatssoll) - h_ist
                    klasse = "saeule-unter"
            else:
                h_basis = h_ist
                klasse = "saeule-laufend" if m["laufend"] else "saeule-neutral"

            y_basis = grundlinie - max(h_basis, 2)
            saldo = m["saldo"] if monatssoll and not m["laufend"] else None
            balken.append({
                "x": round(x, 1), "b": round(b, 1),
                "mitte": round(x + b / 2, 1),
                "y_basis": round(y_basis, 1),
                "h_basis": round(max(h_basis, 2), 1),
                "y_ueber": round(y_basis - h_ueber, 1),
                "h_ueber": round(h_ueber, 1) if h_ueber > 0.6 else 0,
                "y_fehlt": round(y_basis - h_fehlt, 1),
                "h_fehlt": round(h_fehlt, 1) if h_fehlt > 0.6 else 0,
                # Die Wertmarke ist breiter als ihre Spalte. Am Rand wuerde
                # sie deshalb abgeschnitten - dort haengt sie sich an die
                # Kante statt sich zu zentrieren.
                # ⚠️ Die Hoehe ist fest: sie steht im Band ueber der
                # Zeichenflaeche, nicht ueber ihrem Balken. Siehe oben.
                "label_y": marke_band - 9,
                "label_x": round(
                    links if x + b / 2 - marke_halb < links else
                    breite - rechts if x + b / 2 + marke_halb > breite - rechts
                    else x + b / 2, 1),
                "label_anker": (
                    "start" if x + b / 2 - marke_halb < links else
                    "end" if x + b / 2 + marke_halb > breite - rechts
                    else "middle"),
                "takt": round(i * 0.055, 3),
                "kurz": MONATSNAMEN.get(m["monat"][5:7], "")[:3],
                "jahr": m["monat"][:4],
                "wert": hhmm(m["ist"]),
                "wort": m["wort"],
                "laufend": m["laufend"],
                "saldo_wort": (("+" if saldo > 0 else "−" if saldo < 0 else "±")
                               + hhmm(abs(saldo))) if saldo is not None else None,
                "klasse": klasse,
            })
            if monatssoll and not m["laufend"]:
                summe += m["saldo"]
                saldopunkte.append({"x": round(x + b / 2, 1), "saldo": summe,
                                    "wort": hhmm(abs(summe)),
                                    "plus": summe >= 0})

        # Der Saldoverlauf bekommt eine eigene Skala, sonst waere er neben
        # den Monatsbalken kaum zu erkennen.
        linie, punkte, linienlaenge = "", [], 0
        if len(saldopunkte) > 1:
            grenze = max(abs(p["saldo"]) for p in saldopunkte) or 1
            mitte = oben + flaeche / 2
            teile, vorher = [], None
            for p in saldopunkte:
                y = round(mitte - (p["saldo"] / grenze) * (flaeche / 2 * 0.78), 1)
                teile.append(f"{p['x']},{y}")
                if vorher:
                    linienlaenge += ((p["x"] - vorher[0]) ** 2
                                     + (y - vorher[1]) ** 2) ** 0.5
                vorher = (p["x"], y)
                punkte.append({"x": p["x"], "y": y, "wort": p["wort"],
                               "plus": p["plus"]})
            linie = " ".join(teile)

        diagramm = {
            "breite": breite, "hoehe": hoehe, "oben": oben, "links": links,
            "flaeche": flaeche, "grundlinie": grundlinie,
            "balken": balken, "linie": linie, "punkte": punkte,
            # ⚠️ Die Laenge wird hier gerechnet, damit die Linie sich per
            # stroke-dashoffset einzeichnen kann. Im Browser ginge das nur
            # ueber getTotalLength() - also mit Skript, und das laedt die
            # Anwendung bewusst nicht (Abschnitt 13).
            "linienlaenge": round(linienlaenge + 4, 1),
            "raster": [round(grundlinie - flaeche * a, 1)
                       for a in (0.25, 0.5, 0.75)],
            "soll_y": round(grundlinie - hoch(soll_min), 1) if soll_min else None,
            "soll_wert": hhmm(soll_min) if soll_min else None,
            "rechts_x": breite - rechts,
            "mittellinie": round(oben + flaeche / 2, 1),
        }

    # --- Die Zahlen neben dem Diagramm --------------------------------------
    # ⚠️ Sie sind die Gegenleistung dafuer, dass das Bild seit 1.39
    # deutlich flacher ist (siehe oben): der Platz, der rechts davon frei
    # wird, traegt jetzt die vier Auskuenfte, nach denen man beim
    # Betrachten einer Zeitreihe als Naechstes sucht. Gerechnet wird ueber
    # GENAU die Monate, die im Bild stehen - alles andere waere eine
    # zweite Wahrheit neben derselben Grafik.
    verlauf_zahlen = None
    gezeigt = [m for m in letzte if not m["laufend"] and m["soll"]]
    if gezeigt:
        bester = max(gezeigt, key=lambda m: m["saldo"])
        schwaechster = min(gezeigt, key=lambda m: m["saldo"])
        verlauf_zahlen = {
            "monate": len(gezeigt),
            "schnitt": int(round(sum(m["ist"] for m in gezeigt) / len(gezeigt))),
            "summe": sum(m["saldo"] for m in gezeigt),
            "bester": bester,
            "schwaechster": schwaechster,
            # Bei einem einzigen Monat waeren "bester" und "schwaechster"
            # derselbe - dann steht die Gegenueberstellung nicht da.
            "spanne": len(gezeigt) > 1,
        }

    # --- Urlaub -------------------------------------------------------------
    jahr = dt.date.today().strftime("%Y")
    anspruch = float(person["urlaubstage"] or 0)
    genommen = urlaubsjahre.get(jahr, 0)
    urlaub = {
        "jahr": jahr,
        "anspruch": anspruch,
        "genommen": genommen,
        "rest": anspruch - genommen,
        "anteil": min(100, round(genommen / anspruch * 100)) if anspruch else 0,
        "ueberzogen": bool(anspruch and genommen > anspruch),
        "vorjahre": sorted(
            ((j, t) for j, t in urlaubsjahre.items() if j != jahr),
            reverse=True)[:3],
    }

    return _u["templates"].TemplateResponse(
        request=request, name="meinbereich.html", context={
            "seite": "meinbereich", "person": person, "name": person["name"],
            "soll_std": soll_std, "monate": monate, "gesamt": gesamt,
            "laufend": laufend, "alle": bool(alle), "benutzer": benutzer,
            "hinweis": hinweis, "fehler": fehler, "passwort_offen": bool(pw),
            "diagramm": diagramm, "urlaub": urlaub,
            "verlauf_zahlen": verlauf_zahlen,
            # ⚠️ Was ein freier Tag wert ist, stand bisher nirgends auf
            # der Seite - man sah nur ein Soll, das um einen krummen
            # Betrag gefallen war. Die Zahl ist dieselbe, mit der
            # soll_mit_abwesenheit() rechnet: Monatssoll durch die
            # Pauschale von 21,65 Arbeitstagen.
            "tagessoll": (int(round(soll_std * 60 / ARBEITSTAGE_MONAT))
                          if soll_std else 0),
            "arbeitstage_monat": ARBEITSTAGE_MONAT,
            "letzter": letzter, "trend": trend,
            "offene_vorgaenge": offene_vorgaenge, "ueberfaellig": ueberfaellig,
            "eigene_aufgaben": eigene_aufgaben, "spruch": _spruch(benutzer),
            "heute": dt.date.today().isoformat(),
            "bewilligungen": [b for b in alle_lagen if b["art"] != "grundwert"],
            "bewilligungen_grundwert": [b for b in alle_lagen
                                        if b["art"] == "grundwert"],
            "eigene_zeiten": eigene_zeiten, "zeitmonate": zeitmonate,
            "zeiten_laengste": zeiten_laengste,
            "zeiten_monat": gewaehlter_monat, "zeiten_gekappt": zeiten_gekappt,
            "zeiten_summe": zeiten_summe, "zeiten_max": MEINE_ZEITEN_MAX,
            "verwaist": isinstance(person, dict) and person.get("verwaist")})



# --- Das eigene Konto ---------------------------------------------------------
#
# Die Benutzerverwaltung unter Einstellungen ist Administratoren vorbehalten
# (auth.ADMIN_NUR_PFADE). Damit ein normales Konto trotzdem sein Passwort
# wechseln kann, sitzt hier die kleine Selbstbedienung: eigene E-Mail-Adresse
# und eigenes Passwort, sonst nichts. Rolle, Bereiche und die Zuordnung zu
# einem Mitarbeiter bleiben ausdruecklich Sache der Administration - sonst
# koennte sich jeder selbst hochstufen.
#
# Der Pfad liegt unter /meinbereich und damit ausserhalb von
# ADMIN_NUR_PFADE und ausserhalb jedes Bereichs: es sind die eigenen Daten.

def _konto_zurueck(**werte):
    return RedirectResponse("/meinbereich?" + urlencode(werte), status_code=303)


@router.post("/meinbereich/konto")
def konto_speichern(request: Request, email: str = Form(""),
                    passwort_alt: str = Form(""), passwort_neu: str = Form(""),
                    passwort_neu2: str = Form("")):
    benutzer = request.state.benutzer
    email = email.strip()
    meldungen = []

    with db.db() as con:
        satz = con.execute("SELECT * FROM benutzer WHERE id=?",
                           (benutzer["id"],)).fetchone()
        if satz is None:
            return _konto_zurueck(fehler="Dieses Konto gibt es nicht mehr.")

        if passwort_neu or passwort_neu2 or passwort_alt:
            # Das aktuelle Passwort ist Pflicht. Sonst koennte jemand an
            # einem unbeaufsichtigt offenen Bildschirm das Konto uebernehmen
            # und die eigentliche Inhaberin aussperren.
            # "pw=1" haelt den zugeklappten Passwortblock offen, damit die
            # Fehlermeldung nicht ueber einem geschlossenen Block steht.
            if not db.passwort_pruefen(passwort_alt, satz["passwort_hash"]):
                return _konto_zurueck(fehler="Das aktuelle Passwort stimmt nicht.",
                                      pw="1")
            if len(passwort_neu) < 8:
                return _konto_zurueck(
                    fehler="Das neue Passwort braucht mindestens acht Zeichen.",
                    pw="1")
            if passwort_neu != passwort_neu2:
                return _konto_zurueck(
                    fehler="Die beiden neuen Passwörter sind nicht gleich.",
                    pw="1")
            con.execute("UPDATE benutzer SET passwort_hash=? WHERE id=?",
                        (db.passwort_hashen(passwort_neu), benutzer["id"]))
            # Alle anderen Sitzungen beenden. Wer das Passwort wechselt,
            # will in aller Regel genau das - die eigene bleibt bestehen.
            token = request.cookies.get(auth.COOKIE_NAME, "")
            con.execute("DELETE FROM sitzung WHERE benutzer_id=? AND token<>?",
                        (benutzer["id"], token))
            meldungen.append("Passwort geändert")

        if email != (satz["email"] or ""):
            con.execute("UPDATE benutzer SET email=? WHERE id=?",
                        (email or None, benutzer["id"]))
            meldungen.append("E-Mail-Adresse gespeichert" if email
                             else "E-Mail-Adresse entfernt")

    if not meldungen:
        return _konto_zurueck(hinweis="Es gab nichts zu ändern.")
    return _konto_zurueck(hinweis=" · ".join(meldungen) + ".")
