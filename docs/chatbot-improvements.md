# Chatbot verbessern – Schritt für Schritt

## Schritt 1: Konversationen isolieren

**Problem:** Eine globale `RAGSystem`-Instanz enthielt sowohl den Suchindex als
auch den Gesprächsverlauf aller Besucher. Eine Folgefrage oder eine Antwort
auf eine Rückfrage konnte dadurch zum Gespräch einer anderen Person gehören.
Auch `/sources` lieferte den global zuletzt abgefragten Kontext.

**Änderung:** `ConversationState` enthält jetzt sämtliche veränderlichen
Dialogdaten: Verlauf, letzte Fragen, Themenzusammenfassung, ausgewählte und
abgerufene Quellen sowie offene Rückfragen. Für jeden Turn erzeugt
`RAGSystem.for_conversation(state)` eine leichte Instanz, die Dokumente,
Chunks, Embeddings und API-Client mit dem geladenen Index teilt. Nur der
Gesprächszustand ist sitzungsspezifisch. Es entstehen keine zusätzlichen
Embedding-Aufrufe und keine Kopien der großen Embedding-Matrix pro Nutzer.

### Ablauf und API

1. Der erste `POST /chat` enthält wie bisher `{"message": "Was ist NA-Schutz?"}`.
2. Die Antwort enthält zusätzlich `conversation_id`, eine serverseitig erzeugte,
   zufällige Kennung mit 256 Bit Zufall.
3. Weitere Nachrichten senden diese Kennung im Header `X-Conversation-ID`.
4. `GET /sources` verwendet denselben Header. Ohne Kennung liefert die Route
   eine leere Liste; unbekannte oder abgelaufene Kennungen ergeben HTTP 404.
5. Ohne Kennung beginnt jede Chat-Anfrage eine neue Sitzung. Alte API-Clients
   können weiter Fragen stellen, müssen für Folgefragen aber die Kennung senden.

Das Frontend hält die Kennung ausschließlich im Speicher der geöffneten Seite.
Ein neuer Tab oder Neuladen beginnt einen neuen Chat. Ein Ablauf wird sichtbar
gemeldet; die nächste Nachricht beginnt ohne bisherigen Kontext. Eine
fehlgeschlagene Nachricht wird nicht automatisch erneut gesendet.

Die Kennung gewährt Zugriff auf diese anonyme Konversation und sollte nicht
geteilt oder protokolliert werden. Sie ersetzt keine Benutzeranmeldung. Für
spätere Benutzerkonten ist zusätzlich eine Bindung an den angemeldeten Nutzer
erforderlich.

### Gleichzeitigkeit, Fehler und Speicher

- Nachrichten derselben Sitzung werden nacheinander verarbeitet. Verschiedene
  Sitzungen dürfen gleichzeitig antworten; es gibt keine globale LLM-Sperre.
- Eine Anfrage arbeitet auf einer Kopie des kleinen Gesprächszustands. Erst
  nach erfolgreicher Verarbeitung wird dieser übernommen. Ein Modellfehler
  lässt das letzte erfolgreiche Gespräch unverändert.
- Aktive und wartende Anfragen werden bei der Sitzungsbereinigung geschützt.
- Standard: eine Stunde Inaktivität (`SESSION_TTL_SECONDS=3600`), maximal 500
  Sitzungen (`MAX_SESSIONS=500`), letzte 40 Verlaufsnachrichten. Die
  Themenzusammenfassung und zuletzt ausgewählte Quellen bleiben zusätzlich
  erhalten. Eingaben sind auf 8.000 Zeichen begrenzt.
- Abgelaufene Sitzungen werden bei der nächsten Sitzungsoperation entfernt.
  Sind alle Plätze belegt, erhalten neue Chats HTTP 503; bestehende werden
  nicht verdrängt.
