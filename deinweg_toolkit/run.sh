#!/bin/bash
# Startskript des Add-ons.
#
# Aufgabe: die im HA-Formular eingestellten Werte in die
# Umgebungsvariablen uebersetzen, die die Anwendung ohnehin schon liest
# (siehe main.py und db.py), die Datenordner anlegen und uvicorn starten.
# Am Python-Code aendert sich dadurch nichts.
set -euo pipefail

# Der Programmcode liegt im Abbild, die Daten daneben im /share des
# Systems. Diese Trennung ist der ganze Punkt: ein Update tauscht das
# Abbild aus und laesst die Daten unberuehrt.
PROGRAMM=/opt/deinweg
BASIS=/share/deinweg-toolkit

# --- Einstellungen aus dem HA-Formular uebernehmen -------------------------
# /data/options.json schreibt der Supervisor bei jedem Speichern neu.
# shlex.quote sorgt dafuer, dass auch ein Passwort mit Sonderzeichen
# unbeschadet ankommt.
eval "$(python3 - <<'PY'
import json, shlex

with open("/data/options.json", encoding="utf-8") as f:
    o = json.load(f)

def setze(name, schluessel, standard):
    wert = o.get(schluessel, standard)
    if wert is None:
        wert = standard
    print(f"export {name}={shlex.quote(str(wert))}")

setze("TZ",                 "zeitzone",            "Europe/Berlin")
setze("APP_NAME",           "app_name",            "Dein Weg Toolkit")
setze("ADMIN_BENUTZERNAME", "admin_benutzername",  "timo")
setze("ADMIN_PASSWORT",     "admin_passwort",      "")
setze("SITZUNG_TAGE",       "sitzung_tage",        30)
setze("WECKER_INTERVALL",   "wecker_intervall",    3600)
setze("MAX_UPLOAD_MB",      "max_upload_mb",       20)
PY
)"

# --- Feste Pfade ------------------------------------------------------------
export DB_PFAD="${BASIS}/db/zeiten.db"
export WIKI_PFAD="${BASIS}/wiki"
export FILES_PFAD="${BASIS}/files"
export SPRUCH_DATEI="${BASIS}/texte/quotes.txt"
export IDEEN_DATEI="${BASIS}/texte/ideen.txt"
export STRINGS_DATEI="${BASIS}/texte/strings.txt"
export SICHERUNG_PFAD="${BASIS}/sicherungen"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PROGRAMM}"

mkdir -p "${BASIS}/db" "${BASIS}/texte" "${BASIS}/wiki" "${BASIS}/files" \
         "${BASIS}/sicherungen"

echo "[addon] Programm:    ${PROGRAMM} (im Abbild)"
echo "[addon] Datenordner: ${BASIS} (bleibt bei Updates unberührt)"
echo "[addon] Zeitzone:    ${TZ} (aktuell $(date '+%d.%m.%Y %H:%M'))"

# uvicorn wird ueber exec gestartet: so ist es Prozess 1 und bekommt das
# Stopp-Signal des Supervisors direkt, statt dass die Bash es abfaengt.
cd "${PROGRAMM}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
