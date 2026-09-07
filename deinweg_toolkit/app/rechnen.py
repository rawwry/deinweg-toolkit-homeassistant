"""Reine Rechen- und Formatfunktionen.

Bewusst ohne FastAPI, ohne Templates und ohne Kenntnis der Oberflaeche:
dieses Modul importiert nur ``db`` und ``parser``. Genau deshalb duerfen
main.py UND die daraus ausgelagerten Seitenmodule (auswertung.py,
meinbereich.py, export.py) es importieren, ohne dass ein Ringschluss
entsteht - anders als bei den Router-Modulen, die ihre Umgebung ueber
``setup()`` gereicht bekommen.

Was hier hineingehoert: alles, was aus Zahlen und Datumsangaben andere
Zahlen und Texte macht - Monatsrechnung, Soll-Stunden, bewilligte
Zeitraeume, Urlaubszaehlung, der gemeinsame Bereichsfilter und die
Auswahllisten der Filterzeile. Was NICHT hineingehoert: alles, was eine
Anfrage, eine Antwort oder eine Vorlage kennt.

⚠️ Die Formatfunktionen (euro, zahl, stunden, gesamtstunden, tage) stehen
hier, ihre Anmeldung als Jinja-Filter bleibt in main.py - die Templates
gibt es nur dort.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from urllib.parse import urlencode

from . import db
from .parser import norm


def jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def deutsch(datum: str) -> str:
    """JJJJ-MM-TT als TT.MM.JJJJ. Alles andere kommt unveraendert zurueck.

    ⚠️ Auch None und Zahlen: der Filter steht in vielen Vorlagen, und ein
    leeres Feld darf keine Seite abschiessen. Bis 1.21 fing er nur
    ValueError ab - eine Logzeile ohne Datum (Sammelaenderung der
    Datenpflege) warf damit TypeError.
    """
    try:
        return dt.date.fromisoformat(datum).strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return datum or ""


def sicherer_name(name: str) -> str:
    """Ein Dateiname, der ueberall funktioniert - ohne Pfad, ohne Sonderzeichen."""
    name = os.path.basename(name).replace("/", "_").replace("\\", "_")
    return re.sub(r"[^A-Za-z0-9._ äöüÄÖÜß-]", "_", name)[:120] or "datei"


def euro(betrag) -> str:
    """1234.5 wird zu 1.234,50 €"""
    return zahl(betrag) + (" €" if zahl(betrag) != "–" else "")


def zahl(betrag) -> str:
    """Derselbe Betrag ohne Währungszeichen.

    Für Tabellen, deren Spaltenkopf die Einheit schon trägt: das Zeichen
    hinter jedem einzelnen Wert wiederholt nur, was oben steht, und macht
    die Spalte breiter als nötig.
    """
    try:
        text = f"{float(betrag):,.2f}"
    except (TypeError, ValueError):
        return "–"
    return text.replace(",", "#").replace(".", ",").replace("#", ".")




def stunden(wert) -> str:
    """7.5 wird zu '7,5', 4.0 zu '4' – für Eingabefelder und Anzeigen.

    Bewusst ohne Einheit: der Wert steht mal in einem Feld, mal im Text.
    Eine leere Ausgabe bei 0 waere hier falsch - in einem Eingabefeld soll
    die Null sichtbar sein.
    """
    try:
        zahl = float(wert or 0)
    except (TypeError, ValueError):
        return "0"
    text = f"{zahl:.2f}".rstrip("0").rstrip(".")
    return (text or "0").replace(".", ",")




def gesamtstunden(minuten) -> str:
    """5341 Minuten wird zu '89 Std 1 Min' – lesbar für grosse Summen.

    Im Unterschied zu hhmm (HH:MM, gedacht fuer einzelne Einheiten) ist das
    hier fuer Gesamtsummen wie den Bestand auf der Startseite gedacht, wo
    'HH:MM' bei mehreren tausend Stunden wie eine kaputte Uhrzeit aussieht.
    """
    try:
        minuten = int(minuten)
    except (TypeError, ValueError):
        return "0 Std"
    vorz = "-" if minuten < 0 else ""
    minuten = abs(minuten)
    stunden, rest = divmod(minuten, 60)
    text = f"{vorz}{stunden:,}".replace(",", ".") + " Std"
    if rest:
        text += f" {rest} Min"
    return text




def tage(wert) -> str:
    """2.0 wird zu '2 Tage', 1.0 zu '1 Tag', 2.5 bleibt '2,5 Tage'."""
    try:
        zahl = float(wert or 0)
    except (TypeError, ValueError):
        return str(wert)
    text = f"{zahl:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} {'Tag' if abs(zahl) == 1 else 'Tage'}"


def monat_verschieben(monat: str, schritte: int) -> str:
    jahr, mon = int(monat[:4]), int(monat[5:7])
    gesamt = jahr * 12 + (mon - 1) + schritte
    return f"{gesamt // 12:04d}-{gesamt % 12 + 1:02d}"

MONATSNAMEN = {
    "01": "Januar", "02": "Februar", "03": "März", "04": "April",
    "05": "Mai", "06": "Juni", "07": "Juli", "08": "August",
    "09": "September", "10": "Oktober", "11": "November", "12": "Dezember",
}


def monat_wort(monat: str) -> str:
    """2026-08 wird zu 'August 2026'."""
    if not monat or len(monat) < 7:
        return monat or ""
    return f"{MONATSNAMEN.get(monat[5:7], monat[5:7])} {monat[:4]}"




def monatsliste(von: str, bis: str) -> list[str]:
    """Alle Monate von bis einschliesslich, als YYYY-MM."""
    try:
        jahr, mon = int(von[:4]), int(von[5:7])
        jahr_b, mon_b = int(bis[:4]), int(bis[5:7])
    except (ValueError, IndexError):
        return []
    ergebnis = []
    while (jahr, mon) <= (jahr_b, mon_b) and len(ergebnis) < 240:
        ergebnis.append(f"{jahr:04d}-{mon:02d}")
        mon += 1
        if mon > 12:
            mon, jahr = 1, jahr + 1
    return ergebnis


MONATSFAKTOR = 4.33  # durchschnittliche Wochen pro Monat, so von der Leitung vorgegeben


def runde_viertelstunde(minuten: float) -> int:
    """Rundet auf den nächsten 15-Minuten-Takt, damit keine krummen Werte entstehen."""
    return int(round(minuten / 15) * 15)


def soll_minuten(wochenstunden: float, monat: str = "") -> int | None:
    """Rechnet das Wochenkontingent mit dem Faktor 4,33 auf einen Monat hoch.

    Der Monat selbst geht nicht mehr in die Rechnung ein - das Ergebnis ist
    für jeden Monat gleich - wird aber als Parameter beibehalten, damit
    Aufrufer nicht angepasst werden müssen und ein leerer Monat weiterhin
    "kein Soll" bedeutet.
    """
    if not wochenstunden or not monat:
        return None
    return runde_viertelstunde(wochenstunden * 60 * MONATSFAKTOR)


def soll_zeitraum(wochenstunden: float, monate: list[str]) -> int | None:
    """Summiert das Soll über mehrere Monate."""
    if not wochenstunden or not monate:
        return None
    einzelsoll = soll_minuten(wochenstunden, monate[0])
    return einzelsoll * len(monate) if einzelsoll else None


# --- Bewilligte Zeiträume je betreuter Person --------------------------------
#
# Der Kostentraeger sagt Wochenstunden und Stundensatz immer nur befristet
# zu. "Michael Mueller" hat von 08/2024 bis 07/2025 vier Wochenstunden zu
# 65 EUR, ab 08/2025 sieben zu 70 EUR. Eine Auswertung ueber beide
# Zeitraeume muss deshalb Monat fuer Monat mit den Werten rechnen, die in
# diesem Monat galten - ein einziger Wert fuer den ganzen Zeitraum waere
# schlicht falsch.
#
# ⚠️ Gerechnet wird MONATSWEISE, obwohl die Zeitraeume taggenau erfasst
# werden. Ein Zeitraum gilt fuer jeden Monat, den er beruehrt. Alles andere
# waere Scheingenauigkeit: schon das Soll entsteht aus einem pauschalen
# Faktor 4,33 Wochen je Monat, und die Auswertung kennt ohnehin nur Monate.

def monatsgrenzen(monat: str) -> tuple[str, str]:
    """Erster und letzter Tag eines Monats als YYYY-MM-DD."""
    jahr, mon = int(monat[:4]), int(monat[5:7])
    letzter = (dt.date(jahr + (mon == 12), (mon % 12) + 1, 1)
               - dt.timedelta(days=1))
    return f"{monat}-01", letzter.isoformat()


# Ab wie vielen Tagen vor dem Ende gilt eine Bewilligung als "laeuft
# aus"? Zwei Monate - so lange dauert ein Folgeantrag beim Kostentraeger
# erfahrungsgemaess, und frueher waere es nur Rauschen.
BEWILLIGUNG_BALD_TAGE = 60


def bewilligungslage(zeitraeume, grund_stunden, grund_satz, heute: str,
                     vorlauf: int | None = None,
                     selbstzahler: bool = False) -> dict:
    """Wie steht eine betreute Person heute da?

    Eine Stelle fuer die Frage, die in den Einstellungen und in "Mein
    Bereich" gleich beantwortet werden muss. Die Liste kommt absteigend
    nach ``von`` herein, wie ueberall (siehe kontingent_im_monat).

    ``art`` ist eines von:
    * ``selbstzahler`` - braucht gar keinen Bescheid (eigener Satz je Stunde)
    * ``laufend``    - alles in Ordnung
    * ``laeuft_aus`` - gilt noch, endet bald, und es gibt keinen Nachfolger
    * ``abgelaufen`` - der letzte Bescheid ist vorbei
    * ``kuenftig``   - der naechste beginnt erst
    * ``grundwert``  - kein Bescheid, aber ein alter Grundwert. Seit 1.20
      rechnet der nicht mehr mit; die Lage heisst damit "hier steht ein
      Wert, der nichts tut" und verlangt, aufgeloest zu werden.
    * ``leer``       - nichts hinterlegt

    ⚠️ Ein Selbstzahler zahlt aus eigener Tasche und braucht keinen
    Kostentraeger-Bescheid. Fuer ihn ist die ganze Frage gegenstandslos -
    deshalb ganz oben abgefangen und "selbstzahler" zurueckgegeben, was
    NICHT in BEWILLIGUNG_HANDLUNG steht und damit nie eine Warnung
    ausloest. Sein Stundensatz ist der vereinbarte Satz an ``person``.

    ⚠️ **Ein hinterlegter Folgebescheid beendet die Warnung.** "Laeuft
    aus" heisst: hier muss ein Folgeantrag raus. Steht der naechste
    Zeitraum schon da, ist genau das erledigt - dann weiter zu warnen
    macht die Hinweise wertlos, weil man sie nicht mehr abstellen kann.
    Die Lage bleibt ``laufend`` und traegt den Nachfolger unter
    ``nachfolge`` mit, damit die Oberflaeche ihn nennen kann.
    """
    if selbstzahler:
        return {"art": "selbstzahler"}

    laufend = None
    for z in zeitraeume or []:
        if z["von"] <= heute and (not z["bis"] or z["bis"] >= heute):
            laufend = z
            break

    if laufend:
        # Deckt irgendein spaeterer Zeitraum die Zeit nach diesem hier ab?
        # Die Liste steht absteigend nach ``von``; alles mit spaeterem
        # Beginn als der laufende faengt erst in der Zukunft an - was
        # heute schon gilt, waere oben als ``laufend`` gefunden worden.
        nachfolge = next(
            (z for z in zeitraeume or []
             if z["von"] > laufend["von"]
             and (not laufend["bis"] or not z["bis"] or z["bis"] > laufend["bis"])),
            None)
        if laufend["bis"] and not nachfolge:
            try:
                tage = (dt.date.fromisoformat(laufend["bis"])
                        - dt.date.fromisoformat(heute)).days
            except ValueError:
                tage = None
            if tage is not None and tage <= (vorlauf or BEWILLIGUNG_BALD_TAGE):
                return {"art": "laeuft_aus", "bis": laufend["bis"],
                        "tage": tage, "zeitraum": laufend}
        return {"art": "laufend", "zeitraum": laufend, "nachfolge": nachfolge}

    if zeitraeume:
        kuenftig = [z for z in zeitraeume if z["von"] > heute]
        if kuenftig:
            naechster = min(kuenftig, key=lambda z: z["von"])
            return {"art": "kuenftig", "ab": naechster["von"],
                    "zeitraum": naechster}
        vergangen = [z for z in zeitraeume if z["bis"] and z["bis"] < heute]
        letzter = max(vergangen, key=lambda z: z["bis"]) if vergangen else None
        return {"art": "abgelaufen",
                "seit": letzter["bis"] if letzter else "", "zeitraum": letzter}

    if grund_stunden or grund_satz:
        return {"art": "grundwert"}
    return {"art": "leer"}


# Welche Lagen verlangen, dass jemand tätig wird? Reihenfolge ist zugleich
# die Dringlichkeit, nach der sortiert wird.
BEWILLIGUNG_HANDLUNG = ("abgelaufen", "leer", "laeuft_aus", "kuenftig",
                        "grundwert")


# --- Urlaub -------------------------------------------------------------------
#
# Ein Urlaubstag ist ein Kalendertag mit einem Eintrag, dessen Beschreibung
# mit "Urlaub" beginnt. Bewusst "beginnt mit" und nicht "enthaelt": in den
# echten Daten steht eine Zeile "Entlastungsgespraech, Erarbeitung
# Strukturplan Urlaub", die kein Urlaubstag ist.
#
# Seit 1.17.3 zaehlt ein halber Tag auch als halber. Erkannt wird er an
# der Leistung "Urlaub (Halber Tag)" - genauer: daran, dass in der
# Beschreibung "halber tag" vorkommt. Bewusst kein eigenes Feld an
# "eintrag": die Leistung ist Klartext (siehe Abschnitt 10), und ein
# zusaetzliches Feld muesste beim Import, beim Bearbeiten und in der
# Datenpflege mitgefuehrt werden - fuer eine Angabe, die ohnehin schon im
# Text steht.
URLAUB_ANFANG = "urlaub"
URLAUB_HALB = "halber tag"


def urlaubswert(beschreibung: str) -> float:
    """Wie viel Urlaub steckt in dieser Zeile? 1.0, 0.5 oder 0."""
    text = (beschreibung or "").strip().lower()
    if not text.startswith(URLAUB_ANFANG):
        return 0.0
    return 0.5 if URLAUB_HALB in text else 1.0


def urlaubstage_zaehlen(zeilen) -> dict[str, float]:
    """Urlaubstage je Jahr aus den Eintraegen einer Person.

    ⚠️ Gezaehlt wird je KALENDERTAG, nicht je Zeile - an einem Tag koennen
    mehrere Eintraege stehen. Steht an einem Tag irgendwo ein ganzer
    Urlaubstag, zaehlt der Tag ganz; sonst reicht ein halber, und der Tag
    zaehlt halb. Zwei halbe Eintraege am selben Tag ergeben also einen
    halben Tag, keinen ganzen: es bleibt derselbe Kalendertag, an dem
    jemand einen halben Tag frei hatte.
    """
    je_tag: dict[tuple[str, str], float] = {}
    for z in zeilen:
        wert = urlaubswert(z["beschreibung"])
        if not wert:
            continue
        schluessel = (z["datum"][:4], z["datum"])
        je_tag[schluessel] = max(je_tag.get(schluessel, 0.0), wert)
    jahre: dict[str, float] = {}
    for (jahr, _datum), wert in je_tag.items():
        jahre[jahr] = jahre.get(jahr, 0.0) + wert
    return jahre


def bewilligungen_pruefen(con, vorlauf: int | None = None) -> list[dict]:
    """Alle aktiven betreuten Personen, bei denen etwas zu tun ist.

    Dringendstes zuerst. Grundlage fuer die Karte in "Mein Bereich".

    ⚠️ Die Karte trennt danach in zwei Gruppen: alles ausser "grundwert"
    steht offen da, "grundwert" zugeklappt darunter. Ohne diese Trennung
    ertraenken zwanzig Altbestands-Zeilen die drei, um die es geht.
    Seit 1.20 ist "grundwert" allerdings keine harmlose Feststellung
    mehr, sondern eine Luecke - der Grundwert rechnet nicht mehr mit.
    Die Zusammenfassung der zugeklappten Gruppe sagt das deshalb
    ausdruecklich, und in den Einstellungen steht dort die Umzugshilfe.
    """
    heute = dt.date.today().isoformat()
    zr = zeitraeume_lesen(con)
    offen = []
    for p in con.execute(
            "SELECT id, name, wochenstunden, stundensatz, selbstzahler "
            "FROM person WHERE aktiv=1 ORDER BY name"):
        stand = bewilligungslage(zr.get(p["name"], []), p["wochenstunden"],
                                 p["stundensatz"], heute, vorlauf,
                                 selbstzahler=p["selbstzahler"])
        if stand["art"] in BEWILLIGUNG_HANDLUNG:
            offen.append({**stand, "name": p["name"], "id": p["id"],
                          "rang": BEWILLIGUNG_HANDLUNG.index(stand["art"])})
    offen.sort(key=lambda r: (r["rang"], r["name"]))
    return offen


def zeitraeume_lesen(con) -> dict[str, list]:
    """Alle bewilligten Zeiträume, nach Personennamen gebündelt.

    Sortiert nach ``von`` absteigend: der zuletzt begonnene Zeitraum steht
    vorn und gewinnt damit bei Überschneidungen (siehe kontingent_im_monat).
    """
    je_person: dict[str, list] = {}
    for r in con.execute(
            "SELECT p.name, z.* FROM person_zeitraum z "
            "JOIN person p ON p.id = z.person_id "
            "ORDER BY z.von DESC, z.id DESC"):
        je_person.setdefault(r["name"], []).append(r)
    return je_person


def kontingent_im_monat(monat: str, zeitraeume, grund_stunden: float,
                        grund_satz: float,
                        selbstzahler: bool = False) -> tuple[float, float, bool]:
    """Welche Wochenstunden und welcher Stundensatz galten in diesem Monat?

    Gibt ``(wochenstunden, stundensatz, aus_zeitraum)`` zurück.

    ⚠️ **Ohne Bescheid gibt es nichts** (seit 1.20). Greift kein Zeitraum,
    steht dort 0 - keine Stunden, kein Geld. Bis 1.19.2 fielen die Werte
    hier auf die Grundwerte der Person zurueck, und genau das war die
    Fehlerquelle: dasselbe Feld "Grundwert Satz" trug einmal den
    vereinbarten Satz eines Selbstzahlers und einmal einen Rueckfall fuer
    Monate ohne Bescheid. Wer einen Kostentraeger hat und keinen
    Bescheid, verdient aber nichts - ein Rueckfall erfand dort Geld.

    Einzige Ausnahme ist der **Selbstzahler**: er braucht keinen Bescheid,
    sein Grundwert IST der vereinbarte Satz. Deshalb wird er ausdruecklich
    hereingereicht statt aus den Werten erraten - null Euro Grundwert und
    "kein Kostentraeger" sind zwei verschiedene Dinge.

    ⚠️ **Überschneiden sich zwei Zeiträume, gewinnt der später begonnene.**
    Das kommt in der Praxis vor, wenn ein Folgebescheid schon läuft,
    während der alte formal noch nicht abgelaufen ist. Die Liste kommt
    absteigend nach ``von`` herein, der erste Treffer ist also der
    richtige.
    """
    anfang, ende = monatsgrenzen(monat)
    for z in zeitraeume or []:
        if z["von"] > ende:
            continue
        if z["bis"] and z["bis"] < anfang:
            continue
        return (z["wochenstunden"] or 0), (z["stundensatz"] or 0), True
    if selbstzahler:
        return grund_stunden or 0, grund_satz or 0, False
    return 0, 0, False


def bereichsfilter(von_jahr="", von_monat="", bis_jahr="", bis_monat="",
                   mitarbeiter="", klient="", q="", import_id=0,
                   nur_abrechenbar=""):
    """Ein Filter für Auswertung, Datensätze und Export – bewusst nur einmal.

    Baut aus den Formularfeldern die WHERE-Bedingung, die Beschriftung des
    Zeitraums und die Parameter für Links zurück.
    """
    von_jahr, von_monat = str(von_jahr or "").strip(), str(von_monat or "").strip()
    bis_jahr, bis_monat = str(bis_jahr or "").strip(), str(bis_monat or "").strip()

    # "klient" und "mitarbeiter" nehmen seit 1.5 bzw. 1.6 mehrere Namen
    # entgegen - man wertet oft zwei oder drei zusammen aus. Ein einzelner
    # String kommt weiterhin an (alte Lesezeichen, Links aus anderen
    # Seiten) und wird hier zur Liste mit einem Element.
    def als_liste(wert) -> list[str]:
        if isinstance(wert, str):
            roh = [wert.strip()] if wert.strip() else []
        else:
            roh = [str(w).strip() for w in (wert or []) if str(w).strip()]
        # Reihenfolge stabil halten, Dubletten raus - sonst steht derselbe
        # Name zweimal in der Chipleiste.
        return list(dict.fromkeys(roh))

    klienten_filter = als_liste(klient)
    leute_filter = als_liste(mitarbeiter)

    # Teilangaben sinnvoll ergänzen: ein Jahr ohne Monat meint das ganze Jahr.
    von = f"{von_jahr}-{von_monat or '01'}" if von_jahr else ""
    bis = f"{bis_jahr}-{bis_monat or '12'}" if bis_jahr else ""
    if von and bis and von > bis:
        von, bis = bis, von
        von_jahr, von_monat, bis_jahr, bis_monat = (
            bis_jahr, bis_monat, von_jahr, von_monat)

    # Ein Monat ohne Jahr meint diesen Monat in allen Jahren
    nur_monate = (von_monat if not von_jahr else "", bis_monat if not bis_jahr else "")

    wo, werte = ["1=1"], []
    if von:
        wo.append("monat>=?"); werte.append(von)
    if bis:
        wo.append("monat<=?"); werte.append(bis)
    if nur_monate[0] and nur_monate[1]:
        a, b = sorted(nur_monate)
        wo.append("substr(monat, 6, 2) BETWEEN ? AND ?"); werte += [a, b]
    elif nur_monate[0]:
        wo.append("substr(monat, 6, 2)>=?"); werte.append(nur_monate[0])
    elif nur_monate[1]:
        wo.append("substr(monat, 6, 2)<=?"); werte.append(nur_monate[1])
    if leute_filter:
        wo.append("mitarbeiter IN (" + ",".join("?" * len(leute_filter)) + ")")
        werte += leute_filter
    if klienten_filter:
        platzhalter = ",".join("?" * len(klienten_filter))
        wo.append(f"klient IN ({platzhalter})")
        werte += klienten_filter
    if import_id:
        wo.append("import_id=?"); werte.append(import_id)
    if nur_abrechenbar:
        wo.append("klient IN (SELECT name FROM person WHERE abrechenbar=1)")
    if q:
        wo.append("(beschreibung LIKE ? OR klient LIKE ? OR mitarbeiter LIKE ?)")
        werte += [f"%{q}%"] * 3

    def monatsname(nr):
        return MONATSNAMEN.get(nr, nr)

    if von and bis and von == bis:
        wort = monat_wort(von)
    elif von and bis and von[:4] == bis[:4] and von[5:] == "01" and bis[5:] == "12":
        wort = f"Jahr {von[:4]}"
    elif von and bis:
        wort = f"{monat_wort(von)} bis {monat_wort(bis)}"
    elif von:
        wort = f"ab {monat_wort(von)}"
    elif bis:
        wort = f"bis {monat_wort(bis)}"
    elif nur_monate[0] and nur_monate[1] and nur_monate[0] == nur_monate[1]:
        wort = f"{monatsname(nur_monate[0])}, alle Jahre"
    elif nur_monate[0] and nur_monate[1]:
        a, b = sorted(nur_monate)
        wort = f"{monatsname(a)} bis {monatsname(b)}, alle Jahre"
    elif nur_monate[0]:
        wort = f"ab {monatsname(nur_monate[0])}, alle Jahre"
    elif nur_monate[1]:
        wort = f"bis {monatsname(nur_monate[1])}, alle Jahre"
    else:
        wort = "alle Zeiten"

    felder = {"von_jahr": von_jahr, "von_monat": von_monat,
              "bis_jahr": bis_jahr, "bis_monat": bis_monat,
              # Der Einzelwert bleibt (fuer Links und die alte
              # Schreibweise), daneben steht die vollstaendige Liste.
              "mitarbeiter": leute_filter[0] if len(leute_filter) == 1 else "",
              "mitarbeiterliste": leute_filter,
              "klient": klienten_filter[0] if len(klienten_filter) == 1 else "",
              "klienten": klienten_filter, "q": q,
              "import_id": import_id or "", "nur_abrechenbar": nur_abrechenbar}

    aktive = []
    if von or bis or nur_monate[0] or nur_monate[1]:
        aktive.append(("Zeitraum", wort))
    if len(klienten_filter) == 1:
        aktive.append(("Betreute Person", klienten_filter[0]))
    elif klienten_filter:
        aktive.append((f"{len(klienten_filter)} betreute Personen",
                       ", ".join(klienten_filter)))
    if len(leute_filter) == 1:
        aktive.append(("Mitarbeiter", leute_filter[0]))
    elif leute_filter:
        aktive.append((f"{len(leute_filter)} Mitarbeiter", ", ".join(leute_filter)))
    if q:
        aktive.append(("Suche", q))
    if nur_abrechenbar:
        aktive.append(("Nur abrechenbar", "ja"))
    if import_id:
        aktive.append(("Import", f"Nr. {import_id}"))

    return {
        "wo": " AND ".join(wo), "werte": werte,
        "von": von, "bis": bis, "wort": wort, "nur_monate": nur_monate,
        "f": felder, "aktive": aktive,
        # doseq, damit mehrere Namen als eigene klient=-Parameter
        # herauskommen und nicht als ein String mit Kommas.
        # doseq, damit mehrere Namen als eigene klient=/mitarbeiter=
        # Parameter herauskommen und nicht als ein String mit Kommas.
        "query": urlencode(
            {k: v for k, v in felder.items()
             if v and k not in ("klient", "klienten",
                                "mitarbeiter", "mitarbeiterliste")}
            | ({"klient": klienten_filter} if klienten_filter else {})
            | ({"mitarbeiter": leute_filter} if leute_filter else {}),
            doseq=True),
    }


def mitarbeiter_zu_benutzer(con, benutzer):
    """Welcher Mitarbeiter gehoert zum angemeldeten Konto?

    Gleiche Regel wie beim E-Mail-Versand (siehe mail.adresse_fuer):
    ausdrueckliche Zuordnung hat Vorrang, sonst Namensgleichheit.
    """
    zuordnung = ""
    try:
        zuordnung = (benutzer["mitarbeiter"] or "").strip()
    except (IndexError, KeyError, TypeError):
        # Aeltere Sitzung, die die Spalte noch nicht mitgelesen hat -
        # dann greift unten der Weg ueber die Namensgleichheit.
        zuordnung = ""
    if zuordnung:
        r = con.execute("SELECT * FROM mitarbeiter WHERE LOWER(TRIM(name))=LOWER(?)",
                        (zuordnung,)).fetchone()
        if r:
            return r
        # Zuordnung zeigt auf einen Namen, den es im Team nicht mehr gibt -
        # Zeiten koennen trotzdem noch vorhanden sein.
        return {"name": zuordnung, "monatsstunden": 0, "aktiv": 0,
                "abgabepflicht": 0, "verwaist": True}
    return con.execute(
        "SELECT * FROM mitarbeiter WHERE LOWER(name)=LOWER(?)",
        (benutzer["benutzername"],)).fetchone()


def mitarbeiterauswahl(con) -> dict:
    """Namen fuer das Auswahlfeld "Mitarbeiter".

    Erste Gruppe ist das gepflegte Team (Einstellungen -> Mitarbeiter),
    nur die aktiven. Zweite Gruppe sind Namen, die in den Zeiten schon
    vorkommen, aber nicht (mehr) im Team stehen - sonst waeren Zeiten von
    ausgeschiedenen Kolleginnen ueber das Auswahlfeld nicht mehr
    erreichbar. Verglichen wird ueber norm(), weil Schreibweisen aus
    Fremdexporten abweichen koennen.
    """
    team = [r["name"] for r in con.execute(
        "SELECT name FROM mitarbeiter WHERE aktiv=1 ORDER BY name COLLATE NOCASE")]
    bekannt = {norm(n) for n in team}
    weitere = [r["mitarbeiter"] for r in con.execute(
        "SELECT DISTINCT mitarbeiter FROM eintrag ORDER BY 1 COLLATE NOCASE")
        if norm(r["mitarbeiter"]) not in bekannt]
    return {"team": team, "weitere": weitere}


def klientenauswahl(con) -> dict:
    """Namen fuer das Auswahlfeld "Betreute Person".

    Nach demselben Muster wie ``mitarbeiterauswahl``: erste Gruppe sind
    die aktiven betreuten Personen aus den Einstellungen, zweite Gruppe
    Namen, die nur noch in vorhandenen Zeiten vorkommen.

    ⚠️ Die zweite Gruppe ist keine Bequemlichkeit, sondern noetig: ohne
    sie waeren Zeiten auf einen stillgelegten oder aus einem Fremdexport
    stammenden Namen ueber das Feld nicht mehr zu erfassen. Und die erste
    ist noetig, weil eine gerade angelegte Person noch gar keine Zeit hat
    und sonst nicht auswaehlbar waere.
    """
    personen = [r["name"] for r in con.execute(
        "SELECT name FROM person WHERE aktiv=1 ORDER BY name COLLATE NOCASE")]
    bekannt = {norm(n) for n in personen}
    weitere = [r["klient"] for r in con.execute(
        "SELECT DISTINCT klient FROM eintrag ORDER BY 1 COLLATE NOCASE")
        if r["klient"] and norm(r["klient"]) not in bekannt]
    return {"personen": personen, "weitere": weitere}


def auswahllisten() -> dict:
    """Jahre, Mitarbeiter und betreute Personen für die Auswahlfelder."""
    heute = dt.date.today()
    with db.db() as con:
        jahre = [r["j"] for r in con.execute(
            "SELECT DISTINCT substr(monat, 1, 4) j FROM eintrag ORDER BY 1 DESC")]
        leute = [r["mitarbeiter"] for r in con.execute(
            "SELECT DISTINCT mitarbeiter FROM eintrag ORDER BY 1")]
        klienten = [r["klient"] for r in con.execute(
            "SELECT DISTINCT klient FROM eintrag ORDER BY 1")]
        # In welchen Monaten steht ueberhaupt etwas? Der Picker setzt
        # darunter einen Punkt - so sieht man, wo Daten liegen, statt in
        # einen leeren Zeitraum zu filtern und sich zu wundern.
        monate_mit_daten = [r["m"] for r in con.execute(
            "SELECT DISTINCT monat m FROM eintrag ORDER BY 1")]
    if str(heute.year) not in jahre:
        jahre = [str(heute.year)] + jahre
    return {"jahre": jahre, "leute": leute, "klienten": klienten,
            "monatsnamen": MONATSNAMEN, "monate_mit_daten": monate_mit_daten,
            # Der Zeitraum-Picker rechnet "dieser Monat" / "letzte 12
            # Monate" daraus aus. Bewusst vom Server: die Uhr des Browsers
            # kann falsch gehen, und die Auswertung soll denselben Monat
            # meinen wie der Wecker.
            "heute_monat": heute.strftime("%Y-%m")}
