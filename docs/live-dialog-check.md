# Live-Dialog ohne Render-Shell prüfen

Nach dem Merge dieses PRs und dem Render-Deployment in GitHub unter **Actions →
Live-Dialog pruefen → Run workflow** den Branch **main** wählen. Der Workflow
läuft ausschließlich manuell. Er benötigt keine neuen Secrets, keinen lokalen
API-Schlüssel und keine zusätzlichen Python-Pakete.

Der Test verwendet den öffentlichen Dienst mybrainday.onrender.com. Er vergleicht
zunächst dessen `/health`-Revision mit dem gewählten GitHub-Commit. Bei Abweichung
endet er vor den Chat-Anfragen. `unknown` ist ebenfalls keine bestätigte Version.
Ein roter Lauf kann deshalb auf einen noch nicht abgeschlossenen oder veralteten
Render-Deploy hinweisen. Nach dem Deployment erneut manuell starten.

Bei passender Version werden drei Nachrichten in **derselben neuen Sitzung**
gesendet: Leerlaufstrom, Kurzschlussspannung als Folgefrage, Wechsel zur LWL-Prüfung.
Das löst die üblichen kostenpflichtigen Modellaufrufe des laufenden Chatbots aus.
Es gibt keine automatischen Wiederholungen und keinen Indexneuaufbau.

Unter dem abgeschlossenen Lauf findet sich das Artefakt **live-dialog-result**
mit `deployment-check.json` (sieben Tage aufbewahrt). Es enthält Fragen, Antworten,
Quellen und einzelne Prüfergebnisse, aber keine Sitzungskennung. HTTP-Laufzeiten
umfassen Netzwerk und mögliche Wartezeiten; Tokenverbrauch ist in der öffentlichen
API nicht verfügbar und wird nicht aus diesen Zeiten geschätzt.

- `deployment_revision_mismatch_or_not_ready`: Version fehlt, stimmt nicht oder Dienst nicht bereit.
- `request_or_response_error`: HTTP-, Netzwerk- oder Antwortformatfehler; keine fachliche Bewertung.
- `conversation_not_preserved`: Sitzung fehlt oder hat sich zwischen Nachrichten geändert.
- `deployment_changed_during_run`: Version wechselte während des Tests; Lauf nicht vergleichbar.
- `dialog_regression_checks_failed`: Mindestens eine inhaltliche oder Quellenprüfung fehlgeschlagen.

Die beiden PV-Fragen prüfen bekannte Referenzstellen aus Modul 01, Video 2:
Leerlaufstrom (0:02:02 - 0:02:16), Kurzschlussspannung (0:03:25 - 0:03:42).
Alle Zitate werden mit dem Repository-Korpus auf Text und Metadaten verglichen.
Antworten dürfen nur die daraus formatierten Zitatblöcke enthalten. `/sources`
und das `sources`-Feld müssen mit den aktuellen Zitaten übereinstimmen.

Beim Themenwechsel wird nur geprüft, dass alle ausgegebenen Zitate aus Modul 26,
Fachbereich 4 stammen. Das beweist weder die Vollständigkeit der Messverfahren
noch die interne Turn-Klassifikation. Eine alternative fachlich ausreichende
PV-Textstelle kann am strikten Referenztest scheitern und muss dann manuell
geprüft werden. Drei Entwicklungsfälle sind kein unabhängiger Qualitätsbenchmark.

Der Workflow wird nicht automatisch auf Push oder Pull Requests ausgeführt.
Der Test verändert keine Anwendungskonfiguration und stellt nichts bereit.
