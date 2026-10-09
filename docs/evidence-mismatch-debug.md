# Abweichende Belegpassagen diagnostizieren

Die Antwortlogik und die Ablehnungsbedingungen bleiben unverändert. Zusätzlich
kann eine eigene Chat-Anfrage mit `include_diagnostics: true` und
`include_evidence_debug: true` die erste nicht wortgetreu passende Belegpassage
je Prüfversuch erfassen. Beide Flags sind erforderlich und werden pro Anfrage
neu gesetzt. Normale Chats und alleinige Standarddiagnosen enthalten diese
Zusatztexte nicht.

Im Trace unter `validation.mismatch` stehen:

- `model_span`: vom Modell vorgeschlagener Beleg, höchstens 2000 Zeichen.
- `original_text`: tatsächlich zugeordneter Originalabschnitt, höchstens 6000 Zeichen.
- `source`, `filename`, `time_range`: die beanstandete Zuordnung.
- `model_span_truncated`, `original_text_truncated`: explizite Kürzungshinweise.
- `matching_candidate_numbers`: bis zu 40 geprüfte Kandidaten, in denen die
  Passage nach dem bisherigen Leerraumvergleich vorkommt.

`model_span` ist unvalidierter Modelltext, kein freigegebenes Zitat. Andere
Treffer werden nur zur Diagnose genannt und nicht automatisch übernommen.
Es werden weder der gesamte Prompt noch die vollständige rohe Modellantwort
oder Sitzungskennungen hinzugefügt. Keine zusätzlichen Modellaufrufe.

Beide manuellen Live-Testskripte fordern diese Zusatzdiagnose über die gemeinsame
HTTP-Funktion an. Texte erscheinen im Ergebnisartefakt (7 Tage Aufbewahrung),
nicht in der kompakten Actions-Ausgabe. Zugriff auf das Artefakt gewährt auch
Zugriff auf diese Diagnoseinhalte. Keine allgemeine Protokollierung von Chats.

Nach Merge und Deployment `Live-Referenzfragen pruefen` neu starten und
`live-reference-result.zip` zur Auswertung bereitstellen. Der Fehlergrund kann
z.B. eine falsche Quellenzuordnung oder eine Textänderung sein; erst der konkrete
Vergleich erlaubt eine Aussage darüber. Die Diagnose verändert den Test nicht.

131 lokal ausführbare Tests bestanden mit simulierten Modellantworten. Neue
Tests prüfen Standard-Inhaltsfreiheit, ausdrückliche Aktivierung mit beiden Flags,
falsche Quellenzuordnung, Begrenzungen und unveränderte Ablehnung. Zwei weitere
API-Testmodule benötigen das hier fehlende FastAPI und wurden nicht ausgeführt.
