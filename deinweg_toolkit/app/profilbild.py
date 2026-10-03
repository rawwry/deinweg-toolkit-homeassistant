"""Profilbilder (seit 2.0, Timos Wunsch).

Jedes Konto kann sich ein eigenes Bild hochladen; es erscheint statt des
Kuerzels im runden Feld der Kopfzeile, im Kontomenue, im Blatt am Telefon
und oben in „Mein Bereich".

⚠️⚠️ Gespeichert in der VORHANDENEN Tabelle ``symbol`` als Zeile
``profil-<benutzer_id>`` - keine neue Tabelle, keine neue Spalte. Diese
Stage darf das Schema nicht anfassen (CLAUDE.md, Stage 7), und die Tabelle
hat genau die Form, die es braucht (Name, Inhaltstyp, BLOB, Zeitpunkt).
Sie liegt damit auch in jeder Sicherung mit drin.
⚠️ Die beiden oeffentlichen Adressen derselben Tabelle (``/marke/`` und
``/symbol/``) liefern nur ihre festen Namen aus (MARKEN bzw. SYMBOLE) - ein
Profilbild ist darueber NICHT ohne Anmeldung erreichbar. Die Abfragen dort,
die alle Namen lesen, fragen nur ab, ob ein bestimmter Name dabei ist; eine
Zeile mehr stoert sie nicht.

- Ausgeliefert nur an Angemeldete (``/profilbild/…`` ist kein oeffentlicher
  Pfad), mit Inhaltstyp aus unserer eigenen Pruefung und ``nosniff``.
- Erkannt an den ersten Bytes, nicht an der Endung: PNG, JPEG, WebP.
  ⚠️ Kein SVG - das waere ein eigenes Dokument und braeuchte Sandbox und
  Skriptpruefung wie die Logos.
- ⚠️ Das Skript in „Mein Bereich" schneidet das Bild VOR dem Hochladen
  quadratisch zu und verkleinert es auf 256px (Canvas). Der Server
  verkleinert nichts - dafuer braeuchte es eine Bildbibliothek im
  Dockerfile (Abschnitt 13). Ohne Skript geht das Original hinauf, bis
  MAX_BYTES.
- Wird ein Konto geloescht, geht sein Bild mit (``entfernen``) - sonst
  erbte ein neues Konto mit derselben Nummer das Bild.

Importiert nur ``db`` - kein Ringschluss.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response

from . import db

router = APIRouter()

MAX_BYTES = 2 * 1024 * 1024


def name_fuer(benutzer_id: int) -> str:
    return f"profil-{int(benutzer_id)}"


def art_erkennen(daten: bytes) -> str:
    """Inhaltstyp aus den ersten Bytes, leer bei allem anderen."""
    if daten.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if daten.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(daten) > 12 and daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
        return "image/webp"
    return ""


def stand(con, benutzer_id: int) -> str:
    """Zeitpunkt des Bildes als Ziffernfolge (fuer ``?v=``), leer ohne Bild.

    ⚠️ Der Anhang muss sich beim Tausch aendern, sonst haengt der Browser
    am alten Bild - dieselbe Falle wie beim Grafiktausch in 1.27.
    """
    zeile = con.execute("SELECT geaendert_am FROM symbol WHERE name=?",
                        (name_fuer(benutzer_id),)).fetchone()
    return re.sub(r"\D", "", zeile["geaendert_am"]) if zeile else ""


def adresse(con, benutzer_id: int) -> str:
    s = stand(con, benutzer_id)
    return f"/profilbild/{int(benutzer_id)}?v={s}" if s else ""


def entfernen(con, benutzer_id: int) -> None:
    con.execute("DELETE FROM symbol WHERE name=?", (name_fuer(benutzer_id),))


def _zurueck(**werte):
    # Zurueck auf „Mein Konto" - dort steht die Meldung oben und das Bild
    # direkt darunter, man sieht sofort, dass es gewirkt hat.
    return RedirectResponse("/meinbereich/konto?" + urlencode(werte), status_code=303)


@router.get("/profilbild/{benutzer_id}")
def ausliefern(benutzer_id: int):
    with db.db() as con:
        zeile = con.execute("SELECT art, daten FROM symbol WHERE name=?",
                            (name_fuer(benutzer_id),)).fetchone()
    if not zeile or not zeile["daten"]:
        raise HTTPException(404, "Kein Profilbild")
    return Response(content=bytes(zeile["daten"]), media_type=zeile["art"],
                    headers={"X-Content-Type-Options": "nosniff",
                             # Die Adresse traegt ?v=<Stand>, ein Tausch
                             # ergibt also eine neue - darum darf lange
                             # gepuffert werden. „private": es ist ein
                             # Personenbild, kein Bestandteil der Marke.
                             "Cache-Control": "private, max-age=2592000"})


@router.post("/meinbereich/profilbild")
async def speichern(request: Request, bild: UploadFile | None = File(None),
                    entfernen_: str = Form("", alias="entfernen")):
    benutzer_id = request.state.benutzer["id"]
    if entfernen_:
        with db.db() as con:
            entfernen(con, benutzer_id)
        return _zurueck(hinweis="Profilbild entfernt.")
    daten = await bild.read(MAX_BYTES + 1) if bild is not None else b""
    if not daten:
        return _zurueck(fehler="Bitte ein Bild auswählen.")
    if len(daten) > MAX_BYTES:
        return _zurueck(fehler="Das Bild ist größer als 2 MB.")
    art = art_erkennen(daten)
    if not art:
        return _zurueck(fehler="Bitte ein Foto als JPG, PNG oder WebP hochladen.")
    jetzt = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db.db() as con:
        con.execute(
            "INSERT INTO symbol (name, art, daten, breite, hoehe, geaendert_am) "
            "VALUES (?, ?, ?, 0, 0, ?) ON CONFLICT(name) DO UPDATE SET "
            "art=excluded.art, daten=excluded.daten, geaendert_am=excluded.geaendert_am",
            (name_fuer(benutzer_id), art, daten, jetzt))
    return _zurueck(hinweis="Profilbild gespeichert.")
