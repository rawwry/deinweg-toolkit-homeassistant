"""Verwaltungsvorgaenge – organisatorische Vorgaenge rund um betreute Personen.

Bewusst getrennt von main.py, weil das Modul eigenstaendig ist. Eingebunden
wird es am Ende von main.py ueber setup() und include_router().

Grundgedanken:
* Betreute Personen werden hier nie angelegt. Die Auswahl kommt aus den
  bereits importierten bzw. erfassten Zeiten (Spalte eintrag.klient).
* Nichts wird ueberschrieben: jede Aenderung schreibt zusaetzlich eine Zeile
  in vorgang_log. Erledigtes wird nicht geloescht, sondern bleibt als
  abgeschlossener Vorgang in der Historie der betreuten Person stehen.
* Es gibt keine Benutzeranmeldung im Tool. Wer handelt, wird darum bei jeder
  Aktion aus dem Team ausgewaehlt. Die letzte Wahl merkt sich der Browser.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import db

router = APIRouter(prefix="/vorgaenge")

# von setup() gefuellt, damit dieses Modul main.py nicht importieren muss
_umgebung: dict = {}


# --- Festlegungen -----------------------------------------------------------

STATUS_LISTE = [
    "Offen",
    "In Bearbeitung",
    "Eingereicht",
    "Warten auf Rückmeldung",
    "Rückfrage / Unterlagen fehlen",
    "Erledigt",
    "Abgebrochen",
]

# Status, die einen Vorgang abschliessen. Er verschwindet dann aus der
# Uebersicht der offenen Vorgaenge, bleibt aber vollstaendig erhalten.
ABGESCHLOSSEN = ("Erledigt", "Abgebrochen")

# Status, bei denen auf jemand anderen gewartet wird
WARTEND = ("Eingereicht", "Warten auf Rückmeldung")

PRIORITAETEN = ["Niedrig", "Normal", "Hoch", "Dringend"]

# Farbklassen fuer die Statusmarke, siehe style.css
STATUS_KLASSE = {
    "Offen": "vs-offen",
    "In Bearbeitung": "vs-arbeit",
    "Eingereicht": "vs-eingereicht",
    "Warten auf Rückmeldung": "vs-warten",
    "Rückfrage / Unterlagen fehlen": "vs-rueckfrage",
    "Erledigt": "vs-erledigt",
    "Abgebrochen": "vs-abgebrochen",
}

PRIO_KLASSE = {
    "Niedrig": "vp-niedrig",
    "Normal": "vp-normal",
    "Hoch": "vp-hoch",
    "Dringend": "vp-dringend",
}

BALD_TAGE = 7  # was als "bald fällig" gilt

# Farbklasse je Logaktion. Das Logbuch besteht sonst aus lauter gleich
# aussehenden Zeilen; die Marke ist die einzige Stelle, an der auf einen
# Blick steht, WAS passiert ist - sie darf das auch zeigen.
LOG_KLASSE = {
    "Vorgang angelegt":        "la-neu",
    "Vorgang bearbeitet":      "la-aenderung",
    "Status geändert":         "la-aenderung",
    "Zuständigkeit geändert":  "la-aenderung",
    "Frist geändert":          "la-aenderung",
    "Notiz":                   "la-notiz",
    "Vorgang erledigt":        "la-gut",
    "Vorgang abgebrochen":     "la-weg",
    "Vorgang gelöscht":        "la-weg",
}

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
              "Samstag", "Sonntag"]


def setup(templates, umgebung=None) -> None:
    """Wird von main.py aufgerufen, sobald die Templates bereitstehen.

    ``umgebung`` traegt die wenigen Dinge, die aus main.py kommen muessen -
    derzeit nur ``eigener_name``, der Mitarbeitername des angemeldeten
    Kontos. Dasselbe Muster wie bei einstellungen.py und aus demselben
    Grund: so gibt es keinen Ringschluss beim Import.
    """
    _umgebung["templates"] = templates
    _umgebung.update(umgebung or {})
    templates.env.filters["zeitpunkt"] = zeitpunkt
    templates.env.filters["uhrzeit"] = uhrzeit
    templates.env.globals.update({
        # V_ARTEN steht NICHT hier: die Vorgangsarten sind seit der
        # Einstellungen-Verwaltung pro Anfrage aus der Datenbank zu holen
        # (siehe vorgangsarten_liste()) statt einmalig fest zu stehen.
        "V_STATUS": STATUS_LISTE,
        "V_PRIO": PRIORITAETEN,
        "V_STATUS_KLASSE": STATUS_KLASSE,
        "V_PRIO_KLASSE": PRIO_KLASSE,
        "V_ABGESCHLOSSEN": ABGESCHLOSSEN,
        "V_LOG_KLASSE": LOG_KLASSE,
    })


def seite(request: Request, vorlage: str, **kontext):
    return _umgebung["templates"].TemplateResponse(
        request=request, name=vorlage, context={"seite": "vorgaenge", **kontext})


# --- kleine Helfer ----------------------------------------------------------

def jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def heute() -> str:
    return dt.date.today().isoformat()


def deutsch(datum: str) -> str:
    try:
        return dt.date.fromisoformat(datum).strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return datum or ""


def zeitpunkt(wert: str) -> str:
    """2026-08-12 10:34 wird zu 12.08.2026, 10:34 Uhr"""
    try:
        z = dt.datetime.strptime(str(wert)[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(wert or "")
    return z.strftime("%d.%m.%Y, %H:%M Uhr")


def datum_lesen(text: str) -> str:
    """Nimmt 2026-09-02 oder 02.09.2026 und gibt ISO zurueck, sonst ''."""
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


def sauber(text: str, laenge: int = 400) -> str:
    return " ".join((text or "").split())[:laenge]


def mehrzeilig(text: str, laenge: int = 4000) -> str:
    zeilen = [z.rstrip() for z in (text or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(zeilen).strip()[:laenge]


def klientenliste(con) -> list[str]:
    """Betreute Personen aus den vorhandenen Daten – nie von Hand angelegt.

    Quelle sind die erfassten bzw. importierten Zeiten. Zusaetzlich Namen, zu
    denen es schon Vorgaenge gibt, damit nichts verschwindet, falls die
    zugehoerigen Zeiten spaeter zurueckgenommen werden.
    """
    namen = {r["klient"] for r in con.execute(
        "SELECT DISTINCT klient FROM eintrag WHERE TRIM(klient) <> ''")}
    namen |= {r["klient"] for r in con.execute(
        "SELECT DISTINCT klient FROM vorgang WHERE TRIM(klient) <> ''")}
    return sorted(namen, key=lambda s: s.casefold())


def teamliste(con) -> list[str]:
    """Mitarbeitende aus der Teamliste, ergaenzt um Namen aus den Zeiten."""
    namen = {r["name"] for r in con.execute(
        "SELECT name FROM mitarbeiter WHERE aktiv=1")}
    namen |= {r["mitarbeiter"] for r in con.execute(
        "SELECT DISTINCT mitarbeiter FROM eintrag WHERE TRIM(mitarbeiter) <> ''")}
    namen |= {r["zustaendig"] for r in con.execute(
        "SELECT DISTINCT zustaendig FROM vorgang WHERE TRIM(zustaendig) <> ''")}
    return sorted(namen, key=lambda s: s.casefold())


def vorgangsarten_liste(con) -> list[str]:
    """Aktive Vorgangsarten aus den Einstellungen, ergaenzt um Arten, die an
    bestehenden Vorgaengen bereits haengen (auch wenn dort inzwischen
    stillgelegt) - so verschwindet ein Vorgang nie aus seinem eigenen
    Bearbeiten-Formular, nur weil die Art nachtraeglich deaktiviert wurde.
    """
    namen = {r["name"] for r in con.execute(
        "SELECT name FROM vorgangsart WHERE aktiv=1")}
    namen |= {r["art"] for r in con.execute(
        "SELECT DISTINCT art FROM vorgang WHERE TRIM(art) <> ''")}
    return sorted(namen, key=lambda s: s.casefold())


def protokoll(con, vorgang_id: int | None, klient: str, wer: str,
              aktion: str, beschreibung: str = "") -> None:
    """Schreibt eine Zeile ins Logbuch. Wird nie geaendert oder geloescht."""
    con.execute(
        "INSERT INTO vorgang_log (vorgang_id, klient, zeitpunkt, wer, aktion, "
        "beschreibung) VALUES (?,?,?,?,?,?)",
        (vorgang_id, klient, jetzt(), wer, aktion, beschreibung or ""))


def nach_tagen(zeilen) -> list[dict]:
    """Gruppiert Logzeilen nach Kalendertag, neueste Gruppe zuerst.

    Bewusst hier und nicht in der Vorlage: Jinjas groupby braucht einen
    Attributnamen, der Tag steckt aber in den ersten zehn Zeichen von
    "zeitpunkt". Und die Beschriftung ("Heute", "Gestern", sonst der
    Wochentag) gehoert ohnehin in den Code.

    Die Reihenfolge der uebergebenen Zeilen bleibt erhalten - die Abfrage
    sortiert bereits absteigend.
    """
    heute = dt.date.today()
    gruppen: list[dict] = []
    for z in zeilen:
        tag = (z["zeitpunkt"] or "")[:10]
        if not gruppen or gruppen[-1]["tag"] != tag:
            gruppen.append({"tag": tag, "wort": tag_wort(tag, heute), "zeilen": []})
        gruppen[-1]["zeilen"].append(z)
    return gruppen


def tag_wort(tag: str, heute: dt.date) -> str:
    try:
        datum = dt.date.fromisoformat(tag)
    except ValueError:
        return tag or "ohne Datum"
    if datum == heute:
        return "Heute · " + deutsch(tag)
    if datum == heute - dt.timedelta(days=1):
        return "Gestern · " + deutsch(tag)
    return f"{WOCHENTAGE[datum.weekday()]}, {deutsch(tag)}"


def uhrzeit(wert: str) -> str:
    """Nur die Uhrzeit aus einem Zeitpunkt "JJJJ-MM-TT HH:MM"."""
    teile = (wert or "").split(" ")
    return teile[1] if len(teile) > 1 else ""


def zurueck_zu(pfad: str, **werte) -> RedirectResponse:
    frage = urlencode({k: v for k, v in werte.items() if v})
    if not frage:
        return RedirectResponse(pfad, status_code=303)
    trenner = "&" if "?" in pfad else "?"
    return RedirectResponse(f"{pfad}{trenner}{frage}", status_code=303)


def lade(con, vorgang_id: int):
    v = con.execute("SELECT * FROM vorgang WHERE id=?", (vorgang_id,)).fetchone()
    if not v:
        raise HTTPException(404, "Vorgang nicht gefunden")
    return v


def fristlage(v) -> str:
    """'ueberfaellig', 'heute', 'bald', 'offen' oder 'zu' – fuer die Darstellung."""
    if v["status"] in ABGESCHLOSSEN:
        return "zu"
    frist = v["frist"] or ""
    if not frist:
        return "offen"
    tag = heute()
    if frist < tag:
        return "ueberfaellig"
    if frist == tag:
        return "heute"
    grenze = (dt.date.today() + dt.timedelta(days=BALD_TAGE)).isoformat()
    if frist <= grenze:
        return "bald"
    return "offen"


# --- Uebersicht -------------------------------------------------------------

def filter_bauen(klient: str, zustaendig: str, status: str, art: str,
                 faellig: str, zustand: str, q: str) -> dict:
    wo: list[str] = ["1=1"]
    werte: list = []
    aktive: list[tuple[str, str]] = []

    if klient:
        wo.append("klient = ?")
        werte.append(klient)
        aktive.append(("Betreute Person", klient))
    if zustaendig:
        wo.append("zustaendig = ?")
        werte.append(zustaendig)
        aktive.append(("Zuständig", zustaendig))
    if status:
        wo.append("status = ?")
        werte.append(status)
        aktive.append(("Status", status))
    if art:
        wo.append("art = ?")
        werte.append(art)
        aktive.append(("Vorgangsart", art))

    tag = heute()
    grenze = (dt.date.today() + dt.timedelta(days=BALD_TAGE)).isoformat()
    platzhalter = ",".join("?" * len(ABGESCHLOSSEN))

    if faellig == "heute":
        wo.append(f"frist = ? AND status NOT IN ({platzhalter})")
        werte += [tag, *ABGESCHLOSSEN]
        aktive.append(("Fälligkeit", "heute fällig"))
    elif faellig == "bald":
        wo.append(f"frist > ? AND frist <= ? AND status NOT IN ({platzhalter})")
        werte += [tag, grenze, *ABGESCHLOSSEN]
        aktive.append(("Fälligkeit", f"in den nächsten {BALD_TAGE} Tagen"))
    elif faellig == "ueberfaellig":
        wo.append(f"frist <> '' AND frist < ? AND status NOT IN ({platzhalter})")
        werte += [tag, *ABGESCHLOSSEN]
        aktive.append(("Fälligkeit", "überfällig"))
    elif faellig == "ohne":
        wo.append(f"(frist IS NULL OR frist = '') AND status NOT IN ({platzhalter})")
        werte += list(ABGESCHLOSSEN)
        aktive.append(("Fälligkeit", "ohne Frist"))
    elif faellig == "wartend":
        wo.append("status IN (%s)" % ",".join("?" * len(WARTEND)))
        werte += list(WARTEND)
        aktive.append(("Fälligkeit", "wartet auf Rückmeldung"))

    if zustand == "erledigt":
        wo.append(f"status IN ({platzhalter})")
        werte += list(ABGESCHLOSSEN)
        aktive.append(("Zustand", "erledigt oder abgebrochen"))
    elif zustand != "alle":
        zustand = "offen"
        wo.append(f"status NOT IN ({platzhalter})")
        werte += list(ABGESCHLOSSEN)

    if q:
        wo.append("(titel LIKE ? OR beschreibung LIKE ? OR klient LIKE ? "
                  "OR dateiverweis LIKE ?)")
        werte += [f"%{q}%"] * 4
        aktive.append(("Suche", q))

    felder = {"klient": klient, "zustaendig": zustaendig, "status": status,
              "art": art, "faellig": faellig, "zustand": zustand, "q": q}
    return {"wo": " AND ".join(wo), "werte": werte, "f": felder,
            "aktive": aktive,
            "query": urlencode({k: v for k, v in felder.items() if v})}


# Rang der Priorität für die Sortierung. Dringend zuerst.
_PRIO_RANG = ("CASE prioritaet WHEN 'Dringend' THEN 0 WHEN 'Hoch' THEN 1 "
              "WHEN 'Normal' THEN 2 ELSE 3 END")

# ⚠️ „Überfällig“ wiegt schwerer als „Dringend“: das eine ist eine
# Tatsache, das andere eine Einschätzung. Die Standardsortierung stellt
# deshalb zuerst alles Überfällige nach vorn und ordnet erst danach nach
# Frist und Priorität.
_UEBERFAELLIG_ZUERST = ("CASE WHEN frist <> '' AND frist < date('now','localtime') "
                        "THEN 0 ELSE 1 END")

SORTIERUNGEN = {
    "dringlichkeit": (f"{_UEBERFAELLIG_ZUERST}, "
                      "CASE WHEN frist IS NULL OR frist = '' THEN 1 ELSE 0 END, "
                      f"frist ASC, {_PRIO_RANG}, id DESC"),
    "prio": (f"{_PRIO_RANG}, "
             "CASE WHEN frist IS NULL OR frist = '' THEN 1 ELSE 0 END, frist ASC"),
    "frist": "CASE WHEN frist IS NULL OR frist = '' THEN 1 ELSE 0 END, frist ASC, id DESC",
    "frist_neu": "CASE WHEN frist IS NULL OR frist = '' THEN 1 ELSE 0 END, frist DESC, id DESC",
    "person": "klient COLLATE NOCASE ASC, frist ASC",
    "status": "status ASC, frist ASC",
    "art": "art ASC, frist ASC",
    "zustaendig": "zustaendig COLLATE NOCASE ASC, frist ASC",
    "neu": "id DESC",
    "alt": "id ASC",
}


def kennzahlen(con) -> dict:
    tag = heute()
    grenze = (dt.date.today() + dt.timedelta(days=BALD_TAGE)).isoformat()
    platzhalter = ",".join("?" * len(ABGESCHLOSSEN))
    offen_nur = f"status NOT IN ({platzhalter})"

    def zahl(bedingung: str, werte: list) -> int:
        return con.execute(
            f"SELECT COUNT(*) c FROM vorgang WHERE {bedingung}", werte).fetchone()["c"]

    return {
        "offen": zahl(offen_nur, list(ABGESCHLOSSEN)),
        "heute": zahl(f"frist = ? AND {offen_nur}", [tag, *ABGESCHLOSSEN]),
        "bald": zahl(f"frist > ? AND frist <= ? AND {offen_nur}",
                     [tag, grenze, *ABGESCHLOSSEN]),
        "ueberfaellig": zahl(f"frist <> '' AND frist < ? AND {offen_nur}",
                             [tag, *ABGESCHLOSSEN]),
        "wartend": zahl("status IN (%s)" % ",".join("?" * len(WARTEND)),
                        list(WARTEND)),
        "erledigt": zahl(f"status IN ({platzhalter})", list(ABGESCHLOSSEN)),
        "gesamt": zahl("1=1", []),
    }


@router.get("", response_class=HTMLResponse)
def uebersicht(request: Request, klient: str = "", zustaendig: str = "",
               status: str = "", art: str = "", faellig: str = "",
               zustand: str = "alle", q: str = "", sortierung: str = "dringlichkeit",
               neu: str = "", fehler: str = "", hinweis: str = ""):
    if sortierung not in SORTIERUNGEN:
        sortierung = "dringlichkeit"
    filter_ = filter_bauen(klient, zustaendig, status, art, faellig, zustand, q)

    with db.db() as con:
        zeilen = con.execute(
            f"SELECT * FROM vorgang WHERE {filter_['wo']} "
            f"ORDER BY {SORTIERUNGEN[sortierung]} LIMIT 500",
            filter_["werte"]).fetchall()
        zahlen = kennzahlen(con)
        klienten = klientenliste(con)
        leute = teamliste(con)
        arten = vorgangsarten_liste(con)
        # fuer die Filterfelder: nur wirklich vorkommende Werte
        vorhandene_arten = [r["art"] for r in con.execute(
            "SELECT DISTINCT art FROM vorgang ORDER BY 1")]
        vorhandene_zustaendige = [r["zustaendig"] for r in con.execute(
            "SELECT DISTINCT zustaendig FROM vorgang ORDER BY 1 COLLATE NOCASE")]

    liste = [{"v": z, "lage": fristlage(z)} for z in zeilen]

    return seite(request, "vorgaenge.html",
                 liste=liste, zahlen=zahlen, klienten=klienten, leute=leute,
                 V_ARTEN=arten,
                 f=filter_["f"], aktive_filter=filter_["aktive"],
                 query=filter_["query"], sortierung=sortierung,
                 vorhandene_arten=vorhandene_arten,
                 vorhandene_zustaendige=vorhandene_zustaendige,
                 formular_offen=bool(neu or fehler), vorbelegt_klient=klient,
                 eigener_name=_umgebung.get("eigener_name", lambda r: "")(request),
                 heute_iso=heute(), fehler=fehler, hinweis=hinweis,
                 bald_tage=BALD_TAGE)


# --- Vorgang anlegen --------------------------------------------------------

@router.post("")
def anlegen(klient: str = Form(""), art: str = Form(""), titel: str = Form(""),
            beschreibung: str = Form(""), zustaendig: str = Form(""),
            beteiligte: str = Form(""), status: str = Form("Offen"),
            prioritaet: str = Form("Normal"), frist: str = Form(""),
            dateiverweis: str = Form(""), wer: str = Form(""),
            zurueck: str = Form("/vorgaenge")):
    klient = sauber(klient, 120)
    titel = sauber(titel, 160)
    zustaendig = sauber(zustaendig, 80)
    # Ohne handelnde Person waere nicht nachvollziehbar, wer den Vorgang
    # angelegt hat – darum Pflicht und ausdruecklich kein Rueckfall auf
    # die zustaendige Person.
    wer = sauber(wer, 80)
    art = sauber(art, 160)
    status = status if status in STATUS_LISTE else "Offen"
    prioritaet = prioritaet if prioritaet in PRIORITAETEN else "Normal"
    frist_iso = datum_lesen(frist)

    if not klient or not titel or not zustaendig or not wer or not art:
        return zurueck_zu("/vorgaenge", neu="1", fehler=(
            "Betreute Person, Vorgangsart, Titel, zuständige Person und "
            "handelnde Person müssen ausgefüllt sein."))

    with db.db() as con:
        if klient not in klientenliste(con):
            return zurueck_zu("/vorgaenge", neu="1", fehler=(
                f"„{klient}“ ist im System nicht bekannt. Betreute Personen "
                "kommen ausschließlich aus den hochgeladenen Arbeitslisten."))
        if art not in vorgangsarten_liste(con):
            return zurueck_zu("/vorgaenge", neu="1", fehler=(
                f"„{art}“ ist keine eingerichtete Vorgangsart. Vorgangsarten "
                "werden unter Einstellungen → Aufgabenarten gepflegt."))

        cur = con.execute(
            "INSERT INTO vorgang (klient, art, titel, beschreibung, zustaendig, "
            "beteiligte, status, prioritaet, frist, angelegt_am, angelegt_von, "
            "geaendert_am, dateiverweis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (klient, art, titel, mehrzeilig(beschreibung), zustaendig,
             sauber(beteiligte, 200), status, prioritaet, frist_iso, jetzt(),
             wer, jetzt(), sauber(dateiverweis, 300)))
        neue_id = cur.lastrowid

        text = f"Vorgang „{titel}“ angelegt (Art: {art}). Zuständig: {zustaendig}."
        if status != "Offen":
            text += f" Status: {status}."
        if frist_iso:
            text += f" Wiedervorlage/Frist: {deutsch(frist_iso)}."
        if beschreibung.strip():
            text += f" Notiz: {mehrzeilig(beschreibung, 600)}"
        protokoll(con, neue_id, klient, wer, "Vorgang angelegt", text)

    return RedirectResponse(f"/vorgaenge/{neue_id}?hinweis=Vorgang+angelegt.",
                            status_code=303)


# --- Logbuch ueber alle Personen -------------------------------------------

@router.get("/logbuch", response_class=HTMLResponse)
def logbuch(request: Request, klient: str = "", wer: str = "", q: str = ""):
    wo, werte = ["1=1"], []
    if klient:
        wo.append("l.klient = ?")
        werte.append(klient)
    if wer:
        wo.append("l.wer = ?")
        werte.append(wer)
    if q:
        wo.append("(l.beschreibung LIKE ? OR l.aktion LIKE ?)")
        werte += [f"%{q}%"] * 2
    bedingung = " AND ".join(wo)

    with db.db() as con:
        zeilen = con.execute(
            # COALESCE, weil bei geloeschten Vorgaengen kein JOIN-Partner
            # mehr existiert - dort steht der Titel in der Logzeile selbst.
            # "geloescht" macht die Vorlage daran fest, dass die vorgang_id
            # fehlt, der Titel aber da ist.
            f"SELECT l.*, COALESCE(v.titel, l.vorgang_titel) AS titel, "
            f"v.status, (l.vorgang_id IS NULL) AS geloescht "
            f"FROM vorgang_log l "
            f"LEFT JOIN vorgang v ON v.id = l.vorgang_id WHERE {bedingung} "
            f"ORDER BY l.zeitpunkt DESC, l.id DESC LIMIT 400", werte).fetchall()
        gesamt = con.execute(
            f"SELECT COUNT(*) c FROM vorgang_log l WHERE {bedingung}",
            werte).fetchone()["c"]
        klienten = [r["klient"] for r in con.execute(
            "SELECT DISTINCT klient FROM vorgang_log ORDER BY 1 COLLATE NOCASE")]
        leute = [r["wer"] for r in con.execute(
            "SELECT DISTINCT wer FROM vorgang_log ORDER BY 1 COLLATE NOCASE")]

    return seite(request, "vorgang_logbuch.html", zeilen=zeilen,
                 tage=nach_tagen(zeilen), gesamt=gesamt,
                 klienten=klienten, leute=leute,
                 f={"klient": klient, "wer": wer, "q": q})


# --- Betreutenansicht -------------------------------------------------------

@router.get("/person", response_class=HTMLResponse)
def personenansicht(request: Request, name: str = "", hinweis: str = ""):
    name = sauber(name, 120)
    if not name:
        return RedirectResponse("/vorgaenge", status_code=303)

    platzhalter = ",".join("?" * len(ABGESCHLOSSEN))
    with db.db() as con:
        bekannt = name in klientenliste(con)
        offene = con.execute(
            f"SELECT * FROM vorgang WHERE klient=? AND status NOT IN ({platzhalter}) "
            f"ORDER BY {SORTIERUNGEN['frist']}",
            [name, *ABGESCHLOSSEN]).fetchall()
        erledigte = con.execute(
            f"SELECT * FROM vorgang WHERE klient=? AND status IN ({platzhalter}) "
            "ORDER BY COALESCE(NULLIF(datum_erledigt,''), geaendert_am) DESC, id DESC",
            [name, *ABGESCHLOSSEN]).fetchall()
        eintraege = con.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(dauer_min),0) m, MIN(datum) von, "
            "MAX(datum) bis FROM eintrag WHERE klient=?", (name,)).fetchone()
        stamm = con.execute("SELECT * FROM person WHERE name=?", (name,)).fetchone()
        verlauf = con.execute(
            # wie im globalen Logbuch: bei geloeschten Vorgaengen steht
            # der Titel in der Logzeile selbst
            "SELECT l.*, COALESCE(v.titel, l.vorgang_titel) AS titel "
            "FROM vorgang_log l "
            "LEFT JOIN vorgang v ON v.id = l.vorgang_id "
            "WHERE l.klient=? ORDER BY l.zeitpunkt DESC, l.id DESC",
            (name,)).fetchall()
        leute = teamliste(con)

    return seite(request, "vorgang_person.html", name=name, bekannt=bekannt,
                 offene=[{"v": z, "lage": fristlage(z)} for z in offene],
                 erledigte=erledigte, verlauf=verlauf,
                 verlauf_tage=nach_tagen(verlauf), eintraege=eintraege,
                 stamm=stamm, leute=leute, hinweis=hinweis, heute_iso=heute())


# --- Einzelner Vorgang ------------------------------------------------------

@router.get("/{vorgang_id}", response_class=HTMLResponse)
def ansicht(request: Request, vorgang_id: int, hinweis: str = "",
            fehler: str = ""):
    with db.db() as con:
        v = lade(con, vorgang_id)
        verlauf = con.execute(
            "SELECT * FROM vorgang_log WHERE vorgang_id=? "
            "ORDER BY zeitpunkt DESC, id DESC", (vorgang_id,)).fetchall()
        leute = teamliste(con)
        arten = vorgangsarten_liste(con)
        andere = con.execute(
            "SELECT COUNT(*) c FROM vorgang WHERE klient=? AND id<>? "
            "AND status NOT IN (%s)" % ",".join("?" * len(ABGESCHLOSSEN)),
            [v["klient"], vorgang_id, *ABGESCHLOSSEN]).fetchone()["c"]

    return seite(request, "vorgang.html", v=v, verlauf=verlauf,
                 verlauf_tage=nach_tagen(verlauf), leute=leute,
                 V_ARTEN=arten,
                 lage=fristlage(v), andere=andere, hinweis=hinweis,
                 fehler=fehler, heute_iso=heute())


def _fehler(vorgang_id: int, text: str) -> RedirectResponse:
    return zurueck_zu(f"/vorgaenge/{vorgang_id}", fehler=text)


@router.post("/{vorgang_id}/loeschen")
def loeschen(request: Request, vorgang_id: int,
             zurueck: str = Form("/vorgaenge")):
    """Entfernt einen Vorgang endgueltig - das Logbuch bleibt aber stehen.

    Anders als bei betreuten Personen oder Mitarbeitenden gibt es hier
    keine Stilllegung: die Statuswerte "Erledigt"/"Abgebrochen" decken den
    Abschluss eines Vorgangs bereits ab, das Loeschen ist eine zusaetzliche,
    endgueltige Aktion fuer Vorgaenge, die schlicht falsch angelegt wurden
    oder nicht mehr relevant sind.

    Der Verlauf verschwindet dabei ausdruecklich NICHT. Sonst waere ein
    geloeschter Vorgang spurlos weg, und genau das soll nachvollziehbar
    bleiben. Der Trick: erst wird die Loeschzeile geschrieben, dann werden
    alle Logzeilen dieses Vorgangs von ihm geloest (vorgang_id auf NULL,
    Titel mitgenommen) - damit greift der Fremdschluessel mit ON DELETE
    CASCADE beim anschliessenden Loeschen nicht mehr auf sie zu.

    Wer geloescht hat, kommt aus der Anmeldung und nicht aus einem
    Formularfeld. Bei den uebrigen Aktionen waehlt man die handelnde Person
    aus dem Team aus; hier waere das die falsche Quelle - eine Angabe, die
    man selbst eintippt, taugt nicht als Nachweis gegenueber jemandem, der
    hinterher bestreitet, geloescht zu haben.
    """
    try:
        wer = request.state.benutzer["benutzername"]
    except (AttributeError, IndexError, KeyError, TypeError):
        wer = "unbekannt"

    with db.db() as con:
        v = lade(con, vorgang_id)
        angaben = [f"Art: {v['art']}", f"Status: {v['status']}"]
        if v["zustaendig"]:
            angaben.append(f"zuständig: {v['zustaendig']}")
        if v["frist"]:
            angaben.append(f"Frist: {deutsch(v['frist'])}")
        angaben.append(f"angelegt am {deutsch(v['angelegt_am'][:10])} "
                       f"von {v['angelegt_von']}")
        protokoll(con, vorgang_id, v["klient"], wer, "Vorgang gelöscht",
                  f"„{v['titel']}“ – " + ", ".join(angaben))
        con.execute(
            "UPDATE vorgang_log SET vorgang_id=NULL, vorgang_titel=? "
            "WHERE vorgang_id=?", (v["titel"], vorgang_id))
        con.execute("DELETE FROM vorgang WHERE id=?", (vorgang_id,))
    return zurueck_zu(zurueck, hinweis=f"Vorgang „{v['titel']}“ gelöscht. "
                                       "Der Verlauf bleibt im Logbuch stehen.")


@router.post("/{vorgang_id}/status")
def status_aendern(vorgang_id: int, status: str = Form(""), wer: str = Form(""),
                   notiz: str = Form(""), frist: str = Form(""),
                   zurueck: str = Form("")):
    wer = sauber(wer, 80)
    if not wer:
        return _fehler(vorgang_id, "Bitte angeben, wer die Änderung vornimmt.")
    if status not in STATUS_LISTE:
        return _fehler(vorgang_id, "Unbekannter Status.")

    with db.db() as con:
        v = lade(con, vorgang_id)
        alt = v["status"]
        teile = []
        neue_werte: dict = {"status": status, "geaendert_am": jetzt()}

        if alt != status:
            teile.append(f"Status von „{alt}“ auf „{status}“ geändert.")
            # passende Datumsfelder mitziehen, sofern noch leer
            if status == "Eingereicht" and not v["datum_eingereicht"]:
                neue_werte["datum_eingereicht"] = heute()
            if status == "Erledigt" and not v["datum_erledigt"]:
                neue_werte["datum_erledigt"] = heute()
        else:
            teile.append(f"Status bleibt „{status}“.")

        neue_frist = datum_lesen(frist)
        if frist.strip() and neue_frist and neue_frist != (v["frist"] or ""):
            neue_werte["frist"] = neue_frist
            teile.append(f"Wiedervorlage auf den {deutsch(neue_frist)} gesetzt.")
        elif frist.strip() and not neue_frist:
            return _fehler(vorgang_id, "Das Datum der Wiedervorlage ist unklar.")

        if status in ABGESCHLOSSEN and not neue_werte.get("frist"):
            # abgeschlossene Vorgaenge brauchen keine Wiedervorlage mehr
            neue_werte["frist"] = ""
            if v["frist"]:
                teile.append("Wiedervorlage entfernt.")

        satz = ", ".join(f"{k}=?" for k in neue_werte)
        con.execute(f"UPDATE vorgang SET {satz} WHERE id=?",
                    [*neue_werte.values(), vorgang_id])

        text = " ".join(teile)
        if notiz.strip():
            text += " Notiz: " + mehrzeilig(notiz, 1000)
        aktion = ("Vorgang erledigt" if status == "Erledigt" else
                  "Vorgang abgebrochen" if status == "Abgebrochen" else
                  "Status geändert")
        protokoll(con, vorgang_id, v["klient"], wer, aktion, text)

    return zurueck_zu(zurueck or f"/vorgaenge/{vorgang_id}",
                      hinweis="Status aktualisiert.")


@router.post("/{vorgang_id}/zustaendig")
def zustaendig_aendern(vorgang_id: int, zustaendig: str = Form(""),
                       wer: str = Form(""), notiz: str = Form("")):
    wer, neu = sauber(wer, 80), sauber(zustaendig, 80)
    if not wer or not neu:
        return _fehler(vorgang_id, "Neue Zuständigkeit und handelnde Person "
                                   "müssen angegeben sein.")
    with db.db() as con:
        v = lade(con, vorgang_id)
        alt = v["zustaendig"]
        con.execute("UPDATE vorgang SET zustaendig=?, geaendert_am=? WHERE id=?",
                    (neu, jetzt(), vorgang_id))
        text = f"Zuständigkeit von {alt} auf {neu} übergeben."
        if notiz.strip():
            text += " Notiz: " + mehrzeilig(notiz, 1000)
        protokoll(con, vorgang_id, v["klient"], wer, "Zuständigkeit geändert", text)
    return zurueck_zu(f"/vorgaenge/{vorgang_id}", hinweis="Zuständigkeit geändert.")


@router.post("/{vorgang_id}/frist")
def frist_aendern(vorgang_id: int, frist: str = Form(""), wer: str = Form(""),
                  notiz: str = Form("")):
    wer = sauber(wer, 80)
    if not wer:
        return _fehler(vorgang_id, "Bitte angeben, wer die Änderung vornimmt.")
    neue = datum_lesen(frist)
    if frist.strip() and not neue:
        return _fehler(vorgang_id, "Das Datum der Wiedervorlage ist unklar.")

    with db.db() as con:
        v = lade(con, vorgang_id)
        alt = v["frist"] or ""
        con.execute("UPDATE vorgang SET frist=?, geaendert_am=? WHERE id=?",
                    (neue, jetzt(), vorgang_id))
        if neue and alt:
            text = f"Wiedervorlage vom {deutsch(alt)} auf den {deutsch(neue)} verlegt."
        elif neue:
            text = f"Wiedervorlage auf den {deutsch(neue)} gesetzt."
        else:
            text = f"Wiedervorlage vom {deutsch(alt)} entfernt." if alt else \
                   "Wiedervorlage entfernt."
        if notiz.strip():
            text += " Notiz: " + mehrzeilig(notiz, 1000)
        protokoll(con, vorgang_id, v["klient"], wer, "Frist geändert", text)
    return zurueck_zu(f"/vorgaenge/{vorgang_id}", hinweis="Wiedervorlage geändert.")


@router.post("/{vorgang_id}/notiz")
def notiz_anlegen(vorgang_id: int, wer: str = Form(""), notiz: str = Form("")):
    wer, text = sauber(wer, 80), mehrzeilig(notiz, 2000)
    if not wer or not text:
        return _fehler(vorgang_id, "Notiz und handelnde Person müssen "
                                   "ausgefüllt sein.")
    with db.db() as con:
        v = lade(con, vorgang_id)
        con.execute("UPDATE vorgang SET geaendert_am=? WHERE id=?",
                    (jetzt(), vorgang_id))
        protokoll(con, vorgang_id, v["klient"], wer, "Notiz", text)
    return zurueck_zu(f"/vorgaenge/{vorgang_id}", hinweis="Notiz im Verlauf ergänzt.")


FELDER_BESCHRIFTUNG = {
    "titel": "Titel",
    "art": "Vorgangsart",
    "beschreibung": "Beschreibung",
    "prioritaet": "Priorität",
    "beteiligte": "weitere Beteiligte",
    "dateiverweis": "Dokumentenverweis",
    "datum_eingereicht": "Datum der Einreichung",
    "datum_eingang": "Datum des Eingangs",
    "datum_rueckmeldung": "Datum der Rückmeldung",
    "datum_erledigt": "Datum der Erledigung",
}


@router.post("/{vorgang_id}/daten")
def daten_speichern(vorgang_id: int, wer: str = Form(""), titel: str = Form(""),
                    art: str = Form(""), beschreibung: str = Form(""),
                    prioritaet: str = Form("Normal"), beteiligte: str = Form(""),
                    dateiverweis: str = Form(""),
                    datum_eingereicht: str = Form(""),
                    datum_eingang: str = Form(""),
                    datum_rueckmeldung: str = Form(""),
                    datum_erledigt: str = Form("")):
    wer = sauber(wer, 80)
    if not wer:
        return _fehler(vorgang_id, "Bitte angeben, wer die Änderung vornimmt.")
    titel = sauber(titel, 160)
    if not titel:
        return _fehler(vorgang_id, "Ohne Titel geht es nicht.")
    art = sauber(art, 160)
    if not art:
        return _fehler(vorgang_id, "Bitte eine Vorgangsart angeben.")

    neu = {
        "titel": titel,
        "art": art,
        "beschreibung": mehrzeilig(beschreibung),
        "prioritaet": prioritaet if prioritaet in PRIORITAETEN else "Normal",
        "beteiligte": sauber(beteiligte, 200),
        "dateiverweis": sauber(dateiverweis, 300),
        "datum_eingereicht": datum_lesen(datum_eingereicht),
        "datum_eingang": datum_lesen(datum_eingang),
        "datum_rueckmeldung": datum_lesen(datum_rueckmeldung),
        "datum_erledigt": datum_lesen(datum_erledigt),
    }

    with db.db() as con:
        if art not in vorgangsarten_liste(con):
            return _fehler(vorgang_id, (
                f"„{art}“ ist keine eingerichtete Vorgangsart. Vorgangsarten "
                "werden unter Einstellungen → Aufgabenarten gepflegt."))
        v = lade(con, vorgang_id)
        aenderungen = []
        for feld, wert in neu.items():
            alt = v[feld] or ""
            if wert != alt:
                name = FELDER_BESCHRIFTUNG[feld]
                if feld.startswith("datum_"):
                    aenderungen.append(
                        f"{name}: {deutsch(alt) or '—'} → {deutsch(wert) or '—'}")
                elif feld == "beschreibung":
                    aenderungen.append(f"{name} geändert. Neuer Text: {wert or '—'}")
                else:
                    aenderungen.append(f"{name}: {alt or '—'} → {wert or '—'}")

        if not aenderungen:
            return zurueck_zu(f"/vorgaenge/{vorgang_id}",
                              hinweis="Keine Änderung festgestellt.")

        satz = ", ".join(f"{k}=?" for k in neu)
        con.execute(f"UPDATE vorgang SET {satz}, geaendert_am=? WHERE id=?",
                    [*neu.values(), jetzt(), vorgang_id])
        protokoll(con, vorgang_id, v["klient"], wer, "Vorgang bearbeitet",
                  " ".join(aenderungen))

    return zurueck_zu(f"/vorgaenge/{vorgang_id}", hinweis="Änderungen gespeichert.")
