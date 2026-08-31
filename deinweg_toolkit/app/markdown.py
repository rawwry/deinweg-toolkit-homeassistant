"""Kleiner Markdown-Wandler fuer das Wiki.

Bewusst selbst geschrieben statt eine Bibliothek einzubinden: die App
laedt zur Laufzeit nichts nach und kommt ohne Zusatzpakete aus, und der
gebrauchte Umfang ist ueberschaubar - Ueberschriften, Absaetze, Listen
(auch verschachtelt und mit Haekchen), Tabellen, Codebloecke, Zitate,
Trennlinien, Links, Bilder und die ueblichen Auszeichnungen.

Sicherheit: der gesamte Text wird zuerst entschaerft (escape). HTML aus
einer Wiki-Datei wird also NICHT durchgereicht, sondern als Text
angezeigt. Das ist Absicht - eine Wiki-Seite darf jeder Angemeldete
bearbeiten, und ohne diese Grenze waere ein <script> darin sofort
ausfuehrbar. Damit ist das Wiki bewusst strenger als strings.txt, wo
einfaches HTML erlaubt ist: strings.txt liegt nur auf der NAS, eine
Wiki-Seite schreibt man im Browser.
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

# --- Muster -----------------------------------------------------------------

_UEBERSCHRIFT = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_TRENNER = re.compile(r"^\s{0,3}([-*_])\s*(?:\1\s*){2,}$")
_ZITAT = re.compile(r"^\s{0,3}>\s?(.*)$")
_ZAUN = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*[\w+#.-]*\s*$")
_AUFZAEHLUNG = re.compile(r"^(\s*)([*+-]|\d{1,9}[.)])[ \t]+(.*)$")
_HAEKCHEN = re.compile(r"^\[([ xX])\]\s+(.*)$")

# Nach dem Entschaerfen stehen Anfuehrungszeichen als Entitaet da. Fuer die
# Adresse eines Links wird der Rohwert wieder gebraucht (er geht durch die
# Aufloesung des Ziels und wird danach neu entschaerft).
_ZURUECK = (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
            ("&#34;", '"'), ("&#39;", "'"))


def _roh(text: str) -> str:
    for entitaet, zeichen in _ZURUECK:
        text = text.replace(entitaet, zeichen)
    return text


_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "Ä": "ae", "Ö": "oe", "Ü": "ue"}


def sprungmarke(titel: str, vergeben: set | None = None) -> str:
    """Macht aus einer Ueberschrift eine Kennung fuer den Seitenanker.

    Emojis, Satzzeichen und Umlaute fliegen raus - uebrig bleibt etwas,
    das man auch von Hand in eine Adresse tippen koennte.
    """
    text = "".join(_UMLAUTE.get(z, z) for z in titel).lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = text or "abschnitt"
    if vergeben is None:
        return text
    marke, nr = text, 2
    while marke in vergeben:
        marke, nr = f"{text}-{nr}", nr + 1
    vergeben.add(marke)
    return marke


def _einzug(zeile: str) -> int:
    ohne = zeile.expandtabs(4)
    return len(ohne) - len(ohne.lstrip(" "))


def _abruecken(zeile: str, anzahl: int) -> str:
    """Nimmt bis zu 'anzahl' fuehrende Leerzeichen weg."""
    zeile = zeile.expandtabs(4)
    weg = 0
    while weg < anzahl and zeile[weg:weg + 1] == " ":
        weg += 1
    return zeile[weg:]


def _zellen(zeile: str) -> list[str]:
    z = zeile.strip()
    if z.startswith("|"):
        z = z[1:]
    if z.endswith("|") and not z.endswith("\\|"):
        z = z[:-1]
    return [t.strip() for t in re.split(r"(?<!\\)\|", z)]


def _ist_tabellenstrich(zeile: str) -> bool:
    if "|" not in zeile or not zeile.strip():
        return False
    teile = _zellen(zeile)
    if len(teile) < 2:
        return False
    return all(re.fullmatch(r":?-{1,}:?", t) for t in teile)


def _ausrichtung(zeile: str) -> list[str]:
    """Spaltenklassen aus dem Trennstrich - nutzt die vorhandenen
    Hilfsklassen aus style.css."""
    klassen = []
    for t in _zellen(zeile):
        links, rechts = t.startswith(":"), t.endswith(":")
        klassen.append("mitte" if links and rechts else
                       "rechts" if rechts else "")
    return klassen


# --- Auszeichnungen innerhalb einer Zeile ------------------------------------

def haken(gesetzt: bool) -> str:
    """Das Kaestchen einer Aufgabe.

    Bewusst kein <input type="checkbox">: ein abgeschaltetes Kaestchen
    malen Browser grau, die Akzentfarbe kaeme nie durch. Ein eigenes
    Element laesst sich dagegen vollstaendig gestalten - und es ist
    ehrlicher, denn anklicken kann man es ohnehin nicht.
    """
    klasse = "wiki-haken an" if gesetzt else "wiki-haken"
    wort = "erledigt" if gesetzt else "offen"
    return f'<span class="{klasse}" role="img" aria-label="{wort}"></span>'


def _inline(text: str, aufloesen) -> str:
    ablage: list[str] = []

    def merken(html: str) -> str:
        ablage.append(html)
        return f"\x00{len(ablage) - 1}\x00"

    roh = str(escape(text))

    # Code zuerst: was darin steht, wird nicht weiter ausgezeichnet.
    roh = re.sub(r"(`+)(.+?)\1",
                 lambda m: merken(f"<code>{m.group(2).strip()}</code>"),
                 roh)

    def ziel(adresse: str) -> tuple[str, bool]:
        adresse = _roh(adresse).strip()
        # Ein Titel in Anfuehrungszeichen hinter der Adresse wird verworfen.
        adresse = re.split(r'\s+["\']', adresse, maxsplit=1)[0]
        if aufloesen:
            return aufloesen(adresse)
        return adresse, True

    def bild(m):
        adresse, _extern = ziel(m.group(2))
        return merken(f'<img src="{escape(adresse)}" alt="{m.group(1)}">')

    roh = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", bild, roh)

    def link(m):
        adresse, extern = ziel(m.group(2))
        zusatz = ' target="_blank" rel="noopener noreferrer"' if extern else ""
        inhalt = _auszeichnen(m.group(1))
        return merken(f'<a href="{escape(adresse)}"{zusatz}>{inhalt}</a>')

    roh = re.sub(r"\[([^\]]*)\]\(([^)]+)\)", link, roh)

    # Erst nach den Links, sonst wuerde [x](ziel) zerlegt. Was in
    # Codeauszeichnung steht, liegt bereits als Platzhalter in der Ablage
    # und bleibt unberuehrt.
    roh = re.sub(r"\[([ xX])\](?!\()",
                 lambda m: merken(haken(m.group(1).lower() == "x")), roh)

    roh = _auszeichnen(roh)

    # Nackte Adressen verlinken. Gefahrlos erst hier: fertige Links liegen
    # bereits als Platzhalter in der Ablage und koennen nicht getroffen werden.
    roh = re.sub(
        r"(?<![\w])(https?://[^\s<>()\[\]]+)",
        lambda m: merken('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                         % (m.group(1), m.group(1))),
        roh)
    # Dasselbe fuer E-Mail-Adressen: in den Stammblaettern stehen sie als
    # blosser Text, sollen aber anklickbar sein.
    roh = re.sub(
        r"(?<![\w.@+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*"
        r"\.[A-Za-z]{2,})(?![\w@-])",
        lambda m: merken('<a href="mailto:%s">%s</a>' % (m.group(1), m.group(1))),
        roh)

    def zurueck(m):
        return ablage[int(m.group(1))]

    # Mehrfach aufloesen: ein Link kann Code enthalten.
    for _ in range(4):
        neu = re.sub(r"\x00(\d+)\x00", zurueck, roh)
        if neu == roh:
            break
        roh = neu
    return roh


def _auszeichnen(text: str) -> str:
    text = re.sub(r"\*\*\*(?!\s)(.+?)(?<!\s)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w_])__(?!\s)(.+?)(?<!\s)__(?![\w_])", r"<strong>\1</strong>", text)
    text = re.sub(r"~~(?!\s)(.+?)(?<!\s)~~", r"<del>\1</del>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    # Unterstriche nur zwischen Wortgrenzen, sonst zerlegt es Dateinamen
    # wie 01_notfall_und_krisen.
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", text)
    return text


# --- Bloecke ----------------------------------------------------------------

def _ist_blockanfang(zeile: str, zeilen: list[str], i: int) -> bool:
    if not zeile.strip():
        return True
    if (_UEBERSCHRIFT.match(zeile) or _TRENNER.match(zeile)
            or _ZAUN.match(zeile) or _ZITAT.match(zeile)
            or _AUFZAEHLUNG.match(zeile)):
        return True
    if ("|" in zeile and i + 1 < len(zeilen)
            and _ist_tabellenstrich(zeilen[i + 1])):
        return True
    return False


def _absatz(zeilen: list[str], aufloesen) -> str:
    # Jeder Zeilenumbruch im Quelltext ist auch einer in der Anzeige.
    # Klassisches Markdown wuerfe ihn weg und liesse den Absatz
    # durchlaufen; wer im Wiki eine Anschrift oder eine kurze Aufstellung
    # tippt, meint aber genau die Zeilen, die er sieht. Die alten Wege
    # (zwei Leerzeichen oder ein Rueckstrich am Zeilenende) funktionieren
    # weiterhin, sie sind jetzt nur nicht mehr noetig.
    teile = []
    for nr, z in enumerate(zeilen):
        teile.append(_inline(z.rstrip("\\").strip(), aufloesen)
                     + ("<br>" if nr < len(zeilen) - 1 else ""))
    return "\n".join(teile)


def _tabelle(zeilen: list[str], start: int, aufloesen) -> tuple[str, int]:
    kopf = _zellen(zeilen[start])
    klassen = _ausrichtung(zeilen[start + 1])
    i = start + 2
    koerper = []
    while i < len(zeilen) and zeilen[i].strip() and "|" in zeilen[i]:
        koerper.append(_zellen(zeilen[i]))
        i += 1

    def zelle(marke: str, text: str, nr: int) -> str:
        klasse = klassen[nr] if nr < len(klassen) else ""
        raum = f' class="{klasse}"' if klasse else ""
        return f"<{marke}{raum}>{_inline(text, aufloesen)}</{marke}>"

    html = ['<div class="wiki-tabellenrolle"><table class="wiki-tabelle"><thead><tr>']
    html += [zelle("th", t, nr) for nr, t in enumerate(kopf)]
    html.append("</tr></thead><tbody>")
    for reihe in koerper:
        html.append("<tr>")
        html += [zelle("td", t, nr) for nr, t in enumerate(reihe)]
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html), i


def _liste(zeilen: list[str], start: int, aufloesen) -> tuple[str, int]:
    erste = _AUFZAEHLUNG.match(zeilen[start])
    basis = _einzug(zeilen[start])
    geordnet = erste.group(2)[-1] in ".)"
    beginn = erste.group(2)[:-1] if geordnet else ""
    n = len(zeilen)
    posten: list[list[str]] = []
    i = start

    while i < n:
        z = zeilen[i]
        if not z.strip():
            # Leerzeile gehoert noch zur Liste, wenn danach ein weiterer
            # Punkt oder eingerueckter Text folgt.
            j = i
            while j < n and not zeilen[j].strip():
                j += 1
            weiter = j < n and (
                _einzug(zeilen[j]) > basis
                or (_AUFZAEHLUNG.match(zeilen[j]) and _einzug(zeilen[j]) >= basis))
            if not weiter:
                break
            if posten:
                posten[-1].append("")
            i = j
            continue

        treffer = _AUFZAEHLUNG.match(z)
        ein = _einzug(z)
        if treffer and ein <= basis + 1:
            posten.append([treffer.group(3)])
            i += 1
            continue
        if ein > basis and posten:
            posten[-1].append(_abruecken(z, basis + 2))
            i += 1
            continue
        break

    marke = "ol" if geordnet else "ul"
    auf = f'<{marke} start="{beginn}">' if geordnet and beginn not in ("1", "") \
        else f"<{marke}>"
    html = [auf]
    for inhalt in posten:
        klasse = ""
        vorne = ""
        treffer_haken = _HAEKCHEN.match(inhalt[0])
        if treffer_haken:
            klasse = ' class="aufgabe"'
            vorne = haken(treffer_haken.group(1).lower() == "x") + " "
            inhalt = [treffer_haken.group(2)] + inhalt[1:]
        teile = _bloecke(inhalt, aufloesen)
        # Enge Liste: solange im Punkt keine Leerzeile steht, kommt der Text
        # ohne eigenen Absatz aus - sonst stehen die Punkte weit auseinander.
        if teile and teile[0].startswith("<p>") and "" not in inhalt:
            teile[0] = teile[0][3:-4]
        html.append(f"<li{klasse}>{vorne}" + "\n".join(teile) + "</li>")
    html.append(f"</{marke}>")
    return "\n".join(html), i


def _bloecke(zeilen: list[str], aufloesen, verzeichnis=None,
             _vergeben=None) -> list[str]:
    ergebnis: list[str] = []
    i, n = 0, len(zeilen)
    while i < n:
        zeile = zeilen[i]
        if not zeile.strip():
            i += 1
            continue

        if _ZAUN.match(zeile):
            zeichen = zeile.strip()[0]
            i += 1
            inhalt = []
            while i < n and not re.match(r"^\s{0,3}" + re.escape(zeichen) + r"{3,}\s*$",
                                         zeilen[i]):
                inhalt.append(zeilen[i])
                i += 1
            i += 1
            ergebnis.append("<pre><code>"
                            + str(escape("\n".join(inhalt)))
                            + "</code></pre>")
            continue

        if _TRENNER.match(zeile):
            ergebnis.append("<hr>")
            i += 1
            continue

        ueber = _UEBERSCHRIFT.match(zeile)
        if ueber:
            stufe = len(ueber.group(1))
            text = _inline(ueber.group(2), aufloesen)
            marke = ""
            if verzeichnis is not None:
                marke = sprungmarke(ueber.group(2), _vergeben)
                # Auszeichnungszeichen wie ** oder ` gehoeren nicht ins
                # Inhaltsverzeichnis, dort steht nur der Klartext.
                klartext = re.sub(r"[*`_~]", "", ueber.group(2)).strip()
                verzeichnis.append({"stufe": stufe, "titel": klartext,
                                    "marke": marke})
            kennung = f' id="{marke}"' if marke else ""
            ergebnis.append(f"<h{stufe}{kennung}>{text}</h{stufe}>")
            i += 1
            continue

        if _ZITAT.match(zeile):
            innen = []
            while i < n and _ZITAT.match(zeilen[i]):
                innen.append(_ZITAT.match(zeilen[i]).group(1))
                i += 1
            ergebnis.append("<blockquote>"
                            + "\n".join(_bloecke(innen, aufloesen))
                            + "</blockquote>")
            continue

        if "|" in zeile and i + 1 < n and _ist_tabellenstrich(zeilen[i + 1]):
            html, i = _tabelle(zeilen, i, aufloesen)
            ergebnis.append(html)
            continue

        if _AUFZAEHLUNG.match(zeile):
            html, i = _liste(zeilen, i, aufloesen)
            ergebnis.append(html)
            continue

        absatz = []
        while i < n and not _ist_blockanfang(zeilen[i], zeilen, i):
            absatz.append(zeilen[i])
            i += 1
        if absatz:
            ergebnis.append("<p>" + _absatz(absatz, aufloesen) + "</p>")
        else:
            # Sicherheitsnetz: nie stehen bleiben, sonst laeuft die
            # Schleife endlos.
            i += 1
    return ergebnis


_UEBER_BLOCK = re.compile(r"^<h([2-6])(\s[^>]*)?>(.*)</h\1>$", re.S)


def _faltbar(bloecke: list[str]) -> list[str]:
    """Jede Überschrift ab Stufe 2 bekommt ihren Abschnitt als <details>.

    Damit lässt sich ein Kapitel samt Inhalt zuklappen - bei einem
    Stammblatt mit fünfzehn Abschnitten der einzige Weg, den einen zu
    finden, um den es gerade geht.

    ⚠️ Die Überschrift bleibt UNVERÄNDERT im <summary> stehen, mit ihrer
    Kennung. Sonst liefe jede Sprungmarke aus "Auf dieser Seite" ins
    Leere. Erlaubt ist das ausdrücklich: ein <summary> darf genau ein
    Überschriftenelement enthalten.

    Aufgeklappt ist der Anfangszustand - eine Seite, die zugeklappt
    beginnt, sieht aus, als fehlte ihr Inhalt.
    """
    ergebnis: list[str] = []
    # Je offener Abschnitt seine Stufe und die Liste, in die gerade
    # geschrieben wird.
    stapel: list[tuple[int, list[str]]] = []

    def ziel() -> list[str]:
        return stapel[-1][1] if stapel else ergebnis

    def schliessen(bis_stufe: int) -> None:
        while stapel and stapel[-1][0] >= bis_stufe:
            stapel.pop()

    for block in bloecke:
        treffer = _UEBER_BLOCK.match(block.strip())
        if not treffer:
            ziel().append(block)
            continue
        stufe = int(treffer.group(1))
        schliessen(stufe)
        innen: list[str] = []
        aussen = ziel()
        aussen.append('<details class="wiki-falt" open>')
        aussen.append(f'<summary class="wiki-falt-kopf">{block}</summary>')
        aussen.append('<div class="wiki-falt-inhalt">')
        aussen.append(innen)          # Platzhalter, unten aufgelöst
        aussen.append("</div></details>")
        stapel.append((stufe, innen))

    # Die verschachtelten Listen zu einer flachen Zeichenkette machen.
    def flach(teile) -> list[str]:
        raus = []
        for t in teile:
            raus.extend(flach(t) if isinstance(t, list) else [t])
        return raus

    return flach(ergebnis)


def zu_html(text: str, aufloesen=None, verzeichnis=None,
            faltbar: bool = False) -> Markup:
    """Wandelt Markdown in HTML.

    'aufloesen' bekommt die Adresse eines Links und gibt (Adresse, extern)
    zurueck. Damit traegt das Wiki seine eigenen Pfade nach, ohne dass
    dieses Modul etwas ueber Wiki-Ordner wissen muss.

    Mit 'faltbar' wird jeder Abschnitt ab Ueberschriftstufe 2 in ein
    <details> gepackt und laesst sich damit zuklappen.

    Wird eine Liste als 'verzeichnis' uebergeben, sammelt sie die
    Ueberschriften der Seite (Stufe, Titel, Sprungmarke) - daraus baut das
    Wiki sein "Auf dieser Seite". Nur dann bekommen die Ueberschriften
    ueberhaupt eine Kennung, sonst bleibt das HTML so schlank wie bisher.
    """
    zeilen = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    bloecke = _bloecke(zeilen, aufloesen, verzeichnis, set())
    if faltbar:
        bloecke = _faltbar(bloecke)
    return Markup("\n".join(bloecke))
