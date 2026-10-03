# Chatbot verbessern – Schritt für Schritt

## Schritt 1: Konversationen isolieren

**Problem:** Eine globale `RAGSystem`-Instanz enthielt sowohl den Suchindex als
auch den Gesprächsverlauf aller Besucher. Eine Folgefrage oder eine Antwort
auf eine Rückfrage konnte dadurch zum Gespräch einer anderen Person gehören.
Auch `/sources` lieferte den global zuletzt abgefragten Kontext.

**Änderung:** `ConversationState` enthält jetzt sämtliche veränderlichen
Dialogdaten: Verlauf, letzte Fragen, Themenzusammenfassung, ausgewählte und
abgerufene Quellen sowie offene Rückfragen. Für jeden Turn erzeugt
`RAGSystem.for_conversation(state)` eine leichte Instanz, die Dokumente,
Chunks, Embeddings und API-Client mit dem geladenen Index teilt. Nur der
Gesprächszustand ist sitzungsspezifisch. Es entstehen keine zusätzlichen
Embedding-Aufrufe und keine Kopien der großen Embedding-Matrix pro Nutzer.

### Ablauf und API

1. Der erste `POST /chat` enthält wie bisher `{"message": "Was ist NA-Schutz?"}`.
2. Die Antwort enthält zusätzlich `conversation_id`, eine serverseitig erzeugte,
   zufällige Kennung mit 256 Bit Zufall.
3. Weitere Nachrichten senden diese Kennung im Header `X-Conversation-ID`.
4. `GET /sources` verwendet denselben Header. Ohne Kennung liefert die Route
   eine leere Liste; unbekannte oder abgelaufene Kennungen ergeben HTTP 404.
5. Ohne Kennung beginnt jede Chat-Anfrage eine neue Sitzung. Alte API-Clients
   können weiter Fragen stellen, müssen für Folgefragen aber die Kennung senden.

Das Frontend hält die Kennung ausschließlich im Speicher der geöffneten Seite.
Ein neuer Tab oder Neuladen beginnt einen neuen Chat. Ein Ablauf wird sichtbar
gemeldet; die nächste Nachricht beginnt ohne bisherigen Kontext. Eine
fehlgeschlagene Nachricht wird nicht automatisch erneut gesendet.

Die Kennung gewährt Zugriff auf diese anonyme Konversation und sollte nicht
geteilt oder protokolliert werden. Sie ersetzt keine Benutzeranmeldung. Für
spätere Benutzerkonten ist zusätzlich eine Bindung an den angemeldeten Nutzer
erforderlich.

### Gleichzeitigkeit, Fehler und Speicher

- Nachrichten derselben Sitzung werden nacheinander verarbeitet. Verschiedene
  Sitzungen dürfen gleichzeitig antworten; es gibt keine globale LLM-Sperre.
- Eine Anfrage arbeitet auf einer Kopie des kleinen Gesprächszustands. Erst
  nach erfolgreicher Verarbeitung wird dieser übernommen. Ein Modellfehler
  lässt das letzte erfolgreiche Gespräch unverändert.
- Aktive und wartende Anfragen werden bei der Sitzungsbereinigung geschützt.
- Standard: eine Stunde Inaktivität (`SESSION_TTL_SECONDS=3600`), maximal 500
  Sitzungen (`MAX_SESSIONS=500`), letzte 40 Verlaufsnachrichten. Die
  Themenzusammenfassung und zuletzt ausgewählte Quellen bleiben zusätzlich
  erhalten. Eingaben sind auf 8.000 Zeichen begrenzt.
- Abgelaufene Sitzungen werden bei der nächsten Sitzungsoperation entfernt.
  Sind alle Plätze belegt, erhalten neue Chats HTTP 503; bestehende werden
  nicht verdrängt.
- Beim administrativen Index-Neuaufbau wird eine separate Indexinstanz erstellt
  und erst nach Erfolg ausgetauscht. Laufende Anfragen behalten ihren bisherigen
  konsistenten Index. Bestehende Gesprächskontexte dürfen für Folgefragen noch
  zuvor ausgewählte Quellenausschnitte verwenden.

