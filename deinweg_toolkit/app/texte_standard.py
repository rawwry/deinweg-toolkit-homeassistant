"""Eingebaute Standardtexte der Oberflaeche.

Greifen immer dann, wenn ein Schluessel in strings.txt fehlt. Die
Pflege zur Laufzeit laeuft ueber strings.txt, siehe main.texte().
Ausgelagert aus main.py, weil es reine Daten sind.
"""

from __future__ import annotations

TEXTE_STANDARD: dict[str, str] = {}

TEXTE_STANDARD["start.kein_team"] = (
    "Noch niemand im Team – <a href=\"/einstellungen?bereich=mitarbeiter\">anlegen</a>.")
TEXTE_STANDARD["start.vorschau_offen"] = (
    "Diese Dateien wurden eingelesen, sind aber noch nicht im Bestand. "
    "Öffne die Vorschau, prüfe die Zeilen und übernimm sie oder verwirf sie.")
TEXTE_STANDARD["start.upload_name"] = (
    "Der gewählte Name gilt für alle Zeilen der Datei – auch dann, wenn "
    "sie eine eigene Mitarbeiterspalte mitbringt.")
TEXTE_STANDARD["start.upload"] = (
    "Exporte aus Working Hours oder vergleichbare Listen als .xlsx oder .csv hochladen. Vor dem Speichern siehst du eine Vorschau mit allen Dopplungen oder anderen Fuckups.")
TEXTE_STANDARD["erfassung.lead"] = (
    "Für alle, die ihre Liste nicht aus Working Hours exportieren. Mitarbeiter einmal oben eintragen, dann Zeile für Zeile abtippen – der Name und das Datum bleiben stehen, bis du sie änderst.")
TEXTE_STANDARD["erfassung.leer"] = (
    "Noch nichts von Hand erfasst für {mitarbeiter}.")
TEXTE_STANDARD["datensaetze.leer"] = (
    "Keine Einträge für diesen Filter.")
TEXTE_STANDARD["auswertung.soll_erklaerung"] = (
    "Soll = Wochenkontingent × 4,33 je Monat, auf 15 Minuten gerundet. Gepflegt unter <a href=\"/einstellungen?bereich=betreute\">Betreute Personen</a>.")
TEXTE_STANDARD["auswertung.soll_fehlt"] = (
    "Für einen Soll-Ist-Vergleich unter <a href=\"/einstellungen?bereich=betreute\">Betreute Personen</a> Wochenstunden hinterlegen.")
TEXTE_STANDARD["auswertung.gestaffelt"] = (
    "Bei mindestens einer Person haben sich Wochenstunden oder "
    "Stundensatz innerhalb des Zeitraums geändert. Gerechnet wird dann "
    "Monat für Monat mit den Werten, die im jeweiligen Monat galten.")
TEXTE_STANDARD["auswertung.monate_lead"] = (
    "Darunter steht jeder Monat des gewählten Zeitraums einzeln – mit dem "
    "Kontingent und dem Stundensatz, die in genau diesem Monat bewilligt "
    "waren. Monate ohne erfasste Zeiten bleiben stehen, solange für sie "
    "etwas bewilligt war: eine Lücke fällt sonst nicht auf.")
TEXTE_STANDARD["auswertung.monatsliste_lead"] = (
    "Ein Klick führt zum ausführlichen Block.")
TEXTE_STANDARD["auswertung.bewilligt_lead"] = (
    "Die Bescheide, die den gewählten Zeitraum berühren.")
TEXTE_STANDARD["auswertung.monat_leer"] = (
    "In diesem Monat ist nichts erfasst – bewilligt war trotzdem etwas.")
TEXTE_STANDARD["auswertung.tabelle_leer"] = (
    "Für {zeitraum} sind keine Zeiten erfasst.")
TEXTE_STANDARD["auswertung.verdienst_hinweis"] = (
    "Rechnerischer Wert der bisher erfassten Zeiten. Keine Abrechnung.")
TEXTE_STANDARD["bearbeiten.dauer_hinweis"] = (
    "Leer gelassene Dauer wird aus Beginn und Ende berechnet. Eine eingetragene Dauer gewinnt gegenüber der Zeitspanne – praktisch für Zettel ohne Uhrzeiten.")
TEXTE_STANDARD["bearbeiten.lead"] = (
    "Ursprünglich eingelesen am {zeitpunkt}. Änderungen wirken sich sofort auf Auswertung und Export aus.")
TEXTE_STANDARD["ideen.bearbeiten_hinweis"] = (
    "Eingegangen am {zeitpunkt} – der Zeitpunkt bleibt unverändert.")
TEXTE_STANDARD["ideen.hinweis_datei"] = (
    "Die Einträge landen unverändert in <code>ideen.txt</code> im Ordner der Anwendung. Erledigtes kann dort direkt gestrichen werden, die Seite liest die Datei bei jedem Aufruf neu.")
