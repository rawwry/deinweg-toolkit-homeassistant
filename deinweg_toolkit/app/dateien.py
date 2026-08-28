"""Dateiverwaltung – Bilder, PDFs und Office-Dateien im Volume /files.

Bewusst getrennt von main.py, wie die uebrigen Module. Eingebunden wird es
am Ende von main.py ueber setup() und include_router().

Grundgedanken:

* **Der Ordner ist die Struktur.** Genau wie beim Wiki gibt es keine
  Datenbanktabelle: was im Dateisystem liegt, ist der Bestand. So laesst
  sich derselbe Ordner ueber die Weboberflaeche *und* ueber die
  Dateifreigabe der NAS bzw. des Pi bearbeiten - dieselbe Ueberlegung wie
  in wiki.py, und aus demselben Grund.
* **Nur eine Handvoll erlaubter Dateiendungen** (siehe ARTEN). Was nicht
  in der Liste steht, wird gar nicht erst angenommen. Eine Sperrliste
  waere die falsche Richtung: man vergisst immer eine Endung.
* **Der Inhaltstyp kommt aus der Endung, nie aus dem Upload.** Ein Browser
  darf uns nicht diktieren, wie wir eine Datei spaeter ausliefern.
* **Ausgeliefert wird inline nur, was gefahrlos inline sein kann**: Bilder
  und PDF. Alles andere geht als Download raus. SVG ist ausdruecklich
  NICHT erlaubt - eine SVG-Datei kann Skript enthalten, das beim direkten
  Aufruf im Browser laufen wuerde.

⚠️ sicherer_pfad() ist die Sicherheitsgrenze dieses Moduls, genau wie im
Wiki. Es ist die zweite Stelle im Programm, an der ein Wert aus der
Adresse zu einem Dateizugriff wird. Nichts daran abschwaechen.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
from urllib.parse import quote, urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

router = APIRouter()

# von setup() gefuellt, damit dieses Modul main.py nicht importieren muss
_u: dict = {}


# --- Festlegungen -------------------------------------------------------------

# Endung -> (Kategorie, Inhaltstyp, Kurzwort fuer die Kachel)
#
# "bild" wird als Vorschau angezeigt, "pdf" laesst sich im Browser oeffnen,
# alles andere wird heruntergeladen. Das Kurzwort steht auf der Kachel,
# wenn es keine Vorschau gibt.
ARTEN: dict[str, tuple[str, str, str]] = {
    "jpg":  ("bild", "image/jpeg", "JPG"),
    "jpeg": ("bild", "image/jpeg", "JPG"),
    "png":  ("bild", "image/png", "PNG"),
    "gif":  ("bild", "image/gif", "GIF"),
    "webp": ("bild", "image/webp", "WEBP"),
    # SVG ist eine Sonderrolle: als Bild in <img> voellig harmlos, beim
    # direkten Aufruf im Browser aber ein Dokument, das Skript ausfuehren
    # koennte. Deshalb liegt darauf beim Ausliefern eine Sandbox, siehe
    # holen(). Ohne die waere SVG hier nicht erlaubt.
    "svg":  ("bild", "image/svg+xml", "SVG"),
    "mp4":  ("video", "video/mp4", "MP4"),
    "eps":  ("grafik", "application/postscript", "EPS"),
    "pdf":  ("pdf", "application/pdf", "PDF"),
    "docx": ("text", "application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.document", "DOCX"),
    "dotx": ("text", "application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.template", "DOTX"),
    "doc":  ("text", "application/msword", "DOC"),
    "xlsx": ("tabelle", "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet", "XLSX"),
    "xls":  ("tabelle", "application/vnd.ms-excel", "XLS"),
    "pptx": ("praesentation", "application/vnd.openxmlformats-officedocument."
                              "presentationml.presentation", "PPTX"),
    "ppt":  ("praesentation", "application/vnd.ms-powerpoint", "PPT"),
    "odt":  ("text", "application/vnd.oasis.opendocument.text", "ODT"),
    "ods":  ("tabelle", "application/vnd.oasis.opendocument.spreadsheet", "ODS"),
    "odp":  ("praesentation", "application/vnd.oasis.opendocument.presentation", "ODP"),
    "csv":  ("tabelle", "text/csv", "CSV"),
    "txt":  ("text", "text/plain", "TXT"),
    "md":   ("text", "text/plain", "MD"),
}

# Was inline ausgeliefert werden darf. Alles andere bekommt
# Content-Disposition: attachment. Video gehoert dazu, sonst liesse es
# sich nicht im Browser abspielen; EPS nicht, das kann ohnehin kein
# Browser darstellen.
INLINE = ("bild", "pdf", "video")

# dieselbe Liste wie im Wiki - was Betriebssystem und NAS selbst anlegen,
# soll hier gar nicht erst auftauchen
SYSTEMKRAM = {"@eadir", "#recycle", "$recycle.bin", "__macosx",
              "system volume information", "thumbs.db", "desktop.ini",
              "lost+found"}

# Unterpfade, die keine Ordner sein duerfen, weil sie eigene Routen sind
RESERVIERT = ("holen", "aktion")


def setup(templates, werte: dict) -> None:
    """Wird von main.py aufgerufen, sobald die Templates bereitstehen."""
    _u.update(werte)
    _u["templates"] = templates


def wurzel() -> str:
    return _u["FILES_PFAD"]


def _systemkram(name: str) -> bool:
    return name.startswith(".") or name.lower() in SYSTEMKRAM


# --- Sicherheitsgrenze --------------------------------------------------------

def sicherer_pfad(pfad: str) -> str | None:
    """Prueft einen Pfad aus der Adresse oder einem Formular.

    Rueckgabe ist der bereinigte relative Pfad ("" fuer die Wurzel) oder
    None, wenn daran etwas nicht stimmt. Wortgleich mit wiki.sicherer_pfad
    aufgebaut, inklusive der Gegenprobe ueber realpath.
    """
    pfad = (pfad or "").strip().replace("\\", "/").strip("/")
    if not pfad:
        return ""
    teile = []
    for teil in pfad.split("/"):
        if teil in ("", ".", "..") or _systemkram(teil):
            return None
        if re.search(r'[<>:"|?*\x00-\x1f]', teil):
            return None
        teile.append(teil)
    if teile[0].lower() in RESERVIERT:
        return None
    rel = "/".join(teile)
    basis = os.path.realpath(wurzel())
    ziel = os.path.realpath(os.path.join(basis, *teile))
    if ziel != basis and not ziel.startswith(basis + os.sep):
        return None
    return rel


def voller_pfad(rel: str) -> str:
    return os.path.join(wurzel(), *rel.split("/")) if rel else wurzel()


def endung(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def erlaubt(name: str) -> bool:
    return endung(name) in ARTEN


def sicherer_name(name: str, ordner: bool = False) -> str | None:
    """Macht aus einer Eingabe einen brauchbaren Datei- oder Ordnernamen.

    Leerzeichen bleiben hier - anders als im Wiki, wo der Name in der
    Adresse steht. Hier wird der Pfad ohnehin kodiert, und
    "Hilfeplan Anna 2026.pdf" liest sich besser als der Unterstrich-Salat.
    """
    name = (name or "").strip().replace("\\", "/").replace("/", "-")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    if not name or _systemkram(name) or name.lower() in RESERVIERT:
        return None
    if len(name) > 120:
        return None
    if not ordner and not erlaubt(name):
        return None
    return name


def adresse(rel: str) -> str:
    """Adresse zum Ausliefern einer Datei - das ist auch der Link fuers Wiki."""
    return "/dateien/holen/" + quote(rel)


# --- Bestand lesen ------------------------------------------------------------

def _groesse(zahl: int) -> str:
    if zahl >= 1024 * 1024:
        return f"{zahl / 1024 / 1024:.1f} MB".replace(".", ",")
    if zahl >= 1024:
        return f"{zahl / 1024:.0f} KB"
    return f"{zahl} B"


def _zeitpunkt(voll: str) -> str:
    try:
        return dt.datetime.fromtimestamp(
            os.path.getmtime(voll)).strftime("%d.%m.%Y, %H:%M")
    except OSError:
        return ""


def _zaehle(voll: str) -> int:
    """Wie viele Eintraege liegen unter diesem Ordner, alle Ebenen zusammen."""
    gesamt = 0
    for _, ordner, dateien in os.walk(voll):
        ordner[:] = [o for o in ordner if not _systemkram(o)]
        gesamt += len(ordner) + len([d for d in dateien if not _systemkram(d)])
    return gesamt


def inhalt(rel: str) -> tuple[list[dict], list[dict]]:
    """Ordner und Dateien eines Verzeichnisses, je alphabetisch."""
    voll = voller_pfad(rel)
    ordner, dateien = [], []
    try:
        eintraege = os.listdir(voll)
    except OSError:
        return [], []
    for name in eintraege:
        if _systemkram(name):
            continue
        kind = os.path.join(voll, name)
        unter = f"{rel}/{name}" if rel else name
        if os.path.isdir(kind):
            try:
                anzahl = len([n for n in os.listdir(kind) if not _systemkram(n)])
            except OSError:
                anzahl = 0
            ordner.append({
                "name": name, "pfad": unter, "anzahl": anzahl,
                "geaendert": _zeitpunkt(kind),
                # Auch ein Ordner laesst sich im Wiki verlinken - der
                # Verweis fuehrt dann auf die Dateiverwaltung mit genau
                # diesem Ordner geoeffnet.
                "adresse": "/dateien?ordner=" + quote(unter),
                "schnipsel": f"[{name}](/dateien?ordner={quote(unter)})",
            })
        elif os.path.isfile(kind):
            # Auch Dateien mit unbekannter Endung werden GEZEIGT - nur eben
            # nicht ausgeliefert. Wer selbst etwas in den Ordner legt, soll
            # es in der Uebersicht wiederfinden und nicht raten muessen, wo
            # es geblieben ist. Das Ausliefern bleibt streng: holen() nimmt
            # weiterhin nur, was in ARTEN steht.
            bekannt = erlaubt(name)
            art, wort = (ARTEN[endung(name)][0], ARTEN[endung(name)][2]) \
                if bekannt else ("unbekannt", (endung(name) or "?").upper()[:5])
            try:
                bytes_ = os.path.getsize(kind)
            except OSError:
                bytes_ = 0
            dateien.append({
                "name": name, "pfad": unter, "art": art, "wort": wort,
                "bekannt": bekannt,
                "groesse": _groesse(bytes_), "bytes": bytes_,
                "geaendert": _zeitpunkt(kind),
                "adresse": adresse(unter) if bekannt else "",
                # Fertiger Markdown-Schnipsel zum Einsetzen ins Wiki.
                # Bilder als Bild, alles andere als Verweis.
                "schnipsel": (("!" if art == "bild" else "")
                              + f"[{name}]({adresse(unter)})") if bekannt else "",
            })
    ordner.sort(key=lambda o: o["name"].casefold())
    dateien.sort(key=lambda d: d["name"].casefold())
    return ordner, dateien


def baum(rel: str = "", tiefe: int = 0) -> list[dict]:
    """Ordner und Dateien als verschachtelte Liste fuer die Seitenleiste.

    Wie im Wiki: die Ordnerstruktur IST die Struktur. Ordner zuerst, dann
    die Dateien - so steht die Gliederung oben und das Blattwerk darunter.
    """
    if tiefe > 8:
        return []
    unterordner, dateien = inhalt(rel)
    knoten = [{"art": "ordner", "name": o["name"], "pfad": o["pfad"],
               "anzahl": o["anzahl"], "kinder": baum(o["pfad"], tiefe + 1)}
              for o in unterordner]
    knoten += [{"art": d["art"], "name": d["name"], "pfad": d["pfad"],
                "bekannt": d["bekannt"], "kinder": []} for d in dateien]
    return knoten


def ordnerbaum() -> list[dict]:
    """Alle Ordner als flache Liste fuer die Auswahlfelder."""
    gefunden = [{"pfad": "", "anzeige": "— oberste Ebene —"}]

    def geh(rel: str, tiefe: int) -> None:
        if tiefe > 6:
            return
        for o in inhalt(rel)[0]:
            gefunden.append({"pfad": o["pfad"],
                             "anzeige": "  " * tiefe + "└ " + o["name"]})
            geh(o["pfad"], tiefe + 1)

    geh("", 0)
    return gefunden


def _brotkrumen(rel: str) -> list[dict]:
    krumen, gelaufen = [], []
    for teil in (rel.split("/") if rel else []):
        gelaufen.append(teil)
        krumen.append({"name": teil, "pfad": "/".join(gelaufen)})
    return krumen


# --- Seiten -------------------------------------------------------------------

def _zurueck(ordner: str, **werte):
    werte = {k: v for k, v in werte.items() if v}
    if ordner:
        werte["ordner"] = ordner
    frage = urlencode(werte)
    return RedirectResponse("/dateien" + (f"?{frage}" if frage else ""),
                            status_code=303)


@router.get("/dateien", response_class=HTMLResponse)
def uebersicht(request: Request, ordner: str = "", hinweis: str = "",
               fehler: str = ""):
    rel = sicherer_pfad(ordner)
    if rel is None or not os.path.isdir(voller_pfad(rel)):
        rel, fehler = "", fehler or "Diesen Ordner gibt es nicht."
    unterordner, dateien = inhalt(rel)
    return _u["templates"].TemplateResponse(
        request=request, name="dateien.html", context={
            "seite": "dateien", "ordner": rel,
            "brotkrumen": _brotkrumen(rel),
            "unterordner": unterordner, "dateien": dateien,
            "baum": baum(), "wurzel_hier": rel == "",
            "ordner_auswahl": ordnerbaum(),
            "endungen": ", ".join(sorted(ARTEN)),
            "max_mb": _u["MAX_UPLOAD_MB"],
            # Damit die Frage "wo liegt das eigentlich" gar nicht erst
            # aufkommt: der Pfad steht in der Oberflaeche.
            "ablage": wurzel(),
            "hinweis": hinweis, "fehler": fehler})


@router.post("/dateien/hochladen")
async def hochladen(datei: list[UploadFile] = File(...),
                    ordner: str = Form("")):
    rel = sicherer_pfad(ordner)
    if rel is None or not os.path.isdir(voller_pfad(rel)):
        return _zurueck("", fehler="Diesen Ordner gibt es nicht.")

    grenze = _u["MAX_UPLOAD_MB"] * 1024 * 1024
    gespeichert, abgelehnt = [], []
    for f in datei:
        if not f.filename:
            continue
        name = sicherer_name(os.path.basename(f.filename))
        if name is None:
            abgelehnt.append(f"{f.filename} (Dateiart nicht erlaubt)")
            continue
        inhalt_ = await f.read()
        if len(inhalt_) > grenze:
            abgelehnt.append(f"{name} (größer als {_u['MAX_UPLOAD_MB']} MB)")
            continue
        # Gleichnamige Datei nicht ueberschreiben, sondern durchnummerieren.
        # Ein stiller Ueberschreiber waere hier besonders aergerlich: der
        # alte Stand haengt womoeglich schon in einer Wiki-Seite.
        ziel = os.path.join(voller_pfad(rel), name)
        stamm, punkt, ext = name.rpartition(".")
        nr = 2
        while os.path.exists(ziel):
            name = f"{stamm} ({nr}){punkt}{ext}"
            ziel = os.path.join(voller_pfad(rel), name)
            nr += 1
        try:
            with open(ziel, "wb") as z:
                z.write(inhalt_)
        except OSError as e:
            abgelehnt.append(f"{name} ({e})")
            continue
        gespeichert.append(name)

    if not gespeichert:
        return _zurueck(rel, fehler="Nichts hochgeladen. "
                                    + " · ".join(abgelehnt))
    wort = "Datei" if len(gespeichert) == 1 else "Dateien"
    text = f"{len(gespeichert)} {wort} hochgeladen."
    if abgelehnt:
        text += " Nicht übernommen: " + " · ".join(abgelehnt)
    return _zurueck(rel, hinweis=text)


@router.post("/dateien/ordner")
def ordner_anlegen(name: str = Form(""), ordner: str = Form("")):
    rel = sicherer_pfad(ordner)
    if rel is None:
        return _zurueck("", fehler="Diesen Ordner gibt es nicht.")
    sauber = sicherer_name(name, ordner=True)
    if sauber is None:
        return _zurueck(rel, fehler="Dieser Ordnername geht nicht.")
    ziel = os.path.join(voller_pfad(rel), sauber)
    if os.path.exists(ziel):
        return _zurueck(rel, fehler=f"„{sauber}“ gibt es hier schon.")
    try:
        os.makedirs(ziel)
    except OSError as e:
        return _zurueck(rel, fehler=f"Ordner ließ sich nicht anlegen: {e}")
    return _zurueck(rel, hinweis=f"Ordner „{sauber}“ angelegt.")


@router.post("/dateien/loeschen")
def loeschen(pfad: str = Form(""), ordner: str = Form("")):
    rel = sicherer_pfad(pfad)
    zurueck = sicherer_pfad(ordner) or ""
    if not rel:
        return _zurueck(zurueck, fehler="Kein gültiger Pfad.")
    voll = voller_pfad(rel)
    name = os.path.basename(rel)
    if os.path.isdir(voll):
        # Anders als im Wiki laesst sich hier auch ein voller Ordner
        # loeschen. Im Wiki ist ein Ordner ein Kapitel, das man nicht aus
        # Versehen wegklickt; hier ist er eine Ablage, die man auch mal
        # komplett wegwirft. Die Sicherheitsabfrage im Browser nennt
        # dafuer die Zahl der Eintraege, die mitgehen.
        drin = _zaehle(voll)
        try:
            shutil.rmtree(voll)
        except OSError as e:
            return _zurueck(zurueck, fehler=f"Ließ sich nicht entfernen: {e}")
        if drin:
            wort = "Eintrag" if drin == 1 else "Einträge"
            return _zurueck(zurueck, hinweis=f"Ordner „{name}“ mit {drin} "
                                             f"{wort} gelöscht.")
        return _zurueck(zurueck, hinweis=f"Ordner „{name}“ entfernt.")
    if not os.path.isfile(voll):
        return _zurueck(zurueck, fehler="Diese Datei gibt es nicht mehr.")
    try:
        os.remove(voll)
    except OSError as e:
        return _zurueck(zurueck, fehler=f"Ließ sich nicht löschen: {e}")
    return _zurueck(zurueck, hinweis=f"„{name}“ gelöscht.")


@router.post("/dateien/umbenennen")
def umbenennen(pfad: str = Form(""), name: str = Form(""),
               ziel_ordner: str = Form(""), ordner: str = Form("")):
    """Umbenennen und Verschieben in einem Schritt - wie im Wiki-Editor."""
    rel = sicherer_pfad(pfad)
    zurueck = sicherer_pfad(ordner) or ""
    if not rel or not os.path.exists(voller_pfad(rel)):
        return _zurueck(zurueck, fehler="Diese Datei gibt es nicht mehr.")
    ist_ordner = os.path.isdir(voller_pfad(rel))
    neuer_name = sicherer_name(name, ordner=ist_ordner)
    if neuer_name is None:
        return _zurueck(zurueck, fehler="Dieser Name geht nicht. Erlaubt sind: "
                                        + ", ".join(sorted(ARTEN)))
    neuer_ordner = sicherer_pfad(ziel_ordner)
    if neuer_ordner is None or not os.path.isdir(voller_pfad(neuer_ordner)):
        return _zurueck(zurueck, fehler="Diesen Zielordner gibt es nicht.")
    # Ein Ordner darf nicht in sich selbst wandern.
    if ist_ordner and (neuer_ordner == rel
                       or neuer_ordner.startswith(rel + "/")):
        return _zurueck(zurueck, fehler="Ein Ordner kann nicht in sich "
                                        "selbst verschoben werden.")
    neu_rel = f"{neuer_ordner}/{neuer_name}" if neuer_ordner else neuer_name
    if neu_rel == rel:
        return _zurueck(zurueck, hinweis="Es gab nichts zu ändern.")
    if os.path.exists(voller_pfad(neu_rel)):
        return _zurueck(zurueck, fehler=f"„{neuer_name}“ gibt es dort schon.")
    try:
        os.rename(voller_pfad(rel), voller_pfad(neu_rel))
    except OSError as e:
        return _zurueck(zurueck, fehler=f"Ließ sich nicht verschieben: {e}")
    return _zurueck(zurueck, hinweis=f"„{os.path.basename(rel)}“ ist jetzt "
                                     f"„{neuer_name}“.")


@router.post("/dateien/verschieben")
def verschieben(pfad: str = Form(""), ziel: str = Form(""),
                ordner: str = Form("")):
    """Wird vom Ziehen im Baum abgeschickt - dasselbe Muster wie im Wiki.

    Der Name bleibt, nur der Ordner wechselt. Umbenennen und Verschieben
    in einem Schritt macht dagegen /dateien/umbenennen.
    """
    rel = sicherer_pfad(pfad)
    zurueck = sicherer_pfad(ordner) or ""
    if not rel or not os.path.exists(voller_pfad(rel)):
        return _zurueck(zurueck, fehler="Diesen Eintrag gibt es nicht mehr.")
    zielordner = sicherer_pfad(ziel)
    if zielordner is None or not os.path.isdir(voller_pfad(zielordner)):
        return _zurueck(zurueck, fehler="Diesen Zielordner gibt es nicht.")
    name = os.path.basename(rel)
    if os.path.isdir(voller_pfad(rel)) and (
            zielordner == rel or zielordner.startswith(rel + "/")):
        return _zurueck(zurueck, fehler="Ein Ordner kann nicht in sich "
                                        "selbst verschoben werden.")
    neu_rel = f"{zielordner}/{name}" if zielordner else name
    if neu_rel == rel:
        return _zurueck(zurueck, hinweis="Der Eintrag lag schon dort.")
    if os.path.exists(voller_pfad(neu_rel)):
        return _zurueck(zurueck, fehler=f"„{name}“ gibt es dort schon.")
    try:
        os.rename(voller_pfad(rel), voller_pfad(neu_rel))
    except OSError as e:
        return _zurueck(zurueck, fehler=f"Ließ sich nicht verschieben: {e}")
    wohin = (f"nach „{zielordner}“" if zielordner
             else "auf die oberste Ebene")
    return _zurueck(zurueck, hinweis=f"„{name}“ {wohin} verschoben.")


# ⚠️ Diese Route muss NACH den festen Pfaden stehen, sonst schluckt der
# Sammelpfad sie - dieselbe Falle wie bei /wiki/aktion/... im Wiki.
@router.get("/dateien/holen/{pfad:path}")
def holen(pfad: str):
    rel = sicherer_pfad(pfad)
    if not rel:
        return RedirectResponse("/dateien?fehler=Dieser+Pfad+ist+nicht+"
                                "zul%C3%A4ssig.", status_code=303)
    voll = voller_pfad(rel)
    if not os.path.isfile(voll) or not erlaubt(os.path.basename(rel)):
        return RedirectResponse("/dateien?fehler=Diese+Datei+gibt+es+nicht.",
                                status_code=303)
    art, typ, _ = ARTEN[endung(rel)]
    # Der Inhaltstyp kommt aus unserer Liste, nicht aus dem Upload. nosniff
    # verhindert, dass der Browser sich etwas anderes zusammenreimt.
    kopf = {"X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300"}
    # ⚠️ SVG ist die einzige erlaubte Dateiart, die selbst Skript tragen
    # kann. In einem <img> wird davon ohnehin nichts ausgefuehrt - der
    # gefaehrliche Fall ist der direkte Aufruf der Adresse, denn dann ist
    # die Datei ein eigenes Dokument. Die Sandbox nimmt ihm genau das:
    # kein Skript, kein Formular, kein eigener Ursprung. Die Einbindung
    # ins Wiki bleibt davon unberuehrt.
    if endung(rel) == "svg":
        kopf["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return FileResponse(
        voll, media_type=typ,
        filename=None if art in INLINE else os.path.basename(rel),
        headers=kopf)
