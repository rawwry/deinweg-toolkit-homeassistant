"""Eingebaute Standardtexte der Oberflaeche.

Greifen immer dann, wenn ein Schluessel in strings.txt fehlt. Die
Pflege zur Laufzeit laeuft ueber strings.txt, siehe main.texte().
Ausgelagert aus main.py, weil es reine Daten sind.
"""

from __future__ import annotations

import os
import re

TEXTE_STANDARD: dict[str, str] = {}

# --- Das Dateiformat von strings.txt -----------------------------------------
#
# ⚠️⚠️ Lesen und Schreiben stehen seit 1.35 HIER und nirgends sonst.
# Vorher gab es zwei Fassungen, die verschiedene Formate meinten:
# main.texte() las Bloecke ("[schluessel]" in einer Zeile, der Text
# darunter), einstellungen.texte_nachziehen() las und schrieb dagegen
# "schluessel = wert" je Zeile. Folge: der Knopf "Fehlende Texte
# ergaenzen" fand in einer echten strings.txt keinen einzigen Schluessel,
# hielt sie fuer leer und schrieb sie komplett im anderen Format neu -
# eigene Formulierungen weg, und die Datei danach fuer main.texte()
# unlesbar. Der Knopf, der die eigenen Texte gerade retten sollte, hat
# sie zerstoert. Beide Wege gehen jetzt durch dieselben zwei Funktionen.

KOPFZEILEN = [
    "# Texte der Oberfläche. Änderungen wirken sofort, ohne Neustart.",
    "# Aufbau: [schluessel] in eckigen Klammern, darunter der Text.",
    "# Ein Text darf über mehrere Zeilen gehen, Umbrüche werden zu Leerzeichen.",
    "# Einfaches HTML wie <strong> oder <a href=\"...\"> ist erlaubt.",
    "# Geschweifte Klammern wie {zeitraum} sind Platzhalter und bleiben stehen.",
    "# Wird ein Schlüssel gelöscht, greift wieder der eingebaute Standardtext.",
    "",
]


def datei_lesen(pfad: str) -> dict[str, str]:
    """Liest strings.txt. Fehlt sie oder ist sie unlesbar, kommt {} zurueck.

    ⚠️ Zeilen der alten Form "schluessel = wert" werden mitgelesen. Wer
    vor 1.35 einmal auf "Fehlende Texte ergaenzen" gedrueckt hat, hat eine
    Datei in genau dieser Form; ohne die Nachsicht hier waeren seine Texte
    endgueltig verloren, obwohl sie noch dastehen.
    """
    werte: dict[str, str] = {}
    schluessel = None
    teile: list[str] = []
    try:
        with open(pfad, encoding="utf-8") as f:
            for zeile in f:
                roh = zeile.rstrip("\n")
                if roh.startswith("#") and schluessel is None:
                    continue
                kopf = re.fullmatch(r"\[([\w.]+)\]\s*", roh)
                if kopf:
                    if schluessel:
                        werte[schluessel] = " ".join(" ".join(teile).split())
                    schluessel, teile = kopf.group(1), []
                    continue
                if schluessel is None:
                    alt = re.fullmatch(r"([\w.]+)\s*=\s*(.*)", roh)
                    if alt:
                        werte[alt.group(1)] = alt.group(2).strip()
                    continue
                teile.append(roh)
        if schluessel:
            werte[schluessel] = " ".join(" ".join(teile).split())
    except OSError:
        return {}
    return werte


def datei_schreiben(pfad: str, werte: dict[str, str]) -> None:
    """Schreibt strings.txt im Blockformat. Wirft OSError weiter."""
    zeilen = list(KOPFZEILEN)
    # Die Reihenfolge der Standardtexte zuerst, alles Uebrige hinten dran -
    # so bleibt die Datei lesbar, auch wenn jemand einen eigenen
    # Schluessel ergaenzt hat.
    reihenfolge = ([k for k in TEXTE_STANDARD if k in werte]
                   + [k for k in werte if k not in TEXTE_STANDARD])
    for schluessel in reihenfolge:
        zeilen.append(f"[{schluessel}]")
        zeilen.append(werte[schluessel])
        zeilen.append("")
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen))

TEXTE_STANDARD["start.kein_team"] = (
    "Es ist noch niemand im Team eingetragen. <a "
    "href=\"/einstellungen?bereich=mitarbeiter\">Mitarbeitende "
    "anlegen</a>.")
TEXTE_STANDARD["start.vorschau_offen"] = (
    "Diese Dateien sind eingelesen, aber noch nicht gespeichert. Öffne "
    "die Vorschau, prüf die Zeilen und übernimm sie – oder verwirf sie.")
TEXTE_STANDARD["start.upload_name"] = (
    "Der gewählte Name gilt für alle Zeilen der Datei, auch wenn die "
    "Datei selbst eine Spalte mit Namen mitbringt.")
TEXTE_STANDARD["start.upload"] = (
    "Exporte aus Working Hours oder vergleichbare Listen als .xlsx oder .csv hochladen. Vor dem Speichern siehst du eine Vorschau mit allen Dopplungen oder anderen Fuckups.")
# ⚠️ Neuer Schlüssel statt geänderter Text: eine vorhandene strings.txt
# gewinnt gegen jeden Standardtext, unter „erfassung.lead" wäre der neue
# Wortlaut also nie angekommen (Abschnitt 8). Der alte Text nannte
# Working Hours und Listen - beides hat mit der Erfassung von Hand
# nichts zu tun.
TEXTE_STANDARD["erfassung.einleitung"] = (
    "Hier trägst du deine Betreuungszeiten direkt ein. Datum und Name "
    "bleiben stehen, bis du sie änderst. Mit „Weitere Zeile“ legst du "
    "mehrere Einträge an und speicherst sie gemeinsam.")
TEXTE_STANDARD["start.upload_kurz"] = (
    "Exporte als .xlsx oder .csv – zum Aufklappen")
# ⚠️ Wieder ein neuer Schlüssel und kein geänderter Text: eine vorhandene
# strings.txt gewinnt gegen jeden Standardtext (Abschnitt 8). Der Satz
# steht seit 1.24 im zugeklappten Kopf der Importkarte und beantwortet
# die Frage, die dort als Erstes aufkommt - „betrifft mich das?“.
TEXTE_STANDARD["erfassung.fremd"] = (
    "Die Zeiten werden dann vollständig der gewählten Person zugerechnet:"
    " Sie erscheinen in deren Auswertung und zählen für deren "
    "Monatsabgabe. Nutze das nur, wenn du wirklich für jemand anderen "
    "erfasst.")
TEXTE_STANDARD["import.einleitung"] = (
    "Hier kannst du Zeiten aus einem anderen Zeiterfassungsprogramm wie "
    "Working Hours einlesen. Wenn du deine Zeiten direkt hier im Toolkit "
    "erfasst, brauchst du diesen Bereich nicht.")
TEXTE_STANDARD["erfassung.leer"] = (
    "Noch nichts von Hand erfasst für {mitarbeiter}.")
# Das Tagesprotokoll ueber den Eingabezeilen (seit 1.43).
TEXTE_STANDARD["erfassung.titel.protokoll"] = "Bereits von dir erfasst"
TEXTE_STANDARD["erfassung.protokoll_leer"] = (
    "Für diesen Tag hast du noch nichts erfasst.")
# Tagesvorlagen (seit 1.59).
TEXTE_STANDARD["erfassung.vorlagen_leer"] = (
    "Du hast noch keine Vorlage. Vorlagen legst du in „Mein Bereich“ an; "
    "danach lädst du sie hier mit einem Klick.")
TEXTE_STANDARD["erfassung.vorlage_tag"] = (
    "Speichert die Zeilen dieses Tages als Vorlage, ohne Datum. Lädst du "
    "die Vorlage später, füllt sie nur das Formular – gespeichert wird "
    "erst, wenn du die Einträge speicherst.")
TEXTE_STANDARD["datensaetze.leer"] = (
    "Für diese Filtereinstellung gibt es keine Einträge.")
TEXTE_STANDARD["auswertung.soll_erklaerung"] = (
    "Das Soll eines Monats sind die bewilligten Stunden pro Woche × 52 "
    "Wochen ÷ 12 Monate. Bei 3 Stunden pro Woche sind das 13:00 Stunden "
    "im Monat. Ein Zeitraum, der erst beantragt ist, zählt hier noch "
    "nicht. Die Bescheide pflegst du unter <a "
    "href=\"/einstellungen?bereich=betreute\">Betreute Personen</a>.")
TEXTE_STANDARD["auswertung.soll_fehlt"] = (
    "Für die gezeigten Personen ist kein Bewilligungszeitraum "
    "eingetragen, deshalb gibt es kein Soll zum Vergleichen. Trag die "
    "Bescheide unter <a href=\"/einstellungen?bereich=betreute\">Betreute"
    " Personen</a> ein.")
TEXTE_STANDARD["auswertung.gestaffelt"] = (
    "Bei mindestens einer Person haben sich die Stunden pro Woche oder "
    "der Stundensatz im gewählten Zeitraum geändert. Dann wird jeder "
    "Monat mit den Werten gerechnet, die in diesem Monat galten.")
TEXTE_STANDARD["auswertung.monate_lead"] = (
    "Unter „Monat für Monat“ wird jeder Monat mit den Stunden und dem "
    "Stundensatz gerechnet, die in genau diesem Monat bewilligt waren. "
    "Auch Monate ohne erfasste Zeiten stehen dort, solange etwas "
    "bewilligt war – so fallen Lücken auf.")
TEXTE_STANDARD["auswertung.monatsliste_lead"] = (
    "Jede Säule im Diagramm steht für einen Monat. Der gefüllte Teil "
    "zeigt die geleisteten Stunden, der gestrichelte Rahmen das Soll für "
    "diesen Monat. Fährst du mit der Maus über eine Säule, siehst du die "
    "genauen Werte. Darunter steht jeder Monat als eigene Zeile: Ein "
    "Klick darauf – oder auf eine Säule – zeigt, wie sich die Stunden auf"
    " die betreuten Personen verteilen.")
TEXTE_STANDARD["auswertung.bewilligt_lead"] = (
    "Die Bescheide, die den gewählten Zeitraum berühren.")
TEXTE_STANDARD["auswertung.monat_leer"] = (
    "In diesem Monat wurde nichts erfasst, obwohl Stunden bewilligt "
    "waren.")
TEXTE_STANDARD["auswertung.tabelle_leer"] = (
    "Für {zeitraum} sind keine Zeiten erfasst.")
TEXTE_STANDARD["auswertung.stand_lead"] = (
    "Hier siehst du für jede betreute Person, ob die bewilligten Stunden "
    "bis heute erbracht wurden. Grundlage ist immer der Bescheid, der "
    "heute gilt. Klickst du auf eine Person, siehst du die Entwicklung "
    "Monat für Monat.")
TEXTE_STANDARD["auswertung.stand_erklaerung"] = (
    "Monatssoll = Fachleistungsstunden pro Woche × 52 ÷ 12. Soll bis heute "
    "= Monatssoll × Monate vom Beginn des Bescheids bis einschließlich des "
    "laufenden Monats. Start- und laufender Monat zählen voll, auch für das "
    "Ist: es zählt alles ab dem Ersten des Startmonats bis heute. "
    "<strong>Grün</strong>: im Plan oder Vorsprung. <strong>Gelb</strong>: "
    "der Rückstand ist nicht größer als ein Monatssoll, lässt sich also in "
    "diesem Monat noch aufholen. <strong>Rot</strong>: schon vorher im "
    "Rückstand. <strong>Orange</strong>: der Zeitraum ist erst beantragt "
    "und wird vorläufig gerechnet – nach sechs Monaten ohne Bescheid wird "
    "er rot. Der Balken je Person: die ganze Spur ist das Kontingent des "
    "Bescheids, die Füllung das Geleistete, der senkrechte Strich das Soll "
    "bis heute.")
TEXTE_STANDARD["auswertung.stand_leer"] = (
    "Es sind keine aktiven betreuten Personen eingetragen.")
# Seit 2.2: die Auswertung hat zwei Unterseiten (Bewilligungen |
# Zeitraum & Nachweis); die Erklaerung der Ampel steht als Liste.
TEXTE_STANDARD["auswertung.titel.zeitraum"] = (
    "Zeitraum & Nachweis")
TEXTE_STANDARD["auswertung.zeitraum_lead"] = (
    "Wähle oben einen Zeitraum. Du siehst dann, wie viele Stunden darin "
    "geleistet wurden und wie das zum Soll passt – insgesamt und Monat "
    "für Monat. Das ist die Grundlage für den Nachweis gegenüber dem "
    "Kostenträger.")
