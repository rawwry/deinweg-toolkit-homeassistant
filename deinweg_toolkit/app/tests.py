"""Automatische Prüfungen für das Dein Weg Toolkit.

Aufruf (im Ordner config, also dort wo der Ordner app liegt):

    python3 -m app.tests

Ohne Zusatzpakete: die Prüfungen laufen direkt gegen die FastAPI-Anwendung
über deren eigenen Testmodus, es wird also kein Server und kein Netz
gebraucht. Jeder Lauf legt eine frische Datenbank in einem temporären
Ordner an und räumt sie hinterher wieder weg - die echten Daten werden
nie angefasst.

Was hier geprüft wird, ist bewusst kein Detailwissen über einzelne
Rechenwege, sondern das, was beim Bauen erfahrungsgemäß kaputtgeht:
lädt jede Seite, greift die Anmeldung, greifen die Zugriffsrechte, sind
alle Vorlagen fehlerfrei, funktioniert der Weg vom Hochladen bis in den
Bestand.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import traceback


# --- Umgebung vorbereiten, bevor die Anwendung geladen wird ------------------

_ORDNER = tempfile.mkdtemp(prefix="toolkit-test-")
for unter in ("db", "texte", "wiki", "files"):
    os.makedirs(os.path.join(_ORDNER, unter), exist_ok=True)

os.environ.update({
    "DB_PFAD": os.path.join(_ORDNER, "db", "test.db"),
    "SPRUCH_DATEI": os.path.join(_ORDNER, "texte", "quotes.txt"),
    "IDEEN_DATEI": os.path.join(_ORDNER, "texte", "ideen.txt"),
    "STRINGS_DATEI": os.path.join(_ORDNER, "texte", "strings.txt"),
    "WIKI_PFAD": os.path.join(_ORDNER, "wiki"),
    "FILES_PFAD": os.path.join(_ORDNER, "files"),
    "WECKER_INTERVALL": "0",
    "ADMIN_BENUTZERNAME": "pruefer",
    "ADMIN_PASSWORT": "pruefpasswort",
})

from fastapi.testclient import TestClient  # noqa: E402

from . import db  # noqa: E402
from .main import app  # noqa: E402


# --- Kleines Gerüst ----------------------------------------------------------

_ERGEBNIS = {"ok": 0, "fehler": []}


def pruefe(bedingung, beschreibung: str) -> None:
    if bedingung:
        _ERGEBNIS["ok"] += 1
    else:
        _ERGEBNIS["fehler"].append(beschreibung)
        print(f"   FEHLGESCHLAGEN: {beschreibung}")


def abschnitt(titel: str) -> None:
    print(f"\n{titel}")


def anmelden(client: TestClient) -> None:
    antwort = client.post("/login", data={
        "benutzername": "pruefer", "passwort": "pruefpasswort", "weiter": "/"},
        follow_redirects=False)
    pruefe(antwort.status_code == 303, "Anmeldung mit gültigem Passwort")
    pruefe("fehler" not in antwort.headers.get("location", ""),
           "Anmeldung meldet keinen Fehler")


def testdaten_anlegen() -> None:
    """Ein Mitarbeiter, eine betreute Person, ein paar Zeiten."""
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, monatsstunden, urlaubstage, angelegt_am) "
                    "VALUES ('pruefer',1,1,160,30,'2026-01-01 08:00')")
        con.execute("INSERT OR IGNORE INTO person (name, wochenstunden, "
                    "aktiv, angelegt_am) VALUES ('Testperson',10,1,"
                    "'2026-01-01 08:00')")
        for tag, fp in (("2026-01-05", "t1"), ("2026-02-05", "t2")):
            con.execute(
                "INSERT OR IGNORE INTO eintrag (mitarbeiter, datum, monat, "
                "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
                "fingerprint, angelegt_am) VALUES "
                "('pruefer',?,?, '09:00','10:00','Testperson','Besuch',60,1,?,?)",
                (tag, tag[:7], fp, tag + " 09:00"))
        con.execute(
            "INSERT OR IGNORE INTO eintrag (mitarbeiter, datum, monat, start, "
            "ende, klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('pruefer','2026-03-02','2026-03','00:00',"
            "'00:00','Testperson','Urlaub',480,0,'u1','2026-03-02 08:00')")


# --- Die einzelnen Prüfungen -------------------------------------------------

def test_ohne_anmeldung(client: TestClient) -> None:
    abschnitt("Ohne Anmeldung")
    antwort = client.get("/eintraege", follow_redirects=False)
    pruefe(antwort.status_code == 303 and "/login" in
           antwort.headers.get("location", ""),
           "geschützte Seite leitet zur Anmeldung")
    pruefe(client.get("/gesundheit").status_code == 200,
           "Statusabfrage bleibt ohne Anmeldung erreichbar")
    pruefe(client.get("/login").status_code == 200,
           "Anmeldeseite ist erreichbar")
    antwort = client.post("/login", data={"benutzername": "pruefer",
                                          "passwort": "falsch"},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "falsches Passwort wird abgewiesen")


def test_seiten(client: TestClient) -> None:
    abschnitt("Jede Seite lädt")
    seiten = [
        "/", "/eintraege", "/auswertung", "/ideen", "/changelog",
        "/vorgaenge", "/vorgaenge/logbuch", "/meinbereich", "/meinbereich?alle=1",
        "/wiki", "/wiki/aktion/suche?q=Leitfaden",
        "/fuhrpark", "/fuhrpark/auswertung",
        "/fuhrpark/auswertung?zeitraum=alles",
        "/fuhrpark/auswertung?zeitraum=letzter_monat",
        "/einstellungen?bereich=kfz",
        "/einstellungen?bereich=oberflaeche",
        "/einstellungen?bereich=quotes",
        "/einstellungen?bereich=betreute",
        "/einstellungen?bereich=mitarbeiter",
        "/einstellungen?bereich=vorgangsarten",
        "/einstellungen?bereich=leistungen",
        "/einstellungen?bereich=benutzer",
        "/einstellungen?bereich=email",
        "/einstellungen?bereich=vorlagen",
        "/einstellungen?bereich=system",
        "/eintraege?von_jahr=2026&von_monat=01&nur_abrechenbar=1",
        "/auswertung?von_jahr=2026&bis_jahr=2026",
        "/vorgaenge?zustand=alle&sortierung=person",
        "/?mitarbeiter=pruefer&datum=05.01.2026",
    ]
    for seite in seiten:
        antwort = client.get(seite)
        pruefe(antwort.status_code == 200, f"{seite} lädt (HTTP "
                                           f"{antwort.status_code})")


def test_vorlagen_vollstaendig(client: TestClient) -> None:
    """Prüft, dass keine Vorlage einen Struktur- oder Platzhalterfehler hat.

    Ein vergessenes {% endif %} fällt sonst erst auf, wenn jemand die Seite
    aufruft - genau das ist in der Vergangenheit passiert.
    """
    abschnitt("Vorlagen")
    from jinja2 import Environment, FileSystemLoader
    ordner = os.path.join(os.path.dirname(__file__), "templates")
    umgebung = Environment(loader=FileSystemLoader(ordner))
    dateien = [d for d in sorted(os.listdir(ordner)) if d.endswith(".html")]
    pruefe(len(dateien) > 10, "Vorlagen gefunden")
    for datei in dateien:
        try:
            with open(os.path.join(ordner, datei), encoding="utf-8") as f:
                umgebung.parse(f.read())
            pruefe(True, f"{datei} ist fehlerfrei")
        except Exception as e:
            pruefe(False, f"{datei}: {e}")


def test_import(client: TestClient) -> None:
    abschnitt("Import einer Datei")
    try:
        import openpyxl
    except ImportError:
        print("   übersprungen: openpyxl nicht verfügbar")
        return
    import io
    mappe = openpyxl.Workbook()
    blatt = mappe.active
    blatt.append(["Datum", "Von", "Bis", "Tags", "Notiz"])
    blatt.append(["2026-04-07", "08:00", "09:30", "Testperson", "Hausbesuch"])
    puffer = io.BytesIO()
    mappe.save(puffer)
    puffer.seek(0)

    antwort = client.post(
        "/upload",
        files={"datei": ("pruefliste.xlsx", puffer.getvalue(),
                         "application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet")},
        data={"mitarbeiter": "pruefer", "erzwingen": "1"},
        follow_redirects=False)
    pruefe(antwort.status_code == 303, "Datei wird angenommen")
    ziel = antwort.headers.get("location", "")
    pruefe("/vorschau/" in ziel, "Vorschau wird angelegt")

    if "/vorschau/" not in ziel:
        return
    import_id = ziel.rsplit("/", 1)[-1].split("?")[0]
    pruefe(client.get(f"/vorschau/{import_id}").status_code == 200,
           "Vorschau lässt sich öffnen")

    vorher = _anzahl_eintraege()
    antwort = client.post(f"/vorschau/{import_id}/uebernehmen", data={},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Übernahme läuft durch")
    pruefe(_anzahl_eintraege() > vorher, "Zeilen sind im Bestand angekommen")


def test_menue(client: TestClient) -> None:
    """Zeiterfassung, Übersicht und Auswertung liegen unter „Arbeitszeit“."""
    abschnitt("Menü")
    for adresse, hier in (("/", "Zeiterfassung"), ("/eintraege", "Übersicht"),
                          ("/auswertung", "Auswertung")):
        seite = client.get(adresse).text
        kopf = seite.split("<main>")[0]
        pruefe("Arbeitszeit" in kopf,
               f"{adresse}: „Arbeitszeit“ steht in der Kopfzeile")
        pruefe(">Zeiterfassung<" not in kopf,
               f"{adresse}: die drei Einzelpunkte nicht mehr daneben")
        pruefe("unternavigation" in seite,
               f"{adresse}: die Reiterleiste ist da")
        leiste = seite.split('class="unternavigation"')[1].split("</nav>")[0]
        pruefe(f"aria-current=page>{hier}</a>" in leiste,
               f"{adresse}: „{hier}“ ist als aktueller Punkt markiert")
        pruefe(leiste.count("aria-current=page") == 1,
               f"{adresse}: und zwar nur dieser eine")
        pruefe(leiste.count("<a ") == 3,
               f"{adresse}: alle drei Unterpunkte stehen darin")

    seite = client.get("/eintraege").text
    pruefe("<h1>Übersicht</h1>" in seite,
           "die Seite heißt jetzt „Übersicht“ statt „Datensätze“")
    pruefe("– Übersicht" in seite, "auch im Titel des Browserfensters")
    # Der Bereichsschlüssel bleibt "datensaetze" - nur die Beschriftung
    # hat sich geändert. Sonst verlöre jedes eingeschränkte Konto seine
    # Berechtigung.
    from . import auth as _auth
    pruefe("datensaetze" in _auth.BEREICHE,
           "der Berechtigungsschlüssel bleibt unverändert")


def _fahrzeug_ids() -> list:
    with db.db() as con:
        return [r["id"] for r in con.execute("SELECT id FROM fahrzeug ORDER BY id")]


def test_kfz(client: TestClient) -> None:
    """Fuhrpark: Stammdaten, Erfassung, Plausibilitaet, Verbrauch, Faelligkeit.

    Die Daten werden so gelegt, dass sie unabhaengig vom Tag des Laufs
    dieselbe Aussage ergeben - Faelligkeiten haengen am heutigen Datum.
    """
    import datetime as _dt
    from . import kfz

    abschnitt("Fuhrpark")
    heute = _dt.date.today()

    def tage_her(n: int) -> str:
        return (heute - _dt.timedelta(days=n)).isoformat()

    # --- Stammdaten ---------------------------------------------------------
    antwort = client.post("/einstellungen/fahrzeug", data={
        "kennzeichen": "ST-PR 100", "marke": "Prüf", "modell": "Wagen",
        "baujahr": "2020", "km_start": "100000", "kraftstoff": "Diesel",
        "leistung": "100", "hubraum": "1600", "getriebe": "Automatik",
        "farbe": "Grau"}, follow_redirects=False)
    pruefe(antwort.status_code == 303 and "hinweis" in
           antwort.headers.get("location", ""), "Fahrzeug wird angelegt")

    antwort = client.post("/einstellungen/fahrzeug", data={
        "kennzeichen": "stpr100"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "dasselbe Kennzeichen wird nicht zweimal angelegt")

    antwort = client.post("/einstellungen/fahrzeug", data={
        "kennzeichen": "ST-PR 200", "marke": "Zweit", "modell": "Wagen",
        "km_start": "20000", "kraftstoff": "Benzin"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "zweites Fahrzeug wird angelegt")

    ids = _fahrzeug_ids()
    pruefe(len(ids) == 2, "beide Fahrzeuge stehen in der Datenbank")
    if len(ids) < 2:
        return
    eins, zwei = ids[0], ids[1]

    antwort = client.post("/einstellungen/fahrzeug", data={
        "kennzeichen": "ST-PR 300", "baujahr": "1650"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "unmögliches Baujahr wird abgewiesen")

    # --- Erfassung ----------------------------------------------------------
    def erfassen(**werte):
        return client.post("/fuhrpark/erfassen", data=werte,
                           follow_redirects=False)

    # Drei Volltankungen: daraus ergeben sich genau zwei Verbrauchswerte.
    tankungen = [(tage_her(90), 100600, "40,0", "60,00"),
                 (tage_her(60), 101200, "42,0", "63,00"),
                 (tage_her(30), 101900, "49,0", "73,50")]
    for datum, km, liter, preis in tankungen:
        antwort = erfassen(fahrzeug_id=eins, art="tanken", datum=datum, km=km,
                           liter=liter, kosten=preis, voll="1")
        pruefe(antwort.status_code == 303 and "fehler" not in
               antwort.headers.get("location", ""), f"Tanken am {datum}")

    antwort = erfassen(fahrzeug_id=eins, art="tanken", datum=tage_her(20),
                       km=102300, kosten="50,00")
    pruefe("fehler" in antwort.headers.get("location", ""),
           "Tanken ohne Menge wird abgewiesen")

    antwort = erfassen(fahrzeug_id=eins, art="km", datum=tage_her(1), km=50)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein rückwärts laufender Kilometerstand wird abgewiesen")

    antwort = erfassen(fahrzeug_id=eins, art="km", datum=tage_her(45), km=100000)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein Kilometerstand unter einem früher erfassten wird abgewiesen")

    antwort = erfassen(fahrzeug_id=eins, art="km", datum=tage_her(2), km=102500)
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "ein passender Kilometerstand wird gespeichert")

    antwort = erfassen(fahrzeug_id=eins, art="reparatur", datum=tage_her(25),
                       km=102000, kosten="450,00")
    pruefe("fehler" in antwort.headers.get("location", ""),
           "eine Reparatur ohne Beschreibung wird abgewiesen")

    antwort = erfassen(fahrzeug_id=eins, art="reparatur", datum=tage_her(25),
                       km=102000, kosten="450,00",
                       beschreibung="Lichtmaschine ersetzt",
                       werkstatt="Prüfwerkstatt")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "eine Reparatur mit Beschreibung wird gespeichert")

    antwort = erfassen(fahrzeug_id=eins, art="reifen", datum=tage_her(24),
                       km=102050, kosten="45,00")
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein Reifenwechsel ohne Angabe der Art wird abgewiesen")

    antwort = erfassen(fahrzeug_id=zwei, art="sonstiges", datum=tage_her(10),
                       kosten="612,00", beschreibung="Versicherung")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "sonstige Kosten kommen ohne Kilometerstand aus")

    # --- Berechnungen -------------------------------------------------------
    with db.db() as con:
        reihe = kfz.verbrauchsreihe(con, eins)
        pruefe(len(reihe) == 2,
               f"aus drei Volltankungen werden zwei Verbrauchswerte "
               f"(waren {len(reihe)})")
        # 42 Liter auf 600 km sind genau 7,0 l/100 km
        pruefe(reihe and abs(reihe[0]["verbrauch"] - 7.0) < 0.01,
               "der erste Verbrauchswert stimmt rechnerisch")
        schnitt = kfz.schnittverbrauch(reihe)
        # 91 Liter auf 1300 km sind exakt 7,0 l/100 km
        pruefe(schnitt is not None and abs(schnitt - 7.0) < 0.01,
               "der Schnitt ist Gesamtmenge durch Gesamtstrecke")
        pruefe(kfz.km_staende(con).get(eins) == 102500,
               "der aktuelle Kilometerstand ist der höchste erfasste")
        pruefe(kfz.km_staende(con).get(zwei) == 20000,
               "ohne Erfassung gilt der Anfangsstand aus den Stammdaten")
        pruefe(kfz.verbrauchsreihe(con, zwei) == [],
               "ohne Tankdaten entsteht kein Verbrauchswert")

    # --- Faelligkeiten ------------------------------------------------------
    antwort = erfassen(fahrzeug_id=eins, art="inspektion",
                       datum=tage_her(400), km=100100, kosten="289,00",
                       intervall_monate="12")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "eine Inspektion mit Intervall wird gespeichert")

    antwort = erfassen(fahrzeug_id=zwei, art="tuev", datum=tage_her(710),
                       kosten="135,00", intervall_monate="24")
    pruefe(antwort.status_code == 303, "ein TÜV mit Intervall wird gespeichert")

    with db.db() as con:
        offen = kfz.faelligkeiten(con)
        arten = {(e["fahrzeug_id"], e["art"]): e for e in offen}
        fall = arten.get((eins, "inspektion"))
        pruefe(fall is not None and fall["lage"] == "ueberfaellig",
               "eine vor über einem Jahr fällige Inspektion gilt als überfällig")
        pruefe((zwei, "tuev") in arten,
               "ein TÜV, dessen Zweijahresfrist abläuft, taucht auf")
        gespeichert = con.execute(
            "SELECT faellig_datum FROM fahrzeug_ereignis WHERE art='inspektion'"
        ).fetchone()["faellig_datum"]
        pruefe(bool(gespeichert),
               "die nächste Fälligkeit steht in der Datenbank, nicht nur "
               "in der Anzeige")

    # --- Oberflaeche --------------------------------------------------------
    seite = client.get(f"/fuhrpark?fahrzeug={eins}").text
    pruefe("Was möchtest du erfassen?" in seite,
           "die Erfassungsseite bietet die Auswahl an")
    pruefe("Historie" in seite and "Lichtmaschine ersetzt" in seite,
           "die Historie zeigt den erfassten Eintrag")
    for art in ("tanken", "wartung", "tuev", "reifen", "km", "sonstiges",
                "inspektion", "reparatur"):
        antwort = client.get(f"/fuhrpark?fahrzeug={eins}&was={art}")
        pruefe(antwort.status_code == 200 and 'name="art"' in antwort.text,
               f"das Formular für „{art}“ lädt")

    seite = client.get("/fuhrpark/auswertung?zeitraum=alles").text
    pruefe("WAS ANSTEHT" in seite.upper(), "die Auswertung führt die Fälligkeiten")
    pruefe("Prüf Wagen" in seite, "das Fahrzeug steht im Vergleich")
    pruefe("kfz-diagramm" in seite, "mindestens ein Diagramm wird gezeichnet")

    antwort = client.get(f"/fuhrpark/auswertung?fahrzeug={eins}&kategorie=tanken")
    pruefe(antwort.status_code == 200, "die Auswertung lässt sich filtern")

    # --- Kilometerstand beim Tanken ist freiwillig --------------------------
    #
    # Ohne ihn zaehlt die Tankfuellung bei den Kosten mit, ist aber kein
    # Messpunkt fuer den Verbrauch. Ihre Liter duerfen trotzdem nicht
    # verschwinden - sonst kaeme ein zu niedriger Verbrauch heraus.
    antwort = client.post("/einstellungen/fahrzeug", data={
        "kennzeichen": "ST-PR 400", "marke": "Ketten", "modell": "Prüfer",
        "km_start": "1000", "kraftstoff": "Benzin"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "drittes Fahrzeug für die Kettenrechnung")
    drei = _fahrzeug_ids()[-1]

    antwort = erfassen(fahrzeug_id=drei, art="tanken", datum=tage_her(50),
                       km=1000, liter="40,0", kosten="60,00", voll="1")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "Volltankung als Bezugspunkt")
    antwort = erfassen(fahrzeug_id=drei, art="tanken", datum=tage_her(40),
                       liter="40,0", kosten="60,00", voll="1")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "Tanken ohne Kilometerstand wird angenommen")
    antwort = erfassen(fahrzeug_id=drei, art="tanken", datum=tage_her(30),
                       km=2000, liter="45,0", kosten="67,50", voll="1")
    pruefe(antwort.status_code == 303, "Volltankung als zweiter Messpunkt")

    with db.db() as con:
        kette = kfz.verbrauchsreihe(con, drei)
        pruefe(len(kette) == 1,
               f"zwischen zwei Messpunkten entsteht genau ein Wert "
               f"(waren {len(kette)})")
        # 40 + 45 Liter auf 1000 km sind 8,5 – nicht 4,5, wie es
        # herauskaeme, wenn die Tankung ohne Stand unterschlagen würde.
        pruefe(kette and abs(kette[0]["verbrauch"] - 8.5) < 0.01,
               "die Liter einer Tankung ohne Kilometerstand zählen mit")
        pruefe(kette and abs(kette[0]["liter"] - 85.0) < 0.01,
               "und zwar vollständig")

    # Eine Teiltankung dazwischen zählt genauso mit, liefert aber keinen
    # eigenen Wert - dafür ist der Füllstand nicht bekannt.
    erfassen(fahrzeug_id=drei, art="tanken", datum=tage_her(25),
             km=2400, liter="20,0", kosten="30,00")
    erfassen(fahrzeug_id=drei, art="tanken", datum=tage_her(20),
             km=3000, liter="60,0", kosten="90,00", voll="1")
    with db.db() as con:
        kette = kfz.verbrauchsreihe(con, drei)
        pruefe(len(kette) == 2, "die Teiltankung liefert keinen eigenen Wert")
        # 20 + 60 Liter auf 1000 km
        pruefe(len(kette) == 2 and abs(kette[1]["verbrauch"] - 8.0) < 0.01,
               "ihre Liter zählen zum nächsten vollen Tank")

    client.post(f"/einstellungen/fahrzeug/{drei}/loeschen", data={},
                follow_redirects=False)

    # --- Filter der Auswertung ----------------------------------------------
    #
    # Ein eingetragenes Datum gewinnt gegen die Schnellwahl - sonst wäre
    # nicht zu sehen, welche der beiden Angaben gerade wirkt.
    seite = client.get("/fuhrpark/auswertung?zeitraum=alles").text
    pruefe("zeitraumpille" in seite, "die Schnellwahl steht als Reihe da")
    pruefe("Benutzerdefiniert" not in seite,
           "der Umweg über einen Punkt „Benutzerdefiniert“ ist weg")
    def pillenblock(html: str) -> str:
        """Nur der Kasten mit den Schnellwahl-Pillen, ohne den Rest."""
        return html.split('class="zeitraumwahl"')[1].split("</div>")[0]

    antwort = client.get("/fuhrpark/auswertung?zeitraum=dieses_jahr"
                         "&von=2020-01-01&bis=2020-12-31")
    pruefe(antwort.status_code == 200 and "01.01.2020 bis 31.12.2020"
           in antwort.text,
           "ein eigener Zeitraum gewinnt gegen die Schnellwahl")
    pruefe("checked" not in pillenblock(antwort.text),
           "dann ist keine Pille mehr hervorgehoben")
    pruefe('class="zeitraumeigen gilt"' in antwort.text,
           "stattdessen sind die beiden Datumsfelder hervorgehoben")

    antwort = client.get("/fuhrpark/auswertung?zeitraum=letzter_monat")
    block = pillenblock(antwort.text)
    pruefe(block.count("checked") == 1,
           "ohne eigenes Datum ist genau eine Pille hervorgehoben")
    pruefe('value="letzter_monat"' in block.split("checked")[0].rsplit(
        "<label", 1)[-1], "und zwar die gewählte")
    pruefe('class="zeitraumeigen gilt"' not in antwort.text,
           "die Datumsfelder sind dann nicht hervorgehoben")
    # Sonst würde der nächste Klick auf "Filtern" die Schnellwahl
    # stillschweigend in einen eigenen Zeitraum verwandeln.
    # Auf das <div> abzielen, nicht bloss auf den Klassennamen: der Text
    # daneben traegt "zeitraumeigen-wort" und faengt genauso an.
    eigen = antwort.text.split('<div class="zeitraumeigen')[1].split("</div>")[0]
    pruefe('name="von" value=""' in eigen and 'name="bis" value=""' in eigen,
           "die Felder für den eigenen Zeitraum bleiben dabei leer")

    # --- Bearbeiten, Loeschen, Archivieren ----------------------------------
    with db.db() as con:
        eintrag = con.execute(
            "SELECT id FROM fahrzeug_ereignis WHERE art='reparatur'").fetchone()["id"]
    antwort = client.get(f"/fuhrpark?fahrzeug={eins}&bearbeiten={eintrag}")
    pruefe(antwort.status_code == 200 and "Lichtmaschine" in antwort.text,
           "ein Eintrag lässt sich zum Bearbeiten öffnen")
    antwort = client.post(f"/fuhrpark/ereignis/{eintrag}/loeschen",
                          data={"zurueck": f"/fuhrpark?fahrzeug={eins}"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "ein Eintrag lässt sich löschen")

    antwort = client.post(f"/einstellungen/fahrzeug/{zwei}/archivieren",
                          data={}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "ein Fahrzeug lässt sich archivieren")
    seite = client.get(f"/fuhrpark?fahrzeug={zwei}").text
    pruefe("Zweit Wagen" not in seite.split("Archiv")[0],
           "ein archiviertes Fahrzeug steht nicht mehr in der Auswahl")
    antwort = erfassen(fahrzeug_id=zwei, art="km", datum=tage_her(1), km=21000)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "für ein archiviertes Fahrzeug wird nichts mehr erfasst")
    antwort = client.post(f"/einstellungen/fahrzeug/{zwei}/archivieren",
                          data={"aktiv": "1"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "ein Fahrzeug kommt aus dem Archiv zurück")

    with db.db() as con:
        vorher = con.execute(
            "SELECT COUNT(*) c FROM fahrzeug_ereignis WHERE fahrzeug_id=?",
            (zwei,)).fetchone()["c"]
    client.post(f"/einstellungen/fahrzeug/{zwei}/loeschen", data={},
                follow_redirects=False)
    with db.db() as con:
        rest = con.execute(
            "SELECT COUNT(*) c FROM fahrzeug_ereignis WHERE fahrzeug_id=?",
            (zwei,)).fetchone()["c"]
    pruefe(vorher > 0 and rest == 0,
           "mit dem Fahrzeug verschwindet auch seine Historie")

    # --- Menue --------------------------------------------------------------
    startseite = client.get("/").text
    pruefe("Fuhrpark" in startseite,
           "der Menüpunkt Fuhrpark steht in der Navigation")
    pruefe("🚗" not in startseite, "ohne Symbol davor")


def _anzahl_eintraege() -> int:
    with db.db() as con:
        return con.execute("SELECT COUNT(*) c FROM eintrag").fetchone()["c"]


def test_manueller_eintrag(client: TestClient) -> None:
    abschnitt("Manuelle Erfassung")
    vorher = _anzahl_eintraege()
    antwort = client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": "2026-05-04", "start": "10:00",
        "ende": "11:15", "klient": "Testperson", "beschreibung": "Gespräch",
    }, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Eintrag wird angenommen")
    pruefe(_anzahl_eintraege() == vorher + 1, "Eintrag ist gespeichert")


def test_zeiterfassung(client: TestClient) -> None:
    """Listenimport und manueller Eintrag liegen auf einer Seite."""
    abschnitt("Zeiterfassung")
    seite = client.get("/").text
    pruefe("Manuelle Zeiterfassung" in seite,
           "manuelle Erfassung steht auf der Startseite")
    pruefe("Zeitlisten einlesen" in seite, "Listenimport steht darunter")
    pruefe("Bestand" in seite and "Abgaben" in seite,
           "Bestand und Abgaben bleiben erhalten")
    antwort = client.get("/erfassung?mitarbeiter=pruefer", follow_redirects=False)
    pruefe(antwort.status_code == 303
           and antwort.headers.get("location", "").startswith("/?"),
           "alte Adresse /erfassung leitet auf die Startseite um")
    pruefe(client.post("/watchfolder/pruefen", data={},
                       follow_redirects=False).status_code == 404,
           "der Watchfolder ist restlos entfernt")


def test_sammelloeschen(client: TestClient) -> None:
    """Mehrere Datensätze auf einmal löschen."""
    abschnitt("Datensätze sammelweise löschen")
    pruefe('name="ids"' in client.get("/eintraege").text,
           "Auswahlkästchen stehen in der Liste")
    with db.db() as con:
        ids = [r["id"] for r in con.execute(
            "SELECT id FROM eintrag ORDER BY id DESC LIMIT 2")]
    pruefe(len(ids) == 2, "genug Testdaten zum Löschen vorhanden")
    if len(ids) != 2:
        return
    vorher = _anzahl_eintraege()
    antwort = client.post("/eintraege/loeschen",
                          data={"ids": ids, "zurueck": "/eintraege"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Sammellöschen läuft durch")
    pruefe(_anzahl_eintraege() == vorher - 2, "beide Einträge sind weg")
    antwort = client.post("/eintraege/loeschen", data={"zurueck": "/eintraege"},
                          follow_redirects=False)
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "leere Auswahl wird abgefangen")
    pruefe(_anzahl_eintraege() == vorher - 2, "leere Auswahl löscht nichts")


def test_leistungen(client: TestClient) -> None:
    """Vordefinierte Leistungsbeschreibungen: anlegen, auswählen, entfernen."""
    abschnitt("Leistungsbeschreibungen")
    antwort = client.post("/einstellungen/leistung",
                          data={"name": "Begleitung zum Amt"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Leistungsbeschreibung wird angelegt")
    with db.db() as con:
        satz = con.execute("SELECT * FROM leistung WHERE name=?",
                           ("Begleitung zum Amt",)).fetchone()
    pruefe(satz is not None, "Leistungsbeschreibung steht in der Datenbank")
    if satz is None:
        return

    antwort = client.post("/einstellungen/leistung",
                          data={"name": "Begleitung zum Amt"},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "doppelte Bezeichnung wird abgewiesen")

    seite = client.get("/").text
    pruefe('name="leistung"' in seite and "Begleitung zum Amt" in seite,
           "Auswahlfeld erscheint beim manuellen Eintrag")
    pruefe("Eigene Beschreibung" in seite,
           "das freie Textfeld heißt „Eigene Beschreibung“")

    vorher = _anzahl_eintraege()
    client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": "2026-05-06", "start": "08:00",
        "ende": "09:00", "klient": "Testperson",
        "leistung": "Begleitung zum Amt", "beschreibung": "Jobcenter",
    }, follow_redirects=False)
    pruefe(_anzahl_eintraege() == vorher + 1, "Eintrag mit Auswahl gespeichert")
    with db.db() as con:
        text = con.execute(
            "SELECT beschreibung FROM eintrag WHERE datum='2026-05-06'"
        ).fetchone()
    pruefe(text and text["beschreibung"] == "Begleitung zum Amt: Jobcenter",
           "Auswahl und eigener Text werden mit Doppelpunkt zusammengeführt")

    antwort = client.post(f"/einstellungen/leistung/{satz['id']}",
                          data={"name": "Begleitung zum Amt", "aktiv": ""},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Stilllegen läuft durch")
    pruefe('name="leistung"' not in client.get("/").text,
           "stillgelegte Bezeichnung verschwindet aus der Auswahl")

    client.post(f"/einstellungen/leistung/{satz['id']}/loeschen",
                follow_redirects=False)
    with db.db() as con:
        weg = con.execute("SELECT COUNT(*) c FROM leistung").fetchone()["c"]
    pruefe(weg == 0, "Entfernen räumt die Liste")


def test_sprueche(client: TestClient) -> None:
    """Sprüche für die Startseite unter Einstellungen -> Oberfläche."""
    abschnitt("Sprüche für die Startseite")
    from . import einstellungen as e

    vorher = len(e.sprueche_lesen())
    antwort = client.post("/einstellungen/spruch", data={
        "text": "Testspruch eins", "quelle": "Prüfer"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Spruch wird angelegt")
    liste = e.sprueche_lesen()
    pruefe(len(liste) == vorher + 1, "Spruch steht in der Datei")
    pruefe(liste[-1] == {"nr": len(liste) - 1, "text": "Testspruch eins",
                         "quelle": "Prüfer"}, "Text und Quelle stimmen")

    seite = client.get("/einstellungen?bereich=quotes").text
    pruefe("Quotemanager" in seite, "der Quotemanager ist ein eigener Bereich")
    pruefe("Testspruch eins" in seite, "der Spruch erscheint in der Liste")
    pruefe("Prüfer" in seite, "die Quelle erscheint darunter")
    pruefe("Testspruch eins" not in
           client.get("/einstellungen?bereich=oberflaeche").text,
           "unter Oberfläche stehen die Sprüche nicht mehr")

    # Die Anfuehrungszeichen setzt die Anwendung selbst.
    with open(e._u["SPRUCH_DATEI"], encoding="utf-8") as f:
        roh = f.read()
    pruefe("„Testspruch eins“" in roh,
           "in der Datei stehen die Anführungszeichen")
    pruefe('"Testspruch eins"' not in roh,
           "und zwar nur einmal, nicht zusätzlich als gerade Zeichen")

    client.post("/einstellungen/spruch", data={
        "text": '"Schon mit Zeichen getippt"', "quelle": ""},
        follow_redirects=False)
    with open(e._u["SPRUCH_DATEI"], encoding="utf-8") as f:
        roh = f.read()
    pruefe("„Schon mit Zeichen getippt“" in roh,
           "selbst getippte Anführungszeichen werden nicht verdoppelt")
    nr_doppelt = len(e.sprueche_lesen()) - 1
    client.post(f"/einstellungen/spruch/{nr_doppelt}/loeschen",
                follow_redirects=False)

    antwort = client.post("/einstellungen/spruch", data={"text": '""'},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein Spruch aus lauter Anführungszeichen wird abgewiesen")

    antwort = client.post("/einstellungen/spruch", data={"text": "   "},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein leerer Spruch wird abgewiesen")
    pruefe(len(e.sprueche_lesen()) == vorher + 1,
           "die leere Eingabe hat nichts angelegt")

    nr = len(liste) - 1
    antwort = client.post(f"/einstellungen/spruch/{nr}/bearbeiten", data={
        "text": "Testspruch geändert", "quelle": ""}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Bearbeiten läuft durch")
    liste = e.sprueche_lesen()
    pruefe(liste[nr]["text"] == "Testspruch geändert",
           "der Text ist geändert")
    pruefe(liste[nr]["quelle"] == "", "eine geleerte Quelle bleibt leer")

    antwort = client.post(f"/einstellungen/spruch/{nr}/loeschen",
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Löschen läuft durch")
    pruefe(len(e.sprueche_lesen()) == vorher, "der Spruch ist wieder weg")

    antwort = client.post("/einstellungen/spruch/999/loeschen",
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "eine nicht vorhandene Nummer wird abgewiesen")
    pruefe("bereich=quotes" in antwort.headers.get("location", ""),
           "die Rückkehr führt in den Quotemanager")


def test_verwaltungsvorgang(client: TestClient) -> None:
    abschnitt("Aufgaben (Verwaltungsvorgänge)")
    antwort = client.post("/vorgaenge", data={
        "klient": "Testperson", "art": "Antrag gestellt",
        "titel": "Prüfvorgang", "zustaendig": "pruefer", "wer": "pruefer",
        "frist": "2026-12-01",
    }, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Vorgang wird angelegt")

    with db.db() as con:
        zeile = con.execute("SELECT id FROM vorgang WHERE titel='Prüfvorgang'"
                            ).fetchone()
    pruefe(zeile is not None, "Vorgang steht in der Datenbank")
    if not zeile:
        return
    nummer = zeile["id"]
    pruefe(client.get(f"/vorgaenge/{nummer}").status_code == 200,
           "Vorgang lässt sich öffnen")

    client.post(f"/vorgaenge/{nummer}/status", data={
        "status": "Eingereicht", "wer": "pruefer", "notiz": "geprüft"})
    with db.db() as con:
        eintraege = con.execute(
            "SELECT COUNT(*) c FROM vorgang_log WHERE vorgang_id=?",
            (nummer,)).fetchone()["c"]
    pruefe(eintraege >= 2, "jede Änderung landet im Logbuch")

    antwort = client.post(
        "/vorgaenge", data={"klient": "Gibt Es Nicht", "art": "Antrag gestellt",
                            "titel": "Unerlaubt", "zustaendig": "pruefer",
                            "wer": "pruefer"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "unbekannte betreute Person wird abgelehnt")


def test_rechte(client: TestClient) -> None:
    abschnitt("Zugriffsrechte")
    client.post("/einstellungen/benutzer", data={
        "benutzername": "eng", "passwort": "engpasswort", "rolle": "benutzer",
        "email": "eng@example.de", "bereiche": ["datensaetze"]})

    zweiter = TestClient(app)
    antwort = zweiter.post("/login", data={"benutzername": "eng",
                                           "passwort": "engpasswort"},
                           follow_redirects=False)
    pruefe(antwort.status_code == 303, "eingeschränktes Konto kann sich anmelden")
    pruefe(zweiter.get("/eintraege").status_code == 200,
           "freigegebener Bereich ist erreichbar")
    for gesperrt in ("/auswertung", "/vorgaenge", "/einstellungen", "/wiki",
                     "/fuhrpark", "/fuhrpark/auswertung"):
        pruefe(zweiter.get(gesperrt).status_code == 403,
               f"{gesperrt} ist gesperrt (direkter Aufruf)")
    antwort = zweiter.post("/einstellungen/benutzer", data={
        "benutzername": "schmuggel", "passwort": "x"})
    pruefe(antwort.status_code == 403,
           "Benutzerverwaltung ist für Nicht-Administratoren gesperrt")
    pruefe(zweiter.get("/meinbereich").status_code == 200,
           "eigener Bereich bleibt für jeden erreichbar")
    seite = client.get("/meinbereich").text
    pruefe('action="/logout"' in seite, "Abmelden steht in „Mein Bereich“")
    pruefe(seite.count('action="/logout"') == 1, "und zwar genau einmal")
    pruefe('action="/logout"' not in client.get("/eintraege").text,
           "in der Kopfzeile steht es nicht mehr")


def test_symbole(client: TestClient) -> None:
    """Favicon und das Symbol fuer den Startbildschirm."""
    abschnitt("Symbole")
    for pfad, mindestens in (("/static/favicon.ico", 1000),
                             ("/static/apple-touch-icon.png", 2000),
                             ("/static/icon-192.png", 2000),
                             ("/static/icon-512.png", 2000)):
        antwort = client.get(pfad)
        pruefe(antwort.status_code == 200, f"{pfad} wird ausgeliefert")
        pruefe(len(antwort.content) > mindestens, f"{pfad} ist nicht leer")
    kopf = client.get("/").text
    pruefe('rel="apple-touch-icon" sizes="180x180"' in kopf,
           "das Symbol für den Startbildschirm ist eingebunden")
    pruefe("apple-touch-icon.png?v=" in kopf,
           "die Versionsnummer hängt daran, sonst bleibt das alte Symbol stehen")
    pruefe("favicon.ico?v=" in client.get("/login").text,
           "auch die Anmeldeseite trägt das Symbol")


def test_oberflaeche(client: TestClient) -> None:
    """Der Umschalter fuer die Wiki-Ansicht sitzt bei den anderen
    Oberflaechen-Einstellungen und wirkt nur im Browser."""
    abschnitt("Oberfläche")
    seite = client.get("/einstellungen?bereich=oberflaeche").text
    pruefe("wikiliste-knopf" in seite, "Umschalter für die Wiki-Ansicht ist da")
    pruefe('data-wikiliste="kacheln"' in seite, "Kacheln sind die Voreinstellung")
    pruefe("thema-knopf" in seite and "breite-knopf" in seite,
           "die bisherigen Schalter stehen weiter daneben")


def test_sicherung(client: TestClient) -> None:
    abschnitt("Datensicherung")
    antwort = client.get("/einstellungen/sicherung")
    pruefe(antwort.status_code == 200, "Sicherung lässt sich herunterladen")
    pruefe(len(antwort.content) > 10000, "Sicherung ist nicht leer")
    pruefe(antwort.content[:15].startswith(b"SQLite format"),
           "Sicherung ist eine gültige Datenbank")

    antwort = client.post("/einstellungen/sicherung",
                          files={"datei": ("kaputt.db", b"kein sqlite")},
                          data={"bestaetigt": "1"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "unpassende Datei wird abgelehnt")


def test_export(client: TestClient) -> None:
    abschnitt("Export")
    for pfad, art in (("/export.csv", "text/csv"), ("/export.xlsx", None)):
        antwort = client.get(pfad)
        pruefe(antwort.status_code == 200, f"{pfad} wird erzeugt")
        pruefe(len(antwort.content) > 50, f"{pfad} ist nicht leer")


def test_texte(client: TestClient) -> None:
    abschnitt("Texte")
    from . import main
    pruefe(len(main.TEXTE_STANDARD) > 40, "Standardtexte sind geladen")
    fehlend = [s for s, w in main.TEXTE_STANDARD.items() if not w.strip()]
    pruefe(not fehlend, f"kein Text ist leer ({fehlend[:3]})")
    gefaehrlich = main.t("mein.lead", name="<script>x</script>")
    pruefe("<script>" not in gefaehrlich,
           "eingesetzte Namen werden entschärft")


def test_wiki(client: TestClient) -> None:
    """Wiki: anlegen, anzeigen, bearbeiten, verschieben, suchen, loeschen.

    Geprueft wird zusaetzlich, dass kein Pfad aus dem Wiki-Ordner
    herausfuehrt - das ist die einzige Stelle im Programm, an der ein
    Wert aus der Adresse zu einem Dateizugriff wird.
    """
    abschnitt("Wiki")
    from . import wiki as w

    pruefe(client.get("/wiki").status_code == 200, "Wiki lädt")

    antwort = client.post("/wiki/aktion/neu",
                          data={"name": "Erste Seite", "ordner": "", "art": "seite"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Seite wird angelegt")
    pruefe(os.path.isfile(os.path.join(w.wurzel(), "Erste_Seite.md")),
           "Datei liegt im Wiki-Ordner")

    antwort = client.post("/wiki/aktion/neu",
                          data={"name": "Kapitel", "ordner": "", "art": "ordner"},
                          follow_redirects=False)
    pruefe(os.path.isdir(os.path.join(w.wurzel(), "Kapitel")), "Ordner wird angelegt")

    antwort = client.post("/wiki/aktion/neu",
                          data={"name": "Erste Seite", "ordner": "", "art": "seite"},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "gleicher Name im selben Ordner wird abgewiesen")

    seite = client.get("/wiki/Erste_Seite.md")
    pruefe(seite.status_code == 200, "Seite lässt sich öffnen")
    pruefe("Erste Seite" in seite.text, "Überschrift steht auf der Seite")
    pruefe(client.get("/wiki/Erste_Seite.md?bearbeiten=1").status_code == 200,
           "Bearbeitungsmodus lädt")

    inhalt = ("# Prüfseite\n\nEin **fetter** Text mit "
              "[Link](Erste_Seite.md).\n\n- [ ] offen\n- [x] erledigt\n\n"
              "| A | B |\n| :--- | ---: |\n| 1 | 2 |\n")
    stand = w._pruefsumme(open(os.path.join(w.wurzel(), "Erste_Seite.md"),
                               encoding="utf-8").read())
    antwort = client.post("/wiki/aktion/speichern", data={
        "pfad": "Erste_Seite.md", "ordner": "", "name": "Erste_Seite.md",
        "inhalt": inhalt, "pruefsumme": stand}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Speichern läuft durch")
    text = client.get("/wiki/Erste_Seite.md").text
    pruefe("<strong>fetter</strong>" in text, "Markdown wird dargestellt")
    pruefe('class="wiki-haken' in text, "Kästchen zum Abhaken erscheinen")
    pruefe('class="wiki-haken an"' in text, "ein erledigtes ist als solches erkennbar")
    pruefe("wiki-tabelle" in text, "Tabelle wird dargestellt")
    pruefe('class="liste' not in text,
           "eine Tabelle im Wiki-Text ist keine Programmtabelle")
    pruefe('href="/wiki/Erste_Seite.md"' in text, "interner Link zeigt ins Wiki")

    antwort = client.post("/wiki/aktion/speichern", data={
        "pfad": "Erste_Seite.md", "ordner": "", "name": "Erste_Seite.md",
        "inhalt": "veraltet", "pruefsumme": "ueberholt"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "zwischenzeitliche Änderung wird nicht überschrieben")
    pruefe("<strong>fetter</strong>" in client.get("/wiki/Erste_Seite.md").text,
           "der bisherige Text steht noch da")

    antwort = client.post("/wiki/aktion/speichern", data={
        "pfad": "Erste_Seite.md", "ordner": "", "name": "Erste_Seite.md",
        "inhalt": "# Böse\n\n<script>alarm()</script>\n",
        "pruefsumme": w._pruefsumme(inhalt)}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Speichern mit HTML im Text läuft durch")
    pruefe("<script>alarm()" not in client.get("/wiki/Erste_Seite.md").text,
           "HTML aus einer Wiki-Datei wird nicht ausgeführt")

    # "Auf dieser Seite" erscheint erst ab drei Abschnitten - auf einer
    # eigenen Seite geprueft, damit die anderen Pruefungen ihren Text
    # unveraendert vorfinden.
    client.post("/wiki/aktion/neu", data={"name": "Gliederung", "ordner": "",
                                          "art": "seite"}, follow_redirects=False)
    pruefe("Auf dieser Seite" not in client.get("/wiki/Gliederung.md").text,
           "bei einer Seite ohne Abschnitte bleibt es weg")
    with open(os.path.join(w.wurzel(), "Gliederung.md"), encoding="utf-8") as f:
        stand = w._pruefsumme(f.read())
    client.post("/wiki/aktion/speichern", data={
        "pfad": "Gliederung.md", "ordner": "", "name": "Gliederung.md",
        "inhalt": "# Titel\n\n## Erster Teil\n\nText.\n\n### Unterpunkt\n\n"
                  "Text.\n\n## Zweiter Teil\n\nText.\n",
        "pruefsumme": stand}, follow_redirects=False)
    text = client.get("/wiki/Gliederung.md").text
    pruefe("Auf dieser Seite" in text, "Inhaltsverzeichnis der Seite erscheint")
    pruefe("mit-abschnitten" in text,
           "die Seite bekommt dafür eine eigene Spalte")
    pruefe('href="#erster-teil"' in text, "es verweist auf die Abschnitte")
    pruefe('id="erster-teil"' in text, "die Überschrift trägt die Sprungmarke")
    pruefe('href="#titel"' not in text,
           "die Seitenüberschrift steht nicht im Verzeichnis")
    client.post("/wiki/aktion/loeschen", data={"pfad": "Gliederung.md"},
                follow_redirects=False)

    antwort = client.post("/wiki/aktion/verschieben",
                          data={"pfad": "Erste_Seite.md", "ziel": "Kapitel"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Verschieben läuft durch")
    pruefe(os.path.isfile(os.path.join(w.wurzel(), "Kapitel", "Erste_Seite.md")),
           "Datei liegt jetzt im Unterordner")
    pruefe(client.get("/wiki/Kapitel").status_code == 200, "Ordneransicht lädt")

    antwort = client.post("/wiki/aktion/loeschen", data={"pfad": "Kapitel"},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein voller Ordner wird nicht gelöscht")

    antwort = client.get("/wiki/aktion/herunterladen?pfad=Kapitel/Erste_Seite.md")
    pruefe(antwort.status_code == 200, "Seite lässt sich herunterladen")
    pruefe(b"B\xc3\xb6se" in antwort.content,
           "die heruntergeladene Datei enthält den Text im Original")
    pruefe("attachment" in antwort.headers.get("content-disposition", ""),
           "der Browser bietet sie zum Speichern an")
    pruefe("markdown" in antwort.headers.get("content-type", ""),
           "sie wird als Markdown ausgeliefert")
    antwort = client.get("/wiki/aktion/herunterladen?pfad=../../geheim.db",
                         follow_redirects=False)
    pruefe(antwort.status_code == 303 and "fehler" in antwort.headers.get("location", ""),
           "Herunterladen außerhalb des Wikis wird abgewiesen")

    seite = client.get("/wiki/Kapitel").text
    pruefe("wiki-kacheln" in seite and "wiki-listenansicht" in seite,
           "Ordner zeigt Kachel- und Listenansicht an")
    pruefe("wiki-verzeichnis" in seite, "die Listenansicht ist eine Tabelle")
    pruefe("aktion/herunterladen" in seite,
           "in der Listenansicht steht je Zeile ein Herunterladen-Knopf")
    pruefe("<th>Datei</th>" not in seite,
           "die Spalte „Datei“ ist aus der Listenansicht verschwunden")
    pruefe("<th>Größe</th>" in seite, "die Spalte „Größe“ steht linksbündig")

    # Was die Synology selbst in die Ordner legt, gehoert nicht ins Wiki.
    os.makedirs(os.path.join(w.wurzel(), "@eaDir", "SYNOPHOTO"), exist_ok=True)
    with open(os.path.join(w.wurzel(), "@eaDir", "versteckt.md"), "w",
              encoding="utf-8") as f:
        f.write("# Nicht anzeigen\n")
    seite = client.get("/wiki").text
    pruefe("@eaDir" not in seite, "@eaDir taucht in der Navigation nicht auf")
    pruefe(w.sicherer_pfad("@eaDir/versteckt.md") is None,
           "@eaDir ist auch über die Adresse nicht erreichbar")
    pruefe(client.get("/wiki/@eaDir/versteckt.md").status_code == 404,
           "der Aufruf einer Datei darin läuft ins Leere")
    antwort = client.post("/wiki/aktion/neu",
                          data={"name": "@eaDir", "ordner": "", "art": "ordner"},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein Ordner „@eaDir“ lässt sich nicht anlegen")

    treffer = client.get("/wiki/aktion/suche?q=Böse")
    pruefe(treffer.status_code == 200 and "Erste_Seite.md" in treffer.text,
           "Volltextsuche findet die Seite")

    for boese in ("../../etc/passwd", "..%2f..%2fgeheim", "/etc/passwd"):
        antwort = client.get("/wiki/" + boese, follow_redirects=False)
        pruefe(antwort.status_code in (303, 404, 307),
               f"Pfad „{boese}“ führt nicht aus dem Wiki heraus")
    antwort = client.post("/wiki/aktion/loeschen",
                          data={"pfad": "../../pruefer.db"}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "Löschen außerhalb des Wikis wird abgewiesen")
    pruefe(w.sicherer_pfad("../geheim") is None, "sicherer_pfad weist ../ ab")
    pruefe(w.sicherer_pfad("a/../../b") is None, "sicherer_pfad weist Umwege ab")
    pruefe(w.sicherer_pfad("Kapitel/Erste_Seite.md") == "Kapitel/Erste_Seite.md",
           "sicherer_pfad lässt gültige Pfade durch")

    antwort = client.post("/wiki/aktion/loeschen",
                          data={"pfad": "Kapitel/Erste_Seite.md"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "Seite wird gelöscht")
    pruefe(not os.path.exists(os.path.join(w.wurzel(), "Kapitel", "Erste_Seite.md")),
           "die Datei ist weg")
    antwort = client.post("/wiki/aktion/loeschen", data={"pfad": "Kapitel"},
                          follow_redirects=False)
    pruefe(not os.path.exists(os.path.join(w.wurzel(), "Kapitel")),
           "der nun leere Ordner lässt sich entfernen")


def _konto(client: TestClient, name: str, passwort: str, bereiche: list,
           **zusatz) -> TestClient:
    """Legt ein eingeschraenktes Konto an und meldet es in einem eigenen
    Client an. Gibt den angemeldeten Client zurueck."""
    daten = {"benutzername": name, "passwort": passwort, "rolle": "benutzer",
             "bereiche": bereiche}
    daten.update(zusatz)
    client.post("/einstellungen/benutzer", data=daten)
    sitzung = TestClient(app)
    sitzung.post("/login", data={"benutzername": name, "passwort": passwort},
                 follow_redirects=False)
    return sitzung


def test_loeschrecht(client: TestClient) -> None:
    """Eigene Zeiten darf jeder loeschen, fremde nur mit Berechtigung."""
    abschnitt("Löschrecht für fremde Einträge")

    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, angelegt_am) VALUES "
                    "('Kollegin Meier',1,1,'2026-01-01 08:00')")
        for nr, wer in ((901, "Kollegin Meier"), (902, "Kollegin Meier"),
                        (903, "pruefer"), (904, "pruefer")):
            con.execute(
                "INSERT OR REPLACE INTO eintrag (id, mitarbeiter, datum, monat, "
                "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
                "fingerprint, angelegt_am) VALUES "
                "(?,?, '2026-04-06','2026-04','09:00','10:00','Testperson',"
                "'Besuch',60,1,?, '2026-04-06 09:00')",
                (nr, wer, f"lr{nr}"))

    kollegin = _konto(client, "meier", "meierpasswort", ["datensaetze"],
                      mitarbeiter="Kollegin Meier")

    # --- ohne Recht ---------------------------------------------------------
    kollegin.post("/eintraege/903/loeschen", data={"zurueck": "/eintraege"})
    with db.db() as con:
        da = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=903").fetchone()["c"]
    pruefe(da == 1, "fremder Eintrag bleibt ohne Berechtigung stehen")

    kollegin.post("/eintraege/901/loeschen", data={"zurueck": "/eintraege"})
    with db.db() as con:
        weg = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=901").fetchone()["c"]
    pruefe(weg == 0, "den eigenen Eintrag darf sie immer löschen")

    # Sammellöschung mit gemischter Auswahl: nur der eigene fällt weg
    kollegin.post("/eintraege/loeschen",
                  data={"ids": ["902", "904"], "zurueck": "/eintraege"})
    with db.db() as con:
        eigen = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=902").fetchone()["c"]
        fremd = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=904").fetchone()["c"]
    pruefe(eigen == 0, "Sammellöschung entfernt den eigenen Eintrag")
    pruefe(fremd == 1, "Sammellöschung lässt den fremden Eintrag stehen")

    seite = kollegin.get("/eintraege").text
    pruefe('action="/eintraege/904/loeschen"' not in seite,
           "Löschknopf fehlt bei fremden Zeilen")
    pruefe('value="904"' not in seite, "Kästchen fehlt bei fremden Zeilen")

    # --- mit Recht ----------------------------------------------------------
    with db.db() as con:
        con.execute("UPDATE benutzer SET fremde_loeschen=1 WHERE benutzername='meier'")
    mit_recht = TestClient(app)
    mit_recht.post("/login", data={"benutzername": "meier",
                                   "passwort": "meierpasswort"},
                   follow_redirects=False)
    pruefe('action="/eintraege/904/loeschen"' in mit_recht.get("/eintraege").text,
           "mit Berechtigung erscheint der Löschknopf auch bei fremden Zeilen")
    mit_recht.post("/eintraege/904/loeschen", data={"zurueck": "/eintraege"})
    with db.db() as con:
        fremd = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=904").fetchone()["c"]
    pruefe(fremd == 0, "mit Berechtigung lässt sich ein fremder Eintrag löschen")


def test_eigenes_konto(client: TestClient) -> None:
    """Benutzerverwaltung nur fuer Administratoren, eigenes Konto fuer alle."""
    abschnitt("Eigenes Konto")

    nutzer = _konto(client, "selbst", "altpasswort123",
                    ["datensaetze", "einstellungen"])

    # Die Benutzerverwaltung darf ein normales Konto nicht einmal sehen,
    # obwohl es den Bereich "einstellungen" hat.
    seite = nutzer.get("/einstellungen?bereich=benutzer").text
    pruefe("Neues Konto anlegen" not in seite,
           "Benutzerverwaltung bleibt für normale Konten unsichtbar")
    pruefe("bereich=benutzer" not in seite,
           "und taucht auch nicht als Reiter auf")
    pruefe("Neues Konto anlegen" in client.get(
        "/einstellungen?bereich=benutzer").text,
        "Administratoren sehen die Benutzerverwaltung weiterhin")
    pruefe(nutzer.get("/einstellungen?bereich=email").status_code == 200
           and "smtp_server" not in nutzer.get("/einstellungen?bereich=email").text,
           "E-Mail-Einstellungen bleiben normalen Konten verborgen")

    # Das eigene Konto dagegen pflegt jeder selbst.
    pruefe("/meinbereich/konto" in nutzer.get("/meinbereich").text,
           "„Mein Konto“ steht in Mein Bereich")

    antwort = nutzer.post("/meinbereich/konto", data={
        "email": "", "passwort_alt": "falsch",
        "passwort_neu": "neupasswort123", "passwort_neu2": "neupasswort123"},
        follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "falsches aktuelles Passwort wird abgewiesen")

    antwort = nutzer.post("/meinbereich/konto", data={
        "email": "", "passwort_alt": "altpasswort123",
        "passwort_neu": "neupasswort123", "passwort_neu2": "andersherum123"},
        follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "zwei ungleiche neue Passwörter werden abgewiesen")

    antwort = nutzer.post("/meinbereich/konto", data={
        "email": "", "passwort_alt": "altpasswort123",
        "passwort_neu": "kurz", "passwort_neu2": "kurz"},
        follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "ein zu kurzes Passwort wird abgewiesen")

    # Eine zweite offene Sitzung desselben Kontos, die der Wechsel beenden muss
    zweite = TestClient(app)
    zweite.post("/login", data={"benutzername": "selbst",
                                "passwort": "altpasswort123"},
                follow_redirects=False)
    pruefe(zweite.get("/meinbereich").status_code == 200,
           "zweite Sitzung ist zunächst gültig")

    antwort = nutzer.post("/meinbereich/konto", data={
        "email": "selbst@example.de", "passwort_alt": "altpasswort123",
        "passwort_neu": "neupasswort123", "passwort_neu2": "neupasswort123"},
        follow_redirects=False)
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "Passwortwechsel wird bestätigt")
    pruefe(zweite.get("/meinbereich", follow_redirects=False).status_code == 303,
           "andere offene Sitzungen sind danach beendet")
    pruefe(nutzer.get("/meinbereich").status_code == 200,
           "die eigene Sitzung bleibt bestehen")

    dritte = TestClient(app)
    antwort = dritte.post("/login", data={"benutzername": "selbst",
                                          "passwort": "neupasswort123"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303
           and "fehler" not in antwort.headers.get("location", ""),
           "Anmeldung mit dem neuen Passwort greift")
    with db.db() as con:
        adresse = con.execute(
            "SELECT email FROM benutzer WHERE benutzername='selbst'").fetchone()["email"]
    pruefe(adresse == "selbst@example.de", "die eigene E-Mail-Adresse wird gespeichert")


def test_wiki_schreibrecht(client: TestClient) -> None:
    """Ohne Schreibrecht bleibt das Wiki vollstaendig lesbar."""
    abschnitt("Wiki: Lesen ohne Schreiben")

    client.post("/wiki/aktion/neu", data={"name": "Nur Lesen", "ordner": "",
                                          "art": "seite"})
    leser = _konto(client, "leser", "leserpasswort", ["wiki"],
                   wiki_schreiben="")

    pruefe(leser.get("/wiki").status_code == 200, "das Wiki ist lesbar")
    pruefe(leser.get("/wiki/Nur_Lesen.md").status_code == 200,
           "eine einzelne Seite ist lesbar")
    pruefe(leser.get("/wiki/aktion/herunterladen?pfad=Nur_Lesen.md"
                     ).status_code == 200, "Herunterladen bleibt erlaubt")

    seite = leser.get("/wiki/Nur_Lesen.md").text
    pruefe("?bearbeiten=1" not in seite, "kein Bearbeiten-Knopf")
    pruefe('action="/wiki/aktion/loeschen"' not in seite, "kein Löschen-Knopf")
    pruefe('action="/wiki/aktion/neu"' not in leser.get("/wiki").text,
           "kein Formular zum Anlegen")

    editor = leser.get("/wiki/Nur_Lesen.md?bearbeiten=1")
    pruefe(editor.status_code == 200, "der Editoraufruf endet nicht im Fehler")
    pruefe('action="/wiki/aktion/speichern"' not in editor.text,
           "aber der Editor erscheint nicht")
    pruefe("nicht ändern" in editor.text, "stattdessen steht dort der Grund")

    for pfad, daten in (("/wiki/aktion/speichern",
                         {"pfad": "Nur_Lesen.md", "name": "Nur_Lesen.md",
                          "ordner": "", "text": "geändert", "pruefsumme": "x"}),
                        ("/wiki/aktion/neu",
                         {"name": "Heimlich", "ordner": "", "art": "seite"}),
                        ("/wiki/aktion/loeschen", {"pfad": "Nur_Lesen.md"}),
                        ("/wiki/aktion/verschieben",
                         {"pfad": "Nur_Lesen.md", "ziel": ""})):
        pruefe(leser.post(pfad, data=daten).status_code == 403,
               f"{pfad} ist ohne Schreibrecht gesperrt")

    with db.db() as con:
        noch_da = con.execute(
            "SELECT COUNT(*) c FROM benutzer WHERE benutzername='leser'").fetchone()["c"]
    pruefe(noch_da == 1, "das Konto existiert weiterhin")

    schreiber = _konto(client, "schreiber", "schreiberpasswort", ["wiki"],
                       wiki_schreiben="1")
    pruefe('action="/wiki/aktion/speichern"' in
           schreiber.get("/wiki/Nur_Lesen.md?bearbeiten=1").text,
           "mit Schreibrecht öffnet der Editor")


def test_vorgang_loeschung_im_logbuch(client: TestClient) -> None:
    """Ein geloeschter Vorgang bleibt im Logbuch nachvollziehbar."""
    abschnitt("Gelöschte Vorgänge im Logbuch")

    client.post("/vorgaenge", data={
        "klient": "Testperson", "art": "Antrag gestellt",
        "titel": "Spurloser Antrag", "zustaendig": "pruefer", "wer": "pruefer",
        "beschreibung": "wird gleich gelöscht"})
    with db.db() as con:
        vorgang = con.execute(
            "SELECT id FROM vorgang WHERE titel='Spurloser Antrag'").fetchone()
    pruefe(vorgang is not None, "Vorgang zum Löschen angelegt")
    if not vorgang:
        return
    vid = vorgang["id"]

    client.post(f"/vorgaenge/{vid}/notiz",
                data={"wer": "pruefer", "notiz": "eine Zwischennotiz"})
    with db.db() as con:
        vorher = con.execute(
            "SELECT COUNT(*) c FROM vorgang_log WHERE vorgang_id=?",
            (vid,)).fetchone()["c"]
    pruefe(vorher >= 2, "der Vorgang hat einen Verlauf")

    client.post(f"/vorgaenge/{vid}/loeschen", data={"zurueck": "/vorgaenge"})

    with db.db() as con:
        weg = con.execute("SELECT COUNT(*) c FROM vorgang WHERE id=?",
                          (vid,)).fetchone()["c"]
        zeilen = con.execute(
            "SELECT * FROM vorgang_log WHERE vorgang_titel='Spurloser Antrag'"
        ).fetchall()
    pruefe(weg == 0, "der Vorgang selbst ist gelöscht")
    pruefe(len(zeilen) == vorher + 1,
           "der komplette Verlauf bleibt stehen, plus die Löschzeile")
    pruefe(all(z["vorgang_id"] is None for z in zeilen),
           "die Logzeilen hängen an keinem Vorgang mehr")
    pruefe(any(z["aktion"] == "Vorgang gelöscht" for z in zeilen),
           "die Löschung selbst ist protokolliert")
    pruefe(any(z["wer"] == "pruefer" and z["aktion"] == "Vorgang gelöscht"
               for z in zeilen),
           "und zwar mit dem angemeldeten Konto")

    logbuch = client.get("/vorgaenge/logbuch").text
    pruefe("Vorgang gelöscht" in logbuch, "die Löschung steht im Logbuch")
    pruefe("Spurloser Antrag" in logbuch,
           "der Titel des gelöschten Vorgangs ist noch zu sehen")
    pruefe(f'href="/vorgaenge/{vid}"' not in logbuch,
           "aber nicht mehr als Verweis auf den Vorgang")
    pruefe("eine Zwischennotiz" in logbuch,
           "auch der frühere Verlauf ist noch da")


def test_kfz_erfassungsdesign(client: TestClient) -> None:
    """Die Erfassungsauswahl: Strichsymbole statt Emoji, zwei Gruppen."""
    abschnitt("Fuhrpark: Auswahl der Erfassungsart")
    seite = client.get("/fuhrpark").text

    pruefe('class="kfz-arten"' in seite, "die Auswahl steht im neuen Aufbau")
    pruefe('class="kfz-arten-haupt"' in seite and
           'class="kfz-arten-weitere"' in seite,
           "sie ist in Hauptwege und Weitere geteilt")
    pruefe(seite.count('class="kfz-art ') + seite.count('class="kfz-art h') >= 8
           or seite.count("kfz-a-") >= 8,
           "alle acht Erfassungsarten sind vorhanden")
    for art in ("tanken", "inspektion", "wartung", "reparatur", "reifen",
                "tuev", "sonstiges", "km"):
        pruefe(f"kfz-a-{art}" in seite, f"Art „{art}“ trägt ihren Farbton")

    pruefe(seite.count("<svg") >= 8, "jede Art bringt ein gezeichnetes Symbol mit")
    for emoji in ("⛽", "🔧", "🧰", "🛠", "🛞", "📋", "💶", "📍"):
        pruefe(emoji not in seite, f"kein Emoji {emoji} mehr in der Erfassung")
    pruefe("kfz-kachel" not in seite, "das alte Kachelraster ist weg")

    # Tanken und Kilometerstand stehen oben, die übrigen sechs darunter
    oben = seite.split('class="kfz-arten-weitere"')[0]
    pruefe("kfz-a-tanken" in oben and "kfz-a-km" in oben,
           "Tanken und Kilometerstand stehen in der oberen Gruppe")
    pruefe("kfz-a-tuev" not in oben, "die selteneren Arten stehen darunter")

    gewaehlt = client.get("/fuhrpark?was=tanken").text
    pruefe('class="kfz-art haupt kfz-a-tanken aktiv"' in gewaehlt
           or ("kfz-a-tanken aktiv" in gewaehlt),
           "die gewählte Art ist als aktiv markiert")

    auswertung = client.get("/fuhrpark/auswertung").text
    for emoji in ("⛽", "🔧", "🧰", "🛠", "🛞", "📋", "💶", "📍"):
        pruefe(emoji not in auswertung, f"kein Emoji {emoji} in der Auswertung")


def test_marke(client: TestClient) -> None:
    """Grafiken, Kopfzeile und Informationszeichen."""
    abschnitt("Marke und Kopfzeile")

    for pfad, mindestens in (("/static/favicon.ico", 1000),
                             ("/static/favicon-16x16.png", 200),
                             ("/static/favicon-32x32.png", 500),
                             ("/static/icon-192.png", 5000),
                             ("/static/icon-512.png", 20000),
                             ("/static/apple-touch-icon.png", 5000),
                             ("/static/logo-fuer-dunkel.png", 5000),
                             ("/static/logo-fuer-hell.png", 5000),
                             ("/static/marke-fuer-dunkel.png", 2000),
                             ("/static/marke-fuer-hell.png", 2000)):
        antwort = client.get(pfad)
        pruefe(antwort.status_code == 200 and len(antwort.content) >= mindestens,
               f"{pfad} wird ausgeliefert")

    seite = client.get("/").text
    pruefe("marke-fuer-dunkel.png" in seite and "marke-fuer-hell.png" in seite,
           "die Kopfzeile trägt das Zeichen in beiden Fassungen")
    pruefe("marke-wort" not in seite,
           "in der Kopfzeile steht allein das Zeichen, kein Schriftzug daneben")
    pruefe("logo-fuer-dunkel.png" in seite,
           "der vollständige Schriftzug steht in der Fußzeile")
    # Ohne Versionsanhang hängt der Browser nach einem Bildtausch am alten
    # Stand - genau das war beim Einbau der neuen Grafiken zu sehen.
    for bild in ("marke-fuer-dunkel.png", "logo-fuer-dunkel.png"):
        pruefe(f"{bild}?v=" in seite, f"{bild} trägt einen Versionsanhang")
    pruefe("favicon-32x32.png" in seite, "die kleinen Favicons sind eingebunden")

    anmeldung = TestClient(app).get("/login").text
    pruefe("logo-fuer-dunkel.png?v=" in anmeldung,
           "die Anmeldeseite zeigt den vollständigen Schriftzug")

    stil = client.get("/static/style.css").text
    pruefe("--infozeichen" in stil and ".lead::before" in stil,
           "erklärende Texte tragen ein Informationszeichen")
    # Vorbild ist der Hinweis unter Einstellungen -> System: 12,5px und
    # gedaempfte Farbe. Vorher war .lead 15px und stach daneben heraus.
    pruefe(".lead, .felderklaerung { font-size: 12.5px" in stil,
           "alle erklärenden Texte haben dieselbe Schriftgröße")
    pruefe("position: sticky; top: 0" in stil.replace("\n", " "),
           "die Kopfzeile bleibt beim Rollen stehen")
    pruefe("--kopfhoehe" in stil,
           "ihre Höhe steht als Variable für die klebenden Seitenleisten")
    # Der Erklaerabsatz war eine Flexbox - jedes <strong> darin wurde zu
    # einer eigenen schmalen Spalte. Jetzt sitzt nur das Zeichen absolut.
    einzeilig = stil.replace("\n", " ")
    pruefe(".lead, .felderklaerung { position: relative" in einzeilig,
           "der Erklärabsatz ist wieder ein normaler Textblock")
    pruefe("display: flex; align-items: flex-start; gap: 8px; } .lead::before"
           not in einzeilig,
           "und keine Flexbox mehr, die Auszeichnungen zerlegt")
    # Acht Spalten passen auf dem Telefon nicht nebeneinander; die Tabelle
    # rollt dort in ihrer eigenen Huelle statt sich zu stauchen.
    pruefe(".vorgangstabelle { min-width:" in einzeilig,
           "die Aufgabenliste bekommt am Handy eine Mindestbreite")
    pruefe(".tabellenrolle:has(.vorgangstabelle) { overflow-x: auto; }"
           in einzeilig,
           "und rollt dort seitlich, statt die Spalten zu stauchen")
    pruefe(".tabellenrolle .liste.vorgangstabelle th { white-space: normal; }"
           in einzeilig,
           "ihre Spaltentitel dürfen dort umbrechen")
    # Dasselbe für die Tabellen der Auswertung - acht Spalten.
    pruefe(".auswertungsblatt { min-width:" in einzeilig,
           "die Tabellen der Auswertung rollen in ihrer Hülle")
    # Die linke Spalte braucht min-width: 0, sonst sprengen die rollenden
    # Tabellen darin das Raster.
    pruefe(re.search(r"\.auswertunghaupt\s*\{[^}]*min-width:\s*0", stil)
           is not None,
           "die linke Spalte der Auswertung sprengt das Raster nicht")


def test_einstellungen_aufbau(client: TestClient) -> None:
    """Die Einstellungen stehen in Gruppen statt in einer flachen Liste."""
    abschnitt("Aufbau der Einstellungen")
    seite = client.get("/einstellungen").text
    gruppen = re.findall(r'class="seitenmenue-gruppe">([^<]+)<', seite)
    pruefe(len(gruppen) == 5, f"es gibt fünf Gruppen (sind: {gruppen})")
    for wort in ("Darstellung", "Stammdaten", "Auswahllisten",
                 "Konten und E-Mail", "Wartung"):
        pruefe(wort in gruppen, f"Gruppe „{wort}“ ist vorhanden")
    # Jeder Bereich muss weiterhin erreichbar sein
    for bereich in ("oberflaeche", "quotes", "betreute", "mitarbeiter", "kfz",
                    "vorgangsarten", "leistungen", "benutzer", "email",
                    "vorlagen", "system"):
        pruefe(client.get(f"/einstellungen?bereich={bereich}").status_code == 200,
               f"Bereich „{bereich}“ lädt")


def test_einstellungspunkte(client: TestClient) -> None:
    """Zweite Rechteebene innerhalb der Einstellungen (seit 1.2).

    Wer den Bereich „Einstellungen" hat, muss deshalb noch lange nicht
    jeden Punkt darin sehen. „Oberfläche" bleibt immer sichtbar.
    """
    abschnitt("Punkte in den Einstellungen")
    from .auth import EINST_BEREICHE, EINST_IMMER

    pruefe(EINST_IMMER not in EINST_BEREICHE,
           "„Oberfläche“ steht nicht in der abschaltbaren Liste")
    for schluessel in ("benutzer", "email", "vorlagen"):
        pruefe(schluessel not in EINST_BEREICHE,
               f"„{schluessel}“ hängt an der Rolle, nicht an dieser Liste")

    client.post("/einstellungen/benutzer", data={
        "benutzername": "punkt", "passwort": "punktpasswort",
        "rolle": "benutzer",
        # Alle Bereiche ausser Dateien - der Dateien-Schalter unter
        # „Oberflaeche" muss damit verschwinden, der Wiki-Schalter bleiben.
        "bereiche": ["listenimport", "manuelle_eintraege", "datensaetze",
                     "auswertung", "verwaltungsvorgaenge", "fuhrpark",
                     "wiki", "ideen", "einstellungen"],
        "einst_bereiche": ["betreute", "leistungen"]})

    p = TestClient(app)
    p.post("/login", data={"benutzername": "punkt", "passwort": "punktpasswort"},
           follow_redirects=False)

    seite = p.get("/einstellungen").text
    pruefe("bereich=oberflaeche" in seite, "„Oberfläche“ steht im Menü")
    pruefe("bereich=betreute" in seite and "bereich=leistungen" in seite,
           "die beiden erteilten Punkte stehen im Menü")
    for weg in ("mitarbeiter", "kfz", "vorgangsarten", "quotes", "system"):
        pruefe(f"bereich={weg}" not in seite,
               f"„{weg}“ steht nicht mehr im Menü")
    pruefe("Auswahllisten" in seite,
           "die Gruppenüberschrift bleibt, weil darunter noch etwas steht")
    pruefe("Wartung" not in seite,
           "eine Gruppe ohne Inhalt fällt weg")

    # Direkt eingegebene Adresse: fällt auf „Oberfläche“ zurück statt den
    # gesperrten Punkt zu zeigen.
    pruefe("<h1>Oberfläche</h1>" in p.get("/einstellungen?bereich=mitarbeiter").text,
           "ein gesperrter Punkt fällt auf „Oberfläche“ zurück")
    pruefe("<h1>Betreute Personen</h1>" in p.get("/einstellungen?bereich=betreute").text,
           "ein erlaubter Punkt öffnet")

    # Und die POST-Routen dahinter.
    pruefe(p.post("/einstellungen/mitarbeiter",
                  data={"name": "Schmuggel", "monatsstunden": "1"}
                  ).status_code == 403,
           "ein direkt abgeschicktes Formular des gesperrten Punktes wird abgewiesen")
    pruefe(p.post("/einstellungen/fahrzeug",
                  data={"kennzeichen": "XX-YY 1", "bezeichnung": "Test"}
                  ).status_code == 403,
           "das gilt auch für die Fahrzeugrouten im KFZ-Modul")
    antwort = p.post("/einstellungen/person",
                     data={"name": "Punktperson", "wochenstunden": "3"},
                     follow_redirects=False)
    pruefe(antwort.status_code == 303,
           "der erlaubte Punkt lässt sich weiterhin speichern")

    # Die Ansichtsschalter unter „Oberflaeche" haengen am jeweiligen Bereich.
    seite = p.get("/einstellungen?bereich=oberflaeche").text
    pruefe("wikiliste-knopf" in seite,
           "der Wiki-Schalter steht da, der Bereich ist erteilt")
    pruefe("dateiliste-knopf" not in seite,
           "der Dateien-Schalter fehlt, der Bereich ist es nicht")
    pruefe("thema-knopf" in seite and "breite-knopf" in seite,
           "Darkmode und Breite bleiben für jeden")

    # Kein einziger Haken heisst "nichts" - nicht "alles". Ohne den
    # Rueckfall auf auth.KEINE haette ein leeres Formular vollen Zugriff
    # erteilt, weil ein leeres Feld nach der Speicherregel "alles" meint.
    from . import auth as _auth
    pruefe(_auth.einst_bereiche_speichern([]) == _auth.KEINE,
           "kein Haken bei den Einstellungspunkten heißt „nichts“")
    pruefe(_auth.berechtigungen_speichern([]) == _auth.KEINE,
           "und dasselbe bei den Bereichen")
    pruefe(_auth.einst_bereiche_speichern(list(EINST_BEREICHE)) == "",
           "alle Haken heißen weiterhin „alles“")

    leer = {"rolle": "benutzer", "einst_bereiche": _auth.KEINE,
            "berechtigungen": _auth.KEINE}
    pruefe(_auth.hat_einst_zugriff(leer, "betreute") is False,
           "und dann kommt man an keinen Punkt heran")
    pruefe(_auth.hat_einst_zugriff(leer, _auth.EINST_IMMER) is True,
           "„Oberfläche“ bleibt trotzdem erreichbar")
    pruefe(_auth.hat_zugriff(leer, "wiki") is False,
           "auch kein Bereich ist dann erreichbar")

    # Ein Konto ohne jede Einschraenkung sieht weiterhin alles.
    seite = client.get("/einstellungen").text
    for punkt in EINST_BEREICHE:
        pruefe(f"bereich={punkt}" in seite,
               f"der Administrator sieht „{punkt}“ weiterhin")


def test_meine_zeiten(client: TestClient) -> None:
    """„Mein Bereich" zeigt die eigenen Zeiten - ausnahmslos, auch ohne
    den Bereich „Übersicht (Datensätze)"."""
    abschnitt("Eigene Zeiten in „Mein Bereich“")

    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, monatsstunden, urlaubstage, angelegt_am) "
                    "VALUES ('zeitler',1,1,100,30,'2026-01-01 08:00')")
        con.execute(
            "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
            "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('zeitler','2026-04-06','2026-04','09:00',"
            "'11:00','Testperson','Hausbesuch',120,1,'z1','2026-04-06 09:00')")
        eigen = con.execute(
            "SELECT id FROM eintrag WHERE fingerprint='z1'").fetchone()["id"]
        fremd = con.execute(
            "SELECT id FROM eintrag WHERE mitarbeiter='pruefer' "
            "ORDER BY id LIMIT 1").fetchone()["id"]

    client.post("/einstellungen/benutzer", data={
        "benutzername": "zeitler", "passwort": "zeitpasswort",
        "rolle": "benutzer", "mitarbeiter": "zeitler",
        # Ausdruecklich OHNE den Bereich „Übersicht (Datensätze)".
        "bereiche": ["manuelle_eintraege"]})

    z = TestClient(app)
    z.post("/login", data={"benutzername": "zeitler", "passwort": "zeitpasswort"},
           follow_redirects=False)

    pruefe(z.get("/eintraege").status_code == 403,
           "die Übersicht bleibt gesperrt")
    seite = z.get("/meinbereich").text
    pruefe("Meine Zeiten" in seite, "„Meine Zeiten“ steht trotzdem da")
    pruefe(f"/meinbereich/eintrag/{eigen}/bearbeiten" in seite,
           "der eigene Eintrag lässt sich von dort aus bearbeiten")
    pruefe(f"/meinbereich/eintrag/{eigen}/loeschen" in seite,
           "und löschen")
    pruefe("Hausbesuch" in seite, "der Eintrag steht mit seiner Leistung da")

    # Der Knopf „Zur Übersicht" verschwindet ohne den Bereich.
    pruefe("Zur Übersicht" not in z.get("/").text,
           "„Zur Übersicht“ fehlt im Bestand, wenn der Bereich fehlt")
    pruefe("Zur Übersicht" in client.get("/").text,
           "mit dem Bereich steht er weiterhin da")

    # Bearbeiten: der eigene ja, ein fremder nicht.
    pruefe(z.get(f"/meinbereich/eintrag/{eigen}/bearbeiten").status_code == 200,
           "das Formular zum eigenen Eintrag öffnet")
    antwort = z.get(f"/meinbereich/eintrag/{fremd}/bearbeiten",
                    follow_redirects=False)
    pruefe(antwort.status_code == 303
           and "nicht+dein+Eintrag" in antwort.headers.get("location", ""),
           "ein fremder Eintrag öffnet nicht")

    antwort = z.post(f"/meinbereich/eintrag/{eigen}/bearbeiten", data={
        "datum": "2026-04-06", "start": "09:00", "ende": "12:00", "dauer": "",
        "klient": "Testperson", "beschreibung": "Hausbesuch verlängert",
        "mitarbeiter": "zeitler", "zurueck": "/meinbereich"},
        follow_redirects=False)
    pruefe(antwort.status_code == 303
           and "gespeichert" in antwort.headers.get("location", ""),
           "der eigene Eintrag lässt sich speichern")
    pruefe("Hausbesuch verlängert" in z.get("/meinbereich").text,
           "die Änderung steht danach in der Liste")

    # Und er lässt sich nicht auf jemand anderen umschreiben.
    antwort = z.post(f"/meinbereich/eintrag/{eigen}/bearbeiten", data={
        "datum": "2026-04-06", "dauer": "03:00", "klient": "Testperson",
        "beschreibung": "x", "mitarbeiter": "pruefer",
        "zurueck": "/meinbereich"}, follow_redirects=False)
    pruefe("umschreiben" in antwort.headers.get("location", ""),
           "auf eine andere Person umschreiben geht nicht")

    # Löschen: der fremde nicht, der eigene ja.
    antwort = z.post(f"/meinbereich/eintrag/{fremd}/loeschen",
                     data={"zurueck": "/meinbereich"}, follow_redirects=False)
    pruefe("nicht+dein+Eintrag" in antwort.headers.get("location", ""),
           "ein fremder Eintrag lässt sich nicht löschen")
    z.post(f"/meinbereich/eintrag/{eigen}/loeschen",
           data={"zurueck": "/meinbereich"}, follow_redirects=False)
    with db.db() as con:
        weg = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=?",
                          (eigen,)).fetchone()["c"]
    pruefe(weg == 0, "der eigene Eintrag ist danach weg")

    # Abmelden steht oben in der ersten Karte, nicht mehr klein unten.
    seite = z.get("/meinbereich").text
    kopfkarte = seite.split("</section>")[0]
    pruefe('action="/logout"' in kopfkarte,
           "„Abmelden“ steht in der obersten Karte")
    pruefe("abmelden gross" in seite, "und zwar als großer Knopf")
    pruefe(seite.count('action="/logout"') == 1, "genau einmal")