TEXTE_STANDARD["ideen.hinweis_fehler"] = (
    "Konkrete Fehler sind am hilfreichsten mit Datum, betroffener Person und dem, was auf dem Bildschirm stand.")
TEXTE_STANDARD["ideen.lead"] = (
    "Was fehlt, was nervt, was ist kaputt? Hier rein damit. Jede Rückmeldung wird gelesen und landet auf der Liste für die nächsten Versionen. Wer mag, trägt seinen Namen ein – nötig ist das nicht.")
TEXTE_STANDARD["ideen.leer"] = (
    "Noch nichts eingegangen. Du darfst der Erste sein.")
TEXTE_STANDARD["changelog.lead"] = (
    "Was sich von Version zu Version geändert hat. Hier läuft gerade <strong>{version}</strong> – die Nummer steht auch unten auf jeder Seite.")
TEXTE_STANDARD["einst.ansicht"] = (
    "Dunkel ist die Voreinstellung und schont abends die Augen.")
TEXTE_STANDARD["einst.betreute_lead"] = (
    "Hier stehen die Menschen, für die ein wöchentliches Stundenkontingent vereinbart ist. Die Auswertung rechnet das Kontingent auf den gewählten Monat hoch und zeigt, ob zu viel oder zu wenig geleistet wurde.")
TEXTE_STANDARD["einst.breite"] = (
    "Volle Breite zeigt mehr Tabelle auf einmal. Begrenzt hält die Textzeilen kürzer und ist auf sehr breiten Monitoren angenehmer zu lesen.")
TEXTE_STANDARD["einst.sprueche_lead"] = (
    "Diese Sprüche erscheinen zufällig ausgewählt auf der Startseite. Wird "
    "eine Quelle angegeben, steht sie kleiner darunter. Die "
    "Anführungszeichen setzt das Toolkit selbst – bitte nur den reinen "
    "Wortlaut eintragen. Gespeichert wird in der Datei quotes.txt im "
    "/texte-Volume; wer lieber dort direkt schreibt, kann das weiterhin "
    "tun, hier ist es nur bequemer.")
TEXTE_STANDARD["einst.sprueche_leer"] = (
    "Noch kein Spruch hinterlegt – die Startseite zeigt dann einfach keinen.")
TEXTE_STANDARD["einst.wikiliste"] = (
    "Wie Ordner und Seiten im Wiki aufgelistet werden: als Kacheln oder "
    "als Liste. Die Liste bleibt auch bei vielen Seiten übersichtlich.")
TEXTE_STANDARD["einst.dateiliste"] = (
    "Wie Ordner und Dateien in der Dateiverwaltung aufgelistet "
    "werden: als Liste mit Spalten oder als Kacheln mit Vorschau. "
    "Die Liste zeigt mehr auf einmal, die Kacheln zeigen Bilder.")
TEXTE_STANDARD["einst.inaktiv"] = (
    "Wer das Team verlässt, wird am besten auf <em>inaktiv</em> gesetzt statt entfernt: die Person verschwindet aus der Abgabeübersicht, ihre erfassten Zeiten bleiben aber vollständig erhalten.")
TEXTE_STANDARD["einst.kein_team"] = (
    "Noch niemand angelegt.")
TEXTE_STANDARD["einst.keine_person"] = (
    "Noch keine Person angelegt.")
TEXTE_STANDARD["einst.oberflaeche_lead"] = (
    "Alles hier gilt nur für diesen Browser – jeder Kollege stellt sich das selbst ein. Die Wahl bleibt gespeichert.")
TEXTE_STANDARD["einst.ohne_pflicht"] = (
    "Ohne Abgabepflicht taucht jemand in der Übersicht auf, wird aber nicht angemahnt – etwa Aushilfen oder Leitung.")
TEXTE_STANDARD["einst.rechnung"] = (
    "Das Monatssoll ergibt sich aus den Wochenstunden mal 4,33 – der durchschnittlichen Anzahl Wochen pro Monat. Das Ergebnis wird auf den nächsten 15-Minuten-Takt gerundet, damit keine krummen Zahlen entstehen. Bei 5 Stunden pro Woche sind das <strong>21:45 Std</strong>, und zwar in jedem Monat gleich – anders als bei einer Rechnung über die Kalendertage ist der Februar hier kein Sonderfall.")
TEXTE_STANDARD["einst.schreibweise_betreute"] = (
    "Der Name muss exakt so geschrieben sein wie in den importierten Listen, sonst findet die Auswertung keine Zuordnung. Groß- und Kleinschreibung zählt.")
TEXTE_STANDARD["einst.schreibweise_team"] = (
    "Der Name muss so geschrieben sein wie in der Spalte <code>Tags</code> der Working-Hours-Exporte bzw. wie beim manuellen Eintrag. Groß- und Kleinschreibung sowie zusätzliche Leerzeichen sind dabei egal.")
TEXTE_STANDARD["einst.stillgelegt"] = (
    "Stillgelegte Personen bleiben in der Liste, werden bei der Soll-Rechnung aber übersprungen – praktisch, wenn eine Betreuung ausläuft.")
