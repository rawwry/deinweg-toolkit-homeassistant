"""SQLite-Zugriff. Eine Datei, WAL-Modus, Schema wird beim Start angelegt."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager

DB_PFAD = os.environ.get("DB_PFAD", "/db/zeiten.db")

# Fuer den allerersten Administrator-Zugang, siehe init() weiter unten
ADMIN_BENUTZERNAME = os.environ.get("ADMIN_BENUTZERNAME", "timo")
ADMIN_PASSWORT = os.environ.get("ADMIN_PASSWORT", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS import (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dateiname        TEXT NOT NULL,
    mitarbeiter      TEXT,
    hochgeladen_am   TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'vorschau',
    zeilen_gesamt    INTEGER DEFAULT 0,
    zeilen_neu       INTEGER DEFAULT 0,
    zeilen_dubletten INTEGER DEFAULT 0,
    quelle           TEXT DEFAULT 'Upload',
    notiz            TEXT
);

CREATE TABLE IF NOT EXISTS eintrag (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id    INTEGER REFERENCES import(id) ON DELETE SET NULL,
    mitarbeiter  TEXT NOT NULL,
    datum        TEXT NOT NULL,
    monat        TEXT NOT NULL,
    start        TEXT,
    ende         TEXT,
    klient       TEXT NOT NULL,
    beschreibung TEXT,
    dauer_min    INTEGER NOT NULL,
    abrechenbar  INTEGER NOT NULL DEFAULT 1,
    fingerprint  TEXT NOT NULL,
    angelegt_am  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eintrag_fp    ON eintrag(fingerprint);
CREATE INDEX IF NOT EXISTS idx_eintrag_monat ON eintrag(monat);
CREATE INDEX IF NOT EXISTS idx_eintrag_ma    ON eintrag(mitarbeiter);
CREATE INDEX IF NOT EXISTS idx_eintrag_kl    ON eintrag(klient);

CREATE TABLE IF NOT EXISTS vorschau (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id    INTEGER NOT NULL REFERENCES import(id) ON DELETE CASCADE,
    mitarbeiter  TEXT NOT NULL,
    datum        TEXT NOT NULL,
    monat        TEXT NOT NULL,
    start        TEXT,
    ende         TEXT,
    klient       TEXT NOT NULL,
    beschreibung TEXT,
    dauer_min    INTEGER NOT NULL,
    abrechenbar  INTEGER NOT NULL DEFAULT 1,
    fingerprint  TEXT NOT NULL,
    dublette     TEXT,
    warnung      TEXT
);

CREATE INDEX IF NOT EXISTS idx_vorschau_imp ON vorschau(import_id);

-- Stammdaten der betreuten Personen inklusive Wochenkontingent
CREATE TABLE IF NOT EXISTS person (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    wochenstunden  REAL NOT NULL DEFAULT 0,
    stundensatz    REAL NOT NULL DEFAULT 0,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    abrechenbar    INTEGER NOT NULL DEFAULT 1,
    angelegt_am    TEXT NOT NULL
);

-- das Team. Grundlage fuer die Abgabeuebersicht auf der Startseite
CREATE TABLE IF NOT EXISTS mitarbeiter (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    abgabepflicht  INTEGER NOT NULL DEFAULT 1,
    monatsstunden  REAL NOT NULL DEFAULT 0,
    urlaubstage    REAL NOT NULL DEFAULT 0,
    notiz          TEXT,
    angelegt_am    TEXT NOT NULL
);

-- vom Benutzer gepflegte Vorgangsarten fuer die Verwaltungsvorgaenge,
-- ersetzt die frueher fest im Code hinterlegte Liste
CREATE TABLE IF NOT EXISTS vorgangsart (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    angelegt_am    TEXT NOT NULL
);

-- vom Benutzer gepflegte Leistungsbeschreibungen fuer die manuelle
-- Erfassung. Sie dienen allein der einheitlichen Schreibweise: der
-- gewaehlte Text landet als Klartext in eintrag.beschreibung, es gibt
-- also bewusst keinen Fremdschluessel - genau wie bei vorgangsart.
CREATE TABLE IF NOT EXISTS leistung (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    angelegt_am    TEXT NOT NULL
);

-- Login-Benutzer. Bewusst getrennt von "mitarbeiter": ein Mitarbeiter muss
-- keinen Login besitzen, ein Login muss keinem Mitarbeiter entsprechen.
-- berechtigungen ist NULL/leer = voller Zugriff auf alle Bereiche (auch auf
-- solche, die es zum Zeitpunkt der Anlage noch nicht gab); ist es befuellt,
-- steht dort eine kommagetrennte Liste erlaubter Bereichs-Schluessel
-- (siehe auth.BEREICHE). Gilt nur fuer rolle="benutzer" - "admin" hat immer
-- vollen Zugriff, unabhaengig vom Inhalt dieser Spalte.
CREATE TABLE IF NOT EXISTS benutzer (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    benutzername   TEXT NOT NULL UNIQUE,
    passwort_hash  TEXT NOT NULL,
    rolle          TEXT NOT NULL DEFAULT 'benutzer',
    berechtigungen TEXT,
    email          TEXT,
    mitarbeiter    TEXT,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    fremde_loeschen  INTEGER NOT NULL DEFAULT 0,
    fremde_bearbeiten INTEGER NOT NULL DEFAULT 0,
    wiki_schreiben   INTEGER NOT NULL DEFAULT 1,
    angelegt_am    TEXT NOT NULL,
    letzter_login  TEXT
);

-- angemeldete Sitzungen. Eine Zeile je Login, das Cookie enthaelt nur den
-- Token. Loeschen der Zeile meldet die Sitzung sofort ab (z.B. beim
-- Deaktivieren eines Benutzers oder per Abmelden-Knopf).
CREATE TABLE IF NOT EXISTS sitzung (
    token             TEXT PRIMARY KEY,
    benutzer_id       INTEGER NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    erstellt_am       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sitzung_benutzer ON sitzung(benutzer_id);

-- freie Schluessel/Wert-Ablage fuer Einstellungen, die zur Laufzeit
-- aenderbar sein sollen (SMTP-Zugang, E-Mail-Vorlagen). Bewusst nicht in
-- strings.txt, weil hier auch Zugangsdaten liegen und die Pflege ueber die
-- Oberflaeche laufen soll.
CREATE TABLE IF NOT EXISTS konfig (
    schluessel  TEXT PRIMARY KEY,
    wert        TEXT,
    geaendert_am TEXT
);

-- Merkliste bereits verschickter Benachrichtigungen. Verhindert, dass bei
-- jedem Durchlauf des Weckers erneut dieselbe Mail rausgeht.
CREATE TABLE IF NOT EXISTS benachrichtigung (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    art         TEXT NOT NULL,
    bezug       TEXT NOT NULL,
    empfaenger  TEXT NOT NULL,
    gesendet_am TEXT NOT NULL,
    erfolg      INTEGER NOT NULL DEFAULT 1,
    meldung     TEXT,
    UNIQUE (art, bezug, empfaenger)
);

-- organisatorische Vorgaenge rund um betreute Personen (Verwaltungsvorgaenge).
-- klient ist absichtlich ein Name und kein Fremdschluessel: die betreuten
-- Personen kommen aus den hochgeladenen Arbeitslisten (eintrag.klient) und
-- werden fuer dieses Modul nicht neu angelegt.
CREATE TABLE IF NOT EXISTS vorgang (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    klient             TEXT NOT NULL,
    art                TEXT NOT NULL,
    titel              TEXT NOT NULL,
    beschreibung       TEXT,
    zustaendig         TEXT NOT NULL,
    beteiligte         TEXT,
    status             TEXT NOT NULL DEFAULT 'Offen',
    prioritaet         TEXT NOT NULL DEFAULT 'Normal',
    frist              TEXT,
    angelegt_am        TEXT NOT NULL,
    angelegt_von       TEXT NOT NULL,
    geaendert_am       TEXT,
    datum_eingereicht  TEXT,
    datum_eingang      TEXT,
    datum_rueckmeldung TEXT,
    datum_erledigt     TEXT,
    dateiverweis       TEXT
);

CREATE INDEX IF NOT EXISTS idx_vorgang_klient ON vorgang(klient);
CREATE INDEX IF NOT EXISTS idx_vorgang_status ON vorgang(status);
CREATE INDEX IF NOT EXISTS idx_vorgang_frist  ON vorgang(frist);

-- fortlaufendes Logbuch. Zeilen werden nur angehaengt, nie geaendert.
CREATE TABLE IF NOT EXISTS vorgang_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vorgang_id    INTEGER REFERENCES vorgang(id) ON DELETE CASCADE,
    -- Titel des Vorgangs, aber nur bei geloeschten Vorgaengen gefuellt.
    -- Solange der Vorgang existiert, steht der Titel dort und wird per
    -- JOIN geholt; erst beim Loeschen wird er hierher kopiert, damit das
    -- Logbuch weiterhin sagen kann, worum es ging.
    vorgang_titel TEXT,
    klient        TEXT NOT NULL,
    zeitpunkt     TEXT NOT NULL,
    wer           TEXT NOT NULL,
    aktion        TEXT NOT NULL,
    beschreibung  TEXT
);

CREATE INDEX IF NOT EXISTS idx_vlog_vorgang ON vorgang_log(vorgang_id);
CREATE INDEX IF NOT EXISTS idx_vlog_klient  ON vorgang_log(klient);

-- Fuhrpark: Fahrzeugstammdaten. Gepflegt unter Einstellungen -> KFZ.
-- "aktiv" trennt den laufenden Fuhrpark von archivierten Fahrzeugen;
-- geloescht wird ein Fahrzeug nur ausdruecklich, dann faellt ueber den
-- Fremdschluessel auch seine Historie weg.
CREATE TABLE IF NOT EXISTS fahrzeug (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kennzeichen    TEXT NOT NULL,
    marke          TEXT,
    modell         TEXT,
    baujahr        INTEGER,
    erstzulassung  TEXT,
    km_start       INTEGER NOT NULL DEFAULT 0,
    kraftstoff     TEXT,
    leistung       INTEGER,
    hubraum        INTEGER,
    getriebe       TEXT,
    farbe          TEXT,
    notiz          TEXT,
    aktiv          INTEGER NOT NULL DEFAULT 1,
    angelegt_am    TEXT NOT NULL,
    geaendert_am   TEXT
);

CREATE INDEX IF NOT EXISTS idx_fahrzeug_aktiv ON fahrzeug(aktiv);

-- Alle Ereignisse eines Fahrzeugs in einer Tabelle: Tanken, Inspektion,
-- Wartung, Reparatur, Reifenwechsel, TUEV, reiner Kilometerstand und
-- sonstige Kosten. Bewusst eine gemeinsame Struktur statt sieben fast
-- gleicher Tabellen - jede Erfassungsart fuellt davon die Felder, die sie
-- braucht, der Rest bleibt NULL.
--
-- Wichtig fuer die Auswertung:
-- * "km" ist zugleich die Kilometerstandshistorie. Wer beim Tanken einen
--   Kilometerstand eintraegt, muss ihn nicht zusaetzlich als eigenen
--   Eintrag erfassen.
-- * "voll" markiert eine Volltankung. Nur zwischen zwei Volltankungen
--   laesst sich ein Verbrauch sauber rechnen.
-- * "faellig_datum" und "faellig_km" werden beim Speichern aus den
--   Intervallen berechnet und mitgeschrieben. So kann ein spaeteres
--   Erinnerungssystem sie abfragen, ohne die Rechnung zu kennen.
CREATE TABLE IF NOT EXISTS fahrzeug_ereignis (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fahrzeug_id      INTEGER NOT NULL REFERENCES fahrzeug(id) ON DELETE CASCADE,
    art              TEXT NOT NULL,
    datum            TEXT NOT NULL,
    monat            TEXT NOT NULL,
    km               INTEGER,
    kosten           REAL,
    liter            REAL,
    voll             INTEGER NOT NULL DEFAULT 1,
    wartungsart      TEXT,
    wechsel_art      TEXT,
    beschreibung     TEXT,
    werkstatt        TEXT,
    notiz            TEXT,
    faellig_datum    TEXT,
    faellig_km       INTEGER,
    intervall_monate INTEGER,
    intervall_km     INTEGER,
    angelegt_am      TEXT NOT NULL,
    angelegt_von     TEXT
);

CREATE INDEX IF NOT EXISTS idx_ereignis_fahrzeug ON fahrzeug_ereignis(fahrzeug_id);
CREATE INDEX IF NOT EXISTS idx_ereignis_art      ON fahrzeug_ereignis(art);
CREATE INDEX IF NOT EXISTS idx_ereignis_datum    ON fahrzeug_ereignis(datum);
CREATE INDEX IF NOT EXISTS idx_ereignis_monat    ON fahrzeug_ereignis(monat);
CREATE INDEX IF NOT EXISTS idx_ereignis_faellig  ON fahrzeug_ereignis(faellig_datum);

-- Vermerk zu jeder eingelesenen Quelldatei: Name, Pruefsumme, Zeitpunkt.
-- ACHTUNG: wird nur geschrieben, nirgends gelesen. Bis 0.6.10 verhinderte
-- der Hash die Doppelverarbeitung durch den Watchfolder; mit dem ist die
-- Abfrage entfallen, der Vermerk blieb stehen. Er ist damit ein reines
-- Archiv ohne Oberflaeche - entweder sichtbar machen oder wegwerfen.
CREATE TABLE IF NOT EXISTS quelldatei (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    hash           TEXT NOT NULL UNIQUE,
    dateiname      TEXT NOT NULL,
    quelle         TEXT NOT NULL,
    verarbeitet_am TEXT NOT NULL,
    import_id      INTEGER
);
"""


