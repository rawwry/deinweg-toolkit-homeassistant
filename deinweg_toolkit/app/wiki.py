"""Wiki - Wissensbasis aus Markdown-Dateien im Ordner /wiki.

Bewusst kein weiterer Datenbankbereich: die Seiten sind ganz normale
.md-Dateien auf der NAS. Damit laesst sich dasselbe Wiki im Browser
bearbeiten und ueber die Dateifreigabe mit jedem Editor - genau das war
die Anforderung. Die Ordnerstruktur ist die Wiki-Struktur, ein
zusaetzliches Inhaltsverzeichnis gibt es deshalb nicht.

Eingebunden wird das Modul am Ende von main.py ueber setup() und
include_router(), dasselbe Muster wie auth.py, vorgaenge.py und
einstellungen.py. Den Pfad bekommt es dabei gereicht, damit main.py die
einzige Stelle bleibt, an der Umgebungsvariablen gelesen werden.

Sicherheit:
* Jeder Pfad geht durch sicherer_pfad() und wird danach ueber realpath
  gegen den Wiki-Ordner geprueft. Damit kommt weder "../" noch ein
  Symlink aus dem Wiki heraus.
* Gelesen und geschrieben werden ausschliesslich .md-Dateien.
* Der Markdown-Wandler entschaerft allen Text, HTML aus einer Datei wird
  also nicht ausgefuehrt (siehe markdown.py).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import posixpath
import re
import shutil
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import auth, markdown as md

router = APIRouter()

# Von setup() gefuellt: alles, was aus main.py gebraucht wird.
_u: dict = {}

# Dateien, die im Baum ganz oben stehen und den Ordner beschreiben.
STARTSEITEN = ("README.md", "readme.md", "index.md", "Index.md")

# Was Betriebssysteme und die NAS selbst in die Ordner legen. Das gehoert
# nicht ins Wiki: @eaDir legt die Synology fuer Vorschaubilder an,
# #recycle ist ihr Papierkorb, der Rest kommt von Windows und macOS.
# Alles, was mit einem Punkt beginnt, faellt ohnehin schon heraus.
SYSTEMKRAM = {"@eadir", "#recycle", "$recycle.bin", "__macosx",
              "system volume information", "thumbs.db", "desktop.ini",
              "lost+found"}


def _systemkram(name: str) -> bool:
    return name.startswith(".") or name.lower() in SYSTEMKRAM

# Titel je Datei, damit der Navigationsbaum nicht bei jedem Seitenaufruf
# saemtliche Dateien komplett liest. Schluessel ist der volle Pfad, der
# Wert das Paar (Zeitstempel, Titel) - aendert sich die Datei, wird neu
# gelesen.
_TITEL: dict[str, tuple[float, str]] = {}


def setup(templates, werte: dict) -> None:
    _u["templates"] = templates
    _u.update(werte)


# --- Pfade -------------------------------------------------------------------

def wurzel() -> str:
    return _u.get("WIKI_PFAD", "/wiki")


def sicherer_pfad(pfad: str) -> str | None:
    """Prueft einen Pfad aus der Adresse oder einem Formular.

    Rueckgabe ist der bereinigte relative Pfad ("" fuer die Wurzel) oder
    None, wenn daran etwas nicht stimmt. Bewusst streng: lieber eine
    Fehlermeldung als ein Schreibzugriff neben dem Wiki-Ordner.
    """
    pfad = (pfad or "").strip().replace("\\", "/").strip("/")
    if not pfad:
        return ""
    if pfad == "aktion" or pfad.startswith("aktion/"):
        return None
    teile = []
    for teil in pfad.split("/"):
        if teil in ("", ".", "..") or _systemkram(teil):
            return None
        if re.search(r'[<>:"|?*\x00-\x1f]', teil):
            return None
        teile.append(teil)
    rel = "/".join(teile)
    basis = os.path.realpath(wurzel())
    ziel = os.path.realpath(os.path.join(basis, *teile))
    if ziel != basis and not ziel.startswith(basis + os.sep):
        return None
    return rel


def voller_pfad(rel: str) -> str:
    return os.path.join(wurzel(), *rel.split("/")) if rel else wurzel()


def sicherer_name(name: str, ordner: bool = False) -> str | None:
    """Macht aus einer Eingabe einen brauchbaren Datei- oder Ordnernamen."""
    name = (name or "").strip().replace("\\", "/").replace("/", "-")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", "_", name).strip("._-")
    if not name or name.lower() == "aktion" or _systemkram(name):
        return None
    if not ordner and not name.lower().endswith(".md"):
        name += ".md"
    if len(name) > 120:
        return None
    return name


def _adresse(rel: str) -> str:
    return "/wiki/" + quote(rel) if rel else "/wiki"


# --- Baum und Titel ----------------------------------------------------------

# Woerter, die in einem Ordnernamen klein bleiben. Ordnernamen sind hier
# durchweg Substantivgruppen ("notfall_und_krisen"), deshalb wird gross
# geschrieben - ausser bei diesen Verbindungswoertern.
KLEIN = {"und", "oder", "der", "die", "das", "den", "dem", "des", "im",
         "in", "am", "an", "auf", "aus", "bei", "fuer", "für", "mit",
         "nach", "von", "vom", "zu", "zum", "zur", "ohne", "pro", "je"}


def _name_titel(name: str) -> str:
    """Notnagel, wenn eine Datei keine Ueberschrift hat: aus
    03_vorlage_widerspruch_amt.md wird "Vorlage Widerspruch Amt"."""
    titel = re.sub(r"\.md$", "", name, flags=re.I)
    titel = re.sub(r"^[_\d]+[_\-. ]*", "", titel)
    titel = titel.replace("_", " ").replace("-", " ").strip()
    if not titel:
        titel = name
    woerter = []
    for nr, wort in enumerate(titel.split(" ")):
        if not wort:
            continue
        if nr and wort.lower() in KLEIN:
            woerter.append(wort.lower())
        elif wort[:1].islower():
            woerter.append(wort[:1].upper() + wort[1:])
        else:
            woerter.append(wort)
    return " ".join(woerter) or titel


def titel_der_datei(voll: str, name: str) -> str:
    """Erste Ueberschrift der Datei, sonst der Dateiname."""
    try:
        stand = os.path.getmtime(voll)
    except OSError:
        return _name_titel(name)
    gemerkt = _TITEL.get(voll)
    if gemerkt and gemerkt[0] == stand:
        return gemerkt[1]
    titel = ""
    try:
        with open(voll, encoding="utf-8", errors="replace") as f:
            for _ in range(40):
                zeile = f.readline()
                if not zeile:
                    break
                treffer = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", zeile.rstrip())
                if treffer:
                    titel = treffer.group(1).strip()
                    break
    except OSError:
        pass
    titel = titel or _name_titel(name)
    _TITEL[voll] = (stand, titel)
    return titel


def _eintraege(rel: str) -> tuple[list, list]:
    """Sichtbare Unterordner und .md-Dateien eines Ordners."""
    voll = voller_pfad(rel)
    ordner, dateien = [], []
    try:
        namen = sorted(os.listdir(voll), key=lambda n: n.lower())
    except OSError:
        return [], []
    for name in namen:
        if _systemkram(name):
            continue
        pfad = os.path.join(voll, name)
        unter = f"{rel}/{name}" if rel else name
        if os.path.isdir(pfad):
            ordner.append((name, unter, pfad))
        elif name.lower().endswith(".md"):
            dateien.append((name, unter, pfad))
    return ordner, dateien


def baum(rel: str = "", tiefe: int = 0) -> list[dict]:
    """Der Navigationsbaum, so wie er links steht."""
    if tiefe > 8:            # Notbremse gegen verschachtelte Symlinks
        return []
    ordner, dateien = _eintraege(rel)
    if tiefe == 0:
        # Die Startseite steht schon als eigener Punkt ueber dem Baum.
        start = _startseite_im("")
        dateien = [d for d in dateien if d[1] != start]
    knoten = []
    for name, unter, pfad in ordner:
        knoten.append({
            "art": "ordner", "name": name, "pfad": unter,
            "adresse": _adresse(unter), "titel": _name_titel(name),
            "kinder": baum(unter, tiefe + 1),
        })
    for name, unter, pfad in dateien:
        knoten.append({
            "art": "seite", "name": name, "pfad": unter,
            "adresse": _adresse(unter), "titel": titel_der_datei(pfad, name),
            "kinder": [],
        })
    return knoten


def ordnerliste(rel: str = "", tiefe: int = 0) -> list[dict]:
    """Flache Liste aller Ordner fuer die Auswahlfelder."""
    liste = []
    for name, unter, _pfad in _eintraege(rel)[0]:
        liste.append({"pfad": unter, "anzeige": " " * tiefe + name})
        if tiefe < 8:
            liste += ordnerliste(unter, tiefe + 1)
    return liste


def _startseite_im(rel: str) -> str:
    for name in STARTSEITEN:
        if os.path.isfile(os.path.join(voller_pfad(rel), name)):
            return f"{rel}/{name}" if rel else name
    return ""


def _brotkrumen(rel: str) -> list[dict]:
    krumen, gesammelt = [], ""
    for teil in rel.split("/") if rel else []:
        gesammelt = f"{gesammelt}/{teil}" if gesammelt else teil
        krumen.append({"titel": _name_titel(teil), "pfad": gesammelt,
                       "adresse": _adresse(gesammelt)})
    return krumen


def _zeitpunkt(voll: str) -> str:
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(voll)).strftime("%d.%m.%Y %H:%M")
    except OSError:
        return ""


def _umfang(rel: str) -> str:
    """Wie viel in einem Ordner steckt. Steht in der Listenansicht an der
    Stelle, an der bei einer Seite die Dateigroesse steht."""
    ordner, dateien = _eintraege(rel)
    anzahl = len(ordner) + len(dateien)
    if not anzahl:
        return "leer"
    return "1 Eintrag" if anzahl == 1 else f"{anzahl} Einträge"


def _groesse(voll: str) -> str:
    """Dateigroesse in einer Form, die man ueberfliegen kann."""
    try:
        bytes_ = os.path.getsize(voll)
    except OSError:
        return ""
    if bytes_ < 1024:
        return f"{bytes_} B"
    return f"{bytes_ / 1024:.1f} kB".replace(".", ",")


def _pruefsumme(text: str) -> str:
    """Kurzer Fingerabdruck des Inhalts. Damit merkt das Speichern, wenn
    jemand anderes (oder derselbe in einem zweiten Fenster, oder ein
    Editor auf der NAS) die Datei zwischenzeitlich geaendert hat."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# --- Links innerhalb des Wikis ----------------------------------------------