TEXTE_STANDARD["auswertung.stand_rechnung"] = (
    "Das Soll pro Monat sind die bewilligten Stunden pro Woche × 52 ÷ 12."
    " „Soll bis heute“ zählt alle Monate vom Beginn des Bescheids bis "
    "einschließlich des laufenden Monats zusammen. Der erste und der "
    "laufende Monat zählen dabei voll – auch bei den geleisteten Stunden "
    "zählt alles ab dem Ersten des Startmonats bis heute.")
TEXTE_STANDARD["auswertung.ampel_gruen"] = (
    "<strong>Im Plan:</strong> Es wurde so viel oder mehr geleistet, wie "
    "bis heute fällig ist.")
TEXTE_STANDARD["auswertung.ampel_gelb"] = (
    "<strong>Diesen Monat noch offen:</strong> Es fehlen höchstens so "
    "viele Stunden, wie für einen Monat bewilligt sind. Das lässt sich in"
    " diesem Monat noch aufholen.")
TEXTE_STANDARD["auswertung.ampel_rot"] = (
    "<strong>Im Rückstand:</strong> Es fehlen mehr Stunden, als für einen"
    " ganzen Monat bewilligt sind.")
TEXTE_STANDARD["auswertung.ampel_orange"] = (
    "<strong>Vorläufig:</strong> Der Folgebescheid ist beantragt, aber "
    "noch nicht da. Gerechnet wird trotzdem schon. Nach sechs Monaten "
    "ohne Bescheid wird die Zeile rot – dann solltest du nachhaken.")
TEXTE_STANDARD["auswertung.balken_erklaerung"] = (
    "Der Balken je Person: Die ganze Länge ist das Kontingent des "
    "Bescheids, der farbige Teil zeigt die geleisteten Stunden, und der "
    "senkrechte Strich markiert das Soll bis heute. Reicht die Farbe bis "
    "zum Strich oder darüber hinaus, ist die Person im Plan.")
TEXTE_STANDARD["auswertung.verdienst_hinweis"] = (
    "Der Verdienst ist ein rechnerischer Wert: geleistete Stunden × "
    "Stundensatz des jeweiligen Monats. Er ersetzt keine Abrechnung.")
TEXTE_STANDARD["bearbeiten.dauer_hinweis"] = (
    "Leer gelassene Dauer wird aus Beginn und Ende berechnet. Eine eingetragene Dauer gewinnt gegenüber der Zeitspanne – praktisch für Zettel ohne Uhrzeiten.")
# ⚠️ Seit 1.49.1 gilt die umgekehrte Regel: die Zeitspanne zieht die Dauer
# mit, sobald sie sich aendert. Der alte Wortlaut (dauer_hinweis) ist damit
# inhaltlich falsch und steht in UNGENUTZT - unter DEMSELBEN Schluessel
# waere die Berichtigung bei einer eigenen Formulierung nie angekommen
# (Abschnitt 8).
# ⚠️ Seit 1.57 ebenfalls in UNGENUTZT: die Dauer laesst sich nicht mehr
# von Hand eintragen (Timos Wunsch), der zweite Satz war damit falsch.
# Neuer Schluessel: bearbeiten.dauer_rechnung.
TEXTE_STANDARD["bearbeiten.dauer_regel"] = (
    "Beginn und Ende rechnen die Dauer aus – änderst du eine Uhrzeit, "
    "zieht die Dauer mit. Wer sie selbst einträgt, behält den eigenen "
    "Wert: der Weg für einen Zettel ohne Uhrzeiten.")
TEXTE_STANDARD["bearbeiten.dauer_rechnung"] = (
    "Die Dauer wird aus Beginn und Ende berechnet. Änderst du eine "
    "Uhrzeit, passt sich die Dauer automatisch an. Hat der Eintrag keine "
    "Uhrzeiten – zum Beispiel, weil er aus einer Datei eingelesen wurde "
    "–, bleibt die gespeicherte Dauer erhalten.")
TEXTE_STANDARD["bearbeiten.lead"] = (
    "Erfasst am {zeitpunkt}. Was du hier änderst, gilt sofort – auch in "
    "der Auswertung und im Export.")
TEXTE_STANDARD["ideen.bearbeiten_hinweis"] = (
    "Eingegangen am {zeitpunkt}. Dieses Datum bleibt beim Bearbeiten "
    "erhalten.")
TEXTE_STANDARD["ideen.hinweis_datei"] = (
    "Die Einträge landen unverändert in <code>ideen.txt</code> im Ordner der Anwendung. Erledigtes kann dort direkt gestrichen werden, die Seite liest die Datei bei jedem Aufruf neu.")
TEXTE_STANDARD["ideen.hinweis_fehler"] = (
    "Konkrete Fehler sind am hilfreichsten mit Datum, betroffener Person und dem, was auf dem Bildschirm stand.")
TEXTE_STANDARD["ideen.lead"] = (
    "Was fehlt dir, was stört, was funktioniert nicht? Schreib es hier "
    "hinein. Jede Rückmeldung wird gelesen und für die nächsten Versionen"
    " vorgemerkt. Deinen Namen kannst du dazuschreiben, musst du aber "
    "nicht.")
TEXTE_STANDARD["ideen.leer"] = (
    "Bisher ist nichts eingegangen. Du darfst gern den Anfang machen.")
# --- Privatauslagen (seit 1.54) ---------------------------------------------
#
# ⚠️ Die Kartenueberschriften laufen ueber t() nach dem Schema
# <bereich>.titel.<name> - so stehen sie im Editor oben in ihrer Gruppe
# und sind umbenennbar (Abschnitt 8).
TEXTE_STANDARD["auslagen.titel.offen"] = (
    "Aktuell ausgelegt")
TEXTE_STANDARD["auslagen.titel.erfassen"] = (
    "Neue Auslage")
TEXTE_STANDARD["auslagen.titel.liste"] = (
    "In der aktuellen Mappe")
TEXTE_STANDARD["auslagen.titel.wartet"] = (
    "Wartet auf Erstattung")
TEXTE_STANDARD["auslagen.titel.jahr"] = (
    "Dieses Jahr")
# ⚠️ Hiess bis 1.56 „Erledigt". Das stand als einzelnes Wort rechts
# neben der Jahreszahl und sagte nicht, was sich dahinter verbirgt —
# Timos Meldung war, dass man den Aufklapper uebersieht. Der Schluessel
# bleibt; er ist nicht falsch geworden, nur zu leise.
TEXTE_STANDARD["auslagen.titel.archiv"] = (
    "Erstattete Mappen")
# ⚠️ Kurz halten: am Telefon steht dieser Absatz zwischen der Summe und
# dem Betragsfeld, also genau im Weg. Fuenf Zeilen waren zu viel.
TEXTE_STANDARD["auslagen.lead"] = (
    "Betrag eintippen und speichern – mehr braucht es nicht. Das Datum "
    "steht schon auf heute, alles andere ist freiwillig.")
# ⚠️ Steht in UNGENUTZT: seit 1.55 sagen Stift und Muelleimer an der
# Zeile, dass sich dort etwas aendern laesst. Der Schluessel bleibt
# stehen, damit ein zurueckkehrender Text nicht neu geschrieben
# werden muss.
TEXTE_STANDARD["auslagen.liste_lead"] = (
    "Was hier steht, liegt noch bei dir. Ein Klick auf eine Zeile öffnet "
    "sie zum Ändern – solange der Block offen ist.")
TEXTE_STANDARD["auslagen.leer"] = (
    "Du hast noch nichts ausgelegt. Sobald du oben einen Betrag "
    "einträgst, beginnt automatisch eine neue Mappe.")
TEXTE_STANDARD["auslagen.nochnichts"] = (
    "Hier sammelt sich alles, was du für die Einrichtung vorgestreckt "
    "hast.")
TEXTE_STANDARD["auslagen.wartet_lead"] = (
    "Diese Bons hast du abgegeben, das Geld ist aber noch nicht da. "
    "Sobald es angekommen ist, hakst du die Mappe hier ab.")
TEXTE_STANDARD["auslagen.belege_hinweis"] = (
    "Erstattete Mappen bleiben als Nachweis erhalten. Die Fotos der "
    "Belege kannst du löschen, um Platz zu sparen – die Beträge bleiben "
    "dabei stehen.")
TEXTE_STANDARD["changelog.lead"] = (
    "Hier steht, was sich von Version zu Version geändert hat. Gerade "
    "läuft Version <strong>{version}</strong> – die Nummer steht auch "
    "unten auf jeder Seite.")
TEXTE_STANDARD["einst.ansicht"] = (
    "Dunkel ist die Voreinstellung und schont abends die Augen.")
TEXTE_STANDARD["einst.betreute_lead"] = (
    "Hier stehen die Menschen, die ihr betreut, mit ihren Bewilligungen. "
    "Für jede Person legst du zuerst fest, <strong>wer zahlt</strong>: "
    "Bei einem Kostenträger kommen Stunden und Stundensatz aus den "
    "eingetragenen Bescheiden, bei Selbstzahlern aus einem fest "
    "vereinbarten Satz. Die Auswertung vergleicht damit, wie viele "
    "Stunden geleistet wurden und wie viele bewilligt sind.")
TEXTE_STANDARD["einst.breite"] = (
    "Volle Breite zeigt mehr Tabelle auf einmal. Begrenzt hält die Textzeilen kürzer und ist auf sehr breiten Monitoren angenehmer zu lesen.")
TEXTE_STANDARD["einst.sprueche_lead"] = (
    "Diese Sprüche erscheinen über der Zeiterfassung und in „Mein "
    "Bereich“ – jeden Tag ein anderer. Eine Quelle steht kleiner "
    "darunter. Die Anführungszeichen setzt das Toolkit selbst, trag also "
    "nur den reinen Wortlaut ein.")
TEXTE_STANDARD["logbuch.lead"] = (
    "Wer hat an den erfassten Zeiten etwas geändert oder gelöscht? Jede "
    "Änderung steht hier mit Uhrzeit und Namen, und zwar dauerhaft – "
    "Zeilen lassen sich weder ändern noch entfernen. <strong>Neu erfasste "
    "Zeiten stehen nicht drin:</strong> wer sie angelegt hat, steht im "
    "Datensatz selbst.")
# ⚠️ Neuer Schlüssel statt geändertem Text: eine vorhandene strings.txt
# gewinnt gegen jeden Standardtext (Abschnitt 8). Der alte Wortlaut sagte
# "Zeilen lassen sich weder ändern noch entfernen" - seit 1.26 dürfen
# Administratoren aufräumen, und dann stünde dort das Gegenteil.
TEXTE_STANDARD["logbuch.einleitung"] = (
    "Hier siehst du, wer an den erfassten Zeiten etwas geändert oder "
    "gelöscht hat – mit Uhrzeit und Namen. <strong>Neu erfasste Zeiten "
    "stehen hier nicht:</strong> Wer einen Eintrag angelegt hat, steht im"
    " Eintrag selbst.")
TEXTE_STANDARD["logbuch.aufraeumen"] = (
    "Wenn du hier aufräumst, bleibt eine Zeile stehen, die festhält, dass"
    " aufgeräumt wurde.")
TEXTE_STANDARD["logbuch.leer"] = (
    "Bisher wurde an den erfassten Zeiten nichts nachträglich geändert "
    "oder gelöscht.")
TEXTE_STANDARD["einst.sprueche_datei"] = (
    "Die Sprüche liegen in der Datei quotes.txt im Ordner /texte. Du "
    "kannst sie auch dort direkt bearbeiten. Achtung: Jedes Speichern "
    "hier schreibt die ganze Datei neu und vereinheitlicht dabei die "
    "Anführungszeichen.")
TEXTE_STANDARD["einst.sprueche_leer"] = (
    "Es ist noch kein Spruch eingetragen. Solange die Liste leer ist, "
    "erscheint einfach keiner.")
TEXTE_STANDARD["einst.wikiliste"] = (
    "Legt fest, wie Ordner und Seiten im Wiki angezeigt werden: als "
    "Kacheln oder als Liste. Die Liste bleibt auch bei vielen Seiten "
    "übersichtlich.")
TEXTE_STANDARD["einst.dateiliste"] = (
    "Legt fest, wie Ordner und Dateien angezeigt werden: als Liste mit "
    "Spalten oder als Kacheln mit Vorschaubildern. Die Liste zeigt mehr "
    "auf einmal, die Kacheln eignen sich für Bilder.")
