# Beantwortbare Quellen statt bloßer Themenähnlichkeit

Das Problem ist Kontextinsuffizienz (insufficient context): Ein relevanter
Suchtreffer enthält nicht zwingend die zur Antwort nötige Information.
Wissenschaftlicher Bezug: https://arxiv.org/abs/2411.06037

`starter.json` enthält zehn aus drei vorhandenen Transkripten abgeleitete
Entwicklungsfragen, mit elf wörtlich geprüften Referenzstellen. Das ist ein
kleines, vom Assistenten zusammengestelltes Entwicklungsset, kein fachlich
abgenommener, unabhängiger Benchmark. Die Transkripte können selbst Fehler
enthalten; geprüft wird die Auffindbarkeit, nicht die elektrotechnische Richtigkeit.

Ein `evidence_set` enthält alle für eine vollständige Antwort benötigten
Abschnitte. Mehrere Sets erlauben alternative vollständige Belege. Besonders
bei Werten müssen Einheit und Bedingungen mit erfasst werden. Zusätzliche
korrekte Fundstellen können fehlen: Unvollständige Annotationen können die
gemessene Abdeckung unterschätzen. Das Set enthält bisher nur beantwortbare
Fragen; Abstention und Falschpositivraten werden damit nicht gemessen.

## Ausführen

Im Repository-Stamm mit installierten Backend-Abhängigkeiten und vorhandenem
vollständigem Cache ausführen. Der Live-Lauf erzeugt zehn kostenpflichtige
Query-Embeddings über den konfigurierten OpenAI-Schlüssel, keine Chatantworten
und keine neuen Dokument-Embeddings. Er nutzt das Embedding-Modell aus meta.json.

```sh
python -m evaluation.evaluate --live --cache-dir backend/cache --output evaluation/results/live.json
```

Der Bericht speichert die Rankings sowie Hashes von Korpus und Fragenset.
Damit lässt sich die Kontextauswertung anschließend ohne API-Aufrufe wiederholen:

```sh
python -m evaluation.evaluate --rankings evaluation/results/live.json --cache-dir backend/cache --output evaluation/results/replay.json
```

`--top-k` (Standard 8) und `--min-score` (Standard 0.30) sollten der produktiven
Konfiguration entsprechen. Bei abweichenden Quellen oder Fragen bricht Replay
ab. Ergebnisse gehören zur jeweiligen Korpusversion; keine absoluten Cachepfade
oder API-Schlüssel werden in Berichten gespeichert.

## Was die Kennzahlen bedeuten

- `seeds.evidence_recall`: Anteil der benötigten Referenzstellen in den Top-k.
- `context.evidence_recall`: Anteil nach Relevanzschwelle und Nachbarerweiterung.
- `complete_evidence`: Ob alle Stellen mindestens eines vollständigen
  Referenzsets vorhanden sind. Im Summary ist dies der Anteil solcher Fragen.
- `context_chunks` und `context_chars`: Umfang des bereitgestellten Kontexts.

Eine Ankündigung ohne hinterlegte Antwortstelle zählt nicht als Treffer.
Die Kontextauswertung nutzt dieselbe expand_context-Funktion und dieselben
Standardbudgets wie die Anwendung. Das beweist noch nicht, dass das Sprachmodell
die richtige Stelle auswählt. Dafür folgt eine getrennte End-to-End-Abnahme:
ausgegebene Zitate, eigene Zeitstellen, Fachbereich/Modul/Video, Einheiten und
Bedingungen überprüfen; neue reale Fehlerfälle ergänzen und ein unabhängiges
Testset zurückhalten. Erst danach Varianten wie hybride Suche oder größere
Kontextfenster anhand identischer Fragen vergleichen.

## Lokale Prüfung ohne API

```sh
python -m unittest discover -s tests -p 'test_retrieval.py'
python -m unittest discover -s tests -p 'test_evaluation.py'
```