def link_aufloeser(aktueller_ordner: str):
    """Rechnet Verweise in einer Seite auf echte Wiki-Adressen um.

    Ein Link wie [Kontakte](02_kontakte.md) steht relativ zur Datei, in
    der er steht. Er wird deshalb hier serverseitig aufgeloest und nicht
    dem Browser ueberlassen - der wuerde ihn je nach Schraegstrich am
    Ende der Adresse unterschiedlich verstehen.
    """
    def aufloesen(adresse: str) -> tuple[str, bool]:
        adresse = (adresse or "").strip()
        if not adresse:
            return "#", False
        if re.match(r"^[a-zA-Z][\w+.\-]*:", adresse) or adresse.startswith("//"):
            return adresse, True          # http:, mailto:, tel: ...
        if adresse.startswith("#"):
            return adresse, False         # Sprungmarke in derselben Seite
        anker = ""
        if "#" in adresse:
            adresse, rest = adresse.split("#", 1)
            anker = "#" + rest
        # Verweise auf die Dateiverwaltung bleiben, wie sie sind. Ein
        # absoluter Pfad gilt hier sonst als "relativ zur Wiki-Wurzel"
        # (/02_kontakte.md -> /wiki/02_kontakte.md); ohne diese Ausnahme
        # wuerde aus dem fertigen Schnipsel der Dateiverwaltung
        # /wiki/dateien/holen/... und das Bild bliebe leer.
        if adresse.startswith("/dateien/"):
            return adresse + anker, False
        if adresse.startswith("/"):
            ziel = adresse.strip("/")
        else:
            ziel = posixpath.normpath(posixpath.join(aktueller_ordner, adresse))
        if ziel in (".", "/", ""):
            ziel = ""
        if ziel.startswith(".."):
            return "#", False             # zeigt aus dem Wiki heraus
        return _adresse(ziel) + anker, False
    return aufloesen