TEXTE_STANDARD["einst.stundensatz"] = (
    "Der Stundensatz geht in die Box „Verdienst“ der Auswertung ein – als rechnerischer Hinweis, nicht als Abrechnung. Ändert er sich zum Stichtag, gehört das als Zeitraum hinterlegt und nicht in den Grundwert.")
TEXTE_STANDARD["einst.grundwert_hinweis"] = (
    "Der Grundwert gilt für jeden Monat, für den kein Zeitraum hinterlegt "
    "ist. Wer mit Bescheiden arbeitet, trägt alles unten als Zeitraum ein "
    "und lässt den Grundwert auf 0.")
TEXTE_STANDARD["einst.zeitraum_hinweis"] = (
    "Was der Kostenträger jeweils zugesagt hat. Ein Zeitraum ohne Ende "
    "gilt bis auf Weiteres. Überschneiden sich zwei, gewinnt der später "
    "begonnene – so wirkt ein Folgebescheid sofort, auch wenn der alte "
    "formal noch läuft. <strong>Gerechnet wird monatsweise:</strong> ein "
    "Zeitraum gilt für jeden Monat, den er berührt.")
TEXTE_STANDARD["einst.zeitraum_leer"] = (
    "Noch kein Zeitraum hinterlegt – es gilt der Grundwert oben.")
TEXTE_STANDARD["einst.abrechenbar"] = (
    "Legt fest, ob Zeiten dieser Person beim Filter „nur abrechenbare Zeiten“ auf den Seiten Datensätze und Auswertung mitgezählt werden. Betrifft nur diesen Filter, nicht die Soll-Rechnung oder sonstige Zahlen.")
TEXTE_STANDARD["einst.system_lead"] = (
    "Was gerade läuft und wo die Daten liegen – hilfreich, wenn etwas klemmt oder du beim Backup nachsehen willst.")
TEXTE_STANDARD["einst.team_lead"] = (
    "Das Team. Wer hier mit Abgabepflicht steht, erscheint auf der Startseite in der Abgabeübersicht – so ist auf einen Blick klar, hinter wessen Liste noch hergelaufen werden muss.")
TEXTE_STANDARD["einst.team_offen"] = (
    "Zum Übernehmen anklicken. Steht hier eine abweichende Schreibweise eines bekannten Namens, korrigier besser den Namen unten in der Liste.")
TEXTE_STANDARD["vorgaenge.lead"] = (
    "Alles Organisatorische rund um die betreuten Personen: Berichte, Anträge, "
    "Fortschreibungen, Rückmeldungen des LWL, Fristen. Hier gehört hin, was "
    "gegenüber Ämtern und Kostenträgern läuft – nicht die pädagogische Arbeit "
    "im Alltag.")
TEXTE_STANDARD["vorgaenge.anlegen_hinweis"] = (
    "Die betreuten Personen kommen aus den hochgeladenen Arbeitslisten und "
    "werden hier nicht neu angelegt. Fehlt jemand in der Auswahl, liegt für "
    "diese Person noch keine erfasste Zeit vor.")
TEXTE_STANDARD["vorgaenge.datei_hinweis"] = (
    "Der Dokumentenverweis ist ein reiner Textvermerk – etwa der Ablageort auf "
    "dem Server. Dateien selbst werden im Tool nicht gespeichert.")
TEXTE_STANDARD["vorgaenge.zustaendig_hinweis"] = (
    "Die <strong>zuständige Person</strong> bearbeitet den Vorgang von "
    "jetzt an. Sie steht in der Liste, wird bei Fristen per E-Mail "
    "erinnert, und über sie filtert man „meine Aufgaben“. Sie kann "
    "später jederzeit gewechselt werden.")
TEXTE_STANDARD["vorgaenge.protokoll_hinweis"] = (
    "Jede Änderung an einem Vorgang landet mit Zeitpunkt und Konto im "
    "Verlauf – dafür ist nichts auszufüllen, das kommt aus deiner "
    "Anmeldung.")
TEXTE_STANDARD["vorgaenge.keine_personen"] = (
    "Noch keine betreute Person im System. Lade zuerst eine Arbeitsliste hoch "
    "oder erfasse Zeiten von Hand, dann steht die Auswahl hier bereit.")
TEXTE_STANDARD["vorgaenge.leer"] = (
    "Kein Vorgang für diesen Filter.")
TEXTE_STANDARD["vorgaenge.stand_hinweis"] = (
    "Der Status wird nicht einfach überschrieben: jede Änderung landet mit "
    "Zeitpunkt, Namen und Notiz im Logbuch der betreuten Person.")
TEXTE_STANDARD["vorgaenge.bearbeiten_hinweis"] = (
    "Für Tippfehler und nachgetragene Daten. Was sich ändert, wird im Verlauf "
    "mit altem und neuem Wert festgehalten.")
TEXTE_STANDARD["vorgaenge.archiv_hinweis"] = (
    "Erledigte Vorgänge werden nicht gelöscht. Sie bleiben hier dauerhaft "
    "abrufbar, damit nachvollziehbar ist, was wann von wem erledigt wurde.")
