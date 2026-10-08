# Wertung der Arena

Jedes Duell wird nach dieser Seite bewertet. Der Richter vergibt Punkte. `bracket.py` rechnet und entscheidet, wer weiterkommt.

## Die fünf Kriterien

Jedes Kriterium läuft von 0 bis 10. Das Gewicht ist sein Anteil an 100 Punkten.

| Kriterium | Schlüssel | Gewicht | Die Frage |
| --- | --- | --- | --- |
| Richtigkeit | correctness | 30 | Stimmt es? Keine falschen Behauptungen, keine Denkfehler, keine Fehler im Code, nichts, das die lesende Person in die Irre führt. |
| Vollständigkeit | completeness | 25 | Ist jede Anforderung erfüllt, die der Aufgabentext tatsächlich stellt? Gemessen am Text, nicht an dem, was der Richter zusätzlich gern hätte. |
| Robustheit | robustness | 20 | Hält die überarbeitete Lösung den Angriffen dieses Duells stand? Behoben, zutreffend gehalten, oder noch offen. |
| Konkretheit | specificity | 15 | Kann die Person jetzt handeln, ohne zu raten? Genaue Schritte, Werte, Namen, Code. |
| Klarheit | clarity | 10 | Ist die Lösung in einer Länge lesbar, die zur Aufgabe passt? |

Gewichtete Summe = (Richtigkeit × 30 + Vollständigkeit × 25 + Konkretheit × 15 + Robustheit × 20 + Klarheit × 10) / 10.
Das ergibt eine Zahl von 0 bis 100.

## Anker

Die ganze Skala ist da. Eine 7 ist keine höfliche Mitte.

**Richtigkeit**
- 10: Nach eigener Prüfung ist nichts falsch.
- 7: Kleine Ausrutscher, die das Ergebnis für die Person nicht drehen.
- 4: Mindestens ein Fehler, über den die Person stolpern würde.
- 0 bis 2: Im Kern falsch, oder die Anwendung würde Schaden anrichten.

**Vollständigkeit**
- 10: Jede genannte Anforderung ist ganz erfüllt.
- 7: Jede Anforderung ist angerissen, eine bleibt dünn.
- 4: Eine genannte Anforderung fehlt.
- 0 bis 2: Die Lösung beantwortet eine andere Frage als die gestellte.

**Konkretheit**
- 10: Jeder Teil lässt sich sofort ausführen.
- 7: Weitgehend konkret, an einer oder zwei Stellen muss man raten.
- 4: Viele Ausweichformeln, ohne die eigentliche Antwort.
- 0 bis 2: Rat, der zu jeder Aufgabe passen würde.

**Robustheit**
- 10: Jeder Angriff dieses Duells ist in der überarbeiteten Lösung behoben oder zutreffend gehalten, und die Verbesserung zerbricht nichts anderes.
- 7: Ein kleiner Angriff steht noch.
- 4: Ein gewichtiger Angriff steht noch, oder eine Reparatur hat etwas anderes beschädigt.
- 0 bis 2: Ein schwerer Angriff steht noch.

Fehlt die Angriffsdatei, hat die Gegenseite nichts vorgebracht. Bewerte die Robustheit dann nach den Mängeln, die du selbst gefunden hast.

**Klarheit**
- 10: Der Aufbau zeigt, wie man die Lösung benutzt. Kein Füllmaterial.
- 7: Brauchbar, mit etwas Füllung oder einem unklaren Abschnitt.
- 4: Die Antwort muss zusammengesucht werden.
- 0 bis 2: Kaum zu folgen.

## Schwere Fehler

Setze `fatal` nur, wenn du einen Mangel geprüft hast, der die Lösung für diese Aufgabe falsch oder unbenutzbar macht: Code, der so nicht laufen kann, eine falsche zentrale Behauptung, eine harte Grenze gebrochen, die falsche Frage beantwortet. Eine fatale Lösung kann eine nicht-fatale nicht schlagen, ganz gleich welche Summen dastehen. Sind beide fatal, entscheiden die Summen.

## Gleichstand

Es gibt kein Unentschieden. Bei gleicher Summe gewinnt die Lösung mit weniger noch offenen Angriffen. Ist auch das gleich, gewinnt die höhere Richtigkeit. Ist auch das gleich, entscheidet `bracket.py` zugunsten der kleineren Teilnehmerkennung.

## Was nichts zählt

- **Länge.** Länger ist nicht besser. Eine knappe Lösung, die jede Anforderung trifft, schlägt eine lange mit denselben Treffern.
- **Beteuern.** „Behoben“ ist kein Beleg. Sieh in die überarbeitete Lösung.
- **Die Karte.** Der Richter sieht die Karten nicht und rät nicht danach. Gewertet wird die Arbeit.
- **Selbstlob.** Dass eine Lösung sich robust nennt, gibt keine Punkte.
- **Der Geschmack des Richters**, wo die Aufgabe ihn nicht verlangt.
