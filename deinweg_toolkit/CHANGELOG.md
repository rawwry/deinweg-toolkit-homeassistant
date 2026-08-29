# Änderungen am Add-on

Die Versionsnummer folgt der Version des Toolkits. Der vollständige
Verlauf der Anwendung selbst steht in der Oberfläche unter „Changelog“.

## 1.3

- Bewilligte Zeiträume je betreuter Person: eigene Wochenstunden und
  Stundensätze mit Datum von/bis, beliebig viele je Person
- Die Auswertung rechnet Soll und Verdienst Monat für Monat mit den
  Werten, die im jeweiligen Monat galten
- Die bisherigen Felder bleiben als Grundwert für Monate ohne Zeitraum —
  bestehende Personen rechnen unverändert weiter
- Betreute Personen als aufklappbare Liste statt als Tabelle
- Verdienst wird auch ohne hinterlegte Wochenstunden gerechnet

## 1.2

- Rechte je Konto bis in die Einstellungen hinein; „Oberfläche“ bleibt
  immer sichtbar
- Ansichtsschalter für Wiki und Dateien nur noch mit dem passenden Bereich
- Benutzerverwaltung neu gestaltet: eine Zeile je Konto, Editor klappt auf
- „Zur Übersicht“ nur mit dem Bereich „Übersicht (Datensätze)“
- „Mein Bereich“ zeigt die eigenen Zeiten mit Bearbeiten und Löschen
- „Abmelden“ als großer Knopf oben auf der Seite
- Aufgabenliste am Handy rollt seitlich statt zu überlappen
- Zwei Fehler behoben: zerfallende Erklärtexte, und ein Rechteformular
  ohne Haken erteilte vollen Zugriff

## 1.1.2

- Wiki: Zeilenumbrüche aus der Markdown-Datei erscheinen jetzt auch in
  der Anzeige
- Wiki: Hinweis zum Verschieben per Maus entfernt
- Dateien: Hinweistexte über Ablageort, erlaubte Dateiarten und Ziehen
  entfernt
- „Changelog“ vom Kopfzeilen-Symbol in die Fußzeile verschoben, hinter
  die Versionsnummer

## 1.1.1

- Mobiles Menü wieder bedienbar (lag hinter dem Abdunkler)
- Keine animierten Linien mehr beim Überfahren der Menüpunkte
- Anmeldeseite zurück auf die ruhige Fassung aus 1.0.1
- Excel- und CSV-Knopf über der Trefferliste statt im Filterkasten,
  beide in derselben Farbe
- Kleinere Abstandskorrekturen bei der manuellen Zeiterfassung und am
  Filterhinweis

## 1.1

- Auslieferung über GitHub: Home Assistant meldet Updates von selbst
- Der Programmcode liegt jetzt im Abbild, nicht mehr unter
  `share/deinweg-toolkit/app` — der Ordner kann gelöscht werden
- Daten bleiben unter `share/deinweg-toolkit` und werden bei Updates
  nicht angefasst

## 1.0.2

- Anmeldebildschirm: größeres Logo mit Aufbau-Animation
- Am Abbild hat sich nichts geändert: Ordner `app` ersetzen, neu starten

## 1.0.1

- Erklärende Texte durchgehend gleich groß
- Kopfzeile oben links nur noch das Zeichen, neue Menügrafik
- Anmeldebildschirm mit größerem Logo und Aufbau-Animation
- Am Abbild hat sich nichts geändert: Ordner `app` ersetzen, neu starten

## 1.0

- Neue Grafiken: Logo, Favicons, App-Symbole und das Add-on-Icon
- Kopfzeile mit dem Zeichen statt dem vollen Schriftzug, bleibt beim
  Rollen stehen
- Einstellungen in fünf Gruppen geordnet
- Erklärende Texte mit Informationszeichen
- Dateien: Ordner lassen sich umbenennen und ins Wiki verlinken
- Am Abbild hat sich nichts geändert: Ordner `app` ersetzen, neu starten

