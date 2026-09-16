"""Dein Weg Toolkit - die eigenen Grafiken.

Schriftzug, Favicon und App-Symbol lassen sich unter Einstellungen ->
System und Sicherung -> Branding durch eigene Dateien ersetzen. Dieses
Modul liefert sie aus (/marke/, /symbol/) und rechnet daraus das
Web-App-Manifest (/manifest.json).

⚠️ Eigenes Modul seit 1.45. Der Grund ist die 2000-Zeilen-Grenze, die
die Pruefung fuer main.py haelt (seit der Aufteilung in 1.32.1): mit dem
gerechneten Manifest waere main.py darueber gelaufen. Der Block gehoert
ohnehin zusammen - drei Adressen, zwei Tabellen und ein Puffer, die
nichts aus main.py brauchen ausser APP_NAME und VERSION.

⚠️ Modulmuster wie ueberall: eigener APIRouter, eine setup()-Funktion,
Zugriff auf die Umgebung ueber _u. Kein Import von main.py - sonst gaebe
es einen Ringschluss (Abschnitt 3 der CLAUDE.md).

⚠️ Alle drei Adressen sind OHNE ANMELDUNG erreichbar (auth.SessionAuth,
siehe OEFFENTLICHE_PFADE und die Praefixe dort): der Anmeldebildschirm
zeigt den Schriftzug, und Favicon wie Manifest holt der Browser, bevor
es ueberhaupt eine Sitzung gibt.
"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import Response

from . import db

BASIS = os.path.dirname(__file__)

router = APIRouter()

# APP_NAME und VERSION - main.py ist die einzige Stelle, an der
# Umgebungsvariablen gelesen werden.
_u: dict = {}


def setup(umgebung: dict) -> None:
    _u.update(umgebung)


# --- Eigene Logos -------------------------------------------------------------
#
# Die beiden Schriftzuege der Kopfzeile lassen sich unter Einstellungen ->
# System und Sicherung durch eigene SVG-Dateien ersetzen.
#
# ⚠️⚠️ Gespeichert wird in der DATENBANK (Tabelle konfig), nicht als Datei
# neben app/static/. Grund: der Programmcode liegt im Add-on-Abbild
# (COPY app /opt/deinweg/app im Dockerfile) - eine dort abgelegte Datei
# waere beim naechsten Update spurlos weg, und zwar ohne Fehlermeldung.
# In der Datenbank ueberlebt sie jedes Update und liegt ausserdem in der
# Sicherung mit drin. Eine SVG-Datei ist Text und ein paar Dutzend
# Kilobyte gross - das traegt die Tabelle muehelos.

# ⚠️ Der Schluessel ist der Name der Adresse UND - seit 1.47 - der Name
# der Zeile in der Tabelle symbol. Die erste Angabe ist nur noch der Name
# des Formularfelds (bis 1.46 zugleich der konfig-Schluessel).
# ⚠️ Drei Angaben je Eintrag, seit 1.45 auch ein Hinweis: der Name war
# vorher der ganze Satz ("Schriftzug fuer das dunkle Thema") und stand
# damit als Ueberschrift ueber einem Feld, das ihn ohnehin erklaert. Die
# Hinweiszeile sagt jetzt das, was man beim Exportieren wissen muss.
MARKEN = {
    "logo-fuer-dunkel": ("logo_dunkel", "Dunkles Thema",
                         "Helle Schrift – sie steht auf dunklem Grund"),
    "logo-fuer-hell": ("logo_hell", "Helles Thema",
                       "Dunkle Schrift – sie steht auf hellem Grund"),
}

# Wird beim Start und nach jedem Tausch neu gefuellt. Ohne den Puffer
# fragte jeder Seitenaufbau die Datenbank nach dem Zeitstempel - nur um
# ihn an eine Bildadresse zu haengen.
_marken_puffer: dict = {"stand": "", "geladen": False, "symbole": frozenset()}


def markenstand() -> str:
    """Der Anhang fuer ?v= an den Logo-Adressen.

    ⚠️ NICHT die Programmversion: die aendert sich beim Tausch eines Logos
    ja gerade nicht, und der Browser haenge dann am alten Bild. Genau
    diese Falle ist beim Grafiktausch in 1.27 schon einmal zugeschnappt.
    """
    if not _marken_puffer["geladen"]:
        try:
            with db.db() as con:
                zeile = con.execute(
                    "SELECT wert FROM konfig WHERE schluessel='logo_stand'"
                ).fetchone()
            # ⚠️ Nur die Ziffern: der Wert ist ein Zeitpunkt
            # („2026-09-08 10:48"), und Leerzeichen wie Doppelpunkte
            # haben in einer Bildadresse nichts verloren.
            roh = (zeile["wert"] if zeile else "") or ""
            _marken_puffer["stand"] = re.sub(r"\D", "", roh)
        except Exception:
            _marken_puffer["stand"] = ""
        # Welche eigenen Symbole liegen vor? Nur die Namen - die Bilder
        # selbst holt erst die Auslieferung.
        try:
            with db.db() as con:
                _marken_puffer["symbole"] = frozenset(
                    r["name"] for r in con.execute("SELECT name FROM symbol"))
        except Exception:
            _marken_puffer["symbole"] = frozenset()
        _marken_puffer["geladen"] = True
    return _marken_puffer["stand"] or _u.get("VERSION", "")


def eigene_symbolnamen() -> frozenset:
    """Welche Favicons/App-Symbole durch eigene ersetzt sind.

    ⚠️⚠️ Der Name ist mit Bedacht sperrig. Als `eigene_symbole` wurde die
    Funktion auf der Einstellungsseite von der gleichnamigen
    KONTEXTVARIABLEN verdeckt (dort ein Dict) - base.html rief sie auf
    und bekam "'dict' object is not callable". Eine Kontextvariable
    ueberschreibt eine Jinja-Global lautlos; wer eine neue Global
    anlegt, gibt ihr einen Namen, den keine Seite als Kontext benutzt.

    ⚠️ Die Vorlage braucht das, um die ausgelieferten <link>-Zeilen
    wegzulassen. Liesse sie sie stehen, suchte der Browser sich aus den
    Groessenangaben (16, 32, 192, 512) weiter eines davon aus - und der
    Tausch saehe aus, als haette er nicht gewirkt.
    """
    markenstand()          # fuellt den Puffer, falls noetig
    return _marken_puffer["symbole"]


def marken_puffer_leeren() -> None:
    _marken_puffer.update({"stand": "", "geladen": False,
                           "symbole": frozenset()})


@router.get("/marke/{name}.svg")
def marke(name: str):
    """Liefert den Schriftzug aus - eigener aus der Datenbank, sonst der
    ausgelieferte aus app/static/.

    ⚠️ Der CSP-Kopf muss bleiben. In einem <img> ist eine SVG-Datei
    harmlos, Skript darin laeuft dort nicht; gefaehrlich ist allein der
    direkte Aufruf DIESER Adresse, denn dann ist sie ein eigenes
    Dokument. Dieselbe Regel wie bei dateien.holen().
    """
    if name not in MARKEN:
        raise HTTPException(404, "Unbekannte Marke")
    koepfe = {
        "Cache-Control": "public, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
    }
    # ⚠️ Seit 1.47 aus der Tabelle symbol, nicht mehr aus konfig (siehe
    # db.init: dort las konfig_lesen() die Logos bei jedem Seitenaufbau
    # mit). Der Name der Zeile ist der Name der Adresse.
    try:
        with db.db() as con:
            zeile = con.execute("SELECT daten FROM symbol WHERE name=?",
                                (name,)).fetchone()
    except Exception:
        zeile = None
    if zeile and zeile["daten"]:
        return Response(content=bytes(zeile["daten"]),
                        media_type="image/svg+xml", headers=koepfe)
    pfad = os.path.join(BASIS, "static", f"{name}.svg")
    try:
        with open(pfad, encoding="utf-8") as f:
            inhalt = f.read()
    except OSError:
        raise HTTPException(404, "Marke nicht gefunden")
    return Response(content=inhalt, media_type="image/svg+xml", headers=koepfe)


# --- Eigene Favicons und App-Symbole (seit 1.44) ------------------------------
#
# Dieselbe Ueberlegung wie bei den Logos, nur fuer Rasterbilder: der
# Browser-Tab und das Zeichen auf dem iOS-Homescreen lassen sich unter
# Einstellungen -> System und Sicherung -> Branding austauschen.
#
# ⚠️ Gespeichert in der Tabelle "symbol" (BLOB), NICHT in "konfig" -
# die Begruendung steht im Schema in db.py: konfig_lesen() holt bei jedem
# Seitenaufbau die ganze Tabelle.

# ⚠️ Der Schluessel heisst weiter "apple-touch-icon" - er steht so in der
# Tabelle `symbol` und im HTML. Seit 1.45 gilt dasselbe Bild auch fuer
# Android: das gerechnete /manifest.json traegt es mit seinen GEMESSENEN
# Massen ein. Es ist EIN Symbol fuer beide Wege, kein zweites Feld -
# niemand pflegt dasselbe Zeichen gern zweimal.
SYMBOLE = {
    "favicon": ("symbol_favicon", "Favicon", "Das Zeichen im Browser-Tab"),
    "apple-touch-icon": ("symbol_touch", "App-Symbol",
                         "Der Homescreen, wenn jemand die Seite dort "
                         "ablegt – auf dem iPhone wie auf Android"),
}

# Was ausgeliefert wird, wenn kein eigenes hinterlegt ist.
SYMBOL_STANDARD = {
    "favicon": ("favicon-32x32.png", "image/png"),
    "apple-touch-icon": ("apple-touch-icon.png", "image/png"),
}


@router.get("/symbol/{name}")
def symbol(name: str):
    """Liefert Favicon bzw. App-Symbol aus - eigenes, sonst das
    ausgelieferte aus app/static/.

    ⚠️ Ohne Anmeldung erreichbar (auth.SessionAuth): der Browser holt das
    Favicon auch auf dem Anmeldebildschirm, und zwar bevor es eine
    Sitzung gibt.
    """
    if name not in SYMBOLE:
        raise HTTPException(404, "Unbekanntes Symbol")
    koepfe = {
        "Cache-Control": "public, max-age=86400",
        # ⚠️ Der Inhaltstyp kommt aus unserer eigenen Pruefung, nie aus
        # dem Upload - dieselbe Regel wie in dateien.holen().
        "X-Content-Type-Options": "nosniff",
    }
    try:
        with db.db() as con:
            zeile = con.execute(
                "SELECT art, daten FROM symbol WHERE name=?", (name,)).fetchone()
    except Exception:
        zeile = None
    if zeile and zeile["daten"]:
        return Response(content=bytes(zeile["daten"]),
                        media_type=zeile["art"], headers=koepfe)
    datei, art = SYMBOL_STANDARD[name]
    try:
        with open(os.path.join(BASIS, "static", datei), "rb") as f:
            inhalt = f.read()
    except OSError:
        raise HTTPException(404, "Symbol nicht gefunden")
    return Response(content=inhalt, media_type=art, headers=koepfe)


# ⚠️ Das Manifest wird seit 1.45 GERECHNET statt statisch ausgeliefert.
# Grund: sonst gilt ein eigenes App-Symbol nur auf dem iPhone
# (apple-touch-icon steht im HTML), waehrend Android und der
# Installationsdialog des Browsers ihre Symbole aus dieser Datei holen -
# und dort staende weiter das ausgelieferte.
#
# ⚠️ Ohne Anmeldung erreichbar (auth.SessionAuth): der Browser holt das
# Manifest auch auf dem Anmeldebildschirm.
@router.get("/manifest.json")
def manifest():
    """Das Web-App-Manifest fuer Android und den Installationsdialog."""
    zeile = None
    try:
        with db.db() as con:
            zeile = con.execute(
                "SELECT art, breite, hoehe FROM symbol WHERE name=?",
                ("apple-touch-icon",)).fetchone()
    except Exception:
        zeile = None

    if zeile:
        symbol = {"src": f"/symbol/apple-touch-icon?v={markenstand()}",
                  "type": zeile["art"]}
        # ⚠️ Die Groesse steht nur da, wenn sie GEMESSEN ist. Eine
        # geratene waere gelogen: Android sucht sich das Symbol nach
        # dieser Angabe aus, und ein als "192x192" deklariertes 180er
        # Bild kaeme unscharf heraus. Wer 1.44 laufen hatte, dessen Zeile
        # traegt noch keine Masse (Spalten mit Standard 0) - dann bleibt
        # die Angabe eben weg.
        if zeile["breite"] and zeile["hoehe"]:
            symbol["sizes"] = f"{zeile['breite']}x{zeile['hoehe']}"
        symbole = [symbol]
    else:
        symbole = [
            {"src": f"/static/icon-192.png?v={_u.get('VERSION', '')}",
             "sizes": "192x192", "type": "image/png"},
            {"src": f"/static/icon-512.png?v={_u.get('VERSION', '')}",
             "sizes": "512x512", "type": "image/png"},
        ]

    # ⚠️ Der Grundton ist der des dunklen Themas (--grund). Bis 1.44 stand
    # in der statischen Datei noch #131416 - das neutrale Grau von vor
    # 1.14. Der Startbildschirm einer installierten App blitzte damit in
    # einer Farbe auf, die es im Programm nicht mehr gibt.
    return JSONResponse({
        "name": _u.get("APP_NAME", "Dein Weg Toolkit"),
        "short_name": "Dein Weg",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#17121c",
        "theme_color": "#17121c",
        "icons": symbole,
    }, headers={"Cache-Control": "public, max-age=86400"})
