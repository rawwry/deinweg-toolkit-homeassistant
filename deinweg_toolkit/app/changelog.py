"""Versionsverlauf der Anwendung.

Bewusst im Code und nicht in einer separaten Datei: so kommt die
Historie beim blossen Austausch des app-Ordners automatisch mit.
Ausgelagert aus main.py, weil es reine Daten sind.
"""

from __future__ import annotations

CHANGELOG = [
    {"version": "0.1", "titel": "Einführung der Versionierung", "punkte": [
        "Logo in Kopf- und Fußzeile, Farbwelt aus dem Logo übernommen",
        "Hell/Dunkel-Ansicht mit Schalter, Dunkel als Standard",
        "Manueller Eintrag: Datensätze ohne Import von Hand erfassen",
        "Betreute Personen mit wöchentlichem Stundenkontingent",
        "Soll-Ist-Vergleich in der Auswertung",
        "Zebrastreifen in allen Tabellen, dezente Animationen",
    ]},
    {"version": "0.2", "titel": "Zeiträume und Verdienst", "punkte": [
        "Stundensatz je betreuter Person",
        "Zeitraum in der Auswertung frei wählbar statt nur ein Monat",
        "Neue Box „Verdienst lfd. Monat“ mit Betrag je Person und Summe",
        "Spruch auf der Startseite kommt aus quotes.txt auf der NAS",
        "Nur noch die letzten zehn Importe, Rest über einen Knopf",
    ]},
    {"version": "0.2.1", "titel": "Feinschliff", "punkte": [
        "Zeitraum über vier Auswahlfelder statt Monatsfelder",
        "Sprüche ausschließlich aus quotes.txt, keine externe Quelle mehr",
        "Anzahl der Datensätze steht im Bestand oben, Stunden darunter",
    ]},
    {"version": "0.2.2", "titel": "Sprüche mit Struktur", "punkte": [
        "Sprüche werden an einer Zeile mit ## getrennt, Umbrüche bleiben erhalten",
    ]},
    {"version": "0.2.3", "titel": "Typografie", "punkte": [
        "Sprüche in Antiqua-Serifenschrift, Quellenzeile kleiner gesetzt",
        "Breitere Spruchzeile, mehr Abstand unter dem Fußlogo",
    ]},
    {"version": "0.2.4", "titel": "Spruch auch beim manuellen Eintrag", "punkte": [
        "Die Spruchzeile erscheint auf beiden Eingabeseiten",
    ]},
    {"version": "0.2.5", "titel": "Filter sichtbar machen", "punkte": [
        "Knopf „Filter entfernen“ in der Auswertung",
        "Aktive Filter werden als Markierung und Chipleiste angezeigt",
    ]},
    {"version": "0.2.6", "titel": "Gesamtübersicht als Standard", "punkte": [
        "Auswertung öffnet über alle erfassten Zeiten statt nur den laufenden Monat",
        "Fehler behoben: Link in der Monatsbox hatte nicht mehr gefiltert",
    ]},
    {"version": "0.2.7", "titel": "Lesbare Summen", "punkte": [
        "Große Summen als „5.341 Std 58 Min“ statt als vermeintliche Uhrzeit",
    ]},
    {"version": "0.2.8", "titel": "Kontingente nach Vorgabe", "punkte": [
        "Monatssoll über Faktor 4,33 statt über Kalendertage",
        "Alle Sollwerte auf 15 Minuten gerundet",
    ]},
    {"version": "0.2.9", "titel": "Blättern und Neustart", "punkte": [
        "Seitenzahlen bei den Datensätzen mit Angabe der Gesamtmenge",
        "Fehler behoben: zu hohe Seitenzahl in der Adresse ergab eine leere Tabelle",
        "Container startet nach Absturz und Neustart der NAS von selbst wieder",
    ]},
    {"version": "0.3", "titel": "Erste finale Fassung", "punkte": [
        "Filterbereich, Menü und Themenschalter auf die bewährte Darstellung zurückgesetzt",
        "Auswertungsbox nennt Zeitraum, gefilterte Person und Anzahl der Personen",
        "Paginierung an die übrige Oberfläche angepasst",
    ]},
    {"version": "0.3.1", "titel": "Ideen und Protokoll", "punkte": [
        "Neue Seite „Ideen“ als kleines Ticketsystem, Einträge landen in ideen.txt",
        "Neue Seite „Changelog“",
        "„Einträge“ heißt jetzt „Datensätze“, Menü neu sortiert",
        "Inhaltsbereich nutzt die volle Fensterbreite",
    ]},
    {"version": "0.3.2", "titel": "Einstellungen mit Abschnitten", "punkte": [
        "Einstellungen unterteilt in Oberfläche, Betreute Personen und Systeminformationen",
        "Inhaltsbreite umschaltbar zwischen voller und begrenzter Darstellung",
        "Systeminformationen zeigen Bestand, Pfade und Zustand der Textdateien",
        "Stylesheet trägt die Versionsnummer, damit Browser keine alte Fassung behalten",
        "Textfeld auf der Ideenseite läuft über die volle Breite",
    ]},
    {"version": "0.3.3", "titel": "Menü mit Symbolen", "punkte": [
        "Ideen, Changelog und Einstellungen als Symbole rechts in der Kopfzeile",
        "Einstellungen zeigen nur noch den gewählten Bereich statt alles untereinander",
        "Fehler behoben: der Themenschalter in den Einstellungen reagierte nicht, "
        "weil die Kennung doppelt vorkam",
        "Changelog steckt jetzt in der Anwendung statt in einer Textdatei – "
        "beim Austausch des app-Ordners kommt er automatisch mit",
    ]},
    {"version": "0.3.4", "titel": "Ideen verwalten", "punkte": [
        "Eingegangene Ideen lassen sich bearbeiten und entfernen",
        "Liste der Ideen ist so breit wie die Karte darüber",
        "Hinweis in der Auswertung verlinkt direkt auf die betreuten Personen "
        "und nennt die Rechnung mit Faktor 4,33",
    ]},
    {"version": "0.3.5", "titel": "Wer hat abgegeben", "punkte": [
        "Abgabeübersicht auf der Startseite: wer für den Monat Zeiten abgegeben "
        "hat und wer nicht, mit Fortschrittsbalken und Fehlliste",
        "Monat in der Übersicht umschaltbar",
        "Neuer Einstellungsbereich „Mitarbeiter“ zum Anlegen und Pflegen des Teams",
        "Abweichende Schreibweisen in den Daten werden gemeldet",
    ]},
    {"version": "0.3.6", "titel": "Abgaben dezenter", "punkte": [
        "Abgabeübersicht sitzt kompakt in der Seitenspalte statt breit über der Seite",
    ]},
    {"version": "0.3.7", "titel": "Aufgeräumte Startseite", "punkte": [
        "Importordner-Box von der Startseite in die Systeminformationen verschoben",
        "Fehlende Abgaben rot markiert und deutlicher beschriftet",
        "Fußzeile verweist auf timovorwald.de",
    ]},
    {"version": "0.3.8", "titel": "Ein Filter für alles", "punkte": [
        "Stundenkontingent und Verdienst richten sich nach dem gewählten Filter "
        "statt immer den laufenden Monat zu zeigen",
        "Datensätze und Auswertung nutzen denselben Filter, beide mit Suchfeld",
        "Box „Monatliche Gesamtstunden“ entfernt",
        "Export übernimmt den Zeitraum in den Dateinamen",
    ]},
    {"version": "0.3.9", "titel": "Zeitraum auch halb ausgefüllt", "punkte": [
        "Fehler behoben: ein Monat ohne Jahreszahl wurde stillschweigend ignoriert, "
        "die Auswertung zeigte weiter alle Zeiten",
        "Jahr ohne Monat meint jetzt das ganze Jahr, Monat ohne Jahr denselben "
        "Monat in allen Jahren",
        "Das Soll richtet sich nach den Monaten, die der Filter wirklich abdeckt",
        "Suchfeld in der Auswertung ausgeblendet",
    ]},
    {"version": "0.3.10", "titel": "Menü für unterwegs und eigene Texte", "punkte": [
        "Burger-Menü auf Handy und Tablet, das von rechts hereinfährt",
        "Alle erklärenden Texte stehen in strings.txt und sind selbst änderbar, "
        "Änderungen wirken sofort ohne Neustart",
        "Passwortschutz im Stack voreingestellt",
    ]},
    {"version": "0.3.11", "titel": "Feinschliff und App-Icon", "punkte": [
        "Ideen-Seite: Formularkarte über die volle Breite, Rückmeldungen als "
        "Liste statt Kacheln, Box „Wie es weitergeht“ entfernt",
        "Einstellungen: „Ansicht“ heißt jetzt „Darkmode“",
        "Erklärende Texte laufen überall in einer festen Lesebreite, auch bei "
        "voller Fensterbreite",
        "Eigenes App-Icon für den iPhone-Homescreen und den Browser-Tab, "
        "Browsertitel jetzt „Dein Weg Toolkit – Seitenname“",
        "Mobiles Menü fährt von oben ein, mit eigenem Schließen-Knopf",
        "Zwei versehentlich doppelt vorhandene CSS-Abschnitte bereinigt",
    ]},
    {"version": "0.4", "titel": "Verwaltungsvorgänge", "punkte": [
        "Neuer Menüpunkt „Verwaltungsvorgänge“: Anträge, Berichte, "
        "Fortschreibungen, Rückmeldungen des LWL und andere organisatorische "
        "Vorgänge rund um betreute Personen dokumentieren und nachverfolgen",
        "Übersicht mit Kennzahlen für überfällige, heute und bald fällige "
        "Vorgänge sowie für alles, wo auf eine Rückmeldung gewartet wird",
        "Filter nach betreuter Person, Zuständigkeit, Status, Vorgangsart, "
        "Frist und Zustand, dazu acht Sortierungen",
        "Sieben Status von „Offen“ bis „Abgebrochen“, farblich unterscheidbar",
        "Betreutenansicht mit laufenden Vorgängen, dem Archiv der erledigten "
        "und einem fortlaufenden Logbuch aller organisatorischen Schritte",
        "Jede Änderung schreibt einen Logbucheintrag mit Zeitpunkt, Name, "
        "Vorgang und Beschreibung – nichts wird überschrieben",
        "Betreute Personen werden hier nicht neu angelegt, sondern kommen "
        "aus den hochgeladenen Arbeitslisten",
        "Fehler behoben: der Schließen-Knopf im mobilen Menü reagierte nicht, "
        "weil die abdunkelnde Fläche dahinter fehlte",
    ]},
    {"version": "0.4.1", "titel": "Feinschliff Datensätze", "punkte": [
        "Datensätze: größerer Abstand zwischen den Filterknöpfen, der "
        "Anzeige aktiver Filter und den Export-Knöpfen, auf dem Smartphone "
        "zusätzlich vertikal statt gedrängt nebeneinander",
        "Knopf „In Export-Ordner ablegen“ entfernt",
    ]},
    {"version": "0.4.2", "titel": "Kopfzeile aufgeräumt", "punkte": [
        "Fehler behoben: der Schließen-Knopf des mobilen Menüs war auf "
        "breiten Bildschirmen fälschlich sichtbar und tauchte als leere, "
        "unstyled Box zwischen Logo und Navigation auf",
    ]},
    {"version": "0.4.3", "titel": "Eigene Vorgangsarten", "punkte": [
        "Vorgangsarten für die Verwaltungsvorgänge sind nicht mehr fest "
        "vorgegeben, sondern unter Einstellungen → Verwaltungsvorgänge frei "
        "anlegbar, umbenennbar und stillzulegen",
        "Beim allerersten Start weiterhin mit den bisherigen elf "
        "Vorgangsarten vorbefüllt, ab dann frei veränderbar",
        "Stillgelegte Vorgangsarten verschwinden aus der Auswahl beim "
        "Anlegen, bleiben an bestehenden Vorgängen aber weiter sichtbar "
        "und auswählbar",
    ]},
    {"version": "0.4.4", "titel": "Vorgänge löschen, Formular aufgeräumt", "punkte": [
        "Verwaltungsvorgänge lassen sich jetzt endgültig löschen, sowohl "
        "aus der Übersicht als auch auf der Detailseite, inklusive ihres "
        "Logbuchs – für Vorgänge, die falsch angelegt wurden oder schlicht "
        "nicht mehr relevant sind. Für abgeschlossene Vorgänge reicht "
        "weiterhin der Status „Erledigt“ oder „Abgebrochen“, wenn sie im "
        "Archiv der betreuten Person erhalten bleiben sollen",
        "Fehler behoben: der Knopf „Neuen Vorgang anlegen“ tat nichts, "
        "weil ein reiner Sprung-Anker den geschlossenen Formularbereich "
        "nicht öffnete",
        "Dokumentenverweis aus dem Anlegen-Formular entfernt, das Feld "
        "bleibt über „Angaben zum Vorgang bearbeiten“ weiterhin erreichbar",
        "Größere, gleichmäßigere Abstände zwischen den Formularreihen in "
        "allen Formularen der Anwendung, nicht nur bei den "
        "Verwaltungsvorgängen",
        "Fehler behoben: die Rücksprungadresse nach dem Löschen eines "
        "Vorgangs war fehlerhaft zusammengesetzt, wenn sie bereits einen "
        "Filter enthielt",
    ]},
    {"version": "0.5", "titel": "Benutzerkonten und Zugriffsrechte", "punkte": [
        "Das bisher einzige gemeinsame Passwort wird durch echte "
        "Benutzerkonten mit eigenem Login ersetzt – neuer Anmeldebildschirm, "
        "Passwörter werden sicher gehasht (scrypt) statt im Klartext",
        "Neuer Einstellungsbereich „Benutzerverwaltung“ (nur für "
        "Administratoren): Konten anlegen, umbenennen, Passwort setzen, "
        "deaktivieren oder endgültig löschen, optional mit E-Mail-Adresse",
        "Zwei Rollen: Administrator mit vollem Zugriff, und Benutzer, "
        "dessen Zugriff auf einzelne Bereiche (Listenimport, Manuelle "
        "Einträge, Datensätze, Auswertung, Verwaltungsvorgänge, Ideen, "
        "Einstellungen) eingeschränkt werden kann",
        "Die Zugriffsprüfung sitzt serverseitig an der tatsächlichen "
        "Programmstelle, nicht nur in der Navigation – ein nicht "
        "freigegebener Bereich lässt sich auch nicht über eine direkt "
        "eingegebene Adresse erreichen",
        "Beim allerersten Start wird automatisch ein Administrator-Konto "
        "angelegt; ohne gesetztes Passwort erscheint ein einmaliges, "
        "zufällig erzeugtes Passwort im Log des Containers",
        "„Mitarbeiter“ (für die Abgabeübersicht) und „Benutzer“ (für den "
        "Login) bleiben zwei getrennte Dinge – ein Mitarbeiter braucht "
        "keinen Login, ein Login muss keinem Mitarbeiter entsprechen",
    ]},
    {"version": "0.5.1", "titel": "Feinschliff Benutzerverwaltung", "punkte": [
        "Keine Mindestlänge für Passwörter mehr",
        "Fehler behoben: Passwort- und E-Mail-Felder sahen unformatiert "
        "aus (Anmeldeseite und Benutzerverwaltung), weil die allgemeine "
        "Formatierung für Textfelder diese beiden Feldtypen nicht erfasste",
        "Systeminformationen: Zeile „Importordner“ aus der Pfadliste "
        "entfernt (der Funktionsblock mit „Importordner jetzt prüfen“ "
        "bleibt unverändert)",
        "Fußzeile neu formuliert",
    ]},
    {"version": "0.5.2", "titel": "Feinschliff Verwaltungsvorgänge", "punkte": [
        "Übersicht zeigt jetzt standardmäßig alle Vorgänge statt nur die "
        "offenen",
        "Erledigte und abgebrochene Vorgänge werden in der Liste dezent "
        "grün hervorgehoben, analog zu überfälligen Vorgängen in Rot",
        "Filter „Frist / Wiedervorlage“ und „Zustand“ aus dem Filterformular "
        "entfernt – die Kennzahlen oben auf der Seite (überfällig, heute "
        "fällig, wartend, erledigt) führen weiterhin gezielt zur jeweiligen "
        "Ansicht",
    ]},
    {"version": "0.5.3", "titel": "Layout-Fix und weitere Texte auslagerbar", "punkte": [
        "Fehler behoben: ein seitlicher Scrollbalken über die ganze Seite "
        "erschien, sobald eine Tabelle (z. B. die Vorgangsliste) minimal "
        "breiter war als ihr Kasten – betraf potenziell jede breite "
        "Tabelle in der Anwendung",
        "Logbuch-Filter „Mitarbeitende Person“ umbenannt in „Involvierter "
        "Mitarbeiter“",
        "Weitere Texte, die bislang fest im Code standen, lassen sich jetzt "
        "über strings.txt anpassen: Anmeldeseite, die \"leer\"-Meldungen und "
        "der Löschen-Hinweis bei den Verwaltungsvorgängen, sowie der "
        "Text in der Fußzeile",
    ]},
    {"version": "0.5.4", "titel": "Scrollbalken endgültig behoben", "punkte": [
        "Fehler behoben: ein seitlicher Scrollbalken über die gesamte "
        "Seite blieb bestehen, weil der vorherige Fix nur die Kinder des "
        "Hauptbereichs erfasste – Kopfzeile und Fußzeile sind ebenfalls "
        "Flex-Elemente von body und brauchten dieselbe Korrektur",
        "Zusätzlich eine zuverlässige Absicherung ergänzt, die einen "
        "seitlichen Scrollbalken auf der gesamten Seite von vornherein "
        "ausschließt, unabhängig davon, welches einzelne Element im "
        "Zweifel doch einmal zu breit wird",
    ]},
    {"version": "0.5.5", "titel": "Layout-Feinschliff", "punkte": [
        "Auf breiten Bildschirmen dehnten sich Kästen bislang unbegrenzt "
        "aus, während Erklärtexte bewusst auf eine lesbare Zeilenlänge "
        "begrenzt sind – dadurch entstand viel Leerraum neben dem Text. "
        "Der Hauptbereich der Seite hat jetzt auch in der Einstellung "
        "„volle Breite“ eine großzügige Höchstbreite, und Erklärtexte "
        "dürfen etwas breiter laufen als bisher",
        "Verwaltungsvorgänge: der Beschreibungstext in der Liste wird "
        "jetzt vollständig angezeigt statt nach 90 Zeichen abgeschnitten",
        "Verwaltungsvorgänge: die Status-Spalte ist jetzt konsequent "
        "linksbündig wie die übrigen Spalten, auf der Übersicht wie auch "
        "in der Betreutenansicht",
    ]},
    {"version": "0.5.6", "titel": "Listenimport & Auswertung aufgeräumt", "punkte": [
        "Startseite: zurückgenommene Importe werden in „Letzte Importe“ "
        "und „Alle Importe“ nicht mehr aufgeführt",
        "Startseite: Spalte „Einträge“ in der Import-Liste linksbündig",
        "Startseite: die Knöpfe „anzeigen“ und „zurücknehmen“ sind jetzt "
        "kompakte Icons (Auge / Mülleimer), die Sicherheitsabfrage vor "
        "dem Zurücknehmen bleibt unverändert bestehen",
        "Startseite: in der Abgaben-Box steht die Spalte mit Zeit bzw. "
        "Status jetzt linksbündig statt an den rechten Rand gedrückt, "
        "„fehlt!“ heißt jetzt „ausstehend“",
        "Auswertung und Datensätze: die Filterfelder sind etwas schmaler, "
        "damit auf normal breiten Bildschirmen alle Felder in eine Zeile "
        "passen, statt dass einzelne Felder umbrechen",
    ]},
    {"version": "0.5.7", "titel": "Auslieferung korrigiert", "punkte": [
        "Das Paket der Version 2.0.6 war fehlerhaft zusammengestellt: es "
        "enthielt bei sieben Dateien noch einen älteren Stand. Dadurch "
        "fehlten in der eingespielten Fassung unter anderem die "
        "Abrechenbar-Spalte bei den betreuten Personen, der Filter "
        "„nur abrechenbare Zeiten“ auf der Auswertung sowie mehrere "
        "Layout-Korrekturen. Dieses Paket enthält alles vollständig",
        "Einstellungen → Betreute Personen: die Spalte „Notiz“ ist durch "
        "ein Ankreuzfeld „Abrechenbar“ ersetzt, mit dem sich für jede "
        "betreute Person einzeln festlegen lässt, ob ihre Zeiten als "
        "abrechenbar gelten – genau wie beim Feld „Aktiv“ daneben",
        "Das Notizfeld im Formular zum Anlegen einer betreuten Person "
        "ist ebenfalls entfallen und durch das Ankreuzfeld ersetzt",
    ]},
    {"version": "0.5.8", "titel": "Icons statt Textknöpfe, weiterer Feinschliff", "punkte": [
        "Startseite: die Spalte mit Zeit bzw. Status in der Abgaben-Box "
        "ist jetzt zentriert statt rechtsbündig",
        "Datensätze, manuelle Erfassung, Ideen sowie Verwaltungsvorgänge "
        "(Übersicht und Betreutenansicht): die Knöpfe „bearbeiten“/"
        "„löschen“ bzw. „öffnen“/„löschen“ sind durchgängig kompakte Icons "
        "(Stift, Auge, Mülleimer) statt Textknöpfe – die "
        "Sicherheitsabfragen vor dem Löschen bleiben überall bestehen",
        "Datensätze: in der Kopfzeile steht jetzt zuerst die Anzahl der "
        "Einträge, danach die Gesamtzeit",
        "Auswertung: der Filter „nur abrechenbare Zeiten“ ist beim ersten "
        "Aufruf der Seite standardmäßig angehakt, lässt sich aber über "
        "das Filterformular weiterhin gezielt abwählen",
    ]},
    {"version": "0.5.9", "titel": "Auswertung: Standard-Haken zurückgenommen", "punkte": [
        "Der in 0.5.8 eingeführte automatisch gesetzte Haken bei „nur "
        "abrechenbare Zeiten“ auf der Auswertungsseite ist auf Wunsch "
        "wieder zurückgenommen – der Filter startet jetzt wieder "
        "unangehakt wie vor 2.0.8, lässt sich aber weiterhin manuell "
        "setzen",
    ]},
    {"version": "0.6", "titel": "E-Mail-Erinnerungen und Datensicherung", "punkte": [
        "Neuer Einstellungsbereich „E-Mail-Versand“: Postausgangsserver, "
        "Absender und Zugangsdaten hinterlegen, mit Testnachricht zum "
        "Ausprobieren. Das Passwort wird in der Oberfläche nie im Klartext "
        "angezeigt",
        "Neuer Einstellungsbereich „E-Mail-Vorlagen“: Betreff und Text "
        "beider Erinnerungen frei anpassbar, mit Platzhaltern für Name, "
        "Vorgang, Frist und Monat, sowie einem Knopf zum Zurücksetzen",
        "Erinnerung bei überfälliger Frist: Wird die Wiedervorlage eines "
        "Verwaltungsvorgangs überschritten, erhält die zuständige Person "
        "automatisch eine Nachricht",
        "Erinnerung zum Monatsanfang: Wer für den abgelaufenen Monat noch "
        "keine Zeiten eingereicht hat, wird automatisch erinnert",
        "Jede Erinnerung wird nur einmal verschickt; wird eine Frist "
        "verschoben, kann erneut erinnert werden. Der Versandverlauf ist "
        "in den Einstellungen einsehbar",
        "Neu in „System“: Datenbank als Sicherung herunterladen und eine "
        "Sicherung wieder einspielen. Vor dem Einspielen wird geprüft, ob "
        "die Datei überhaupt zum Tool passt; die bisherige Datenbank wird "
        "zur Sicherheit daneben abgelegt statt überschrieben",
        "„Systeminformationen“ heißt jetzt „System“",
        "Fehler behoben: die Filter-Schaltfläche „nur abrechenbare Zeiten“ "
        "war breiter als ihre Spalte und überlappte das Feld daneben",
    ]},
    {"version": "0.6.1", "titel": "Benutzerkonto einem Mitarbeiter zuordnen", "punkte": [
        "Neues Auswahlfeld „Gehört zu Mitarbeiter“ im Benutzerkonto: legt "
        "eindeutig fest, für wen ein Konto Erinnerungen erhält – auch wenn "
        "der Benutzername anders lautet als der Name im Team",
        "Ohne gesetzte Zuordnung greift weiterhin der bisherige Weg über "
        "Namensgleichheit, bestehende Konten funktionieren also unverändert "
        "weiter",
        "In der Benutzerliste ist auf einen Blick erkennbar, ob ein Konto "
        "Erinnerungen erhält, nur über Namensgleichheit gefunden wird oder "
        "mangels E-Mail-Adresse gar nicht erreichbar ist",
    ]},
    {"version": "0.6.2", "titel": "Monatssoll und persönlicher Bereich", "punkte": [
        "Einstellungen → Mitarbeiter: neues Feld „Std/Monat“ für die "
        "monatliche Arbeitszeit, beim Anlegen wie in der Team-Tabelle",
        "Neuer Menüpunkt „Mein Bereich“: jede angemeldete Person sieht dort "
        "ihre eigenen Zahlen – Überstunden oder offene Stunden, Soll und Ist "
        "je Monat sowie eine Monatsübersicht",
        "Der laufende Monat wird getrennt ausgewiesen und zählt nicht in den "
        "Saldo, sonst stünde man am Monatsanfang immer tief im Minus",
        "Monate ohne erfasste Zeiten erscheinen bewusst mit dem vollen Soll "
        "im Minus, damit vergessene Abgaben auffallen",
        "Ist kein Monatssoll hinterlegt, wird kein Saldo berechnet und "
        "stattdessen ein Hinweis angezeigt",
        "Die Zuordnung Konto → Mitarbeiter aus 2.1.1 steuert auch, wessen "
        "Zahlen im persönlichen Bereich erscheinen",
        "Fehler behoben: die Zuordnung fehlte in den Sitzungsdaten, wodurch "
        "der persönliche Bereich eine Fehlerseite ausgelöst hätte",
    ]},
    {"version": "0.6.3", "titel": "Diagramm im persönlichen Bereich", "punkte": [
        "Neues Verlaufsdiagramm in „Mein Bereich“: ein Balken je Monat, "
        "grün bei erreichtem Soll und rot darunter, dazu das Monatssoll "
        "als gestrichelte Linie und der aufsummierte Saldo als Kurve",
        "Fehler behoben: die Monatsübersicht war etwas zu breit und "
        "erzeugte einen seitlichen Scrollbalken. Die Zeiten stehen jetzt "
        "im kompakten Format Std:Min statt ausgeschrieben",
    ]},
    {"version": "0.6.4", "titel": "Urlaubsverwaltung", "punkte": [
        "Einstellungen → Mitarbeiter: neues Feld „Urlaub/Jahr“ für den "
        "Urlaubsanspruch in Tagen pro Kalenderjahr",
        "„Mein Bereich“ zeigt genommene und verbleibende Urlaubstage des "
        "laufenden Jahres mit Fortschrittsbalken, dazu die Vorjahre",
        "Gezählt werden Tage mit einem Eintrag, dessen Beschreibung mit "
        "„Urlaub“ beginnt – ein Kalendertag zählt einmal, auch bei "
        "mehreren Zeilen am selben Tag",
        "Wird der Anspruch überschritten, färbt sich die Anzeige rot und "
        "nennt die Anzahl der Tage darüber",
        "Das Verlaufsdiagramm nimmt nicht mehr die volle Breite ein, "
        "sondern steht als kompakte Karte neben der Urlaubsübersicht",
    ]},
    {"version": "0.6.5", "titel": "Mein Bereich aufgeräumt", "punkte": [
        "Die Kachel „Stand“ mit dem über alle Monate aufsummierten Saldo "
        "ist ersetzt durch „Letzter abgeschlossener Monat“: Saldo des "
        "Vormonats, dazu die letzten drei Monate einzeln und der "
        "Monatsschnitt – daraus lässt sich ablesen, ob man gerade "
        "regelmäßig über oder unter dem Soll liegt",
        "Der aufsummierte Gesamtsaldo ist auch aus der Kopfzeile entfernt",
        "Mehr Abstand unter dem Urlaubsbalken",
        "Fehler behoben: Karten mit Tabellen hatten zwei ineinander "
        "liegende Scroll-Bereiche, wodurch schon bei minimaler Überbreite "
        "ein seitlicher Balken auftauchte. Lange Texte in Tabellenzellen "
        "brechen jetzt zusätzlich um, statt die Tabelle zu verbreitern",
        "„Mein Bereich“ steht nicht mehr in der Navigation, sondern als "
        "Benutzersymbol rechts neben dem Abmelden-Knopf",
        "Einstellungen → Mitarbeiter: Spalte „Notiz“ aus der Team-Tabelle "
        "entfernt. Bereits hinterlegte Notizen bleiben gespeichert und "
        "gehen beim Bearbeiten einer Zeile nicht verloren",
    ]},
    {"version": "0.6.6", "titel": "Scrollbalken in Tabellen endgültig weg", "punkte": [
        "Die Tabellen in „Mein Bereich“ und bei den Verwaltungsvorgängen "
        "ließen sich mit dem Trackpad noch einige Pixel seitlich "
        "verschieben. Sie haben jetzt eine feste Spaltenaufteilung und "
        "können dadurch rechnerisch nicht mehr breiter werden als ihre "
        "Karte – der Scrollbereich entfällt damit ganz, statt nur selten "
        "sichtbar zu sein",
        "Lange, nicht trennbare Wörter brechen in diesen Tabellen um, "
        "statt die Spalten auseinanderzudrücken",
        "„Mein Bereich“: mehr Abstand zwischen der großen Zahl der "
        "verbleibenden Urlaubstage und dem Wort „übrig“",
    ]},
    {"version": "0.6.7", "titel": "Dein Weg Toolkit", "punkte": [
        "Die Anwendung heißt jetzt „Dein Weg Toolkit“ – auch Container, "
        "Hostname und Pfade im Portainer-Stack sind umbenannt. Gespeicherte "
        "Einstellungen wie Dark Mode und Inhaltsbreite werden dabei "
        "automatisch übernommen",
        "Zwei zusätzliche Volumes (/kfz und /stammdaten) im Stack "
        "vorbereitet, noch ohne Funktion",
        "Listenimport: die Liste der zuletzt hochgeladenen Dateien ist "
        "entfallen. An ihrer Stelle steht nur noch, was tatsächlich auf "
        "eine Prüfung wartet",
        "Hochgeladene Dateien werden nicht mehr ins Archiv kopiert – die "
        "Zeilen stehen ohnehin in der Datenbank",
        "Listenimport: der Mitarbeitername ist Pflicht und gilt immer, "
        "auch wenn die Datei eine eigene Spalte mitbringt. Die frühere "
        "Rückfrage dazu ist entfallen",
        "Erklärtexte laufen über die volle Kartenbreite statt auf eine "
        "Lesebreite begrenzt zu sein",
    ]},
    {"version": "0.6.8", "titel": "Automatische Prüfung und Aufräumen", "punkte": [
        "Neu: eine automatische Prüfung, die in einem Rutsch kontrolliert, "
        "ob jede Seite lädt, die Anmeldung greift, die Zugriffsrechte "
        "halten, alle Vorlagen fehlerfrei sind und der Weg vom Hochladen "
        "bis in den Bestand funktioniert – 76 Einzelprüfungen, Aufruf über "
        "pruefen.sh",
        "main.py von rund 3.000 auf gut 1.600 Zeilen verkleinert: "
        "Änderungsprotokoll, Standardtexte und der gesamte "
        "Einstellungsbereich liegen jetzt in eigenen Dateien",
        "Das Volume /stamm heißt jetzt /texte – es enthält die "
        "bearbeitbaren Textdateien und war neben dem neuen Ordner "
        "stammdaten missverständlich",
    ]},
    {"version": "0.6.9", "titel": "Einheitliche Leistungen, ruhigere Tabellen",
     "punkte": [
        "Neu: vordefinierte Leistungsbeschreibungen. Unter Einstellungen → "
        "Leistungsbeschreibungen gepflegt, beim manuellen Eintrag als "
        "Auswahlfeld verfügbar. Damit steht dieselbe Leistung nicht mehr in "
        "fünf Schreibweisen im Bestand",
        "Das freie Textfeld beim manuellen Eintrag heißt jetzt „Eigene "
        "Beschreibung“ und ergänzt die Auswahl, statt sie zu ersetzen",
        "Bereits vorhandene Beschreibungen aus den erfassten Zeiten lassen "
        "sich in den Einstellungen mit einem Klick in die Auswahl übernehmen",
        "Fehler behoben: die Filterfelder hörten auf breiten Bildschirmen "
        "auf halber Strecke auf, statt die volle Breite der Karte zu nutzen. "
        "Betraf Datensätze, Auswertung, Verwaltungsvorgänge und das Logbuch",
        "Fehler behoben: ein langer Status wie „Warten auf Rückmeldung“ lief "
        "in der Vorgangsliste aus seiner Spalte heraus und legte sich über "
        "die Zuständigkeit. Lange Statusangaben brechen jetzt um",
        "Vorgangsliste: die Spalte „Vorgang“ ist deutlich breiter, die "
        "Spalte mit den beiden Knöpfen schmaler und heißt jetzt „Aktion“",
        "Ein weiteres Volume (/files) im Stack vorbereitet, noch ohne Funktion",
    ]},
    {"version": "0.6.10", "titel": "Eine Zeiterfassung statt zwei Seiten", "punkte": [
        "„Listenimport“ und „Manueller Eintrag“ sind zu einem Menüpunkt "
        "„Zeiterfassung“ zusammengefasst. Der manuelle Eintrag steht oben, "
        "das Einlesen von Listen darunter, „Bestand“ und „Abgaben“ "
        "unverändert daneben",
        "Datensätze: mehrere Einträge ankreuzen und gesammelt löschen – mit "
        "Sicherheitsabfrage, die die Anzahl nennt",
        "Der automatische Import über den Importordner (Watchfolder) ist "
        "entfallen. Eingelesen wird ausschließlich über den Upload. Die "
        "Volumes /import und /archiv sowie die Einstellungen "
        "WATCH_INTERVALL und AUTO_UEBERNEHMEN sind damit hinfällig",
        "Verwaltungsvorgang: der Verlauf steht jetzt direkt unter der "
        "Detailansicht statt weiter unten",
        "Verwaltungsvorgang: die Beschriftung „Wiedervorlage“ brach um und "
        "verschob das Feld darunter – der Zusatz ist gekürzt",
        "Fehler behoben: die Fußzeile klebte auf sehr breiten Fenstern "
        "links, während das Logo darüber mittig blieb",
    ]},
    {"version": "0.7", "titel": "Wiki", "punkte": [
        "Neuer Menüpunkt „Wiki“: die Wissensbasis des Teams, aufgebaut aus "
        "Markdown-Dateien im Ordner /wiki auf der NAS. Die Ordnerstruktur "
        "ist die Struktur des Wikis und steht links als Navigationsbaum",
        "Seiten lassen sich direkt im Browser bearbeiten – oder weiterhin "
        "mit jedem Editor über die Dateifreigabe. Beides greift auf "
        "dieselben Dateien zu",
        "Seiten und Ordner lassen sich im Baum mit der Maus in einen "
        "anderen Ordner ziehen. Vor dem Verschieben wird nachgefragt",
        "Neue Seiten und Ordner anlegen, Seiten umbenennen und löschen – "
        "das Löschen fragt nach, ein Ordner lässt sich nur entfernen, "
        "wenn er leer ist",
        "Volltextsuche über alle Seiten",
        "Wird eine Datei zwischenzeitlich von außen geändert, überschreibt "
        "das Speichern sie nicht mehr stillschweigend, sondern meldet es",
        "Markdown wird ohne Zusatzpaket dargestellt: Überschriften, Listen "
        "samt Kästchen zum Abhaken, Tabellen, Codeblöcke, Zitate und "
        "Links zwischen den Seiten. HTML aus einer Wiki-Datei wird "
        "bewusst nicht ausgeführt, sondern angezeigt",
        "Neuer Berechtigungsbereich „Wiki“ in der Benutzerverwaltung",
        "Neues Volume /wiki im Stack – der Stack muss dafür einmal neu "
        "aufgesetzt werden",
    ]},
    {"version": "0.7.1", "titel": "Wiki-Liste, Herunterladen, Abmelden umgezogen",
     "punkte": [
        "Wiki: zweite Darstellung für Ordner. Statt der Kacheln lässt sich "
        "eine Liste einstellen – bei vielen Seiten deutlich übersichtlicher, "
        "mit Dateiname, Größe und Änderungsdatum je Zeile. Umgeschaltet wird "
        "unter Einstellungen → Oberfläche, die Wahl gilt je Browser",
        "Wiki: jede Seite lässt sich als Markdown-Datei herunterladen",
        "Wiki: „Bearbeiten“, „Herunterladen“ und „Löschen“ sind jetzt drei "
        "Symbolknöpfe (Stift, Pfeil, Mülleimer) statt Textknöpfe – in der "
        "Seitenansicht oben und in der Listenansicht je Zeile",
        "Wiki: Ordner und Seiten sind in der Navigation links klarer zu "
        "unterscheiden – Ordner mit ausgefülltem Symbol in der Akzentfarbe "
        "und halbfetter Schrift, Seiten leicht eingerückt darunter",
        "Manuelle Zeiterfassung: vorgegebene Leistung und eigene "
        "Beschreibung werden mit Doppelpunkt getrennt statt mit "
        "Gedankenstrich („Begleitung zum Amt: Jobcenter“). Bereits "
        "gespeicherte Einträge bleiben unverändert",
        "„Abmelden“ ist aus der Kopfzeile nach „Mein Bereich“ gewandert. "
        "Dort steht unten, wer angemeldet ist, mit dem Knopf daneben",
        "Fehler behoben: auf jeder Seite ließ sich ein bis zwei Pixel nach "
        "links und rechts scrollen. Ursache war die Sprechblase des "
        "rechten Kopfzeilen-Symbols – sie ist unter ihrem Symbol zentriert "
        "und ragte damit über den Fensterrand hinaus, obwohl man sie gar "
        "nicht sah. Die letzte Blase hängt jetzt rechtsbündig",
    ]},
    {"version": "0.7.2", "titel": "Wiki-Seiten lesbarer", "punkte": [
        "Wiki-Seiten sind großzügiger gesetzt: deutlich mehr Luft über "
        "einer Überschrift als darunter, damit sichtbar ist, welcher "
        "Abschnitt zu welcher Überschrift gehört. Der Unterstrich unter "
        "den Zwischenüberschriften ist dafür entfallen",
        "Eingerückte Aufzählungen bekommen an jeder Ebene eine senkrechte "
        "Führungslinie. Bei Stammblättern mit mehreren Ebenen "
        "(Krankenkasse → Ärztliche Anbindung → Hausarzt → Adresse) ist "
        "damit auf einen Blick zu sehen, was zu wem gehört",
        "E-Mail-Adressen im Text sind anklickbar",
        "Ordner, die das Betriebssystem oder die NAS selbst anlegt "
        "(@eaDir, #recycle, Thumbs.db und Ähnliches), tauchen im Wiki "
        "nicht mehr auf und sind auch nicht mehr aufrufbar",
        "Listenansicht im Wiki: die Spalte „Datei“ ist entfallen, die "
        "Spalte „Größe“ steht linksbündig und nennt bei einem Ordner, wie "
        "viele Einträge darin liegen",
        "Fehler behoben: in der Listenansicht rutschte der dritte "
        "Aktionsknopf je nach Fensterbreite in eine zweite Zeile",
    ]},
    {"version": "0.7.3", "titel": "Wiki: Feinschliff der Darstellung",
     "punkte": [
        "Überschriften im Wiki sind jetzt vier Stufen tief unterscheidbar: "
        "die Seitenüberschrift trägt die Akzentfarbe, darunter folgen "
        "volle Textfarbe, eine Zwischenstufe und die leise Farbe – "
        "zusammen mit Größe und Laufweite",
        "Links im Wiki-Text werden nicht mehr unterstrichen. Erkennbar "
        "sind sie an der Akzentfarbe und der kräftigeren Schrift, der "
        "Unterstrich kommt erst beim Überfahren",
        "Tabellen im Wiki sehen aus wie eine eigene kleine Karte: runde "
        "Ecken, abgesetzte Kopfzeile, Zeilenwechsel beim Überfahren. Die "
        "Spalten richten sich nach ihrem Inhalt, statt stur gleich breit "
        "zu sein",
        "Neu: „Auf dieser Seite“. Hat eine Seite drei oder mehr "
        "Abschnitte, steht oben ein Verzeichnis, das direkt dorthin "
        "springt. Jede Überschrift hat dafür eine eigene Adresse – ein "
        "Klick im Verzeichnis, und die Adresszeile zeigt den Link auf "
        "genau diesen Abschnitt, den man weitergeben kann",
        "Die Pfadangabe über der Seite steht jetzt über beiden Spalten. "
        "Vorher schob sie die rechte Karte nach unten, sodass Navigation "
        "und Inhalt auf verschiedenen Höhen begannen",
        "Die Navigation links ist etwas breiter",
        "Vorsorge gegen seitliche Rollbalken: die Karte einer Wiki-Seite "
        "klemmt zu breite Inhalte jetzt selbst ab, statt einen Rollbalken "
        "über die ganze Karte zu legen, und für ältere Browser gibt es "
        "eine zweite Umbruchregel für lange Pfadangaben",
    ]},
    {"version": "0.7.4", "titel": "Wiki-Feinschliff, neue App-Symbole",
     "punkte": [
        "Die Überschriften einer Wiki-Seite sind jetzt vier Abstufungen "
        "derselben Farbe statt Pink, Weiß und zweimal Grau. Je tiefer die "
        "Ebene, desto zurückgenommener der Ton – die Rangfolge ist damit "
        "an der Farbe ablesbar",
        "Ein „[x]“ im Text wird zum ausgefüllten Kästchen in der "
        "Akzentfarbe, ein „[ ]“ zum leeren. Das gilt nicht nur in "
        "Aufzählungen, sondern auch mitten im Satz – etwa in der "
        "Statuszeile eines Stammblatts",
        "Tabellen im Wiki: eigene Karte mit Schatten, ruhige Kopfzeile "
        "mit feinem Farbstrich darunter, keine Zebrastreifen mehr, dafür "
        "eine Hervorhebung der Zeile beim Überfahren",
        "„Auf dieser Seite“ ist umgezogen: auf breiten Fenstern steht es "
        "als mitlaufende Spalte rechts neben dem Text und hebt hervor, in "
        "welchem Abschnitt man gerade liest. Auf schmaleren Fenstern ist "
        "es ein zugeklapptes Menü über dem Text und damit aus dem Weg",
        "Neues App-Symbol: auf dem iPhone lässt sich das Toolkit zum "
        "Startbildschirm hinzufügen und erscheint dort mit eigenem Symbol. "
        "Auch das Symbol im Browser-Tab (Favicon) ist neu",
        "Das Volume /stammdaten ist aus dem Stack entfernt – es wurde nie "
        "gebraucht. Beim nächsten Neuaufsetzen des Stacks verschwindet es; "
        "der Ordner auf der NAS kann stehen bleiben",
    ]},
    {"version": "0.7.5", "titel": "Abschnittsnavigation im Kartenstil",
     "punkte": [
        "Die Farben der Überschriften laufen jetzt richtig herum: die "
        "erste Ebene trägt den kräftigsten Ton, nach unten wird er immer "
        "heller. Vorher war die erste Ebene heller als die zweite",
        "„Auf dieser Seite“ sieht aus wie die Navigationskarte links und "
        "verhält sich auch so – dieselbe Kartenform, dieselbe "
        "Beschriftung, dieselben Zeilen mit Hervorhebung. Tiefere Ebenen "
        "bekommen dieselbe Führungslinie wie der Baum links",
    ]},
    {"version": "0.7.6", "titel": "Sprüche in den Einstellungen pflegen",
     "punkte": [
        "Neu unter Einstellungen → Oberfläche: Sprüche für die Startseite "
        "lassen sich jetzt anlegen, bearbeiten und entfernen, ohne die "
        "Datei quotes.txt von Hand anzufassen. Wer lieber direkt in der "
        "Datei schreibt, kann das weiterhin tun – beide Wege führen zur "
        "selben Datei",
    ]},
    {"version": "0.7.7", "titel": "Quotemanager, ruhigere Abschnittsliste",
     "punkte": [
        "Die Sprüche für die Startseite haben einen eigenen Punkt in den "
        "Einstellungen bekommen: „Quotemanager“. Vorher hingen sie unten "
        "an der Oberfläche mit dran",
        "Die Anführungszeichen setzt das Toolkit jetzt selbst – "
        "eingetragen wird nur der Wortlaut. Wer sie trotzdem mittippt, "
        "bekommt sie nicht doppelt. In der Liste steht jeder Spruch so, "
        "wie er später auf der Startseite erscheint",
        "Beim nächsten Speichern werden alle Sprüche auf einheitliche "
        "deutsche Anführungszeichen gebracht – auch die, die bisher "
        "gerade oder gar keine hatten",
        "Wiki: die Abschnittsliste rechts kommt ohne senkrechte Linien "
        "aus. Stattdessen ein abgesetzter Kopf, Punktmarken je Ebene "
        "(gefüllt oben, hohl darunter) und bei einer langen Gliederung "
        "bleibt die Beschriftung beim Rollen stehen",
        "Fehler behoben: die Hervorhebung des Abschnitts, in dem man "
        "gerade liest, blieb beim Rollen stehen. Sie hing an einer "
        "Browserfunktion, die sich nur meldet, wenn eine Überschrift eine "
        "gedachte Linie kreuzt – jetzt wird beim Rollen schlicht "
        "nachgerechnet",
    ]},
    {"version": "0.8", "titel": "Fuhrpark", "punkte": [
        "Neuer Menüpunkt „Fuhrpark“ mit genau zwei Unterpunkten: "
        "Erfassung und Auswertung",
        "Fahrzeuge werden unter Einstellungen → KFZ angelegt: Kennzeichen, "
        "Marke, Modell, Baujahr, Erstzulassung, Anfangskilometerstand, "
        "Kraftstoff, Leistung, Hubraum, Getriebe, Farbe. Ausgemusterte "
        "Fahrzeuge wandern ins Archiv und behalten ihre Historie",
        "Erfassung: Fahrzeug auswählen, dann eine Kachel anklicken – "
        "Tanken, Inspektion, Wartung, Reparatur, Reifenwechsel, TÜV, "
        "Kilometerstand oder sonstige Kosten. Darunter steht die "
        "vollständige Historie mit Bearbeiten und Löschen",
        "Ein Kilometerstand, der beim Tanken oder bei einer Reparatur "
        "nebenbei mitkommt, zählt automatisch als Kilometerstand des "
        "Fahrzeugs – er muss nicht zweimal eingetragen werden",
        "Kilometerstände werden auf Plausibilität geprüft: ein Wert unter "
        "einem früher erfassten Stand wird mit einer Begründung "
        "abgewiesen statt still gespeichert",
        "Wartungen und Inspektionen bekommen ein Intervall nach Monaten, "
        "nach Kilometern oder beidem. Fällig ist, was zuerst eintritt; "
        "die nächste Fälligkeit rechnet das Toolkit selbst aus",
        "Auswertung als Cockpit: ganz oben steht, worum sich jemand "
        "kümmern muss (überfällig, bald fällig, saisonaler "
        "Reifenwechsel), darunter Kennzahlen, Kostenentwicklung je Monat, "
        "Kostenverteilung nach Kategorie, Verbrauchsentwicklung, ein "
        "Fahrzeugvergleich und die letzten Einträge",
        "Verbrauch wird nur zwischen zwei Volltankungen gerechnet, Kosten "
        "je Kilometer nur bei bekannter Strecke. Fehlen die Daten, steht "
        "dort ein Strich statt einer falschen Zahl",
        "Filter über Zeitraum, Fahrzeug und Kategorie – sie wirken auf die "
        "ganze Auswertung",
        "Neuer Berechtigungsbereich „Fuhrpark“ in der Benutzerverwaltung. "
        "Bestehende Konten ohne Einschränkung sehen ihn automatisch",
        "Die Fälligkeiten sind so abgelegt, dass die geplanten "
        "E-Mail-Erinnerungen später darauf aufsetzen können, ohne dass "
        "daran etwas umgebaut werden muss",
    ]},
    {"version": "0.8.1", "titel": "Arbeitszeit als ein Menüpunkt, Fuhrpark "
                                 "nachgeschärft", "punkte": [
        "„Zeiterfassung“, „Datensätze“ und „Auswertung“ liegen jetzt "
        "unter dem einen Menüpunkt „Arbeitszeit“. Die drei Seiten stehen "
        "darunter als Reiterleiste – dieselbe wie beim Fuhrpark. Das "
        "Hauptmenü ist damit von sechs auf vier Punkte geschrumpft",
        "„Datensätze“ heißt jetzt „Übersicht“. In der Benutzerverwaltung "
        "steht der Bereich als „Übersicht (Datensätze)“, damit er "
        "wiederzuerkennen ist; an den vergebenen Rechten ändert sich "
        "nichts",
        "Das Auto-Symbol vor „Fuhrpark“ im Menü ist weg",
        "Fuhrpark → Erfassung: „Tanken“ und „Kilometerstand“ sind die "
        "beiden Handgriffe, die ständig vorkommen – sie haben jetzt "
        "deutlich mehr Fläche als der Rest. Die acht Kacheln füllen dabei "
        "ein sauberes Raster ohne Lücken",
        "Der Kilometerstand beim Tanken ist nicht mehr Pflicht. Ohne ihn "
        "zählt die Tankfüllung bei den Kosten mit, ergibt aber keinen "
        "Verbrauchswert – ihre Liter zählen dafür zur nächsten "
        "Volltankung mit Stand",
        "Fehler behoben: eine Tankfüllung ohne Kilometerstand wäre in der "
        "Verbrauchsrechnung samt ihrer Liter unter den Tisch gefallen. "
        "Das hätte einen zu niedrigen Verbrauch ergeben. Getrennt "
        "erfasste Kilometerstände ersetzen den Stand an der Zapfsäule "
        "übrigens nicht: dazwischen liegen unbekannt viele Kilometer, "
        "geschätzte Werte wären erfundene Statistik",
        "Fuhrpark → Auswertung: der Zeitraum-Filter ist neu. Statt eines "
        "Auswahlfeldes mit dem Punkt „Benutzerdefiniert“ und zwei "
        "Datumsfeldern daneben steht dort jetzt eine Reihe zum Anklicken "
        "– und daneben der eigene Zeitraum. Es ist immer zu sehen, "
        "welches von beidem gerade gilt",
    ]},
    {"version": "0.8.2", "titel": "Betrieb auf dem Raspberry Pi", "punkte": [
        "Das Toolkit läuft jetzt als Add-on unter Home Assistant OS und "
        "damit rund um die Uhr, unabhängig von der NAS",
        "Alle Einstellungen (Admin-Konto, Sitzungsdauer, Wecker-Intervall, "
        "Upload-Grenze, Zeitzone) über das Formular in Home Assistant",
        "Daten unter /share, damit das Wiki weiterhin auch über die "
        "Dateifreigabe bearbeitet werden kann",
        "Am Programm selbst wurde dafür nichts geändert",
    ]},
    {"version": "0.8.3", "titel": "Neue Versionszählung", "punkte": [
        "Der Verlauf ist neu nummeriert: jede 0.x steht jetzt für einen "
        "Meilenstein – Grundgerüst, Auswertung, erste finale Fassung, "
        "Verwaltungsvorgänge, Benutzerkonten, E-Mail und persönlicher "
        "Bereich, Wiki, Fuhrpark",
        "Die dritte Stelle ist wie bisher Politur zwischen zwei "
        "Meilensteinen",
    ]},
    {"version": "0.8.4", "titel": "Einträge anderer nur mit Berechtigung löschen", "punkte": [
        "Neues Recht je Konto: „Einträge anderer löschen“ "
        "(Einstellungen → Benutzerverwaltung)",
        "Ohne dieses Recht lassen sich in der Übersicht nur die eigenen "
        "Zeiten löschen – die eigenen aber immer",
        "Kästchen und Löschknopf fehlen bei fremden Zeilen; ein von Hand "
        "abgeschicktes Formular wird serverseitig ebenfalls abgewiesen",
        "Administratoren dürfen weiterhin alles",
        "Das Recht ist bei bestehenden Konten zunächst NICHT gesetzt und "
        "muss ausdrücklich erteilt werden",
    ]},
    {"version": "0.8.5", "titel": "Benutzerverwaltung nur für Administratoren", "punkte": [
        "Benutzerverwaltung, E-Mail-Versand und E-Mail-Vorlagen sehen "
        "ausschließlich Administratoren – auch bei direkt eingegebener "
        "Adresse",
        "Neu: „Mein Konto“ in Mein Bereich. Dort ändert jede Person ihr "
        "eigenes Passwort und ihre E-Mail-Adresse, sonst nichts",
        "Ein Passwortwechsel verlangt das aktuelle Passwort und beendet "
        "alle anderen offenen Sitzungen dieses Kontos",
    ]},
    {"version": "0.8.6", "titel": "Wiki: Lesen und Schreiben getrennt", "punkte": [
        "Neues Recht je Konto: „Wiki bearbeiten“",
        "Ohne dieses Recht bleibt das Wiki vollständig lesbar und "
        "herunterladbar, lässt sich aber nicht ändern",
        "Bearbeiten, Anlegen, Löschen und Verschieben verschwinden dann "
        "aus der Oberfläche; das Ziehen im Baum ist abgeschaltet",
        "Bestehende Konten behalten das Recht",
    ]},
    {"version": "0.8.7", "titel": "Fuhrpark-Erfassung neu gestaltet, Löschungen im Logbuch", "punkte": [
        "Die Auswahl „Was möchtest du erfassen?“ ist neu gestaltet: "
        "gezeichnete Strichsymbole statt Emoji, in den Farben der jeweiligen "
        "Kategorie",
        "Statt eines Rasters mit Lücken jetzt zwei Gruppen: oben Tanken und "
        "Kilometerstand, darunter die sechs selteneren Arten",
        "Dieselben Symbole in der Historie und in den letzten Einträgen der "
        "Auswertung",
        "Verwaltungsvorgänge: Wird ein Vorgang gelöscht, bleibt sein "
        "vollständiger Verlauf im Logbuch stehen und wird als „gelöscht“ "
        "gekennzeichnet",
        "Die Löschung selbst wird protokolliert – mit dem angemeldeten "
        "Konto, nicht mit einer selbst eingetippten Angabe",
    ]},
    {"version": "0.8.8", "titel": "Zeiterfassung im Stapel, ruhigeres Logbuch", "punkte": [
        "Neues Recht je Konto: „Einträge anderer bearbeiten“ – getrennt vom "
        "Löschrecht, weil beides verschieden schwer wiegt: eine gelöschte "
        "Zeile fällt auf, eine stillschweigend geänderte nicht",
        "Ohne dieses Recht lassen sich fremde Zeiten weder öffnen noch "
        "speichern, und ein eigener Eintrag lässt sich nicht auf eine "
        "andere Person umschreiben",
        "Zeiterfassung: „Mitarbeiter“ ist jetzt ein Auswahlfeld mit den "
        "Namen aus dem Team – beim manuellen Eintrag wie beim Listenimport",
        "Manuelle Erfassung: mehrere Einträge auf einmal. „+ Weitere Zeile“ "
        "öffnet eine zusätzliche Zeile, das Datum der vorigen wird "
        "übernommen",
        "Ein Fehler in einer Zeile speichert gar nichts und nennt die "
        "Zeilennummer; leere Zeilen werden übersprungen",
        "Nach dem Speichern bleibt die Seite beim Formular stehen statt an "
        "den Seitenanfang zu springen",
        "„Zeitlisten einlesen“ steht in derselben Schriftgröße wie "
        "„Manuelle Zeiterfassung“, Datei und Mitarbeiter nebeneinander",
        "Logbuch nach Tagen gegliedert („Heute“, „Gestern“, sonst der "
        "Wochentag), Zeit und handelnde Person in einer eigenen Spalte, "
        "jede Aktionsart in ihrer eigenen Farbe",
        "Betreutenansicht: die Kopfkarte in drei Bändern statt drei "
        "aneinanderklebender Blöcke",
    ]},
    {"version": "0.8.9", "titel": "Dateiverwaltung, Aufräumen", "punkte": [
        "Neuer Menüpunkt „Dateien“: Bilder, PDFs und Office-Dateien "
        "hochladen, in Ordnern sortieren, umbenennen, verschieben und "
        "löschen. Alles landet im Ordner „files“ und ist damit auch über "
        "die Dateifreigabe erreichbar",
        "Zu jeder Datei steht ein fertiger Markdown-Schnipsel, der sich "
        "direkt ins Wiki einsetzen lässt – Bilder erscheinen dort als Bild",
        "Erlaubt sind nur bekannte Dateiarten; der Inhaltstyp beim "
        "Ausliefern kommt aus einer festen Liste, nicht aus dem Upload",
        "Neuer Berechtigungsbereich „Dateien“",
        "Listenimport: Dateifeld und Mitarbeiter-Auswahl sind jetzt "
        "gleich hoch",
        "Manuelle Erfassung: der Haken „auch speichern, wenn ein "
        "identischer Eintrag schon existiert“ ist entfallen. Gleiche "
        "Einträge gehen jetzt immer durch",
        "Aufgeräumt: die tote Route „In Export-Ordner ablegen“ samt dem "
        "Ordner /export, fünf nirgends gelesene Datenbankspalten, die "
        "letzten Emoji im Fuhrpark und die docker-compose.yml der "
        "NAS-Variante",
    ]},
    {"version": "0.9", "titel": "Dateiverwaltung im Wiki-Aufbau", "punkte": [
        "Die Dateiverwaltung ist neu gebaut und folgt jetzt dem Wiki: links "
        "die Ordnerstruktur als Baum, rechts der Inhalt",
        "Hochladen und Ordner anlegen sitzen als Symbolknöpfe in der "
        "Seitenleiste",
        "Zwei Ansichten wie im Wiki, umschaltbar unter Einstellungen → "
        "Oberfläche. Standard ist die Liste mit Name, Art, Größe und "
        "Änderungsdatum",
        "Ziehen mit der Maus verschiebt Dateien und Ordner – genau wie im "
        "Wiki-Baum",
        "Der Ablageort steht jetzt in der Oberfläche: alles liegt im Ordner "
        "„files“ neben dem Programm",
        "Was dort über die Dateifreigabe von Hand abgelegt wird, erscheint "
        "in der Übersicht – auch Dateiarten, die sich nicht öffnen lassen. "
        "Sie werden angezeigt statt verschwiegen",
        "Menü: „Dateien“ steht jetzt vor „Wiki“",
        "„Verwaltungsvorgänge“ heißen im Menü und auf der Seite jetzt "
        "„Aufgaben“. Adresse und Berechtigung bleiben unverändert",
        "Fehler behoben: ein per Skript ausgeblendetes Element blieb "
        "sichtbar, wenn eine Klassenregel ihm eine Darstellung gab",
    ]},
    {"version": "0.9.1", "titel": "Auslieferung korrigiert", "punkte": [
        "Die Add-on-Anleitung nannte den Neubau nur bei geänderten "
        "Paketversionen im Dockerfile nötig. Tatsächlich wird auch "
        "run.sh beim Bauen fest ins Abbild eingebacken (COPY) — eine "
        "Änderung daran wirkt ohne „Neu erstellen“ nicht, ein bloßer "
        "Neustart lädt weiter die alte Fassung",
        "Klarere Faustregel: hat sich etwas außerhalb von "
        "share/…/app geändert, im Zweifel neu erstellen",
        "Neuer Abschnitt in „Wenn etwas klemmt“ für den Fall, dass "
        "hochgeladene Dateien nicht in share/deinweg-toolkit/files "
        "erscheinen",
        "Am Programm selbst hat sich nichts geändert",
    ]},
    {"version": "0.9.2", "titel": "Dateien nachgeschärft, neuer Anmeldebildschirm", "punkte": [
        "Vier neue Dateiarten: MP4, SVG, EPS und DOTX",
        "SVG wird mit einer Sandbox ausgeliefert – als Bild eingebunden "
        "harmlos, beim direkten Aufruf kann daraus kein Skript laufen",
        "Fehler behoben: der Löschknopf einer Datei war in der "
        "Listenansicht vorhanden, wurde aber aus der Spalte gedrängt und "
        "war dadurch nicht erreichbar",
        "Ordner lassen sich jetzt auch löschen, wenn etwas darin liegt. "
        "Die Sicherheitsabfrage nennt, wie viele Einträge mitgehen",
        "Ordner zeigen ihr Änderungsdatum – die Spalte „Geändert“ blieb "
        "sonst leer, sobald auf einer Ebene nur Ordner lagen",
        "Spaltenüberschriften und Inhalte durchgehend linksbündig",
        "Der Umschalter zwischen Listen- und Kachelansicht steht jetzt "
        "direkt auf der Dateien-Seite",
        "Wiki: Bilder nehmen höchstens 68 % der Textbreite ein und werden "
        "nie über ihre eigene Größe hinaus vergrößert",
        "Neuer Anmeldebildschirm: Logo über der Karte statt darin",
    ]},
    {"version": "1.0", "titel": "Neue Marke, aufgeräumte Oberfläche", "punkte": [
        "Neue Grafiken durchgängig eingebaut: Logo, Favicons, App-Symbole "
        "und ein eigenes Zeichen für die Kopfzeile",
        "Die Kopfzeile trägt jetzt das Zeichen mit dem Namen daneben – der "
        "vollständige Schriftzug hat eine Unterzeile, die in der Kopfhöhe "
        "niemand lesen konnte. Er steht weiterhin auf der Anmeldeseite und "
        "in der Fußzeile",
        "Die Kopfzeile bleibt beim Rollen oben stehen; der aktive "
        "Menüpunkt ist zusätzlich unterstrichen",
        "Einstellungen in fünf Gruppen geordnet: Darstellung, Stammdaten, "
        "Auswahllisten, Konten und E-Mail, Wartung",
        "Erklärende Texte tragen ein kleines Informationszeichen und "
        "liegen wieder vollständig in strings.txt",
        "Dateien: die Zählung oben rechts ist entfallen",
        "Dateien: Ordner lassen sich umbenennen und ins Wiki verlinken – "
        "dieselben Aktionen wie bei einer Datei",
    ]},
    {"version": "1.0.1", "titel": "Feinschliff an Marke und Texten", "punkte": [
        "Alle erklärenden Texte haben jetzt dieselbe Schriftgröße und "
        "dasselbe Aussehen – vorher waren Einleitungen größer als "
        "Feldhinweise, was auf einer Seite wie zwei Textsorten wirkte",
        "In der Kopfzeile steht oben links nur noch das Zeichen, ohne "
        "Schriftzug daneben",
        "Neue Menügrafik in beiden Fassungen eingebaut",
        "Anmeldebildschirm: größeres Logo, das sich beim Laden aufbaut. "
        "Wer im Betriebssystem „Bewegung reduzieren“ eingestellt hat, "
        "bekommt die Seite unbewegt",
    ]},
    {"version": "1.0.2", "titel": "Auftritt des Logos", "punkte": [
        "Anmeldebildschirm: das Logo ist größer und bekommt einen "
        "richtigen Auftritt – es kippt unscharf aus der Tiefe herein, "
        "eine schräge Kante wischt es frei, ein Glanzlicht läuft darüber, "
        "zum Schluss leuchtet es einmal auf und die Karte steigt nach",
        "Nach 2,6 Sekunden steht alles still. Wer im Betriebssystem "
        "„Bewegung reduzieren“ eingestellt hat, sieht die Seite sofort "
        "fertig",
    ]},
    {"version": "1.1", "titel": "Updates über Home Assistant", "punkte": [
        "Das Toolkit liegt jetzt als Add-on-Repository auf GitHub. Home "
        "Assistant erkennt neue Fassungen von selbst und bietet sie im "
        "Add-on-Store an – kein ZIP, kein Kopieren über die Freigabe",
        "Der Programmcode steckt dafür im Abbild statt unter "
        "share/deinweg-toolkit/app. Nur so kann ein Update ihn wirklich "
        "mitliefern; vorher wäre bei einem Update nur die Hülle erneuert "
        "worden",
        "Die Daten bleiben, wo sie sind: db, texte, wiki und files unter "
        "share/deinweg-toolkit. Ein Update fasst sie nicht an",
        "Der Ordner share/deinweg-toolkit/app wird nicht mehr gebraucht "
        "und kann gelöscht werden",
    ]},
    {"version": "1.1.1", "titel": "Menü am Handy, ruhigere Oberfläche", "punkte": [
        "Am Handy ließ sich das Menü nicht mehr bedienen: es lag hinter "
        "dem Abdunkler und war dadurch verschwommen und nicht anklickbar. "
        "Ursache war der Stapelkontext der Kopfzeile, nicht das Menü selbst",
        "Die pinken Linien, die beim Überfahren der Menüpunkte "
        "hereinliefen, sind entfernt",
        "Anmeldeseite: zurück zur ruhigen Fassung aus 1.0.1",
        "Manuelle Zeiterfassung: Abstand zwischen „+ Weitere Zeile“ und "
        "„Eintrag speichern“",
        "Arbeitszeit → Übersicht: „Excel“ und „CSV“ stehen nicht mehr im "
        "Filterkasten, sondern über der Trefferliste – und beide in "
        "derselben, zurückhaltenden Farbe. Vorher lag der pinke "
        "Excel-Knopf da, wo man „Filtern“ erwartet",
        "Der Knopf „Zurücksetzen“ im Filterhinweis geht am Handy nicht "
        "mehr über die ganze Breite",
    ]},
    {"version": "1.1.2", "titel": "Umbrüche im Wiki, weniger Hinweistexte", "punkte": [
        "Wiki: Ein Zeilenumbruch im Text ist jetzt auch einer in der "
        "Anzeige. Bisher lief ein Absatz durch, egal wie man ihn getippt "
        "hatte – Anschriften und kurze Aufstellungen klebten dadurch in "
        "einer Zeile",
        "Wiki: Der Hinweis zum Verschieben per Maus ist entfernt",
        "Dateien: Die drei Hinweistexte über Ablageort, erlaubte "
        "Dateiarten und das Ziehen mit der Maus sind entfernt",
        "„Changelog“ steht nicht mehr als Symbol in der Kopfzeile, "
        "sondern als Link in der Fußzeile hinter der Versionsnummer",
    ]},
    {"version": "1.2", "titel": "Rechte bis in die Einstellungen, eigene Zeiten in „Mein Bereich“", "punkte": [
        "Neu: für jedes Konto lässt sich einzeln festlegen, welche Punkte "
        "es innerhalb der Einstellungen sehen darf. „Oberfläche“ bleibt "
        "immer sichtbar – dort stehen nur Darkmode, Breite und die "
        "Ansichtsschalter, die ohnehin jeder für sich selbst einstellt",
        "Die Schalter für die Wiki- und die Dateien-Ansicht verschwinden, "
        "wenn dem Konto der jeweilige Bereich fehlt",
        "Benutzerverwaltung neu gestaltet: je Konto eine Zeile mit Name, "
        "Rolle, Zuordnung und einer Zusammenfassung der Rechte. Der Editor "
        "klappt darunter auf und ist in Konto und Rechte geteilt",
        "„Zur Übersicht“ im Kasten „Bestand“ steht nur noch da, wenn das "
        "Konto den Bereich „Übersicht (Datensätze)“ auch hat",
        "„Mein Bereich“ zeigt jetzt die eigenen Zeiten – unabhängig von "
        "jeder Bereichsberechtigung, mit Monatswahl, Bearbeiten und "
        "Löschen. Fremde Einträge sind dort genauso geschützt wie in der "
        "Übersicht",
        "„Abmelden“ steht als großer Knopf oben in der ersten Karte statt "
        "klein unten bei „Mein Konto“",
        "Aufgabenliste am Handy: die acht Spalten wurden ineinander "
        "geschoben und waren nicht mehr lesbar. Die Tabelle rollt dort "
        "jetzt seitlich, statt sich zu stauchen",
        "Fehler behoben: Erklärtexte mit Hervorhebungen zerfielen in "
        "schmale Spalten nebeneinander – zu sehen bei „Einzelrechte“ in "
        "der Benutzerverwaltung",
        "Fehler behoben: ein Rechteformular ohne einen einzigen Haken "
        "erteilte vollen Zugriff statt gar keinen",
    ]},
    {"version": "1.3", "titel": "Bewilligte Zeiträume je betreuter Person", "punkte": [
        "Zu jeder betreuten Person lassen sich jetzt beliebig viele "
        "Zeiträume hinterlegen – je mit eigenen Wochenstunden, eigenem "
        "Stundensatz und einer Notiz für das Aktenzeichen. Genau so, wie "
        "der Kostenträger es bewilligt: 08/2024 bis 07/2025 vier Stunden "
        "zu 65 €, ab 08/2025 sieben zu 70 €",
        "Ein Zeitraum ohne Ende gilt bis auf Weiteres. Überschneiden sich "
        "zwei, gewinnt der später begonnene – so wirkt ein Folgebescheid "
        "sofort, auch wenn der alte formal noch läuft",
        "Die Auswertung rechnet damit Monat für Monat: über einen Zeitraum "
        "hinweg, in dem sich die Zusage geändert hat, stimmen Soll und "
        "Verdienst jetzt. Vorher galt für den ganzen Zeitraum ein einziger "
        "Wert und das Ergebnis war schlicht falsch",
        "Wo gestaffelt gerechnet wurde, steht das auch da – in der Spalte "
        "„Soll“ als Marke und unter der Tabelle als Hinweis",
        "Die alten Felder bleiben als Grundwert bestehen und gelten für "
        "jeden Monat, den kein Zeitraum abdeckt. Bestehende Personen "
        "rechnen dadurch unverändert weiter",
        "Betreute Personen stehen jetzt als aufklappbare Liste statt als "
        "Tabelle – die Zeiträume passen in keine Tabellenzelle. Die Zeile "
        "zeigt, was heute gilt",
        "Der Verdienst hängt nicht mehr daran, dass auch Wochenstunden "
        "hinterlegt sind. Ein Monat mit Stundensatz, aber ohne Kontingent "
        "fiel vorher stillschweigend aus der Summe",
    ]},
    {"version": "1.4", "titel": "Auswertung Monat für Monat", "punkte": [
        "Die Auswertung teilt den gewählten Zeitraum jetzt in Monate auf: "
        "unter den bisherigen Boxen steht je Monat ein eigener Block mit "
        "dem, was geleistet wurde, was bewilligt war und was daraus "
        "verdient ist – gerechnet mit dem Stundensatz, der in genau "
        "diesem Monat galt",
        "Darüber eine Zusammenfassung über den ganzen gefilterten "
        "Zeitraum: geleistet, bewilligt, Abweichung, Verdienst und die "
        "Zahl der Monate",
        "Monate ohne erfasste Zeiten bleiben stehen, solange für sie "
        "etwas bewilligt war – eine Lücke fällt sonst nicht auf",
        "Ein Monat, für den kein Zeitraum hinterlegt ist, wird in der "
        "Spalte „Bewilligt“ als Grundwert markiert. So hält man einen "
        "fehlenden Bescheid nicht für eine Bewilligung",
        "Die Aufteilung erscheint ab zwei Monaten – bei einem einzelnen "
        "stünde dort dasselbe noch einmal",
        "Einstellungen → Betreute Personen: die Schalter „Zeiten sind "
        "abrechenbar“ und „Person aktiv“ klebten am Speichern-Knopf. "
        "Jetzt haben die drei Lagen Luft voneinander, und die Knopfzeile "
        "schließt den Block mit einer feinen Linie ab",
    ]},
    {"version": "1.4.1", "titel": "Auswertung in einer Spalte", "punkte": [
        "Die Auswertung lief oben zweispaltig und unten über die volle "
        "Breite. Die beiden Hälften waren verschieden hoch, dadurch klaffte "
        "rechts eine Lücke, und ab den Monatsblöcken wechselte das Raster "
        "mitten auf der Seite. Jetzt läuft alles in einer Spalte",
        "„Stunden pro betreuter Person“, „Stundenkontingent“ und "
        "„Verdienst“ standen als drei Kästen nebeneinander und zählten "
        "dieselben Namen dreimal auf. Sie sind zu einer Karte "
        "„Überblick“ zusammengefasst: vier Kennzahlen oben, darunter eine "
        "Zeile je Person mit Einheiten, Geleistet, Bewilligt, Abweichung, "
        "Satz und Verdienst – dazu der Kontingentbalken unter dem Namen "
        "und eine Summenzeile",
        "Alle Spalten stehen linksbündig, wie in jeder anderen Liste des "
        "Programms. Die rechtsbündigen Zahlenspalten der Monatsblöcke "
        "sahen daneben wie ein Fremdkörper aus",
        "Überblick und Monatsblöcke tragen dieselbe Spaltenfolge – das "
        "Auge muss sie nicht zweimal lernen",
        "Ein Band mit Überschrift „Monat für Monat“ trennt die beiden "
        "Teile der Seite. Vorher lief das eine ohne erkennbare Kante ins "
        "andere über",
        "Am Handy stehen die Spalten in Pixeln statt in Prozent: "
        "„8.488,58 €“ lief sonst aus seiner Zelle in die Nachbarspalte",
    ]},
    {"version": "1.4.2", "titel": "Auswertung mit Seitenspalte", "punkte": [
        "Die Auswertung steht wieder in zwei Spalten – diesmal aber über "
        "ihre ganze Länge und nicht nur oben. Die Monatsblöcke liegen "
        "damit in der schmaleren linken Spalte und wirken ruhiger",
        "Rechts drei Kästen, die den Platz füllen, der neben einer langen "
        "Monatsliste sonst leer bliebe:",
        "„Stundenkontingent“ – die Balken je betreuter Person, wie vorher. "
        "Der Balken ist damit aus der Tabellenzelle raus, wo er jede Zeile "
        "auf drei Zeilen aufzog",
        "„Monate“ – jeder Monat mit Balken, Stunden und Verdienst; ein "
        "Klick springt zum ausführlichen Block links. Bei fünfzehn Blöcken "
        "der schnellste Weg zum gesuchten Monat",
        "„Bewilligt“ – die Bescheide, die den gewählten Zeitraum berühren, "
        "je Person mit Zeitraum, Wochenstunden, Satz und Notiz. Damit "
        "steht neben den Zahlen auch, woher sie kommen",
        "Spaltenbreiten der Tabellen so gesetzt, dass im engsten Fall "
        "jeder Spaltentitel und jeder Betrag in seine Zelle passt",
    ]},
    {"version": "1.4.3", "titel": "Einheiten, keine Marken in den Zellen", "punkte": [
        "Maßangaben an den Werten, an denen sie fehlten: „Std“ hinter den "
        "Kennzahlen, in der Kopfzeile jedes Monatsblocks und in der "
        "Seitenspalte. In den Tabellen steht die Einheit einmal im "
        "Spaltenkopf statt in jeder Zelle – dort auf einer eigenen, "
        "gedämpften Zeile, damit sie die Spalte nicht breiter macht",
        "Die Marke „Grundwert“ in der Spalte „Bewilligt“ ist entfallen. Sie "
        "brach jede zweite Zeile um und machte die Spalte unnötig breit. "
        "Wo der Grundwert gegriffen hat, steht weiterhin in der "
        "Seitenspalte unter „Bewilligt“ – einmal je Person statt einmal je "
        "Zeile",
        "Dasselbe für die Marke „gestaffelt“: dass mit mehreren Sätzen "
        "gerechnet wurde, steht in der Spalte „Satz“ („2 Sätze“) und als "
        "Hinweis unter der Tabelle",
        "Damit passen die Tabellen wieder in ihre Spalte – der seitliche "
        "Rollbalken ist bis hinunter zu einem 1300 Pixel breiten Fenster "
        "weg. Die Summenzeile ist außerdem nicht mehr größer gesetzt als "
        "der Rest; bei fünfstelligen Beträgen sprengte sie sonst ihre "
        "Spalte",
    ]},
    {"version": "1.4.4", "titel": "Auswertung: eine Spalte weniger, keine Rollbalken", "punkte": [
        "Die Spalte „Mitarbeiter“ ist aus beiden Tabellen der Auswertung "
        "entfallen. Wer die Zeit erfasst hat, steht in der Übersicht unter "
        "„Arbeitszeit“; in der Auswertung geht es um die betreute Person",
        "„Betreute Person“ und „Einh.“ tragen jetzt auch eine zweite Zeile "
        "im Kopf („Name“ bzw. „Anzahl“). Damit sind alle Spaltenköpfe "
        "gleich gebaut und gleich hoch",
        "Der seitliche Rollbalken ist weg – er blieb auch bei breitem "
        "Fenster stehen, weil die Summenzeile mit sechsstelligen Beträgen "
        "wie „178.980,66 €“ nicht in ihre Spalte passte. Der Betrag lief "
        "über den Rand hinaus und zog die Rollbreite der ganzen Tabelle "
        "mit sich. Die Spalte ist jetzt entsprechend bemessen, und mit der "
        "eingesparten Mitarbeiterspalte passt die Tabelle bis hinunter zu "
        "einem 1080 Pixel breiten Fenster ohne Rollen",
    ]},
    {"version": "1.5", "titel": "Mehrere Betreute filtern, Bewilligungen im Blick", "punkte": [
        "Der Filter der Auswertung nimmt jetzt mehrere betreute Personen "
        "auf einmal: „Betreute Personen“ klappt eine Liste mit Kästchen "
        "auf. Zugeklappt steht dort der Name oder die Zahl der Gewählten. "
        "Übersicht und Export folgen derselben Auswahl",
        "Filterbereich aufgeräumt: „nur abrechenbare Zeiten“ steht nicht "
        "mehr zwischen den Auswahlfeldern, wo es je nach Umbruch mal am "
        "Zeilenende und mal mittendrin landete, sondern in einer eigenen "
        "Zeile darunter – links das Kriterium, rechts die Knöpfe",
        "Einstellungen → Betreute Personen: jede Zeile sagt jetzt, wie die "
        "Person heute dasteht – „gültig“, „Bewilligung ausgelaufen“ (mit "
        "Datum), „gilt erst ab …“ oder „keine Bewilligung hinterlegt“. "
        "Betroffene Zeilen sind rot markiert, und über der Liste steht, "
        "wie viele es sind. Vorher stand dort nur „kein Kontingent "
        "hinterlegt“, was auch eine ausgelaufene Bewilligung bedeuten "
        "konnte",
        "Im aufgeklappten Block steht der Hinweis noch einmal ausdrücklich "
        "und sagt, was das für die Auswertung bedeutet",
        "Die bewilligten Zeiträume stehen jetzt oben im Block, die "
        "Stammdaten darunter – der Name ändert sich nie, die Bescheide "
        "dauernd. Die Grundwerte sind als „Rückfall“ gekennzeichnet",
        "„speichern“ und „entfernen“ stehen als eine Knopfzeile ganz unten, "
        "„entfernen“ rechts abgesetzt – mitten in der Karte sahen sie aus "
        "wie ein vergessener Rest",
        "Der seitliche Rollbalken in der Auswertung ist endgültig weg: die "
        "Tabelle rechnet ihre Spaltenbreiten jetzt selbst aus dem Inhalt, "
        "statt auf von Hand gesetzten Pixelwerten zu stehen. Die waren "
        "dreimal zu knapp geraten – zuletzt, weil dieselbe Schrift auf "
        "einem anderen Rechner ein paar Pixel breiter läuft",
    ]},
    {"version": "1.6", "titel": "Filter überall gleich, Bewilligungen in Mein Bereich", "punkte": [
        "Die Namensliste im Filter hat jetzt ein Suchfeld: aufklappen, "
        "Anfangsbuchstaben tippen, und die Liste zeigt nur noch die "
        "passenden Namen. Enter hakt den ersten Treffer an",
        "Der Text im zugeklappten Feld folgt den Kästchen sofort – vorher "
        "stand dort noch „alle“, obwohl schon zwei Namen angehakt waren",
        "Dieselbe Mehrfachauswahl gilt jetzt auch für „Mitarbeiter“",
        "Die Übersicht hat denselben Filter wie die Auswertung bekommen. "
        "Das Suchfeld ist geblieben und sitzt in der unteren Zeile neben "
        "„nur abrechenbare Zeiten“",
        "„Mein Bereich“ zeigt oben, bei welchen betreuten Personen eine "
        "Bewilligung abgelaufen ist, in den nächsten 60 Tagen ausläuft "
        "oder ganz fehlt – mit einem Sprung direkt zu den Zeiträumen. "
        "Personen, für die nie ein Bescheid hinterlegt war, stehen "
        "zugeklappt darunter, damit sie die dringenden Fälle nicht "
        "ertränken",
        "Neues Recht „Bewilligungen in Mein Bereich“ in der "
        "Benutzerverwaltung. Standard an: es ist eine Erinnerung fürs "
        "Team, keine heikle Auskunft",
        "Einstellungen → Betreute Personen kennt jetzt auch „läuft aus“ – "
        "mit der Zahl der verbleibenden Tage",
        "Der seitliche Rollbalken in der Auswertung: Die Tabellen brauchen "
        "rund 630 Pixel. Bei einer 340 Pixel breiten Seitenspalte blieb "
        "links darunter zu wenig übrig, und die Tabelle rollte. Die zweite "
        "Spalte erscheint deshalb erst ab 1200 Pixel Fensterbreite; "
        "darunter rutscht sie unter den Inhalt und die Tabellen bekommen "
        "die volle Breite",
    ]},
    {"version": "1.7", "titel": "Mein Bereich neu geordnet", "punkte": [
        "„Mein Bereich“ ist in Abschnitte geteilt: oben der Spruch wie auf "
        "der Zeiterfassung, darunter eine schmale Kopfzeile mit Namen und "
        "Abmelden, dann „Meine Arbeitszeit“ und „Was ansteht“",
        "Die Kopfkarte ist deutlich kleiner. Sie hatte eine eigene "
        "Überschriftenzeile samt Erklärabsatz und nahm den halben ersten "
        "Bildschirm für eine Auskunft, die man einmal liest",
        "Neu unter „Was ansteht“: die eigenen Aufgaben mit Titel, "
        "betreuter Person, Status und Frist – überfällige rot markiert, "
        "ein Klick führt zum Vorgang",
        "Daneben „Bewilligungen im Blick“, jetzt kompakter und ohne den "
        "gelben Rahmen. Wie dringend etwas ist, sagt der farbige Balken "
        "an der Zeile",
        "Der seitliche Rollbalken der Auswertungstabellen: In den Tabellen "
        "steht jetzt nichts mehr auf „nicht umbrechen“. Eine Zelle, die "
        "nicht umbrechen darf, setzt eine Mindestbreite, die die Tabelle "
        "nicht unterschreiten kann – steht sie in einer schmaleren Spalte, "
        "muss sie überlaufen. Darf dagegen alles umbrechen, passt die "
        "Tabelle in jede Breite. Sichtbar ist davon nichts: umgebrochen "
        "wird nur, wo der Platz sonst wirklich nicht reicht",
    ]},
    {"version": "1.7.1", "titel": "Was ansteht nach oben, Rollbalken abgeschaltet", "punkte": [
        "„Was ansteht“ steht jetzt vor der Arbeitszeit – was heute zu tun "
        "ist, wiegt schwerer als die Zahlen des letzten Monats",
        "Die Aufgabenkarte bleibt auch dann stehen, wenn nichts offen ist, "
        "und sagt das auch. Vorher verschwand sie einfach, was aussah wie "
        "ein Fehler",
        "Die Tabellen der Auswertung können auf dem Schreibtisch gar nicht "
        "mehr seitlich rollen. Sie passen dort mit Sicherheit in ihre "
        "Karte – ein Rollbalken war also immer ein Rundungsfehler, eine "
        "Schrift, die auf einem anderen Rechner ein halbes Pixel breiter "
        "läuft, oder die Scrollbar-Einstellung des Systems. Jetzt gibt es "
        "schlicht nichts mehr zu rollen. Auf dem Telefon bleibt das "
        "Rollen erhalten, dort ist es nötig",
    ]},
    {"version": "1.8", "titel": "Aufgaben als Karten", "punkte": [
        "Die Vorgangsliste ist keine Tabelle mehr, sondern ein Raster aus "
        "Karten – eine je Vorgang. In der Tabelle stand der Titel, also "
        "das Einzige, wonach man wirklich sucht, als schmale Spalte "
        "zwischen sieben anderen, und bei zwanzig Zeilen sah alles gleich "
        "aus",
        "Jede Karte hat ihre eigene Ordnung: oben der Titel, darunter "
        "betreute Person und Art, dann die Notiz (auf zwei Zeilen "
        "gekürzt), unten Status, Frist, zuständige Person und Priorität",
        "Der Balken links sagt schon vor dem Lesen, wie dringend es ist – "
        "rot für überfällig, orange für heute und bald, grün für erledigt",
        "Öffnen und Löschen erscheinen beim Überfahren der Karte. Sonst "
        "zöge das Rot des Löschknopfes auf zwanzig Karten mehr "
        "Aufmerksamkeit als die Vorgänge selbst. Per Tastatur und auf dem "
        "Telefon sind sie immer da",
        "„Mein Bereich“: hat man keine offene Aufgabe, fliegt in der Karte "
        "jetzt eine Katze auf einem Regenbogen durchs Bild. Handgezeichnet "
        "und ohne nachgeladenes Bild, und sie hält still, wenn im System "
        "„Bewegung reduzieren“ eingestellt ist",
        "Der Knopf „Zu den Aufgaben“ steht dort jetzt mittig unter dem "
        "Text",
    ]},
    {"version": "1.8.1", "titel": "Aufgaben verständlicher, Katze verrückter", "punkte": [
        "Höchstens zwei Vorgangskarten nebeneinander. Bei vier wurde jede "
        "so schmal, dass Titel und Notiz umbrachen – man sah mehr Karten, "
        "aber von jeder weniger",
        "„Überfällig“ wiegt jetzt schwerer als „Dringend“: das eine ist "
        "eine Tatsache, das andere eine Einschätzung. Überfällige Vorgänge "
        "tragen die Marke gleich neben dem Titel, die Priorität ist eine "
        "ruhige Pille in der Fußzeile geworden. Die Liste ist von Haus aus "
        "nach Dringlichkeit sortiert – überfällige zuerst, dann nach "
        "Frist, dann nach Priorität",
        "Es gab einen Knopf „Neuen Vorgang anlegen“ und direkt darunter "
        "noch einmal dieselbe Beschriftung als Aufklapper. Jetzt gibt es "
        "nur noch den Knopf; er öffnet das Formular über die Adresse und "
        "heißt danach „Formular schließen“",
        "Das Anlegeformular steht in drei Blöcken: „Worum geht es?“, „Wer "
        "kümmert sich, bis wann?“ und „Wer trägt das gerade ein?“ – mit "
        "einer Erklärung, was der Unterschied zwischen zuständiger und "
        "handelnder Person ist. Beide Felder sind mit dem angemeldeten "
        "Konto vorbelegt",
        "Die Katze ist doppelt so groß, hektischer und im Pixelraster des "
        "Originals gezeichnet – mit Zickzack-Regenbogen und funkelnden "
        "Pixelsternen",
    ]},
    {"version": "1.9", "titel": "Handelnde Person entfällt, Arbeitszeit aufgeräumt", "punkte": [
        "Das Feld „Handelnde Person“ ist ersatzlos entfallen. Wer eine "
        "Änderung vornimmt, kommt jetzt überall aus der Anmeldung – so "
        "wie es beim Löschen schon immer war. Das Feld stammte aus der "
        "Zeit vor den Benutzerkonten, stand verwirrend neben der "
        "zuständigen Person und taugte als Nachweis ohnehin nicht: man "
        "konnte jeden beliebigen Namen wählen. Im Verlauf steht jetzt "
        "immer das Konto, das die Änderung gemacht hat",
        "Das Anlegeformular hat dadurch nur noch zwei Blöcke und kommt "
        "mit einem Feld weniger aus",
        "Manuelle Zeiterfassung: der Mitarbeitername steht in einem "
        "eigenen Band mit der Marke „gilt für alle Zeilen“ – vorher sah "
        "er aus wie das erste von acht gleichrangigen Feldern. Zwischen "
        "Kopf und Eingabe liegt eine beschriftete Trennlinie, „Weitere "
        "Zeile“ und „Eintrag speichern“ sind sauber voneinander getrennt",
        "Zeitlisten einlesen: statt des nackten Dateifelds, das in jedem "
        "Browser anders aussieht, jetzt eine Ablagefläche mit Symbol, die "
        "nach der Auswahl die Dateinamen anzeigt",
        "Die Katze ist wieder kleiner und ruhiger – der Pixelstil bleibt",
    ]},
    {"version": "1.10", "titel": "Dateien und Wiki mit Rechtsklick, Aufgaben blättern", "punkte": [
        "Aufgaben: ein Schalter blendet erledigte Vorgänge aus. "
        "Standardmäßig sind sie eingeblendet – Erledigtes verschwinden zu "
        "lassen sollte man selbst entscheiden. Dazu höchstens 20 Karten "
        "je Seite mit Blätterleiste",
        "Dateien: in der Seitenleiste stehen nur noch Ordner. Der Baum "
        "zeigt die Struktur, das Hauptfenster den Inhalt – beides doppelt "
        "machte die Leiste bei einem Ordner mit dreißig Bildern "
        "unbrauchbar lang",
        "Dateien: „Hochladen“ und „Neuer Ordner“ stehen jetzt im "
        "Hauptfenster. Sie wirken auf den Ordner, den man gerade ansieht, "
        "und gehören dorthin, wo dessen Inhalt steht",
        "Dateien: Dateien lassen sich vom Rechner direkt ins Fenster "
        "ziehen – auch gezielt auf einen Ordner",
        "Dateien und Wiki: Rechtsklick auf einen Eintrag öffnet ein Menü "
        "mit den passenden Aktionen. Mit Umschalt+Rechtsklick kommt "
        "weiterhin das Menü des Browsers",
        "Dateien: Ordner sind deutlich von Dateien zu unterscheiden – "
        "Akzentfarbe, getönter Hintergrund, Balken links",
        "Dateien: ein Klick auf ein Bild öffnet es im Fenster statt auf "
        "einer neuen Seite",
        "Wiki: derselbe Umschalter zwischen Kacheln und Liste wie bei den "
        "Dateien, und „Neu anlegen“ steht ebenfalls im Hauptfenster",
        "Einstellungen: mehr Luft zwischen „Einstellungen“ und der ersten "
        "Gruppe",
        "Zeiterfassung: der Mitarbeiterblock ist ruhiger gesetzt – die "
        "Marke klebt nicht mehr auf der Kante",
        "Das Zeichen in der Kopfzeile bewegt sich nicht mehr bei jedem "
        "Seitenwechsel",
        "Die Katze ist größer und läuft im Takt des Vorbilds",
    ]},
    {"version": "1.10.1", "titel": "Tabellen ruhiger, Spalten linksbündig", "punkte": [
        "„Mein Bereich“: beide Tabellen stehen jetzt vollständig "
        "linksbündig – „Dauer“ war als einzige Spalte rechtsbündig und "
        "sah daneben wie ein Fremdkörper aus",
        "Die Liste der eigenen Zeiten ist etwas kleiner gesetzt und "
        "bekommt hinter jeder Dauer einen Balken: zwanzig HH:MM-Werte "
        "untereinander sagen nicht, welche Einheit lang und welche kurz "
        "war. Die Balken wachsen beim Laden einmal auf, die Zeile hebt "
        "sich beim Überfahren",
        "Auch die Monatsübersicht trägt jetzt ihre Einheiten im "
        "Spaltenkopf",
        "Auswertung: die zweizeiligen Spaltenköpfe haben mehr Luft "
        "zwischen Titel und Einheit und eine kräftigere Linie darunter",
        "Dateien: in der Spalte „Geändert“ stehen Datum und Uhrzeit "
        "untereinander. Als „30.08.2026, 11:43“ brach die Spalte an einer "
        "beliebigen Stelle um – wo genau, entschied die Fensterbreite",
    ]},
    {"version": "1.11", "titel": "Sicherung, Schutz und pflegbare Texte", "punkte": [
        "Jeden Sonntag legt das Tool von selbst eine Kopie der Datenbank "
        "ab. Die fünf jüngsten bleiben liegen, ältere werden verworfen. "
        "Die Liste steht unter Einstellungen → System",
        "Schutz vor fremden Formularen: eine schreibende Anfrage, die "
        "nicht von einer Seite des Tools kommt, wird abgewiesen. Das "
        "läuft an einer Stelle für die ganze Anwendung und braucht kein "
        "Skript",
        "Neuer E-Mail-Anlass: eine gesammelte Erinnerung an "
        "Bewilligungen, die auslaufen, abgelaufen sind oder fehlen. "
        "Empfänger, Vorlauf und Vorlage stehen in den Einstellungen, "
        "verschickt wird höchstens eine Mail je Woche",
        "Einstellungen → System: fehlende Standardtexte lassen sich "
        "nachziehen. Bisher gewann eine einmal angelegte strings.txt "
        "gegen jeden verbesserten Text aus einem Update – der kam damit "
        "nie an. „Fehlende ergänzen“ lässt eigene Formulierungen in Ruhe",
        "Die Fußzeile steht in drei Zeilen, und der mittlere Satz sowie "
        "die Rechtezeile lassen sich in den Einstellungen selbst "
        "beschriften",
        "Aufgaben: der Schalter „Erledigte ausblenden“ tut jetzt etwas – "
        "das Skript dazu stand versehentlich vor der Checkbox",
        "Keine Animationen mehr im Menü am Handy",
        "Statt der fliegenden Katze hängt jetzt ein müdes Faultier im "
        "Baum, wenn nichts zu tun ist",
    ]},
    {"version": "1.12", "titel": "Verlauf mit Aussage, Faultier mit Leben", "punkte": [
        "„Mein Bereich“: das Verlaufsdiagramm zeigt nicht mehr nur, wie "
        "viel erfasst wurde, sondern auch den Abstand zum Soll – der "
        "Balken ist geteilt, oben sitzt entweder das Zuviel oder als "
        "gestrichelter Umriss das Fehlende",
        "Die Balken wachsen beim Laden aus der Grundlinie, die Saldolinie "
        "zeichnet sich ein; wer die Maus über einen Monat hält, sieht "
        "Stunden und Saldo",
        "Erinnerung an Bewilligungen jetzt an mehrere Empfänger "
        "gleichzeitig, angehakt statt ausgewählt",
        "Das Faultier hat eine Nachtszene bekommen: Mond, Sterne, eine "
        "Motte – und es atmet, wippt mit dem Kopf und gähnt alle "
        "dreizehn Sekunden",
        "Prüfung von 837 auf 862 Einzelprüfungen erweitert",
    ]},
    {"version": "1.12.1", "titel": "Folgebescheide zählen, Diagramm lesbar", "punkte": [
        "Ist zu einer auslaufenden Bewilligung bereits ein Folgebescheid "
        "hinterlegt, wird nicht mehr gewarnt – weder in „Mein Bereich“ "
        "noch per E-Mail. Genau dafür ist der Hinweis da, und wenn er "
        "sich nicht abstellen lässt, taugt er nichts",
        "In den Einstellungen stand bei einer auslaufenden Bewilligung "
        "„keine Bewilligung hinterlegt“ – auch bei zwei gepflegten "
        "Zeiträumen. Der Anzeige fehlte schlicht dieser Fall",
        "Die Zeile nennt jetzt „läuft aus am …“ und, falls vorhanden, "
        "den Folgebescheid",
        "Verlaufsdiagramm: die Werte beim Überfahren standen im dunklen "
        "Thema in Schwarz auf Schwarz – zwei Farbnamen waren falsch "
        "geschrieben. Die Beschriftungen sind außerdem etwas kleiner",
        "Die Animation des Diagramms läuft erst, wenn es im Bild steht – "
        "vorher war sie vorbei, bevor man hingescrollt hatte",
        "Prüfung von 862 auf 877 Einzelprüfungen erweitert",
    ]},
    {"version": "1.13", "titel": "Auswahl statt Tippfehler, Wiki zum Zuklappen", "punkte": [
        "Manuelle Zeiterfassung: „Betreuter“ heißt „Betreute Person“ und "
        "ist ein Auswahlfeld. Eigene Namen lassen sich nicht mehr "
        "eintippen – dieselbe Person landete sonst in drei Schreibweisen "
        "in der Auswertung. Getippt werden darf trotzdem: das Feld "
        "durchsucht die Liste, wie die Filter auch",
        "Der Mitarbeiterblock darüber steht in einer Spalte statt in zwei "
        "verschieden hohen Hälften nebeneinander",
        "Abgaben: wer etwas abgegeben hat, ist anklickbar – der Name "
        "führt in die Übersicht, gefiltert auf diese Person und diesen "
        "Monat",
        "Übersicht: die Kästchen stehen wieder auf der Höhe ihres Datums, "
        "auch wenn die Leistung über drei Zeilen läuft",
        "Übersicht: Suchfeld vor dem Schalter „nur abrechenbare Zeiten“",
        "Wiki: jede Überschrift lässt sich samt Inhalt zuklappen, dazu "
        "ein Knopf für alle auf einmal. Bei einem Stammblatt mit fünfzehn "
        "Abschnitten der einzige Weg, den einen zu finden",
        "„Mein Bereich“: aus dem Faultier ist ein Panda geworden, der "
        "nachts auf dem Ast sitzt, Bambus kaut und döst – mit mehr Luft "
        "zum Rand der Karte",
        "„Mein Bereich“: „Meine Zeiten“ und die Monatsübersicht rollen am "
        "Handy seitlich, statt sich unlesbar zu stauchen",
        "Prüfung von 878 auf 900 Einzelprüfungen erweitert",
    ]},
    {"version": "1.14", "titel": "Aubergine, drei Erinnerungen, ruhigere Ordner", "punkte": [
        "Der dunkle Grund ist jetzt ein sehr dunkles Aubergine statt "
        "eines neutralen Grautons – die rosa Akzentfarbe stand darauf "
        "vorher beziehungslos daneben",
        "E-Mail-Versand: Erinnerung an die Zeiterfassung und Erinnerung "
        "an Fristen lassen sich einzeln einstellen, wie die Bewilligungen "
        "auch. Neu dabei: ein Stichtag für die Monatsabgabe (wer bis zum "
        "Fünften Zeit hat, wird nicht am Ersten erinnert), ein Vorlauf "
        "für Fristen (Vorwarnung vor dem Termin) und Mitlesende, die "
        "dieselbe Fristmeldung bekommen",
        "Dateien: Ordner und Dateien unterscheiden sich am getönten "
        "Symbolfeld statt an einem senkrechten Balken an der Zeilenkante",
        "Auswertung: die Spalte „Einh.“ heißt „Einheit“ und ist breiter, "
        "darunter steht „Anz“",
        "„Mein Bereich“: die Spalte „Dauer“ ist breiter und trägt keine "
        "Einheit mehr, „Betreute Person“ heißt dort wieder „Betreuter“",
        "Zeiterfassung: in den Abgaben führt jetzt jeder Name in die "
        "Übersicht, auch der ohne Abgabe – die leere Liste ist dort die "
        "Antwort auf die Frage, mit der man hinklickt",
        "Prüfung von 900 auf 915 Einzelprüfungen erweitert",
    ]},
    {"version": "1.15", "titel": "Datenpflege, Wiki-Baum, kleinere Politur", "punkte": [
        "Neu: „Arbeitszeit → Datenpflege“. Damit lassen sich viele "
        "Einträge auf einen gemeinsamen Wert ziehen – etwa „AU“, „krank“ "
        "und „Krankheit“ auf eine Schreibweise. Auch Mitarbeiter und "
        "betreute Personen lassen sich so umbenennen, wahlweise nur in "
        "den Zeiten oder überall: Stammeintrag, Benutzerkonto, Aufgaben, "
        "Logbuch und E-Mail-Listen",
        "Die Datenpflege ist bewusst eng abgesichert: eigener "
        "Berechtigungsbereich UND fest auf Administratoren begrenzt, "
        "zwei Schritte mit Vorschau je betroffener Stelle, das Wort "
        "ÄNDERN muss getippt werden, und unmittelbar davor legt das Tool "
        "eine Sicherung an",
        "⚠️ Ein Stammeintrag wird dabei nie gelöscht. Wird auf einen "
        "Namen umbenannt, den es schon gibt, wird der alte nur "
        "stillgelegt – bewilligte Zeiträume und Urlaubstage bleiben",
        "Wiki: ein Knopf über dem Baum klappt alle Ordner auf einmal auf "
        "und wieder zu",
        "Wiki: die linke Spalte wächst auf breiten Fenstern mit und "
        "rückt weniger tief ein – ein voll aufgeklappter Baum passt jetzt "
        "hinein, statt seitlich abgeschnitten zu werden",
        "Auswertung: kein Eurozeichen mehr hinter jedem Wert in den "
        "Spalten „Satz“ und „Verdienst“ – es steht im Spaltenkopf",
        "Prüfung von 915 auf 949 Einzelprüfungen erweitert",
    ]},
    {"version": "1.15.1", "titel": "Datenpflege gewarnt, Wiki aufgeräumt", "punkte": [
        "Über der Datenpflege steht jetzt ein deutlicher Hinweis, und die "
        "Karte selbst trägt einen rötlichen Ton – auf einem "
        "Bildschirmfoto ist damit sofort zu sehen, dass das hier nicht "
        "das übliche Formular ist",
        "Die Datenpflege ist bei einem normalen Konto nicht mehr "
        "automatisch dabei. „Kein Haken“ heißt sonst „alles erlaubt“; für "
        "diesen einen Bereich gilt das ausdrücklich nicht – er muss "
        "einzeln erteilt werden und ist in der Benutzerverwaltung als "
        "solcher gekennzeichnet",
        "Wiki: statt des breiten Knopfes klappt ein kleines Zeichen "
        "rechts über dem Baum alle Ordner auf und zu",
        "Wiki: Suchfeld und Lupe stecken in einem gemeinsamen Kasten und "
        "sind dadurch gleich hoch – vorher standen sie als zwei "
        "verschieden hohe Kästchen nebeneinander",
        "Prüfung von 949 auf 956 Einzelprüfungen erweitert",
    ]},
    {"version": "1.15.2", "titel": "Einstellungen zur Oberfläche neu geordnet", "punkte": [
        "Statt eines Kippschalters mit wechselndem Wort stehen beide "
        "Möglichkeiten nebeneinander, die gewählte ist hervorgehoben. "
        "Vorher musste man raten, ob „Hell“ neben dem Schalter den "
        "aktuellen Zustand meint oder das, was beim Klicken passiert",
        "Die vier Einstellungen stehen in zwei Gruppen: „Darstellung“ "
        "(Farben, Inhaltsbreite) und „Listen oder Kacheln“ (Wiki, "
        "Dateien)",
        "Die Steuerung steht in einer eigenen Spalte und rutscht nicht "
        "mehr unter den Text, sobald eine Beschreibung zwei Zeilen "
        "braucht – am Handy steht sie bei allen vier gleich",
        "Prüfung von 956 auf 957 Einzelprüfungen erweitert",
    ]},
    {"version": "1.15.3", "titel": "Werkzeugleisten aufgeräumt", "punkte": [
        "Dateien: „Dateien hochladen“ und „Neuer Ordner“ sind gleich "
        "hoch. Der eine ist ein Label, der andere ein Knopf – die "
        "bringen vom Browser verschiedene Zeilenhöhen mit; die steht "
        "jetzt fest",
        "Dateien: der Knopf „Öffnen“ ist entfallen. Ein Klick auf den "
        "Dateinamen tut dasselbe, und die Spalte „Aktionen“ ist damit "
        "eine Schaltfläche schmaler",
        "Wiki: „Neue Seite oder neuen Ordner anlegen“ ist keine "
        "aufklappbare Zeile mehr, sondern ein Zeichen in der linken "
        "Spalte neben dem Falt-Zeichen – und funktioniert jetzt auch von "
        "einer Seite aus, nicht nur aus einem Ordner",
        "Wiki: dasselbe Anlegeformular stand auf einer Ordnerseite "
        "doppelt. Jetzt steht es genau einmal",
        "Wiki: „Ordner löschen“ ist ein kleiner Mülleimer, der "
        "Ansichtsumschalter ein Zeichen – und beide haben die Plätze "
        "getauscht",
        "Einstellungen → Oberfläche: alle vier Umschalter sind gleich "
        "breit, und Wiki wie Dateien stehen in derselben Reihenfolge",
        "Prüfung von 957 auf 967 Einzelprüfungen erweitert",
    ]},
]