- Beim administrativen Index-Neuaufbau wird eine separate Indexinstanz erstellt
  und erst nach Erfolg ausgetauscht. Laufende Anfragen behalten ihren bisherigen
  konsistenten Index. Bestehende Gesprächskontexte dürfen für Folgefragen noch
  zuvor ausgewählte Quellenausschnitte verwenden.

### Deployment-Grenze

Die Sitzungen liegen **im Speicher eines einzelnen Serverprozesses**. Ein
Neustart oder Deployment beendet sie. Mehrere Worker oder mehrere Instanzen
benötigen zuerst einen gemeinsamen Sitzungsspeicher (zum Beispiel Redis) mit
einer pro Sitzung wirksamen Sperre bzw. Versionskontrolle. Nur ein gemeinsamer
Speicher ohne Schutz vor parallelen Schreibvorgängen reicht nicht.

`render.yaml` startet deshalb ausdrücklich einen Worker vom Repository-Root:

```bash
uvicorn backend.app:app --workers 1 --host 0.0.0.0 --port "$PORT"
```

Das korrigiert zugleich den bisherigen Startpfad: `app.py` verwendet einen
relativen Paketimport und muss als `backend.app` importiert werden.

### Überprüfung

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node --check frontend/app.js
```

Die Tests verwenden die echten API-Routen, die RAG-Dialogsteuerung und den
Sitzungsspeicher. Modellabhängige Schritte sind deterministisch ersetzt;
es entstehen keine API-Kosten. Geprüft werden unabhängige Folgefragen und
Quellen zweier Nutzer, offene Rückfragen, fehlende/ungültige/abgelaufene
Kennungen, Fehler-Rollback, Sitzungsgrenzen und parallele Verarbeitung.
Die Tests bewerten noch nicht die fachliche Qualität echter Modellantworten.

Manueller Abnahmetest nach Deployment: In zwei getrennten Tabs nach NA-Schutz
und Stromwandlern fragen, danach jeweils „Warum?“ eingeben und die Quellen
öffnen. Beide Gespräche müssen beim eigenen Thema bleiben. Nach Neuladen
beginnt die jeweilige Seite ohne gespeicherten Dialogkontext.

## Schritt 2: Wörtliche Zitate, Fachbereiche und Quellenlayout

**Produktvorgabe:** Antworten bleiben direkte Zitate aus den Lehrvideos. Eine
freie Antwortgenerierung oder Paraphrasierung wird nicht eingeführt. Die
ursprüngliche Empfehlung zur Antwortgenerierung entfällt.

### Zuordnung aus der bereitgestellten Gesamtübersicht

Die zentrale Datei `backend/subject_areas.json` enthält folgende Zuordnung:

| Fachbereich | Bezeichnung aus der Vorlage | Module |
| --- | --- | --- |
| 1 | Komponenten der Photovoltaik | 01–09 |
| 2 | Komponenten der Transformator- und Übergabestation | 10–15 |
| 3 | Systemintegration | 16–21 |
| 4 | Datentechnik | 22–29 |
| 5 | Anwendungsregel VDE-AR-N 4110 | 30–36 |
| 6 | Elektrische Energiesystem | 37–44 |

Die Bezeichnungen wurden aus der vom Nutzer bereitgestellten Übersicht
übernommen, einschließlich der Schreibweise von Fachbereich 6. Die Bilddatei
selbst wird nicht ins Repository aufgenommen.

Die Zuordnung erfolgt deterministisch anhand der Modulnummer (z. B. `1` oder
`01`), nicht durch das Sprachmodell. Doppelte Zuordnungen und fehlende Module
1–44 verhindern das Laden einer fehlerhaften Konfiguration. Neue, noch nicht
zugeordnete Modulnummern werden als „Nicht zugeordnet“ angezeigt. Änderungen
an der JSON-Datei benötigen einen Backend-Neustart, aber **keinen Neuaufbau
der Embeddings**. Die Fachbereiche werden auch an die Video-API angehängt.

### Zitat und Quelle gehören zusammen

`construct_answer_from_chunks()` erstellt die Antwort und `last_citations`
aus genau denselben ausgewählten Ausschnitten. Der Zitattext wird nicht
umformuliert; wie bisher wird lediglich äußerer Leerraum entfernt. Jede
Quellenangabe enthält Fachbereichsnummer und -name, Modulnummer und -name,
Videonummer und -name sowie den ursprünglichen Zeitbereich.

`POST /chat` liefert zusätzlich `citations`. Das bisherige Feld `sources`
bleibt als Alias erhalten, enthält aber ebenfalls nur tatsächlich zitierte
Ausschnitte. `GET /sources` liefert dieselben Belege für die letzte erfolgreiche
Antwort dieser Sitzung. Technische Retrieval-Scores werden nicht ausgegeben.
`text` enthält das vollständige Zitat; `text_preview` bleibt als gekürztes
Kompatibilitätsfeld erhalten. Die neue Oberfläche verwendet `text`.

Zu Beginn jedes Turns werden dessen Zitate geleert. Smalltalk, Ablehnungen und
noch offene Rückfragen zeigen deshalb keine alten Quellen. Der fachliche
Folgefragenkontext (`last_selected_chunks`) bleibt unabhängig davon erhalten.
Das schützt Folgefragen davor, ihren Kontext nach einem „Danke“ zu verlieren.
Bei einem fehlgeschlagenen Turn bleibt durch die Transaktion aus Schritt 1 der
letzte erfolgreiche Zustand erhalten.

### Layoutkorrektur

Die Ursache der großen Leerflächen im Screenshot war `white-space: pre-wrap`
am gesamten Dialoginhalt. Das machte Einrückungen und Zeilenumbrüche der
HTML-Vorlage sichtbar. Der Dialog verwendet jetzt normalen HTML-Textfluss.
Nur Zitate und Transkripte erhalten ihre tatsächlichen Zeilenumbrüche.

Jede Quellenkarte zeigt Fachbereich, Modul, Video und Zeitstelle kompakt
oberhalb des vollständigen Zitats. Metadaten und Zitat werden über DOM-Knoten
mit `textContent` eingesetzt, sodass HTML-artiger Transkripttext als Text
erscheint. Die technischen Relevanzwerte und alleinstehenden Trennstriche
entfallen. Der Dialogkopf bleibt sichtbar, während lange Quellenlisten im
Dialogkörper scrollen.

### Prüfung und Abnahme

Die Backend-Suite umfasst jetzt 15 Tests. Zusätzlich zu Schritt 1 deckt sie
alle 44 Modulzuordnungen, fehlerhafte Zuordnungsdateien, vollständige wörtliche
Zitate, den Ausschluss nicht zitierter Treffer, Folgefragen und das Leeren der
Belege bei Smalltalk, Ablehnungen und Rückfragen ab. Modellschritte bleiben
ersetzt; fachliche Relevanz echter Modellentscheidungen wird damit noch nicht
bewertet.

Die Browserprüfung `tests/test_sources_ui.cjs` wurde mit Chromium bei
1440 × 1000 und 390 × 844 Pixeln erfolgreich ausgeführt und visuell kontrolliert.
Sie prüft vollständige Zitate, Fachbereich und Zeitstelle, den Sitzungsheader,
kompakte Abstände, fehlenden horizontalen Überlauf, scrollbare lange Listen,
sichtbaren Schließen-Button, sichere Textdarstellung und den Leerzustand.
Die API ist dabei lokal simuliert; dies ersetzt keinen produktiven End-to-End-Test.

Für eine eigene Browserprüfung Playwright lokal installieren und ausführen:

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node tests/test_sources_ui.cjs
```

