# Automatischer Neuaufbau des Suchindex bei geänderten Transkripten

## Ziel

Änderungen an den Quelldateien unter `backend/docs/*.txt` sollen bei einem Render-Deployment automatisch berücksichtigt werden, ohne bei jedem Deployment unnötig neue Embeddings zu erzeugen.

## Umsetzung

Der Render-Build führt nach der Installation der Python-Abhängigkeiten nun aus:

```bash
python -m backend.prepare_index
```

`backend.prepare_index` lädt die aktuellen `.txt`-Quellen und versucht anschließend, den vorhandenen Cache über die bereits bestehende Indexvalidierung zu laden.

- Ist der Cache vollständig und passt zu den aktuellen Quelldateien, wird er unverändert weiterverwendet.
- Fehlt der Cache oder erkennt die bestehende Manifest-/Hash-Prüfung einen veralteten Cache, werden Chunks und Embeddings neu erzeugt und der Cache wird kontrolliert gespeichert.
- Andere Fehler werden nicht abgefangen. Der Render-Build schlägt in diesem Fall fehl, sodass keine fehlerhafte neue Version gestartet wird.

Damit wird insbesondere eine Änderung an `backend/docs/*.txt` durch die vorhandene Quell-Hash- und Chunk-Prüfung erkannt. Ein manueller Neuaufbau des Cache vor dem Push ist für Render-Deployments nicht mehr erforderlich.

## Ablauf nach einer Änderung

```text
backend/docs/*.txt ändern
        ↓
Git commit / push
        ↓
Render Build
        ↓
prepare_index
        ↓
Index gültig? ── ja ──> vorhandenen Cache verwenden
        │
       nein
        ↓
Chunks erzeugen
        ↓
Embeddings erzeugen
        ↓
Cache + Manifest speichern
        ↓
Anwendung starten
```

## Fehlerverhalten

Die Neuerzeugung erfolgt während des Build-Schritts und damit vor dem Start der neuen Anwendungsversion. Schlägt beispielsweise die Embedding-Erzeugung fehl, beendet sich der Build mit einem Fehler. Die fehlerhafte Version wird dadurch nicht als neue laufende Version gestartet.

## Kostenverhalten

Neue Embeddings werden nur erzeugt, wenn der Index fehlt oder nicht mehr zu den Quelldokumenten passt. Normale Deployments ohne Änderung der indexrelevanten Quellen verwenden den vorhandenen Cache weiter.

## Unveränderte Komponenten

Die bestehende Laufzeitinitialisierung in `backend/app.py`, die Cache-Validierung in `backend/index_manifest.py`, die Indexerzeugung in `backend/rag_utils.py` und der geschützte `/rebuild`-Endpunkt wurden nicht verändert.

## Tests

`tests/test_prepare_index.py` prüft drei Fälle:

1. gültiger Cache wird ohne Neuaufbau wiederverwendet,
2. veralteter Cache wird neu aufgebaut,
3. fehlender Cache wird neu aufgebaut.