Die Tests prüfen numerische Übereinstimmung mit skalarer Kosinusähnlichkeit,
Nullvektoren, Ranggleichstände und ungültige Eingaben sowie das Ankündigungs-
Beispiel, unvollständige Belege, die Relevanzschwelle und veraltete Referenzen.
Synthetische Testresultate dürfen nicht als Live-Treffergenauigkeit berichtet werden.

## Finale Antworten und Fehlerlokalisierung

Für den vollständigen Chatablauf zusätzlich `--answers` setzen:

```sh
python -m evaluation.evaluate --live --answers --cache-dir backend/cache --output evaluation/results/answers.json
```

Dieser Lauf nutzt `RAGSystem.ask` einschließlich Klassifikation und Zitatauswahl.
Jede Frage startet in einem neuen ConversationState. Es entstehen zusätzlich
kostenpflichtige Chat-Modellaufrufe; die Anzahl hängt vom Antwortpfad ab. Es
werden keine Dokument-Embeddings neu erstellt. Sitzungskennungen und API-Schlüssel
werden nicht im Bericht gespeichert. Das Chat-Modell wird im Bericht festgehalten.

Die Ausgabe enthält Suchtreffer, Referenzabdeckung im erweiterten Kontext,
finale Antwort, Zitate und Antworttyp. Die Zitate werden gegen Originaltext,
Zeitstelle und Fachbereich/Modul/Video geprüft. Eine echte Quellen-ID mit
erfundenem Text zählt nicht als belegte Antwort. Auch zusätzliche generierte
Prosa im ansonsten zitierenden Antwortformat wird erkannt.

`reference_diagnosis` unterscheidet: vollständiges Referenzset ausgegeben,
Referenzset fehlt bereits im rekonstruierten Kontext, oder Referenzset ist dort
vorhanden und wird nicht vollständig ausgegeben. Dies ist keine automatische
fachliche Bewertung: Alternative korrekte Belege bleiben möglich. Bei Rückfragen
oder vorgeschalteten Klassifikationen kann die fehlende Ausgabe mehrere Ursachen
haben. Der Bericht beweist nicht, welcher einzelne Modellaufruf fehlerhaft war.
Der Kontext wird aus den Suchankern rekonstruiert; interne Modellprompts werden
nicht aufgezeichnet. Die Evaluation umfasst neue Einzelanfragen, keine Dialogfolgen.

Gespeicherte Antworten werden beim normalen Replay automatisch mitgeprüft.
Für diesen Replay müssen top-k und Relevanzschwelle dem Original entsprechen.

## Live-Prüfung vom 4. Oktober 2026

Die zehn Fragen wurden über die Render-Oberfläche mit jeweils neu geladener
Seite gestellt. Sichtbare Chatantworten und Quellenfenster liegen in
`results/live-ui-2026-10-04.json`. Der klare Fehler zur Stromfrage wurde einmal
in einer weiteren neuen Sitzung reproduziert; siehe Wiederholungsdatei und
Screenshot. Der bereitgestellte Dienst weist keinen Commit aus, deshalb ist
die exakte Deploy-Version unbekannt. GitHub-main stand bei
`5d36f08a8328cb83424ce9d481018d6a5ccaef4e`; das beweist keine Deploy-Version.

Der Bericht [Live-Abnahme](live-review-2026-10-04.md) erläutert die Ergebnisse.
Die sichtbaren Ausgaben lassen sich ohne API erneut gegen die Transkripte prüfen:

```sh
python -m evaluation.check_ui_run evaluation/results/live-ui-2026-10-04.json --output evaluation/results/live-ui-2026-10-04-checked.json
python -m unittest discover -s tests -p 'test_answer_evaluation.py'
```

Für die UI-Prüfung müssen die referenzierten Transkripte im docs-Verzeichnis
liegen. Der Parser ist bewusst auf das aktuelle deutsche Ausgabeformat
beschränkt. Der Quellenfenstercheck prüft das Vorhandensein aller Chat-Zitate
mit Metadaten; er schließt zusätzliche Karten oder Darstellungsfehler nicht aus.