# --- Anzeige -----------------------------------------------------------------

def _zurueck(ziel: str, hinweis: str = "", fehler: str = ""):
    werte = {k: v for k, v in (("hinweis", hinweis), ("fehler", fehler)) if v}
    trenner = "&" if "?" in ziel else "?"
    return RedirectResponse(ziel + (trenner + urlencode(werte) if werte else ""),
                            status_code=303)


def _rahmen(request: Request, zusatz: dict, hinweis: str = "", fehler: str = "",
            code: int = 200):
    inhalt = {
        "seite": "wiki",
        "baum": baum(),
        "ordner_auswahl": ordnerliste(),
        "hinweis": hinweis,
        "fehler": fehler,
        "aktuell": "",
        "brotkrumen": [],
        "suchwort": "",
        "ordner": "",
        "titel": "Wiki",
        "wurzel_hier": False,
        "adresse": "/wiki",
        "verzeichnis": [],
    }
    inhalt.update(zusatz)
    return _u["templates"].TemplateResponse(
        request=request, name="wiki.html", context=inhalt, status_code=code)


@router.get("/wiki", response_class=HTMLResponse)
def wiki_start(request: Request, hinweis: str = "", fehler: str = ""):
    """Startseite: die README des Wiki-Ordners, sonst die Ordneruebersicht."""
    start = _startseite_im("")
    if start:
        return _seite(request, start, hinweis=hinweis, fehler=fehler, ist_start=True)
    return _ordner(request, "", hinweis=hinweis, fehler=fehler)


