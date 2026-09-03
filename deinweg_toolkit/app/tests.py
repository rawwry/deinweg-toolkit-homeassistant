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
import datetime as dt
import re
import shutil
import sys
import tempfile
import traceback


# --- Umgebung vorbereiten, bevor die Anwendung geladen wird ------------------

_ORDNER = tempfile.mkdtemp(prefix="toolkit-test-")
for unter in ("db", "texte", "wiki", "files", "sicherungen"):
    os.makedirs(os.path.join(_ORDNER, unter), exist_ok=True)

os.environ.update({
    "DB_PFAD": os.path.join(_ORDNER, "db", "test.db"),
    "SPRUCH_DATEI": os.path.join(_ORDNER, "texte", "quotes.txt"),
    "IDEEN_DATEI": os.path.join(_ORDNER, "texte", "ideen.txt"),
    "STRINGS_DATEI": os.path.join(_ORDNER, "texte", "strings.txt"),
    "WIKI_PFAD": os.path.join(_ORDNER, "wiki"),
    "FILES_PFAD": os.path.join(_ORDNER, "files"),
    "SICHERUNG_PFAD": os.path.join(_ORDNER, "sicherungen"),
    "WECKER_INTERVALL": "0",
    "ADMIN_BENUTZERNAME": "pruefer",
    "ADMIN_PASSWORT": "pruefpasswort",
})

from fastapi.testclient import TestClient  # noqa: E402

from . import auth  # noqa: E402
from . import db  # noqa: E402
from . import mail  # noqa: E402
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
        # ⚠️ Drei Punkte, nicht mehr: die Datenpflege ist mit 1.16 in die
        # Einstellungen gezogen.
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
    # ⚠️ Der Stift springt zur Zeile, nicht an den Seitenanfang: die Zeile
    # trägt eine Sprungmarke, der Bearbeiten-Link zeigt darauf.
    nr_erster = len(liste) - 1
    pruefe(f'id="spruch-{nr_erster}"' in seite,
           "jede Spruchzeile trägt eine Sprungmarke")
    pruefe(f"spruch_bearbeiten={nr_erster}#spruch-{nr_erster}" in seite,
           "und der Bearbeiten-Stift springt genau dorthin")
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
                             # Seit 1.17.1 sind Logo und Bildmarke SVG - sie
                             # skalieren damit auf jedem Bildschirm sauber.
                             ("/static/logo-fuer-dunkel.svg", 5000),
                             ("/static/logo-fuer-hell.svg", 5000),
                             ("/static/marke-fuer-dunkel.svg", 1000),
                             ("/static/marke-fuer-hell.svg", 1000)):
        antwort = client.get(pfad)
        pruefe(antwort.status_code == 200 and len(antwort.content) >= mindestens,
               f"{pfad} wird ausgeliefert")

    seite = client.get("/").text
    pruefe("marke-fuer-dunkel.svg" in seite and "marke-fuer-hell.svg" in seite,
           "die Kopfzeile trägt das Zeichen in beiden Fassungen")
    pruefe("marke-wort" not in seite,
           "in der Kopfzeile steht allein das Zeichen, kein Schriftzug daneben")
    pruefe("logo-fuer-dunkel.svg" in seite,
           "der vollständige Schriftzug steht in der Fußzeile")
    # Kein PNG mehr: die vier alten Dateien sind ersetzt, nicht ergänzt.
    pruefe("logo-fuer-dunkel.png" not in seite
           and "marke-fuer-dunkel.png" not in seite,
           "und nirgends mehr als PNG")
    pruefe(client.get("/static/logo-fuer-dunkel.png").status_code == 404,
           "die alten PNG-Dateien sind weg")
    # Ohne Versionsanhang hängt der Browser nach einem Bildtausch am alten
    # Stand - genau das war beim Einbau der neuen Grafiken zu sehen.
    for bild in ("marke-fuer-dunkel.svg", "logo-fuer-dunkel.svg"):
        pruefe(f"{bild}?v=" in seite, f"{bild} trägt einen Versionsanhang")
    pruefe("favicon-32x32.png" in seite, "die kleinen Favicons sind eingebunden")

    # ⚠️ Eine SVG-Schrift, die als <text> mit einer nicht mitgelieferten
    # Hausschrift dasteht, sieht im Browser irgendwie aus - nur nicht wie
    # das Logo. In den ausgelieferten Dateien muss die Schrift deshalb in
    # Pfaden vorliegen.
    for bild in ("logo-fuer-dunkel.svg", "logo-fuer-hell.svg",
                 "marke-fuer-dunkel.svg", "marke-fuer-hell.svg"):
        quelle = client.get("/static/" + bild).text
        pruefe("<text" not in quelle and "font-family" not in quelle,
               f"{bild} enthält keine lebende Schrift, nur Pfade")

    anmeldung = TestClient(app).get("/login").text
    pruefe("logo-fuer-dunkel.svg?v=" in anmeldung,
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
    # Die Aufgabenliste ist seit 1.8 keine Tabelle mehr, sondern ein
    # Raster aus Karten - eine Tabelle mit acht Spalten war auf dem
    # Telefon ohnehin nur noch eine Rollflaeche.
    pruefe(".vorgangstabelle" not in einzeilig,
           "die achtspaltige Aufgabentabelle ist entfallen")
    pruefe(re.search(r"\.vorgangskarten \{\s*display: grid", stil) is not None,
           "die Vorgänge stehen als Karten in einem Raster")
    # Höchstens zwei nebeneinander: bei vier wird jede Karte so schmal,
    # dass Titel und Notiz umbrechen.
    pruefe("grid-template-columns: repeat(2, minmax(0, 1fr));" in einzeilig,
           "höchstens zwei Karten nebeneinander")
    pruefe(".vorgangskarte.vk-ueberfaellig { border-left-color: var(--dopp); }"
           in einzeilig,
           "eine überfällige Karte ist am Balken links zu erkennen")
    # Dasselbe für die Tabellen der Auswertung - acht Spalten.
    # ⚠️ Diese eine Tabelle steht auf table-layout: auto. Bei fixed muss
    # man jede Spaltenbreite raten, und eine zu knapp geratene Spalte
    # laesst eine nicht umbrechende Zelle ueberlaufen - genau daher kamen
    # die seitlichen Rollbalken, die auch bei breitem Fenster blieben.
    pruefe("liste.auswertungsblatt { table-layout: auto;" in einzeilig,
           "die Auswertungstabelle rechnet ihre Spalten aus dem Inhalt")
    # ⚠️ Kein nowrap in dieser Tabelle: eine Zelle, die nicht umbrechen
    # darf, setzt eine Mindestbreite, die die Tabelle nicht unterschreiten
    # kann - genau daran hingen die hartnäckigen Rollbalken.
    pruefe(re.search(r"\.liste\.auswertungsblatt td,\s*"
                     r"\.tabellenrolle \.liste\.auswertungsblatt th \{\s*"
                     r"white-space: normal", stil) is not None,
           "in der Auswertungstabelle bricht alles um")
    # Ab 760px kann die Hülle gar nicht mehr rollen - dort ist ein
    # Rollbalken immer ein Rundungsfehler und nie eine echte Überbreite.
    pruefe(re.search(r"@media \(min-width: 760px\) \{\s*"
                     r"\.tabellenrolle:has\(\.auswertungsblatt\) \{\s*"
                     r"overflow-x: clip", stil) is not None,
           "und die Hülle kann auf dem Schreibtisch gar nicht rollen")
    pruefe(".tabellenrolle:has(.auswertungsblatt) { overflow-x: auto; }"
           in einzeilig,
           "und rollt in ihrer Hülle, wenn es wirklich zu eng wird")
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
    # Die Kopfkarte ist seit 1.7 die erste Karte der Seite; davor steht
    # nur noch der Spruch.
    kopfkarte = seite.split('class="karte meinkopf"')[1].split("</section>")[0]
    pruefe('action="/logout"' in kopfkarte,
           "„Abmelden“ steht in der Kopfkarte")
    pruefe(seite.index("meinkopf") < seite.index("Bewilligungen im Blick")
           if "Bewilligungen im Blick" in seite else True,
           "die Kopfkarte steht vor den Bewilligungen")
    pruefe('class="knopf abmelden"' in seite,
           "und zwar als eigener Knopf in der Kopfzeile")
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
    pruefe('class="massangabe">Name<' in seite
           and 'class="massangabe">Anz<' in seite,
           "auch die beiden Spalten ohne Einheit tragen eine zweite Zeile")
    # Die Spalte "Mitarbeiter" ist mit 1.4.4 entfallen - wer die Zeit
    # erfasst hat, steht in der Übersicht, nicht in der Auswertung.
    pruefe("<th>Mitarbeiter" not in seite,
           "die Spalte „Mitarbeiter“ steht nicht mehr in der Auswertung")
    kopf = seite.split("<thead>")[1].split("</thead>")[0]
    spalten = kopf.count("<th>") + kopf.count("<th ")
    pruefe(spalten == 7, f"sieben Spalten (sind: {spalten})")
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


def test_mehrere_betreute(client: TestClient) -> None:
    """Der Filter der Auswertung nimmt mehrere Betreute auf einmal."""
    abschnitt("Filter: mehrere Betreute")
    with db.db() as con:
        for name in ("Filter Eins", "Filter Zwei", "Filter Drei"):
            con.execute("INSERT OR IGNORE INTO person (name, wochenstunden, "
                        "stundensatz, aktiv, abrechenbar, angelegt_am) "
                        "VALUES (?,4,50,1,1,'2025-01-01 08:00')", (name,))
        for nr, name in enumerate(("Filter Eins", "Filter Zwei", "Filter Drei"), 1):
            con.execute(
                "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
                "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
                "angelegt_am) VALUES ('pruefer','2025-05-05','2025-05','09:00',"
                "'10:00',?,'Besuch',60,1,?,'2025-05-05 09:00')",
                (name, f"fi{nr}"))

    def tabelle(html):
        # Nur der Tabellenkörper - im Filter stehen ohnehin alle Namen als
        # Kästchen, danach kann man nicht prüfen.
        return html.split("<tbody>")[1].split("</tbody>")[0]

    zwei = client.get("/auswertung?klient=Filter+Eins&klient=Filter+Zwei").text
    körper = tabelle(zwei)
    pruefe("Filter Eins" in körper and "Filter Zwei" in körper,
           "beide gewählten Personen stehen in der Auswertung")
    pruefe("Filter Drei" not in körper, "die dritte nicht")
    pruefe("2 betreute Personen" in zwei,
           "die Chipleiste nennt die Zahl der Personen")

    einer = tabelle(client.get("/auswertung?klient=Filter+Eins").text)
    pruefe("Filter Zwei" not in einer, "eine einzelne Person filtert wie bisher")
    pruefe("Filter Eins" in einer, "und wird namentlich genannt")

    # Das Auswahlfeld selbst.
    pruefe('name="klient" value="Filter Eins"' in zwei
           and 'class="wahlliste"' in zwei,
           "die Auswahl steht als Kästchenliste im Filter")
    pruefe(zwei.count('type="checkbox" name="klient"') >= 3,
           "mit einem Kästchen je Person")
    pruefe("2 Personen</span>" in zwei.replace("\n", "").replace("  ", ""),
           "und zeigt zugeklappt, wie viele gewählt sind")
    pruefe('class="wahlliste-feld"' in zwei,
           "über der Liste steht ein Suchfeld zum Tippen")

    # Dieselbe Mehrfachauswahl für die Mitarbeiter.
    zwei_leute = client.get("/auswertung?mitarbeiter=pruefer").text
    pruefe(zwei_leute.count('type="checkbox" name="mitarbeiter"') >= 1,
           "auch die Mitarbeiter stehen als Kästchenliste da")
    pruefe("Mitarbeiter" in zwei_leute, "mit ihrem eigenen Feld")

    # Auch die Übersicht und der Export folgen der Mehrfachauswahl.
    liste = tabelle(client.get(
        "/eintraege?klient=Filter+Eins&klient=Filter+Zwei").text)
    pruefe("Filter Eins" in liste and "Filter Drei" not in liste,
           "die Übersicht filtert genauso")
    csv = client.get("/export.csv?klient=Filter+Eins&klient=Filter+Zwei").text
    pruefe("Filter Eins" in csv and "Filter Zwei" in csv
           and "Filter Drei" not in csv,
           "und der Export nimmt beide mit")

    # Der Schalter steht in einer eigenen Zeile unter den Feldern.
    pruefe('class="filter-fuss"' in zwei,
           "Schalter und Knöpfe stehen in einer eigenen Zeile")


def test_bewilligungsstand(client: TestClient) -> None:
    """Eine ausgelaufene Bewilligung muss sofort auffallen."""
    abschnitt("Bewilligungsstand")
    heute = dt.date.today()
    vorbei = (heute - dt.timedelta(days=40)).isoformat()
    frueher = (heute - dt.timedelta(days=400)).isoformat()
    kuenftig_von = (heute + dt.timedelta(days=30)).isoformat()

    client.post("/einstellungen/person", data={
        "name": "Abgelaufen Anton", "wochenstunden": "0", "stundensatz": "0",
        "abrechenbar": "1"})
    client.post("/einstellungen/person", data={
        "name": "Kuenftig Karla", "wochenstunden": "0", "stundensatz": "0",
        "abrechenbar": "1"})
    client.post("/einstellungen/person", data={
        "name": "Laufend Lena", "wochenstunden": "0", "stundensatz": "0",
        "abrechenbar": "1"})
    with db.db() as con:
        ids = {r["name"]: r["id"] for r in con.execute(
            "SELECT id, name FROM person WHERE name IN "
            "('Abgelaufen Anton','Kuenftig Karla','Laufend Lena')")}
    client.post(f"/einstellungen/person/{ids['Abgelaufen Anton']}/zeitraum",
                data={"von": frueher, "bis": vorbei, "wochenstunden": "4",
                      "stundensatz": "60"})
    client.post(f"/einstellungen/person/{ids['Kuenftig Karla']}/zeitraum",
                data={"von": kuenftig_von, "wochenstunden": "4",
                      "stundensatz": "60"})
    client.post(f"/einstellungen/person/{ids['Laufend Lena']}/zeitraum",
                data={"von": frueher, "wochenstunden": "4", "stundensatz": "60"})

    seite = client.get("/einstellungen?bereich=betreute").text
    pruefe("Bewilligung ausgelaufen" in seite,
           "eine ausgelaufene Bewilligung wird benannt")
    pruefe("gilt erst ab" in seite,
           "ein noch nicht begonnener Zeitraum ebenfalls")
    pruefe(">gültig<" in seite, "ein laufender wird als gültig ausgewiesen")
    pruefe("ohne-bewilligung" in seite,
           "die betroffene Zeile ist markiert")
    pruefe("ohne gültige Bewilligung" in seite,
           "und oben steht, wie viele betroffen sind")

    # Der ausdrückliche Hinweis im aufgeklappten Block.
    offen = client.get(
        f"/einstellungen?bereich=betreute&offen={ids['Abgelaufen Anton']}").text
    pruefe("bewilligungswarnung" in offen,
           "im aufgeklappten Block steht die Warnung ausdrücklich")

    # Ein Zeitraum ohne Ende gilt weiter - keine Warnung.
    zeile = seite.split("Laufend Lena")[1][:400]
    pruefe("Bewilligung ausgelaufen" not in zeile,
           "ein Zeitraum ohne Ende löst keine Warnung aus")


def test_bewilligungen_mein_bereich(client: TestClient) -> None:
    """Fehlende und auslaufende Bewilligungen stehen in „Mein Bereich“."""
    abschnitt("Bewilligungen in „Mein Bereich“")
    from .main import bewilligungslage, BEWILLIGUNG_BALD_TAGE

    heute = dt.date.today()
    h = heute.isoformat()

    class Z(dict):
        def __getitem__(self, k):
            return dict.get(self, k)

    # --- Die Regel selbst ---------------------------------------------------
    laeuft = [Z(von="2020-01-01",
                bis=(heute + dt.timedelta(days=10)).isoformat(),
                wochenstunden=4, stundensatz=60)]
    lage = bewilligungslage(laeuft, 0, 0, h)
    pruefe(lage["art"] == "laeuft_aus" and lage["tage"] == 10,
           "ein Zeitraum, der bald endet, gilt als „läuft aus“")

    weit = [Z(von="2020-01-01",
              bis=(heute + dt.timedelta(days=BEWILLIGUNG_BALD_TAGE + 5)).isoformat(),
              wochenstunden=4, stundensatz=60)]
    pruefe(bewilligungslage(weit, 0, 0, h)["art"] == "laufend",
           "einer, der erst später endet, nicht")
    ohne_ende = [Z(von="2020-01-01", bis=None, wochenstunden=4, stundensatz=60)]
    pruefe(bewilligungslage(ohne_ende, 0, 0, h)["art"] == "laufend",
           "ein Zeitraum ohne Ende läuft nie aus")
    pruefe(bewilligungslage([], 3, 40, h)["art"] == "grundwert",
           "ohne Zeitraum, aber mit Grundwert: „grundwert“")
    pruefe(bewilligungslage([], 0, 0, h)["art"] == "leer",
           "ganz ohne alles: „leer“")

    # --- Die Karte ----------------------------------------------------------
    seite = client.get("/meinbereich").text
    pruefe("Bewilligungen im Blick" in seite, "die Karte steht in Mein Bereich")
    pruefe("bewilligungsliste" in seite, "mit einer Liste der Personen")
    pruefe("Abgelaufen Anton" in seite,
           "die abgelaufene Bewilligung steht darin")
    # Personen, bei denen nur der Grundwert greift, stehen zugeklappt
    # darunter - sonst ertränken sie die dringenden Fälle.
    pruefe("bewilligung-rest" in seite,
           "Personen ohne Zeitraum stehen zugeklappt darunter")

    # --- Das Recht ----------------------------------------------------------
    from .auth import darf_bewilligungen_sehen
    pruefe(darf_bewilligungen_sehen({"rolle": "benutzer",
                                     "bewilligungen_sehen": 1}) is True,
           "mit dem Recht sichtbar")
    pruefe(darf_bewilligungen_sehen({"rolle": "benutzer",
                                     "bewilligungen_sehen": 0}) is False,
           "ohne das Recht nicht")
    pruefe(darf_bewilligungen_sehen({"rolle": "benutzer"}) is True,
           "eine Sitzung von vor der Migration fällt auf den Standard")

    client.post("/einstellungen/benutzer", data={
        "benutzername": "ohnebewilligung", "passwort": "ohnepasswort",
        "rolle": "benutzer", "bereiche": ["datensaetze"]})
    with db.db() as con:
        bid = con.execute("SELECT id FROM benutzer WHERE benutzername="
                          "'ohnebewilligung'").fetchone()["id"]
        con.execute("UPDATE benutzer SET bewilligungen_sehen=0 WHERE id=?",
                    (bid,))
    o = TestClient(app)
    o.post("/login", data={"benutzername": "ohnebewilligung",
                           "passwort": "ohnepasswort"}, follow_redirects=False)
    pruefe("Bewilligungen im Blick" not in o.get("/meinbereich").text,
           "ohne das Recht fehlt die Karte ganz")

    # Und der Schalter steht in der Benutzerverwaltung.
    verwaltung = client.get("/einstellungen?bereich=benutzer").text
    pruefe('name="bewilligungen_sehen"' in verwaltung,
           "das Recht lässt sich in der Benutzerverwaltung vergeben")


def test_uebersicht_filter(client: TestClient) -> None:
    """Die Übersicht trägt denselben Filter wie die Auswertung."""
    abschnitt("Filter der Übersicht")
    seite = client.get("/eintraege").text
    pruefe('class="wahlliste"' in seite,
           "auch hier stehen die Namen als Kästchenliste")
    pruefe(seite.count("filterwahl") >= 2,
           "für betreute Personen und für Mitarbeiter")
    pruefe('class="filter-suche"' in seite,
           "das Suchfeld steht in der Fußzeile des Filters")
    pruefe(seite.index('class="filter-fuss"') < seite.index('class="filter-suche"'),
           "und zwar innerhalb dieser Zeile")

    # Mehrere Mitarbeiter zugleich.
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, monatsstunden, urlaubstage, angelegt_am) "
                    "VALUES ('zweiter',1,1,100,30,'2026-01-01 08:00')")
        con.execute(
            "INSERT INTO eintrag (mitarbeiter, datum, monat, start, ende, "
            "klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('zweiter','2026-02-02','2026-02','09:00',"
            "'10:00','Testperson','Besuch',60,1,'zw1','2026-02-02 09:00')")
    beide = client.get("/auswertung?mitarbeiter=pruefer&mitarbeiter=zweiter").text
    pruefe("2 Mitarbeiter" in beide,
           "zwei Mitarbeiter zugleich stehen in der Chipleiste")
    einer = client.get("/eintraege?mitarbeiter=zweiter").text
    körper = einer.split("<tbody>")[1].split("</tbody>")[0]
    pruefe("zweiter" in körper and "pruefer" not in körper,
           "ein einzelner Mitarbeiter filtert wie bisher")