def test_benutzerverwaltung_aufbau(client: TestClient) -> None:
    """Die Kontenliste klappt auf, statt alles gleichzeitig zu zeigen."""
    abschnitt("Aufbau der Benutzerverwaltung")
    seite = client.get("/einstellungen?bereich=benutzer").text
    pruefe('<details class="konto' in seite,
           "jedes Konto ist ein eigener aufklappbarer Block")
    pruefe('class="konto-kopf"' in seite,
           "die Zeile darüber trägt das Wichtigste")
    pruefe("konto-rechte" in seite,
           "und eine Zusammenfassung der Rechte")
    pruefe('name="einst_bereiche"' in seite,
           "die Punkte der Einstellungen lassen sich hier vergeben")
    pruefe(seite.index("Konten") < seite.index("Neues Konto anlegen"),
           "die vorhandenen Konten stehen über dem Anlegeformular")
    # Der Editor haengt weiterhin am Formular ausserhalb des Rasters.
    pruefe('id="bn-' in seite, "die Felder hängen an einem eigenen Formular")


def test_kontingent_zeitraeume(client: TestClient) -> None:
    """Bewilligte Zeiträume je betreuter Person (seit 1.3).

    Der Kostenträger sagt Wochenstunden und Stundensatz nur befristet zu.
    Geprüft wird beides: die Pflege in den Einstellungen und dass die
    Auswertung Monat für Monat mit den Werten rechnet, die im jeweiligen
    Monat galten.
    """
    abschnitt("Bewilligte Zeiträume")
    from .main import kontingent_im_monat, monatsgrenzen, soll_minuten

    # --- Die Regel selbst ---------------------------------------------------
    pruefe(monatsgrenzen("2025-02") == ("2025-02-01", "2025-02-28"),
           "Monatsgrenzen: Februar endet am 28.")
    pruefe(monatsgrenzen("2024-02") == ("2024-02-01", "2024-02-29"),
           "im Schaltjahr am 29.")
    pruefe(monatsgrenzen("2025-12") == ("2025-12-01", "2025-12-31"),
           "der Dezember schlägt korrekt ins Folgejahr um")

    class Z(dict):
        def __getitem__(self, k):
            return dict.get(self, k)

    erst = Z(von="2024-08-01", bis="2025-07-31", wochenstunden=4, stundensatz=65)
    folge = Z(von="2025-08-01", bis="2025-12-31", wochenstunden=7, stundensatz=70)
    # So kommt die Liste aus der Datenbank: neuester Beginn zuerst.
    liste = [folge, erst]

    pruefe(kontingent_im_monat("2024-09", liste, 0, 0) == (4, 65, True),
           "mitten im ersten Zeitraum gelten dessen Werte")
    pruefe(kontingent_im_monat("2024-08", liste, 0, 0) == (4, 65, True),
           "der Anfangsmonat zählt dazu")
    pruefe(kontingent_im_monat("2025-07", liste, 0, 0) == (4, 65, True),
           "der Endmonat auch")
    pruefe(kontingent_im_monat("2025-08", liste, 0, 0) == (7, 70, True),
           "ab dem Folgebescheid gelten dessen Werte")
    pruefe(kontingent_im_monat("2025-12", liste, 0, 0) == (7, 70, True),
           "bis zu dessen letztem Monat")
    pruefe(kontingent_im_monat("2026-01", liste, 3, 40) == (3, 40, False),
           "danach greift wieder der Grundwert der Person")
    pruefe(kontingent_im_monat("2024-07", liste, 3, 40) == (3, 40, False),
           "und davor genauso")
    pruefe(kontingent_im_monat("2025-05", [], 3, 40) == (3, 40, False),
           "ohne jeden Zeitraum gilt immer der Grundwert")

    offen = Z(von="2026-01-01", bis=None, wochenstunden=9, stundensatz=80)
    pruefe(kontingent_im_monat("2030-06", [offen], 0, 0) == (9, 80, True),
           "ein Zeitraum ohne Ende gilt bis auf Weiteres")

    # Ueberschneidung: der spaeter begonnene gewinnt. Kommt vor, wenn ein
    # Folgebescheid schon laeuft, waehrend der alte formal noch gilt.
    ueberlappt = [Z(von="2025-08-01", bis="2025-12-31", wochenstunden=7, stundensatz=70),
                  Z(von="2024-08-01", bis="2025-08-31", wochenstunden=4, stundensatz=65)]
    pruefe(kontingent_im_monat("2025-08", ueberlappt, 0, 0) == (7, 70, True),
           "bei Überschneidung gewinnt der später begonnene Zeitraum")

    # --- Pflege in den Einstellungen ---------------------------------------
    client.post("/einstellungen/person", data={
        "name": "Michael Müller", "wochenstunden": "0", "stundensatz": "0",
        "abrechenbar": "1"})
    with db.db() as con:
        pid = con.execute("SELECT id FROM person WHERE name='Michael Müller'"
                          ).fetchone()["id"]

    antwort = client.post(f"/einstellungen/person/{pid}/zeitraum", data={
        "von": "2024-08-01", "bis": "2025-07-31", "wochenstunden": "4",
        "stundensatz": "65", "notiz": "Erstbescheid"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "ein Zeitraum lässt sich anlegen")
    pruefe(f"offen={pid}" in antwort.headers.get("location", ""),
           "und die Person ist danach aufgeklappt")
    client.post(f"/einstellungen/person/{pid}/zeitraum", data={
        "von": "2025-08-01", "bis": "2025-12-31", "wochenstunden": "7",
        "stundensatz": "70,00", "notiz": "Fortschreibung"})

    with db.db() as con:
        gespeichert = con.execute(
            "SELECT * FROM person_zeitraum WHERE person_id=? ORDER BY von",
            (pid,)).fetchall()
    pruefe(len(gespeichert) == 2, "beide Zeiträume stehen in der Datenbank")
    pruefe(gespeichert[0]["wochenstunden"] == 4
           and gespeichert[0]["stundensatz"] == 65,
           "mit den eingetragenen Werten")
    pruefe(gespeichert[1]["stundensatz"] == 70,
           "„70,00“ mit Komma wird als Betrag gelesen")

    # Fehlerhafte Eingaben.
    for daten, wort, was in (
            ({"von": "", "bis": "", "wochenstunden": "4"},
             "Ohne+Beginn", "ohne Beginn"),
            ({"von": "2025-01-01", "bis": "quatsch", "wochenstunden": "4"},
             "kein+g", "unlesbares Ende"),
            ({"von": "2025-01-01", "bis": "2024-01-01", "wochenstunden": "4"},
             "liegt+vor+dem+Beginn", "Ende vor Beginn"),
            ({"von": "2025-01-01", "wochenstunden": "999"},
             "Wochenstunden", "unmögliche Wochenstunden"),
            ({"von": "2025-01-01", "wochenstunden": "4", "stundensatz": "abc"},
             "Stundensatz", "unlesbarer Stundensatz")):
        ort = client.post(f"/einstellungen/person/{pid}/zeitraum", data=daten,
                          follow_redirects=False).headers.get("location", "")
        pruefe("fehler=" in ort and wort in ort, f"abgewiesen: {was}")
    with db.db() as con:
        anzahl = con.execute("SELECT COUNT(*) c FROM person_zeitraum "
                             "WHERE person_id=?", (pid,)).fetchone()["c"]
    pruefe(anzahl == 2, "keine der fehlerhaften Eingaben wurde gespeichert")

    # Ändern und Entfernen.
    zid = gespeichert[0]["id"]
    client.post(f"/einstellungen/person/zeitraum/{zid}", data={
        "von": "2024-08-01", "bis": "2025-07-31", "wochenstunden": "4",
        "stundensatz": "66,50", "notiz": "korrigiert"})
    with db.db() as con:
        geaendert = con.execute("SELECT * FROM person_zeitraum WHERE id=?",
                                (zid,)).fetchone()
    pruefe(geaendert["stundensatz"] == 66.5 and geaendert["notiz"] == "korrigiert",
           "ein Zeitraum lässt sich ändern")
    client.post(f"/einstellungen/person/zeitraum/{zid}", data={
        "von": "2024-08-01", "bis": "2025-07-31", "wochenstunden": "4",
        "stundensatz": "65", "notiz": "Erstbescheid"})

    # --- Die Auswertung rechnet damit --------------------------------------
    # Zwei Einheiten, je eine in einem der beiden Zeiträume.
    with db.db() as con:
        for datum, minuten, fp in (("2024-09-10", 120, "mm1"),
                                   ("2025-09-10", 180, "mm2")):
            con.execute(
                "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
                "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "angelegt_am) VALUES ('pruefer',?,?, '09:00','11:00',"
                "'Michael Müller','Hausbesuch',?,1,?,?)",
                (datum, datum[:7], minuten, fp, datum + " 09:00"))

    # Von Hand nachgerechnet: 12 Monate zu 4 Std/Woche plus 5 Monate zu 7.
    soll_4 = soll_minuten(4, "2024-09")
    soll_7 = soll_minuten(7, "2025-09")
    erwartet_soll = soll_4 * 12 + soll_7 * 5
    pruefe(soll_4 == 1035 and soll_7 == 1815,
           f"Monatssoll je Stufe (ist: {soll_4} / {soll_7})")

    seite = client.get("/auswertung?von_jahr=2024&von_monat=08"
                       "&bis_jahr=2025&bis_monat=12").text
    from .parser import hhmm as _hhmm
    pruefe(_hhmm(erwartet_soll) in seite,
           f"das Soll über beide Zeiträume stimmt ({_hhmm(erwartet_soll)})")
    # 2 Std zu 65 EUR plus 3 Std zu 70 EUR.
    pruefe("340,00 €" in seite,
           "der Verdienst rechnet jeden Monat mit dem Satz dieses Monats")
    # Der Hinweis unter der Tabelle. In den Zellen selbst steht seit 1.4.3
    # keine Marke mehr - sie brach die Zeilen um.
    pruefe("Monat für Monat mit den Werten" in seite,
           "die Auswertung weist auf die Staffelung hin")
    pruefe("Grundwert</span>" not in seite,
           "in den Zellen steht keine Marke „Grundwert“ mehr")
    pruefe("2 Sätze" in seite,
           "und nennt statt eines Satzes deren Anzahl")

    # Nur der erste Zeitraum: eine Stufe, ein Satz, kein Hinweis.
    seite = client.get("/auswertung?von_jahr=2024&von_monat=08"
                       "&bis_jahr=2025&bis_monat=07").text
    pruefe(_hhmm(soll_4 * 12) in seite, "über einen Zeitraum allein stimmt es auch")
    pruefe("130,00 €" in seite, "und der Verdienst ebenso")
    pruefe("Monat für Monat mit den Werten" not in seite,
           "dann steht dort auch kein Hinweis")

    # --- Der Grundwert bleibt der Rückfall ---------------------------------
    client.post("/einstellungen/person", data={
        "name": "Ohne Zeitraum", "wochenstunden": "5", "stundensatz": "50",
        "abrechenbar": "1"})
    with db.db() as con:
        con.execute(
            "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
            "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('pruefer','2025-03-04','2025-03','09:00',"
            "'13:00','Ohne Zeitraum','Besuch',240,1,'oz1','2025-03-04 09:00')")
    seite = client.get("/auswertung?von_jahr=2025&von_monat=03"
                       "&bis_jahr=2025&bis_monat=03").text
    pruefe(_hhmm(soll_minuten(5, "2025-03")) in seite,
           "eine Person ohne Zeiträume rechnet unverändert mit dem Grundwert")
    pruefe("200,00 €" in seite, "auch beim Verdienst")

    # --- Die Zeiträume hängen an der Person --------------------------------
    seite = client.get("/einstellungen?bereich=betreute").text
    pruefe('id="person-' in seite and "zeitraumtabelle" in seite,
           "die Zeiträume stehen bei der Person in den Einstellungen")
    pruefe("Fortschreibung" in seite, "mit ihrer Notiz")

    client.post(f"/einstellungen/person/{pid}/loeschen")
    with db.db() as con:
        rest = con.execute("SELECT COUNT(*) c FROM person_zeitraum "
                           "WHERE person_id=?", (pid,)).fetchone()["c"]
    pruefe(rest == 0,
           "mit der Person verschwinden auch ihre Zeiträume (Fremdschlüssel)")


def test_zeitraum_rechte(client: TestClient) -> None:
    """Die Zeitraum-Routen hängen am Einstellungspunkt „Betreute Personen“."""
    abschnitt("Zeiträume: Zugriff")
    client.post("/einstellungen/benutzer", data={
        "benutzername": "ohnebetreute", "passwort": "ohnepasswort",
        "rolle": "benutzer", "bereiche": ["einstellungen"],
        "einst_bereiche": ["leistungen"]})
    o = TestClient(app)
    o.post("/login", data={"benutzername": "ohnebetreute",
                           "passwort": "ohnepasswort"}, follow_redirects=False)
    pruefe(o.post("/einstellungen/person/1/zeitraum",
                  data={"von": "2025-01-01", "wochenstunden": "4"}
                  ).status_code == 403,
           "ohne den Punkt „Betreute Personen“ lässt sich kein Zeitraum anlegen")
    pruefe(o.post("/einstellungen/person/zeitraum/1",
                  data={"von": "2025-01-01", "wochenstunden": "4"}
                  ).status_code == 403,
           "und keiner ändern")
    pruefe(o.post("/einstellungen/person/zeitraum/1/loeschen").status_code == 403,
           "und keiner löschen")


def test_monatsbloecke(client: TestClient) -> None:
    """Die Auswertung teilt den Zeitraum in Monatsblöcke (seit 1.4).

    Für einen Nachweis gegenüber dem Kostenträger reicht die Summe über
    den ganzen Zeitraum nicht - es zählt der einzelne Monat, und der
    rechnet mit dem Satz, der in genau diesem Monat bewilligt war.
    """
    abschnitt("Auswertung Monat für Monat")
    from .main import soll_minuten
    from .parser import hhmm as _hhmm

    client.post("/einstellungen/person", data={
        "name": "Blockmann", "wochenstunden": "0", "stundensatz": "0",
        "abrechenbar": "1"})
    with db.db() as con:
        pid = con.execute("SELECT id FROM person WHERE name='Blockmann'"
                          ).fetchone()["id"]
    client.post(f"/einstellungen/person/{pid}/zeitraum", data={
        "von": "2024-08-01", "bis": "2025-07-31", "wochenstunden": "4",
        "stundensatz": "60,49"})
    client.post(f"/einstellungen/person/{pid}/zeitraum", data={
        "von": "2025-08-01", "bis": "2026-07-31", "wochenstunden": "3",
        "stundensatz": "75"})
    with db.db() as con:
        for datum, minuten, fp in (("2024-09-10", 120, "bl1"),
                                   ("2025-09-10", 180, "bl2")):
            con.execute(
                "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
                "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "angelegt_am) VALUES ('pruefer',?,?, '09:00','11:00',"
                "'Blockmann','Hausbesuch',?,1,?,?)",
                (datum, datum[:7], minuten, fp, datum + " 09:00"))

    seite = client.get("/auswertung?von_jahr=2024&von_monat=08"
                       "&bis_jahr=2025&bis_monat=10&klient=Blockmann").text

    # 15 Monate, jeder mit einem Soll - also 15 Blöcke.
    pruefe(seite.count('class="karte monatsblock') == 15,
           f"je Monat ein Block (sind: {seite.count('class=\"karte monatsblock')})")
    for wort in ("August 2024", "Januar 2025", "Juli 2025", "Oktober 2025"):
        pruefe(f"<h3>{wort}</h3>" in seite, f"der Block „{wort}“ steht da")

    # Der Monat aus dem ersten Zeitraum: 2 Std zu 60,49 EUR.
    pruefe("120,98 €" in seite,
           "September 2024 rechnet mit dem Satz des ersten Zeitraums")
    # Der Monat aus dem zweiten: 3 Std zu 75 EUR.
    pruefe("225,00 €" in seite,
           "September 2025 rechnet mit dem Satz des zweiten Zeitraums")
    pruefe("345,98 €" in seite, "die Summe stimmt")

    # Ein Monat ohne Zeiten bleibt stehen, solange etwas bewilligt war -
    # sonst faellt die Luecke nicht auf.
    pruefe("ohne-zeiten" in seite,
           "Monate ohne erfasste Zeiten bleiben stehen")
    pruefe("In diesem Monat ist nichts erfasst" in seite,
           "und sagen das auch")

    # Das Soll je Monat richtet sich nach dem jeweiligen Zeitraum.
    pruefe(_hhmm(soll_minuten(4, "2024-09")) in seite
           and _hhmm(soll_minuten(3, "2025-09")) in seite,
           "beide Kontingentstufen tauchen als Soll auf")

    # Der Überblick darüber - seit 1.4.1 eine Karte mit Kennzahlen und
    # einer Zeile je Person, statt drei Kästen nebeneinander.
    pruefe("<h2>Überblick</h2>" in seite, "es gibt einen Überblick")
    pruefe('class="abschnittsband"' in seite and "Monat für Monat" in seite,
           "und ein Band, das die Monatsblöcke davon abgrenzt")
    gesamt_soll = soll_minuten(4, "2024-09") * 12 + soll_minuten(3, "2025-09") * 3
    pruefe(_hhmm(gesamt_soll) in seite,
           f"mit dem Soll über alle Monate ({_hhmm(gesamt_soll)})")
    pruefe("15 Monate" in seite, "und der Zahl der Monate")

    # Die Seitenspalte: Kontingentbalken, Sprungliste, Bescheide.
    pruefe("auswertungsraster" in seite and "auswertunghaupt" in seite,
           "die Seite steht in zwei Spalten, über ihre ganze Länge")
    pruefe("<h2>Stundenkontingent</h2>" in seite and "standliste" in seite,
           "der Kontingentbalken steht in der Seitenspalte")
    pruefe("auslastung" not in seite,
           "und nicht mehr zusätzlich in der Tabellenzelle")
    pruefe("monatsspur" in seite and 'href="#monat-2025-09"' in seite,
           "die Monate sind als Sprungliste verlinkt")
    pruefe(seite.count('id="monat-') == 15,
           "jeder Block trägt seine Sprungmarke")
    pruefe("<h2>Bewilligt</h2>" in seite and "bescheidliste" in seite,
           "die zugrunde liegenden Bescheide stehen daneben")
    # Maßangaben: einmal je Spalte im Kopf, nicht in jeder Zelle.
    pruefe(seite.count('class="massangabe">Std<') >= 3,
           "die Zeitspalten tragen ihre Einheit im Kopf")
    pruefe('class="massangabe">€<' in seite,
           "die Geldspalten ebenso")
    pruefe('class="kmass">Std<' in seite,
           "die Kennzahlen tragen ihre Einheit hinter der Zahl")
    pruefe("Std</span></td>" not in seite,
           "in den Zellen selbst steht die Einheit nicht")
    pruefe("01.08.2024" in seite and "31.07.2025" in seite,
           "mit ihrem Zeitraum")
    pruefe("4 Std/Woche" in seite, "und ihren Werten")

    # Bei einem einzelnen Monat waere der Block eine Wiederholung.
    einer = client.get("/auswertung?von_jahr=2024&von_monat=09"
                       "&bis_jahr=2024&bis_monat=09&klient=Blockmann").text
    pruefe("monatsblock" not in einer,
           "bei einem einzigen Monat entfällt die Aufteilung")
    pruefe('class="abschnittsband"' not in einer, "und das Band dazu auch")
    pruefe("<h2>Überblick</h2>" in einer, "der Überblick bleibt")

    # Der Grundwert wird als solcher gekennzeichnet, damit man einen
    # fehlenden Bescheid nicht für eine Bewilligung hält.
    client.post("/einstellungen/person", data={
        "name": "Grundmann", "wochenstunden": "2", "stundensatz": "40",
        "abrechenbar": "1"})
    with db.db() as con:
        con.execute(
            "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
            "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('pruefer','2024-09-12','2024-09','09:00',"
            "'10:00','Grundmann','Besuch',60,1,'gr1','2024-09-12 09:00')")
    seite = client.get("/auswertung?von_jahr=2024&von_monat=08"
                       "&bis_jahr=2024&bis_monat=10&klient=Grundmann").text
    pruefe(">Grundwert<" in seite,
           "ein Monat ohne Zeitraum ist als Grundwert markiert")
    pruefe("40,00 €" in seite, "und rechnet mit dem Grundsatz")


def test_versionen() -> None:
    """Die Versionszaehlung: beginnt bei 0.1, endet beim aktuellen Stand."""
    abschnitt("Versionen")
    from .changelog import CHANGELOG
    from .main import VERSION

    nummern = [e["version"] for e in CHANGELOG]
    # Bewusst keine feste Nummer: sonst muesste diese Pruefung bei jeder
    # Auslieferung mitgeaendert werden und waere damit wertlos. Geprueft
    # wird die Form und dass Anwendung und Changelog dasselbe sagen.
    pruefe(re.fullmatch(r"\d+\.\d+(\.\d+)?", VERSION) is not None,
           f"die Version hat die erwartete Form (ist: {VERSION})")
    pruefe(nummern[0] == "0.1", "der Verlauf beginnt bei 0.1")
    pruefe(nummern[-1] == VERSION,
           "der jüngste Eintrag entspricht der Version der Anwendung")
    pruefe(len(nummern) == len(set(nummern)), "keine Nummer kommt doppelt vor")
    # Die Erzählung "acht Meilensteine 0.1 bis 0.8, dann die fertige
    # Fassung" muss halten: alles VOR dem ersten 1.x-Eintrag ist 0.x, und
    # danach kommt nichts mehr aus der 0er-Reihe. So bleibt die Prüfung
    # gültig, egal wie viele Auslieferungen nach 1.0 noch folgen.
    erste_eins = next((i for i, n in enumerate(nummern)
                       if not n.startswith("0.")), len(nummern))
    pruefe(all(n.startswith("0.") for n in nummern[:erste_eins]),
           "die gesamte Vorgeschichte liegt unterhalb von 1.0")
    pruefe(not any(n.startswith("0.") for n in nummern[erste_eins:]),
           "nach 1.0 folgt kein Eintrag mehr aus der 0er-Reihe")
    pruefe(not any("Beta" in n for n in nummern), "kein „Beta“ mehr im Verlauf")

    # Die acht Meilensteine müssen alle vorkommen
    for meilenstein in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8"):
        pruefe(meilenstein in nummern, f"Meilenstein {meilenstein} ist vorhanden")

    # Innerhalb einer Reihe darf keine Lücke stehen
    luecken = []
    for reihe in ("0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8"):
        unter = sorted(int(n.rsplit(".", 1)[1]) for n in nummern
                       if n.startswith(reihe + ".") and n.count(".") == 2)
        if unter and unter != list(range(1, len(unter) + 1)):
            luecken.append(reihe)
    pruefe(not luecken, f"keine Lücken in den Unterversionen (offen: {luecken})")


def test_bearbeitungsrecht(client: TestClient) -> None:
    """Fremde Eintraege bearbeiten braucht ein eigenes Recht."""
    abschnitt("Bearbeitungsrecht für fremde Einträge")

    with db.db() as con:
        for nr, wer in ((911, "Kollegin Meier"), (912, "pruefer")):
            con.execute(
                "INSERT OR REPLACE INTO eintrag (id, mitarbeiter, datum, monat, "
                "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
                "fingerprint, angelegt_am) VALUES "
                "(?,?, '2026-05-04','2026-05','09:00','10:00','Testperson',"
                "'Besuch',60,1,?, '2026-05-04 09:00')", (nr, wer, f"br{nr}"))

    kollegin = _konto(client, "meier2", "meier2passwort", ["datensaetze"],
                      mitarbeiter="Kollegin Meier")

    # --- ohne Recht ---------------------------------------------------------
    antwort = kollegin.get("/eintraege/912/bearbeiten", follow_redirects=False)
    pruefe(antwort.status_code == 303,
           "das Formular für einen fremden Eintrag öffnet nicht")
    pruefe("Berechtigung" in antwort.headers.get("location", ""),
           "und nennt den Grund")

    kollegin.post("/eintraege/912/bearbeiten", data={
        "datum": "2026-05-04", "start": "09:00", "ende": "12:00",
        "klient": "Gekapert", "beschreibung": "verändert",
        "mitarbeiter": "pruefer", "zurueck": "/eintraege"})
    with db.db() as con:
        z = con.execute("SELECT klient FROM eintrag WHERE id=912").fetchone()
    pruefe(z["klient"] == "Testperson",
           "auch ein direkt abgeschicktes Formular ändert nichts")

    pruefe(kollegin.get("/eintraege/911/bearbeiten").status_code == 200,
           "den eigenen Eintrag darf sie bearbeiten")
    kollegin.post("/eintraege/911/bearbeiten", data={
        "datum": "2026-05-04", "start": "09:00", "ende": "11:00",
        "klient": "Testperson", "beschreibung": "eigene Änderung",
        "mitarbeiter": "Kollegin Meier", "zurueck": "/eintraege"})
    with db.db() as con:
        z = con.execute("SELECT dauer_min, beschreibung FROM eintrag "
                        "WHERE id=911").fetchone()
    pruefe(z["dauer_min"] == 120 and z["beschreibung"] == "eigene Änderung",
           "die eigene Änderung wird gespeichert")

    # Den eigenen Eintrag auf jemand anderen umschreiben ist ebenfalls
    # ein Zugriff auf fremde Daten und muss scheitern.
    kollegin.post("/eintraege/911/bearbeiten", data={
        "datum": "2026-05-04", "start": "09:00", "ende": "11:00",
        "klient": "Testperson", "beschreibung": "umgeschrieben",
        "mitarbeiter": "pruefer", "zurueck": "/eintraege"})
    with db.db() as con:
        z = con.execute("SELECT mitarbeiter FROM eintrag WHERE id=911").fetchone()
    pruefe(z["mitarbeiter"] == "Kollegin Meier",
           "ein Eintrag lässt sich nicht auf eine andere Person umschreiben")

    seite = kollegin.get("/eintraege").text
    pruefe("/eintraege/912/bearbeiten" not in seite,
           "der Bearbeiten-Knopf fehlt bei fremden Zeilen")
    pruefe("/eintraege/911/bearbeiten" in seite,
           "bei den eigenen steht er weiterhin")

    # --- mit Recht ----------------------------------------------------------
    with db.db() as con:
        con.execute("UPDATE benutzer SET fremde_bearbeiten=1 "
                    "WHERE benutzername='meier2'")
    mit_recht = TestClient(app)
    mit_recht.post("/login", data={"benutzername": "meier2",
                                   "passwort": "meier2passwort"},
                   follow_redirects=False)
    pruefe(mit_recht.get("/eintraege/912/bearbeiten").status_code == 200,
           "mit Berechtigung öffnet das Formular auch für fremde Einträge")
    pruefe("/eintraege/912/bearbeiten" in mit_recht.get("/eintraege").text,
           "und der Knopf erscheint in der Liste")

    # Löschen und Bearbeiten sind getrennt: dieses Konto darf jetzt
    # bearbeiten, aber weiterhin nicht löschen.
    mit_recht.post("/eintraege/912/loeschen", data={"zurueck": "/eintraege"})
    with db.db() as con:
        da = con.execute("SELECT COUNT(*) c FROM eintrag WHERE id=912").fetchone()["c"]
    pruefe(da == 1, "das Bearbeitungsrecht erlaubt noch kein Löschen")


def test_mehrfacherfassung(client: TestClient) -> None:
    """Mehrere Zeiteintraege in einem Rutsch."""
    abschnitt("Mehrere Einträge auf einmal")

    def vorher() -> int:
        with db.db() as con:
            return con.execute("SELECT COUNT(*) c FROM eintrag").fetchone()["c"]

    stand = vorher()
    antwort = client.post("/erfassung", data={
        "mitarbeiter": "pruefer",
        "datum": ["01.06.2026", "01.06.2026", "02.06.2026"],
        "klient": ["Testperson", "Testperson", "Testperson"],
        "start": ["09:00", "11:00", "14:00"],
        "ende": ["10:30", "12:00", "15:15"],
        "beschreibung": ["Besuch A", "Besuch B", "Besuch C"]},
        follow_redirects=False)
    ziel = antwort.headers.get("location", "")
    pruefe(vorher() == stand + 3, "drei Zeilen werden in einem Rutsch gespeichert")
    pruefe("3+Eintr" in ziel or "3 Eintr" in ziel,
           "die Rückmeldung nennt die Anzahl")
    pruefe(ziel.endswith("#erfassen"),
           "die Rückkehr springt zum Formular statt an den Seitenanfang")

    # Leere Zeilen einfach überspringen
    stand = vorher()
    client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": ["03.06.2026", "", ""],
        "klient": ["Testperson", "", ""], "start": ["09:00", "", ""],
        "ende": ["10:00", "", ""], "beschreibung": ["Einzeln", "", ""]},
        follow_redirects=False)
    pruefe(vorher() == stand + 1, "leere Zeilen werden übersprungen")

    # Halb gefüllte Zeile: nichts wird gespeichert, die Meldung nennt die Zeile
    stand = vorher()
    antwort = client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": ["04.06.2026", "05.06.2026"],
        "klient": ["Testperson", ""], "start": ["09:00", "09:00"],
        "ende": ["10:00", "10:00"], "beschreibung": ["", ""]},
        follow_redirects=False)
    pruefe(vorher() == stand,
           "bei einem Fehler wird gar nichts gespeichert, auch nicht die gute Zeile")
    pruefe("Zeile+2" in antwort.headers.get("location", ""),
           "die Meldung nennt die betroffene Zeile")

    # Zwei gleiche Zeilen gehen seit 0.8.9 durch: die Dublettenprüfung der
    # manuellen Erfassung ist entfallen, derselbe Besuch am selben Tag zur
    # selben Uhrzeit kommt in der Praxis vor.
    stand = vorher()
    client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": ["06.06.2026", "06.06.2026"],
        "klient": ["Testperson", "Testperson"], "start": ["09:00", "09:00"],
        "ende": ["10:00", "10:00"], "beschreibung": ["gleich", "gleich"]},
        follow_redirects=False)
    pruefe(vorher() == stand + 2, "zwei gleiche Zeilen werden beide gespeichert")
    pruefe('name="trotzdem"' not in client.get("/").text,
           "der Haken „trotzdem speichern“ steht nicht mehr im Formular")

    # Eine einzelne Zeile verhält sich wie früher
    stand = vorher()
    client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": "07.06.2026", "klient": "Testperson",
        "start": "08:00", "ende": "09:30", "beschreibung": "einzeln"},
        follow_redirects=False)
    pruefe(vorher() == stand + 1, "eine einzelne Zeile geht weiterhin durch")