TEXTE_STANDARD["einst.inaktiv"] = (
    "Wenn jemand das Team verlässt, setz die Person besser auf "
    "<em>inaktiv</em>, statt sie zu löschen. Sie verschwindet dann aus "
    "der Abgabeübersicht, ihre erfassten Zeiten bleiben aber vollständig "
    "erhalten.")
TEXTE_STANDARD["einst.kein_team"] = (
    "Es ist noch niemand eingetragen.")
TEXTE_STANDARD["einst.keine_person"] = (
    "Es ist noch keine Person eingetragen.")
TEXTE_STANDARD["einst.oberflaeche_lead"] = (
    "Diese Einstellungen gelten nur für diesen Browser. Jede und jeder "
    "stellt sie für sich selbst ein, und die Auswahl bleibt gespeichert.")
TEXTE_STANDARD["einst.ohne_pflicht"] = (
    "Wer keine Abgabepflicht hat, steht zwar in der Übersicht, bekommt "
    "aber keine Erinnerung – zum Beispiel Aushilfen oder die Leitung.")
TEXTE_STANDARD["einst.rechnung"] = (
    "Das Soll für einen Monat sind die bewilligten Stunden pro Woche × 52"
    " Wochen ÷ 12 Monate. Bei 5 Stunden pro Woche sind das <strong>21:40 "
    "Stunden</strong> – in jedem Monat gleich, auch im Februar.")
TEXTE_STANDARD["einst.schreibweise_betreute"] = (
    "Groß- und Kleinschreibung, Umlaute und Leerzeichen am Rand spielen "
    "beim Zuordnen keine Rolle. Ansonsten sollte der Name so geschrieben "
    "sein wie in den erfassten oder eingelesenen Zeiten – sonst findet "
    "die Auswertung die Stunden nicht.")
TEXTE_STANDARD["einst.schreibweise_team"] = (
    "Der Name sollte so geschrieben sein wie in der Spalte "
    "<code>Tags</code> der Working-Hours-Exporte bzw. wie bei der "
    "Erfassung. Groß- und Kleinschreibung und zusätzliche Leerzeichen "
    "spielen keine Rolle.")
TEXTE_STANDARD["einst.stillgelegt"] = (
    "Stillgelegte Personen bleiben in der Liste, werden aber nicht mehr "
    "mitgerechnet – praktisch, wenn eine Betreuung endet.")
TEXTE_STANDARD["einst.stundensatz"] = (
    "Aus dem Stundensatz rechnet die Auswertung den Verdienst. Das ist "
    "ein rechnerischer Wert, keine Abrechnung. Ändert sich der Satz zu "
    "einem Stichtag, trag dafür einen neuen Zeitraum ein.")
TEXTE_STANDARD["einst.art_kostentraeger"] = (
    "Stunden pro Woche und Stundensatz stehen nur in den eingetragenen "
    "Bewilligungszeiträumen. Für Monate ohne Bescheid rechnet die "
    "Auswertung <strong>weder ein Soll noch einen Verdienst</strong> – "
    "ohne Bewilligung wird nichts bezahlt.")
TEXTE_STANDARD["einst.art_selbstzahler"] = (
    "Der vereinbarte Satz gilt für jeden Monat, für den kein Zeitraum "
    "eingetragen ist. Selbstzahler brauchen keinen Bescheid und bekommen "
    "deshalb auch keine Bewilligungswarnung. Ändert sich der Satz zu "
    "einem Stichtag, trag zusätzlich einen Zeitraum ein.")
TEXTE_STANDARD["einst.grundwert_umzug"] = (
    "Bis Version 1.19.2 galt dieser Wert für Monate ohne Bescheid. Er "
    "steht hier noch, wird aber nicht mehr verwendet. Lag ein Bescheid "
    "zugrunde, übernimm ihn als Zeitraum – dann bleiben die Zahlen in der"
    " Auswertung gleich. War es nur ein Platzhalter, verwirf ihn.")
TEXTE_STANDARD["einst.zeitraum_hinweis"] = (
    "Hier trägst du ein, was der Kostenträger bewilligt hat. Ein Zeitraum"
    " ohne Enddatum gilt bis auf Weiteres. Überschneiden sich zwei "
    "Zeiträume, gilt der, der später beginnt – so wirkt ein Folgebescheid"
    " sofort, auch wenn der alte formal noch läuft. <strong>Gerechnet "
    "wird in ganzen Monaten:</strong> Ein Zeitraum zählt für jeden Monat,"
    " den er berührt. Ist ein Folgebescheid beantragt, aber noch nicht "
    "da, markier ihn als „beantragt“ – dann rechnet die Seite "
    "„Bewilligungen“ schon vorläufig mit ihm.")
# ⚠️ Diese beiden Schlüssel hiessen bis 1.19.2 "einst.zeitraum_leer" und
# "einst.selbstzahler_hinweis". Sie sind umbenannt, weil ihr alter
# Wortlaut seit 1.20 schlicht falsch ist ("es gilt der Grundwert oben") -
# und eine vorhandene strings.txt gewinnt gegen jeden Standardtext
# (Abschnitt 8). Unter demselben Namen waere die Berichtigung bei
# bestehenden Installationen nie angekommen.
TEXTE_STANDARD["einst.ohne_zeitraum"] = (
    "Für diese Person ist noch kein Zeitraum eingetragen. Die Auswertung "
    "rechnet deshalb weder ein Soll noch einen Verdienst.")
TEXTE_STANDARD["einst.selbstzahler_satz"] = (
    "Selbstzahler zahlen selbst und brauchen keinen Bescheid vom "
    "Kostenträger. Sie bekommen keine Bewilligungswarnung, und als "
    "Stundensatz gilt der vereinbarte Satz. Einen Zeitraum brauchst du "
    "nur, wenn sich der Satz zu einem Stichtag ändert.")
TEXTE_STANDARD["einst.abrechenbar"] = (
    "Legt fest, ob die Zeiten dieser Person mitzählen, wenn du in der "
    "Übersicht oder der Auswertung „nur abrechenbare Zeiten“ "
    "einschaltest. Auf das Soll und alle anderen Zahlen hat das keinen "
    "Einfluss.")
TEXTE_STANDARD["einst.system_lead"] = (
    "Was gerade läuft und wo die Daten liegen – nützlich, wenn etwas hakt"
    " oder du eine Sicherung suchst.")
TEXTE_STANDARD["einst.hinweistexte_abweichung"] = (
    "In der Datei <code>strings.txt</code> steht nur, was hier geändert "
    "wurde. Alle anderen Texte kommen aus dem Programm und werden mit "
    "jedem Update verbessert. Ein Text, den du geändert hast, bekommt "
    "dagegen keine Verbesserungen mehr – setz ihn zurück, wenn du wieder "
    "den aktuellen Wortlaut möchtest.")
TEXTE_STANDARD["einst.system_melden"] = (
    "Wie sich das Toolkit von selbst meldet. Bei welchen Anlässen das "
    "passiert, legst du unter „E-Mail“ fest – die Schalter dort gelten "
    "für E-Mail und Push gleichermaßen.")
# ⚠️ Neuer Schluessel (seit 1.44): der Abschnitt heisst jetzt "Branding"
# und traegt zusaetzlich Favicon und App-Symbol. Der alte Wortlaut
# (einst.system_aussehen) nannte "die erklaerenden Texte", die dort seit
# 1.37 gar nicht mehr stehen - unter demselben Schluessel waere die
# Berichtigung bei einer bestehenden strings.txt nie angekommen.
TEXTE_STANDARD["einst.system_branding"] = (
    "Woran man das Toolkit erkennt: der Schriftzug, das Zeichen im "
    "Browser-Tab, das Symbol auf dem Startbildschirm des Handys und die "
    "Fußzeile. Das gilt für alle Konten – anders als die Einstellungen "
    "unter „Oberfläche“.")
TEXTE_STANDARD["einst.symbol_lead"] = (
    "Das kleine Zeichen im Browser-Tab und das Symbol, das erscheint, "
    "wenn jemand das Toolkit auf den Startbildschirm des Handys legt – "
    "auf dem iPhone wie auf Android. Tauschst du nur eins davon aus, "
    "bleibt beim anderen das mitgelieferte.")
TEXTE_STANDARD["einst.symbol_hinweis"] = (
    "Erlaubt sind PNG-Dateien bis 512 KB, für das Favicon auch ICO. "
    "<strong>Beide Bilder sollten quadratisch sein.</strong> Für das "
    "Favicon reichen 32 × 32 oder 64 × 64 Pixel. Für das App-Symbol nimm "
    "am besten <strong>512 × 512 Pixel</strong>: Das iPhone verkleinert "
    "es selbst, und Android bietet „Zum Startbildschirm hinzufügen“ erst "
    "ab 192 Pixeln an. <strong>Durchsichtige Flächen zeigt das iPhone "
    "schwarz</strong> – gib dem Symbol deshalb besser einen eigenen "
    "Hintergrund. Die Bilder werden in der Datenbank gespeichert, bleiben"
    " bei jedem Update erhalten und sind in der Sicherung enthalten.")
TEXTE_STANDARD["einst.system_aussehen"] = (
    "Was auf jeder Seite steht: der Schriftzug, die Fußzeile und die "
    "erklärenden Texte. Gilt für alle Konten, anders als der Punkt "
    "„Oberfläche“.")
TEXTE_STANDARD["einst.system_sicherung"] = (
    "Die wöchentliche Sicherung auf dem Gerät – und der Weg, eine "
    "Sicherung herunterzuladen oder wieder einzuspielen.")
TEXTE_STANDARD["einst.system_pfade"] = (
    "Wo die Daten im Container liegen. Das brauchst du, wenn du über die "
    "Dateifreigabe an sie herankommen willst oder etwas fehlt.")
TEXTE_STANDARD["einst.team_lead"] = (
    "Hier steht euer Team. Wer eine Abgabepflicht hat, erscheint auf der "
    "Startseite in der Abgabeübersicht – so siehst du auf einen Blick, "
    "wessen Zeiten für den Monat noch fehlen.")
TEXTE_STANDARD["einst.team_offen"] = (
    "Diese Namen kommen in erfassten Zeiten vor, stehen aber noch nicht "
    "im Team. Ein Klick übernimmt sie. Ist es nur eine andere "
    "Schreibweise eines bekannten Namens, korrigier lieber den Namen in "
    "der Liste unten.")
TEXTE_STANDARD["vorgaenge.lead"] = (
    "Hier landet alles Organisatorische rund um die betreuten Personen: "
    "Berichte, Anträge, Fortschreibungen, Rückmeldungen vom LWL und "
    "Fristen. Kurz: alles, was mit Ämtern und Kostenträgern läuft – nicht"
    " die pädagogische Arbeit im Alltag.")
TEXTE_STANDARD["vorgaenge.anlegen_hinweis"] = (
    "Zur Auswahl stehen alle betreuten Personen, für die schon Zeiten "
    "erfasst sind. Fehlt jemand, wurde für diese Person bisher noch keine"
    " Zeit eingetragen.")
TEXTE_STANDARD["vorgaenge.datei_hinweis"] = (
    "Der Dokumentenverweis ist ein reiner Textvermerk – etwa der Ablageort auf "
    "dem Server. Dateien selbst werden im Tool nicht gespeichert.")
TEXTE_STANDARD["vorgaenge.zustaendig_hinweis"] = (
    "Die <strong>zuständige Person</strong> bearbeitet den Vorgang von "
    "jetzt an. Sie steht in der Liste, wird bei Fristen per E-Mail "
    "erinnert, und über sie filtert man „meine Aufgaben“. Sie kann "
    "später jederzeit gewechselt werden.")
# ⚠️ Neuer Schlüssel: seit 1.30 können mehrere Personen zuständig sein,
# der alte Wortlaut sprach von genau einer. Unter dem alten Schlüssel
# wäre die Berichtigung bei einer vorhandenen strings.txt nie angekommen.
TEXTE_STANDARD["vorgaenge.zustaendig_mehrere"] = (
    "Alle hier gewählten Personen kümmern sich um die Aufgabe: Sie steht "
    "in ihrer Liste, sie werden an Fristen erinnert und bekommen eine "
    "E-Mail über die neue Aufgabe, sofern diese Benachrichtigung "
    "eingeschaltet ist. Du kannst die Auswahl später jederzeit ändern.")
TEXTE_STANDARD["vorgaenge.protokoll_hinweis"] = (
    "Jede Änderung an einer Aufgabe wird mit Zeitpunkt und deinem Namen "
    "im Verlauf festgehalten. Dafür musst du nichts ausfüllen – das kommt"
    " aus deiner Anmeldung.")