def test_meinbereich_aufbau(client: TestClient) -> None:
    """Aufbau von „Mein Bereich“ nach dem Umbau in 1.7."""
    abschnitt("Aufbau von „Mein Bereich“")
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO vorgangsart (name, aktiv, "
                    "angelegt_am) VALUES ('Antrag',1,'2026-01-01 08:00')")
        con.execute(
            "INSERT INTO vorgang (klient, art, titel, zustaendig, status, "
            "prioritaet, frist, angelegt_am, angelegt_von) VALUES "
            "('Testperson','Antrag','Folgeantrag stellen','pruefer','Offen',"
            "'Hoch','2020-01-01','2026-01-01 08:00','pruefer')")
    seite = client.get("/meinbereich").text

    pruefe('class="spruch"' in seite or "spruch" not in seite,
           "der Spruch steht oben, sofern einer gepflegt ist")
    pruefe('class="karte meinkopf"' in seite,
           "die Kopfkarte ist die schmale Fassung")
    pruefe(seite.index("meinkopf") < seite.index("Meine Arbeitszeit"),
           "sie steht vor den Inhalten")

    baender = re.findall(r'class="abschnittsband"[^>]*>\s*<h2>([^<]+)</h2>', seite)
    pruefe(baender == ["Was ansteht", "Meine Arbeitszeit"],
           f"„Was ansteht“ steht vor der Arbeitszeit (ist: {baender})")

    pruefe("Folgeantrag stellen" in seite,
           "die eigenen Aufgaben stehen mit Titel da")
    pruefe('class="aufgabenliste"' in seite, "als eigene Liste")
    pruefe("überfällig seit" in seite,
           "eine überschrittene Frist wird als solche benannt")
    pruefe("Alle meine Aufgaben" in seite,
           "mit einem Weg in den Aufgabenbereich")

    # Die Bewilligungskarte hat keinen farbigen Rahmen mehr.
    pruefe("bewilligungskarte dringend" not in seite,
           "die Bewilligungskarte trägt keinen farbigen Rahmen mehr")
    pruefe("Bewilligungen im Blick" in seite, "sie steht aber weiterhin da")
    pruefe(seite.index("Was ansteht") < seite.index("Bewilligungen im Blick"),
           "und zwar im Abschnitt „Was ansteht“")

    # Ohne offene Aufgabe steht dort nicht nichts, sondern eine Ansage.
    with db.db() as con:
        con.execute("UPDATE vorgang SET status='Erledigt' "
                    "WHERE LOWER(TRIM(zustaendig))='pruefer'")
    leer = client.get("/meinbereich").text
    pruefe("Meine Aufgaben" in leer,
           "die Aufgabenkarte bleibt auch ohne offene Aufgabe stehen")
    pruefe("Hier ist tote Hose" in leer and "nichtsoffen" in leer,
           "und sagt ausdrücklich, dass nichts offen ist")
    pruefe("Zu den Aufgaben" in leer, "mit einem Weg dorthin")
    # Der Spaß muss ohne nachgeladenes Bild auskommen (Abschnitt 13) und
    # bei „Bewegung reduzieren" still stehen.
    pruefe('class="panda"' in leer and "panda-tier" in leer,
           "und einem dösenden Panda")
    bild = leer.split('class="panda"')[1].split("</svg>")[0]
    pruefe("<img" not in bild and "<script" not in bild,
           "handgezeichnet, ohne nachgeladenes Bild und ohne Skript")
    # Er lebt: Kopf, Atem, Beine, Bambus, Motte und Mond sind eigene Teile.
    for teil in ("panda-kopf", "panda-bauch", "panda-bein", "panda-bambus",
                 "panda-lid", "panda-falter", "panda-mond", "panda-stern"):
        pruefe(teil in bild, f"der Panda hat den Teil „{teil}“")
    stil = client.get("/static/style.css").text.replace("\n", " ")
    pruefe("prefers-reduced-motion: no-preference" in stil
           and "panda-wippen" in stil,
           "der Panda hält still, wenn Bewegung reduziert werden soll")
    # ⚠️ Jede Bewegung muss INNERHALB des Blocks stehen. Eine Animation
    # davor liefe auch dann, wenn jemand Bewegung abgestellt hat.
    block = bewegungsbloecke(stil)
    for teil in ("panda-kopf", "panda-bauch", "panda-bein", "panda-falter"):
        pruefe(f".{teil}" in block,
               f"„{teil}“ bewegt sich nur mit erlaubter Bewegung")
    with db.db() as con:
        con.execute("UPDATE vorgang SET status='Offen' "
                    "WHERE LOWER(TRIM(zustaendig))='pruefer'")


def test_vorgang_anlegen(client: TestClient) -> None:
    """Das Anlegeformular: ein Auslöser, drei Blöcke, erklärte Rollen."""
    abschnitt("Vorgang anlegen")
    zu = client.get("/vorgaenge").text
    # Es gab einen Knopf „Neuen Vorgang anlegen" und direkt darunter noch
    # einmal dieselbe Beschriftung als Aufklapper - zwei Bedienelemente
    # für dieselbe Sache.
    pruefe(zu.count("Neuen Vorgang anlegen") == 1,
           "zugeklappt gibt es genau einen Auslöser")
    pruefe('href="/vorgaenge?neu=1#neu"' in zu,
           "und der öffnet das Formular über die Adresse, nicht per Skript")
    pruefe("neu-formular" not in zu, "der alte Aufklapper ist weg")

    offen = client.get("/vorgaenge?neu=1").text
    pruefe('id="neu"' in offen and 'name="titel"' in offen,
           "mit ?neu=1 steht das Formular da")
    pruefe("Formular schließen" in offen,
           "und lässt sich wieder schließen")
    bloecke = re.findall(r'class="formblock-titel">([^<]+)<', offen)
    pruefe(len(bloecke) == 2,
           f"das Formular steht in zwei Blöcken (sind: {bloecke})")
    pruefe("zuständige Person" in offen,
           "die Rolle der zuständigen Person wird erklärt")

    # ⚠️ Das Feld „Handelnde Person" ist mit 1.9 ersatzlos entfallen - wer
    # handelt, kommt aus der Anmeldung. Es stammte aus der Zeit vor den
    # Logins, stand verwirrend neben der zuständigen Person und taugte als
    # Nachweis ohnehin nicht: man konnte jeden Namen wählen.
    pruefe('name="wer"' not in offen,
           "es gibt kein Feld „Handelnde Person“ mehr")
    pruefe("Handelnde Person" not in offen,
           "und auch keine Beschriftung dazu")
    pruefe('value="pruefer" selected' in offen,
           "die zuständige Person ist mit dem eigenen Konto vorbelegt")

    # Und das Anlegen funktioniert weiterhin.
    antwort = client.post("/vorgaenge", data={
        "klient": "Testperson", "art": "Antrag", "titel": "Formularprobe",
        "zustaendig": "pruefer", "status": "Offen", "prioritaet": "Normal",
        "frist": ""}, follow_redirects=False)
    pruefe(antwort.status_code == 303,
           "ein Vorgang lässt sich ohne das Feld anlegen")
    pruefe("Formularprobe" in client.get("/vorgaenge").text,
           "und steht danach in der Liste")

    # Und im Logbuch steht trotzdem, wer es war - aus der Anmeldung.
    with db.db() as con:
        zeile = con.execute(
            "SELECT wer FROM vorgang_log WHERE beschreibung LIKE '%Formularprobe%' "
            "OR vorgang_id = (SELECT id FROM vorgang WHERE titel='Formularprobe') "
            "ORDER BY id DESC LIMIT 1").fetchone()
    pruefe(zeile is not None and zeile["wer"] == "pruefer",
           f"im Verlauf steht das angemeldete Konto (ist: "
           f"{zeile['wer'] if zeile else None})")


def test_dringlichkeit(client: TestClient) -> None:
    """Überfällig wiegt schwerer als „Dringend“."""
    abschnitt("Dringlichkeit vor Priorität")
    from .vorgaenge import SORTIERUNGEN
    heute = dt.date.today()
    with db.db() as con:
        con.execute(
            "INSERT INTO vorgang (klient, art, titel, zustaendig, status, "
            "prioritaet, frist, angelegt_am, angelegt_von) VALUES "
            "('Testperson','Antrag','Alt und überfällig','pruefer','Offen',"
            "'Niedrig',?,'2026-01-01 08:00','pruefer')",
            ((heute - dt.timedelta(days=9)).isoformat(),))
        con.execute(
            "INSERT INTO vorgang (klient, art, titel, zustaendig, status, "
            "prioritaet, frist, angelegt_am, angelegt_von) VALUES "
            "('Testperson','Antrag','Dringend aber später','pruefer','Offen',"
            "'Dringend',?,'2026-01-01 08:00','pruefer')",
            ((heute + dt.timedelta(days=20)).isoformat(),))

    pruefe("dringlichkeit" in SORTIERUNGEN,
           "es gibt eine Sortierung nach Dringlichkeit")
    seite = client.get("/vorgaenge?sortierung=dringlichkeit&q=überfällig").text
    seite_beide = client.get("/vorgaenge?sortierung=dringlichkeit").text
    pruefe(seite_beide.index("Alt und überfällig")
           < seite_beide.index("Dringend aber später"),
           "der überfällige Vorgang steht vor dem dringenden")
    pruefe('option value="dringlichkeit" selected' in seite_beide,
           "und diese Sortierung ist die Voreinstellung")

    # Auf der Karte steht die Fristlage neben dem Titel, die Priorität
    # tritt dahinter zurück.
    pruefe('class="vk-lage l-ueberfaellig">überfällig<' in seite_beide,
           "überfällig steht als Marke gleich neben dem Titel")