def test_zeiterfassung_auswahl(client: TestClient) -> None:
    """Mitarbeiter als Auswahlfeld, beide Überschriften gleich groß."""
    abschnitt("Zeiterfassung: Auswahl und Aufbau")
    seite = client.get("/").text

    pruefe("<h1>Manuelle Zeiterfassung</h1>" in seite
           and "<h1>Zeitlisten einlesen</h1>" in seite,
           "beide Überschriften stehen auf derselben Stufe")
    pruefe(seite.count('name="mitarbeiter"') >= 2,
           "beide Karten haben ein Mitarbeiter-Feld")
    pruefe('<input type="text" name="mitarbeiter"' not in seite,
           "keins davon ist mehr ein freies Textfeld")
    pruefe(seite.count('<select name="mitarbeiter"') == 2,
           "beide sind Auswahlfelder")
    pruefe("pruefer" in seite, "das Team steht zur Auswahl")
    pruefe('id="zeile-mehr"' in seite, "es gibt einen Knopf für weitere Zeilen")
    pruefe('id="erfassen"' in seite, "die Sprungmarke für die Rückkehr ist da")

    # Ein Name, der nur noch in alten Zeiten vorkommt, bleibt erreichbar
    with db.db() as con:
        con.execute(
            "INSERT OR REPLACE INTO eintrag (id, mitarbeiter, datum, monat, "
            "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
            "fingerprint, angelegt_am) VALUES (921,'Ehemalige Kollegin',"
            "'2026-02-02','2026-02','09:00','10:00','Testperson','Besuch',"
            "60,1,'ehem1','2026-02-02 09:00')")
    seite = client.get("/").text
    pruefe("Ehemalige Kollegin" in seite and "nicht mehr im Team" in seite,
           "Namen ohne Teameintrag stehen in einer eigenen Gruppe")