TEXTE_STANDARD["vorgaenge.logbuch_lead"] = (
    "Jeder organisatorische Schritt über alle betreuten Personen hinweg, "
    "neueste zuerst. Einträge entstehen automatisch und lassen sich nicht "
    "nachträglich ändern.")
TEXTE_STANDARD["einst.ungepflegt"] = (
    "Diese Namen tauchen in erfassten Zeiten auf, haben aber kein Kontingent. Zum Übernehmen anklicken – die Wochenstunden trägst du danach ein.")
TEXTE_STANDARD["einst.vorgangsarten_lead"] = (
    "Die Vorgangsarten stehen im Anlegen-Formular der Aufgaben zur "
    "Auswahl. Lege hier an, was für euch tatsächlich vorkommt – die Liste "
    "muss zu Beginn nicht vollständig sein und lässt sich jederzeit erweitern.")
TEXTE_STANDARD["einst.vorgangsarten_offen"] = (
    "Diese Bezeichnungen tauchen an bestehenden Vorgängen auf, stehen aber "
    "noch nicht in der Liste unten. Zum Übernehmen anklicken.")
TEXTE_STANDARD["einst.vorgangsarten_stillgelegt"] = (
    "Stillgelegte Vorgangsarten verschwinden aus der Auswahl beim Anlegen, "
    "bleiben aber an bereits bestehenden Vorgängen sichtbar und dort auch "
    "weiterhin auswählbar.")
TEXTE_STANDARD["einst.vorgangsarten_keine"] = (
    "Noch keine Vorgangsart angelegt.")
TEXTE_STANDARD["einst.leistungen_lead"] = (
    "Diese Bezeichnungen stehen auf der Seite „Manueller Eintrag“ zur Auswahl. "
    "Sinn der Sache ist eine einheitliche Schreibweise: dieselbe Leistung soll "
    "nicht in fünf Varianten im Bestand landen. Gespeichert wird weiterhin nur "
    "der Text selbst – eine später geänderte Bezeichnung wirkt sich deshalb "
    "nicht rückwirkend auf bereits erfasste Zeiten aus.")
TEXTE_STANDARD["einst.leistungen_offen"] = (
    "Diese Beschreibungen kommen in den erfassten Zeiten am häufigsten vor, "
    "stehen aber noch nicht in der Auswahl. Zum Übernehmen anklicken.")
TEXTE_STANDARD["einst.leistungen_stillgelegt"] = (
    "Stillgelegte Bezeichnungen verschwinden aus der Auswahl beim manuellen "
    "Eintrag, bleiben hier aber erhalten und lassen sich jederzeit wieder "
    "einschalten.")
TEXTE_STANDARD["einst.leistungen_keine"] = (
    "Noch keine Leistungsbeschreibung angelegt. Solange die Liste leer ist, "
    "steht beim manuellen Eintrag nur das freie Textfeld zur Verfügung.")
TEXTE_STANDARD["erfassung.kein_team"] = (
    "Es ist noch niemand im Team eingetragen. Ohne Mitarbeiter lässt "
    "sich keine Zeit erfassen – trag die Namen unter Einstellungen → "
    "Mitarbeiter ein.")
TEXTE_STANDARD["erfassung.leistung_leer"] = (
    "Vordefinierte Leistungsbeschreibungen lassen sich unter "
    "<strong>Einstellungen → Leistungsbeschreibungen</strong> anlegen. "
    "Sie erscheinen dann hier als Auswahl.")
TEXTE_STANDARD["einst.benutzer_lead"] = (
    "Login-Konten für die Anwendung. Das ist unabhängig von den unter "
    "„Mitarbeiter“ gepflegten Namen für die Abgabeübersicht – ein "
    "Mitarbeiter braucht keinen Login, ein Login muss keinem Mitarbeiter "
    "entsprechen.")
TEXTE_STANDARD["einst.benutzer_bereiche_hinweis"] = (
    "Alle angehakten Bereiche darf das Konto nutzen. Sind alle angehakt, "
    "gilt das als voller Zugriff und schließt auch später neu "
    "hinzukommende Bereiche automatisch mit ein. Bei der Rolle "
    "„Administrator“ hat diese Auswahl keine Wirkung.")
TEXTE_STANDARD["einst.benutzer_einstpunkte_hinweis"] = (
    "Eine Ebene unter dem Bereich „Einstellungen“: welche Punkte darin "
    "sichtbar sind. Sind alle angehakt, gilt das als voller Zugriff und "
    "schließt später hinzukommende Punkte mit ein. „Oberfläche“ bleibt "
    "immer sichtbar – dort stehen nur Darkmode, Breite und die "
    "Ansichtsschalter, die jeder für sich selbst einstellt.")
