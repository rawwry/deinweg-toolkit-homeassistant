"""Push-Nachrichten an einen ntfy-Server.

Zweiter Zustellweg neben der E-Mail, fuer dieselben Anlaesse. Gedacht
fuer einen selbst betriebenen ntfy-Server; ntfy.sh selbst geht genauso.

Grundgedanken:
* **Ein Thema fuer alle.** ntfy verteilt ueber Themen, nicht ueber
  Adressen - wer das Thema abonniert, bekommt die Nachricht. Eine
  Zuordnung Person -> Empfaenger wie bei der Mail gibt es hier also
  nicht, und deshalb geht je Anlass genau EINE Nachricht heraus, nicht
  eine je zustaendiger Person.
* **Keine neue Abhaengigkeit.** Verschickt wird ueber urllib aus der
  Standardbibliothek. Ein Paket mehr im Dockerfile waere fuer einen
  einzigen POST der falsche Handel (CLAUDE.md, Abschnitt 13).
* ⚠️ **Gesendet wird als JSON, nicht ueber die Kopfzeilen.** ntfy nimmt
  Titel, Prioritaet und Marken auch als HTTP-Koepfe entgegen - Koepfe
  tragen aber kein UTF-8, und ein Titel wie „Frist ueberfaellig:
  Verlaengerung LWL fuer Mueller" kaeme als Buchstabensalat an oder
  liesse den Versand mit einem Kodierungsfehler abbrechen. Der
  JSON-Weg (POST auf die Serverwurzel mit "topic" im Koerper) hat das
  Problem nicht. Nicht auf Koepfe zurueckbauen.
* Dieses Modul kennt weder die Datenbank noch die Anwendung - es
  verschickt, sonst nichts. Wann etwas verschickt wird und wie
  Doppelversand verhindert wird, steht in mail.py.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

# Standardwerte, die mail.STANDARD mit aufnimmt - die Tabelle "konfig"
# ist fuer beide Wege dieselbe.
STANDARD = {
    "ntfy_aktiv": "0",
    # ntfy.sh ist der oeffentliche Dienst; Timo betreibt einen eigenen.
    # ⚠️ Hier steht bewusst KEINE echte Adresse (CLAUDE.md, Abschnitt 2):
    # dieses Repository ist oeffentlich.
    "ntfy_server": "https://ntfy.sh",
    "ntfy_thema": "",
    "ntfy_token": "",
    "ntfy_benutzer": "",
    "ntfy_passwort": "",
}

# Wird in der Oberflaeche nie im Klartext zurueckgegeben.
GEHEIM = {"ntfy_token", "ntfy_passwort"}

# Wie lange auf den Server gewartet wird. Der Wecker laeuft in einer
# Hintergrundschleife; ein haengender Server darf sie nicht festsetzen.
ZEITSPERRE = 10

# ntfy kennt fuenf Stufen. Wir benutzen drei: was ueberfaellig ist, darf
# lauter sein als eine Erinnerung.
PRIO_HOCH = "high"
PRIO_NORMAL = "default"
PRIO_LEISE = "low"


def aktiv(k: dict) -> bool:
    """Ist der Push-Weg eingeschaltet UND vollstaendig eingerichtet?

    Ohne Server oder Thema gibt es nichts zu tun - dann soll der Wecker
    gar nicht erst einen Versand versuchen und eine Fehlerzeile ins
    Protokoll schreiben.
    """
    return bool(k.get("ntfy_aktiv") == "1"
                and (k.get("ntfy_server") or "").strip()
                and (k.get("ntfy_thema") or "").strip())


def thema(k: dict) -> str:
    return (k.get("ntfy_thema") or "").strip().strip("/")


def serveradresse(k: dict) -> str:
    """Die Serverwurzel, ohne Schraegstrich am Ende.

    Fehlt das Schema, wird https:// angenommen - „ntfy.beispiel.de" ist
    die Schreibweise, die man aus dem Kopf tippt.
    """
    roh = (k.get("ntfy_server") or "").strip().rstrip("/")
    if not roh:
        return ""
    if "://" not in roh:
        roh = "https://" + roh
    return roh


def einrichtung_pruefen(k: dict) -> str:
    """Leerer String, wenn alles passt - sonst der Grund im Klartext."""
    server = serveradresse(k)
    if not server:
        return "Es ist kein Server eingetragen."
    teile = urllib.parse.urlsplit(server)
    # ⚠️ Nur http und https. Der Wert kommt aus einem Formular und wird
    # zu einem Netzaufruf des Servers - ein „file://" oder „gopher://"
    # hat hier nichts zu suchen.
    if teile.scheme not in ("http", "https") or not teile.netloc:
        return "Die Serveradresse muss mit http:// oder https:// beginnen."
    if not thema(k):
        return "Es ist kein Thema eingetragen."
    return ""


def senden(k: dict, titel: str, text: str,
           prioritaet: str = PRIO_NORMAL,
           marken: tuple[str, ...] = ()) -> tuple[bool, str]:
    """Verschickt eine Push-Nachricht. Gibt (Erfolg, Meldung) zurueck.

    ⚠️ Wirft nie - der Wecker laeuft im Hintergrund, und ein nicht
    erreichbarer Server darf die uebrigen Anlaesse nicht mitreissen.
    Dieselbe Regel wie bei mail.senden().
    """
    problem = einrichtung_pruefen(k)
    if problem:
        return False, problem

    koerper = {
        "topic": thema(k),
        "title": titel,
        "message": text,
        "priority": prioritaet,
    }
    if marken:
        koerper["tags"] = list(marken)

    daten = json.dumps(koerper).encode("utf-8")
    anfrage = urllib.request.Request(
        serveradresse(k), data=daten, method="POST",
        headers={"Content-Type": "application/json"})

    # Zugang: ein Zugriffstoken hat Vorrang, sonst Benutzername und
    # Passwort. Ein oeffentliches Thema braucht beides nicht.
    token = (k.get("ntfy_token") or "").strip()
    benutzer = (k.get("ntfy_benutzer") or "").strip()
    passwort = k.get("ntfy_passwort") or ""
    if token:
        anfrage.add_header("Authorization", f"Bearer {token}")
    elif benutzer:
        roh = f"{benutzer}:{passwort}".encode("utf-8")
        anfrage.add_header(
            "Authorization", "Basic " + base64.b64encode(roh).decode("ascii"))

    try:
        with urllib.request.urlopen(anfrage, timeout=ZEITSPERRE) as antwort:
            if 200 <= antwort.status < 300:
                return True, ""
            return False, f"Der Server antwortete mit {antwort.status}."
    except urllib.error.HTTPError as e:
        # ntfy schreibt den Grund in den Koerper - der ist brauchbarer als
        # „HTTP 403".
        try:
            grund = e.read().decode("utf-8", "replace").strip()[:200]
        except Exception:
            grund = ""
        return False, f"HTTP {e.code}{': ' + grund if grund else ''}"
    except Exception as e:
        # Auch Zeitueberschreitung, Namensaufloesung und Zertifikatsfehler
        # landen hier. Der Klartext hilft beim Einrichten mehr als der
        # Ausnahmetyp.
        return False, f"{type(e).__name__}: {e}"