Manuell nach Deployment: eine Antwort mit Zitaten anfordern, „Letzte
Quellenstellen“ öffnen und Zitat sowie Zeitbereich vergleichen. Alle Karten
müssen Fachbereich, Modul und Video enthalten. Nach „Danke“ dürfen keine alten
Belege erscheinen. Anschließend muss eine Folgefrage weiterhin das vorherige
Thema verwenden können.

## Weitere Etappen

Schritt 1 und Schritt 2 sind als getrennte Änderungspakete vorbereitet.
Die folgenden Etappen richten sich nach der Vorgabe, direkte Zitate zu liefern.

| Etappe | Ziel und Nachweis |
| --- | --- |
| 3 | Zitatauswahl und Umfang verbessern: passende wörtliche Ausschnitte samt Zeitstellen auswählen, ohne Aussagen zu paraphrasieren. |
| 4 | Ein fachlich geprüftes Golden Testset und Evaluation aufbauen; relevante Quellen und erwartete Textstellen als Referenz verwenden. |
| 5 | Hybrid Retrieval und vektorisierte semantische Suche; Ranking-Fusion evaluieren, rohe BM25- und Cosine-Scores nicht ungeprüft gewichten. |
| 6 | Metadaten in Embeddings, Segmentfenster sowie Fingerprint/Indexversion gemeinsam einführen; kontrollierter Neuaufbau erforderlich. |
| 7 | Kandidaten reranken und Beantwortbarkeit anhand des Testsets kalibrieren. |
| 8 | Eigenständige Suchfragen aus Folgefragen und begrenztem Gesprächskontext erzeugen. |
| 9 | Router-Aufrufe bündeln und Klassifikationen auf validierte strukturierte Ausgaben umstellen. |
| 10 | Latenz, Retrieval-Qualität und Modellverbrauch messen; Verbesserungen gegen die Ausgangswerte vergleichen. |

