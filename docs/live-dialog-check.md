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
umfassen Netzwerk und mögliche Wartezeiten. Die angeforderten Diagnosen enthalten
die vom Anbieter gemeldeten Tokenmetriken; fehlende Werte werden nicht geschätzt.

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

Beim Themenwechsel muss zusätzlich die konkrete Referenz aus Modul 26, Video 2
`26 LWL Pruefprotokolle 2 Normen.txt`, (0:03:40 - 0:03:48), enthalten sein.
Diese Passage nennt Dämpfungs- und Durchgängigkeitsmessung. Eine bloße
thematische Erwähnung besteht den Test damit nicht mehr. Weiterhin müssen
alle Zitate aus Modul 26, Fachbereich 4 stammen (`topic_scope_valid`), damit
keine PV-Zitate aus dem vorherigen Thema übernommen werden.

Der Test belegt damit weder die Vollständigkeit aller Messverfahren noch die
interne Turn-Klassifikation. Eine alternative fachlich ausreichende Textstelle
kann bei PV oder LWL am strikten Referenztest scheitern und muss dann manuell
geprüft werden. Drei Entwicklungsfälle sind kein unabhängiger Qualitätsbenchmark.

Der Workflow wird nicht automatisch auf Push oder Pull Requests ausgeführt.
Der Test verändert keine Anwendungskonfiguration und stellt nichts bereit.

## Fehler zwischen Suche und Zitatauswahl eingrenzen

Der Test fordert nun mit `include_diagnostics: true` eine Diagnose für seine
eigene Gesprächsrunde an. Normale Browseranfragen erhalten dieses Zusatzfeld
nicht. Es enthält keine Prompttexte, Transkripttexte oder Sitzungskennungen,
sondern Quellenreferenzen (Datei und Zeitstelle), Scores, Auswahl-Nummern,
Turn-/Antworttyp und die bereits erfassten Aufruf- und Tokenmetriken.
Die eigentlichen Antworten und Zitate stehen weiterhin separat im Testbericht.
Diagnosen sind Teil der öffentlichen Chat-API für die eigene Sitzung und kein
Zugriff auf andere Gespräche. Es gibt dafür weder weitere Modellaufrufe noch
eine neue Protokollierung aller Nutzergespräche.

`reference_trace` zeigt pro tatsächlichem Verarbeitungsschritt, ob die erwartete
PV- oder LWL-Referenz enthalten war und ob das Modell sie ausgewählt hat:

- `retrieval`: direkt gefundene Treffer vor der Kontexterweiterung.
- `selection`: Kandidaten einschließlich Nachbarstellen und erste Auswahl.
- `review`: dieselben Kandidaten und die bestätigte oder ersetzte Auswahl.

Fehlt die Referenz in `retrieval`, ist aber bei `selection` vorhanden, hat die
Kontexterweiterung sie ergänzt. Ist sie bei `selection` vorhanden, aber am Ende
nicht ausgewählt, liegt das Problem für diese Referenz in der Auswahlstrecke.
Fehlt sie in allen Auswahlkandidaten, muss zuerst die Suche/Kontexterweiterung
untersucht werden. Das ist ein Nachweis über konkrete Quellenreferenzen, keine
automatische fachliche Bewertung aller möglichen alternativen Belege.

Bei Folgefragen kann zunächst nur der lokale Kontext geprüft werden. Scheitert
dieser, folgen globale Suche und weitere Auswahlstufen. Deshalb ist die
Reihenfolge der Einträge relevant; mehrere `selection`-/`review`-Einträge sind
kein Fehler. `review` entfällt, wenn bereits der erste Vorschlag leer/ungültig ist.
Fehlende Diagnosen erscheinen als `available: false`, nicht als fehlender Treffer.

Die Diagnose wird pro Nachricht zurückgesetzt und auf 16 Ereignisse mit jeweils
40 Referenzen begrenzt. Bei gekürzten Quellenlisten ist `truncated` wahr; daraus
darf keine vollständige Abwesenheitsdiagnose abgeleitet werden. Die aktuellen
Produktionspfade bleiben innerhalb dieser Grenzen. Bereits vorhandene
Tokenmetriken enthalten nur gemeldeten Verbrauch, keine Preisberechnung.

Im Actions-Protokoll stehen nun auch erwartete/tatsächliche Version und die
Referenzprüfung je Stufe. Die vollständigen Diagnosen liegen im Ergebnisartefakt.


Der Bericht enthält außerdem `outcome`: bestandene Referenzprüfungen, Ablehnung,
Rückfrage, nicht bestätigte Referenz oder fehlerhafte Zitat-/Quellenausgabe.
`passed` verlangt weiterhin das Bestehen sämtlicher Prüfungen. Die LWL-Anforderung
wurde gegenüber dem bisherigen reinen Modulvergleich verschärft.
Details und aktueller Suchvergleich: `docs/recall-and-enumeration.md`.


## Stand vom 9. Oktober 2026

Der Live-Lauf 37912770293 auf Revision d609a5fa193d021714731140cb5744fe818d6aa6
bestand alle drei bisherigen Dialogfälle. Dieser Lauf verwendete für LWL noch
den reinen Modulvergleich und belegt die neue konkrete Referenzanforderung nicht.
Auch die genaue Ursache der früheren Ablehnung lässt sich aus dem kompakten
Actions-Protokoll nicht ableiten.

Die verschärfte Prüfung ist mit 14 lokalen, simulierten Tests geprüft, darunter
ein Originalzitat ohne Methodenreferenz, unerwünschte PV-Zitate neben der gültigen
LWL-Referenz und ein unvollständiger Referenzkorpus. Kein Chatbot-Prompt und kein
Produktionsverhalten wurde für die neue Referenz angepasst. Nach Merge und
Deployment ist ein neuer manueller Live-Lauf erforderlich.
