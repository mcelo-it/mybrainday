# Lasttest für den mybrainday-Chatbot

Der Lasttest simuliert getrennte Teilnehmende gegen den produktiven `/chat`-Endpoint. Jede virtuelle Person erhält ihre eigene `conversation_id` und stellt überwiegend fachliche Fragen sowie vereinzelt Folgefragen.

## Installation

```bash
python -m pip install -r requirements-dev.txt
```

## Zielsystem festlegen

Ersetze `https://DEINE-RENDER-URL.onrender.com` in den folgenden Befehlen durch die produktive Render-URL.

Vor einem geplanten Test kann geprüft werden, ob der Dienst bereits läuft:

```bash
curl https://DEINE-RENDER-URL.onrender.com/health
```

## 1. Cold-Start-Test

Diesen Test nur durchführen, wenn die Render-Instanz vorher ausreichend lange nicht aufgerufen wurde.

```bash
time curl -sS -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" \
  https://DEINE-RENDER-URL.onrender.com/health
```

Danach den gleichen Befehl direkt erneut ausführen. Die Differenz zeigt den Cold-Start-Effekt.

## 2. Lasttest mit 14 Teilnehmenden

```bash
locust -f tests/load/locustfile.py \
  --host https://DEINE-RENDER-URL.onrender.com \
  --headless \
  -u 14 \
  -r 14 \
  -t 5m \
  --csv tests/load/results-14
```

`-u 14` erzeugt 14 gleichzeitige virtuelle Nutzer. `-r 14` startet sie innerhalb von ungefähr einer Sekunde. Die Laufzeit beträgt fünf Minuten.

## 3. Reserve-Test mit 20 Teilnehmenden

```bash
locust -f tests/load/locustfile.py \
  --host https://DEINE-RENDER-URL.onrender.com \
  --headless \
  -u 20 \
  -r 20 \
  -t 5m \
  --csv tests/load/results-20
```

## 4. Stresstest mit 28 Teilnehmenden

```bash
locust -f tests/load/locustfile.py \
  --host https://DEINE-RENDER-URL.onrender.com \
  --headless \
  -u 28 \
  -r 28 \
  -t 3m \
  --csv tests/load/results-28
```

## Interaktive Oberfläche

Alternativ kann Locust mit Browser-Oberfläche gestartet werden:

```bash
locust -f tests/load/locustfile.py \
  --host https://DEINE-RENDER-URL.onrender.com
```

Danach `http://localhost:8089` im Browser öffnen.

## Auswertung

Für den geplanten Einsatz mit 14 Teilnehmenden sollten insbesondere folgende Punkte geprüft werden:

- `Failures`: idealerweise 0.
- HTTP 429: Hinweis auf Rate-Limits eines externen Dienstes, insbesondere OpenAI.
- HTTP 5xx oder Timeouts: Hinweis auf Überlastung oder Backendfehler.
- Median und p95 der Antwortzeit: p95 sollte möglichst stabil bleiben, wenn von 14 auf 20 Nutzer erhöht wird.
- Render-Logs während des Tests: auf Neustarts, Speicherfehler und Exceptions achten.

Ein praxisnahes Freigabekriterium für die Untersuchung ist: 14 Nutzer über fünf Minuten ohne Fehler und ohne fortlaufend steigende Antwortzeiten. Wenn auch 20 Nutzer stabil laufen, besteht zusätzliche Reserve.

## Hinweise

Der Test sendet echte Anfragen an den Chatbot. Dadurch entstehen echte OpenAI-API-Aufrufe und gegebenenfalls Kosten. Den 28-Nutzer-Test deshalb nur kurz ausführen.

Die Testergebnisse (`results-*.csv`) sollten nicht zwingend committed werden. Sie können lokal archiviert und für die Dokumentation der Masterarbeit ausgewertet werden.
