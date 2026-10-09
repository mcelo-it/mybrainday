# Zehn Referenzfragen ohne Render-Shell prüfen

Nach Merge und Render-Deployment unter **Actions → Live-Referenzfragen pruefen →
Run workflow → main** starten. Der Workflow verwendet den öffentlichen Chatbot,
benötigt keine neuen Secrets und installiert keine zusätzlichen Python-Pakete.
Er läuft ausschließlich manuell. Zehn Chat-Anfragen verursachen die üblichen
Modellkosten; es gibt keine automatischen Wiederholungen durch das Testskript.

Jede Frage aus `evaluation/starter.json` beginnt eine eigene Sitzung. Der
bestehende Workflow `Live-Dialog pruefen` bleibt für Folgefragen und Themenwechsel
erforderlich. Beide prüfen vor und nach den Anfragen die Deployment-Revision.
Bei einer Versionsabweichung zu Beginn werden keine Chat-Anfragen gesendet.

Vor den Anfragen werden alle Referenztexte mit dem lokalen Korpus abgeglichen.
Ein vollständiges zulässiges `evidence_set` muss in der Antwort vorkommen; bei
der Verlustvergleichsfrage sind das zwei Stellen. Alternative vollständige
Belegsets werden unterstützt. Text, Metadaten, reine Zitatformatierung und die
Übereinstimmung mit `/sources` sowie dem Antwortfeld `sources` werden geprüft.

Das Ergebnisartefakt **live-reference-result** enthält `reference-check.json`:
Antworten, Zitate, Prüfergebnisse, Diagnose und Laufzeiten, jedoch keine
Sitzungskennungen. Es wird sieben Tage aufbewahrt. Das Actions-Protokoll zeigt
nur Prüfergebnisse und Referenzen pro Verarbeitungsstufe. Bei Fehlern enthält
der Bericht bereits abgeschlossene Fälle und einen bereinigten Fehlertyp.

Das Set umfasst sechs PV- und vier Transformatorfragen. Es wurde als
Entwicklungsset zusammengestellt, nicht unabhängig fachlich geprüft und nicht
als zurückgehaltener Benchmark verwendet. Bekannte Referenzen können alternative
korrekte Antworten verfehlen. Ein grüner Lauf beweist weder die Qualität aller
Antworten noch die Vollständigkeit des Kurswissens. Fehlende Referenzen müssen
anhand der gelieferten Zitate und der Stufendiagnose überprüft werden; der Test
soll nicht allein zum Erreichen eines grünen Ergebnisses gelockert werden.

Validierung vor dem ersten Live-Lauf: Alle zehn Fragen mit insgesamt elf
Referenzstellen passen zum vorhandenen vollständigen Korpus. 23 lokale Tests
mit simulierten HTTP-Antworten bestanden, darunter frische Sitzungen, vollständige
Mehrstellenbelege, alternative Belegsets, veränderte Zitate, Versionswechsel,
abweichende Quellen und Abbruch ohne erneute Anfrage bei Fehlern.
Ein Live-Ergebnis dieses neuen Workflows liegt noch nicht vor.
