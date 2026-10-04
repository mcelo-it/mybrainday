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