def test_automatische_sicherung(client: TestClient) -> None:
    """Sonntags eine Kopie, hoechstens eine je Tag, hoechstens fuenf."""
    abschnitt("Automatische Sicherung")
    from . import main

    for datei in os.listdir(main.SICHERUNG_PFAD):
        os.remove(os.path.join(main.SICHERUNG_PFAD, datei))

    # Montag bis Samstag passiert nichts.
    pruefe(all(main.automatische_sicherung(dt.date(2026, 8, 24) + dt.timedelta(t))
               is None for t in range(6)),
           "an Werktagen wird nicht gesichert")
    pruefe(not main.sicherungsdateien(), "und es liegt auch nichts da")

    sonntag = dt.date(2026, 8, 30)
    name = main.automatische_sicherung(sonntag)
    pruefe(name == "sicherung-2026-08-30.db", "sonntags wird gesichert")
    pruefe(main.automatische_sicherung(sonntag) is None,
           "ein zweiter Anlauf am selben Tag legt nichts Neues an")
    pfad = os.path.join(main.SICHERUNG_PFAD, name)
    pruefe(os.path.getsize(pfad) > 0, "die Sicherung ist nicht leer")

    # Die Kopie muss eine lesbare Datenbank sein, keine halbe Datei.
    import sqlite3 as _s
    con = _s.connect(pfad)
    zahl = con.execute("SELECT COUNT(*) FROM eintrag").fetchone()[0]
    con.close()
    pruefe(zahl > 0, "und enthaelt die Daten")

    # Sechs Sonntage: die aelteste faellt weg.
    for w in range(1, 6):
        main.automatische_sicherung(sonntag + dt.timedelta(days=7 * w))
    vorhanden = sorted(main.sicherungsdateien())
    pruefe(len(vorhanden) == 5, "es bleiben fünf Sicherungen liegen")
    pruefe("sicherung-2026-08-30.db" not in vorhanden,
           "die älteste wird verworfen")

    seite = client.get("/einstellungen?bereich=system").text
    pruefe(vorhanden[-1] in seite, "die Einstellungen zeigen die Sicherungen")


def test_csrf(client: TestClient) -> None:
    """Schreibende Anfragen von fremden Seiten werden abgewiesen."""
    abschnitt("Schutz vor fremden Formularen")
    daten = {"nr": "1", "text": "Probe"}

    eigen = client.post("/ideen", data=daten, follow_redirects=False,
                        headers={"sec-fetch-site": "same-origin"})
    pruefe(eigen.status_code in (200, 303), "die eigene Seite darf schreiben")

    fremd = client.post("/ideen", data=daten, follow_redirects=False,
                        headers={"sec-fetch-site": "cross-site"})
    pruefe(fremd.status_code == 403, "eine fremde Seite nicht")

    herkunft = client.post("/ideen", data=daten, follow_redirects=False,
                           headers={"origin": "http://boese.example"})
    pruefe(herkunft.status_code == 403, "eine fremde Herkunft ebenso wenig")

    # Ohne jede Angabe (alte Browser, curl) bleibt es erlaubt - sonst
    # waere die Anwendung fuer sie unbedienbar.
    ohne = client.get("/einstellungen", follow_redirects=False)
    pruefe(ohne.status_code == 200, "Lesen bleibt davon unberührt")


def test_bewilligungsmail(client: TestClient) -> None:
    """Der dritte Erinnerungsanlass: auslaufende Bewilligungen."""
    abschnitt("Erinnerung an Bewilligungen")
    from . import mail
    from . import main

    seite = client.get("/einstellungen?bereich=email").text
    pruefe("bewilligung_aktiv" in seite and "bewilligung_tage" in seite,
           "die Einstellungen kennen den neuen Anlass")
    vorlagen = client.get("/einstellungen?bereich=vorlagen").text
    pruefe("vorlage_bewilligung_betreff" in vorlagen,
           "und es gibt eine eigene Vorlage dafür")

    antwort = client.post("/einstellungen/bewilligungsmail", data={
        "bewilligung_aktiv": "1", "bewilligung_tage": "45",
        "bewilligung_empfaenger": "pruefer"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "die Einstellung lässt sich speichern")
    with db.db() as con:
        k = mail.konfig_lesen(con)
    pruefe(k["bewilligung_tage"] == "45" and k["bewilligung_aktiv"] == "1",
           "und steht danach in der Konfiguration")

    # Mehrere Empfaenger: sie kommen als mehrere Felder desselben Namens
    # herein und werden kommagetrennt abgelegt.
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, monatsstunden, urlaubstage, angelegt_am) "
                    "VALUES ('Zweite Person',1,1,160,30,'2026-01-01 08:00')")
    antwort = client.post("/einstellungen/bewilligungsmail", data={
        "bewilligung_aktiv": "1", "bewilligung_tage": "45",
        "bewilligung_empfaenger": ["pruefer", "Zweite Person"]},
        follow_redirects=False)
    pruefe(antwort.status_code == 303, "mehrere Empfänger lassen sich speichern")
    with db.db() as con:
        k = mail.konfig_lesen(con)
    pruefe(mail.empfaengerliste(k["bewilligung_empfaenger"])
           == ["pruefer", "Zweite Person"], "und stehen beide in der Liste")
    seite = client.get("/einstellungen?bereich=email").text
    pruefe(seite.count('name="bewilligung_empfaenger"') >= 2,
           "die Oberfläche zeigt je Person ein Kästchen")
    # Der Name steht auf der Seite mehrfach (auch bei den Fristen) -
    # gesucht ist der Kasten im Block „Erinnerung an Bewilligungen".
    block = seite.split("Erinnerung an Bewilligungen")[1]
    kasten = block[block.index('value="Zweite Person"'):][:120]
    pruefe("checked" in kasten, "und hakt die gespeicherten an")

    # Eingeschaltet, aber niemand angehakt: das muss auffallen.
    antwort = client.post("/einstellungen/bewilligungsmail", data={
        "bewilligung_aktiv": "1", "bewilligung_tage": "45"},
        follow_redirects=False)
    pruefe("fehler=" in antwort.headers.get("location", ""),
           "eingeschaltet ohne Empfänger wird abgewiesen")

    client.post("/einstellungen/bewilligungsmail", data={
        "bewilligung_aktiv": "1", "bewilligung_tage": "45",
        "bewilligung_empfaenger": ["pruefer"]}, follow_redirects=False)

    # Die Liste selbst: sie kommt aus derselben Funktion wie die Anzeige.
    with db.db() as con:
        faelle = main.bewilligungen_pruefen(con, vorlauf=45)
    pruefe(isinstance(faelle, list), "die Fallliste ist abrufbar")
    pruefe(all("name" in f and "art" in f for f in faelle),
           "jeder Fall nennt Person und Grund")

    antwort = client.post("/einstellungen/bewilligungsmail", data={
        "bewilligung_aktiv": "", "bewilligung_tage": "60",
        "bewilligung_empfaenger": ""}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "und wieder abschalten geht auch")


def test_erinnerungsoptionen(client: TestClient) -> None:
    """Zeiterfassung und Fristen lassen sich ebenso einstellen."""
    abschnitt("Erinnerungen: Zeiterfassung und Fristen")
    from . import mail

    seite = client.get("/einstellungen?bereich=email").text
    for feld in ("abgabe_aktiv", "abgabe_tag", "frist_aktiv",
                 "frist_vorlauf", "frist_kopie"):
        pruefe(feld in seite, f"die Einstellungen kennen „{feld}“")

    # --- Zeiterfassung ---------------------------------------------------
    antwort = client.post("/einstellungen/abgabemail", data={
        "abgabe_aktiv": "1", "abgabe_tag": "5"}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "der Stichtag lässt sich speichern")
    with db.db() as con:
        k = mail.konfig_lesen(con)
        pruefe(k["abgabe_tag"] == "5", "und steht in der Konfiguration")
        # ⚠️ Vor dem Stichtag passiert nichts - vorher ging die Mail in
        # der Nacht zum Ersten heraus.
        heute = dt.date.today()
        k2 = dict(k, abgabe_tag=str(min(28, max(heute.day + 1, 2))))
        if heute.day < 28:
            pruefe(mail.pruefe_abgaben(con, k2) == [],
                   "vor dem Stichtag wird nicht erinnert")
        pruefe(mail.pruefe_abgaben(con, dict(k, abgabe_aktiv="0")) == [],
               "abgeschaltet wird gar nicht erinnert")

    # Ein Stichtag außerhalb 1–28 wird auf den Rand gezogen.
    client.post("/einstellungen/abgabemail",
                data={"abgabe_aktiv": "1", "abgabe_tag": "99"},
                follow_redirects=False)
    with db.db() as con:
        pruefe(mail.konfig_lesen(con)["abgabe_tag"] == "28",
               "ein zu großer Stichtag wird begrenzt")

    # --- Fristen ---------------------------------------------------------
    antwort = client.post("/einstellungen/fristmail", data={
        "frist_aktiv": "1", "frist_vorlauf": "3",
        "frist_kopie": ["pruefer", "Zweite Person"]}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "die Fristoptionen lassen sich speichern")
    with db.db() as con:
        k = mail.konfig_lesen(con)
    pruefe(k["frist_vorlauf"] == "3", "der Vorlauf steht in der Konfiguration")
    pruefe(mail.empfaengerliste(k["frist_kopie"]) == ["pruefer", "Zweite Person"],
           "und beide Mitlesenden ebenso")
    with db.db() as con:
        pruefe(mail.pruefe_fristen(con, dict(k, frist_aktiv="0")) == [],
               "abgeschaltet wird auch hier nicht erinnert")

    seite = client.get("/einstellungen?bereich=email").text
    block = seite.split("Erinnerung an Fristen")[1]
    kasten = block[block.index('value="pruefer"'):][:140]
    pruefe("checked" in kasten, "die Oberfläche hakt die Mitlesenden an")

    # Zurück auf den Auslieferungsstand, damit die übrigen Prüfungen
    # nicht auf veränderten Werten sitzen.
    client.post("/einstellungen/fristmail",
                data={"frist_aktiv": "1", "frist_vorlauf": "0"},
                follow_redirects=False)
    client.post("/einstellungen/abgabemail",
                data={"abgabe_aktiv": "1", "abgabe_tag": "1"},
                follow_redirects=False)