TEXTE_STANDARD["vorgaenge.keine_personen"] = (
    "Es gibt noch keine betreute Person mit erfassten Zeiten. Erfasse "
    "zuerst Zeiten oder lies eine Liste ein, dann steht die Auswahl hier "
    "bereit.")
TEXTE_STANDARD["vorgaenge.leer"] = (
    "Für diese Filtereinstellung gibt es keine Aufgabe.")
# Seit 1.60: Leer-Zustände, die sagen, warum leer.
TEXTE_STANDARD["vorgaenge.leer_meine"] = (
    "Dir ist gerade keine offene Aufgabe zugewiesen.")
TEXTE_STANDARD["vorgaenge.leer_ueberfaellig"] = (
    "Nichts ist überfällig – sehr gut.")
TEXTE_STANDARD["vorgaenge.aktualisieren_hinweis"] = (
    "Hier änderst du Status, Priorität, Zuständigkeit und Wiedervorlage "
    "in einem Schritt. Alles zusammen wird als ein Eintrag im Verlauf "
    "festgehalten – auf Wunsch mit einer Notiz.")
TEXTE_STANDARD["vorgaenge.stand_hinweis"] = (
    "Der Status wird nicht einfach überschrieben: Jede Änderung wird mit "
    "Zeitpunkt, Namen und Notiz im Verlauf festgehalten.")
TEXTE_STANDARD["vorgaenge.bearbeiten_hinweis"] = (
    "Für Tippfehler und nachgetragene Angaben. Jede Änderung wird im "
    "Verlauf mit altem und neuem Wert festgehalten.")
TEXTE_STANDARD["vorgaenge.archiv_hinweis"] = (
    "Erledigte Aufgaben werden nicht gelöscht. Sie bleiben hier dauerhaft"
    " sichtbar, damit nachvollziehbar ist, was wann von wem erledigt "
    "wurde.")
TEXTE_STANDARD["vorgaenge.logbuch_lead"] = (
    "Jeder organisatorische Schritt zu allen betreuten Personen, der "
    "neueste zuerst. Die Einträge entstehen automatisch und lassen sich "
    "nachträglich nicht ändern.")
TEXTE_STANDARD["einst.ungepflegt"] = (
    "Diese Namen kommen in erfassten Zeiten vor, sind hier aber noch "
    "nicht eingetragen. Ein Klick übernimmt sie; die Bewilligung trägst "
    "du danach ein.")
TEXTE_STANDARD["einst.vorgangsarten_lead"] = (
    "Die Vorgangsarten stehen beim Anlegen einer Aufgabe zur Auswahl. Leg"
    " hier an, was bei euch tatsächlich vorkommt – die Liste muss nicht "
    "von Anfang an vollständig sein.")
TEXTE_STANDARD["einst.vorgangsarten_offen"] = (
    "Diese Bezeichnungen kommen bei bestehenden Aufgaben vor, stehen aber"
    " noch nicht in der Liste. Ein Klick übernimmt sie.")
TEXTE_STANDARD["einst.vorgangsarten_stillgelegt"] = (
    "Stillgelegte Vorgangsarten stehen beim Anlegen nicht mehr zur "
    "Auswahl. An bestehenden Aufgaben bleiben sie sichtbar und "
    "auswählbar.")
TEXTE_STANDARD["einst.vorgangsarten_keine"] = (
    "Es ist noch keine Vorgangsart angelegt.")
TEXTE_STANDARD["einst.leistungen_lead"] = (
    "Diese Leistungen stehen bei der Zeiterfassung zur Auswahl. So wird "
    "dieselbe Leistung immer gleich geschrieben und taucht nicht in fünf "
    "Varianten auf. Beim Eintrag wird nur der Text gespeichert – änderst "
    "du eine Bezeichnung später, bleiben die schon erfassten Zeiten "
    "unverändert.")
TEXTE_STANDARD["einst.leistungen_offen"] = (
    "Diese Beschreibungen kommen in den erfassten Zeiten am häufigsten "
    "vor, stehen aber noch nicht in der Auswahl. Ein Klick übernimmt sie.")
TEXTE_STANDARD["einst.leistungen_stillgelegt"] = (
    "Stillgelegte Leistungen stehen bei der Erfassung nicht mehr zur "
    "Auswahl. Sie bleiben hier aber erhalten und lassen sich jederzeit "
    "wieder einschalten.")
TEXTE_STANDARD["einst.leistungen_keine"] = (
    "Es ist noch keine Leistung angelegt. Solange die Liste leer ist, "
    "gibt es bei der Erfassung nur das freie Textfeld.")
TEXTE_STANDARD["erfassung.kein_team"] = (
    "Es ist noch niemand im Team eingetragen. Ohne Mitarbeitende lässt "
    "sich keine Zeit erfassen – trag die Namen unter Einstellungen → "
    "Mitarbeiter ein.")
TEXTE_STANDARD["erfassung.keine_personen"] = (
    "Es ist noch keine betreute Person eingetragen. Du legst sie unter "
    "Einstellungen → Betreute Personen an. Eigene Namen lassen sich hier "
    "bewusst nicht eintippen, damit dieselbe Person nicht in drei "
    "Schreibweisen in der Auswertung landet.")
TEXTE_STANDARD["erfassung.leistungen_leer"] = (
    "Feste Leistungen legst du unter <strong>Einstellungen → "
    "Leistungen</strong> an. Sie stehen dann hier zur Auswahl.")
TEXTE_STANDARD["einst.benutzer_lead"] = (
    "Hier stehen die Zugänge zum Toolkit. Sie sind unabhängig von den "
    "Namen unter „Mitarbeiter“: Nicht jede Person im Team braucht einen "
    "Zugang, und nicht jeder Zugang gehört zu jemandem aus dem Team.")
TEXTE_STANDARD["einst.benutzer_bereiche_regel"] = (
    "Das Konto darf alle angehakten Bereiche nutzen. Sind alle angehakt, "
    "gilt das als voller Zugriff – auch auf Bereiche, die später "
    "dazukommen. Eine Ausnahme ist <strong>die Datenpflege</strong>: Sie "
    "muss immer ausdrücklich angehakt werden, weil sie viele Einträge auf"
    " einmal ändert. Die Auswahl gilt <strong>auch für "
    "Administratoren</strong>; nur die Einstellungen bleiben ihnen immer "
    "erhalten.")
TEXTE_STANDARD["einst.benutzer_bereiche_hinweis"] = (
    "Alle angehakten Bereiche darf das Konto nutzen. Sind alle angehakt, "
    "gilt das als voller Zugriff und schließt auch später neu "
    "hinzukommende Bereiche automatisch mit ein – mit einer Ausnahme: "
    "<strong>die Datenpflege</strong> muss immer ausdrücklich angehakt "
    "werden, sie ändert viele Einträge auf einmal. Bei der Rolle "
    "„Administrator“ hat diese Auswahl keine Wirkung.")
# ⚠️ Seit 1.56 gilt diese Auswahl auch fuer Administratoren (Timos
# Wunsch, "welcher Nutzer Zugang zum Menuepunkt Einstellungen ->
# Sprueche hat"). Der Satz dazu ist hier ERGAENZT und nicht unter einem
# neuen Schluessel abgelegt: der alte Wortlaut war unvollstaendig, nicht
# falsch - die Regel aus Abschnitt 8 meint Texte, die inhaltlich falsch
# geworden sind.
TEXTE_STANDARD["einst.benutzer_einstpunkte_hinweis"] = (
    "Welche Punkte innerhalb der Einstellungen das Konto sieht. Sind alle"
    " angehakt, gilt das auch für Punkte, die später dazukommen. "
    "„Oberfläche“ ist immer sichtbar, weil dort jede und jeder die eigene"
    " Darstellung einstellt. <strong>Die Auswahl gilt auch für "
    "Administratoren.</strong> Benutzerverwaltung, E-Mail sowie System "
    "und Sicherung hängen an der Rolle „Administrator“ und stehen deshalb"
    " nicht zur Wahl.")
# ⚠️ Seit 1.55 gelten die Haken auch fuer Administratoren. Die beiden
# alten Schluessel (einst.benutzer_admin_hinweis,
# einst.benutzer_bereiche_hinweis) behaupteten das Gegenteil und sind
# damit inhaltlich falsch - unter DEMSELBEN Schluessel waere die
# Berichtigung bei einer eigenen Formulierung nie angekommen
# (Abschnitt 8). Sie stehen jetzt in UNGENUTZT.
TEXTE_STANDARD["einst.benutzer_admin_regel"] = (
    "Dieses Konto ist Administrator – die Auswahl unten gilt trotzdem. So"
    " kannst du Bereiche ausblenden, die du nicht brauchst. <strong>Die "
    "Einstellungen bleiben immer erreichbar</strong>, sonst käme niemand "
    "mehr auf diese Seite zurück.")
TEXTE_STANDARD["einst.benutzer_admin_hinweis"] = (
    "Die Rolle ist „Administrator“ – dieses Konto hat damit ohnehin "
    "vollen Zugriff. Die Auswahl unten wird trotzdem gespeichert und "
    "greift wieder, sobald die Rolle auf „Benutzer“ zurückgestellt wird.")
TEXTE_STANDARD["einst.auslagenmail_wozu"] = (
    "Reicht jemand Privatauslagen ein, entsteht eine Aufgabe für die "
    "Person, die die Auslagen abrechnet – und diese Nachricht geht an "
    "sie. <strong>Wer das ist, legst du unter Einstellungen → Mitarbeiter"
    " fest.</strong> Ist dort niemand angehakt, passiert beides nicht.")
TEXTE_STANDARD["einst.auslagenmail_hinweis"] = (
    "Die Nachricht geht innerhalb weniger Minuten hinaus. Sobald die "
    "Aufgabe auf „Erledigt“ steht, gilt die Mappe als erstattet – das "
    "kann die abrechnende oder die einreichende Person tun.")
# ⚠️ Steht in BEIDEN Mitarbeiterformularen. Der Satz muss den Kern
# treffen: es wird nichts geloescht, es wird nur anders GEZAEHLT.
TEXTE_STANDARD["einst.zeiterfassung_ab"] = (
    "Ab diesem Tag zählen Soll und Saldo in „Mein Bereich“: Diagramm, "
    "Monatstabelle und Trend beginnen hier. Was vorher erfasst wurde, "
    "<strong>bleibt erhalten</strong> und steht weiterhin in der "
    "Übersicht und im Export. Liegt der Tag mitten im Monat, zählt erst "
    "der folgende Monat. Der Übertrag ist der Stand an Über- oder "
    "Minusstunden, der an diesem Tag schon bestand – er funktioniert nur "
    "zusammen mit einem Startdatum.")
TEXTE_STANDARD["einst.wiki_geschuetzt_lead"] = (
    "Ein geschützter Ordner ist für alle unsichtbar, die ihn nicht "
    "ausdrücklich freigegeben bekommen: im Ordnerbaum, in der "
    "Ordneransicht, in der Suche und beim Verschieben. Auch über die "
    "Adresse kommt man nicht hinein.")
TEXTE_STANDARD["einst.wiki_geschuetzt_hinweis"] = (
    "Der Schutz gilt für den Ordner und alles darin. Wer ihn sehen darf, "
    "hakst du unten bei jedem Konto einzeln an – <strong>ohne Haken sieht"
    " ihn niemand</strong>. Administratoren sehen immer alles.")
TEXTE_STANDARD["einst.benutzer_rechte_hinweis"] = (
    "Drei Rechte, die keinen eigenen Bereich bilden, sondern innerhalb "
    "eines Bereichs eine Grenze ziehen. <strong>Einträge anderer "
    "bearbeiten</strong> und <strong>Einträge anderer löschen</strong>: "
    "ohne diese Rechte kann das Konto in der Übersicht nur seine eigenen "
    "Zeiten ändern beziehungsweise löschen – die eigenen aber immer. Beide "
    "sind getrennt, weil beides verschieden schwer wiegt: eine gelöschte "
    "Zeile fällt auf, eine stillschweigend geänderte nicht. "
    "<strong>Wiki bearbeiten</strong>: ohne dieses Recht bleibt das Wiki "
    "vollständig lesbar, lässt sich aber nicht ändern.")