def test_logbuch_darstellung(client: TestClient) -> None:
    """Das Logbuch ist nach Tagen gegliedert und faerbt die Aktionen."""
    abschnitt("Darstellung des Logbuchs")
    seite = client.get("/vorgaenge/logbuch").text

    pruefe('class="logtag"' in seite, "es gibt Tagesüberschriften")
    pruefe("Heute · " in seite or "Heute&#" in seite,
           "der heutige Tag ist als solcher benannt")
    pruefe('class="logzeit"' in seite and 'class="loguhr"' in seite,
           "Zeit und handelnde Person stehen in einer eigenen Spalte")
    pruefe('class="loginhalt"' in seite, "der Inhalt steht in der zweiten Spalte")
    pruefe("la-neu" in seite, "die Aktionsmarke trägt eine Farbklasse")
    pruefe(seite.count("28.08.2026, ") == 0 and "Uhr</span>" not in seite,
           "das Datum steht nicht mehr in jeder einzelnen Zeile")

    from .vorgaenge import nach_tagen, tag_wort
    import datetime as _dt
    heute = _dt.date.today()
    pruefe(tag_wort(heute.isoformat(), heute).startswith("Heute"),
           "tag_wort erkennt heute")
    pruefe(tag_wort((heute - _dt.timedelta(days=1)).isoformat(),
                    heute).startswith("Gestern"),
           "tag_wort erkennt gestern")
    pruefe("," in tag_wort((heute - _dt.timedelta(days=9)).isoformat(), heute),
           "ältere Tage bekommen den Wochentag")
    pruefe(nach_tagen([]) == [], "eine leere Liste ergibt keine Gruppe")

    # Auch die Betreutenansicht und die Vorgangsansicht gruppieren
    person = client.get("/vorgaenge/person?name=Testperson").text
    pruefe('class="logtag"' in person,
           "die Betreutenansicht gliedert ihren Verlauf ebenso")
    pruefe('class="personenzahlen"' in person,
           "ihre Kopfkarte steht in der neuen Gliederung")