def test_texte_nachziehen(client: TestClient) -> None:
    """strings.txt gewinnt gegen die Standardtexte - deshalb nachziehbar."""
    abschnitt("Standardtexte nachziehen")
    from .main import STRINGS_DATEI, TEXTE_STANDARD

    seite = client.get("/einstellungen?bereich=system").text
    pruefe("/einstellungen/texte" in seite,
           "die Einstellungen bieten das Nachziehen an")

    # Eine Datei mit genau einem, selbst geaenderten Text.
    with open(STRINGS_DATEI, "w", encoding="utf-8") as f:
        f.write("login.lead = Selbst geschrieben\n")

    antwort = client.post("/einstellungen/texte", data={"modus": "fehlende"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "„Fehlende ergänzen“ läuft durch")
    inhalt = open(STRINGS_DATEI, encoding="utf-8").read()
    pruefe("login.lead = Selbst geschrieben" in inhalt,
           "der eigene Text bleibt unangetastet")
    pruefe("einst.fusszeile_lead" in inhalt,
           "und die fehlenden Schlüssel stehen jetzt drin")
    fehlend = [s for s in TEXTE_STANDARD if s + " =" not in inhalt]
    pruefe(not fehlend, f"es fehlt keiner mehr (offen: {fehlend[:3]})")

    antwort = client.post("/einstellungen/texte", data={"modus": "alle"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "„Alle zurücksetzen“ läuft durch")
    inhalt = open(STRINGS_DATEI, encoding="utf-8").read()
    pruefe("login.lead = Selbst geschrieben" not in inhalt,
           "danach gilt wieder der ausgelieferte Wortlaut")


def test_fusszeile(client: TestClient) -> None:
    """Zwei Haelften, und die Rechtezeile ist pflegbar."""
    abschnitt("Fußzeile")
    seite = client.get("/meinbereich").text
    fuss = seite[seite.index("<footer"):seite.index("</footer>")]
    # Seit 1.17.1 nur noch zwei Zeilen: der Satz unter dem Logo ist weg,
    # dafuer steht das Logo selbst groesser da.
    pruefe(fuss.count("fuss-zeile") == 2, "die Fußzeile hat zwei Zeilen")
    pruefe("fuss-satz" not in fuss,
           "der Satz unter dem Logo ist entfallen")
    pruefe("eigentlich nicht organisieren wollen" not in fuss,
           "und steht auch im Wortlaut nirgends mehr")
    pruefe('class="fussband"' in fuss, "sie stehen in einem gemeinsamen Band")
    pruefe('class="fussmarke"' in fuss and 'class="fussangaben"' in fuss,
           "links die Marke, rechts die Angaben")
    pruefe(fuss.index("fussmarke") < fuss.index("fussangaben"),
           "und zwar in dieser Reihenfolge")
    # Die Logos stehen seit 1.17 in fusstext() und nicht mehr in base.html -
    # beide Fassungen muessen weiterhin da sein, samt Versionsanhang.
    pruefe("logo-fuer-dunkel.svg?v=" in fuss and "logo-fuer-hell.svg?v=" in fuss,
           "beide Logos hängen mit Versionsanhang in der Fußzeile")
    pruefe('<a href="/changelog">Changelog</a>' in fuss,
           "der Changelog steht als Verweis daneben")
    pruefe("Was ist neu?" not in fuss,
           "und heißt dort nicht mehr „Was ist neu?“")

    # Das Feld fuer den Satz ist mit ihm verschwunden - ein Eingabefeld,
    # dessen Wert nirgends erscheint, waere schlimmer als keines.
    pruefe('name="fusszeile_satz"'
           not in client.get("/einstellungen?bereich=system").text,
           "das Eingabefeld dafür gibt es nicht mehr")

    antwort = client.post("/einstellungen/fusszeile",
                          data={"fusszeile_recht": "© 2026 Probe"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303, "die Rechtezeile lässt sich ändern")
    pruefe("© 2026 Probe" in client.get("/meinbereich").text,
           "und steht danach unten auf der Seite")

    # Leeres Feld heisst: wieder der ausgelieferte Wortlaut.
    client.post("/einstellungen/fusszeile", data={"fusszeile_recht": ""},
                follow_redirects=False)
    pruefe("Alle Rechte vorbehalten" in client.get("/meinbereich").text,
           "leer heißt: wieder der Standardtext")


def test_versandzeit(client: TestClient) -> None:
    """Erinnerungen gehen morgens ab 8 Uhr heraus, nicht nachts."""
    abschnitt("Versandzeit der Erinnerungen")
    from . import mail

    pruefe(mail.VERSANDSTUNDE == 8, "die Versandstunde steht auf 8 Uhr")
    pruefe(not mail.versandzeit_erreicht(dt.datetime(2026, 5, 4, 3, 30)),
           "um halb vier nachts ist sie nicht erreicht")
    pruefe(not mail.versandzeit_erreicht(dt.datetime(2026, 5, 4, 7, 59)),
           "eine Minute vor acht auch nicht")
    pruefe(mail.versandzeit_erreicht(dt.datetime(2026, 5, 4, 8, 0)),
           "um Punkt acht schon")
    # ⚠️ Bewusst „ab 8 Uhr" und nicht „um genau 8 Uhr": war der Rechner um
    # acht aus, soll die Erinnerung spaeter am Tag trotzdem noch
    # herausgehen statt lautlos auszufallen.
    pruefe(mail.versandzeit_erreicht(dt.datetime(2026, 5, 4, 21, 0)),
           "und abends noch - eine verpasste Stunde darf sie nicht schlucken")

    # Beide Anlaesse halten sich daran. Geprueft wird ueber eine
    # vorgezogene Versandstunde: liegt sie hinter der jetzigen Uhrzeit,
    # darf keiner der beiden etwas tun.
    with db.db() as con:
        k = mail.konfig_lesen(con)
        k = dict(k, frist_aktiv="1", abgabe_aktiv="1", abgabe_tag="1")
        echt = mail.VERSANDSTUNDE
        try:
            mail.VERSANDSTUNDE = 25   # nie erreicht
            pruefe(mail.pruefe_fristen(con, k) == [],
                   "vor der Versandstunde geht keine Fristmeldung heraus")
            pruefe(mail.pruefe_abgaben(con, k) == [],
                   "und keine Erinnerung an die Zeiterfassung")
            # Ein ausdruecklich angeforderter Monat geht trotzdem: da
            # drueckt jemand bewusst auf den Knopf.
            mail.pruefe_abgaben(con, dict(k, mail_aktiv="1"), monat="2026-01")
            pruefe(True, "ein ausdrücklich angefragter Monat bleibt möglich")
        finally:
            mail.VERSANDSTUNDE = echt

    seite = client.get("/einstellungen?bereich=email").text
    # ⚠️ Der Satz steht im Markup und nicht in strings.txt - eine schon
    # vorhandene strings.txt gewinnt gegen die Standardtexte, die Angabe
    # waere sonst bei Timo nie angekommen (CLAUDE.md, Abschnitt 8).
    pruefe(seite.count('class="klein leise versandzeit"') == 2,
           "beide Anlässe nennen die Versandzeit in der Oberfläche")
    pruefe("morgens ab 8 Uhr" in seite, "und zwar im Klartext")


def test_zitat_abstand(client: TestClient) -> None:
    """Über und unter dem Zitat steht derselbe Rand."""
    abschnitt("Abstände um das Zitat")
    stil = client.get("/static/style.css").text
    block = stil[stil.index(".spruch {"):stil.index(".spruch blockquote")]
    pruefe("margin: 8px auto;" in block,
           "das Zitat trägt oben und unten denselben Rand")
    pruefe("26px auto 8px" not in block,
           "der ausgleichende Randwert von 1.17 ist weg")
    # ⚠️ Die eigentliche Ursache war der untere Rand der Reiterleiste, der
    # oberhalb des Zitats zum Abstand dazukam: 18 + 18 + 26 gegen 8 + 18.
    pruefe("main > .unternavigation:has(+ .spruch) { margin-bottom: 0; }" in stil,
           "und die Reiterleiste gibt ihren unteren Rand ab, wenn ein Zitat folgt")


def test_diagramm_wertmarke(client: TestClient) -> None:
    """Die Wertmarke steht über allem, nicht im Balken."""
    abschnitt("Wertmarke des Verlaufsdiagramms")
    seite = client.get("/meinbereich").text
    # ⚠️ Erst ab dem Diagramm schneiden, DANN bis zum naechsten </svg>.
    # Auf der Seite stehen vorher schon die Zeichen der Kopfzeile und der
    # Panda - ein seite.index("</svg>") faende deren Ende und lieferte
    # einen leeren Ausschnitt, in dem jede Pruefung stumm durchginge.
    rest = seite[seite.index('class="stundendiagramm"'):]
    bild = rest[:rest.index("</svg>")]

    marken = [float(y) for y in re.findall(
        r'<text x="[-\d.]+" y="([-\d.]+)" class="wertmarke"', bild)]
    stuecke = [float(y) for y in re.findall(
        r'<rect x="[-\d.]+" y="([-\d.]+)"[^>]*?class="stueck', bild)]
    pruefe(len(marken) > 1 and len(stuecke) > 1,
           "Marken und Balken stehen im Bild")
    pruefe(len(set(marken)) == 1,
           "alle Wertmarken stehen auf derselben Höhe – in einem eigenen Band")
    # ⚠️ Der Kern der Sache: die Marke ist mit „12:30 · +2:15" rund
    # dreimal so breit wie ihre Spalte und ragte deshalb in die
    # Nachbarspalten - dort lag sie mitten im Balken. Sie muss über dem
    # HÖCHSTEN Balken stehen, nicht knapp über ihrem eigenen.
    pruefe(max(marken) < min(stuecke),
           "und liegen über dem höchsten Balken, nicht darin")

    # Die Treffflaeche reicht bis an den oberen Rand, sonst verliert man
    # die Marke beim Hinaufwandern mit der Maus.
    pruefe('class="treffer"' in bild and 'y="0"' in bild,
           "die Trefferfläche deckt das Band mit ab")

    stil = client.get("/static/style.css").text
    pruefe(".stundendiagramm .wertmarke { display: none; }" in stil,
           "ohne Zeiger steht kein einziger Wert dauerhaft im Bild")
    pruefe(".stundendiagramm .nebenmonat { display: none; }" in stil,
           "und auf schmalen Fenstern nur jeder zweite Monatsname")
    # ⚠️ Gezaehlt wird vom Ende her: der juengste Monat behaelt seinen
    # Namen, und der ist der, den man zuerst sucht.
    namen = re.findall(r'class="achsentext ?(nebenmonat)?"', bild)
    pruefe(len(namen) >= 2 and namen[-1] == "" and namen[-2] == "nebenmonat",
           "der jüngste Monat trägt seinen Namen auch auf dem Telefon")


def test_meinbereich_hinweise(client: TestClient) -> None:
    """Erklärende Texte stehen über ihrem Inhalt, nicht darunter."""
    abschnitt("Hinweise in „Mein Bereich“")
    seite = client.get("/meinbereich").text
    # Vorbild ist die Karte „Meine Zeiten": Überschrift, Erklärung,
    # dann der Inhalt. Bis 1.17 stand die Erklärung mal oben, mal unten.
    for karte, marke in (("Laufender Monat", "systemliste"),
                         ("Verlauf", "diagrammhuelle"),
                         ("Urlaub", "urlaubsspur"),
                         ("Monatsübersicht", "monatstabelle"),
                         ("Meine Zeiten", "zeitentabelle")):
        pruefe(karte in seite, f"die Karte „{karte}“ steht auf der Seite")
        teil = seite[seite.index(karte):]
        lead = teil.find('class="lead"')
        inhalt = teil.find(marke)
        pruefe(0 <= lead < inhalt,
               f"„{karte}“: die Erklärung steht über dem Inhalt")

    pruefe("mein.laufend_hinweis" not in seite, "Textschlüssel bleiben ersetzt")


def test_wiki_geschuetzter_ordner(client: TestClient) -> None:
    """Ein geschuetzter Wiki-Ordner ist ohne Freigabe schlicht nicht da."""
    abschnitt("Wiki: geschützter Ordner")

    client.post("/wiki/aktion/neu",
                data={"name": "Geheimkram", "ordner": "", "art": "ordner"})
    client.post("/wiki/aktion/neu", data={"name": "Vollmacht",
                                          "ordner": "Geheimkram", "art": "seite"})
    client.post("/wiki/aktion/speichern",
                data={"pfad": "Geheimkram/Vollmacht.md", "ordner": "Geheimkram",
                      "name": "Vollmacht.md",
                      "inhalt": "# Vollmacht\n\nKennwort Sperrgut.",
                      "pruefsumme": ""})
    client.post("/wiki/aktion/neu",
                data={"name": "Offenes", "ordner": "", "art": "ordner"})

    # Die Liste der schuetzbaren Ordner steht in der Benutzerverwaltung.
    verwaltung = client.get("/einstellungen?bereich=benutzer").text
    pruefe('name="ordner" value="Geheimkram"' in verwaltung,
           "der Ordner steht in der Benutzerverwaltung zur Wahl")

    antwort = client.post("/einstellungen/wiki-geschuetzt",
                          data={"ordner": ["Geheimkram"]}, follow_redirects=False)
    pruefe(antwort.status_code == 303, "er lässt sich als geschützt markieren")
    with db.db() as con:
        pruefe(auth.geschuetzte_ordner(con) == ["Geheimkram"],
               "und steht danach in der Konfiguration")

    # --- Konto ohne Freigabe -------------------------------------------------
    # ⚠️ Ohne wiki_ordner heisst hier "keiner" - anders als bei den
    # Bereichen, wo leer "alles" bedeutet.
    fremd = _konto(client, "ohne_ordner", "ohneordner123", ["wiki"])
    seite = fremd.get("/wiki").text
    pruefe("Geheimkram" not in seite, "im Baum taucht er nicht auf")
    pruefe("Offenes" in seite, "der ungeschützte Ordner dagegen schon")
    pruefe(fremd.get("/wiki/Geheimkram").status_code == 403,
           "der Ordner ist über die Adresse nicht erreichbar")
    pruefe(fremd.get("/wiki/Geheimkram/Vollmacht.md").status_code == 403,
           "eine Seite darin ebenso wenig")
    pruefe(fremd.get("/wiki/aktion/herunterladen?pfad=Geheimkram/Vollmacht.md"
                     ).status_code == 403, "und herunterladen geht auch nicht")

    # ⚠️ Der Inhalt darf auch nicht durch die Volltextsuche sickern - dort
    # stuende sonst der Textausschnitt mitsamt Fundstelle.
    treffer = fremd.get("/wiki/aktion/suche?q=Sperrgut").text
    pruefe("Vollmacht.md" not in treffer and "Kennwort" not in treffer,
           "die Suche findet nichts darin")
    pruefe('value="Geheimkram"' not in fremd.get("/wiki/Offenes").text,
           "und im Auswahlfeld zum Verschieben steht er nicht")

    # --- Schreibaktionen ------------------------------------------------------
    # ⚠️ Die Middleware sieht nur die Adresse; diese Pfade stehen im
    # Formular. Sie muessen trotzdem abgewiesen werden.
    for pfad, daten in (
            ("/wiki/aktion/loeschen", {"pfad": "Geheimkram/Vollmacht.md"}),
            ("/wiki/aktion/speichern", {"pfad": "Geheimkram/Vollmacht.md",
                                        "inhalt": "kaputt"}),
            ("/wiki/aktion/neu", {"ordner": "Geheimkram", "name": "Schmuggel",
                                  "art": "seite"}),
            ("/wiki/aktion/verschieben", {"pfad": "Offenes",
                                          "ziel": "Geheimkram"})):
        pruefe(fremd.post(pfad, data=daten).status_code == 403,
               f"{pfad} wird abgewiesen")
    wiki_ordner_pfad = os.path.join(_ORDNER, "wiki")
    pruefe(os.path.isfile(os.path.join(wiki_ordner_pfad, "Geheimkram",
                                       "Vollmacht.md")),
           "die geschützte Seite steht unverändert da")
    pruefe(os.path.isdir(os.path.join(wiki_ordner_pfad, "Offenes")),
           "und der offene Ordner wurde nicht verschoben")

    # --- Konto mit Freigabe ---------------------------------------------------
    mit = _konto(client, "mit_ordner", "mitordner123", ["wiki"],
                 wiki_ordner=["Geheimkram"])
    pruefe("Geheimkram" in mit.get("/wiki").text, "mit Freigabe steht er im Baum")
    pruefe(mit.get("/wiki/Geheimkram").status_code == 200, "und lässt sich öffnen")
    pruefe(mit.get("/wiki/Geheimkram/Vollmacht.md").status_code == 200,
           "die Seite darin ebenfalls")
    pruefe("Vollmacht" in mit.get("/wiki/aktion/suche?q=Sperrgut").text,
           "und die Suche findet sie")

    # Administratoren sehen ihn immer - sonst koennte sich die Verwaltung
    # selbst aussperren.
    pruefe(client.get("/wiki/Geheimkram").status_code == 200,
           "ein Administrator sieht ihn ohne eigene Freigabe")

    # ⚠️ Solange nichts geschuetzt ist, darf der Filter gar nicht greifen.
    client.post("/einstellungen/wiki-geschuetzt", data={"ordner": []},
                follow_redirects=False)
    pruefe(fremd.get("/wiki/Geheimkram").status_code == 200,
           "ohne Schutzmarkierung ist der Ordner wieder für alle da")
    client.post("/einstellungen/wiki-geschuetzt", data={"ordner": ["Geheimkram"]},
                follow_redirects=False)


def test_fusszeile_buendig(client: TestClient) -> None:
    """Die Fußzeile steht bündig zum Inhalt darüber."""
    abschnitt("Fußzeile: Bündigkeit")
    stil = client.get("/static/style.css").text
    # ⚠️ Der seitliche Abstand gehoert dem Band, nicht dem footer - sonst
    # deckt sich zwar die Trennlinie mit main, der Inhalt darin steht aber
    # 26px weiter aussen als die Karten darueber.
    pruefe("footer { flex: 0 0 auto; color: var(--leise); font-size: 12.5px;\n"
           "         padding: 30px 0 0; }" in stil,
           "footer trägt keinen seitlichen Abstand mehr")
    band = stil[stil.index(".fussband {"):stil.index("[data-breite=\"begrenzt\"] .fussband")]
    pruefe("padding: 20px 26px 24px;" in band,
           "das Band bringt seinen eigenen mit – denselben Wert wie main")
    pruefe("  .fussband { padding-left: 16px; padding-right: 16px; }" in stil,
           "am Telefon ebenso, dort mit 16px")
    pruefe(".fussmarke img { height: 54px;" in stil,
           "das Logo ist eine Spur kleiner geworden")


def test_kfz_linksbuendig(client: TestClient) -> None:
    """Im Fuhrpark steht alles linksbündig, wie in jeder anderen Liste."""
    abschnitt("Fuhrpark: linksbündig")
    for pfad in ("/fuhrpark", "/fuhrpark/auswertung"):
        seite = client.get(pfad).text
        # ⚠️ Am Dialog abschneiden: der Changelog darin kann das Wort
        # enthalten und macht die Pruefung sonst unscharf.
        seite = seite.split('<div class="neuheiten"')[0]
        pruefe('class="num' not in seite and 'class="rechts' not in seite,
               f"{pfad} trägt keine rechtsbündige Zelle mehr")
        pruefe('class="zahlen' in seite,
               f"{pfad} behält aber die Tabellenziffern")


def test_zeitspanne_meinbereich(client: TestClient) -> None:
    """„Meine Zeiten" zeigt die Zeitspanne wie die Übersicht."""
    abschnitt("Mein Bereich: Zeitspanne")
    seite = client.get("/meinbereich").text
    pruefe('class="zeitspanne"' in seite,
           "die Zeitspanne steht in derselben Hülle wie in der Übersicht")
    pruefe('class="bis"' in seite, "die Endzeit ist gedämpft abgesetzt")
    zeiten = seite[seite.index("zeitentabelle"):] if "zeitentabelle" in seite else ""
    pruefe("}}–{{" not in zeiten and "–</td>" not in zeiten,
           "und nicht mehr als Bindestrich dazwischen")


def test_spruch_hoehe(client: TestClient) -> None:
    """Der Zitatblock ist immer gleich hoch."""
    abschnitt("Zitat: gleichbleibende Höhe")
    # ⚠️ Ohne Quelle stand bisher gar keine figcaption da - der Block war
    # dann 29px flacher, und weil bei jedem Aufruf ein anderer Spruch
    # gezogen wird, sprang die ganze Seite beim Aktualisieren um genau
    # diesen Betrag.
    from . import einstellungen as _e
    with open(_e._u["SPRUCH_DATEI"], "w", encoding="utf-8") as f:
        f.write("Ein Spruch ganz ohne Quelle.\n")
    seite = client.get("/").text
    pruefe("<figcaption>" in seite,
           "auch ein Spruch ohne Quelle bekommt seine Quellenzeile")
    pruefe("<figcaption></figcaption>" in seite,
           "und zwar eine leere")
    stil = client.get("/static/style.css").text
    pruefe(".spruch figcaption:empty::before { content: \"\\00a0\"; }" in stil,
           "eine leere Quellenzeile hält ihre Höhe über ein geschütztes Leerzeichen")



def test_mehrfachauswahl(client: TestClient) -> None:
    """Die Kästchen der Übersicht erscheinen erst auf Wunsch."""
    abschnitt("Mehrfachauswahl")
    seite = client.get("/eintraege").text
    pruefe('id="auswahlmodus"' in seite and 'class="auswahlschalter"' in seite,
           "der Schalter steht als Kästchen ohne Namen auf der Seite")
    pruefe('for="auswahlmodus"' in seite, "der Knopf daneben ist sein Label")
    pruefe("Mehrfachauswahl" in seite and "Auswahl beenden" in seite,
           "beide Beschriftungen stehen im Markup")
    # Ohne Skript muss das genauso gehen - der Knopf ist ein <label>, kein
    # <button> mit einem Klickhandler daran.
    knopf = seite[seite.index('for="auswahlmodus"') - 200:
                  seite.index('for="auswahlmodus"') + 40]
    pruefe("<label" in knopf, "es ist ein Label und kein Knopf mit Skript")
    pruefe("onclick" not in knopf, "und hängt an keinem Klickhandler")

    stil = client.get("/static/style.css").text.replace("\n", " ")
    pruefe(".auswahlschalter:not(:checked) ~ .liste .wahlspalte" in stil,
           "ohne Schalter ist die Kästchenspalte ausgeblendet")
    pruefe(".auswahlschalter:not(:checked) ~ .massenleiste" in stil,
           "und die Leiste mit dem Löschknopf ebenfalls")
    # ⚠️ Die Groesse des Kaestchens steht ausdruecklich im Stylesheet: der
    # Rand darueber ist darauf gerechnet, damit es auf der Hoehe des
    # Datums sitzt. Ohne feste Groesse stuende es je nach Browser daneben.
    regel = stil[stil.index(".liste .wahlspalte input"):][:220]
    pruefe("width: 15px" in regel and "height: 15px" in regel,
           "das Kästchen hat eine feste Größe")
    pruefe("margin: 3px 0 0" in regel,
           "und einen darauf gerechneten Abstand nach oben")

    # Ohne Loeschrecht gibt es nichts auszuwaehlen - dann fehlt auch der
    # Schalter, statt einen Knopf anzubieten, der ins Leere fuehrt.
    with db.db() as con:
        vorhanden = con.execute(
            "SELECT 1 FROM benutzer WHERE benutzername='ohnerecht'").fetchone()
        if not vorhanden:
            con.execute(
                "INSERT INTO benutzer (benutzername, passwort_hash, rolle, "
                "berechtigungen, aktiv, fremde_loeschen, angelegt_am) "
                "VALUES ('ohnerecht', ?, 'benutzer', 'datensaetze', 1, 0, ?)",
                (db.passwort_hashen("ohnerechtpasswort"),
                 dt.datetime.now().isoformat(" ", "seconds")))
    gast = TestClient(app)
    gast.post("/login", data={"benutzername": "ohnerecht",
                              "passwort": "ohnerechtpasswort"},
              follow_redirects=False)
    ohne = gast.get("/eintraege").text
    pruefe('id="auswahlmodus"' not in ohne,
           "ohne löschbare Zeilen fehlt der Schalter ganz")


def test_leistungen_umbenannt(client: TestClient) -> None:
    """Der Einstellungspunkt heißt „Leistungen“, der Schlüssel bleibt."""
    abschnitt("Leistungen")
    seite = client.get("/einstellungen?bereich=leistungen").text
    pruefe("<h1>Leistungen</h1>" in seite, "die Seite heißt „Leistungen“")
    # ⚠️ Nicht auf das blosse Wort pruefen: der Hinweis auf Neuerungen
    # steht auf jeder Seite und zitiert den Changelog-Eintrag dazu.
    inhalt = seite.split('<div class="neuheiten"')[0]
    pruefe("Leistungsbeschreibungen" not in inhalt,
           "das lange Wort steht nirgends mehr auf der Seite")
    pruefe('bereich=leistungen" class="aktiv">Leistungen</a>' in seite,
           "im Menü daneben ebenso")
    # ⚠️ Der Berechtigungsschluessel bleibt „leistungen" - sonst verloere
    # jedes eingeschraenkte Konto seinen Zugriff auf diesen Punkt.
    from . import auth as _a
    pruefe(_a.EINST_BEREICHE["leistungen"] == "Leistungen",
           "die Benutzerverwaltung nennt ihn genauso")
    pruefe("leistungen" in _a.EINST_BEREICHE,
           "der Schlüssel selbst ist unverändert")


def bewegungsbloecke(stil: str) -> str:
    """Alles, was in einem prefers-reduced-motion-Block steht.

    Die Anwendung hat mehrere solcher Blöcke. Ein simples split() träfe
    immer nur den ersten - deshalb hier über die Klammern gezählt.
    """
    marke = "@media (prefers-reduced-motion: no-preference)"
    teile, stelle = [], stil.find(marke)
    while stelle != -1:
        i = stil.find("{", stelle)
        tiefe, j = 0, i
        while j < len(stil):
            if stil[j] == "{":
                tiefe += 1
            elif stil[j] == "}":
                tiefe -= 1
                if tiefe == 0:
                    break
            j += 1
        teile.append(stil[i:j])
        stelle = stil.find(marke, j)
    return "\n".join(teile)


def test_betreute_auswahl(client: TestClient) -> None:
    """Die betreute Person kommt aus einer Liste, nicht aus einem Textfeld."""
    abschnitt("Betreute Person als Auswahl")
    seite = client.get("/").text

    pruefe('<input type="text" name="klient"' not in seite,
           "kein freies Textfeld mehr für die betreute Person")
    pruefe('<select name="klient"' in seite, "sondern ein Auswahlfeld")
    pruefe('<span>Betreute Person</span>' in seite,
           "und es heißt „Betreute Person“, nicht mehr „Betreuter“")
    pruefe("<datalist" not in seite, "die alte Vorschlagsliste ist weg")
    pruefe("Testperson" in seite, "die gepflegten Personen stehen zur Wahl")
    # Ein Skript macht daraus ein durchsuchbares Feld - ohne Skript bleibt
    # es ein ganz normales Auswahlfeld.
    pruefe("suchwahl" in seite and "tippen zum Suchen" in seite,
           "getippt werden darf trotzdem: das Feld ist durchsuchbar")

    # ⚠️ Das Auswahlfeld allein reicht nicht - ein abgeschicktes Formular
    # kann alles enthalten. Der Server prüft den Namen deshalb noch einmal.
    antwort = client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": "05.03.2026",
        "klient": "Frei Erfunden", "start": "09:00", "ende": "10:00",
        "beschreibung": "Probe"}, follow_redirects=False)
    ziel = antwort.headers.get("location", "")
    pruefe("fehler=" in ziel, "ein unbekannter Name wird abgewiesen")
    pruefe("Liste" in ziel or "Einstellungen" in ziel,
           "und die Meldung sagt, woher die Namen kommen")

    # Eine abweichende Schreibweise wird auf die gepflegte gezogen.
    antwort = client.post("/erfassung", data={
        "mitarbeiter": "pruefer", "datum": "06.03.2026",
        "klient": "  testperson  ", "start": "09:00", "ende": "10:00",
        "beschreibung": "Schreibweise"}, follow_redirects=False)
    pruefe("fehler=" not in antwort.headers.get("location", ""),
           "eine andere Schreibweise wird angenommen")
    with db.db() as con:
        z = con.execute("SELECT klient FROM eintrag WHERE beschreibung="
                        "'Schreibweise'").fetchone()
    pruefe(z and z["klient"] == "Testperson",
           "und auf die gepflegte Schreibweise gezogen")
    with db.db() as con:
        con.execute("DELETE FROM eintrag WHERE beschreibung='Schreibweise'")


def test_abgaben_verweise(client: TestClient) -> None:
    """Wer abgegeben hat, ist anklickbar und führt in die Übersicht."""
    abschnitt("Abgaben: Namen führen weiter")
    heute = dt.date.today()
    with db.db() as con:
        con.execute(
            "INSERT OR REPLACE INTO eintrag (id, mitarbeiter, datum, monat, "
            "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
            "fingerprint, angelegt_am) VALUES (960,'pruefer',?,?,'09:00',"
            "'10:00','Testperson','Abgabeprobe',60,1,'abg1','2026-01-01 08:00')",
            (heute.isoformat(), heute.strftime("%Y-%m")))
    seite = client.get("/").text
    pruefe("/eintraege?mitarbeiter=" in seite,
           "der Name führt in die gefilterte Übersicht")
    verweis = seite.split("/eintraege?mitarbeiter=")[1].split('"')[0]
    pruefe(f"von_monat={heute:%m}" in verweis
           and f"bis_monat={heute:%m}" in verweis,
           "und zwar auf genau diesen Monat")
    pruefe(f"von_jahr={heute:%Y}" in verweis, "und dieses Jahr")
    # Auch wer nichts abgegeben hat, ist anklickbar - die leere Liste ist
    # dort die Antwort auf die Frage, mit der man hinklickt.
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, angelegt_am) VALUES "
                    "('Ohne Abgabe',1,1,'2026-01-01 08:00')")
    seite = client.get("/").text
    pruefe(seite.count("/eintraege?mitarbeiter=") >= 2,
           "auch ohne Abgabe führt der Name weiter")
    # Der Verweis liefe ohne den Bereich nur in ein 403 - dann bleibt der
    # Name schlichter Text.
    nutzer = _konto(client, "abgabeleser", "abgabepasswort",
                    ["listenimport", "manuelle_eintraege"])
    ohne = nutzer.get("/").text
    pruefe("/eintraege?mitarbeiter=" not in ohne,
           "ohne den Bereich „Übersicht“ ist der Name kein Verweis")
    with db.db() as con:
        con.execute("DELETE FROM eintrag WHERE id=960")