# ⚠️ Neuer Schluessel statt Aenderung am alten (siehe Abschnitt 8 der
# CLAUDE.md): eine vorhandene strings.txt gewinnt gegen jeden
# Standardtext - unter "…_hinweis" waere der berichtigte Wortlaut bei
# einer bestehenden Installation nie angekommen. Der alte Schluessel
# bleibt stehen und steht in UNGENUTZT.
TEXTE_STANDARD["einst.benutzer_rechte"] = (
    "Diese Rechte gelten innerhalb eines Bereichs. <strong>Einträge "
    "anderer bearbeiten</strong> bzw. <strong>löschen</strong>: Ohne "
    "diese Rechte kann das Konto in der Übersicht nur die eigenen Zeiten "
    "ändern oder löschen – die eigenen aber immer. Beides ist getrennt, "
    "weil eine gelöschte Zeile auffällt, eine still geänderte dagegen "
    "nicht. <strong>Aufgaben anderer löschen</strong>: Selbst angelegte "
    "Aufgaben darf jede und jeder löschen, die von anderen nur mit diesem"
    " Recht. <strong>Wiki bearbeiten</strong>: Ohne dieses Recht lässt "
    "sich das Wiki lesen, aber nicht ändern. <strong>Bewilligungen in "
    "„Mein Bereich“</strong>: zeigt dort, welche Bewilligungen auslaufen "
    "oder fehlen. <strong>Verdienst und Stundensätze</strong>: Ohne "
    "dieses Recht zeigt die Auswertung nur Stunden und keine Geldbeträge."
    " Administratoren sehen sie immer.")
TEXTE_STANDARD["einst.dateien_versteckt_lead"] = (
    "Ein Ordner der Dateiverwaltung, den nur ausgewählte Konten sehen. "
    "Gedacht für Material, das im Alltag stört, aber gebraucht wird – "
    "etwa Bilder, die im Wiki eingebunden sind, oder Dateien zum "
    "Herunterladen wie E-Mail-Profile für neue Kolleginnen und Kollegen.")
TEXTE_STANDARD["einst.dateien_versteckt_warnung"] = (
    "<strong>Das ist ein Versteck, kein Schutz.</strong> Der Ordner "
    "verschwindet aus Baum und Übersicht, aber jede Datei darin ist über "
    "ihren direkten Link für alle erreichbar – genau dafür sind diese "
    "Ordner da. Leg dort nichts Vertrauliches ab.")
TEXTE_STANDARD["einst.dateien_versteckt_hinweis"] = (
    "Nur Ordner der obersten Ebene, jeweils mit allem darin. Wer keinen "
    "Haken bekommt, sieht den Ordner nicht – weder im Baum noch in der "
    "Ordnerauswahl noch über die Adresse. Administratoren sehen ihn "
    "immer.")
TEXTE_STANDARD["einst.ntfy_lead"] = (
    "Push-Nachrichten aufs Handy über einen ntfy-Server – entweder den "
    "öffentlichen unter ntfy.sh oder einen eigenen. Sie kommen zusätzlich"
    " zur E-Mail und bei denselben Anlässen: überfällige Fristen, "
    "fehlende Monatsabgaben, auslaufende Bewilligungen, neue und "
    "erledigte Aufgaben.")
TEXTE_STANDARD["einst.ntfy_hinweis"] = (
    "<strong>Bei welchen Anlässen Nachrichten verschickt werden, legst du"
    " unter „E-Mail“ fest</strong> – die Schalter dort gelten für beide "
    "Wege. Der E-Mail-Versand selbst darf dabei ausgeschaltet sein. Das "
    "Thema kannst du frei wählen, es ist aber zugleich das Kennwort: "
    "<strong>Wer es kennt, kann mitlesen.</strong> Nimm deshalb etwas "
    "Langes, schwer Erratbares, oder schütze das Thema auf dem Server mit"
    " Zugangsdaten. In der App „ntfy“ trägst du denselben Server und "
    "dasselbe Thema ein.")
TEXTE_STANDARD["einst.ntfy_zugang"] = (
    "Nur nötig, wenn der Server das Thema schützt. Ein Zugriffstoken geht"
    " vor Benutzername und Passwort. Aus Sicherheitsgründen bleiben die "
    "Felder leer – ein leeres Feld lässt den gespeicherten Wert "
    "unverändert.")
TEXTE_STANDARD["einst.logo_lead"] = (
    "Der Schriftzug in der Kopfzeile, in der Fußzeile und auf der "
    "Anmeldeseite. Es gibt zwei Dateien, weil das helle und das dunkle "
    "Farbschema unterschiedliche Farben brauchen. Tauschst du nur eine "
    "aus, bleibt beim anderen der mitgelieferte Schriftzug.")
TEXTE_STANDARD["einst.logo_hinweis"] = (
    "Erlaubt sind SVG-Dateien bis 512 KB. <strong>Die Schrift muss in "
    "Pfade umgewandelt sein</strong> – sonst ersetzt der Browser sie "
    "durch eine andere Schriftart. Dateien mit Skripten werden abgelehnt."
    " Die Logos werden in der Datenbank gespeichert, bleiben bei jedem "
    "Update erhalten und sind in der Sicherung enthalten.")
TEXTE_STANDARD["einst.hinweistexte_lead"] = (
    "Alle erklärenden Texte der Oberfläche, nach Bereichen sortiert. Was "
    "du hier änderst, steht sofort auf der Seite – ohne Neustart.")
TEXTE_STANDARD["einst.hinweistexte_hinweis"] = (
    "Einfaches HTML wie <strong>&lt;strong&gt;</strong> oder ein Link ist"
    " erlaubt. Wörter in geschweiften Klammern wie <code>{name}</code> "
    "sind Platzhalter und müssen stehen bleiben – dort wird später der "
    "passende Wert eingesetzt. Leerst du ein Feld, gilt wieder der "
    "mitgelieferte Text. Zeilenumbrüche werden zu Leerzeichen.")
# ⚠️ NEUER Schluessel (1.40): der Punkt traegt seitdem nicht mehr nur die
# Hinweistexte, sondern auch die Ueberschriften der Karten. Der alte
# Wortlaut ("Alle erklaerenden Texte der Oberflaeche") war damit falsch,
# und unter demselben Schluessel waere die Berichtigung bei einer
# bestehenden strings.txt nie angekommen (Abschnitt 8).
TEXTE_STANDARD["einst.texte_bezeichnungen_lead"] = (
    "Die Überschriften der Karten und alle erklärenden Texte, sortiert "
    "nach Bereichen. Innerhalb eines Bereichs stehen die Überschriften "
    "oben. Änderungen siehst du sofort auf der Seite.")
TEXTE_STANDARD["einst.hinweistexte_leer"] = (
    "Ein leeres Feld stellt den mitgelieferten Text wieder her.")
TEXTE_STANDARD["einst.sprueche_sehen"] = (
    "Der Spruch über der Zeiterfassung und in „Mein Bereich“. Das ist "
    "kein Recht, sondern Geschmackssache – deshalb wirkt der Haken auch "
    "bei Administratoren. Ohne Haken verschwindet der Spruch ganz.")
TEXTE_STANDARD["einst.benutzer_selbst"] = "das eigene Konto"
# --- Überschriften der Karten (seit 1.40) ------------------------------------
#
# ⚠️⚠️ Das ist eine AUSNAHME von der Konvention weiter unten ("nicht in
# strings.txt: Feldbeschriftungen, Knopftexte, Tabellenüberschriften") und
# Timos ausdrücklicher Auftrag: die Karten auf "Auswertung" und in "Mein
# Bereich" heissen so, wie er sie nennen will. Die Grenze bleibt sonst
# bestehen - Feldbeschriftungen, Knopftexte und SPALTENüberschriften
# gehoeren weiterhin nicht hierher.
#
# ⚠️ Das zweite Segment "titel" ist kein Zufall: der Texteditor gruppiert
# nach dem ERSTEN Segment (die Karten landen also im Bereich, zu dem sie
# gehoeren) und erkennt am zweiten, dass es eine Ueberschrift ist - die
# steht dann oben in der Gruppe, in einem einzeiligen Feld und mit der
# Marke "Ueberschrift". Wer eine neue ergaenzt, haelt sich an dieses
# Schema, dann stimmt beides von selbst.
TEXTE_STANDARD["mein.titel.ansteht"] = "Was ansteht"
TEXTE_STANDARD["mein.titel.aufgaben"] = "Meine Aufgaben"
TEXTE_STANDARD["mein.titel.bewilligungen"] = "Bewilligungen im Blick"
TEXTE_STANDARD["mein.titel.arbeitszeit"] = "Meine Arbeitszeit"
TEXTE_STANDARD["mein.titel.verlauf"] = "Verlauf"
# {jahr} wird durch das laufende Kalenderjahr ersetzt.
TEXTE_STANDARD["mein.titel.urlaub"] = "Urlaub {jahr}"
# {monate} ist die Zahl der gezeigten Monate (in aller Regel drei).
TEXTE_STANDARD["mein.titel.trend"] = "Die letzten {monate} Monate"
TEXTE_STANDARD["mein.titel.monate"] = "Monat für Monat"
TEXTE_STANDARD["mein.titel.zeiten"] = "Eintrag für Eintrag"
TEXTE_STANDARD["mein.titel.konto"] = "Mein Konto"
TEXTE_STANDARD["mein.titel.vorlagen"] = "Meine Vorlagen"
TEXTE_STANDARD["mein.vorlagen_einleitung"] = (
    "Vorlagen für Tage, die sich ähnlich wiederholen. In der "
    "Zeiterfassung lädst du sie über „Vorlagen“ neben „Neuer Eintrag“. "
    "Sie füllen dort nur das Formular – gespeichert wird erst, wenn du "
    "die Einträge speicherst.")
TEXTE_STANDARD["mein.vorlagen_leer"] = (
    "Leg hier eine Vorlage an – oder speichere in der Zeiterfassung einen"
    " Tag, den du schon eingetragen hast, als Vorlage.")
TEXTE_STANDARD["auswertung.titel.stand"] = "Stand der Bewilligungen"
TEXTE_STANDARD["auswertung.titel.ueberblick"] = "Überblick"
TEXTE_STANDARD["auswertung.titel.monate"] = "Monat für Monat"
TEXTE_STANDARD["auswertung.titel.kontingent"] = "Stundenkontingent"
TEXTE_STANDARD["auswertung.titel.monatsliste"] = "Monate"
TEXTE_STANDARD["auswertung.titel.bewilligt"] = "Bewilligt"

TEXTE_STANDARD["mein.konto_lead"] = (
    "Hier änderst du dein Passwort und die E-Mail-Adresse, an die "
    "Erinnerungen geschickt werden. Alles andere an deinem Konto – Rolle,"
    " Zugriffsrechte und die Zuordnung zum Team – pflegt jemand mit "
    "Administratorrechten.")
TEXTE_STANDARD["einst.benutzer_keine"] = (
    "Es ist noch kein Konto angelegt.")
TEXTE_STANDARD["einst.monatsstunden"] = (
    "Die monatliche Arbeitszeit ist die Grundlage für „Mein Bereich“: "
    "Dort sieht jede Person, ob sie im Plus oder im Minus liegt. Steht "
    "hier 0, wird kein Saldo berechnet.")
TEXTE_STANDARD["mein.lead"] = (
    "Deine erfassten Zeiten als {name} im Vergleich zu deinem Monatssoll."
    " Diese Seite siehst nur du – andere Konten sehen hier ihre eigenen "
    "Zahlen.")
TEXTE_STANDARD["mein.keine_zuordnung"] = (
    "Dieses Konto ist keiner Person im Team zugeordnet, deshalb gibt es "
    "hier keine persönlichen Zahlen. Jemand mit Administratorrechten kann"
    " die Zuordnung unter Einstellungen → Benutzerverwaltung im Feld "
    "„Gehört zu Mitarbeiter“ setzen.")
TEXTE_STANDARD["mein.verwaist"] = (
    "Dein Konto ist „{name}“ zugeordnet, diesen Namen gibt es im Team "
    "aber nicht mehr. Deine Zeiten werden weiter angezeigt, ein "
    "Monatssoll lässt sich so aber nicht hinterlegen.")
TEXTE_STANDARD["mein.kein_soll"] = (
    "Für dich ist noch keine monatliche Arbeitszeit eingetragen, deshalb "
    "wird kein Saldo berechnet. Jemand mit Administratorrechten trägt sie"
    " unter Einstellungen → Mitarbeiter ein.")
TEXTE_STANDARD["mein.laufend_hinweis"] = (
    "Der laufende Monat zählt noch nicht zum Saldo – sonst stündest du am"
    " Monatsanfang immer tief im Minus.")
