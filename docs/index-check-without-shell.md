# Suchindex ohne Render-Shell prüfen

Der Workflow „Suchindex pruefen“ benötigt keinen Render-Zugang und keinen
OpenAI-Schlüssel. Er lädt den gewählten Repository-Stand auf einen normalen
GitHub-Runner und prüft dessen backend/cache gegen backend/docs. Er startet
keinen Server, erzeugt keine Embeddings und verändert keine Projektdateien.
Abhängigkeiten werden nur im temporären Runner installiert.

## Im Browser

1. Den PR mit diesem Workflow in main übernehmen. GitHub zeigt den manuellen
   Startknopf erst an, wenn der Workflow im Standardbranch vorhanden ist.
2. Im Repository den Reiter **Actions** öffnen.
3. Links **Suchindex pruefen** wählen.
4. **Run workflow** anklicken, **main** wählen und den Start bestätigen.
5. Den neuen Lauf öffnen, dann den Job **check-index** und den Schritt
   **Cache nur lesen und pruefen**.

Die Ausgabe enthält `result`, `index_validation`, `index_id` und bei Erfolg
die Anzahl von Dokumenten und Chunks. `verified` bestätigt die Manifestprüfung.
`legacy-structural-only` ist bei alten Caches ohne Manifest erwartbar und ergibt
ebenfalls einen grünen Lauf. Eine entsprechende Warnung ist kein Prüffehler.
Ein roter Lauf im Prüfschritt enthält die Fehlermeldung. Scheitert bereits das
Laden oder Installieren, wurde der Cache noch gar nicht geprüft.

GitHub dokumentiert den manuellen Start unter
https://docs.github.com/de/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
und die kostenlosen Standard-Runner für öffentliche Repositories unter
https://docs.github.com/en/billing/concepts/product-billing/github-actions.
Bei privaten Repositories gelten die jeweiligen Actions-Kontingente.

## Was das Ergebnis aussagt

Dies prüft den im GitHub-Repository gespeicherten Cache. Wenn Render denselben
Commit, diese Dateien und die Standardpfade verwendet, ist das ein relevanter
Konsistenznachweis für dieses Deployment. Ein auf Render separat neu aufgebauter
Cache oder abweichende RAG_DOCS_PATH-/RAG_CACHE_DIR-Pfade sind damit nicht geprüft.
Der Workflow verbindet sich nicht mit Render und löst dort keinen Neuaufbau aus.
Ein Merge kann unabhängig davon einen bereits eingerichteten Render-Autodeploy
auslösen; das ist keine Aktion dieses Workflows.

Für eine lokale Prüfung mit installierten Abhängigkeiten lautet der neue Befehl:

```sh
python -m backend.check_index
```

Im Gegensatz zum früheren Beispiel `RAGSystem()` wird dabei auch kein OpenAI-
Client initialisiert. Ein API-Schlüssel ist deshalb ausdrücklich nicht erforderlich.