## Korrektur: Quellen aus der angezeigten Antwort übernehmen

Nach Schritt 2 wurde gemeldet, dass der Quellenbereich trotz Zitaten im Chat
leer bleibt. Das Frontend verwendete die bereits in POST /chat gelieferten
citations nicht, sondern führte beim Öffnen des Dialogs eine zweite Abfrage
gegen GET /sources aus. Eine dort leere Antwort konnte vorhandene Belege
unsichtbar machen. Ob dies im gemeldeten Live-System durch Versionsmischung,
Sitzungszuordnung oder einen anderen Laufzeitfehler verursacht wurde, ist ohne
Live-URL noch nicht bestätigt.

Die Oberfläche hält jetzt die citations der letzten erfolgreichen Chatantwort
im Speicher dieses Tabs und zeigt genau diese im Quellenfenster. Es gibt dafür
keine zweite Serverabfrage. Eine erfolgreiche Antwort mit leerer citations-Liste
leert auch die Anzeige. Fehlt das Feld vollständig, erscheint ein Hinweis zur
fehlenden Zuordnung, statt fälschlich zu behaupten, es gäbe keine Zitate.
Retrieval-Kandidaten aus alten sources-Feldern werden nicht als Zitate übernommen.
Fehlgeschlagene Anfragen erhalten die Belege der vorherigen erfolgreichen
Antwort; eine abgelaufene Sitzung setzt die Zuordnung zurück.

Der neue Test `node tests/test_source_state.cjs` führt die echten Frontend-
Funktionen mit simuliertem DOM und HTTP-Antworten aus. Er scheitert am bisherigen
Code und besteht nach der Änderung. Er deckt vorhandene Zitate bei leerer
separater Quellenabfrage, unveränderten Text, Folgeanfragen mit Sitzungskennung,
Fehler, leere und veraltete Serverantworten ab. JavaScript-Syntaxprüfungen
bestehen ebenfalls. Der Playwright-Test wurde an den neuen Ablauf angepasst,
konnte für diese Korrektur in der aktuellen Umgebung jedoch nicht erneut
laufen, weil der Browser beim Start abbrach. Eine erneute Live-Prüfung steht aus.