@router.get("/wiki/aktion/suche", response_class=HTMLResponse)
def wiki_suche(request: Request, q: str = ""):
    """Volltextsuche ueber Titel und Inhalt aller Seiten."""
    wort = (q or "").strip()
    treffer = []
    if len(wort) >= 2:
        muster = re.compile(re.escape(wort), re.I)
        for rel, voll in _alle_seiten():
            try:
                with open(voll, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            name = os.path.basename(rel)
            im_text = muster.search(text)
            if not im_text and not muster.search(name):
                continue
            stelle = ""
            if im_text:
                anfang = max(0, im_text.start() - 60)
                stelle = _lesbar(text[anfang:im_text.start() + 120])
                if anfang:
                    stelle = "… " + stelle
            treffer.append({
                "pfad": rel, "adresse": _adresse(rel),
                "titel": titel_der_datei(voll, name),
                "ordner": os.path.dirname(rel),
                "stelle": stelle,
                "anzahl": len(muster.findall(text)),
            })
        treffer.sort(key=lambda x: (-x["anzahl"], x["pfad"]))
    return _rahmen(request, {"art": "suche", "suchwort": wort, "treffer": treffer,
                             "titel": "Suche"})


def _lesbar(ausschnitt: str) -> str:
    """Nimmt einer Textstelle die Markdown-Zeichen, damit die Vorschau in
    der Trefferliste lesbar bleibt statt aus Sternchen zu bestehen."""
    text = re.sub(r"^\s*[-*+]\s+|^\s*#{1,6}\s+", " ", ausschnitt, flags=re.M)
    text = re.sub(r"[*_`>#|]+", "", text)
    text = re.sub(r"-{3,}", " ", text)
    return " ".join(text.split())


def _alle_seiten(rel: str = "", tiefe: int = 0) -> list[tuple[str, str]]:
    if tiefe > 8:
        return []
    ordner, dateien = _eintraege(rel)
    seiten = [(unter, pfad) for _n, unter, pfad in dateien]
    for _n, unter, _p in ordner:
        seiten += _alle_seiten(unter, tiefe + 1)
    return seiten


@router.get("/wiki/aktion/herunterladen")
def wiki_herunterladen(pfad: str = ""):
    """Gibt die Seite als .md-Datei heraus - also genau das, was auch im
    Wiki-Ordner liegt. Kein Umweg ueber eine Umwandlung: wer eine Seite
    herunterlaedt, soll sie anderswo weiterbearbeiten koennen."""
    rel = sicherer_pfad(pfad)
    if not rel or not rel.lower().endswith(".md"):
        return _zurueck("/wiki", fehler="Diese Seite gibt es nicht (mehr).")
    try:
        with open(voller_pfad(rel), "rb") as f:
            daten = f.read()
    except OSError:
        return _zurueck("/wiki", fehler="Diese Seite gibt es nicht (mehr).")
    name = os.path.basename(rel)
    # Umlaute im Dateinamen: der schlichte filename-Teil vertraegt nur
    # ASCII, deshalb zusaetzlich die kodierte Fassung nach RFC 5987.
    schlicht = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "wiki.md"
    return Response(
        content=daten, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="{schlicht}"; '
                 f"filename*=UTF-8''{quote(name)}"})