def test_dateien(client: TestClient) -> None:
    """Dateiverwaltung: hochladen, ordnen, ausliefern, verlinken.

    Der Schwerpunkt liegt auf der Sicherheitsgrenze: erlaubte Endungen,
    Ausliefern mit festem Inhaltstyp, und dass kein Pfad aus dem
    Dateiordner herausfuehrt.
    """
    abschnitt("Dateien")
    from . import dateien as d

    bild = open(os.path.join(os.path.dirname(__file__), "static",
                             "icon-192.png"), "rb").read()

    pruefe(client.get("/dateien").status_code == 200, "Dateiseite lädt")

    # --- Hochladen ----------------------------------------------------------
    antwort = client.post("/dateien/hochladen", files=[
        ("datei", ("Testbild.png", bild, "image/png")),
        ("datei", ("Bericht.pdf", b"%PDF-1.4\ntest", "application/pdf")),
        ("datei", ("Schadcode.exe", b"MZ", "application/octet-stream")),
    ], data={"ordner": ""}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "Hochladen antwortet mit Umleitung")
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Testbild.png")),
           "das Bild liegt im Dateiordner")
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Bericht.pdf")),
           "die PDF-Datei ebenfalls")
    pruefe(not os.path.isfile(os.path.join(d.wurzel(), "Schadcode.exe")),
           "eine nicht erlaubte Dateiart wird abgewiesen")
    pruefe("Nicht+übernommen" in antwort.headers.get("location", "")
           or "Nicht" in antwort.headers.get("location", ""),
           "und die Meldung sagt das auch")

    # Gleicher Name darf nicht überschreiben
    client.post("/dateien/hochladen",
                files=[("datei", ("Testbild.png", bild, "image/png"))],
                data={"ordner": ""})
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Testbild (2).png")),
           "eine gleichnamige Datei wird durchnummeriert statt überschrieben")

    # --- Ordner -------------------------------------------------------------
    client.post("/dateien/ordner", data={"name": "Fotos 2026", "ordner": ""})
    pruefe(os.path.isdir(os.path.join(d.wurzel(), "Fotos 2026")),
           "ein Ordner lässt sich anlegen")
    antwort = client.post("/dateien/ordner", data={"name": "Fotos 2026",
                                                   "ordner": ""},
                          follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "derselbe Ordnername wird ein zweites Mal abgewiesen")

    seite = client.get("/dateien?ordner=Fotos+2026").text
    pruefe(seite.count("Fotos 2026") >= 1, "der Ordner lässt sich öffnen")

    # --- Verschieben und Umbenennen ----------------------------------------
    client.post("/dateien/umbenennen", data={
        "pfad": "Testbild.png", "name": "Gruppenfoto.png",
        "ziel_ordner": "Fotos 2026", "ordner": ""})
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Fotos 2026", "Gruppenfoto.png")),
           "Umbenennen und Verschieben in einem Schritt")
    antwort = client.post("/dateien/umbenennen", data={
        "pfad": "Fotos 2026/Gruppenfoto.png", "name": "Gruppenfoto.exe",
        "ziel_ordner": "", "ordner": ""}, follow_redirects=False)
    pruefe("fehler" in antwort.headers.get("location", ""),
           "in eine nicht erlaubte Endung umbenennen geht nicht")

    # --- Ausliefern ---------------------------------------------------------
    antwort = client.get("/dateien/holen/Fotos%202026/Gruppenfoto.png")
    pruefe(antwort.status_code == 200, "das Bild wird ausgeliefert")
    pruefe(antwort.headers.get("content-type") == "image/png",
           "mit dem Inhaltstyp aus unserer Liste")
    pruefe(antwort.headers.get("x-content-type-options") == "nosniff",
           "und mit nosniff")
    pruefe("attachment" not in antwort.headers.get("content-disposition", ""),
           "Bilder gehen inline raus")
    pruefe(antwort.content == bild, "der Inhalt stimmt")

    client.post("/dateien/hochladen",
                files=[("datei", ("Konzept.docx", b"PK\x03\x04",
                                  "application/octet-stream"))],
                data={"ordner": ""})
    antwort = client.get("/dateien/holen/Konzept.docx")
    pruefe("attachment" in antwort.headers.get("content-disposition", ""),
           "Office-Dateien gehen als Download raus, nicht inline")

    # --- Sicherheitsgrenze --------------------------------------------------
    # "..": bewusst kodiert als %2e%2e. Unkodiert loest der HTTP-Client
    # den Schritt nach oben schon selbst auf, die Anfrage kaeme also nie
    # in dieser Form am Server an - die Pruefung liefe ins Leere.
    for versuch in ("../texte/quotes.txt", "../../db/test.db", "%2e%2e",
                    "%2e%2e%2f%2e%2e%2fdb", ".geheim.png", "@eaDir/x.png",
                    "holen/x.png"):
        antwort = client.get(f"/dateien/holen/{versuch}", follow_redirects=False)
        pruefe(antwort.status_code in (303, 404),
               f"„{versuch}“ wird abgewiesen")
    for versuch in ("../ausserhalb", "..", ".versteckt", "@eaDir"):
        pruefe(d.sicherer_pfad(versuch) is None,
               f"sicherer_pfad weist „{versuch}“ ab")
    pruefe(d.sicherer_pfad("Fotos 2026/Gruppenfoto.png") == "Fotos 2026/Gruppenfoto.png",
           "ein gültiger Pfad kommt unverändert zurück")
    pruefe(d.sicherer_name("Bild.exe") is None,
           "sicherer_name weist eine nicht erlaubte Endung ab")
    for endung, kategorie in (("mp4", "video"), ("svg", "bild"),
                              ("eps", "grafik"), ("dotx", "text")):
        pruefe(endung in d.ARTEN and d.ARTEN[endung][0] == kategorie,
               f"„{endung}“ ist erlaubt und zählt als {kategorie}")
    # SVG darf, aber nur mit Sandbox - sonst könnte ein direkter Aufruf
    # Skript aus der Datei ausführen.
    client.post("/dateien/hochladen", files=[
        ("datei", ("Zeichnung.svg",
                   b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                   "image/svg+xml"))], data={"ordner": ""})
    antwort = client.get("/dateien/holen/Zeichnung.svg")
    pruefe(antwort.status_code == 200
           and antwort.headers.get("content-type") == "image/svg+xml",
           "SVG wird ausgeliefert")
    pruefe("sandbox" in antwort.headers.get("content-security-policy", ""),
           "aber mit einer Sandbox, die Skript darin abschaltet")
    pruefe(d.sicherer_name("Hilfeplan Anna 2026.pdf") == "Hilfeplan Anna 2026.pdf",
           "Leerzeichen im Dateinamen bleiben erhalten")

    # --- Löschen ------------------------------------------------------------
    client.post("/dateien/loeschen",
                data={"pfad": "Fotos 2026/Gruppenfoto.png", "ordner": ""})
    pruefe(not os.path.isfile(os.path.join(d.wurzel(), "Fotos 2026",
                                           "Gruppenfoto.png")),
           "eine Datei lässt sich löschen")
    client.post("/dateien/loeschen", data={"pfad": "Fotos 2026", "ordner": ""})
    pruefe(not os.path.isdir(os.path.join(d.wurzel(), "Fotos 2026")),
           "ein leerer Ordner ebenfalls")

    # Seit 0.9.2 geht auch ein Ordner mit Inhalt weg - anders als im Wiki,
    # wo ein Ordner ein Kapitel ist. Die Sicherheitsabfrage im Browser
    # nennt dafür die Zahl der Einträge.
    os.makedirs(os.path.join(d.wurzel(), "Voll", "Tiefer"), exist_ok=True)
    for ziel in (("Voll", "a.png"), ("Voll", "Tiefer", "b.png")):
        with open(os.path.join(d.wurzel(), *ziel), "wb") as f:
            f.write(bild)
    antwort = client.post("/dateien/loeschen",
                          data={"pfad": "Voll", "ordner": ""},
                          follow_redirects=False)
    pruefe(not os.path.isdir(os.path.join(d.wurzel(), "Voll")),
           "auch ein voller Ordner lässt sich löschen")
    pruefe("hinweis" in antwort.headers.get("location", ""),
           "und die Rückmeldung bestätigt es")
    pruefe("3" in antwort.headers.get("location", ""),
           "die Meldung nennt die Zahl der mitgelöschten Einträge")

    # --- Verlinkung im Wiki -------------------------------------------------
    seite = client.get("/dateien").text
    pruefe("![Testbild (2).png](/dateien/holen/" in seite
           or "](/dateien/holen/" in seite,
           "zu jeder Datei steht ein fertiger Markdown-Schnipsel")

    client.post("/wiki/aktion/neu", data={"name": "Mit Bild", "ordner": "",
                                          "art": "seite"})
    editor = client.get("/wiki/Mit_Bild.md?bearbeiten=1").text
    pruef = re.search(r'name="pruefsumme" value="([^"]*)"', editor).group(1)
    client.post("/wiki/aktion/speichern", data={
        "pfad": "Mit_Bild.md", "name": "Mit_Bild.md", "ordner": "",
        "pruefsumme": pruef,
        "inhalt": "# Mit Bild\n\n![Bild](/dateien/holen/Bericht.pdf)\n\n"
                  "[Andere Seite](andere.md)\n"})
    html = client.get("/wiki/Mit_Bild.md").text
    pruefe('src="/dateien/holen/Bericht.pdf"' in html,
           "ein Verweis auf die Dateiverwaltung bleibt im Wiki unverändert")
    pruefe("/wiki/dateien/" not in html,
           "er wird nicht als Wiki-Pfad missverstanden")
    pruefe('href="/wiki/andere.md"' in html,
           "normale Wiki-Verweise werden weiterhin aufgelöst")

    # --- Aufbau wie im Wiki -------------------------------------------------
    seite = client.get("/dateien").text
    pruefe('class="wiki-seitenleiste karte"' in seite,
           "die Seite hat eine Seitenleiste wie das Wiki")
    pruefe('class="wiki-baum"' in seite, "darin steht der Dateibaum")
    pruefe('id="dateifeld"' in seite and 'id="ordnerknopf"' in seite,
           "Hochladen und Ordner anlegen stehen als Symbolknöpfe darin")
    pruefe("dateien-listenansicht" in seite
           and "dateien-kachelansicht" in seite,
           "beide Ansichten stehen im HTML, umgeschaltet wird per CSS")
    pruefe('data-dateiliste="liste"' in client.get("/dateien").text
           or 'data-dateiliste="liste"' in client.get("/").text,
           "die Listenansicht ist der Standard")
    pruefe('id="datei-verschieben"' in seite,
           "das Formular fürs Ziehen liegt außerhalb der übrigen Formulare")
    pruefe(seite.count('draggable="true"') >= 2,
           "Einträge lassen sich ziehen")
    # Der Ablageort und die beiden anderen Hinweistexte in der
    # Seitenleiste sind mit 1.1.2 auf Timos Wunsch entfallen.
    pruefe(d.wurzel() not in seite,
           "die Hinweistexte in der Seitenleiste sind entfernt")

    # --- Von Hand abgelegte Dateien ----------------------------------------
    # Genau der Weg über die Dateifreigabe: etwas liegt einfach im Ordner.
    os.makedirs(os.path.join(d.wurzel(), "Von Hand"), exist_ok=True)
    with open(os.path.join(d.wurzel(), "Von Hand", "Notiz.rtf"), "w") as f:
        f.write("Text")
    with open(os.path.join(d.wurzel(), "Von Hand", "Bild.png"), "wb") as f:
        f.write(bild)
    seite = client.get("/dateien?ordner=Von+Hand").text
    pruefe("Notiz.rtf" in seite,
           "eine von Hand abgelegte Datei mit unbekannter Endung wird angezeigt")
    pruefe("Bild.png" in seite, "eine bekannte ebenfalls")
    pruefe(client.get("/dateien/holen/Von%20Hand/Notiz.rtf",
                      follow_redirects=False).status_code == 303,
           "ausgeliefert wird die unbekannte Datei aber nicht")
    pruefe(client.get("/dateien/holen/Von%20Hand/Bild.png").status_code == 200,
           "die bekannte schon")

    # --- Verschieben (das schickt das Ziehen ab) ---------------------------
    client.post("/dateien/verschieben",
                data={"pfad": "Von Hand/Bild.png", "ziel": "", "ordner": ""})
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Bild.png")),
           "Verschieben auf die oberste Ebene")
    client.post("/dateien/verschieben",
                data={"pfad": "Bild.png", "ziel": "Von Hand", "ordner": ""})
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Von Hand", "Bild.png")),
           "und wieder zurück in den Ordner")
    for pfad, ziel, was in (
            ("Von Hand", "Von Hand", "ein Ordner nicht in sich selbst"),
            ("Von Hand", "Gibtsnicht", "kein Verschieben in ein fehlendes Ziel"),
            ("../texte/quotes.txt", "", "kein Pfad aus dem Ordner heraus")):
        antwort = client.post("/dateien/verschieben",
                              data={"pfad": pfad, "ziel": ziel, "ordner": ""},
                              follow_redirects=False)
        pruefe("fehler" in antwort.headers.get("location", ""),
               f"Verschieben: {was}")

    # --- Ordner: Umbenennen und Verlinken ----------------------------------
    os.makedirs(os.path.join(d.wurzel(), "Kapitel"), exist_ok=True)
    with open(os.path.join(d.wurzel(), "Kapitel", "drin.png"), "wb") as f:
        f.write(bild)
    seite = client.get("/dateien").text
    pruefe('data-schnipsel="[Kapitel](/dateien?ordner=Kapitel)"' in seite,
           "auch ein Ordner hat einen Markdown-Schnipsel fürs Wiki")
    pruefe('data-umbenennen="Kapitel"' in seite,
           "und einen Knopf zum Umbenennen")
    client.post("/dateien/umbenennen", data={
        "pfad": "Kapitel", "name": "Kapitel neu", "ziel_ordner": "", "ordner": ""})
    pruefe(os.path.isdir(os.path.join(d.wurzel(), "Kapitel neu")),
           "ein Ordner lässt sich umbenennen")
    pruefe(os.path.isfile(os.path.join(d.wurzel(), "Kapitel neu", "drin.png")),
           "sein Inhalt wandert mit")
    client.post("/dateien/loeschen", data={"pfad": "Kapitel neu", "ordner": ""})

    # --- Kopfzeile ohne Zählung --------------------------------------------
    seite = client.get("/dateien").text
    kopf = seite.split('class="kopfzeile"')[1].split("</div>")[0]
    pruefe("summe" not in kopf, "die Zählung oben rechts ist entfallen")
    pruefe("dateiliste-knopf" in seite,
           "der Ansichtsumschalter steht weiterhin auf der Seite")

    # --- Umschalter in den Einstellungen ------------------------------------
    einst = client.get("/einstellungen").text
    pruefe("Dateien-Ansicht" in einst and "dateiliste-knopf" in einst,
           "der Umschalter steht unter Einstellungen → Oberfläche")

    # --- Berechtigung -------------------------------------------------------
    ohne = _konto(client, "ohnedateien", "ohnedateienpasswort", ["datensaetze"])
    pruefe(ohne.get("/dateien").status_code == 403,
           "ohne den Bereich „Dateien“ ist die Seite gesperrt")
    pruefe(ohne.get("/dateien/holen/Bericht.pdf").status_code == 403,
           "auch das Ausliefern einer einzelnen Datei")
    pruefe("/dateien" not in ohne.get("/eintraege").text.split("<nav>")[1]
           .split("</nav>")[0],
           "und der Menüpunkt fehlt")