## Schritt 3: Kontextfenster für die Zitatauswahl

Ein semantischer Treffer wie „Jetzt berechnen wir die Spannung“ kann das Thema
präzise treffen, aber die Frage nach dem Wert nicht beantworten. Deshalb wird
nicht nur der Prompt geändert: Die Auswahl erhält jetzt Nachbarabschnitte aus
demselben Video. Ein Treffer öffnet ein Fenster aus einem vorherigen und bis
zu drei folgenden Segmenten. Überlappungen werden dedupliziert und Abschnitte
pro Video in Transkriptreihenfolge angeordnet. Fachbereich, Modul, Video,
Segmentposition und Zeitbereich stehen im Auswahlkontext.

Die ursprünglichen Top-8-Treffer bilden weiterhin den Einstieg. Die bestehende
Relevanzprüfung erfolgt vor der Erweiterung. Ein Fenster enthält nur Abschnitte
mit identischem Dateinamen; unterschiedliche Videos werden nie als fortlaufende
Erklärung behandelt. Der Kontext ist auf 40 Ausschnitte und 60.000 Zeichen
Transkripttext begrenzt. Einzelne Texte werden nicht mitten im Zitat gekürzt;
bei Budgetmangel werden zusätzliche Ausschnitte ausgelassen. Die Begrenzung
betrifft Text, nicht die zusätzlichen Metadaten oder eine exakte Tokenzahl.

Nachbarabschnitte sind selbst auswählbare Quellen. Sie behalten ihren eigenen
Text und Zeitbereich. Ihr Zugang zur Auswahl beruht auf dem Relevanzwert des
Ankertreffers, nicht auf einem erfundenen eigenen Embedding-Score. Dadurch kann
ein nachfolgender Ergebnisabschnitt auch ohne Wiederholung der Suchbegriffe
zitiert werden. Die Modellauswahl bleibt für die tatsächliche Beantwortbarkeit
verantwortlich; der Ankerwert allein beweist keine fachliche Antwortqualität.

Die Auswahlregel fordert die eigentliche Antwort statt einer bloßen
Ankündigung. Bei Zahlen sind Einheit und Bedingungen mit auszuwählen; ein
Beispielwert darf nicht zur allgemeingültigen Empfehlung werden. Wenn eine
Bedingung im vorherigen Abschnitt steht, können beide Stellen separat zitiert
werden. Die Ausgabe bleibt wörtlich und mit Originalzeitstellen versehen.

Die Erweiterung gilt auch bei Folgefragen. Bei Rückfragen wird die vollständige
begrenzte Kandidatenliste verwendet, nicht mehr nur deren erste acht Einträge.
Der bisherige Fallback, bei erfolgloser Auswahl alle Quellen einer Option zu
zitieren, entfällt. Unerwartete freie Modelltexte werden nicht mehr mittels
beliebiger enthaltener Zahlen als Quellenliste interpretiert.

Validierung: Fünf Tests für Fensterbildung, Videogrenzen, Überlappungen,
Budgetgrenzen und Originaltext sowie vier Tests für Auswahlablauf, Folgefragen,
Originalzeitstellen, NONE nach Rückfragen und ungültige Modellantworten bestehen.
Die vier Ablaufprüfungen nutzen simulierte Modellantworten; in dieser Umgebung
wurden außerdem die fehlenden OpenAI-/dotenv-Importbindungen ersetzt. Die
Produktionsklasse und ihre Auswahl-/Antwortmethoden wurden unverändert geladen.
Python-Kompilierungsprüfung bestanden. Die komplette API-Suite konnte mangels
installierter Laufzeitabhängigkeiten hier nicht erneut ausgeführt werden.
Diese Tests belegen die Datenweitergabe und Auswahlmechanik, noch keine
verbesserte Treffergenauigkeit mit echten Modellantworten.

