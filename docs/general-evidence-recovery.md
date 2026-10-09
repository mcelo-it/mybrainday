# Allgemeine Belegauswahl und begrenzte Korrektur

Eine leere oder formal ungültige Vorauswahl beweist nicht, dass alle vorhandenen
Quellen unzureichend sind. Bei vorhandenen Kandidaten prüft deshalb die zweite
Stufe jetzt auch einen leeren Vorschlag unabhängig anhand derselben gesamten
Kandidatenmenge. Es werden weder Test-IDs noch konkrete Referenzfragen abgefragt.

Die Auswahl- und Prüfaufforderungen unterscheiden explizit quantitative Fragen,
Definitionen, qualitative Veränderungen und Vergleiche. Mehrere inhaltlich
zusammengehörige Abschnitte dürfen gemeinsam eine Antwort belegen. Bedingungen
und Bezug müssen übereinstimmen; Vorwissen darf keine fehlenden Aussagen ersetzen.

Meldet die formale Prüfung `span_not_in_source`, erfolgt genau ein weiterer
Prüfaufruf mit Hinweis auf wortgetreues Kopieren einschließlich Schreibweisen und
Transkriptionsfehlern. Er erhält erneut die Originalkandidaten und einen leeren
Vorschlag, nicht den fehlerhaften Beleg als vermeintliche Quelle. Seine Ausgabe
muss dieselbe vollständige Validierung bestehen. Eine bewusste Ablehnung, fehlende
Zahlenbelege oder andere Validierungsfehler lösen keinen solchen Versuch aus.
Ein erneut ungültiger Beleg wird verworfen. Providerfehler werden weitergereicht.

Die Ausgabe besteht weiterhin aus unveränderten Originalsegmenten. Die Suche
wird durch diese Änderung nicht erweitert: Belege außerhalb der Kandidaten kann
auch die zusätzliche Prüfung nicht verwenden. Es ist kein allgemeiner Nachweis
semantischer Richtigkeit und keine Garantie gegen wiederholte Modellfehler.

Diagnose: Der zusätzliche Versuch erscheint als `review_repair`; die Metrikstufe
heißt `repair_quote_evidence`. Nach leerer Vorauswahl kommt ein Prüfaufruf hinzu,
bei ungültigen Belegpassagen höchstens ein weiterer pro Auswahlvorgang. Bei einer
lokalen Folgefragenprüfung mit anschließender globaler Suche gilt die Grenze je
Auswahlvorgang. Dadurch können Laufzeit und Kosten steigen.

Validierung: 127 lokal ausführbare Tests bestanden, mit simulierten Modell- und
HTTP-Antworten. Neue Fälle prüfen Wiedergewinnung nach leerer Auswahl, erfolgreiche
Belegkorrektur, Abbruch nach einmaliger erfolgloser Korrektur und das Beibehalten
bewusster Ablehnungen. Zwei API-Testmodule waren wegen fehlendem FastAPI in dieser
Arbeitsumgebung nicht ausführbar. Kein Live-Nachweis dieser Änderung liegt vor.
Nach Merge und Deployment beide manuellen Live-Workflows starten. Die bestehenden
Referenzanforderungen bleiben unverändert; ein unabhängiges, fachlich geprüftes
Testset ist weiterhin erforderlich, um Generalisierung zu beurteilen.