@router.get("/wiki/{pfad:path}", response_class=HTMLResponse)
def wiki_seite(request: Request, pfad: str, bearbeiten: str = "",
               hinweis: str = "", fehler: str = ""):
    rel = sicherer_pfad(pfad)
    if rel is None:
        return _rahmen(request, {"art": "fehlt", "titel": "Nicht gefunden",
                                 "gesucht": pfad},
                       fehler="Dieser Pfad ist nicht zulässig.", code=404)
    voll = voller_pfad(rel)
    if os.path.isdir(voll):
        return _ordner(request, rel, hinweis=hinweis, fehler=fehler)
    if os.path.isfile(voll) and rel.lower().endswith(".md"):
        # Ohne Schreibrecht gibt es keinen Editor. Die Middleware weist die
        # Speicher-Route ohnehin ab; hier wird zusaetzlich die Ansicht
        # verweigert, damit niemand erst einen Text tippt und dann ein 403
        # kassiert. Bewusst kein Fehler, sondern die Leseansicht mit Hinweis.
        darf_schreiben = auth.darf_wiki_schreiben(request.state.benutzer)
        if bearbeiten and not darf_schreiben:
            return _seite(request, rel, bearbeiten=False, hinweis=hinweis,
                          fehler="Du darfst Wiki-Seiten lesen, aber nicht ändern.")
        return _seite(request, rel, bearbeiten=bool(bearbeiten),
                      hinweis=hinweis, fehler=fehler)
    return _rahmen(request, {"art": "fehlt", "titel": "Nicht gefunden",
                             "gesucht": rel, "aktuell": rel,
                             "adresse": _adresse(rel),
                             "brotkrumen": _brotkrumen(rel)},
                   fehler=fehler, hinweis=hinweis, code=404)


