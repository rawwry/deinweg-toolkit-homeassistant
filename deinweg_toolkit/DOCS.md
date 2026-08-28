# Dein Weg Toolkit

Betreuungszeiten, Aufgaben, Fuhrpark, Wiki und Dateiablage für eine
Einrichtung des ambulant betreuten Wohnens.

## Einrichten

1. **Installieren**, dann in den Reiter **Konfiguration** wechseln
2. `admin_passwort` leer lassen — beim ersten Start wird eines erzeugt
   und **einmalig ins Protokoll geschrieben**
3. **Starten** und den Reiter **Protokoll** ansehen. Dort steht:

   ```
   [addon] Programm:    /opt/deinweg (im Abbild)
   [addon] Datenordner: /share/deinweg-toolkit (bleibt bei Updates unberührt)
   [start] Erster Administrator angelegt:
   [start]   Benutzername: timo
   [start]   Passwort:     ...
   ```

   Das Passwort **jetzt notieren**, es erscheint nur dieses eine Mal.
   Danach unter Mein Bereich → Mein Konto ändern.
4. Über **Weboberfläche öffnen** oder `http://homeassistant.local:8778`

Die Schalter **Beim Systemstart starten** und **Watchdog** eingeschaltet
lassen: das erste bringt das Toolkit nach einem Stromausfall von selbst
zurück, das zweite startet es neu, falls es je abstürzen sollte.

## Einstellungen

| Feld | Bedeutung |
|---|---|
| `app_name` | Anzeigename in der Oberfläche |
| `admin_benutzername` | nur beim allerersten Start; danach zählt die Benutzerverwaltung |
| `admin_passwort` | leer = wird erzeugt und ins Protokoll geschrieben |
| `sitzung_tage` | wie lange eine Anmeldung gültig bleibt (30) |
| `wecker_intervall` | Sekunden zwischen zwei Prüfungen auf fällige E-Mail-Erinnerungen (3600), `0` schaltet ab |
| `max_upload_mb` | Obergrenze beim Hochladen von Zeitlisten und Dateien (20) |
| `zeitzone` | `Europe/Berlin`. **Nicht ändern** — davon hängen Monatsgrenzen, Fristen und der Wecker ab |

## Updates

Home Assistant meldet neue Versionen von selbst. **Update** anklicken,
fertig — der Rest passiert unbeaufsichtigt. Beim ersten Mal und nach
Paketänderungen baut der Pi das Abbild neu, das dauert ein paar Minuten.

**Deine Daten bleiben dabei unberührt.** Sie liegen unter
`/share/deinweg-toolkit/` und gehören nicht zum Abbild.

## Wo die Daten liegen

```
share/deinweg-toolkit/
├── db/      die Datenbank (zeiten.db)
├── texte/   quotes.txt, ideen.txt, strings.txt
├── wiki/    die Wiki-Seiten als Markdown
└── files/   die Dateiverwaltung
```

Der Ordner liegt in der Samba-Freigabe **share**. Wiki-Seiten und Dateien
lassen sich damit im Browser *und* im Finder bearbeiten — was du dort
ablegst, erscheint in der Anwendung.

## Datensicherung

Zwei Wege, beide sinnvoll:

- **Home-Assistant-Sicherung.** Achte darauf, dass beim Anlegen der
  Ordner **share** mit ausgewählt ist — sonst fehlt genau die Datenbank.
- **Aus der Anwendung heraus:** Einstellungen → System → Datenbank
  herunterladen. Ergibt eine einzelne Datei, die sich dort auch wieder
  einspielen lässt.

## Wenn etwas klemmt

**Das Add-on taucht nicht im Store auf.** Add-on-Store → drei Punkte →
**Nach Updates suchen**. Hilft das nicht, steht die Ursache im Klartext
unter Einstellungen → System → Protokolle → **Supervisor**.

**Hochgeladene Dateien erscheinen nicht.** Im Protokoll prüfen, ob dort
`Datenordner: /share/deinweg-toolkit` steht. Falls nicht, das Add-on
einmal neu starten.

**Prüfung von Hand ausführen** (nur im Zweifel nötig). Mit dem Add-on
*Advanced SSH & Web Terminal* bei ausgeschaltetem Schutzmodus:

```
docker exec addon_deinweg_toolkit sh -c "cd /opt/deinweg && python -m app.tests"
```

Alle Prüfungen müssen bestehen. Sie legen sich eine eigene Datenbank in
einem temporären Ordner an und fassen die echten Daten nicht an.