def test_wiki_falten(client: TestClient) -> None:
    """Überschriften lassen sich samt Inhalt zuklappen."""
    abschnitt("Wiki: Abschnitte einklappen")
    from . import markdown as md

    text = ("# Titel\n\nVorspann\n\n## Kapitel A\n\nText A\n\n"
            "### Unter A1\n\nText A1\n\n## Kapitel B\n\nText B\n")
    html = str(md.zu_html(text, None, [], faltbar=True))
    pruefe(html.count('<details class="wiki-falt" open>') == 3,
           "jede Überschrift ab Stufe 2 bekommt einen eigenen Abschnitt")
    pruefe("<h1" in html and "<summary" in html
           and '<summary class="wiki-falt-kopf"><h1' not in html,
           "die Seitenüberschrift bleibt außen vor")
    # ⚠️ Die Kennung muss an der Überschrift bleiben, sonst liefe jede
    # Sprungmarke aus „Auf dieser Seite“ ins Leere.
    pruefe('id="kapitel-a"' in html and 'id="unter-a1"' in html,
           "die Sprungmarken bleiben erhalten")
    # Verschachtelung: das Unterkapitel steckt im Kapitel darüber.
    innen = html.split('id="kapitel-a"')[1].split('id="kapitel-b"')[0]
    pruefe('id="unter-a1"' in innen,
           "ein Unterkapitel liegt im Kapitel darüber")
    pruefe(str(md.zu_html(text, None, [])).count("wiki-falt") == 0,
           "ohne faltbar bleibt das HTML wie zuvor")

    with open(os.path.join(_ORDNER, "wiki", "falten.md"), "w",
              encoding="utf-8") as f:
        f.write(text)
    seite = client.get("/wiki/falten.md").text
    pruefe('class="wiki-falt"' in seite, "die Wiki-Seite liefert die Abschnitte")
    pruefe('id="wiki-falten"' in seite, "und einen Knopf für alle auf einmal")
    stil = client.get("/static/style.css").text
    pruefe(".wiki-falt-kopf" in stil, "die Abschnitte sind gestaltet")