def _seite(request: Request, rel: str, bearbeiten: bool = False,
           hinweis: str = "", fehler: str = "", ist_start: bool = False):
    voll = voller_pfad(rel)
    try:
        with open(voll, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        return _rahmen(request, {"art": "fehlt", "titel": "Nicht lesbar",
                                 "gesucht": rel},
                       fehler=f"Die Datei ließ sich nicht lesen: {e}", code=404)
    ordner = posixpath.dirname(rel)
    zusatz = {
        "art": "bearbeiten" if bearbeiten else "seite",
        "aktuell": rel,
        "adresse": _adresse(rel),
        "wurzel_hier": rel == _startseite_im(""),
        "brotkrumen": _brotkrumen(rel),
        "titel": titel_der_datei(voll, os.path.basename(rel)),
        "roh": text,
        "name": os.path.basename(rel),
        "ordner": ordner,
        "pruefsumme": _pruefsumme(text),
        "geaendert": _zeitpunkt(voll),
        "zeichen": len(text),
        "ist_start": ist_start,
    }
    if not bearbeiten:
        # Das Verzeichnis der Ueberschriften wird beim Wandeln gleich
        # mitgesammelt - daraus baut die Vorlage "Auf dieser Seite".
        verzeichnis: list[dict] = []
        zusatz["html"] = md.zu_html(text, link_aufloeser(ordner), verzeichnis,
                                    faltbar=True)
        # Die Ueberschrift der obersten Stufe ist der Seitentitel und steht
        # schon oben; im Verzeichnis waere sie nur eine Dopplung.
        stufen = [u for u in verzeichnis if u["stufe"] >= 2]
        zusatz["verzeichnis"] = stufen if len(stufen) >= 3 else []
    return _rahmen(request, zusatz, hinweis=hinweis, fehler=fehler)


def _ordner(request: Request, rel: str, hinweis: str = "", fehler: str = ""):
    unterordner, dateien = _eintraege(rel)
    start = _startseite_im(rel)
    einleitung = ""
    if start:
        try:
            with open(voller_pfad(start), encoding="utf-8", errors="replace") as f:
                einleitung = md.zu_html(f.read(), link_aufloeser(rel))
        except OSError:
            einleitung = ""
    return _rahmen(request, {
        "art": "ordner",
        "aktuell": rel,
        "adresse": _adresse(rel),
        "wurzel_hier": not rel,
        "brotkrumen": _brotkrumen(rel),
        "titel": _name_titel(os.path.basename(rel)) if rel else "Wiki",
        "ordner": rel,
        "einleitung": einleitung,
        "start_datei": start,
        "start_adresse": _adresse(start),
        "kinder_ordner": [{"pfad": u, "adresse": _adresse(u),
                           "titel": _name_titel(n), "umfang": _umfang(u)}
                          for n, u, _p in unterordner],
        "kinder_seiten": [{"pfad": u, "adresse": _adresse(u), "name": n,
                           "titel": titel_der_datei(p, n),
                           "geaendert": _zeitpunkt(p),
                           "groesse": _groesse(p)}
                          for n, u, p in dateien if u != start],
    }, hinweis=hinweis, fehler=fehler)


# --- Bearbeiten --------------------------------------------------------------

@router.post("/wiki/aktion/speichern")
def wiki_speichern(pfad: str = Form(""), ordner: str = Form(""),
                   name: str = Form(""), inhalt: str = Form(""),
                   pruefsumme: str = Form("")):
    """Speichert den Text. Ordner und Dateiname duerfen dabei mit
    geaendert werden - das ist zugleich Umbenennen und Verschieben."""
    rel = sicherer_pfad(pfad)
    if not rel or not os.path.isfile(voller_pfad(rel)):
        return _zurueck("/wiki", fehler="Diese Seite gibt es nicht (mehr).")

    alt_voll = voller_pfad(rel)
    try:
        with open(alt_voll, encoding="utf-8", errors="replace") as f:
            vorher = f.read()
    except OSError as e:
        return _zurueck(_adresse(rel), fehler=f"Datei nicht lesbar: {e}")

    # Zwischenzeitliche Aenderung von aussen nicht ueberschreiben.
    if pruefsumme and pruefsumme != _pruefsumme(vorher):
        return _zurueck(
            _adresse(rel) + "?bearbeiten=1",
            fehler="Die Datei wurde zwischenzeitlich geändert – vermutlich in "
                   "einem anderen Fenster oder direkt auf der NAS. Zur "
                   "Sicherheit wurde nichts überschrieben. Bitte den eigenen "
                   "Text kopieren, die Seite neu laden und erneut einsetzen.")

    ziel_ordner = sicherer_pfad(ordner)
    if ziel_ordner is None or (ziel_ordner and not os.path.isdir(voller_pfad(ziel_ordner))):
        return _zurueck(_adresse(rel) + "?bearbeiten=1",
                        fehler="Diesen Ordner gibt es nicht.")
    ziel_name = sicherer_name(name or os.path.basename(rel))
    if not ziel_name:
        return _zurueck(_adresse(rel) + "?bearbeiten=1",
                        fehler="Der Dateiname ist nicht verwendbar.")

    neu_rel = f"{ziel_ordner}/{ziel_name}" if ziel_ordner else ziel_name
    neu_voll = voller_pfad(neu_rel)
    if neu_rel != rel and os.path.exists(neu_voll):
        return _zurueck(_adresse(rel) + "?bearbeiten=1",
                        fehler=f"„{ziel_name}“ gibt es in diesem Ordner schon.")

    text = (inhalt or "").replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    try:
        _schreiben(alt_voll, text)
        if neu_rel != rel:
            os.replace(alt_voll, neu_voll)
    except OSError as e:
        return _zurueck(_adresse(rel) + "?bearbeiten=1",
                        fehler=f"Speichern fehlgeschlagen: {e}")

    hinweis = "Gespeichert."
    if neu_rel != rel:
        hinweis = f"Gespeichert und nach „{neu_rel}“ verschoben."
    return _zurueck(_adresse(neu_rel), hinweis=hinweis)


def _schreiben(voll: str, text: str) -> None:
    """Erst daneben schreiben, dann umlegen - so bleibt bei einem Abbruch
    die alte Fassung heil statt halb ueberschrieben zu sein."""
    ordner = os.path.dirname(voll)
    os.makedirs(ordner, exist_ok=True)
    zwischen = os.path.join(ordner, f".{os.path.basename(voll)}.neu")
    with open(zwischen, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(zwischen, voll)


@router.post("/wiki/aktion/neu")
def wiki_neu(ordner: str = Form(""), name: str = Form(""),
             art: str = Form("seite")):
    ziel_ordner = sicherer_pfad(ordner)
    if ziel_ordner is None or (ziel_ordner and not os.path.isdir(voller_pfad(ziel_ordner))):
        return _zurueck("/wiki", fehler="Diesen Ordner gibt es nicht.")
    ist_ordner = art == "ordner"
    ziel_name = sicherer_name(name, ordner=ist_ordner)
    if not ziel_name:
        return _zurueck(_adresse(ziel_ordner),
                        fehler="Bitte einen verwendbaren Namen angeben.")
    neu_rel = f"{ziel_ordner}/{ziel_name}" if ziel_ordner else ziel_name
    neu_voll = voller_pfad(neu_rel)
    if os.path.exists(neu_voll):
        return _zurueck(_adresse(ziel_ordner),
                        fehler=f"„{ziel_name}“ gibt es hier schon.")
    try:
        if ist_ordner:
            os.makedirs(neu_voll)
            return _zurueck(_adresse(neu_rel), hinweis=f"Ordner „{ziel_name}“ angelegt.")
        titel = _name_titel(ziel_name)
        _schreiben(neu_voll, f"# {titel}\n\n")
    except OSError as e:
        return _zurueck(_adresse(ziel_ordner), fehler=f"Anlegen fehlgeschlagen: {e}")
    return _zurueck(_adresse(neu_rel) + "?bearbeiten=1",
                    hinweis="Seite angelegt – der Text kann direkt hier stehen.")


@router.post("/wiki/aktion/loeschen")
def wiki_loeschen(pfad: str = Form("")):
    rel = sicherer_pfad(pfad)
    if not rel:
        return _zurueck("/wiki", fehler="Kein gültiger Pfad.")
    voll = voller_pfad(rel)
    eltern = _adresse(posixpath.dirname(rel))
    if os.path.isdir(voll):
        unterordner, dateien = _eintraege(rel)
        if unterordner or dateien:
            return _zurueck(_adresse(rel), fehler=(
                f"„{os.path.basename(rel)}“ enthält noch "
                f"{len(unterordner) + len(dateien)} Einträge. Ein Ordner "
                "lässt sich erst entfernen, wenn er leer ist – so kann "
                "nicht versehentlich ein ganzer Zweig verschwinden."))
        try:
            shutil.rmtree(voll)
        except OSError as e:
            return _zurueck(_adresse(rel), fehler=f"Löschen fehlgeschlagen: {e}")
        return _zurueck(eltern, hinweis=f"Ordner „{os.path.basename(rel)}“ entfernt.")
    if not os.path.isfile(voll):
        return _zurueck("/wiki", fehler="Diese Seite gibt es nicht (mehr).")
    try:
        os.remove(voll)
    except OSError as e:
        return _zurueck(_adresse(rel), fehler=f"Löschen fehlgeschlagen: {e}")
    return _zurueck(eltern, hinweis=f"„{os.path.basename(rel)}“ wurde entfernt.")


@router.post("/wiki/aktion/verschieben")
def wiki_verschieben(pfad: str = Form(""), ziel: str = Form("")):
    """Wird vom Ziehen im Navigationsbaum aufgerufen (und vom Auswahlfeld
    im Bearbeitungsmodus, das ueber /wiki/aktion/speichern laeuft)."""
    rel = sicherer_pfad(pfad)
    ziel_ordner = sicherer_pfad(ziel)
    if not rel or ziel_ordner is None:
        return _zurueck("/wiki", fehler="Verschieben nicht möglich.")
    voll = voller_pfad(rel)
    ziel_voll = voller_pfad(ziel_ordner)
    if not os.path.exists(voll):
        return _zurueck("/wiki", fehler="Diesen Eintrag gibt es nicht (mehr).")
    if ziel_ordner and not os.path.isdir(ziel_voll):
        return _zurueck(_adresse(rel), fehler="Das Ziel ist kein Ordner.")
    if posixpath.dirname(rel) == ziel_ordner:
        return _zurueck(_adresse(rel), hinweis="Liegt schon dort.")
    # Ein Ordner darf nicht in sich selbst wandern.
    if os.path.isdir(voll) and (ziel_ordner == rel
                                or ziel_ordner.startswith(rel + "/")):
        return _zurueck(_adresse(rel),
                        fehler="Ein Ordner lässt sich nicht in sich selbst verschieben.")
    name = os.path.basename(rel)
    neu_rel = f"{ziel_ordner}/{name}" if ziel_ordner else name
    if os.path.exists(voller_pfad(neu_rel)):
        return _zurueck(_adresse(rel),
                        fehler=f"Im Zielordner gibt es „{name}“ bereits.")
    try:
        os.replace(voll, voller_pfad(neu_rel))
    except OSError as e:
        return _zurueck(_adresse(rel), fehler=f"Verschieben fehlgeschlagen: {e}")
    wohin = ziel_ordner or "die oberste Ebene"
    return _zurueck(_adresse(neu_rel), hinweis=f"„{name}“ liegt jetzt in {wohin}.")


# --- Start -------------------------------------------------------------------

def wiki_anlegen() -> None:
    """Legt den Wiki-Ordner an und schreibt eine Startseite, falls er
    vollstaendig leer ist. Wird beim Start aus main.py aufgerufen."""
    try:
        os.makedirs(wurzel(), exist_ok=True)
    except OSError as e:
        print(f"[start] Wiki-Ordner {wurzel()} nicht verfuegbar: {e}", flush=True)
        return
    ordner, dateien = _eintraege("")
    if ordner or dateien:
        return
    try:
        _schreiben(os.path.join(wurzel(), "README.md"),
                   "# Wiki\n\nDas ist die Startseite. Sie liegt als "
                   "`README.md` im Wiki-Ordner und lässt sich über "
                   "„Bearbeiten“ ändern.\n\nOrdner sind die Struktur des "
                   "Wikis: Ein neuer Ordner ist ein neues Kapitel, eine "
                   "neue Seite darin ein Artikel.\n")
        print("[start] Wiki-Startseite angelegt", flush=True)
    except OSError as e:
        print(f"[start] Wiki-Startseite nicht schreibbar: {e}", flush=True)
