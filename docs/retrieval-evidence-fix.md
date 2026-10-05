# Gezielter Fix nach der Live-Diagnose

## Bestätigter Befund

Der Lauf 37317193689 auf Revision 816919e bestätigte dieselbe Render-Version
vor und nach allen drei Dialogfragen. Bei Leerlaufstrom fehlte die bekannte
Referenzstelle in den acht Suchtreffern und allen 34 Auswahlkandidaten. Beide
Auswahlstufen akzeptierten stattdessen dasselbe allgemeine Kennlinienzitat.
Bei der Kurzschluss-Folgefrage wurden nur fünf lokale Kandidaten geprüft;
der akzeptierte unzureichende Beleg verhinderte die globale Suche. Der
Themenwechsel zur LWL-Prüfung wurde als neue Frage behandelt und bestand den
Test. Damit sind sowohl eine Lücke bei den Suchkandidaten als auch ein Fehler
bei der Belegprüfung nachgewiesen. Die Ursache der semantischen Rangfolge
selbst ist damit nicht abschließend erklärt.

## Suche

Der Webdienst verwendet ohne explizite Umgebungsüberschreibung nun `hybrid`
mit 16 statt acht direkten Treffern. Die bestehende BM25-Suche ergänzt die
semantische Suche. Häufige Frage-/Funktionswörter werden nur aus der lexikalischen
Suchanfrage entfernt; Negationen, Zahlen und Fachbegriffe bleiben erhalten.
Bis zur Hälfte der Trefferplätze wird für die besten positiven BM25-Treffer
reserviert; der Rest wird mit der bestehenden RRF-Rangfolge gefüllt. Anschließend
werden die gewählten Treffer in RRF-Reihenfolge ausgegeben. Alle müssen weiterhin
die Kosinus-Schwelle bestehen. BM25-/RRF-Werte werden nicht als Kosinus ausgegeben.

Bei der Kontexterweiterung werden zuerst alle direkten Treffer aufgenommen,
danach vorherige/folgende Segmente. Das verhindert, dass Nachbarn früher Treffer
spätere direkte Treffer verdrängen. Die Grenzen von 40 Segmenten und 60.000
Textzeichen bleiben bestehen. Die größere Treffervielfalt bedeutet innerhalb
dieses Budgets weniger Platz für Nachbarn; fehlende wichtige Bedingungen bleiben
ein zu prüfendes Risiko. Überlange Treffer können am Zeichenbudget scheitern.

Ein bereits gesetztes `RAG_RETRIEVAL_MODE=semantic` hat weiterhin Vorrang. Für
die neue Suche in diesem Fall den Wert in Render auf `hybrid` setzen. `/health`
zeigt den tatsächlichen Modus. Mit `semantic` verwendet der Webdienst wieder
acht semantische Treffer; die strengere Belegprüfung bleibt aktiv. Die allgemeine
RAG-Klasse und der Evaluations-CLI behalten ihre bisherigen expliziten Defaults;
für den Dienstvergleich dort `--retrieval-mode hybrid --top-k 16` verwenden.
Es werden keine Dokument-Embeddings neu aufgebaut und keine zusätzlichen
Such-Embedding-Aufrufe pro Suchvorgang eingeführt.

## Belegprüfung

Die zweite Modellprüfung liefert jetzt JSON mit `selected` und `evidence`.
Jeder Evidenz-Eintrag enthält eine ausgewählte Quellennummer und eine exakte
Teilzeichenfolge dieser Originalquelle. Fehlende, erfundene, falsch zugeordnete
oder formal ungültige Belege werden abgewiesen. Für benötigte Bedingungen dürfen
zusätzliche Originalsegmente in `selected` stehen. Die endgültige Antwort
verwendet weiter die vollständigen Originalsegmente einschließlich Quellenangabe,
nicht die vom Modell gelieferten Teilpassagen.

Bei erkannten quantitativen Strom-/Spannungsfragen muss mindestens eine
Belegpassage einen entsprechenden Wert mit Einheit oder eine unterstützte
explizite Nullformulierung enthalten. Ein bloßes Nennen von Kurzschlussstrom
und Leerlaufspannung besteht diese Prüfung nicht mehr. Bei Folgefragen wird
hierfür die erhaltene Original-Folgefrage ausgewertet. Andere Größen und
qualitative Fragen erhalten keine fälschlich behauptete deterministische
Vollprüfung; sie verlassen sich auf die Modellprüfung und den Originaltextabgleich.

Die Zahlenprüfung ist konservativ und deckt nicht jede Schreibweise ab. Sie
beweist insbesondere nicht, dass Betriebszustand, Bezug und sämtliche Bedingungen
semantisch zusammenpassen. Alternative Zahlwörter, getrennte Einheiten oder
indirekte Belege können verworfen werden. Diese Grenzen sind kein Anlass,
unzureichende Treffer ungeprüft wieder freizugeben: Lokal abgewiesene Belege
führen zur globalen Suche, global fehlende Belege zur Meldung über unzureichende
Quellen. Ein zusätzlicher Suchweg kann bei zuvor falsch akzeptierten lokalen
Antworten mehr Modellaufrufe benötigen.

## Prüfung und nächste Abnahme

71 lokale Tests bestanden, einschließlich striktem Originaltextabgleich,
Zurückweisen des beobachteten allgemeinen Zitats bei beiden Zahlenfragen,
Dimensionsprüfung, globaler Suche nach lokal verworfenem Beleg, reservierter
lexikalischer Treffer außerhalb des semantischen Rangfensters und Erhaltung
später direkter Treffer im Kontextbudget. Modellantworten und Embeddings wurden
in den Unit-Tests simuliert; Provider-Importbindungen waren lokal ersetzt.
FastAPI-Integrationstests wurden mangels installierter Abhängigkeiten nicht
ausgeführt. Der vollständige Embedding-Cache und ein unabhängiges Bewertungsset
standen lokal nicht zur Verfügung; ein Verbesserungserfolg im Betrieb ist noch
nicht nachgewiesen.

Nach Merge und abgeschlossenem Render-Deployment einen **neuen** Lauf von
`Live-Dialog pruefen` auf `main` starten. Prüfen: tatsächlicher Modus, Anwesenheit
der beiden Referenzen im Auswahlkontext, bestätigte Auswahl und Originalzitate.
Eine ehrliche Ablehnung bleibt im Referenztest rot, ist aber von einem erneut
fälschlich freigegebenen Zitat zu unterscheiden. Testschwellen und Referenzen
wurden für diesen Fix nicht gelockert. Danach weitere nicht zur Entwicklung
verwendete Fragen und Bedingungen prüfen.