def verbinde() -> sqlite3.Connection:
    ordner = os.path.dirname(DB_PFAD)
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    con = sqlite3.connect(DB_PFAD, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def db():
    con = verbinde()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def spalte_ergaenzen(con, tabelle: str, spalte: str, definition: str) -> None:
    vorhanden = {r["name"] for r in con.execute(f"PRAGMA table_info({tabelle})")}
    if spalte not in vorhanden:
        con.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {definition}")


def spalte_entfernen(con, tabelle: str, spalte: str) -> None:
    """Gegenstueck zu spalte_ergaenzen: wirft eine Spalte weg, die es nicht
    mehr braucht.

    Nur fuer Spalten aufrufen, die nachweislich nirgends gelesen oder
    geschrieben werden - hier faellt echter Inhalt weg, falls doch etwas
    drinsteht. DROP COLUMN gibt es erst ab SQLite 3.35; aeltere Fassungen
    scheitern hier, und dann bleibt die Spalte eben stehen. Das ist
    unschoen, aber harmlos: niemand liest sie.
    """
    vorhanden = {r["name"] for r in con.execute(f"PRAGMA table_info({tabelle})")}
    if spalte not in vorhanden:
        return
    try:
        con.execute(f"ALTER TABLE {tabelle} DROP COLUMN {spalte}")
    except sqlite3.OperationalError as e:
        print(f"[db] {tabelle}.{spalte} liess sich nicht entfernen: {e}", flush=True)


# --- Passwoerter -------------------------------------------------------------
#
# hashlib.scrypt statt einer zusaetzlichen Abhaengigkeit (bcrypt/argon2/passlib):
# in der Python-Standardbibliothek enthalten, gilt als sicher fuer
# Passwort-Hashing. Parameter N=2^14, r=8, p=1 sind die von Colin Percival
# im urspruenglichen scrypt-Paper empfohlenen Werte fuer interaktive Logins.

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def passwort_hashen(klartext: str) -> str:
    salt = secrets.token_bytes(16)
    wert = hashlib.scrypt(klartext.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R,
                          p=_SCRYPT_P, dklen=32, maxmem=64 * 1024 * 1024)
    return f"{salt.hex()}${wert.hex()}"


def passwort_pruefen(klartext: str, gespeichert: str) -> bool:
    try:
        salt_hex, wert_hex = gespeichert.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        pruef = hashlib.scrypt(klartext.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R,
                               p=_SCRYPT_P, dklen=32, maxmem=64 * 1024 * 1024)
        return secrets.compare_digest(pruef.hex(), wert_hex)
    except (ValueError, TypeError):
        return False


# Beim allerersten Start einmalig angelegt, danach nie wieder angefasst
# ⚠️ Bewusst leer. Hier standen bis 1.1 die echten Vornamen des Teams -
# das ging, solange der Code nur auf der NAS lag. Seit das Repository
# oeffentlich auf GitHub liegt, waere das die Personalliste einer
# Einrichtung der Eingliederungshilfe im Netz. Wer neu installiert, legt
# das Team unter Einstellungen -> Mitarbeiter an; bestehende Installationen
# merken davon nichts, die Liste greift ohnehin nur beim allerersten Start.
START_TEAM: list[str] = []

# Vorbelegung der Vorgangsarten beim allerersten Start, danach frei durch den
# Benutzer unter Einstellungen -> Verwaltungsvorgaenge pflegbar
START_VORGANGSARTEN = [
    "Hilfeplan / Bericht / Stellungnahme erstellt",
    "Bericht eingereicht",
    "Antrag gestellt",
    "Fortschreibung beantragt",
    "Rückmeldung LWL / Kostenträger",
    "Unterlagen nachgereicht / nachgefordert",
    "Zielvereinbarung versendet / eingegangen",
    "GEZ-Befreiung",
    "Bescheid eingegangen",
    "Wiedervorlage / Frist",
    "Sonstiger organisatorischer Vorgang",
]


def init() -> dict | None:
    """Legt das Schema an. Gibt Angaben zum initialen Administrator zurueck,
    aber nur in dem einen Moment, in dem er gerade frisch angelegt wurde -
    main.py gibt das dann einmalig im Log aus, weil es sonst nirgends zu
    sehen waere.
    """
    initialer_admin = None
    with db() as con:
        tabellen = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        con.executescript(SCHEMA)

        # Team nur befuellen, wenn die Tabelle gerade neu entstanden ist.
        # So kommen geloeschte Namen nach einem Neustart nicht zurueck.
        if "mitarbeiter" not in tabellen:
            jetzt = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
            con.executemany(
                "INSERT OR IGNORE INTO mitarbeiter (name, angelegt_am) VALUES (?,?)",
                [(name, jetzt) for name in START_TEAM])
        # ebenso die Vorgangsarten: nur beim allerersten Anlegen der Tabelle
        if "vorgangsart" not in tabellen:
            jetzt = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
            con.executemany(
                "INSERT OR IGNORE INTO vorgangsart (name, angelegt_am) VALUES (?,?)",
                [(name, jetzt) for name in START_VORGANGSARTEN])
        # erster Administrator: nur wenn die Benutzertabelle gerade neu
        # entstanden ist UND noch kein einziger Benutzer existiert - so kann
        # dieser Codepfad einen spaeter absichtlich geloeschten Timo nicht
        # wiederbeleben, legt aber bei einer frischen Installation zuverlaessig
        # genau einen Zugang an.
        if "benutzer" not in tabellen:
            vorhanden = con.execute("SELECT COUNT(*) c FROM benutzer").fetchone()["c"]
            if not vorhanden:
                jetzt = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
                generiert = not bool(ADMIN_PASSWORT)
                passwort = ADMIN_PASSWORT or secrets.token_urlsafe(9)
                con.execute(
                    "INSERT INTO benutzer (benutzername, passwort_hash, rolle, "
                    "angelegt_am) VALUES (?,?,?,?)",
                    (ADMIN_BENUTZERNAME, passwort_hashen(passwort), "admin", jetzt))
                initialer_admin = {"benutzername": ADMIN_BENUTZERNAME,
                                   "passwort": passwort, "generiert": generiert}
        # sanfte Migration aelterer Datenbanken
        spalte_ergaenzen(con, "import", "quelle", "TEXT DEFAULT 'Upload'")
        spalte_ergaenzen(con, "import", "archivpfad", "TEXT")
        spalte_ergaenzen(con, "person", "stundensatz", "REAL NOT NULL DEFAULT 0")
        spalte_ergaenzen(con, "person", "abrechenbar", "INTEGER NOT NULL DEFAULT 1")
        # Verknuepfung Login -> Mitarbeiter. Bis 2.1 lief die Zuordnung fuer
        # E-Mail-Erinnerungen allein ueber Namensgleichheit; das greift nur,
        # wenn der Benutzername exakt so heisst wie der Mitarbeiter.
        spalte_ergaenzen(con, "benutzer", "mitarbeiter", "TEXT")
        # Monatliche Sollarbeitszeit in Stunden. 0 = nicht hinterlegt, dann
        # wird fuer diese Person kein Saldo berechnet.
        spalte_ergaenzen(con, "mitarbeiter", "monatsstunden",
                         "REAL NOT NULL DEFAULT 0")
        # Urlaubsanspruch in Tagen pro Kalenderjahr. 0 = nicht hinterlegt.
        spalte_ergaenzen(con, "mitarbeiter", "urlaubstage",
                         "REAL NOT NULL DEFAULT 0")
        # Darf dieser Benutzer Zeiteintraege ANDERER loeschen? Bewusst mit
        # Standard 0: das Recht muss ausdruecklich erteilt werden. Die
        # eigenen Eintraege darf jeder immer loeschen, dafuer braucht es
        # keinen Schalter (siehe main.darf_eintrag_loeschen).
        spalte_ergaenzen(con, "benutzer", "fremde_loeschen",
                         "INTEGER NOT NULL DEFAULT 0")
        # Dasselbe fuers Bearbeiten. Getrennt vom Loeschen, weil beides
        # verschieden schwer wiegt: eine geloeschte Zeile faellt auf, eine
        # stillschweigend geaenderte nicht. Wer nur eine Schreibweise
        # richtigstellen soll, braucht kein Loeschrecht - und umgekehrt.
        spalte_ergaenzen(con, "benutzer", "fremde_bearbeiten",
                         "INTEGER NOT NULL DEFAULT 0")
        # Darf dieser Benutzer Wiki-Seiten aendern? Standard 1, weil bis
        # hierher jeder mit Wiki-Zugriff auch schreiben durfte - ein
        # Standard von 0 haette bestehenden Konten stillschweigend eine
        # Faehigkeit genommen.
        spalte_ergaenzen(con, "benutzer", "wiki_schreiben",
                         "INTEGER NOT NULL DEFAULT 1")
        # Titel eines geloeschten Vorgangs, siehe Schema oben.
        spalte_ergaenzen(con, "vorgang_log", "vorgang_titel", "TEXT")

        # --- mit 0.8.9 weggeraeumt ------------------------------------------
        # Alle vier wurden nirgends gelesen und standen nur noch im Schema:
        # die beiden archivpfade und quelldatei.fehler sind Reste des mit
        # 0.6.10 entfernten Watchfolders, person.notiz war nie an eine
        # Oberflaeche angeschlossen, und sitzung.letzte_aktivitaet wurde
        # beim Anlegen einmal gefuellt und danach nie wieder angefasst -
        # der Name versprach etwas, das der Code nicht einloest.
        for tabelle, spalte in (("person", "notiz"),
                                ("import", "archivpfad"),
                                ("quelldatei", "archivpfad"),
                                ("quelldatei", "fehler"),
                                ("sitzung", "letzte_aktivitaet")):
            spalte_entfernen(con, tabelle, spalte)
    return initialer_admin