def test_werkzeuge(client: TestClient) -> None:
    """Aufgeräumte Werkzeugleisten in Dateien, Wiki und Einstellungen."""
    abschnitt("Werkzeugleisten")

    # --- Dateien: kein zweiter Weg zum Öffnen ---------------------------
    with open(os.path.join(_ORDNER, "files", "werkzeug.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    seite = client.get("/dateien").text
    zeile = seite.split("werkzeug.png")[1].split("</tr>")[0]
    pruefe('title="Öffnen"' not in seite,
           "⚠️ kein „Öffnen“-Knopf mehr – der Dateiname ist der Verweis")
    pruefe("/dateien/holen/" in seite, "und der Name führt weiterhin zur Datei")

    # --- Wiki: das Anlegeformular genau einmal --------------------------
    # ⚠️ Bis 1.15.3 stand es auf einer Ordnerseite doppelt: einmal als
    # aufklappbare Zeile und einmal als eigene Karte darunter.
    os.makedirs(os.path.join(_ORDNER, "wiki", "Werkzeugprobe"), exist_ok=True)
    ordner = client.get("/wiki/Werkzeugprobe").text
    pruefe(ordner.count('class="wiki-anlegen"') == 1,
           "das Anlegeformular steht genau einmal auf der Seite")
    pruefe('id="wiki-neu"' in ordner,
           "und wird über ein Zeichen in der Seitenleiste ausgelöst")
    # Auch von einer Seite aus, sonst wäre das Zeichen mal da und mal weg.
    with open(os.path.join(_ORDNER, "wiki", "werkzeugseite.md"), "w",
              encoding="utf-8") as f:
        f.write("# Werkzeugseite\n")
    einzeln = client.get("/wiki/werkzeugseite.md").text
    pruefe(einzeln.count('class="wiki-anlegen"') == 1,
           "auch von einer Seite aus lässt sich etwas anlegen")

    # --- Wiki: erst der Mülleimer, dann der Umschalter ------------------
    leiste = ordner.split('class="wiki-werkzeugleiste"')[1].split("</div>\n")[0]
    pruefe(">Ordner löschen<" not in leiste and 'title="Ordner löschen"' in leiste,
           "„Ordner löschen“ steht nur noch als Zeichen mit Sprechblase da")
    pruefe(leiste.index("loeschen") < leiste.index("wikiliste-knopf"),
           "der Mülleimer steht vor dem Umschalter")
    pruefe("wikiliste-text" in leiste,
           "der Umschalter behält seinen Text für Vorleseprogramme")

    # --- Einstellungen: gleiche Reihenfolge -----------------------------
    einst = client.get("/einstellungen?bereich=oberflaeche").text
    def reihe(klasse):
        teil = einst.split(klasse + "-knopf")
        return [t.split('data-wert="')[1].split('"')[0] for t in teil[:-1]
                if 'data-wert="' in t]
    pruefe(reihe("wikiliste") == reihe("dateiliste"),
           "Wiki und Dateien stehen in derselben Reihenfolge")
    stil = client.get("/static/style.css").text
    pruefe(".wahlpaar {" in stil and "grid-template-columns: 1fr 1fr" in stil,
           "die Umschalter sind alle gleich breit")


def test_verlaufsdiagramm(client: TestClient) -> None:
    """Das Diagramm: geteilte Balken, gerechnete Linienlänge, kein Skript."""
    abschnitt("Verlaufsdiagramm")
    seite = client.get("/meinbereich").text
    pruefe('class="stundendiagramm"' in seite, "das Diagramm steht auf der Seite")
    bild = seite.split('class="stundendiagramm"')[1].split("</svg>")[0]
    pruefe("<script" not in bild and "http" not in bild,
           "handgebautes SVG, nichts nachgeladen")

    # Der geteilte Balken ist der Kern: unten das Erreichte, darüber das
    # Zuviel oder das Fehlende.
    pruefe('class="stueck basis"' in bild, "jeder Monat hat einen Grundbalken")
    pruefe('class="stueck ueber"' in bild or 'class="stueck fehlt"' in bild,
           "und ein Stück für die Abweichung zum Soll")
    pruefe('class="treffer"' in bild, "die ganze Spalte ist anfassbar")
    pruefe('class="wertmarke"' in bild, "beim Überfahren steht der Wert da")

    # ⚠️ Die Länge der Saldolinie kommt aus Python. Im Browser ginge das
    # nur über getTotalLength(), also mit Skript.
    if 'class="saldolinie"' in bild:
        pruefe("--laenge:" in bild, "die Saldolinie bringt ihre Länge mit")

    # Die Animation soll man sehen: sie wartet, bis das Diagramm im Bild
    # steht. Ohne Skript läuft sie wie zuvor gleich beim Laden.
    umgebung = seite.split('class="diagrammhuelle"')[1].split("<div class=\"legende\"")[0]
    pruefe("IntersectionObserver" in umgebung and "pausiert" in umgebung,
           "die Animation wartet, bis das Diagramm im Bild steht")

    stil = client.get("/static/style.css").text.replace("\n", " ")
    pruefe("dia-wachsen" in stil and "dia-strich" in stil,
           "Balken und Linie zeichnen sich ein")
    pruefe("dia-wachsen" in bewegungsbloecke(stil),
           "und stehen still, wenn Bewegung reduziert werden soll")
    pruefe("animation-play-state: paused" in stil
           and ".stundendiagramm.sichtbar" in stil,
           "angehalten wird über animation-play-state, nicht über die Deckkraft")


def test_farbvariablen(client: TestClient) -> None:
    """Jede benutzte CSS-Variable muss es auch geben.

    ⚠️ Ein Tippfehler in einem var(--…) ist unsichtbar: die Eigenschaft
    fällt still auf ihren Anfangswert zurück. Genau so stand die
    Wertmarke des Diagramms in Schwarz auf dunklem Grund - sie hieß
    var(--text), die Variable heißt aber --tinte.
    """
    abschnitt("CSS-Variablen")
    stil = client.get("/static/style.css").text

    definiert = set(re.findall(r"(--[a-z0-9-]+)\s*:", stil))
    # Ein zweiter Wert in var(…) ist der Rückfall - der darf fehlen.
    ohne_rueckfall = set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", stil))
    # Manches wird erst im Markup gesetzt (style="--takt: …").
    aus_markup = set()
    for name in os.listdir("app/templates"):
        if name.endswith(".html"):
            with open(os.path.join("app/templates", name), encoding="utf-8") as f:
                aus_markup |= set(re.findall(r"(--[a-z0-9-]+)\s*:", f.read()))

    fehlend = sorted(ohne_rueckfall - definiert - aus_markup)
    pruefe(not fehlend, f"keine unbekannte CSS-Variable (offen: {fehlend})")


def test_bewilligung_nachfolge(client: TestClient) -> None:
    """Ein hinterlegter Folgebescheid beendet die Warnung."""
    abschnitt("Bewilligung mit Folgebescheid")
    from .main import bewilligungslage

    heute = "2026-08-30"

    def zr(von, bis):
        return {"von": von, "bis": bis, "wochenstunden": 4, "stundensatz": 70}

    # Absteigend nach „von“, so kommt die Liste überall herein.
    laufend_allein = [zr("2025-10-01", "2026-09-30")]
    stand = bewilligungslage(laufend_allein, 0, 0, heute)
    pruefe(stand["art"] == "laeuft_aus",
           "ohne Folgebescheid läuft die Bewilligung aus")
    pruefe(stand["bis"] == "2026-09-30", "und die Meldung nennt das Datum")

    mit_nachfolge = [zr("2026-10-01", "2027-09-30"), zr("2025-10-01", "2026-09-30")]
    stand = bewilligungslage(mit_nachfolge, 0, 0, heute)
    pruefe(stand["art"] == "laufend",
           "mit hinterlegtem Folgebescheid wird nicht mehr gewarnt")
    pruefe(stand["nachfolge"] and stand["nachfolge"]["von"] == "2026-10-01",
           "der Folgebescheid wird mitgegeben")
    pruefe(stand["zeitraum"]["von"] == "2025-10-01",
           "es gilt weiterhin der heutige Zeitraum")

    # Ein Folgebescheid, der noch VOR dem Ende endet, ist keiner.
    kein_nachfolger = [zr("2026-09-01", "2026-09-15"), zr("2025-10-01", "2026-09-30")]
    pruefe(bewilligungslage(kein_nachfolger, 0, 0, heute)["art"] == "laeuft_aus",
           "ein kürzerer Zeitraum dazwischen zählt nicht als Nachfolger")

    # Ein Folgebescheid ohne Ende gilt bis auf Weiteres.
    offen = [zr("2026-10-01", None), zr("2025-10-01", "2026-09-30")]
    pruefe(bewilligungslage(offen, 0, 0, heute)["art"] == "laufend",
           "ein Folgebescheid ohne Ende zählt auch")

    # ⚠️ Und der Fall, der die ganze Sache aufgedeckt hat: in den
    # Einstellungen stand „keine Bewilligung hinterlegt“, weil die
    # Vorlage für „läuft aus“ gar keinen Zweig hatte.
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO person (name, wochenstunden, "
                    "stundensatz, aktiv, angelegt_am) VALUES "
                    "('Auslaufperson', 0, 0, 1, '2026-01-01 08:00')")
        pid = con.execute("SELECT id FROM person WHERE name='Auslaufperson'"
                          ).fetchone()["id"]
        con.execute("DELETE FROM person_zeitraum WHERE person_id=?", (pid,))
        heute_echt = dt.date.today()
        con.execute("INSERT INTO person_zeitraum (person_id, von, bis, "
                    "wochenstunden, stundensatz, angelegt_am) "
                    "VALUES (?,?,?,?,?,'2026-01-01 08:00')",
                    (pid, (heute_echt - dt.timedelta(days=300)).isoformat(),
                     (heute_echt + dt.timedelta(days=20)).isoformat(), 4, 70))
    seite = client.get("/einstellungen?bereich=betreute").text
    zeile = seite.split("Auslaufperson")[1][:600]
    pruefe("läuft aus am" in zeile,
           "die Einstellungen sagen „läuft aus“")
    pruefe("keine Bewilligung hinterlegt" not in zeile,
           "und nicht mehr fälschlich „keine Bewilligung hinterlegt“")

    # Mit Folgebescheid verschwindet die Warnung auch dort.
    with db.db() as con:
        con.execute("INSERT INTO person_zeitraum (person_id, von, bis, "
                    "wochenstunden, stundensatz, angelegt_am) "
                    "VALUES (?,?,?,?,?,'2026-01-01 08:00')",
                    (pid, (heute_echt + dt.timedelta(days=21)).isoformat(),
                     (heute_echt + dt.timedelta(days=400)).isoformat(), 5, 72))
    seite = client.get("/einstellungen?bereich=betreute").text
    zeile = seite.split("Auslaufperson")[1][:600]
    pruefe("läuft aus am" not in zeile and "gültig" in zeile,
           "mit Folgebescheid steht dort wieder „gültig“")
    pruefe("Folgebescheid ab" in zeile, "und der Folgebescheid wird genannt")

    # Und die Person fällt aus der Karte „Bewilligungen im Blick“.
    mein = client.get("/meinbereich").text
    pruefe("Auslaufperson" not in mein.split("Bewilligungen im Blick")[1][:2500],
           "und nicht mehr in „Bewilligungen im Blick“")
    with db.db() as con:
        con.execute("DELETE FROM person WHERE id=?", (pid,))


def test_datenpflege(client: TestClient) -> None:
    """Sammeländerung: zwei Schritte, Sicherung, nichts geht verloren."""
    abschnitt("Datenpflege")
    from . import auth
    from . import main

    def anwenden(daten, wort="ÄNDERN"):
        return client.post("/einstellungen/datenpflege/anwenden", data=dict(daten, bestaetigung=wort),
                           follow_redirects=False)

    seite = client.get("/einstellungen/datenpflege").text
    pruefe("Datenpflege" in seite and "Vorschau anzeigen" in seite,
           "die Seite ist erreichbar und führt erst zur Vorschau")
    pruefe(">Datenpflege<" in client.get("/einstellungen?bereich=system").text,
           "und steht in den Einstellungen unter „Wartung“")
    pruefe(">Datenpflege<" not in client.get("/eintraege").text,
           "aber nicht mehr als Reiter unter „Arbeitszeit“")

    # --- Warnung --------------------------------------------------------
    pruefe("warnband" in seite and "Sicherung" in seite,
           "über dem Formular steht ein deutlicher Hinweis")
    pruefe("gefahrenkarte" in seite, "und die Karte ist als heikel gekennzeichnet")

    # --- Standardmäßig aus ----------------------------------------------
    # ⚠️ „Kein Haken" heißt sonst „alles erlaubt". Für die Datenpflege
    # gilt das ausdrücklich nicht - sonst bekäme sie jedes Konto, das
    # zufällig keine Einschränkung trägt.
    class _Konto(dict):
        pass
    ohne = _Konto(rolle="benutzer", berechtigungen="")
    pruefe(not auth.hat_zugriff(ohne, "datenpflege"),
           "ein Konto ohne Einschränkung bekommt die Datenpflege NICHT")
    pruefe(auth.hat_zugriff(ohne, "auswertung"),
           "alle übrigen Bereiche bekommt es weiterhin")
    mit = _Konto(rolle="benutzer", berechtigungen="auswertung,datenpflege")
    pruefe(auth.hat_zugriff(mit, "datenpflege"),
           "ausdrücklich erteilt greift sie")
    verwaltung = client.get("/einstellungen?bereich=benutzer").text
    kasten = verwaltung.split('value="datenpflege"')[-1][:80]
    pruefe("checked" not in kasten,
           "im Anlegeformular ist der Haken nicht vorgesetzt")

    # --- Zugriff --------------------------------------------------------
    # ⚠️ Die Seite ändert Werte quer durch die Datenbank. Sie hängt an
    # ihrem Bereich UND fest an der Rolle.
    fremd = _konto(client, "pfleger", "pflegerpasswort",
                   ["datensaetze", "datenpflege"])
    pruefe(fremd.get("/einstellungen/datenpflege").status_code == 403,
           "ein normales Konto kommt auch mit dem Bereich nicht hinein")
    pruefe(fremd.post("/einstellungen/datenpflege/anwenden", data={
        "feld": "beschreibung", "suchart": "genau", "suchwert": "x",
        "neuer_wert": "y", "bestaetigung": "ÄNDERN"}).status_code == 403,
        "und schon gar nicht ans Anwenden")

    # --- Testdaten ------------------------------------------------------
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO mitarbeiter (name, aktiv, "
                    "abgabepflicht, angelegt_am) VALUES "
                    "('Pflegeprobe',1,1,'2026-01-01 08:00')")
        for nr, text in ((941, "AU"), (942, "au "), (943, "AU-Bescheinigung"),
                         (944, "Betreuung")):
            con.execute(
                "INSERT OR REPLACE INTO eintrag (id, mitarbeiter, datum, monat, "
                "start, ende, klient, beschreibung, dauer_min, abrechenbar, "
                "fingerprint, angelegt_am) VALUES "
                "(?, 'Pflegeprobe','2026-05-04','2026-05','09:00','10:00',"
                "'Testperson',?,60,1,?, '2026-05-04 09:00')",
                (nr, text, f"pf{nr}"))

    # --- Schritt 1 ändert nichts ----------------------------------------
    grund = {"feld": "beschreibung", "suchart": "genau",
             "suchwert": "AU", "neuer_wert": "Krank"}
    vorschau = client.post("/einstellungen/datenpflege/vorschau", data=grund).text
    pruefe("Das würde passieren" in vorschau, "die Vorschau erscheint")
    pruefe("ÄNDERN" in vorschau,
           "und verlangt für den zweiten Schritt das Bestätigungswort")
    with db.db() as con:
        pruefe(con.execute("SELECT COUNT(*) c FROM eintrag WHERE beschreibung "
                           "IN ('AU','au ')").fetchone()["c"] == 2,
               "und ändert selbst noch nichts")

    # ⚠️ Verglichen wird über norm(): „AU“ und „au “ gehören zusammen,
    # „AU-Bescheinigung“ aber nicht - das ist kein „ist genau“.
    pruefe(">AU-Bescheinigung<" not in vorschau,
           "„ist genau“ fasst nur die wirklich gleichen Werte")

    # --- Falsches Wort ändert nichts ------------------------------------
    antwort = anwenden(grund, "ja")
    pruefe("Zum Anwenden muss das Wort" in antwort.text,
           "ohne das Bestätigungswort passiert nichts")
    with db.db() as con:
        pruefe(con.execute("SELECT COUNT(*) c FROM eintrag WHERE beschreibung "
                           "IN ('AU','au ')").fetchone()["c"] == 2,
               "und die Daten stehen unverändert da")

    # --- Anwenden -------------------------------------------------------
    vorher = len(main.sicherungsdateien())
    antwort = anwenden(grund)
    pruefe(antwort.status_code == 303, "mit dem Wort wird geändert")
    with db.db() as con:
        pruefe(con.execute("SELECT COUNT(*) c FROM eintrag WHERE "
                           "beschreibung='Krank'").fetchone()["c"] == 2,
               "beide Schreibweisen sind zusammengezogen")
        pruefe(con.execute("SELECT beschreibung b FROM eintrag WHERE id=943"
                           ).fetchone()["b"] == "AU-Bescheinigung",
               "der längere Text blieb unangetastet")
    pruefe(len(main.sicherungsdateien()) == vorher + 1,
           "vorher wurde eine Sicherung angelegt")

    # „enthält“ greift weiter.
    anwenden({"feld": "beschreibung", "suchart": "enthaelt",
              "suchwert": "bescheinigung", "neuer_wert": "Krank"})
    with db.db() as con:
        pruefe(con.execute("SELECT COUNT(*) c FROM eintrag WHERE "
                           "beschreibung='Krank'").fetchone()["c"] == 3,
               "„enthält“ findet auch den Teiltext")

    # --- Mitarbeiter global ---------------------------------------------
    with db.db() as con:
        con.execute("INSERT INTO vorgang (klient, art, titel, zustaendig, "
                    "status, prioritaet, angelegt_am, angelegt_von, "
                    "geaendert_am) VALUES ('Testperson','Sonstiges',"
                    "'Pflegevorgang','Pflegeprobe','Offen','Normal',"
                    "'2026-01-01 08:00','pruefer','2026-01-01 08:00')")
        con.execute("INSERT INTO vorgang_log (vorgang_id, zeitpunkt, wer, "
                    "aktion, beschreibung, klient) SELECT id,"
                    "'2026-01-01 08:00','Pflegeprobe','neu','angelegt',"
                    "'Testperson' FROM vorgang WHERE titel='Pflegevorgang'")
        mail.konfig_schreiben(con, {"frist_kopie": "Pflegeprobe, pruefer"})

    namen = {"feld": "mitarbeiter", "suchart": "genau",
             "suchwert": "Pflegeprobe", "neuer_wert": "Pflege Probe",
             "ueberall": "1"}
    vorschau = client.post("/einstellungen/datenpflege/vorschau", data=namen).text
    for stelle in ("Zeiteinträge", "Aufgaben (zuständig)", "Logbuchzeilen",
                   "Team-Eintrag", "E-Mail-Empfängerliste"):
        pruefe(stelle in vorschau, f"die Vorschau nennt „{stelle}“")

    anwenden(namen)
    with db.db() as con:
        for wort, frage in (
                ("Zeiten", "SELECT COUNT(*) c FROM eintrag WHERE "
                           "mitarbeiter='Pflege Probe'"),
                ("Team", "SELECT COUNT(*) c FROM mitarbeiter WHERE "
                         "name='Pflege Probe'"),
                ("Aufgabe", "SELECT COUNT(*) c FROM vorgang WHERE "
                            "zustaendig='Pflege Probe'"),
                ("Logbuch", "SELECT COUNT(*) c FROM vorgang_log WHERE "
                            "wer='Pflege Probe'")):
            pruefe(con.execute(frage).fetchone()["c"] > 0,
                   f"{wort} trägt den neuen Namen")
        pruefe(con.execute("SELECT COUNT(*) c FROM eintrag WHERE "
                           "mitarbeiter='Pflegeprobe'").fetchone()["c"] == 0,
               "und nirgends mehr den alten")
        k = mail.konfig_lesen(con)
    pruefe("Pflege Probe" in k["frist_kopie"],
           "auch die E-Mail-Empfängerliste wandert mit")

    # --- Zusammenführung: nichts wird gelöscht --------------------------
    zusammen = {"feld": "mitarbeiter", "suchart": "genau",
                "suchwert": "Pflege Probe", "neuer_wert": "pruefer",
                "ueberall": "1"}
    vorschau = client.post("/einstellungen/datenpflege/vorschau", data=zusammen).text
    pruefe("stillgelegt" in vorschau,
           "die Vorschau sagt, dass zusammengeführt statt umbenannt wird")
    anwenden(zusammen)
    with db.db() as con:
        alt = con.execute("SELECT aktiv FROM mitarbeiter WHERE "
                          "name='Pflege Probe'").fetchone()
        pruefe(alt is not None, "⚠️ der alte Stammeintrag ist NICHT gelöscht")
        pruefe(alt["aktiv"] == 0, "sondern nur stillgelegt")
        pruefe(con.execute("SELECT COUNT(*) c FROM mitarbeiter WHERE "
                           "name='pruefer'").fetchone()["c"] == 1,
               "und den Zielnamen gibt es genau einmal")
        con.execute("DELETE FROM eintrag WHERE id BETWEEN 941 AND 944")
        con.execute("DELETE FROM vorgang WHERE titel='Pflegevorgang'")
        con.execute("DELETE FROM mitarbeiter WHERE name='Pflege Probe'")
        mail.konfig_schreiben(con, {"frist_kopie": ""})


def test_neuigkeiten(client: TestClient) -> None:
    """Nach einer neuen Fassung steht der Changelog einmal im Bild."""
    abschnitt("Hinweis auf Neuerungen")
    from .changelog import CHANGELOG
    from .main import VERSION

    with db.db() as con:
        con.execute("UPDATE benutzer SET gesehen_version=NULL "
                    "WHERE benutzername='pruefer'")
    seite = client.get("/").text
    pruefe('class="neuheiten"' in seite, "der Hinweis steht da")
    pruefe(VERSION in seite.split('class="neuheiten"')[1][:600],
           "und nennt die neue Versionsnummer")
    pruefe(CHANGELOG[-1]["titel"] in seite, "samt Überschrift des Eintrags")
    pruefe(CHANGELOG[-1]["punkte"][0] in seite, "und den einzelnen Punkten")
    pruefe('href="/changelog"' in seite.split('class="neuheiten"')[1][:2600],
           "mit einem Weg zum vollständigen Verlauf")
    # ⚠️ Auf jeder Seite, nicht nur direkt nach dem Login: wer ihn dort
    # wegklickt, bekäme ihn sonst nie wieder.
    pruefe('class="neuheiten"' in client.get("/meinbereich").text,
           "und zwar auf jeder Seite, bis er zur Kenntnis genommen ist")

    antwort = client.post("/neuigkeiten/gelesen", data={"weiter": "/meinbereich"},
                          follow_redirects=False)
    pruefe(antwort.status_code == 303
           and antwort.headers.get("location") == "/meinbereich",
           "„Verstanden“ führt zurück, wo man war")
    pruefe('class="neuheiten"' not in client.get("/").text,
           "danach ist er weg")
    with db.db() as con:
        stand = con.execute("SELECT gesehen_version g FROM benutzer "
                            "WHERE benutzername='pruefer'").fetchone()["g"]
    pruefe(stand == VERSION, "und die Fassung ist als gesehen vermerkt")

    # Ein fremdes Ziel darf die Weiterleitung nicht annehmen.
    antwort = client.post("/neuigkeiten/gelesen",
                          data={"weiter": "https://boese.example/"},
                          follow_redirects=False)
    pruefe(antwort.headers.get("location") == "/",
           "ein fremdes Ziel wird nicht übernommen")

    # Ein frisch angelegtes Konto kennt die laufende Fassung bereits.
    _konto(client, "neuling", "neulingpasswort", ["auswertung"])
    with db.db() as con:
        neu = con.execute("SELECT gesehen_version g FROM benutzer "
                          "WHERE benutzername='neuling'").fetchone()["g"]
    pruefe(neu == VERSION,
           "ein neues Konto wird nicht mit dem Changelog begrüßt")


def test_auswertung_standard(client: TestClient) -> None:
    """Ohne Angabe zeigt die Auswertung das laufende Jahr."""
    abschnitt("Auswertung: laufendes Jahr")
    jahr = str(dt.date.today().year)

    seite = client.get("/auswertung").text
    pruefe(f"Jahr {jahr}" in seite,
           "ohne Angabe steht das laufende Jahr im Kopf")
    pruefe(f'<option value="{jahr}" selected>' in seite,
           "und die Jahresfelder sind entsprechend vorbelegt")

    # ⚠️ Wer ausdrücklich „alle“ wählt, bekommt weiterhin alles. Erkannt
    # wird das an der Abfrage: das Filterformular schickt immer alle
    # Felder mit, auch die leeren.
    alle = client.get("/auswertung?von_jahr=&bis_jahr=&von_monat=&bis_monat=").text
    pruefe("alle Zeiten" in alle,
           "mit ausdrücklich leerem Jahr gilt wieder die ganze Zeit")

    # Die vier Kennzahlen tragen alle eine Farbe.
    for klasse in ("k-geleistet", "k-bewilligt", "k-verdienst"):
        pruefe(klasse in seite, f"die Kennzahl „{klasse}“ ist eingefärbt")


def test_urlaub_halbe_tage(client: TestClient) -> None:
    """Halbe Urlaubstage zählen halb, ganze ganz."""
    abschnitt("Urlaub: halbe Tage")
    from .main import urlaubswert, urlaubstage_zaehlen
    pruefe(urlaubswert("Urlaub") == 1.0, "„Urlaub“ ist ein ganzer Tag")
    pruefe(urlaubswert("Urlaub (Halber Tag)") == 0.5,
           "„Urlaub (Halber Tag)“ ist ein halber")
    pruefe(urlaubswert("urlaub (halber tag) – vormittags") == 0.5,
           "Groß-/Kleinschreibung ist egal")
    pruefe(urlaubswert("Entlastungsgespräch, Strukturplan Urlaub") == 0.0,
           "„Urlaub“ mitten im Text zählt nicht (beginnt nicht damit)")
    zeilen = [
        {"datum": "2026-03-02", "beschreibung": "Urlaub"},
        {"datum": "2026-03-03", "beschreibung": "Urlaub (Halber Tag)"},
        {"datum": "2026-03-03", "beschreibung": "Hausbesuch"},
        {"datum": "2026-03-04", "beschreibung": "Urlaub (Halber Tag)"},
        {"datum": "2026-03-04", "beschreibung": "Urlaub (Halber Tag)"},
        {"datum": "2026-03-05", "beschreibung": "Urlaub (Halber Tag)"},
        {"datum": "2026-03-05", "beschreibung": "Urlaub"},
        {"datum": "2025-12-30", "beschreibung": "Urlaub"},
    ]
    jahre = urlaubstage_zaehlen(zeilen)
    pruefe(jahre.get("2026") == 3.0,
           "3 Tage 2026: ganz + halb + halb (zwei halbe am Tag = ein halber) + ganz")
    pruefe(jahre.get("2025") == 1.0, "und ein ganzer Tag 2025")


def test_selbstzahler(client: TestClient) -> None:
    """Ein Selbstzahler braucht keinen Bescheid und wirft keine Warnung."""
    abschnitt("Betreute Person: Selbstzahler")
    from .main import bewilligungslage
    # Ohne Zeitraum und ohne Grundwert waere die Lage sonst „leer".
    stand = bewilligungslage([], 0, 0, "2026-06-01", selbstzahler=True)
    pruefe(stand["art"] == "selbstzahler",
           "die Lage ist „selbstzahler“, nicht „leer“")
    from .main import BEWILLIGUNG_HANDLUNG
    pruefe("selbstzahler" not in BEWILLIGUNG_HANDLUNG,
           "und löst damit keine Bewilligungswarnung aus")

    # Anlegen mit gesetztem Haken, dann pruefen: Badge da, keine Warnung.
    client.post("/einstellungen/person", data={
        "name": "Selbstzahler Probe", "wochenstunden": "0",
        "stundensatz": "60,00", "abrechenbar": "1", "selbstzahler": "1"})
    seite = client.get("/einstellungen?bereich=betreute").text
    # Die Zeile beginnt am <details> VOR dem Namen, dort steht die
    # Statusklasse; sie endet am nächsten </details>.
    anfang = seite.rindex("<details", 0, seite.index("Selbstzahler Probe"))
    ende = seite.index("</details>", seite.index("Selbstzahler Probe"))
    block = seite[anfang:ende]
    pruefe("Selbstzahler" in block, "die Person trägt die Marke „Selbstzahler“")
    pruefe('class="marke-status info"' in block,
           "die Marke steht als blaue Pille in der Statusspalte, wie „gültig“")
    pruefe("p-selbstzahler" in block,
           "und die Zeile trägt die Statusklasse für die blaue Färbung")
    pruefe("ohne-bewilligung" not in block,
           "und keinen roten Balken für eine fehlende Bewilligung")

    with db.db() as con:
        wert = con.execute("SELECT selbstzahler FROM person WHERE name=?",
                           ("Selbstzahler Probe",)).fetchone()
        pruefe(wert and wert["selbstzahler"] == 1,
               "der Haken steht in der Datenbank")

    # Sie taucht nicht in „Bewilligungen im Blick" auf (bewilligungen_pruefen
    # liefert nur, was in BEWILLIGUNG_HANDLUNG steht).
    from .main import bewilligungen_pruefen
    with db.db() as con:
        offen = bewilligungen_pruefen(con)
    pruefe(not any(b["name"] == "Selbstzahler Probe" for b in offen),
           "und steht in keiner Bewilligungsliste")

    # In der Auswertung steht für einen Selbstzahler „Selbstzahler“ statt
    # „Grundwert … ohne Bescheid“. Dafür braucht die Person erfasste Zeit.
    with db.db() as con:
        con.execute(
            "INSERT OR IGNORE INTO eintrag (mitarbeiter, datum, monat, start, "
            "ende, klient, beschreibung, dauer_min, abrechenbar, fingerprint, "
            "angelegt_am) VALUES ('pruefer','2026-05-04','2026-05','09:00',"
            "'11:00','Selbstzahler Probe','Besuch',120,1,'szp1','2026-05-04 09:00')")
    ausw = client.get("/auswertung?von_jahr=2026&von_monat=05&"
                      "bis_jahr=2026&bis_monat=05").text
    seitenspalte = ausw[ausw.index("Selbstzahler Probe"):] \
        if "Selbstzahler Probe" in ausw else ""
    pruefe('<span class="marke-status info">Selbstzahler</span>' in ausw,
           "die Auswertung nennt den Selbstzahler beim Namen, nicht „Grundwert“")

    # Zeilenfärbung nach Status: eine gültige Person grün, eine leere rot.
    with db.db() as con:
        con.execute("INSERT OR IGNORE INTO person (name, wochenstunden, "
                    "stundensatz, aktiv, angelegt_am) VALUES "
                    "('Leer Probe', 0, 0, 1, '2026-01-01 08:00')")
    seite2 = client.get("/einstellungen?bereich=betreute").text
    def zeile(name):
        a = seite2.rindex("<details", 0, seite2.index(name))
        return seite2[a:seite2.index("</details>", seite2.index(name))]
    pruefe("p-leer" in zeile("Leer Probe"),
           "eine Person ohne alles trägt die rote Statusklasse")
    css = client.get("/static/style.css").text
    pruefe(".konto.person.p-leer" in css and ".konto.person.p-laufend" in css
           and ".konto.person.p-selbstzahler" in css,
           "und das Stylesheet färbt die Zeilen je nach Stand")


def test_zuweisungsmail(client: TestClient) -> None:
    """Neue Aufgaben lösen eine gesammelte Mail aus."""
    abschnitt("E-Mail: neue Aufgabe zugewiesen")
    from . import mail

    # Optionen sind in der Oberflaeche vorhanden und speicherbar.
    seite = client.get("/einstellungen?bereich=email").text
    pruefe('action="/einstellungen/zuweisungsmail"' in seite,
           "die Einstellungen kennen die Zuweisungsmail")
    pruefe("zuweisung_verzug" in seite, "samt Sammelverzug")
    client.post("/einstellungen/zuweisungsmail",
                data={"zuweisung_aktiv": "1", "zuweisung_verzug": "0"})
    with db.db() as con:
        k = mail.konfig_lesen(con)
    pruefe(k["zuweisung_aktiv"] == "1" and k["zuweisung_verzug"] == "0",
           "und speichern die Werte")

    # Ein zu grosser Verzug wird begrenzt.
    client.post("/einstellungen/zuweisungsmail",
                data={"zuweisung_aktiv": "1", "zuweisung_verzug": "99999"})
    with db.db() as con:
        pruefe(mail.konfig_lesen(con)["zuweisung_verzug"] == "1440",
               "ein zu großer Verzug wird auf 1440 Minuten begrenzt")

    # --- die Sammel-Logik selbst -------------------------------------------
    gesendet = []
    echt_senden, echt_adresse = mail.senden, mail.adresse_fuer
    try:
        mail.senden = lambda adr, betr, txt, kk=None: (
            gesendet.append((adr, betr, txt)) or (True, "ok"))
        mail.adresse_fuer = lambda con, name: (
            "post@x" if name.strip().lower() == "zuweisungs-tester" else None)
        with db.db() as con:
            con.execute(
                "INSERT OR IGNORE INTO person (name, aktiv, angelegt_am) "
                "VALUES ('Z-Klient', 1, '2026-01-01 08:00')")
            # ein ALTER Vorgang, schon gemeldet - darf nicht mitkommen
            con.execute(
                "INSERT INTO vorgang (klient, art, titel, zustaendig, status, "
                "prioritaet, angelegt_am, angelegt_von, zuweis_gemeldet) VALUES "
                "('Z-Klient','Antrag','Alt','Zuweisungs-Tester','Offen','Normal',"
                "'2026-01-01 08:00','timo',1)")
            # zwei NEUE Vorgaenge fuer dieselbe Person
            for titel in ("Neu A", "Neu B"):
                con.execute(
                    "INSERT INTO vorgang (klient, art, titel, zustaendig, status, "
                    "prioritaet, angelegt_am, angelegt_von, zuweis_gemeldet) VALUES "
                    "('Z-Klient','Antrag',?,'Zuweisungs-Tester','Offen','Normal',"
                    "'2026-01-01 08:00','timo',0)", (titel,))
            k = mail.konfig_lesen(con)
            k = dict(k, mail_aktiv="1", zuweisung_aktiv="1", zuweisung_verzug="0")
            prot = mail.pruefe_zuweisungen(con, k)
        pruefe(len(gesendet) == 1,
               "beide neuen Aufgaben kommen in EINE Mail, nicht zwei")
        if gesendet:
            _adr, betreff, text = gesendet[0]
            pruefe("Neu A" in text and "Neu B" in text,
                   "und die Mail nennt beide Aufgaben")
            pruefe("Alt" not in text,
                   "die schon gemeldete alte Aufgabe steht nicht drin")
            pruefe("(2)" in betreff,
                   "der Betreff nennt die Anzahl")
        with db.db() as con:
            offen = con.execute(
                "SELECT COUNT(*) c FROM vorgang WHERE zuweis_gemeldet=0 "
                "AND zustaendig='Zuweisungs-Tester'").fetchone()["c"]
        pruefe(offen == 0, "nach dem Versand ist nichts mehr offen")
    finally:
        mail.senden, mail.adresse_fuer = echt_senden, echt_adresse


def test_zuweisung_altbestand(client: TestClient) -> None:
    """Bestehende Aufgaben lösen beim Update keine Sammelmail aus."""
    abschnitt("E-Mail: Altbestand bleibt still")
    # ⚠️ Der Kern der Migration: waere zuweis_gemeldet fuer alte Vorgaenge
    # 0, bekaeme das Team beim Update eine Mail ueber die ganze Historie.
    # Die Migration setzt sie deshalb auf 1. Neu angelegte Vorgaenge (ueber
    # die Route) stehen dagegen auf 0.
    with db.db() as con:
        # Ein ueber die normale Route angelegter Vorgang ist "offen".
        pass
    client.post("/vorgaenge", data={
        "klient": "Testperson", "art": "Antrag", "titel": "Frischer Vorgang",
        "zustaendig": "pruefer"})
    with db.db() as con:
        frisch = con.execute(
            "SELECT zuweis_gemeldet FROM vorgang WHERE titel='Frischer Vorgang'"
        ).fetchone()
    pruefe(frisch is not None and frisch["zuweis_gemeldet"] == 0,
           "ein neu angelegter Vorgang steht auf „noch nicht gemeldet“")

    # ⚠️ Wird eine bereits gemeldete Aufgabe an eine ANDERE Person
    # übergeben, wird der Vermerk zurückgesetzt - die neue Zuständige
    # bekommt dann ihrerseits eine Zuweisungs-Mail.
    with db.db() as con:
        vid = con.execute(
            "SELECT id FROM vorgang WHERE titel='Frischer Vorgang'"
        ).fetchone()["id"]
        con.execute("UPDATE vorgang SET zuweis_gemeldet=1 WHERE id=?", (vid,))
    # Übergabe an dieselbe Person: kein Wechsel, Vermerk bleibt.
    client.post(f"/vorgaenge/{vid}/zustaendig",
                data={"zustaendig": "pruefer", "notiz": ""})
    with db.db() as con:
        gleich = con.execute(
            "SELECT zuweis_gemeldet FROM vorgang WHERE id=?", (vid,)
        ).fetchone()["zuweis_gemeldet"]
    pruefe(gleich == 1, "Übergabe auf denselben Namen löst keine neue Mail aus")
    # Übergabe an eine andere Person: Wechsel, Vermerk wird zurückgesetzt.
    client.post(f"/vorgaenge/{vid}/zustaendig",
                data={"zustaendig": "Neue Zuständige", "notiz": ""})
    with db.db() as con:
        neu_wert = con.execute(
            "SELECT zustaendig, zuweis_gemeldet FROM vorgang WHERE id=?", (vid,)
        ).fetchone()
    pruefe(neu_wert["zustaendig"] == "Neue Zuständige"
           and neu_wert["zuweis_gemeldet"] == 0,
           "eine Übergabe an eine andere Person meldet die Aufgabe neu")


def test_dateien_kein_ziehhinweis(client: TestClient) -> None:
    """Der Ziehhinweis in der Dateiverwaltung ist entfernt."""
    abschnitt("Dateien: kein Ziehhinweis")
    # ⚠️ Der Hinweis-auf-Neuerungen zitiert den Changelog, in dem der
    # entfernte Satz vorkommt - vor der Prüfung also am Dialog abschneiden.
    seite = client.get("/dateien").text.split('<div class="neuheiten"')[0]
    pruefe("einfach hierher ziehen" not in seite,
           "der Hinweis „oder Dateien einfach hierher ziehen“ ist weg")
    pruefe("dateiziehhinweis" not in seite,
           "auch die zugehörige Klasse steht nicht mehr im Markup")


def test_wiki_bildgroesse(client: TestClient) -> None:
    """Eine Prozentangabe hinter der Bildadresse skaliert das Bild."""
    abschnitt("Wiki: Bildgröße in Prozent")
    from . import markdown as md
    # ⚠️ Die Groesse muss VOR der Adressaufloesung gelesen werden, sonst
    # kodiert der Aufloeser das „ =30%" weg. Deshalb hier mit einem
    # Aufloeser, der die Adresse veraendert - so faellt der Fehler auf.
    html = md.zu_html("![x](/dateien/holen/plan.png =30%)")
    pruefe('style="width: 30%; max-width: 30%"' in html,
           "die Prozentangabe wird zu width und max-width")
    pruefe("=30%" not in html and "%3D30" not in html,
           "und steht nicht mehr in der Bildadresse")
    pruefe('src="/dateien/holen/plan.png"' in html,
           "die Adresse selbst bleibt sauber")
    # Werte ausserhalb 1-100 werden geklemmt.
    pruefe('width: 100%' in md.zu_html("![x](/a.png =250%)"),
           "über 100 % wird auf 100 begrenzt")
    # Ohne Angabe kein style.
    pruefe("style=" not in md.zu_html("![x](/a.png)"),
           "ohne Angabe bleibt das Bild unverändert")


def test_wiki_hauptknoepfe(client: TestClient) -> None:
    """Anlegen geht auch aus dem Hauptfenster, nicht nur der Seitenleiste."""
    abschnitt("Wiki: Anlegen-Knöpfe im Hauptfenster")
    client.post("/wiki/aktion/neu",
                data={"name": "Knopftest", "ordner": "", "art": "ordner"})
    seite = client.get("/wiki/Knopftest").text
    pruefe(seite.count('class="knopf-icon wiki-neu-knopf"') == 2,
           "in der Ordner-Werkzeugleiste stehen zwei Anlegen-Knöpfe")
    pruefe('data-wunsch="seite"' in seite and 'data-wunsch="ordner"' in seite,
           "einer für eine Seite, einer für einen Ordner")
    stil = client.get("/static/style.css").text
    pruefe(".wiki-anlegen.mit-knopf:not([open])" in stil,
           "zugeklappt bringt der Anlegen-Block weder Linie noch Abstand mit")


def test_mobile_tabellen(client: TestClient) -> None:
    """Wiki-Tabellen und die Dateiliste rollen auf dem Telefon statt zu stauchen."""
    abschnitt("Mobile Tabellen")
    stil = client.get("/static/style.css").text
    # Wiki-Tabelle: an ihrem Inhalt ausgerichtet, Zellen brechen normal um.
    pruefe("min-width: 100%; border-collapse: collapse;" in stil,
           "die Wiki-Tabelle richtet sich nach ihrem Inhalt (min-width statt fix)")
    pruefe(".wiki-tabelle th, .wiki-tabelle td {" in stil
           and "word-break: normal;" in stil,
           "und ihre Zellen brechen zwischen Wörtern um, nicht mittendrin")
    # Dateiliste: rollt unterhalb von 760px.
    pruefe(".tabellenrolle:has(.dateiverzeichnis)," in stil,
           "die Dateiliste rollt am Telefon in ihrer eigenen Hülle")


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
    pruefe("Listen oder Kacheln" in einst and "dateiliste-knopf" in einst,
           "der Umschalter steht unter Einstellungen → Oberfläche")
    # ⚠️ Beide Möglichkeiten stehen als eigene Knöpfe da, nicht als ein
    # Kippschalter mit wechselndem Wort.
    pruefe(einst.count('class="dateiliste-knopf"') == 2,
           "und zwar als Paar: Liste und Kacheln nebeneinander")

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
        test_mehrere_betreute(client)
        test_bewilligungsstand(client)
        test_bewilligungen_mein_bereich(client)
        test_uebersicht_filter(client)
        test_meinbereich_aufbau(client)
        test_vorgang_anlegen(client)
        test_dringlichkeit(client)
        test_automatische_sicherung(client)
        test_csrf(client)
        test_bewilligungsmail(client)
        test_erinnerungsoptionen(client)
        test_texte_nachziehen(client)
        test_fusszeile(client)
        test_mehrfachauswahl(client)
        test_wiki_geschuetzter_ordner(client)
        test_fusszeile_buendig(client)
        test_kfz_linksbuendig(client)
        test_zeitspanne_meinbereich(client)
        test_spruch_hoehe(client)
        test_urlaub_halbe_tage(client)
        test_selbstzahler(client)
        test_zuweisungsmail(client)
        test_zuweisung_altbestand(client)
        test_dateien_kein_ziehhinweis(client)
        test_wiki_bildgroesse(client)
        test_wiki_hauptknoepfe(client)
        test_mobile_tabellen(client)
        test_versandzeit(client)
        test_zitat_abstand(client)
        test_diagramm_wertmarke(client)
        test_meinbereich_hinweise(client)
        test_leistungen_umbenannt(client)
        test_betreute_auswahl(client)
        test_abgaben_verweise(client)
        test_wiki_falten(client)
        test_werkzeuge(client)
        test_verlaufsdiagramm(client)
        test_datenpflege(client)
        test_auswertung_standard(client)
        test_neuigkeiten(client)
        test_farbvariablen(client)
        test_bewilligung_nachfolge(client)
        test_versionen()
    except Exception:
        print("\nUnerwarteter Abbruch:")
        traceback.print_exc()
        _ERGEBNIS["fehler"].append("Abbruch mit Ausnahme")


if __name__ == "__main__":
    code = main_lauf()
    shutil.rmtree(_ORDNER, ignore_errors=True)
    sys.exit(code)