TEXTE_STANDARD["einst.benutzer_admin_hinweis"] = (
    "Die Rolle ist „Administrator“ – dieses Konto hat damit ohnehin "
    "vollen Zugriff. Die Auswahl unten wird trotzdem gespeichert und "
    "greift wieder, sobald die Rolle auf „Benutzer“ zurückgestellt wird.")
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
TEXTE_STANDARD["einst.benutzer_selbst"] = "das eigene Konto"
TEXTE_STANDARD["mein.konto_lead"] = (
    "Hier änderst du dein eigenes Passwort und die Adresse, an die "
    "Erinnerungen gehen. Alles Weitere an deinem Konto – Rolle, Zugriff "
    "auf Bereiche, Zuordnung zu einem Mitarbeiter – pflegt eine Person "
    "mit Administratorrechten.")
TEXTE_STANDARD["einst.benutzer_keine"] = "Noch kein Konto angelegt."
TEXTE_STANDARD["einst.monatsstunden"] = (
    "Die monatliche Arbeitszeit ist die Grundlage für den persönlichen "
    "Bereich: Jede Person sieht dort, ob sie im Plus oder Minus liegt. Ohne "
    "Eintrag (0) wird für sie kein Saldo berechnet.")
TEXTE_STANDARD["mein.lead"] = (
    "Deine erfassten Zeiten als {name}, gegenübergestellt dem hinterlegten "
    "Monatssoll. Diese Seite sieht nur du – andere Konten sehen hier ihre "
    "eigenen Zahlen.")
TEXTE_STANDARD["mein.keine_zuordnung"] = (
    "Diesem Konto ist kein Mitarbeiter zugeordnet, deshalb lassen sich keine "
    "persönlichen Zahlen anzeigen. Ein Administrator kann die Zuordnung unter "
    "Einstellungen → Benutzerverwaltung im Feld „Gehört zu Mitarbeiter“ "
    "setzen.")
TEXTE_STANDARD["mein.verwaist"] = (
    "Das Konto ist „{name}“ zugeordnet – diesen Namen gibt es im Team aber "
    "nicht mehr. Erfasste Zeiten werden weiterhin angezeigt, ein Monatssoll "
    "lässt sich so jedoch nicht hinterlegen.")
TEXTE_STANDARD["mein.kein_soll"] = (
    "Für dich ist noch keine monatliche Arbeitszeit hinterlegt, deshalb wird "
    "kein Saldo berechnet. Ein Administrator trägt sie unter Einstellungen → "
    "Mitarbeiter ein.")
TEXTE_STANDARD["mein.laufend_hinweis"] = (
    "Der laufende Monat zählt noch nicht in den Saldo oben – sonst stünde "
    "man am Monatsanfang immer tief im Minus.")
TEXTE_STANDARD["mein.kein_laufender"] = (
    "Für diesen Monat sind noch keine Zeiten erfasst.")
TEXTE_STANDARD["mein.kein_abgeschlossener"] = (
    "Noch kein abgeschlossener Monat vorhanden – die Auswertung beginnt, "
    "sobald der erste Monat vorbei ist.")
TEXTE_STANDARD["mein.diagramm_hinweis"] = (
    "Jeder Balken ist ein Monat: grün, wenn das Soll erreicht wurde, sonst "
    "rot. Die gestrichelte Linie zeigt das Monatssoll, die durchgezogene "
    "Linie den aufsummierten Saldo über die abgeschlossenen Monate – steigt "
    "sie, baust du Überstunden auf.")
TEXTE_STANDARD["mein.urlaub_hinweis"] = (
    "Gezählt werden Tage, an denen ein Eintrag mit der Beschreibung „Urlaub“ "
    "steht – ein Tag zählt einmal, auch bei mehreren Zeilen. Halbe "
    "Urlaubstage erkennt die Zählung nicht, sie zählen als ganzer Tag.")
TEXTE_STANDARD["mein.kein_urlaubsanspruch"] = (
    "Für dich ist noch kein Urlaubsanspruch hinterlegt, deshalb wird nur "
    "gezählt, aber nichts gegengerechnet. Ein Administrator trägt ihn unter "
    "Einstellungen → Mitarbeiter ein.")
TEXTE_STANDARD["einst.urlaubstage"] = (
    "Der Urlaubsanspruch in Tagen pro Kalenderjahr. Im persönlichen Bereich "
    "sieht jede Person davon ausgehend, wie viele Tage sie schon genommen "
    "hat und wie viele noch offen sind. 0 = kein Anspruch hinterlegt.")
TEXTE_STANDARD["mein.bewilligungen_lead"] = (
    "Abgelaufen, läuft in den nächsten 60 Tagen aus oder fehlt ganz – "
    "hier gehört ein Folgeantrag raus.")
TEXTE_STANDARD["mein.keine_aufgaben"] = (
    "Auf dich läuft gerade kein offener Vorgang. Neue Aufgaben tauchen "
    "hier auf, sobald dir eine zugewiesen wird.")
TEXTE_STANDARD["mein.ansteht_lead"] = (
    "Was auf deinem Tisch liegt: eigene Aufgaben mit Frist und "
    "Bewilligungen, die nachgehalten werden müssen.")
