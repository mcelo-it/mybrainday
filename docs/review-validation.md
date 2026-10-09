# Belegprüfung: Leerraum und Diagnose

Die bisherige Belegprüfung verwarf auch dann die gesamte Auswahl, wenn eine
ansonsten identische Passage nur andere Leerzeichen oder Absatzumbrüche enthielt.
Der Vergleich toleriert jetzt ausschließlich Unterschiede zwischen
Leerraumfolgen. Wörter, Zahlen, Groß-/Kleinschreibung und Satzzeichen müssen
weiterhin übereinstimmen. Quellenübergreifende oder erfundene Passagen bleiben
unzulässig. Die Ausgabe verwendet weiterhin die unveränderten Originalsegmente.

Bei aktivierter Diagnose enthält das Ereignis `review` zusätzlich `validation`:

- `status`: `accepted`, `model_abstained`, `invalid_json`, `invalid_schema`,
  `invalid_source`, `missing_evidence`, `invalid_evidence_schema`,
  `invalid_evidence_source`, `empty_span`, `span_not_in_source` oder
  `quantity_not_supported`.
- `proposed`: gültige Quellen-IDs der Prüferantwort, maximal 40.
- `whitespace_normalized`: ob ein Beleg den Leerraumvergleich benötigte.

Diese Angaben enthalten weder die Modellantwort noch Belegtexte. Die Diagnose
bleibt optional. Es gibt keinen zusätzlichen Modellaufruf und keine ungeprüfte
Übernahme der ersten Auswahl. Die Live-Testkriterien bleiben unverändert.

109 lokal ausführbare Tests bestanden, einschließlich Ablehnungsdiagnose,
Leerraumtoleranz und unveränderter Zitat-Ausgabe. Modellantworten wurden simuliert;
das ist kein Nachweis für die Qualität des Live-Modells. Zwei zusätzliche
Testmodule benötigen FastAPI, das in dieser Arbeitsumgebung fehlt, und konnten
hier nicht ausgeführt werden.

Nach Merge und Deployment einen neuen Lauf von `Live-Dialog pruefen` starten.
Falls eine Auswahl erneut verworfen wird, zeigt `validation.status` erstmals,
ob der Prüfer selbst verzichtet oder die formale Prüfung ablehnt. Der bisherige
Trace erlaubt diese Unterscheidung nicht; die Leerraumursache ist für den
bisherigen Live-Fehler daher nicht bewiesen.
