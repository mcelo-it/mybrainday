# Explizite Zuordnung von Teilantworten zu Belegen

Die bisherige Prüferantwort enthält nur ausgewählte Quellen und wörtliche
Belegpassagen. Das genügt nicht zur Kontrolle, ob alle Teile einer Frage
berücksichtigt wurden. Die produktive Prüfung verlangt jetzt zusätzlich
`coverage`: eine Liste mit `subject`, `property` und `evidence` je Teilantwort.
Die Zahlen in `coverage.evidence` verweisen auf die 1-basierten Positionen in der
Belegliste, nicht auf Quellen-Nummern. Die eigentlichen Belege werden weiterhin
wortgetreu gegen die Originalquellen geprüft.

Jede Teilantwort benötigt mindestens eine gültige Belegreferenz. Die Liste ist
auf 20 Einträge begrenzt, Gegenstand und Eigenschaft auf jeweils 500 Zeichen.
Bei expliziten Vergleichsformulierungen (Unterschied, unterscheiden, vergleichen,
gegenüber, versus, vs) verlangt der Validator mindestens zwei unterschiedlich
benannte Gegenstände mit identischem Eigenschaftslabel. Diese allgemeine
sprachliche Erkennung verwendet keine Referenz-IDs oder konkreten Kursbegriffe.
Sie ist keine vollständige Erkennung aller möglichen Vergleichsformulierungen.
Die Prüfanweisung verlangt unabhängig davon die Abdeckung aller Teilfragen.

Zusätzliche Ablehnungsgründe: `invalid_coverage`, `uncovered_requirement`,
`invalid_coverage_reference`, `incomplete_comparison_coverage`. Die Diagnose
speichert nur den Status und gegebenenfalls die Anzahl der Zuordnungen, keine
neuen Modelltexte. Normale Antworten bleiben unveränderte Originalzitate.
Ein bewusster Verzicht hat alle drei Listen leer. Es gibt keine neuen API-Aufrufe;
das zusätzliche Schema kann die Zahl der ausgegebenen Tokens erhöhen.

Die Zuordnung ist ein struktureller Vertrag, kein Beweis semantischer Richtigkeit.
Das Modell kann einen Gegenstand übersehen oder eine Passage falsch zuordnen.
Der Code kann weder die Bedeutung der Eigenschaftslabels noch die fachliche
Folgerung aus den Belegen deterministisch nachweisen. Synonyme Eigenschaftslabels
werden konservativ abgelehnt, wenn das Modell die Anweisung zum identischen
Wortlaut nicht befolgt. Ungewöhnliche Frageformulierungen bleiben eine Grenze.

136 lokal ausführbare Tests bestanden mit simulierten Antworten. Neue Tests
verwenden einen Materialvergleich außerhalb der bisherigen PV-/Trafo-Fragen:
fehlende zweite Seite, unbelegte Teilantwort, unterschiedliche Eigenschaften,
ungültige Verweise, doppelte Gegenstände und erfundene Belege. Ein zusätzlicher
Test prüft, dass auch der produktive RAG-Aufruf die Zuordnung verlangt. Zwei
API-Testmodule waren mangels FastAPI nicht ausführbar. Keine Live-Wirksamkeit
behauptet: nach Merge und Deployment beide manuellen Workflows starten.
Die Referenzanforderungen bleiben unverändert.