def test_menue_reihenfolge(client: TestClient) -> None:
    """Reihenfolge im Hauptmenü und die Bezeichnung „Aufgaben“."""
    abschnitt("Menü: Reihenfolge und Bezeichnungen")
    seite = client.get("/").text
    nav = seite.split("<nav>")[1].split("</nav>")[0]
    punkte = re.findall(r">([^<>]+)</a>", nav)
    pruefe(punkte == ["Arbeitszeit", "Aufgaben", "Fuhrpark", "Dateien", "Wiki"],
           f"das Menü steht in der erwarteten Reihenfolge (ist: {punkte})")
    pruefe("Verwaltungsvorgänge" not in nav,
           "„Verwaltungsvorgänge“ steht nicht mehr im Menü")
    pruefe(nav.index("Dateien") < nav.index("Wiki"),
           "„Dateien“ steht vor „Wiki“")

    # Der Pfad und der Berechtigungsschlüssel bleiben, nur die Beschriftung
    # ändert sich - sonst verlöre jedes eingeschränkte Konto seinen Zugriff.
    pruefe('href="/vorgaenge"' in nav, "der Pfad /vorgaenge bleibt")
    from .auth import BEREICHE
    pruefe("verwaltungsvorgaenge" in BEREICHE,
           "der Berechtigungsschlüssel bleibt unverändert")
    pruefe(BEREICHE["verwaltungsvorgaenge"] == "Aufgaben",
           "nur seine Beschriftung heißt jetzt „Aufgaben“")
    pruefe("<h1>Aufgaben</h1>" in client.get("/vorgaenge").text,
           "die Seite selbst heißt ebenfalls „Aufgaben“")

    # Der Changelog stand bis 1.1.1 als Symbol in der Kopfzeile. Jetzt
    # haengt er als Link in der Fusszeile hinter der Versionsnummer.
    from .main import VERSION
    kopf = seite.split("</header>")[0]
    fuss = seite.split("<footer>")[1].split("</footer>")[0]
    pruefe('href="/changelog"' not in kopf,
           "der Changelog steht nicht mehr in der Kopfzeile")
    pruefe('href="/changelog"' in fuss,
           "der Changelog steht in der Fußzeile")
    pruefe(fuss.index(VERSION) < fuss.index('href="/changelog"'),
           "und zwar hinter der Versionsnummer")
    pruefe(client.get("/changelog").status_code == 200,
           "die Changelog-Seite ist weiterhin erreichbar")


