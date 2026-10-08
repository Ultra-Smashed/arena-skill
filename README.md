# Arena

Wenn eine Antwort nicht trägt, schick dieselbe Aufgabe durch ein Turnier. Ein Claude-Code-Skill. Die Teilnehmer sind Unter-Agenten des Modells, das gerade läuft. Verschieden macht sie die Karte, nicht ein zweites Modell.

Jede Karte ist eine Denkweise, ein Arbeitsablauf und eine Haltung. Alle bekommen denselben Aufgabentext. Danach greifen sie einander an, überarbeiten die eigene Lösung, und ein Richter vergibt Punkte. `bracket.py` rechnet und lässt die schwächere Lösung ausscheiden, bis eine bleibt.

Die Unter-Agenten schreiben nur nach `.arena/`. Die siegreiche Lösung kommt zurück. Ob sie ins Projekt übernommen wird, bleibt eine eigene Frage.

## Installieren

Ordner kopieren, dann ist der Befehl `/arena`:

```bash
cp -r skills/arena ~/.claude/skills/
```

Im Projekt statt global: denselben Ordner nach `.claude/skills/` im Repo legen.

Als Plugin, der Befehl heißt dann mit Namensraum, also `/arena-skill:arena`:

```text
/plugin marketplace add <dieses-repo>
/plugin install arena-skill@arena-skill
```

Es braucht Claude Code, weil die Teilnehmer über das Agenten-Werkzeug starten, und Python 3.8 oder neuer. Nichts zu installieren per pip.

## Benutzen

```text
/arena
/arena --quick Formulier die Überschrift für die Preisseite
/arena --agents 32 Beheb den flatternden Test in tests/test_api.py
/arena --seed 7 Plan die Launch-Woche, ich habe 6 Stunden am Tag
```

Ohne Text nimmt `/arena` die letzte Bitte als Aufgabe und die Antwort, die nicht getragen hat, als die Fassung zum Vergleich. Sagt jemand nur, die Antwort sei schlecht, kann der Skill von selbst anspringen. Dann fragt er einmal, bevor er etwas ausgibt.

| Flag | Wirkung |
| --- | --- |
| `--agents N` | N Teilnehmer. Standard 100. |
| `--quick` | 16 Teilnehmer. Der Lauf für den Alltag. |
| `--seed S` | Dieselbe Saat, dieselben Karten, dieselbe Paarung. Standard zufällig, und festgehalten. |
| `--wave W` | Unter-Agenten pro Welle. Standard 10. Nur anheben, wenn das Limit für gleichzeitige Aufrufe angehoben wurde. |

## Ablauf

1. **Entwurf.** N Unter-Agenten, einer pro Aufruf. Dieselbe Aufgabe, eine eigene Karte. 15 Denkweisen, 12 Arbeitsabläufe, 12 Haltungen, 2160 Karten. Keine Karte zweimal, die drei Listen so gleichmäßig wie möglich. Bis 100 Teilnehmer teilen sich zwei Karten höchstens ein Merkmal.
2. **Angriff.** Die Lösungen werden gepaart, möglichst ohne dieselbe Denkweise in einem Duell. Jede Seite greift durch ihre Karte an: was falsch ist, welche Anforderung fehlt, welche Eingabe bricht. Höchstens 7 Angriffe, markiert als FATAL, MAJOR oder MINOR.
3. **Verteidigung.** Jede Seite geht die Angriffe durch, räumt ein oder hält dagegen, und schreibt die Lösung neu.
4. **Richter.** Ein eigener Unter-Agent liest beide Fassungen und vergibt Punkte: Richtigkeit 30, Vollständigkeit 25, Robustheit 20, Konkretheit 15, Klarheit 10. Die Karten sieht er nicht. Wer weiterkommt, setzt `bracket.py`. Eine als fatal geprüfte Lösung kann eine andere, die das nicht ist, nicht schlagen, auch bei höherer Summe.
5. **Weiter.** Die überarbeitete Lösung geht in die nächste Runde. Bei ungerader Zahl gibt es ein Freilos, nie zweimal derselben Lösung, solange eine andere noch keines hatte.
6. **Ergebnis.** Eine Lösung, die Angriffe, die sie bestanden hat, ihre Karte, die Rundenzahl. Lag eine abgelehnte Antwort vor, vergleicht ein letzter Richter blind, und das Ergebnis wird auch dann gesagt, wenn die alte Antwort vorn liegt.

Der Stand liegt in einer JSON-Datei. Der Chat führt nur die Schleife und liest die Lösungsdateien während des Laufs nicht. Jeder Unter-Agent schreibt auf die Platte und antwortet mit einer Zeile. Nach einer Verdichtung des Gesprächs setzt `bracket.py next` auf dem Stand auf.

## Was es ausgibt an Aufrufen

