# Dein Weg Toolkit — Home-Assistant-Add-on

Ein internes Werkzeug für eine Einrichtung des ambulant betreuten
Wohnens: Betreuungszeiten erfassen und auswerten, Aufgaben und Fristen
dokumentieren, Fuhrpark verwalten, Wissensbasis als Wiki, Dateiablage.

Läuft als Add-on auf Home Assistant OS.

## Einbau

1. In Home Assistant: **Einstellungen → Add-ons → Add-on-Store**
2. Oben rechts die drei Punkte → **Repositories**
3. Diese Adresse eintragen und hinzufügen:
   `https://github.com/rawwry/deinweg-toolkit-homeassistant`
4. Der Store zeigt jetzt **Dein Weg Toolkit** — installieren, einstellen,
   starten

Ab dann meldet Home Assistant neue Versionen von selbst.

## Wo die Daten liegen

Alles unter `/share/deinweg-toolkit/`:

| Ordner | Inhalt |
|---|---|
| `db/` | die Datenbank |
| `texte/` | quotes.txt, ideen.txt, strings.txt |
| `wiki/` | die Wiki-Seiten als Markdown |
| `files/` | die Dateiverwaltung |

Der Ordner liegt in der Samba-Freigabe **share** — Wiki-Seiten und
Dateien lassen sich also im Browser *und* im Finder bearbeiten.

**Updates fassen diesen Ordner nicht an.** Der Programmcode steckt im
Abbild, die Daten liegen daneben.

## Einstellungen

| Feld | Bedeutung |
|---|---|
| `admin_benutzername` | nur beim allerersten Start |
| `admin_passwort` | leer lassen → wird erzeugt und einmalig ins Protokoll geschrieben |
| `sitzung_tage` | wie lange eine Anmeldung gültig bleibt |
| `wecker_intervall` | Sekunden zwischen zwei Prüfungen auf fällige E-Mail-Erinnerungen, `0` schaltet ab |
| `max_upload_mb` | Obergrenze beim Hochladen |
| `zeitzone` | `Europe/Berlin` — davon hängen Monatsgrenzen und Fristen ab |

## Erreichbar unter

`http://homeassistant.local:8778` oder über **Weboberfläche öffnen** auf
der Add-on-Seite.