def test_markdown() -> None:
    """Der eigene Markdown-Wandler - er ersetzt eine Bibliothek und muss
    deshalb selbst geprueft werden."""
    abschnitt("Markdown")
    from . import markdown as md
    html = str(md.zu_html("# Titel\n\nText mit *kursiv*, **fett** und `code`."))
    pruefe("<h1>Titel</h1>" in html, "Überschrift")
    pruefe("<em>kursiv</em>" in html and "<strong>fett</strong>" in html,
           "kursiv und fett")
    pruefe("<code>code</code>" in html, "Code im Fließtext")

    # Seit 1.1.2 ist jeder Zeilenumbruch im Quelltext auch einer in der
    # Anzeige. Vorher lief der Absatz durch.
    html = str(md.zu_html("Musterweg 1\n12345 Musterstadt\n"))
    pruefe("<br>" in html, "ein einfacher Zeilenumbruch wird angezeigt")
    pruefe(html.count("<p>") == 1,
           "die Zeilen bleiben trotzdem ein Absatz")
    html = str(md.zu_html("Erster Absatz.\n\nZweiter Absatz.\n"))
    pruefe(html.count("<p>") == 2 and "<br>" not in html,
           "eine Leerzeile trennt weiterhin zwei Absätze")

    html = str(md.zu_html("- eins\n- zwei\n  - zwei a\n"))
    pruefe(html.count("<ul>") == 2 and html.count("<li>") == 3,
           "verschachtelte Aufzählung")

    html = str(md.zu_html("1. eins\n2. zwei\n"))
    pruefe("<ol>" in html, "nummerierte Aufzählung")

    html = str(md.zu_html("| A | B |\n| --- | ---: |\n| 1 | 2 |\n"))
    pruefe("<table" in html and html.count("<td") == 2, "Tabelle")
    pruefe('class="rechts"' in html, "Ausrichtung der Spalte")
    pruefe("wiki-tabellenrolle" in html, "Tabelle steht in ihrem eigenen Kasten")

    verzeichnis = []
    html = str(md.zu_html("# Groß & Ölig\n\n## Zweiter\n\n## Zweiter\n",
                          None, verzeichnis))
    pruefe([u["marke"] for u in verzeichnis] == ["gross-oelig", "zweiter", "zweiter-2"],
           "Sprungmarken sind lesbar und eindeutig")
    pruefe('<h1 id="gross-oelig">' in html, "die Kennung steht am Element")
    pruefe("<h2>" in str(md.zu_html("## Ohne Verzeichnis")),
           "ohne Verzeichnis bleibt das HTML unverändert schlank")

    html = str(md.zu_html("> zitiert\n\n---\n\n```\ncode\n```\n"))
    pruefe("<blockquote>" in html and "<hr>" in html and "<pre>" in html,
           "Zitat, Trennlinie und Codeblock")

    html = str(md.zu_html("<script>alarm()</script> & <b>x</b>"))
    pruefe("<script>" not in html and "<b>" not in html,
           "HTML im Text wird entschärft")
    pruefe("&amp;" in html, "kaufmännisches Und wird entschärft")

    html = str(md.zu_html("Datei 01_notfall_und_krisen bleibt heil."))
    pruefe("<em>" not in html, "Unterstriche in Dateinamen bleiben stehen")

    html = str(md.zu_html("*Status:* [x] Aktiv | [ ] Pausiert"))
    pruefe(html.count("wiki-haken") == 2,
           "auch im Fließtext wird [x] zum Kästchen")
    pruefe('wiki-haken an' in html, "das gesetzte Kästchen ist markiert")
    pruefe("[x]" not in str(md.zu_html("- [x] fertig")),
           "in der Aufzählung bleibt kein [x] als Text stehen")
    pruefe("[x]" in str(md.zu_html("Im Code: `[x]`")),
           "in Codeauszeichnung bleibt [x] unangetastet")
    pruefe('<a href="/wiki/z.md">x</a>' in
           str(md.zu_html("[x](z.md)", lambda a: ("/wiki/" + a, False))),
           "ein Link namens [x] bleibt ein Link")

    html = str(md.zu_html("Schreib an info@praxis-erdmann.com."))
    pruefe('href="mailto:info@praxis-erdmann.com"' in html,
           "E-Mail-Adressen werden verlinkt")
    pruefe(str(md.zu_html("Version 2.9 und @eaDir")).count("mailto") == 0,
           "was keine Adresse ist, wird nicht verlinkt")

    # Verschachtelte Listen tragen die Fuehrungslinien der Darstellung -
    # geprueft wird die Struktur, die das Stylesheet dafuer braucht.
    html = str(md.zu_html("* eins\n\t* zwei\n\t\t* drei\n"))
    pruefe(html.count("<ul>") == 3, "drei Ebenen aus Tabulator-Einrückung")
    pruefe("<li>eins\n<ul>" in html,
           "die Unterliste steht im übergeordneten Punkt")

    html = str(md.zu_html("[Ziel](unter/seite.md)",
                          lambda a: ("/wiki/" + a, False)))
    pruefe('href="/wiki/unter/seite.md"' in html, "Link wird aufgelöst")
    html = str(md.zu_html("[Weg](https://example.de)",
                          lambda a: (a, True)))
    pruefe('rel="noopener noreferrer"' in html, "externer Link öffnet sicher")