TEXTE_STANDARD["mein.kein_laufender"] = (
    "Für diesen Monat hast du noch keine Zeiten erfasst.")
# ⚠️ Der Satz, der die Sorge abraeumt: es wird nichts geloescht, nur
# anders gezaehlt. Er steht unter dem Stundenkonto, also genau dort, wo
# die Frage aufkommt.
TEXTE_STANDARD["mein.erfassung_ab"] = (
    "Ältere Zeiten bleiben erhalten und stehen weiterhin unter „Eintrag "
    "für Eintrag“. Sie zählen nur nicht mehr zu Soll und Saldo.")
TEXTE_STANDARD["mein.erfassung_kuenftig"] = (
    "Für dich beginnt die verbindliche Zeiterfassung am {datum}. Bis "
    "dahin gibt es hier noch keine Monatszahlen. Erfassen kannst du "
    "trotzdem schon – alle Zeiten bleiben erhalten.")
TEXTE_STANDARD["mein.kein_abgeschlossener"] = (
    "Es gibt noch keinen abgeschlossenen Monat. Die Zahlen beginnen, "
    "sobald der erste Monat vorbei ist.")
TEXTE_STANDARD["mein.urlaub_hinweis"] = (
    "Gezählt werden Tage, an denen ein Eintrag mit „Urlaub“ beginnt. "
    "Jeder Tag zählt einmal, auch bei mehreren Einträgen. „Urlaub (Halber"
    " Tag)“ zählt einen halben Tag; steht am selben Tag auch ein ganzer, "
    "zählt der ganze.")
TEXTE_STANDARD["mein.kein_urlaubsanspruch"] = (
    "Für dich ist noch kein Urlaubsanspruch eingetragen. Deine "
    "Urlaubstage werden gezählt, aber nicht mit einem Anspruch "
    "verrechnet. Jemand mit Administratorrechten trägt ihn unter "
    "Einstellungen → Mitarbeiter ein.")
TEXTE_STANDARD["einst.urlaubstage"] = (
    "Der Urlaubsanspruch in Tagen pro Kalenderjahr. In „Mein Bereich“ "
    "sieht jede Person, wie viele Tage sie schon genommen hat und wie "
    "viele noch übrig sind. 0 heißt: kein Anspruch eingetragen.")
TEXTE_STANDARD["mein.bewilligungen_lead"] = (
    "Diese Bewilligungen sind abgelaufen, laufen in den nächsten 60 Tagen"
    " aus oder fehlen ganz – hier muss ein Folgeantrag gestellt werden.")
TEXTE_STANDARD["mein.keine_aufgaben"] = (
    "Hier liegt absolut gar nichts an. Schau einfach beschäftigt und "
    "bewege ab und zu die Maus, bis dir jemand die nächste Katastrophe "
    "anhängt.")
TEXTE_STANDARD["mein.ansteht_lead"] = (
    "Was gerade auf deinem Tisch liegt: deine Aufgaben mit Frist und "
    "Bewilligungen, um die sich jemand kümmern muss.")
TEXTE_STANDARD["mein.bewilligungen_gut"] = (
    "Bei keiner betreuten Person läuft gerade eine Bewilligung aus oder "
    "fehlt.")
TEXTE_STANDARD["mein.zeiten_lead"] = (
    "Alle Zeiten, die auf deinen Namen erfasst sind. Hier kannst du deine"
    " eigenen Einträge immer korrigieren oder löschen – auch wenn du "
    "keinen Zugriff auf die Übersicht unter „Arbeitszeit“ hast.")
TEXTE_STANDARD["mein.zeiten_leer"] = (
    "Für diesen Zeitraum ist nichts erfasst.")
TEXTE_STANDARD["mein.zeiten_gekappt"] = (
    "Du siehst die neuesten {max} Einträge. Für ältere wähle oben einen "
    "Monat aus.")
TEXTE_STANDARD["mein.tabelle_hinweis"] = (
    "Monate ohne erfasste Zeiten erscheinen mit dem vollen Soll im Minus – "
    "das ist Absicht, damit vergessene Abgaben auffallen. Urlaub, Krankheit "
    "oder Feiertage berücksichtigt die Rechnung nicht.")
TEXTE_STANDARD["mein.monatstabelle_hinweis"] = (
    "Jede Zeile ist ein Monat, der neueste steht oben. Monate ohne "
    "erfasste Zeiten stehen mit dem vollen Soll im Minus – das ist "
    "Absicht, damit eine vergessene Abgabe auffällt. Urlaub und "
    "Krankmeldungen senken das Soll und stehen dann in der Spalte „Frei“."
    " Feiertage senken das Soll nicht, weil auch an Feiertagen gearbeitet"
    " wird.")
TEXTE_STANDARD["mein.keine_zeiten"] = (
    "Für {name} sind bisher keine Zeiten erfasst.")
TEXTE_STANDARD["einst.benutzer_mitarbeiter_hinweis"] = (
    "Legt fest, zu welcher Person im Team dieses Konto gehört. Davon "
    "hängt ab, wer Erinnerungen bekommt und welche Zeiten in „Mein "
    "Bereich“ erscheinen. Ohne Zuordnung sucht das Toolkit nach einem "
    "Teammitglied, das genauso heißt wie der Benutzername. Weicht der "
    "Benutzername ab, setz die Zuordnung hier.")
TEXTE_STANDARD["einst.email_lead"] = (
    "Zugang zum Mailserver für die automatischen Erinnerungen. Empfänger "
    "ist jeweils die E-Mail-Adresse des Benutzerkontos – wer keinen "
    "Zugang mit hinterlegter Adresse hat, bekommt keine Nachricht.")
TEXTE_STANDARD["einst.email_test_hinweis"] = (
    "Schickt sofort eine Testnachricht, auch wenn der automatische "
    "Versand ausgeschaltet ist. So prüfst du, ob die Zugangsdaten "
    "stimmen.")
TEXTE_STANDARD["einst.email_pruefen_hinweis"] = (
    "Führt alle Prüfungen sofort aus, statt auf den nächsten stündlichen "
    "Durchlauf zu warten. Schon verschickte Erinnerungen werden dabei "
    "nicht noch einmal verschickt.")
TEXTE_STANDARD["einst.email_verlauf_hinweis"] = (
    "Jede Erinnerung wird nur einmal verschickt. Wird eine Frist "
    "verschoben, kann erneut daran erinnert werden.")
TEXTE_STANDARD["einst.email_keine"] = (
    "Bisher wurde keine Nachricht verschickt.")

# --- Die drei Abschnitte des Punktes „E-Mail" --------------------------------
#
# ⚠️ Bis 1.37 waren Versand und Vorlagen zwei getrennte Punkte im Menue.
# Das war die falsche Achse: wer den Wortlaut einer Erinnerung aendern
# wollte, schaltete den Anlass auf der einen Seite ein und suchte seinen
# Text auf der anderen - und keine der beiden Seiten sagte, dass es die
# andere ueberhaupt gibt. Seit 1.38 ein Punkt in drei Abschnitten, und
# jeder Anlass traegt seinen Wortlaut gleich mit.
TEXTE_STANDARD["einst.email_zugang"] = (
    "Über welchen Server die Nachrichten verschickt werden und mit "
    "welcher Absenderadresse sie ankommen. Ohne diese Angaben wird keine "
    "Nachricht verschickt.")
TEXTE_STANDARD["einst.email_anlaesse"] = (
    "Wann das Toolkit von sich aus eine Nachricht schickt. Jeden Anlass "
    "kannst du einzeln ein- und ausschalten. Den Wortlaut der Nachricht "
    "findest du direkt beim Anlass: aufklappen, ändern, speichern.")
TEXTE_STANDARD["einst.email_protokoll"] = (
    "Welche Nachrichten tatsächlich verschickt wurden – und die "
    "Möglichkeit, alle Texte auf die mitgelieferte Fassung "
    "zurückzusetzen.")
TEXTE_STANDARD["einst.vorlagen_wortlaut"] = (
    "Der Wortlaut steht direkt beim Anlass: aufklappen, Betreff und Text "
    "ändern und zusammen mit dem Anlass speichern. Wörter in geschweiften"
    " Klammern sind Platzhalter, die beim Versand durch die echten Werte "
    "ersetzt werden – lass sie am besten stehen.")
TEXTE_STANDARD["einst.vorlagen_ruecksetzen_alle"] = (
    "Setzt alle Vorlagen auf die mitgelieferte Fassung zurück. Ob die "
    "Anlässe ein- oder ausgeschaltet sind, bleibt dabei unverändert.")
TEXTE_STANDARD["einst.vorlagen_lead"] = (
    "Wortlaut der beiden automatischen Nachrichten. Die Platzhalter in "
    "geschweiften Klammern werden beim Versand durch die echten Werte "
    "ersetzt – am besten stehen lassen.")
TEXTE_STANDARD["einst.vorlage_frist_hinweis"] = (
    "Geht an die zuständige Person, sobald die Wiedervorlage eines "
    "Vorgangs überschritten ist.")
TEXTE_STANDARD["einst.vorlage_abgabe_hinweis"] = (
    "Geht zu Beginn eines neuen Monats an alle abgabepflichtigen "
    "Mitarbeitenden, von denen für den abgelaufenen Monat noch keine "
    "Zeiten vorliegen.")
TEXTE_STANDARD["einst.vorlagen_zuruecksetzen"] = (
    "Stellt beide Vorlagen wieder so her, wie sie ausgeliefert wurden.")
TEXTE_STANDARD["einst.sicherung_export"] = (
    "Lädt den kompletten Datenbestand als eine Datei herunter. Das klappt"
    " auch, während andere gerade mit dem Toolkit arbeiten. Lade "
    "regelmäßig eine Sicherung herunter und bewahr sie außerhalb des "
    "Geräts auf.")
TEXTE_STANDARD["einst.sicherung_import"] = (
    "Spielt eine früher heruntergeladene Sicherung zurück. Der aktuelle "
    "Datenbestand wird dabei vollständig ersetzt; die bisherige Datenbank"
    " wird vorher zur Sicherheit daneben abgelegt. Danach musst du dich "
    "neu anmelden.")
TEXTE_STANDARD["mein.diagramm_hinweis"] = (
    "Jeder Balken steht für einen Monat. Der farbige Teil zeigt deine "
    "erfassten Stunden. Darüber siehst du entweder, wie viel du über dem "
    "Soll lagst, oder – gestrichelt umrandet – wie viel bis zum Soll "
    "gefehlt hat. Die Linie zeigt deinen Saldo über die gezeigten Monate "
    "zusammengezählt. Fährst du mit der Maus über einen Monat, siehst du "
    "die genauen Werte.")
TEXTE_STANDARD["einst.sicherung_automatisch"] = (
    "Jeden Sonntag legt das Toolkit von selbst eine Kopie der Datenbank "
    "auf dem Gerät ab. Die fünf neuesten bleiben erhalten, ältere werden "
    "gelöscht. Das ersetzt keine Sicherung an einem anderen Ort – dafür "
    "ist der Knopf darunter da.")
TEXTE_STANDARD["einst.abgabemail_lead"] = (
    "Erinnert alle Mitarbeitenden mit Abgabepflicht, von denen für den "
    "letzten Monat noch keine Zeiten vorliegen. Jede Person bekommt "
    "höchstens eine Erinnerung pro Monat.")
TEXTE_STANDARD["einst.abgabemail_hinweis"] = (
    "Vor dem eingestellten Tag passiert nichts. Wer bis zum Fünften Zeit "
    "hat, trägt hier eine 5 ein – sonst käme die Erinnerung schon in der "
    "Nacht zum Ersten.")
TEXTE_STANDARD["einst.zuweisungsmail_lead"] = (
    "Benachrichtigt eine Person, wenn ihr eine Aufgabe zugewiesen wird – "
    "beim Anlegen und wenn eine bestehende Aufgabe an sie übergeben wird.")
TEXTE_STANDARD["einst.zuweisungsmail_hinweis"] = (
    "Nach der zuletzt zugewiesenen Aufgabe wartet das Toolkit so viele "
    "Minuten, bevor die E-Mail rausgeht. Kommen in dieser Zeit weitere "
    "Aufgaben dazu, stehen alle in einer Nachricht. Bei 0 geht die E-Mail"
    " innerhalb einer Minute raus.")
TEXTE_STANDARD["einst.smtp_fehlt"] = (
    "<strong>Es ist noch kein Mailserver eingetragen.</strong> Trag "
    "Absenderadresse, Server, Benutzername und Passwort ein und speichere"
    " einmal – erst danach kann etwas verschickt werden. Die Angaben "
    "liegen nur hier in der Datenbank, nirgends im Programmcode.")
