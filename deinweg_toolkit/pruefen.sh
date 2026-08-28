#!/bin/sh
# Automatische Prüfung des Toolkits.
#
# Aufruf auf der NAS (im Ordner, in dem "app" liegt):
#     sh pruefen.sh
#
# Nutzt das venv des Containers, falls vorhanden, sonst das System-Python.
# Es wird nichts an den echten Daten verändert: die Prüfung legt sich eine
# eigene Datenbank in einem temporären Ordner an.

if [ -x ./venv/bin/python ]; then
  PY=./venv/bin/python
else
  PY=python3
fi

"$PY" -c "import httpx" 2>/dev/null || {
  echo "Für die Prüfung fehlt das Paket httpx. Einmalig nachinstallieren:"
  echo "  $PY -m pip install httpx"
  exit 2
}

exec "$PY" -m app.tests
