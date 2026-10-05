# Leerlauf-Suche und konkrete Aufzählungsfragen

## Messbare Suchlücke

Der vollständige Repository-Korpus mit 11.800 Segmenten wurde lokal gelesen.
Bei der Leerlaufstrom-Frage lag der bekannte Beleg in der bisherigen BM25-Liste
auf Rang 13; nur acht lexikalische Plätze waren reserviert. Die Formulierung
„fließt“ bevorzugte zahlreiche andere Stellen, während der Beleg „kein Strom“
und „null Ampere“ enthält. Deshalb reicht die reine Erweiterung auf 16 gemischte
Treffer nicht aus.

BM25 gewichtet nun fünf normalisierte Formulierungswörter geringer:
`fliesst`, `fliessen`, `betraegt`, `betragen`, `eingesetzt` mit Faktor 0,25.
Sie bleiben Suchsignale und werden nicht gelöscht. Fachbegriffe, Betriebszustände,
Negationen und Zahlen behalten ihr Gewicht. Semantische Suchanfragen und die
Originalfrage bleiben vollständig erhalten. Diese kleine, explizite Heuristik
ist keine grammatische Analyse und kein allgemein optimiertes Sprachmodell.

Auf dem vollständigen Korpus rückt die Leerlauf-Referenz von BM25-Rang 13 auf 4.
Die Referenzränge der anderen neun Starterfälle bleiben gleich; insgesamt elf
Referenzstellen in zehn Fällen wurden geprüft. Die Rohdaten des Vergleichs
enthalten nur Ränge und Hashes, keine Transkripttexte:
`evaluation/results/lexical-weighting-2026-10-05.json`.

Reproduzierbar ohne Modellaufrufe aus dem Repository-Verzeichnis:

```sh
python -m evaluation.lexical_probe --output evaluation/results/lexical-probe.json
```

Dieser Vergleich prüft ausschließlich BM25 vor der Kosinus-Schwelle. Er beweist
noch nicht, dass die Referenz im laufenden hybriden System tatsächlich ausgewählt
und korrekt beantwortet wird. Das Starterset war an der Entwicklung beteiligt;
die Messung ist kein unabhängiger Qualitätsbenchmark. Die Schwellenwerte, die
16 Trefferplätze und das Kontextbudget bleiben unverändert.

## Aufzählungen vor einer Rückfrage prüfen

Wird eine Frage vom Modell als `DOMAIN_GENERIC` eingestuft, erkennt eine begrenzte
Regel konkrete Aufzählungsfragen wie „Welche Messverfahren … bei LWL?“ und versucht
zuerst die bestehende Zitatauswahl samt strenger Belegprüfung. Nur eine bestätigte
Quellenantwort wird ausgegeben. Andernfalls bleibt die bisherige Rückfrage erhalten.
Das gilt sowohl für neue Fragen als auch für den globalen Suchweg bei Folgefragen.

Eine reine Frage wie „Welche Methoden gibt es?“ ohne benanntes Thema sowie
quantitative Fragen wie „Welche Spannung ist zulässig?“ durchlaufen diese Ausnahme
nicht. Die Erkennung ist eine Heuristik mit begrenztem Wortschatz; sie garantiert
keine vollständige Aufzählung und kann andere Formulierungen übersehen. Bei einer
zuvor direkt gestellten Rückfrage können nun bis zu zwei zusätzliche Modellaufrufe
entstehen. Es wird keine fachliche Antwort aus der Regel selbst erzeugt.

## Differenzierter Testbericht

Der Bericht ergänzt `outcome`, ohne `passed`, Referenzen oder Schwellen zu ändern:

| Wert | Bedeutung |
| --- | --- |
| `reference_checks_passed` | Alle bisherigen Prüfungen bestanden. |
| `abstained` | Keine ausreichenden Belege ausgegeben. |
| `clarification` | Rückfrage gestellt; deren Notwendigkeit ist zu beurteilen. |
| `reference_not_confirmed` | Originalzitate, aber Referenz nicht bestätigt; alternative korrekte Belege sind möglich. |
| `invalid_quote_output` | Originaltext-/Metadaten- oder Zitatformatprüfung fehlgeschlagen. |
| `source_mismatch` | Quellenanzeige/API und Antwortzitate stimmen nicht überein. |
| `no_source_answer` | Sonstige Antwort ohne bestätigte Quellen. |

Eine Ablehnung oder Rückfrage besteht die drei bekannten beantwortbaren Testfälle
weiterhin nicht. Fehlende Referenzübereinstimmung wird nicht automatisch als
fachlich falsche Antwort bezeichnet. Alternative Belege wurden hier nicht ohne
inhaltliche Prüfung zu den Referenzen hinzugefügt.

80 lokale Tests bestanden (davon die acht Kontextauswahltests nach der letzten
Präzisierung der Aufzählungsregel erneut geprüft). Modelle waren simuliert und
Provider-Importbindungen lokal ersetzt. Zusätzlich wurde der beschriebene
BM25-Vergleich mit dem vollständigen Korpus ausgeführt. Kein Live-Nachweis dieser
Änderung; FastAPI-Integrationstests mangels installierter Abhängigkeiten nicht
ausgeführt. Nach Merge und Deployment einen neuen Lauf von `Live-Dialog pruefen`
auf `main` starten.