### Deployment-Grenze

Die Sitzungen liegen **im Speicher eines einzelnen Serverprozesses**. Ein
Neustart oder Deployment beendet sie. Mehrere Worker oder mehrere Instanzen
benötigen zuerst einen gemeinsamen Sitzungsspeicher (zum Beispiel Redis) mit
einer pro Sitzung wirksamen Sperre bzw. Versionskontrolle. Nur ein gemeinsamer
Speicher ohne Schutz vor parallelen Schreibvorgängen reicht nicht.

`render.yaml` startet deshalb ausdrücklich einen Worker vom Repository-Root:

```bash
uvicorn backend.app:app --workers 1 --host 0.0.0.0 --port "$PORT"
```

Das korrigiert zugleich den bisherigen Startpfad: `app.py` verwendet einen
relativen Paketimport und muss als `backend.app` importiert werden.

### Überprüfung

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node --check frontend/app.js
```

Die Tests verwenden die echten API-Routen, die RAG-Dialogsteuerung und den
Sitzungsspeicher. Modellabhängige Schritte sind deterministisch ersetzt;
es entstehen keine API-Kosten. Geprüft werden unabhängige Folgefragen und
Quellen zweier Nutzer, offene Rückfragen, fehlende/ungültige/abgelaufene
Kennungen, Fehler-Rollback, Sitzungsgrenzen und parallele Verarbeitung.
Die Tests bewerten noch nicht die fachliche Qualität echter Modellantworten.

Manueller Abnahmetest nach Deployment: In zwei getrennten Tabs nach NA-Schutz
und Stromwandlern fragen, danach jeweils „Warum?“ eingeben und die Quellen
öffnen. Beide Gespräche müssen beim eigenen Thema bleiben. Nach Neuladen
beginnt die jeweilige Seite ohne gespeicherten Dialogkontext.

## Weitere Etappen

Diese Liste ist der Arbeitsplan; nur Schritt 1 gehört zu diesem Änderungspaket.
Jede weitere Etappe erhält eigene Änderungen, Prüfung und Erläuterung.

| Etappe | Ziel und Nachweis |
| --- | --- |
| 2 | `answer` und tatsächlich verwendete `citations` trennen; keine alten Quellen bei Smalltalk oder Ablehnung; Quellenanzeige im Frontend anpassen. |
| 3 | Belegte Antworten aus Quellen formulieren; Quellen-IDs prüfen und unbelegte Antworten abfangen. |
| 4 | Ein fachlich geprüftes Golden Testset und Evaluation aufbauen; erste Fragen früh sammeln, Referenzantworten nicht ungeprüft automatisch erzeugen. |
| 5 | Hybrid Retrieval und vektorisierte semantische Suche; Ranking-Fusion evaluieren, rohe BM25- und Cosine-Scores nicht ungeprüft gewichten. |
| 6 | Metadaten in Embeddings, Segmentfenster sowie Fingerprint/Indexversion gemeinsam einführen; kontrollierter Neuaufbau erforderlich. |
| 7 | Kandidaten reranken und Answerability anhand des Testsets kalibrieren. |
| 8 | Eigenständige Suchfragen aus Folgefragen und begrenztem Gesprächskontext erzeugen. |
| 9 | Router-Aufrufe bündeln und Klassifikationen auf validierte strukturierte Ausgaben umstellen. |
| 10 | Latenz, Retrieval-Qualität und Modellverbrauch messen; Verbesserungen gegen die Ausgangswerte vergleichen. |

Die Quellenliste enthält in Schritt 1 weiterhin Retrieval-Kandidaten. Ihre
semantische Korrektur gehört ausdrücklich zu Schritt 2. Auch eine bessere
fachliche Antwortqualität wird durch die Sitzungsisolation allein noch nicht
nachgewiesen.