TEXTE_STANDARD["einst.leerzellen"] = (
    "In der Auswertung bleiben manche Zellen leer, zum Beispiel wenn für "
    "eine Person nichts bewilligt ist. „Leer“ lässt sie leer, „Mit "
    "Strich“ setzt einen Gedankenstrich hinein. Gilt nur für diesen "
    "Browser.")
TEXTE_STANDARD["einst.aufgabenliste"] = (
    "Karten zeigen Titel, Notiz und Stand untereinander. Die Liste zeigt "
    "mehr Aufgaben auf einmal und stellt die Fristen in einer Spalte "
    "untereinander.")
TEXTE_STANDARD["einst.erledigtmail_lead"] = (
    "Meldet der Person, die eine Aufgabe angelegt hat, dass sie "
    "abgeschlossen wurde – erledigt oder abgebrochen. Wer Aufgaben "
    "verteilt, erfährt so von selbst, wann etwas fertig ist.")
TEXTE_STANDARD["einst.erledigtmail_wozu"] = (
    "Benachrichtigt die Person, die eine Aufgabe angelegt hat, sobald sie"
    " erledigt ist. Wer Aufgaben verteilt, erfährt so automatisch, wann "
    "etwas fertig ist.")
TEXTE_STANDARD["einst.erledigtmail_hinweis"] = (
    "Die Nachricht geht innerhalb einer Minute raus. Wer eine Aufgabe "
    "selbst angelegt und selbst erledigt hat, bekommt keine Nachricht.")
TEXTE_STANDARD["einst.vorlagen_format"] = (
    "Jede Nachricht wird zweimal mitgeschickt: als reiner Text und als "
    "formatierte Fassung. Jedes Mailprogramm zeigt die Fassung an, die es"
    " darstellen kann.")
TEXTE_STANDARD["einst.fristmail_lead"] = (
    "Erinnert die zuständigen Personen an Fristen aus den Aufgaben. "
    "Erledigte Aufgaben werden nicht berücksichtigt.")
TEXTE_STANDARD["einst.fristmail_hinweis"] = (
    "Mit einem Vorlauf gibt es zwei Nachrichten pro Frist: eine "
    "Vorwarnung und, falls bis dahin nichts passiert, eine Erinnerung "
    "nach Ablauf der Frist. Wer zusätzlich informiert werden soll, "
    "bekommt dieselbe Nachricht.")
TEXTE_STANDARD["einst.bewilligungsmail_lead"] = (
    "Erinnert an Bewilligungen, die bald auslaufen, schon abgelaufen sind"
    " oder ganz fehlen. Es kommt eine gesammelte E-Mail pro Woche, nicht "
    "eine pro Person.")
TEXTE_STANDARD["einst.bewilligungsmail_hinweis"] = (
    "Der Vorlauf legt fest, ab wann eine Bewilligung als „läuft bald aus“"
    " gilt. Abgelaufene und fehlende Bewilligungen stehen immer mit in "
    "der E-Mail. Ein beantragter Folgebescheid erscheint erst, wenn er "
    "seit sechs Monaten aussteht.")
TEXTE_STANDARD["einst.fusszeile_lead"] = (
    "Die Zeile mit den Rechten ganz unten auf jeder Seite. Bleibt das "
    "Feld leer, gilt wieder der mitgelieferte Text.")
TEXTE_STANDARD["einst.fusszeile_hinweis"] = (
    "Programmname, Version und der Link zum Changelog stehen fest in der "
    "Zeile darüber und lassen sich nicht ändern.")
TEXTE_STANDARD["einst.texte_lead"] = (
    "Die erklärenden Texte der Oberfläche liegen in <code>strings.txt</code>. "
    "Diese Datei gewinnt gegen die ausgelieferten Texte – neue oder "
    "verbesserte Formulierungen aus einem Update kommen deshalb nicht "
    "von selbst an. „Fehlende Texte ergänzen“ trägt nur nach, was in der "
    "Datei noch gar nicht steht, und lässt eigene Änderungen in Ruhe.")
TEXTE_STANDARD["datenpflege.lead"] = (
    "Hier fasst du viele Einträge auf einen gemeinsamen Wert zusammen – "
    "zum Beispiel „AU“, „krank“ und „Krankheit“ zu einer Schreibweise. Es"
    " passiert nichts sofort: Zuerst siehst du eine Vorschau mit der "
    "Anzahl und einigen Beispielzeilen. Groß- und Kleinschreibung sowie "
    "Leerzeichen am Rand spielen beim Suchen keine Rolle.")
TEXTE_STANDARD["datenpflege.warnung"] = (
    "Was du hier änderst, gilt sofort für alle betroffenen Einträge – "
    "auch für die aus vergangenen Jahren, die längst gemeldet sind. Schau"
    " dir die Vorschau deshalb genau an, bevor du bestätigst.")
TEXTE_STANDARD["datenpflege.sicherung"] = (
    "Direkt vor der Änderung legt das Toolkit eine Kopie der Datenbank "
    "unter „System und Sicherung“ ab. Rückgängig machen lässt sich die "
    "Änderung nur darüber. Personen im Team oder betreute Personen werden"
    " dabei nie gelöscht, höchstens stillgelegt.")
TEXTE_STANDARD["login.lead"] = (
    "Mit Benutzername und Passwort anmelden, um fortzufahren.")
TEXTE_STANDARD["login.vergessen_lead"] = (
    "Gib deinen Benutzernamen oder deine E-Mail-Adresse ein. Ist für dein"
    " Konto eine Adresse hinterlegt, schicken wir dir einen Link, mit dem"
    " du ein neues Passwort festlegen kannst.")
TEXTE_STANDARD["login.vergessen_gesendet"] = (
    "Wenn es zu deiner Angabe ein Konto mit E-Mail-Adresse gibt, ist "
    "jetzt ein Link unterwegs. Er gilt 30 Minuten. Kommt nichts an, schau"
    " im Spam-Ordner nach oder wende dich an die Verwaltung.")
TEXTE_STANDARD["login.vergessen_aus"] = (
    "Ein neues Passwort per E-Mail ist hier nicht eingerichtet. Wende "
    "dich bitte an die Verwaltung – dort kann dein Passwort neu gesetzt "
    "werden.")
TEXTE_STANDARD["einst.passwortmail_wozu"] = (
    "Auf der Anmeldeseite steht dann „Passwort vergessen?“. Wer seinen "
    "Benutzernamen oder seine E-Mail-Adresse eingibt, bekommt einen Link "
    "an die Adresse des Kontos und kann damit ein neues Passwort "
    "festlegen. Der Link gilt 30 Minuten und nur einmal. Danach werden "
    "alle Anmeldungen des Kontos beendet, und eine Bestätigung geht an "
    "dieselbe Adresse.")
TEXTE_STANDARD["einst.passwortmail_adresse"] = (
    "Unter dieser Adresse ruft das Team das Toolkit auf, zum Beispiel "
    "http://192.168.1.20:8778 – so steht sie später im Link. Sie wird "
    "bewusst hier eingetragen: Würde sie aus der Anfrage gelesen, ließe "
    "sich ein Link auf einen fremden Server umlenken. Ohne Adresse bleibt"
    " die Funktion aus. Wer keine E-Mail-Adresse am Konto hat, bekommt "
    "keinen Link; das Passwort setzt dann weiterhin die Verwaltung.")
TEXTE_STANDARD["vorgaenge.verlauf_leer"] = "Noch keine Einträge."
TEXTE_STANDARD["vorgaenge.loeschen_hinweis"] = (
    "Der Vorgang verschwindet dabei vollständig, inklusive seines "
    "Verlaufs. Das lässt sich nicht rückgängig machen. Für einen "
    "abgeschlossenen Vorgang reicht in der Regel der Status „Erledigt“ "
    "oder „Abgebrochen“ – er bleibt dann in der Betreutenansicht als "
    "Archiv erhalten.")
# ⚠️ Neuer Schluessel statt Aenderung am alten (Abschnitt 8 der
# CLAUDE.md): "Abgebrochen" gibt es seit 1.33 nicht mehr, und unter dem
# alten Schluessel waere der berichtigte Wortlaut bei einer bestehenden
# strings.txt nie angekommen.
TEXTE_STANDARD["vorgaenge.loeschen"] = (
    "Die Aufgabe wird dabei vollständig gelöscht und lässt sich nicht "
    "wiederherstellen; ihr Verlauf bleibt im Logbuch erhalten. Für eine "
    "abgeschlossene Aufgabe reicht meistens der Status „Erledigt“ – sie "
    "bleibt dann als Archiv bei der betreuten Person sichtbar.")
TEXTE_STANDARD["vorgaenge.logbuch_leer"] = "Noch keine Einträge."
TEXTE_STANDARD["vorgaenge.person_keine_offenen"] = (
    "Für {name} ist gerade keine Aufgabe offen.")
TEXTE_STANDARD["vorgaenge.person_keine_archiviert"] = (
    "Bisher wurde nichts abgeschlossen.")
TEXTE_STANDARD["vorgaenge.person_kein_logbuch"] = (
    "Bisher sind keine organisatorischen Schritte festgehalten.")
TEXTE_STANDARD["datensaetze.nur_eigene"] = (
    "Auswählen kannst du nur deine eigenen Einträge.")
TEXTE_STANDARD["datensaetze.nur_eigene_bearbeiten"] = (
    "Bearbeiten kannst du ebenfalls nur deine eigenen.")
TEXTE_STANDARD["datensaetze.nichts_loeschbar"] = (
    "Hier stehen keine Einträge, die du löschen darfst.")
TEXTE_STANDARD["datensaetze.nichts_loeschbar_eigen"] = (
    "Hier stehen keine Einträge, die du löschen darfst – deine eigenen "
    "sind unter „{name}“ erfasst.")
TEXTE_STANDARD["kfz.bearbeiten_lead"] = (
    "Änderungen gelten sofort, auch in der Auswertung.")
TEXTE_STANDARD["kfz.faellig_zeitraum"] = (
    "Diese Liste richtet sich nach dem heutigen Tag. Der Zeitraumfilter "
    "oben wirkt hier bewusst nicht – was fällig ist, ist fällig.")
TEXTE_STANDARD["dateien.lead"] = (
    "Bilder, PDFs und Office-Dateien an einem Ort. Links steht die "
    "Ordnerstruktur – sie ist der Bestand. Zu jeder Datei gibt es einen "
    "fertigen Markdown-Schnipsel, den du ins Wiki einsetzen kannst.")
TEXTE_STANDARD["dateien.ablage"] = (
    "Alles liegt im Ordner <code>{pfad}</code>. Was du dort über die "
    "Dateifreigabe selbst ablegst, erscheint hier automatisch.")
TEXTE_STANDARD["dateien.erlaubt"] = (
    "Hochladen lassen sich {endungen} – höchstens {mb} MB je Datei. "
    "Gleichnamige Dateien werden nicht überschrieben, sondern "
    "durchnummeriert.")
TEXTE_STANDARD["dateien.ziehen"] = (
    "Einträge lassen sich mit der Maus in einen Ordner ziehen.")
TEXTE_STANDARD["dateien.baum_leer"] = (
    "Hier liegt noch nichts. Lade eine Datei hoch oder leg einen Ordner "
    "an.")
TEXTE_STANDARD["dateien.leer"] = (
    "In diesem Ordner liegt noch keine Datei.")
TEXTE_STANDARD["dateien.unbekannt"] = (
    "Diese Dateiart wird nicht unterstützt. Die Datei bleibt liegen und "
    "lässt sich umbenennen, verschieben oder löschen – öffnen oder ins "
    "Wiki einbinden kannst du sie aber nicht.")
TEXTE_STANDARD["wiki.baum_leer"] = (
    "Im Wiki liegt noch nichts. Über „Neu anlegen“ erstellst du die erste"
    " Seite oder den ersten Ordner.")
TEXTE_STANDARD["wiki.baum_leer_lesen"] = (
    "Im Wiki-Ordner liegt noch nichts. Anlegen darf nur, wer das Recht "
    "„Wiki bearbeiten“ hat.")
TEXTE_STANDARD["wiki.ziehen"] = (
    "Seiten und Ordner lassen sich im Baum mit der Maus auf einen anderen "
    "Ordner ziehen. Vor dem Verschieben wird nachgefragt.")
TEXTE_STANDARD["wiki.editor_lead"] = (
    "Geschrieben wird in Markdown. Dateiname und Ordner kannst du hier "
    "gleich mit ändern – beim Speichern wird die Seite dann umbenannt "
    "oder verschoben. Mit Strg+S (am Mac Cmd+S) speicherst du ebenfalls.")