Der Skill selbst ist lokal. Die Aufrufe laufen über das Modell, und 100 Teilnehmer sind viele.

| Teilnehmer | Runden | Aufrufe | Wellen zu 10 |
| --- | --- | --- | --- |
| 100, der Standard | 7 | 595 | 70 |
| 64 | 6 | 379 | 49 |
| 32 | 5 | 187 | 28 |
| 16, `--quick` | 4 | 91 | 16 |
| 8 | 3 | 43 | 10 |

Liegt eine abgelehnte Antwort vor, kommt ein Vergleich dazu. Jeder Aufruf liest die Aufgabe und eine oder zwei Lösungen, die Rechnung wächst also mit der Aufgabe. Für den Alltag `--quick` oder `--agents 16`, die 100 für die Antwort, auf die es ankommt. Vor dem Start stehen die Zahlen da, und `python3 skills/arena/bracket.py plan --agents N` zeigt sie jederzeit.

## Das Programm

`bracket.py` ist Python aus der Standardbibliothek. Deshalb verliert die Leitung den Faden nicht.

```bash
python3 skills/arena/bracket.py plan --agents 100
python3 skills/arena/bracket.py init --agents 100 --seed 7 --task-file task.md [--baseline-file alt.md]
python3 skills/arena/bracket.py next
python3 skills/arena/bracket.py prompts attack
python3 skills/arena/bracket.py pairings
python3 skills/arena/bracket.py collect
python3 skills/arena/bracket.py record r3-m07 a042 --reason "..."
python3 skills/arena/bracket.py advance
python3 skills/arena/bracket.py status
python3 skills/arena/bracket.py winner
```

Die Tests spielen ein volles Turnier mit festgelegten Siegern durch und prüfen, dass am Ende genau eine Lösung bleibt, dazu 16, 7 und 1 Teilnehmer, die Garantien beim Mischen, und jede Phase vom Entwurf bis zum Vergleich:

```bash
python3 -m unittest discover -s tests -v
```

## Kleingedrucktes

**Viele Versionen heißen viele Unter-Agenten desselben Modells.** Nicht viele Modelle. Den Unterschied macht die Karte. Keine Karte doppelt, jede Denkweise, jeder Arbeitsablauf und jede Haltung so gleichmäßig wie möglich, und bis 100 Teilnehmer teilen sich zwei Karten höchstens ein Merkmal.

**Ein Teilnehmer ist seine Karte plus seine Lösungsdatei.** Zwischen den Aufrufen merkt sich niemand etwas. Greift `a017` in Runde 3 an, ist das ein frischer Unter-Agent mit der Karte und der letzten Lösung von `a017`.

**Die gebliebene Lösung ist die, die jedes Duell überstanden hat.** Die Richter sind dasselbe Modell, an einer Rubrik, die im Repo liegt und geändert werden kann. Das ist die stärkste Lösung dieses Laufs, kein Beweis, dass sie stimmt. Deshalb liegen die bestandenen Angriffe bei, und deshalb sagt der Skill, wenn die abgelehnte Antwort besser punktet.

**Nicht alle laufen auf einmal.** Die Wellen haben die Größe 10, passend zum üblichen Limit gleichzeitiger Aufrufe. Wer das Limit anhebt, gibt `--wave` mit.

**Ohne Freigabe im Voraus kommt eine Bestätigung pro Datei.** Jeder Unter-Agent schreibt nach `.arena/`. Für den Lauf die Änderungen annehmen.

**Unter-Agenten sehen den Chat nicht.** Die Aufgabendatei ist alles, was sie kennen. Steht eine Anforderung nicht darin, verfehlen sie alle. Sie liegt unter `.arena/<lauf>/task.md`.

**Das Projekt bleibt unangetastet.** Änderungen an Dateien stehen in der siegreichen Lösung. Übernehmen ist eine eigene Frage, und der Skill stellt sie.

**Dieselbe Saat gibt dieselben Karten und dieselbe Paarung.** Nicht dieselben Antworten. Das Modell ist nicht festgelegt.

**Eine unscharfe Aufgabe wird nicht scharf.** Unscharf hinein, viele unscharfe Antworten hinaus.

## Dateien

```text
skills/arena/SKILL.md          Leitung des Turniers und die Briefings
skills/arena/bracket.py        Stand und Rechnung, nur die Standardbibliothek
skills/arena/strategies.json   15 Denkweisen, 12 Arbeitsabläufe, 12 Haltungen
skills/arena/rubric.md         die fünf Kriterien der Richter
tests/test_bracket.py          die Tests
LICENSE                        MIT
```

## Lizenz

MIT. Kopieren, ändern, weitergeben. Der Hinweis auf das Copyright bleibt dabei stehen.

## Credit

Made by Christopher Thanisch, [thanisch.co](https://thanisch.co).