# --- Ablauf ------------------------------------------------------------------

def main_lauf() -> int:
    print("Dein Weg Toolkit – automatische Prüfung")
    print(f"Testordner: {_ORDNER}")

    # Als Kontext verwenden: nur dann laeuft die Startroutine der Anwendung,
    # die das Datenbankschema anlegt und den ersten Zugang erzeugt.
    with TestClient(app) as client:
        _durchlauf(client)

    print("\n" + "=" * 60)
    if _ERGEBNIS["fehler"]:
        print(f"{len(_ERGEBNIS['fehler'])} Prüfung(en) fehlgeschlagen, "
              f"{_ERGEBNIS['ok']} in Ordnung:")
        for f in _ERGEBNIS["fehler"]:
            print(f"  - {f}")
    else:
        print(f"Alle {_ERGEBNIS['ok']} Prüfungen bestanden.")
    print("=" * 60)
    return 1 if _ERGEBNIS["fehler"] else 0


def _durchlauf(client: TestClient) -> None:
    try:
        test_ohne_anmeldung(client)
        anmelden(client)
        testdaten_anlegen()

        test_vorlagen_vollstaendig(client)
        test_seiten(client)
        test_import(client)
        test_manueller_eintrag(client)
        test_zeiterfassung(client)
        test_leistungen(client)
        test_sprueche(client)
        test_verwaltungsvorgang(client)
        test_kfz(client)
        test_menue(client)
        test_export(client)
        test_sammelloeschen(client)
        test_texte(client)
        test_wiki(client)
        test_markdown()
        test_oberflaeche(client)
        test_symbole(client)
        test_sicherung(client)
        test_rechte(client)
        test_loeschrecht(client)
        test_eigenes_konto(client)
        test_wiki_schreibrecht(client)
        test_vorgang_loeschung_im_logbuch(client)
        test_kfz_erfassungsdesign(client)
        test_bearbeitungsrecht(client)
        test_mehrfacherfassung(client)
        test_zeiterfassung_auswahl(client)
        test_logbuch_darstellung(client)
        test_dateien(client)
        test_menue_reihenfolge(client)
        test_marke(client)
        test_einstellungen_aufbau(client)
        test_einstellungspunkte(client)
        test_meine_zeiten(client)
        test_benutzerverwaltung_aufbau(client)
        test_kontingent_zeitraeume(client)
        test_zeitraum_rechte(client)
        test_monatsbloecke(client)
        test_versionen()
    except Exception:
        print("\nUnerwarteter Abbruch:")
        traceback.print_exc()
        _ERGEBNIS["fehler"].append("Abbruch mit Ausnahme")


if __name__ == "__main__":
    code = main_lauf()
    shutil.rmtree(_ORDNER, ignore_errors=True)
    sys.exit(code)