TEXTE_STANDARD["wiki.ordner_leer"] = (
    "Dieser Ordner ist noch leer.")
TEXTE_STANDARD["wiki.suche_lead"] = (
    "Gib mindestens zwei Zeichen ein. Gesucht wird in den Dateinamen und "
    "im Text aller Seiten.")
TEXTE_STANDARD["wiki.suche_leer"] = (
    "Keine Seite enthält „{wort}“.")
TEXTE_STANDARD["wiki.fehlt"] = (
    "Unter „{pfad}“ gibt es keine Seite. Vielleicht wurde sie umbenannt, "
    "verschoben oder direkt auf dem Gerät gelöscht.")
# --- Fuhrpark ----------------------------------------------------------------

TEXTE_STANDARD["kfz.keine_fahrzeuge"] = (
    "Es ist noch kein Fahrzeug angelegt. Fahrzeuge legst du unter <a "
    "href=\"/einstellungen?bereich=kfz\">Einstellungen → Fahrzeuge</a> "
    "an, danach kannst du hier alles dazu erfassen.")
TEXTE_STANDARD["kfz.erfassen_lead"] = (
    "Wähl aus, was passiert ist – danach folgt ein kurzes Formular. "
    "Trägst du dabei einen Kilometerstand ein, zählt er automatisch als "
    "Kilometerstand des Fahrzeugs; du musst ihn nicht noch einmal extra "
    "erfassen.")
TEXTE_STANDARD["kfz.tanken_km_hinweis"] = (
    "Der Kilometerstand ist freiwillig. Ohne ihn zählt die Tankfüllung "
    "bei den Kosten mit, ergibt aber keinen Verbrauchswert. Die Liter "
    "gehen trotzdem nicht verloren: Sie zählen bei der nächsten "
    "Volltankung mit Kilometerstand mit.")
TEXTE_STANDARD["kfz.historie_leer"] = (
    "Für {fahrzeug} ist noch nichts erfasst. Am besten trägst du zuerst "
    "den aktuellen Kilometerstand ein.")
TEXTE_STANDARD["kfz.intervall_hinweis"] = (
    "Gib ein Intervall in Monaten <strong>oder</strong> in Kilometern an "
    "– gern auch beides. Fällig ist dann, was zuerst eintritt. Ein von "
    "Hand eingetragener Termin geht dem Intervall vor.")
TEXTE_STANDARD["kfz.nichts_faellig"] = (
    "Nichts ist überfällig, und in den nächsten 30 Tagen oder 1.000 "
    "Kilometern steht nichts an. Fälligkeiten entstehen aus den "
    "Intervallen, die du bei Wartung, Inspektion oder TÜV einträgst.")
TEXTE_STANDARD["kfz.kennzahlen_unvollstaendig"] = (
    "Kosten pro Kilometer und Verbrauch lassen sich erst berechnen, wenn "
    "genug Daten da sind: Kilometerstände über den Zeitraum und "
    "mindestens zwei Volltankungen. Fehlt etwas davon, steht hier lieber "
    "ein Strich als eine falsche Zahl.")
TEXTE_STANDARD["kfz.diagramm_leer"] = (
    "Für den Kostenverlauf braucht es Kosten aus mindestens zwei Monaten.")
TEXTE_STANDARD["kfz.kosten_leer"] = (
    "Für {zeitraum} sind keine Kosten erfasst.")
TEXTE_STANDARD["kfz.verbrauch_leer"] = (
    "Noch keine Verbrauchswerte. Ein Wert entsteht zwischen zwei "
    "Volltankungen – lass beim Tanken also den Haken „Vollgetankt“ "
    "gesetzt und trag den Kilometerstand mit ein.")
TEXTE_STANDARD["kfz.vergleich_hinweis"] = (
    "„Gefahren“ und „je km“ beziehen sich auf den gewählten Zeitraum und "
    "brauchen erfasste Kilometerstände. Der Verbrauch ist der "
    "Durchschnitt über alle ausgewerteten Tankfüllungen.")
TEXTE_STANDARD["kfz.aktivitaeten_leer"] = (
    "Für {zeitraum} ist nichts erfasst.")

TEXTE_STANDARD["einst.kfz_lead"] = (
    "Die Fahrzeuge eurer Einrichtung. Was hier steht, kannst du unter <a "
    "href=\"/fuhrpark\">Fuhrpark → Erfassung</a> auswählen und mit "
    "Tankvorgängen, Wartungen und Kosten füllen.")
TEXTE_STANDARD["einst.kfz_keine"] = (
    "Es ist noch kein Fahrzeug angelegt.")
TEXTE_STANDARD["einst.kfz_archiv_hinweis"] = (
    "Ein ausgemustertes Fahrzeug gehört ins Archiv, nicht in den "
    "Papierkorb: Archiviert verschwindet es aus allen Auswahlen und aus "
    "der Auswertung, seine Geschichte bleibt aber erhalten.")
TEXTE_STANDARD["einst.kfz_archiv"] = (
    "Archivierte Fahrzeuge erscheinen weder in der Erfassung noch in der "
    "Auswertung. Du kannst sie jederzeit zurückholen.")

TEXTE_STANDARD["footer.text"] = (
    "Dein Weg Toolkit <span class=\"version\">{version}</span>: Organisation "
    "für Menschen, die eigentlich nicht organisieren wollen.<br>"
    "© 2026 <a href=\"https://timovorwald.de\" target=\"_blank\" "
    "rel=\"noopener noreferrer\">timovorwald.de</a>. Alle Rechte vorbehalten.")

# --- Schluessel ohne Abnehmer ------------------------------------------------
#
# ⚠️ Diese Texte werden derzeit nirgends mehr abgerufen. Sie bleiben
# stehen, weil ein zurueckkehrender Text sonst neu geschrieben werden
# muesste - und weil `strings_anlegen()` sie in bestehende Dateien
# ohnehin schon geschrieben hat. Wer in strings.txt daran feilt, wundert
# sich aber, warum nichts passiert; deshalb stehen sie hier.
#
# ⚠️ Die Liste haelt die automatische Pruefung aktuell (test_texte_tot):
# wird ein Schluessel wieder gebraucht oder faellt ein neuer weg, schlaegt
# sie an. Ohne das verrottete diese Notiz binnen zweier Versionen.
UNGENUTZT = frozenset({
    # seit 2.2: die Auswertung hat zwei Unterseiten. Die Ampel erklärt
    # sich als Liste (auswertung.ampel_*), die Säulen stehen mit den
    # aufklappbaren Monaten in EINER Karte „Monat für Monat“.
    "auswertung.stand_erklaerung", "auswertung.titel.monatsliste",
    # seit dem Umbau 2.1: die Seitenspalte der Auswertung ist entfallen
    # („Stundenkontingent“ und „Bewilligt“ beantwortet jetzt der „Stand
    # der Bewilligungen“). Die Überschriften bleiben, damit eine schon
    # umbenannte Fassung in strings.txt nicht ins Leere zeigt.
    "auswertung.titel.kontingent", "auswertung.titel.bewilligt",
    "auswertung.bewilligt_lead",
    # seit 2.0: die Anmeldekarte grüßt nach der Tageszeit; der Satz
    # „Mit Benutzername und Passwort anmelden …" wiederholte nur die Felder.
    "login.lead",
    # seit 2.0: Hell/Dunkel und die Inhaltsbreite stehen in den neuen
    # Reglern der Darstellung (_darstellung.html), die sich selbst
    # erklären - die beiden Sätze darüber sind entfallen.
    "einst.ansicht",
    "einst.breite",
    # seit 1.49.1: die Regel ist umgekehrt - die Zeitspanne gewinnt,
    # solange niemand die Dauer selbst anfasst. Ersetzt durch
    # bearbeiten.dauer_regel.
    "bearbeiten.dauer_hinweis",
    # seit 1.57: die Dauer ist eine Anzeige, kein Eingabefeld mehr - "wer
    # sie selbst eintraegt" geht nicht mehr. Ersetzt durch
    # bearbeiten.dauer_rechnung.
    "bearbeiten.dauer_regel",
    # seit 1.44: der Abschnitt heisst "Branding" und traegt auch Favicon
    # und App-Symbol; der alte Wortlaut nannte die erklaerenden Texte,
    # die dort seit 1.37 nicht mehr stehen. Ersetzt durch
    # einst.system_branding.
    "einst.system_aussehen",
    # seit 1.43: die Tabelle "Zuletzt von Hand erfasst" ist durch das
    # Tagesprotokoll im Erfassungsformular ersetzt. Ihr Leer-Zustand galt
    # einer Person ("Noch nichts erfasst fuer {mitarbeiter}"), der neue
    # gilt einem TAG - das ist eine andere Aussage und deshalb ein neuer
    # Schluessel (erfassung.protokoll_leer).
    "erfassung.leer",
    "dateien.ablage",       # seit 1.1.2, Hinweise aus der Seitenleiste raus
    "dateien.erlaubt",      # dito
    "dateien.lead",         # dito
    "dateien.ziehen",       # seit 1.18.1
    # seit 1.32: der Text nennt jetzt vier Rechte und steht deshalb
    # unter einem NEUEN Schluessel (einst.benutzer_rechte) - eine
    # vorhandene strings.txt gewinnt sonst gegen die Aenderung.
    "einst.benutzer_rechte_hinweis",
    # seit 1.55: beide behaupteten, die Bereichsauswahl habe bei der
    # Rolle "Administrator" keine Wirkung. Genau das stimmt nicht mehr.
    # Ersetzt durch einst.benutzer_bereiche_regel bzw.
    # einst.benutzer_admin_regel.
    "einst.benutzer_bereiche_hinweis",
    "einst.benutzer_admin_hinweis",
    # seit 1.55: der Satz erklaerte, dass ein Klick auf die Zeile sie
    # zum Aendern oeffnet. Das sagt jetzt der Stift an der Zeile, und
    # zwar kuerzer.
    "auslagen.liste_lead",
    # seit 1.33: beide nennen "Abgebrochen", den Status gibt es nicht
    # mehr. Ersetzt durch vorgaenge.loeschen bzw. einst.erledigtmail_wozu.
    "einst.erledigtmail_lead",
    "vorgaenge.loeschen_hinweis",
    # seit 1.37: die Karte "Standardtexte" ist entfallen. Der Schluessel
    # bleibt stehen - wer eine eigene strings.txt hat, hat ihn womoeglich
    # umformuliert, und ein geloeschter Schluessel waere ein Datenverlust
    # ohne Gegenwert.
    "einst.texte_lead",
    # seit 1.40: der Punkt heisst "Texte und Bezeichnungen" und traegt
    # auch die Ueberschriften - der alte Lead sprach nur von erklaerenden
    # Texten. Ersetzt durch einst.texte_bezeichnungen_lead.
    "einst.hinweistexte_lead",
    # seit 1.38: „E-Mail-Versand" und „E-Mail-Vorlagen" sind ein Punkt.
    # Jeder Anlass traegt seinen Wortlaut selbst, ein eigener Hinweis je
    # Vorlage waere neben dem Lead des Anlasses die zweite Erklaerung
    # derselben Sache. Die beiden Lead-Texte nennen ausserdem "beide"
    # Nachrichten - es sind fuenf. Ersetzt durch einst.vorlagen_wortlaut
    # bzw. einst.vorlagen_ruecksetzen_alle.
    "einst.vorlagen_lead",
    "einst.vorlagen_zuruecksetzen",
    "einst.vorlage_frist_hinweis",
    "einst.vorlage_abgabe_hinweis",
    # seit 1.38: der Text behauptete, Urlaub und Krankheit blieben
    # unberuecksichtigt - seit 1.37 senken beide das Soll. Ein
    # berichtigter Wortlaut unter demselben Schluessel waere bei einer
    # bestehenden strings.txt nie angekommen (Abschnitt 8).
    "mein.tabelle_hinweis",
    "footer.text",          # seit 1.1.2, die Fusszeile kommt aus dem Markup
    "ideen.hinweis_datei",
    "ideen.hinweis_fehler",
    "logbuch.lead",         # seit 1.26, ersetzt durch logbuch.einleitung
    "start.upload",         # seit 1.25
    "start.upload_kurz",    # seit 1.24
    "vorgaenge.datei_hinweis",
    "vorgaenge.zustaendig_hinweis",  # seit 1.30, ersetzt durch _mehrere
    "wiki.baum_leer_lesen",
    "wiki.ziehen",
})