TEXTE_STANDARD["mein.bewilligungen_gut"] = (
    "Bei keiner betreuten Person läuft gerade eine Bewilligung aus oder "
    "fehlt.")
TEXTE_STANDARD["mein.zeiten_lead"] = (
    "Alle Zeiten, die auf deinen Namen laufen. Hier stehen sie unabhängig "
    "davon, ob du die Übersicht unter „Arbeitszeit“ nutzen darfst – deine "
    "eigenen Einträge kannst du immer richtigstellen oder entfernen.")
TEXTE_STANDARD["mein.zeiten_leer"] = (
    "Für diesen Zeitraum ist nichts erfasst.")
TEXTE_STANDARD["mein.zeiten_gekappt"] = (
    "Es werden die neuesten {max} Einträge gezeigt. Für ältere wähle oben "
    "einen Monat.")
TEXTE_STANDARD["mein.tabelle_hinweis"] = (
    "Monate ohne erfasste Zeiten erscheinen mit dem vollen Soll im Minus – "
    "das ist Absicht, damit vergessene Abgaben auffallen. Urlaub, Krankheit "
    "oder Feiertage berücksichtigt die Rechnung nicht.")
TEXTE_STANDARD["mein.keine_zeiten"] = (
    "Für {name} sind bisher keine Zeiten erfasst.")
TEXTE_STANDARD["einst.benutzer_mitarbeiter_hinweis"] = (
    "Legt fest, für wen dieses Konto Erinnerungen bekommt – etwa bei einem "
    "überfälligen Vorgang oder einer fehlenden Monatsabgabe. Ohne Zuordnung "
    "sucht das System nach einem Mitarbeiter, der genauso heißt wie der "
    "Benutzername. Weicht der Benutzername vom Namen im Team ab, sollte die "
    "Zuordnung hier gesetzt werden.")
TEXTE_STANDARD["einst.email_lead"] = (
    "Zugang zum Postausgangsserver für automatische Erinnerungen. Empfänger "
    "ist jeweils die E-Mail-Adresse, die beim Benutzerkonto hinterlegt ist – "
    "wer keinen Login mit Adresse hat, bekommt keine Nachricht.")
TEXTE_STANDARD["einst.email_test_hinweis"] = (
    "Schickt sofort eine Nachricht, unabhängig davon, ob der automatische "
    "Versand eingeschaltet ist. Gut geeignet, um die Zugangsdaten zu prüfen.")
TEXTE_STANDARD["einst.email_pruefen_hinweis"] = (
    "Führt alle Prüfungen sofort aus, statt bis zum nächsten stündlichen "
    "Durchlauf zu warten. Bereits verschickte Erinnerungen werden dabei "
    "nicht erneut versendet.")
TEXTE_STANDARD["einst.email_verlauf_hinweis"] = (
    "Jede Erinnerung wird nur einmal verschickt. Wird eine Frist verschoben, "
    "kann zu diesem Vorgang erneut erinnert werden.")
TEXTE_STANDARD["einst.email_keine"] = "Bisher wurde keine Nachricht verschickt."
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
    "Lädt den kompletten Datenbestand als einzelne Datei herunter. Die "
    "Kopie wird sauber erstellt, auch wenn gerade jemand mit dem Tool "
    "arbeitet. Am besten regelmäßig herunterladen und außerhalb der NAS "
    "aufbewahren.")
TEXTE_STANDARD["einst.sicherung_import"] = (
    "Spielt eine zuvor heruntergeladene Sicherung zurück. Der aktuelle "
    "Datenbestand wird dabei vollständig ersetzt. Die bisherige Datenbank "
    "wird vorher zur Sicherheit daneben abgelegt, gelöscht wird nichts. "
    "Nach dem Einspielen ist eine neue Anmeldung nötig.")
TEXTE_STANDARD["einst.sicherung_automatisch"] = (
    "Jeden Sonntag legt das Tool von selbst eine Kopie der Datenbank ab. "
    "Die fünf jüngsten bleiben liegen, ältere werden verworfen. Das "
    "ersetzt keine Sicherung außer Haus – dafür ist der Knopf darunter "
    "da.")
TEXTE_STANDARD["einst.bewilligungsmail_lead"] = (
    "Erinnert an Bewilligungen, die demnächst auslaufen, bereits "
    "abgelaufen sind oder ganz fehlen. Eine gesammelte Mail je Woche, "
    "keine einzelne je Person.")
TEXTE_STANDARD["einst.bewilligungsmail_hinweis"] = (
    "Der Vorlauf sagt, ab wann eine Bewilligung als auslaufend gilt. "
    "Abgelaufene und fehlende Bewilligungen stehen unabhängig davon "
    "immer mit in der Mail.")
TEXTE_STANDARD["einst.fusszeile_lead"] = (
    "Der Text ganz unten auf jeder Seite. Bleibt ein Feld leer, gilt "
    "wieder der ausgelieferte Wortlaut.")
