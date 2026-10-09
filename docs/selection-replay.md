# Belegauswahl getrennt vom Produktivdienst vergleichen

Dieses Experiment verändert keine Render-Konfiguration, keine produktiven
Prompts und keine Sitzungen. Es ruft die OpenAI-API direkt aus einem manuellen
GitHub-Workflow auf. Dafür ist im Repository unter Settings → Secrets and
variables → Actions ein Repository-Secret `OPENAI_API_KEY` erforderlich.
Ohne Schlüssel endet der Workflow vor Modellaufrufen. Den Schlüssel im
Secret-Feld hinterlegen, nicht in Repository-Dateien.

Nach Merge: Actions → **Belegauswahl isoliert vergleichen** → Run workflow.
Unter `source_run_id` die numerische Lauf-ID eines vollständigen Workflows
**Live-Referenzfragen pruefen** angeben, dessen `live-reference-result`-Artefakt
noch verfügbar ist. Die ID steht in dessen URL hinter `/actions/runs/`.
Das Quellartefakt wird heruntergeladen; der Korpus wird aus exakt dessen
GitHub-Revision geladen. Ein Render-Deployment ist für dieses Experiment unnötig.

Die Fragen müssen unverändert zum bestehenden Entwicklungsset passen. Die
Kandidatenliste wird aus dem selection-Trace vollständig mit gleicher Reihenfolge
und gleichen Scores rekonstruiert. Gekürzte oder mehrdeutige Kandidatenlisten,
fehlende Quellen, geänderte Referenztexte und Versionsabweichungen führen zum
Abbruch vor Modellaufrufen. Jede Variante bekommt einen neuen ConversationState.

Varianten:

- `selection_then_review`: bisherige Auswahl mit anschließender Belegprüfung.
- `direct_review`: dieselbe Belegprüfung direkt auf allen Kandidaten, ohne
  Vorauswahlvorschlag. Die vorhandene begrenzte Belegkorrektur bleibt aktiv.

Die Reihenfolge der beiden Varianten wechselt je Frage. Modell: gpt-4.1-mini,
Temperatur gemäß bestehendem RAG-Code. Ein Versuch pro Variante und Frage.
Bei zehn Fragen sind maximal 50 logische Modellaufrufe möglich; keine Embeddings,
keine automatische SDK-Wiederholung. Normale API-Kosten entstehen. Fehler stoppen
das Experiment, bereits abgeschlossene Ergebnisse werden gespeichert.

Artefakt **selection-replay-result**: Antworten, Zitate, Referenzbewertung,
Kandidatenhash, Diagnose einschließlich angeforderter begrenzter Fehlerpassagen,
Tokenmetriken und Laufzeiten; sieben Tage Aufbewahrung. Die kompakte Actions-
Ausgabe enthält nur Bewertungen und Aufrufzahlen. Rohe Providerfehler und
API-Schlüssel werden nicht im Bericht gespeichert.

Ein grüner Workflow bedeutet **Experiment vollständig**, nicht **Antworten
fachlich bestanden**. `complete_evidence` misst die vorhandenen Referenzsets;
auch eine unvollständige oder ausgeschweifte Antwort kann zusätzliche fachliche
Prüfung brauchen. Ein einzelner Lauf belegt keine statistische Überlegenheit.
Das bestehende Entwicklungsset enthält nur wenige qualitative/vergleichende
Fragen und ist kein unabhängiger Benchmark. Vor einer Produktionsänderung sind
weitere fachlich geprüfte Vergleiche aus anderen Themen und Wiederholungen nötig.

Validierung bei Erstellung: Der hochgeladene Bericht ließ sich mit zehn Fragen
und insgesamt 400 Kandidatenvorkommen rekonstruieren, ohne Modellaufrufe.
22 lokale Tests für Replay, Belegprüfung und Antwortbewertung bestanden mit
simulierten Antworten. Noch kein Live-Modellvergleich ausgeführt.