Für die fachliche Abnahme werden echte Fragen benötigt, bei denen bisher eine
Ankündigung statt des Ergebnisses erschien. Zu prüfen sind Ergebnis, Einheit,
Bedingungen und Videozeit. Ergebnisse weiter als drei Segmente nach dem Treffer
können weiterhin fehlen; eine spätere adaptive Erweiterung sollte anhand
solcher Beispiele bewertet werden. Kein neuer Embedding-Index ist erforderlich.
Die Modellaufrufzahl steigt nicht, die längeren Prompts können jedoch Kosten
und Latenz erhöhen.

## Schritt 4: Antwortstellen messbar machen und Suche vektorisieren

Der wissenschaftliche Bezug ist Kontextinsuffizienz (insufficient context):
Relevanz allein garantiert keine ausreichende Antwortgrundlage. Siehe
„Sufficient Context: A New Lens on Retrieval Augmented Generation Systems“
(https://arxiv.org/abs/2411.06037). Durch isolierte Segmente kann die eigentliche
Antwort außerhalb des anfänglichen Treffers liegen.

Unter evaluation/ liegt jetzt ein Entwicklungsset mit zehn Fragen aus drei
Transkripten und elf geprüften wörtlichen Referenzstellen. Für eine Frage
werden zwei Abschnitte gemeinsam benötigt. Die Auswertung misst sowohl den
Anteil gefundener Belege als auch vollständige Belegsets vor und nach der
Kontexterweiterung. Sie verwendet den produktiven Fensteralgorithmus. Die
Anleitung beschreibt einen ausdrücklich gestarteten Live-Lauf sowie API-freies
Replay mit gespeicherten Rankings und Versionshashes. Fehlende oder veränderte
Referenzen führen vor kostenpflichtigen Anfragen zum Abbruch.

Dies ist noch keine Messung der finalen Modellauswahl und kein unabhängiger
Qualitätsbenchmark. Ohne vollständigen lokalen Index und echte Frage-Embeddings
wurde hier keine Live-Treffergenauigkeit bestimmt. Fachliche Abnahme und ein
separates Testset bleiben notwendig. Auch nicht beantwortbare Fragen fehlen
bisher. Es werden keine verbesserten Trefferquoten aus simulierten Tests abgeleitet.

Die semantische Suche berechnet Kosinusähnlichkeiten jetzt als Matrixoperation
statt einer Python-Schleife über sämtliche Chunks. Die Zeilennormen werden beim
Laden oder Erstellen des Index berechnet und von Gesprächsinstanzen gemeinsam
verwendet. Scores, Relevanzschwelle und stabile Reihenfolge bei gleichen Scores
bleiben erhalten. Kleine Gleitkommaabweichungen können praktisch identische
Treffer anders ordnen. Ein Index-Neuaufbau ist nicht erforderlich.

Validierung: Drei numerische Retrieval-Tests, vier Evaluationstests, fünf
Fenstertests und vier bestehende Auswahltests bestanden. Für die Auswahltests
wurden nur die fehlenden OpenAI-/dotenv-Importbindungen ersetzt; Modellantworten
waren simuliert. Der produktive Chunk-Parser bestätigte alle elf Referenzstellen.
Python-Kompilierung bestanden. Ein einzelner synthetischer Vergleich mit
5.000 Vektoren à 1.536 Dimensionen ergab 22,30 ms für die Schleife und 0,86 ms
für die Matrixoperation; maximale Scoreabweichung 2,98e-8. Dies ist eine lokale
Mikromessung, keine Aussage zur gesamten Chat-Latenz oder Produktionsleistung.

Nächster fachlicher Schritt: Live-Auswertung auf dem vollständigen Cache,
anschließend manuelle Abnahme der tatsächlich ausgegebenen Zitate. Erst auf
dieser Grundlage hybride Suche und adaptive Kontextfenster vergleichen.