TEXTE_STANDARD["einst.fusszeile_hinweis"] = (
    "Programmname, Version und der Verweis auf den Changelog stehen "
    "fest in der ersten Zeile und lassen sich nicht ändern.")
TEXTE_STANDARD["einst.texte_lead"] = (
    "Die erklärenden Texte der Oberfläche liegen in <code>strings.txt</code>. "
    "Diese Datei gewinnt gegen die ausgelieferten Texte – neue oder "
    "verbesserte Formulierungen aus einem Update kommen deshalb nicht "
    "von selbst an. „Fehlende Texte ergänzen“ trägt nur nach, was in der "
    "Datei noch gar nicht steht, und lässt eigene Änderungen in Ruhe.")
TEXTE_STANDARD["login.lead"] = (
    "Mit Benutzername und Passwort anmelden, um fortzufahren.")
TEXTE_STANDARD["vorgaenge.verlauf_leer"] = "Noch keine Einträge."
TEXTE_STANDARD["vorgaenge.loeschen_hinweis"] = (
    "Der Vorgang verschwindet dabei vollständig, inklusive seines "
    "Verlaufs. Das lässt sich nicht rückgängig machen. Für einen "
    "abgeschlossenen Vorgang reicht in der Regel der Status „Erledigt“ "
    "oder „Abgebrochen“ – er bleibt dann in der Betreutenansicht als "
    "Archiv erhalten.")
TEXTE_STANDARD["vorgaenge.logbuch_leer"] = "Noch keine Einträge."
TEXTE_STANDARD["vorgaenge.person_keine_offenen"] = (
    "Aktuell ist für {name} kein Vorgang offen.")
TEXTE_STANDARD["vorgaenge.person_keine_archiviert"] = "Noch nichts abgeschlossen."
TEXTE_STANDARD["vorgaenge.person_kein_logbuch"] = (
    "Noch keine organisatorischen Schritte dokumentiert.")
TEXTE_STANDARD["datensaetze.nur_eigene"] = (
    "Auswählbar sind nur deine eigenen Einträge.")
TEXTE_STANDARD["datensaetze.nur_eigene_bearbeiten"] = (
    "Bearbeiten geht ebenfalls nur bei den eigenen.")
TEXTE_STANDARD["datensaetze.nichts_loeschbar"] = (
    "Hier stehen keine Einträge, die du löschen darfst.")
TEXTE_STANDARD["datensaetze.nichts_loeschbar_eigen"] = (
    "Hier stehen keine Einträge, die du löschen darfst – deine eigenen "
    "laufen auf „{name}“.")
TEXTE_STANDARD["kfz.bearbeiten_lead"] = (
    "Änderungen wirken sich sofort auf die Auswertung aus.")
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
    "Hier liegt noch nichts. Lade oben eine Datei hoch oder lege einen "
    "Ordner an.")
TEXTE_STANDARD["dateien.leer"] = (
    "In diesem Ordner liegt noch keine Datei.")
TEXTE_STANDARD["dateien.unbekannt"] = (
    "Diese Dateiart wird nicht unterstützt. Sie bleibt liegen und lässt "
    "sich umbenennen, verschieben oder löschen – öffnen oder ins Wiki "
    "einbinden geht nicht.")
TEXTE_STANDARD["wiki.baum_leer"] = (
    "Im Wiki-Ordner liegt noch nichts. Über „Neu anlegen“ entsteht die "
    "erste Seite oder der erste Ordner.")
TEXTE_STANDARD["wiki.baum_leer_lesen"] = (
    "Im Wiki-Ordner liegt noch nichts. Anlegen darf nur, wer das Recht "
    "„Wiki bearbeiten“ hat.")
TEXTE_STANDARD["wiki.ziehen"] = (
    "Seiten und Ordner lassen sich im Baum mit der Maus auf einen anderen "
    "Ordner ziehen. Vor dem Verschieben wird nachgefragt.")
TEXTE_STANDARD["wiki.editor_lead"] = (
    "Geschrieben wird in Markdown. Dateiname und Ordner lassen sich hier "
    "gleich mit ändern – das Speichern benennt die Datei dann um bzw. "
    "verschiebt sie. Strg+S (bzw. Cmd+S) speichert ebenfalls.")
TEXTE_STANDARD["wiki.ordner_leer"] = (
    "Dieser Ordner ist noch leer.")
TEXTE_STANDARD["wiki.suche_lead"] = (
    "Mindestens zwei Zeichen eingeben. Gesucht wird in den Dateinamen und "
    "im gesamten Text aller Seiten.")
TEXTE_STANDARD["wiki.suche_leer"] = (
    "Keine Seite enthält „{wort}“.")
TEXTE_STANDARD["wiki.fehlt"] = (
    "Unter „{pfad}“ liegt keine Seite. Vielleicht wurde sie umbenannt, "
    "verschoben oder direkt auf der NAS entfernt.")
# --- Fuhrpark ----------------------------------------------------------------

