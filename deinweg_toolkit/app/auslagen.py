"""Privatauslagen - was man fuer die Einrichtung aus eigener Tasche vorlegt.

Eigener Router nach demselben Muster wie vorgaenge.py und wiki.py:
main.py reicht ueber setup() nur, was hier gebraucht wird (Templates, den
Ablageort der Belege und die Obergrenze fuer Uploads). So gibt es keinen
Ringschluss beim Import.

Das Problem, das dieses Modul loest (Timos Worten nach): wer tankt, fuer
eine betreute Person einkauft oder ein Essen auslegt, sammelt die Bons
zuhause im Briefumschlag, zaehlt irgendwann fuenfzig Zettel zusammen,
schreibt die Summe darauf und laeuft danach dem Geld hinterher. Die
Rechnerei nimmt ihm das hier ab - vor allem aber merkt sich das Werkzeug,
was noch offen ist.

⚠️ Das Modul haengt bewusst an NICHTS sonst im Toolkit (Timos Vorgabe).
Keine betreute Person, kein Fahrzeug, keine Leistung - nur Betrag, Datum,
eine Notiz und wahlweise ein Foto vom Bon. Wer hier etwas anbindet, macht
aus einem Modul, das man in zehn Sekunden bedient, eine Erfassungsmaske.

⚠️⚠️ Es sind PERSOENLICHE Zahlen. Jedes Konto sieht ausschliesslich seine
eigenen Auslagen - auch Administratoren. Das ist der eine Punkt, an dem
dieses Modul von den uebrigen abweicht, und er ist Absicht: wer wie viel
privat vorstreckt, geht niemanden sonst etwas an. Deshalb prueft JEDE
Route die Eigentuemerschaft selbst; die Middleware kann das nicht, sie
kennt nur den Pfad.

Der Ablauf in drei Zustaenden:

    offen  ->  abgegeben  ->  erstattet

"offen" ist die Mappe, in der gesammelt wird - je Konto gibt es davon
hoechstens EINEN, und fehlt er, legt das Erfassen ihn selbst an. Es
braucht also keinen Knopf "neuen Block starten". "abgegeben" ist genau
der Zustand, in dem man heute hinter dem Geld herlaeuft: Bons sind weg,
Geld noch nicht da. "erstattet" ist Archiv.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import db
from .parser import parse_datum

router = APIRouter()

# von setup() gefuellt
_u: dict = {}

ZUSTAENDE = ("offen", "abgegeben", "erstattet")

# Wie lange ein abgegebener Block still warten darf, bevor die Karte
# faerbt. Dieselben Toene wie die Ampel der Aufgaben, und aus demselben
# Grund: zwei Stellen, die "das dauert zu lange" meinen, muessen auch
# gleich aussehen.
MAHNT_AB = 14
DRAENGT_AB = 30

# Belegarten. Wie in dateien.py eine Erlaubnisliste und keine Sperrliste -
# man vergisst immer eine Endung. Der Inhaltstyp kommt aus DIESER Liste,
# nie aus dem Upload.
#
# ⚠️ HEIC steht mit drin, weil iPhones so fotografieren. Anzeigen kann es
# kaum ein Browser, deshalb geht es als Download hinaus statt inline -
# ein leeres Bildfeld waere schlimmer als ein Verweis, der funktioniert.
BELEGARTEN: dict[str, tuple[str, bool]] = {
    "jpg":  ("image/jpeg", True),
    "jpeg": ("image/jpeg", True),
    "png":  ("image/png", True),
    "webp": ("image/webp", True),
    "gif":  ("image/gif", True),
    "pdf":  ("application/pdf", True),
    "heic": ("image/heic", False),
    "heif": ("image/heif", False),
}


def setup(templates, werte: dict) -> None:
    _u["templates"] = templates
    _u.update(werte or {})


# --- Betraege ----------------------------------------------------------------

def betrag_lesen(text: str) -> int | None:
    """Macht aus einer Eingabe einen Betrag in ganzen Cent.

    Versteht "12,40", "12.40", "12", "1.234,56", "1234.56" und ein
    vorangestelltes oder angehaengtes Eurozeichen. Gibt None zurueck,
    wenn daraus keine Zahl wird oder sie nicht positiv ist.

    ⚠️ Gerechnet wird ueber die Ziffern, nicht ueber float(): 0.1 + 0.2
    ist in Fliesskomma nicht 0.3, und hier werden bis zu fuenfzig Zeilen
    addiert und am Ende jemandem als Betrag genannt.
    """
    roh = (text or "").strip().replace("€", "").replace(" ", "")
    if not roh:
        return None
    roh = roh.replace(" ", "")
    # ⚠️ Der Punkt ist zweideutig: in "1.234,56" trennt er Tausender, in
    # "12.40" ist er das Komma einer englischen Tastatur. Steht ein Komma
    # dabei, ist die Sache klar - dann ist der Punkt ein Tausendertrenner.
    # Steht keines, gilt der Punkt als Komma.
    #
    # Bleibt "1.234" ohne Komma: das kann 1.234 EUR heissen oder 1,23 EUR,
    # und beides waere geraten. Die Pruefung unten laesst es deshalb
    # durchfallen und die Meldung bittet um eine eindeutige Eingabe.
    # Lieber einmal nachfragen als tausend Euro daneben liegen.
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", roh):
        return None
    ganz, _, rest = roh.partition(".")
    cent = int(ganz) * 100 + int((rest + "00")[:2])
    return cent if cent > 0 else None


def euro(cent) -> str:
    """Cent als "1.234,50 €"."""
    try:
        cent = int(cent)
    except (TypeError, ValueError):
        cent = 0
    text = f"{abs(cent) // 100:,}".replace(",", ".")
    return f"{'-' if cent < 0 else ''}{text},{abs(cent) % 100:02d} €"


# --- Zugriff -----------------------------------------------------------------

def _konto(request: Request):
    """Die Zeile des angemeldeten Kontos, oder None."""
    return getattr(request.state, "benutzer", None)


def _abgewiesen() -> HTMLResponse:
    return HTMLResponse("<h1>403</h1><p>Das ist nicht deine Auslage.</p>",
                        status_code=403)


def _zurueck(hinweis: str = "", fehler: str = "", datum: str = "") -> RedirectResponse:
    """Zurueck auf die Seite, mit Meldung.

    ⚠️ Das Datum faehrt mit: wer fuenf Bons vom Samstag nachtraegt, soll
    es nicht fuenfmal tippen. Dieselbe Ueberlegung wie in der manuellen
    Zeiterfassung (erfassung_speichern.zurueck).
    """
    teile = {}
    if hinweis:
        teile["hinweis"] = hinweis
    if fehler:
        teile["fehler"] = fehler
    if datum:
        teile["datum"] = datum
    adresse = "/privatauslagen"
    if teile:
        adresse += "?" + urlencode(teile)
    return RedirectResponse(adresse, status_code=303)


def _heute() -> str:
    return dt.date.today().isoformat()


def _jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# --- Bloecke -----------------------------------------------------------------

def offener_block(con, benutzer_id: int, anlegen: bool = False):
    """Der eine offene Block dieses Kontos.

    Mit anlegen=True wird er erzeugt, falls keiner da ist - genau das
    macht den Knopf "neuen Block starten" ueberfluessig.
    """
    zeile = con.execute(
        "SELECT * FROM auslage_block WHERE benutzer_id=? AND zustand='offen' "
        "ORDER BY id DESC LIMIT 1", (benutzer_id,)).fetchone()
    if zeile or not anlegen:
        return zeile
    con.execute(
        "INSERT INTO auslage_block (benutzer_id, zustand, begonnen_am) "
        "VALUES (?, 'offen', ?)", (benutzer_id, _heute()))
    return con.execute(
        "SELECT * FROM auslage_block WHERE benutzer_id=? AND zustand='offen' "
        "ORDER BY id DESC LIMIT 1", (benutzer_id,)).fetchone()


def block_holen(con, block_id: int, benutzer_id: int):
    """Ein Block - aber nur, wenn er diesem Konto gehoert.

    ⚠️ Die Eigentuemerpruefung steht in der WHERE-Klausel, nicht als
    if-Abfrage dahinter. So kann sie beim Ergaenzen einer neuen Route
    nicht vergessen werden, solange diese Funktion benutzt wird.
    """
    return con.execute(
        "SELECT * FROM auslage_block WHERE id=? AND benutzer_id=?",
        (block_id, benutzer_id)).fetchone()


def auslage_holen(con, auslage_id: int, benutzer_id: int):
    """Eine einzelne Auslage samt ihrem Block - nur fuer den Eigentuemer."""
    return con.execute(
        "SELECT a.*, b.zustand, b.benutzer_id FROM auslage a "
        "JOIN auslage_block b ON b.id = a.block_id "
        "WHERE a.id=? AND b.benutzer_id=?",
        (auslage_id, benutzer_id)).fetchone()


def zeilen(con, block_id: int) -> list:
    """Die Auslagen eines Blocks, juengste zuerst.

    ⚠️ Absteigend, wie im Tagesprotokoll der Zeiterfassung: was man
    gerade eingetippt hat, soll direkt unter dem Formular stehen. Das
    ist die Rueckmeldung, dass es angekommen ist.
    """
    return con.execute(
        "SELECT * FROM auslage WHERE block_id=? "
        "ORDER BY datum DESC, id DESC", (block_id,)).fetchall()


def summe(con, block_id: int) -> int:
    zeile = con.execute(
        "SELECT COALESCE(SUM(cent), 0) s FROM auslage WHERE block_id=?",
        (block_id,)).fetchone()
    return int(zeile["s"])


def _tage_her(datum: str) -> int:
    d = parse_datum(datum)
    return (dt.date.today() - d).days if d else 0


def _lage(tage: int) -> str:
    """Wie dringend ein abgegebener Block ist - dieselben drei Stufen wie
    die Ampel der Aufgabenkarten."""
    if tage >= DRAENGT_AB:
        return "draengt"
    if tage >= MAHNT_AB:
        return "mahnt"
    return "frisch"


# --- Belege ------------------------------------------------------------------

def _belegordner(benutzer_id: int) -> str:
    return os.path.join(_u["AUSLAGEN_PFAD"], str(int(benutzer_id)))


def belegpfad(benutzer_id: int, auslage_id: int, endung: str) -> str | None:
    """Der Ablageort eines Belegs.

    ⚠️⚠️ Gebaut wird er aus zwei ZAHLEN und einer Endung aus der festen
    Liste - nie aus einem Text der Datenbank und schon gar nicht aus der
    Adresse. Damit kann hier strukturell kein Pfad herauskommen, der aus
    dem Ordner zeigt; es braucht keine realpath-Gegenprobe wie im Wiki,
    weil es gar nichts zu pruefen gibt.
    """
    endung = (endung or "").lower().lstrip(".")
    if endung not in BELEGARTEN:
        return None
    return os.path.join(_belegordner(benutzer_id),
                        f"{int(auslage_id)}.{endung}")


def beleg_speichern(benutzer_id: int, auslage_id: int, dateiname: str,
                    inhalt: bytes) -> str | None:
    """Legt ein Belegfoto ab und gibt seine Endung zurueck (die kommt in
    die Datenbank). None, wenn die Art nicht erlaubt ist."""
    endung = (dateiname or "").rpartition(".")[2].lower()
    ziel = belegpfad(benutzer_id, auslage_id, endung)
    if ziel is None:
        return None
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    with open(ziel, "wb") as f:
        f.write(inhalt)
    return endung


def beleg_entfernen(benutzer_id: int, auslage_id: int, endung: str) -> None:
    ziel = belegpfad(benutzer_id, auslage_id, endung)
    if ziel:
        try:
            os.remove(ziel)
        except OSError:
            pass


# --- Seite -------------------------------------------------------------------

def _bild(con, request: Request, hinweis: str = "", fehler: str = "",
          datum: str = "") -> dict:
    """Alles, was die Vorlage braucht. Eine Stelle, damit Anzeige und
    Umleitung nach einem Speichern nicht auseinanderlaufen."""
    konto = _konto(request)
    bid = konto["id"]

    block = offener_block(con, bid)
    laufend = zeilen(con, block["id"]) if block else []
    offen_summe = summe(con, block["id"]) if block else 0

    wartend = []
    for b in con.execute(
            "SELECT * FROM auslage_block WHERE benutzer_id=? AND "
            "zustand='abgegeben' ORDER BY abgegeben_am, id", (bid,)).fetchall():
        tage = _tage_her(b["abgegeben_am"])
        st = zeilen(con, b["id"])
        wartend.append({"b": b, "summe": summe(con, b["id"]),
                        "anzahl": len(st), "tage": tage,
                        "lage": _lage(tage), "zeilen": st})

    erledigt = []
    for b in con.execute(
            "SELECT * FROM auslage_block WHERE benutzer_id=? AND "
            "zustand='erstattet' ORDER BY erstattet_am DESC, id DESC "
            "LIMIT 24", (bid,)).fetchall():
        st = zeilen(con, b["id"])
        erledigt.append({"b": b, "summe": summe(con, b["id"]),
                         "anzahl": len(st), "zeilen": st,
                         "belege": sum(1 for z in st if z["beleg"])})

    # Kleine Jahresbilanz. Kostet eine Abfrage und beantwortet die Frage,
    # die nach der offenen Summe als naechste kommt.
    jahr = dt.date.today().year
    bilanz = con.execute(
        "SELECT COALESCE(SUM(a.cent), 0) s, COUNT(a.id) n FROM auslage a "
        "JOIN auslage_block b ON b.id = a.block_id "
        "WHERE b.benutzer_id=? AND a.datum LIKE ?",
        (bid, f"{jahr}-%")).fetchone()

    return {
        "request": request, "seite": "privatauslagen",
        "hinweis": hinweis, "fehler": fehler,
        "block": block, "laufend": laufend, "offen_summe": offen_summe,
        "wartend": wartend,
        "wartend_summe": sum(w["summe"] for w in wartend),
        "erledigt": erledigt,
        "jahr": jahr, "jahr_summe": int(bilanz["s"]), "jahr_anzahl": bilanz["n"],
        "datum": datum or _heute(),
        "heute": _heute(),
        "betrag": euro,
        "max_mb": _u.get("MAX_UPLOAD_MB", 20),
        "belegarten": sorted(BELEGARTEN),
    }


@router.get("/privatauslagen", response_class=HTMLResponse)
def seite(request: Request, hinweis: str = "", fehler: str = "",
          datum: str = ""):
    with db.db() as con:
        daten = _bild(con, request, hinweis, fehler, datum)
    return _u["templates"].TemplateResponse(
        request=request, name="auslagen.html", context=daten)


# --- Erfassen ----------------------------------------------------------------

@router.post("/privatauslagen/erfassen")
async def erfassen(request: Request, betrag: str = Form(""),
                   datum: str = Form(""), notiz: str = Form(""),
                   beleg: UploadFile | None = File(None)):
    konto = _konto(request)
    cent = betrag_lesen(betrag)
    if cent is None:
        return _zurueck(fehler="Der Betrag ist nicht lesbar. Zum Beispiel "
                               "12,40 oder 12.", datum=datum)

    tag = parse_datum(datum) or dt.date.today()
    if tag > dt.date.today():
        return _zurueck(fehler="Das Datum liegt in der Zukunft.", datum=datum)

    inhalt = b""
    dateiname = ""
    if beleg is not None and beleg.filename:
        dateiname = beleg.filename
        inhalt = await beleg.read()
        grenze = int(_u.get("MAX_UPLOAD_MB", 20)) * 1024 * 1024
        if len(inhalt) > grenze:
            return _zurueck(fehler=f"Der Beleg ist größer als "
                                   f"{_u.get('MAX_UPLOAD_MB', 20)} MB.",
                            datum=datum)
        if dateiname.rpartition(".")[2].lower() not in BELEGARTEN:
            return _zurueck(fehler="Diese Dateiart geht als Beleg nicht. "
                                   "Erlaubt sind Fotos und PDF.", datum=datum)

    with db.db() as con:
        block = offener_block(con, konto["id"], anlegen=True)
        c = con.execute(
            "INSERT INTO auslage (block_id, datum, cent, notiz, angelegt_am) "
            "VALUES (?,?,?,?,?)",
            (block["id"], tag.isoformat(), cent,
             (notiz or "").strip() or None, _jetzt()))
        neu = c.lastrowid
        if inhalt:
            endung = beleg_speichern(konto["id"], neu, dateiname, inhalt)
            if endung:
                con.execute("UPDATE auslage SET beleg=? WHERE id=?",
                            (endung, neu))

    text = f"{euro(cent)} festgehalten."
    if inhalt:
        text += " Beleg liegt dabei."
    return _zurueck(hinweis=text, datum=tag.isoformat())


@router.post("/privatauslagen/{auslage_id}/aendern")
def aendern(request: Request, auslage_id: int, betrag: str = Form(""),
            datum: str = Form(""), notiz: str = Form("")):
    konto = _konto(request)
    with db.db() as con:
        zeile = auslage_holen(con, auslage_id, konto["id"])
        if zeile is None:
            return _abgewiesen()
        # ⚠️ Nur im offenen Block. Sobald die Bons abgegeben sind, liegt
        # die Wahrheit bei der Chefin auf dem Tisch - eine Liste, die sich
        # danach noch aendert, waere kein Nachweis mehr. Wer wirklich
        # korrigieren muss, holt den Block ueber "zurück zu offen" heran.
        if zeile["zustand"] != "offen":
            return _zurueck(fehler="Dieser Block ist schon abgegeben. "
                                   "Hol ihn erst zurück auf „offen“.")
        cent = betrag_lesen(betrag)
        if cent is None:
            return _zurueck(fehler="Der Betrag ist nicht lesbar.")
        tag = parse_datum(datum) or parse_datum(zeile["datum"])
        con.execute(
            "UPDATE auslage SET cent=?, datum=?, notiz=? WHERE id=?",
            (cent, tag.isoformat(), (notiz or "").strip() or None, auslage_id))
    return _zurueck(hinweis="Auslage geändert.")


@router.post("/privatauslagen/{auslage_id}/loeschen")
def loeschen(request: Request, auslage_id: int):
    konto = _konto(request)
    with db.db() as con:
        zeile = auslage_holen(con, auslage_id, konto["id"])
        if zeile is None:
            return _abgewiesen()
        if zeile["zustand"] != "offen":
            return _zurueck(fehler="Dieser Block ist schon abgegeben.")
        if zeile["beleg"]:
            beleg_entfernen(konto["id"], auslage_id, zeile["beleg"])
        con.execute("DELETE FROM auslage WHERE id=?", (auslage_id,))
    return _zurueck(hinweis="Auslage entfernt.")


# --- Belege ausliefern -------------------------------------------------------
#
# ⚠️ Diese Route muss im Quelltext VOR "/privatauslagen/{auslage_id}/..."
# stehen - dieselbe Falle wie bei den Wiki- und Dateiaktionen. Hier
# faellt sie heute nicht zu (die Pfade sind verschieden lang), aber die
# naechste Route mit einem Platzhalter an erster Stelle waere genau der
# Fall. Reihenfolge einhalten.

@router.get("/privatauslagen/beleg/{auslage_id}")
def beleg_holen(request: Request, auslage_id: int):
    konto = _konto(request)
    with db.db() as con:
        zeile = auslage_holen(con, auslage_id, konto["id"])
    if zeile is None or not zeile["beleg"]:
        return _abgewiesen()
    pfad = belegpfad(konto["id"], auslage_id, zeile["beleg"])
    if not pfad or not os.path.isfile(pfad):
        return HTMLResponse("<h1>404</h1><p>Den Beleg gibt es nicht mehr.</p>",
                            status_code=404)
    typ, inline = BELEGARTEN[zeile["beleg"]]
    kopf = {
        # ⚠️ Der Inhaltstyp kommt aus BELEGARTEN, nie aus dem Upload -
        # dieselbe Regel wie in dateien.holen(). nosniff dazu, damit der
        # Browser nicht selbst etwas anderes daraus macht.
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition":
            ("inline" if inline else "attachment")
            + f'; filename="beleg-{auslage_id}.{zeile["beleg"]}"',
        # Ein Bon ist eine persoenliche Unterlage. Er gehoert in keinen
        # Zwischenspeicher, aus dem ihn spaeter jemand anders herausholt.
        "Cache-Control": "private, no-store",
    }
    return FileResponse(pfad, media_type=typ, headers=kopf)


# --- Zustand eines Blocks ----------------------------------------------------

@router.post("/privatauslagen/block/{block_id}/zustand")
def zustand_setzen(request: Request, block_id: int, ziel: str = Form("")):
    konto = _konto(request)
    if ziel not in ZUSTAENDE:
        return _zurueck(fehler="Diesen Zustand gibt es nicht.")
    with db.db() as con:
        block = block_holen(con, block_id, konto["id"])
        if block is None:
            return _abgewiesen()
        if block["zustand"] == ziel:
            return _zurueck()
        betrag = summe(con, block_id)
        if ziel == "abgegeben" and not betrag:
            return _zurueck(fehler="In diesem Block steht noch nichts.")
        # ⚠️ Es darf nur EINEN offenen Block je Konto geben. Wer einen
        # abgegebenen zurueckholt, waehrend schon ein neuer laeuft,
        # haette sonst zwei - und neue Auslagen landeten je nach
        # Sortierung mal hier, mal dort.
        if ziel == "offen":
            anderer = offener_block(con, konto["id"])
            if anderer and anderer["id"] != block_id:
                return _zurueck(
                    fehler="Es läuft schon ein offener Block. Gib den erst "
                           "ab oder räum ihn leer, dann geht das hier wieder.")

        con.execute(
            "UPDATE auslage_block SET zustand=?, "
            "abgegeben_am = CASE WHEN ?='abgegeben' THEN ? "
            "                    WHEN ?='offen' THEN NULL "
            "                    ELSE abgegeben_am END, "
            "erstattet_am = CASE WHEN ?='erstattet' THEN ? ELSE NULL END "
            "WHERE id=?",
            (ziel, ziel, _heute(), ziel, ziel, _heute(), block_id))

        # ⚠️ Hier waere die Stelle fuer Timos naechsten Schritt: beim
        # Wechsel auf "abgegeben" eine Aufgabe in der Aufgabenverwaltung
        # anlegen ("Erstattung 247,80 EUR", zustaendig die Chefin). Sie
        # ist ausdruecklich NOCH NICHT gebaut - erst besprechen, an wen
        # sie geht und was in der Frist steht.

    meldungen = {
        "abgegeben": f"{euro(betrag)} als abgegeben vermerkt. "
                     f"Der Block wartet jetzt auf die Erstattung.",
        "erstattet": f"{euro(betrag)} erstattet. Erledigt.",
        "offen": "Der Block ist wieder offen.",
    }
    return _zurueck(hinweis=meldungen[ziel])


@router.post("/privatauslagen/block/{block_id}/belege-loeschen")
def belege_loeschen(request: Request, block_id: int):
    """Raeumt die Fotos eines erstatteten Blocks weg.

    Die Zahlen bleiben stehen - nur die Bilddateien gehen. Ein
    Handyfoto misst gut drei Megabyte; fuenfzig davon je Block summieren
    sich auf einer Speicherkarte schneller, als man denkt. Sobald das
    Geld da ist, hat der Beleg seinen Zweck erfuellt.
    """
    konto = _konto(request)
    with db.db() as con:
        block = block_holen(con, block_id, konto["id"])
        if block is None:
            return _abgewiesen()
        if block["zustand"] != "erstattet":
            return _zurueck(fehler="Belege lassen sich erst wegräumen, wenn "
                                   "das Geld da ist.")
        weg = 0
        for z in zeilen(con, block_id):
            if z["beleg"]:
                beleg_entfernen(konto["id"], z["id"], z["beleg"])
                con.execute("UPDATE auslage SET beleg=NULL WHERE id=?",
                            (z["id"],))
                weg += 1
    wort = "Beleg" if weg == 1 else "Belege"
    return _zurueck(hinweis=f"{weg} {wort} weggeräumt. Die Beträge stehen "
                            f"weiterhin da.")
