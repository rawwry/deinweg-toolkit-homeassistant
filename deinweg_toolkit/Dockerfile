# Dasselbe Grundabbild wie früher auf der NAS, damit sich die Anwendung
# überall gleich verhält. python:3.12-slim gibt es für aarch64
# (Raspberry Pi 5) und amd64.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/deinweg

# tzdata muss mit hinein. Ohne die Zeitzonendateien rechnet der Container
# in UTC, und damit lägen Monatsgrenzen, Fristen und der E-Mail-Wecker im
# Sommer zwei Stunden daneben.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

# Feste Versionen, keine Abweichung - sonst ist es nicht mehr dieselbe
# Anwendung. httpx gehört nicht zum Betrieb, sondern ermöglicht
# "python -m app.tests" direkt auf dem Pi. Ein Werkzeug, das seine eigene
# Prüfung nicht mitbringt, prüft niemand.
RUN pip install --no-cache-dir \
      fastapi==0.115.6 \
      "uvicorn[standard]==0.34.0" \
      jinja2==3.1.5 \
      python-multipart==0.0.20 \
      openpyxl==3.1.5 \
      httpx==0.28.1

# ⚠️ Seit 1.1 liegt der Programmcode IM Abbild, nicht mehr unter
# /share/deinweg-toolkit/app. Nur so kann Home Assistant ein Update
# vollständig ausliefern; vorher wäre bei einem Update nur die Hülle
# erneuert worden und die Anwendung alt geblieben. Die Daten liegen
# weiterhin unter /share - sie gehören dem Betreiber, nicht dem Abbild.
COPY app /opt/deinweg/app
COPY pruefen.sh /opt/deinweg/pruefen.sh
COPY run.sh /run.sh
RUN chmod +x /run.sh /opt/deinweg/pruefen.sh

CMD [ "/run.sh" ]