TEXTE_STANDARD["kfz.keine_fahrzeuge"] = (
    "Noch kein Fahrzeug angelegt. Fahrzeuge kommen unter "
    "<a href=\"/einstellungen?bereich=kfz\">Einstellungen → KFZ</a> hinein, "
    "danach lässt sich hier alles dazu erfassen.")
TEXTE_STANDARD["kfz.erfassen_lead"] = (
    "Aussuchen, was passiert ist – der Rest ist ein kurzes Formular. "
    "Ein Kilometerstand, der hier nebenbei mitkommt, zählt automatisch "
    "als Kilometerstand des Fahrzeugs; er muss nicht noch einmal "
    "getrennt erfasst werden.")
TEXTE_STANDARD["kfz.tanken_km_hinweis"] = (
    "Der Kilometerstand ist freiwillig. Ohne ihn zählt die Tankfüllung bei "
    "den Kosten mit, ergibt aber keinen Verbrauchswert – die Liter gehen "
    "trotzdem nicht verloren, sie zählen zur nächsten Volltankung mit "
    "Stand. Aus getrennt erfassten Kilometerständen lässt sich der Stand "
    "an der Zapfsäule nicht ableiten; geschätzte Werte wären erfundene "
    "Statistik.")
TEXTE_STANDARD["kfz.historie_leer"] = (
    "Für {fahrzeug} ist noch nichts erfasst. Der erste Eintrag ist meist "
    "der aktuelle Kilometerstand.")
TEXTE_STANDARD["kfz.intervall_hinweis"] = (
    "Intervall nach Monaten <strong>oder</strong> nach Kilometern – gerne "
    "auch beides. Fällig ist dann, was zuerst eintritt. Ein von Hand "
    "gesetzter Termin gewinnt gegenüber dem Intervall.")
TEXTE_STANDARD["kfz.nichts_faellig"] = (
    "Nichts überfällig, nichts in den nächsten 30 Tagen oder 1.000 "
    "Kilometern. Fälligkeiten entstehen aus den Intervallen, die beim "
    "Erfassen einer Wartung, Inspektion oder des TÜV hinterlegt werden.")
TEXTE_STANDARD["kfz.kennzahlen_unvollstaendig"] = (
    "Kosten je Kilometer und Verbrauch entstehen erst, wenn genug Daten "
    "da sind: dafür braucht es Kilometerstände über den Zeitraum hinweg "
    "und mindestens zwei Volltankungen. Fehlt etwas davon, steht hier "
    "lieber ein Strich als eine falsche Zahl.")
TEXTE_STANDARD["kfz.diagramm_leer"] = (
    "Für eine Kostenentwicklung braucht es Kosten aus mindestens zwei "
    "Monaten.")
TEXTE_STANDARD["kfz.kosten_leer"] = (
    "Für {zeitraum} sind keine Kosten erfasst.")
TEXTE_STANDARD["kfz.verbrauch_leer"] = (
    "Noch keine Verbrauchswerte. Ein Wert entsteht zwischen zwei "
    "Volltankungen – bei der Erfassung also den Haken „Vollgetankt“ stehen "
    "lassen und den Kilometerstand mit eintragen.")
TEXTE_STANDARD["kfz.vergleich_hinweis"] = (
    "„Gefahren“ und „je km“ beziehen sich auf den gewählten Zeitraum und "
    "brauchen erfasste Kilometerstände. Der Verbrauch ist der Schnitt über "
    "alle gewerteten Tankfüllungen, nicht der Mittelwert der Einzelwerte.")
TEXTE_STANDARD["kfz.aktivitaeten_leer"] = (
    "Für {zeitraum} ist nichts erfasst.")

TEXTE_STANDARD["einst.kfz_lead"] = (
    "Die Fahrzeuge des Fuhrparks. Was hier steht, lässt sich unter "
    "<a href=\"/fuhrpark\">Fuhrpark → Erfassung</a> auswählen und mit "
    "Tankvorgängen, Wartungen und Kosten füllen.")
TEXTE_STANDARD["einst.kfz_keine"] = (
    "Noch kein Fahrzeug angelegt.")
TEXTE_STANDARD["einst.kfz_archiv_hinweis"] = (
    "Ein ausgemustertes Fahrzeug gehört ins Archiv, nicht in den "
    "Papierkorb: archiviert verschwindet es aus allen Auswahlen und aus "
    "der Auswertung, seine Historie bleibt aber erhalten.")
TEXTE_STANDARD["einst.kfz_archiv"] = (
    "Archivierte Fahrzeuge tauchen in der Erfassung und in der Auswertung "
    "nicht mehr auf. Zurückholen geht jederzeit.")

TEXTE_STANDARD["footer.text"] = (
    "Dein Weg Toolkit <span class=\"version\">{version}</span>: Organisation "
    "für Menschen, die eigentlich nicht organisieren wollen.<br>"
    "© 2026 <a href=\"https://timovorwald.de\" target=\"_blank\" "
    "rel=\"noopener noreferrer\">timovorwald.de</a>. Alle Rechte vorbehalten.")


