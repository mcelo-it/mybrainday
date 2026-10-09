# Rücknahme der verpflichtenden Coverage-Zuordnung

Die Live-Berichte für Revision 22241de31ebc51cde309f0db2ac7d043bc70e4c5 zeigen
eine Regression nach PR #25: 2/10 Referenzfragen und 0/3 Dialogschritte bestanden.
Die Ablehnungen betreffen überwiegend invalid_coverage_reference sowie
invalid_evidence_schema. Die Logs enthalten nicht die rohen Modellantworten;
daher ist eine bestimmte Verwechslung der Nummerierung nicht abschließend belegt.

Die fünf in PR #25 geänderten bestehenden Dateien werden exakt aus Revision
7eb5ce48fd9e00cfa975adbc92925a9c4aba4d07 wiederhergestellt. Die drei ausschließlich
für diese Änderung hinzugefügten Dateien werden entfernt. Damit entfällt der
neue Pflichtvertrag; die zuvor bestehende wörtliche Belegprüfung, Mengenprüfung
und begrenzte Korrektur bleiben erhalten. Keine Live-Testanforderung wird geändert.

Der vorherige Stand bestand 9/10 Referenzfragen und 3/3 Dialogschritte. Der
unvollständige Verlustvergleich ist damit ausdrücklich noch nicht behoben.
127 lokal ausführbare Tests bestanden nach der Rücknahme mit simulierten
Antworten; zwei API-Testmodule benötigen das hier fehlende FastAPI. Der
Produktionsstand muss nach Merge und Deployment erneut live geprüft werden.

Weitere Änderungen am Prüfschema sollen zunächst außerhalb des produktiven
Antwortpfads mit echten Modellantworten auf dem vorhandenen Entwicklungsset
geprüft werden. Ein gemockter Schematest beweist keine Einhaltung durch das
Live-Modell. Erst danach sollte ein neues Schema verbindlich werden.