## 0.9.2

- MP4, SVG, EPS und DOTX kommen als erlaubte Dateiarten dazu
- Löschknopf in der Dateiliste war unerreichbar — behoben
- Volle Ordner lassen sich löschen, Ansichtsumschalter direkt auf der
  Seite, alles linksbündig
- Wiki: Bilder werden nicht mehr über die volle Breite gezogen
- Neuer Anmeldebildschirm
- Am Abbild hat sich nichts geändert: Ordner `app` ersetzen, neu starten

## 0.9.1

- Anleitung korrigiert: run.sh wird beim Bauen fest ins Abbild kopiert.
  Eine Änderung daran wirkt erst nach „Neu erstellen“, ein bloßer
  Neustart reicht nicht
- Neuer Fehlerbehebungs-Abschnitt für den Fall, dass hochgeladene
  Dateien nicht in share/deinweg-toolkit/files erscheinen
- Am Programm selbst hat sich nichts geändert

## 0.9

- Dateiverwaltung neu gebaut: Seitenleiste mit Dateibaum, Listenansicht
  als Standard, Ziehen mit der Maus
- Der Ablageort steht in der Oberfläche. Was du über die Samba-Freigabe
  in `share/deinweg-toolkit/files` legst, erscheint automatisch in der App
- Menü: „Dateien“ vor „Wiki“, „Verwaltungsvorgänge“ heißen „Aufgaben“
- Am Abbild hat sich nichts geändert: Ordner `app` ersetzen, neu starten

## 0.8.9

- Neuer Menüpunkt „Dateien“: Bilder, PDFs und Office-Dateien hochladen,
  in Ordnern sortieren und im Wiki verlinken
- Alles landet unter `share/deinweg-toolkit/files` und ist damit auch
  über die Dateifreigabe erreichbar
- Der Ordner `export` wird nicht mehr angelegt; die Route, die dorthin
  schrieb, gab es seit Langem nicht mehr
- Am Abbild selbst hat sich nichts geändert. Es reicht, den Ordner `app`
  unter `share/deinweg-toolkit/` zu ersetzen und neu zu starten

## 0.8.8

- Neues Recht „Einträge anderer bearbeiten“, getrennt vom Löschrecht
- Zeiterfassung: Mitarbeiter als Auswahlfeld, mehrere Einträge auf einmal,
  kein Sprung an den Seitenanfang nach dem Speichern
- Logbuch nach Tagen gegliedert und farbig nach Aktionsart
- Am Add-on selbst hat sich nichts geändert; es reicht, den Ordner `app`
  unter `share/deinweg-toolkit/` zu ersetzen und neu zu starten

## 0.8.7

- Zwei neue Rechte je Benutzerkonto: „Einträge anderer löschen“ und
  „Wiki bearbeiten“
- Benutzerverwaltung nur noch für Administratoren, dafür „Mein Konto“
  für alle
- Fuhrpark-Erfassung neu gestaltet
- Gelöschte Verwaltungsvorgänge bleiben im Logbuch nachvollziehbar
- Am Add-on selbst hat sich nichts geändert; ein Neubau des Abbilds ist
  nicht nötig. Es reicht, den Ordner `app` unter
  `share/deinweg-toolkit/` zu ersetzen und das Add-on neu zu starten

## 0.8.2

- Erste Fassung als lokales Home-Assistant-Add-on
  (damals noch unter der alten Zählung als 2.14 ausgeliefert)
- Läuft mit denselben Paketversionen wie auf der NAS
- Alle Daten unter `/share/deinweg-toolkit`, damit das Wiki weiterhin
  auch über die Dateifreigabe bearbeitet werden kann
- Einstellungen (Admin-Konto, Sitzungsdauer, Wecker-Intervall,
  Upload-Grenze, Zeitzone) über das Formular in Home Assistant
