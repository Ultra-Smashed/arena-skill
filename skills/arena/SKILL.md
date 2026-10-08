---
name: arena
description: >-
  Schickt eine Aufgabe durch ein K.-o.-Turnier aus Unter-Agenten. Standard
  sind 100 Teilnehmer, --quick nimmt 16. Jeder bekommt denselben Aufgabentext
  und eine andere Karte aus Denkweise, Arbeitsablauf und Haltung. Sie greifen
  einander an, überarbeiten die eigene Lösung, ein Richter vergibt Punkte,
  bracket.py entscheidet, wer weiterkommt, bis eine Lösung bleibt. Nutzen,
  wenn die letzte Antwort nicht trägt, bei „nochmal“, „das reicht nicht“,
  „schlecht“, „arena“, „lass sie gegeneinander“ oder „make them compete“.
argument-hint: "[--agents N | --quick] [--seed S] [--wave W] <Aufgabe>"
---

# arena

Für den Fall, dass eine Antwort nicht trägt. Statt dieselbe Frage nur noch einmal zu stellen, läuft ein Turnier: N Unter-Agenten bekommen dieselbe Aufgabe, jeder mit einer anderen Karte, und scheiden aus, bis eine Lösung bleibt. Du führst das Turnier. Du schreibst keine Lösung und du richtest kein Duell.

Was nach `/arena` steht: `$ARGUMENTS`

Ist das leer oder nur ein Platzhalter, nimm die Aufgabe aus dem Gespräch.

## Das Programm

Jede Buchhaltung läuft über `bracket.py` in diesem Skill:

```bash
python3 "${CLAUDE_SKILL_DIR}/bracket.py" <befehl>
```

`ARENA` meint genau diesen Aufruf. Ist die Variable nicht gesetzt, nimm das Verzeichnis, das Claude Code als Basis dieses Skills nennt. Der Stand liegt in `.arena/<lauf>/arena.json`. Nach `init` findet jeder Befehl den Lauf über `.arena/LATEST`.

## Schritt 1: Größe nennen, und einmal fragen, wenn niemand das Turnier verlangt hat

Lies die Flags aus der Anfrage. Alles andere ist die Aufgabe.

| Flag | Bedeutung |
| --- | --- |
| `--agents N` | N Teilnehmer. Standard 100. |
| `--quick` | 16 Teilnehmer. Der Lauf für den Alltag. |
| `--seed S` | Dieselbe Saat, dieselben Karten, dieselbe Paarung. Standard: zufällig, und festgehalten. |
| `--wave W` | Unter-Agenten pro Welle. Standard 10. Nur anheben, wenn das Limit für gleichzeitige Werkzeugaufrufe angehoben wurde. |

Liegt kein Aufgabentext da, ist die Aufgabe die letzte Bitte in diesem Gespräch, und deine letzte Antwort darauf ist die Fassung, die geschlagen werden soll.

Führ `ARENA plan --agents N` aus, oder `ARENA plan --quick`. Es zeigt Runden, Aufrufe und Wellen.

- **Die Person hat das Turnier verlangt** (`/arena`, „arena“, gegeneinander antreten lassen): sag in einer Zeile, wie groß es wird, zum Beispiel „100 Teilnehmer, 7 Runden, 595 Aufrufe“, und leg los.
- **Der Skill läuft, weil die Antwort nicht getragen hat** („falsch“, „nochmal“, „schlecht“), und das Turnier wurde nicht genannt: frag einmal, bevor etwas ausgegeben wird. Drei Möglichkeiten: das volle Turnier (100 Teilnehmer, 595 Aufrufe), `--quick` (16 Teilnehmer, 91 Aufrufe), oder ein gewöhnlicher neuer Versuch. Wart auf die Antwort.

Die Unter-Agenten schreiben nach `.arena/` im aktuellen Verzeichnis. Ohne Freigabe im Voraus ist das eine Bestätigung pro Datei, bei einem großen Lauf sind das hunderte. Schlag vor dem Entwurf vor, den Lauf mit akzeptierten Änderungen zu fahren. Änder die Einstellung nicht selbst.

## Schritt 2: die Aufgabendatei

Daran hängt das Ergebnis. **Unter-Agenten sehen dieses Gespräch nicht.** Teilnehmer, Angriff und Richter kennen nur die Aufgabendatei. Schreib `.arena/task.md` so, dass sie für sich steht:

- Die Bitte, in den Worten der Person, wo du sie hast.
- Jede Anforderung und Grenze, die irgendwo im Gespräch stand: Zielgruppe, Länge, Form, Ton, Stack, Frist, was bleiben muss.
- Was eine fremde Person braucht: absolute Pfade der wichtigen Dateien, beigelegte Daten, was das Produkt ist, welche Konventionen im Repo gelten.
- Woran „fertig“ zu erkennen ist, falls das gesagt wurde.
- Liegt eine Antwort vor, die nicht getragen hat: was daran gestört hat, in den Worten der Person.

Erfinde keine Anforderungen. Schreib auch nicht deine eigene Vorstellung der richtigen Lösung hinein. Das würde alle Teilnehmer in dieselbe Richtung schieben.

Liegt eine frühere Antwort vor, die nicht getragen hat, schreib sie wortgetreu nach `.arena/baseline.md`.

## Schritt 3: init

```bash
ARENA init --agents N --seed S --task-file .arena/task.md --baseline-file .arena/baseline.md
```

Lass `--baseline-file` weg, wenn nichts zu schlagen ist, und `--seed` weg, wenn die Saat zufällig sein soll. `init` kopiert die Aufgabe in den Lauf, mischt die Karten ohne Doppelte und schreibt `arena.json`.

## Schritt 4: die Schleife

Steuer sie immer mit `ARENA next`. Der Befehl liest den Stand von der Platte und nennt den nächsten Schritt mit dem genauen Aufruf.

Jede Phase mit Unter-Agenten läuft gleich:

1. `ARENA prompts <phase>` schreibt ein Briefing pro Auftrag und listet die offenen Aufträge in Wellen. Die Phasen heißen `spawn`, `attack`, `defend`, `judge` und `final`.
2. Start **eine Welle pro Nachricht**: ein Aufruf des Agenten-Werkzeugs pro Auftrag in dieser Welle. Jeder Aufruf ist:
   - `subagent_type`: `general-purpose`
   - `description`: `arena <auftrag>`
   - `prompt`: `Lies diese Datei und folge ihr genau. Sie ist dein ganzes Briefing.` plus der absolute Pfad aus der Zeile `brief:`
   - `run_in_background`: false, wo das Werkzeug das kann, damit die Welle gemeinsam zurückkommt.
3. Wart, bis jede Antwort dieser Welle da ist, bevor die nächste Welle startet.
4. Nach der letzten Welle wieder `ARENA next`. Fehlt eine Ausgabe, schickt dich derselbe Befehl in dieselbe Phase zurück, und `prompts` listet nur die fehlenden Aufträge. Lass sie einmal nachlaufen. Scheitert ein Auftrag zum zweiten Mal, schreibt das Programm bei Angriff, Verteidigung und Entwurf `KEINE AUSGABE` in die Ausgabedateien (`ARENA check <phase>` zeigt sie) und geht weiter. Ein fehlender Angriff zählt als keiner. Eine fehlende Lösung verliert ihr Duell. Ein Richter, der zweimal scheitert, bekommt einen dritten, frischen Lauf. Entscheide ein Duell nie selbst.

Die Reihenfolge, die `next` vorgibt:

- **spawn**, einmal: jeder Teilnehmer schreibt seine Lösung.
- dann jede Runde: **attack** (zwei pro Duell), **defend** (zwei pro Duell), **judge** (einer pro Duell), `ARENA collect`, `ARENA advance`.
- **final**, einmal, nur wenn eine abgelehnte Antwort vorliegt: ein Richter vergleicht die siegreiche Lösung blind mit ihr. Danach `ARENA collect`.
- `next` meldet `FERTIG`: weiter zu Schritt 5.

Nach jedem `advance` gib der Person eine Zeile, etwa „Runde 2 fertig: noch 25 von 100.“ Sonst nichts. Keine Paarungen, Angriffe, Urteile oder Lösungen in den Chat.

Wellen gibt es, weil höchstens eine begrenzte Zahl von Werkzeugaufrufen gleichzeitig läuft, im Standard zehn. Ein Entwurf mit 100 Teilnehmern sind zehn Wellen, der ganze Lauf 70 Wellen, 71 mit dem letzten Vergleich.

## Schritt 5: das Ergebnis

Führ `ARENA winner` aus und lies nur die Lösungsdatei, deren Pfad dort steht. Das ist die einzige Lösungsdatei, die du im ganzen Lauf liest. Gib der Person:

1. **Die siegreiche Lösung**, vollständig.
2. **Warum sie geblieben ist**: die bestandenen Angriffe aus `winner`, als kurze Liste. Die Karte in einer Zeile (Denkweise, Arbeitsablauf, Haltung).
3. **Runden**: zum Beispiel „7 Runden, 100 Teilnehmer, eine Lösung übrig.“
4. **Gegen die abgelehnte Antwort**, falls es eine gab: die Punkte des Vergleichs, ohne Beschönigung. Liegt die alte Antwort vorn, sag das und zeig beide.
5. Wo der Lauf liegt.

Ändert die Lösung Dateien im Projekt, wende sie nicht an. Frag: anwenden, oder noch ändern?

## Regeln für die Leitung

- Du leitest. Du schreibst keine Wettbewerbslösung, du greifst nicht an, du richtest nicht, und du kürt keinen Sieger. `collect` übernimmt, was in den Urteilen steht. Die Punkte rechnet `bracket.py`. Weicht das Feld `winner` eines Richters von dieser Rechnung ab, gilt die Rechnung. `record` ist nur dazu da, die Buchhaltung zu richten, wenn die Person das ausdrücklich will.
- Jeder Unter-Agent bekommt die Aufgabe über sein Briefing. `prompts` baut es aus der einen Aufgabendatei, für alle wortgleich. Formulier die Aufgabe nicht für einen Agenten um und gib keinem einen zusätzlichen Hinweis.
- Lies während des Laufs keine Lösungen, Angriffe oder Urteile. Es sind hunderte. Der Stand liegt auf der Platte. Du brauchst `next`, `status` und `pairings`.
- Wird der Kontext mitten im Lauf verdichtet, ist nichts verloren. Führ `ARENA status` aus, dann `ARENA next`, und mach weiter.
- Führ jeden `ARENA`-Befehl in dem Verzeichnis aus, in dem `init` lief. Dort liegt `.arena/LATEST`.
- Unter-Agenten schreiben nur unter `.arena/`. Hat einer woanders geschrieben, sag das der Person.
- Sagt die Person Stopp, hör auf. `ARENA status` zeigt, wo der Lauf steht, und `ARENA next` setzt ihn später fort.

## Die Briefings

`prompts` füllt die Platzhalter und schreibt pro Auftrag eine Datei. Was hier steht, ist der Text, den jeder Unter-Agent bekommt. Änder ein einzelnes Briefing nicht.

### Entwurf

```text
Du bist Teilnehmer {{agent}} in einer Arena mit {{n}} Teilnehmern. Alle {{n}} haben dieselbe Aufgabe bekommen, Wort für Wort. Dich unterscheidet nur die Karte unten. Deine Lösung wird angegriffen, überarbeitet und von einem Richter bewertet, bis eine Lösung übrig ist.

=== AUFGABE (für alle gleich) ===
{{task}}
=== ENDE DER AUFGABE ===

{{baseline_note}}

=== DEINE KARTE ===
Denkweise: {{reasoning_name}}. {{reasoning_how}}
Arbeitsablauf: {{workflow_name}}. {{workflow_how}}
Haltung: {{strategy_name}}. {{strategy_how}}
=== ENDE DER KARTE ===

So arbeitest du:
1. Nutze die Karte wirklich. Denke in der Denkweise, geh die Schritte des Arbeitsablaufs der Reihe nach, und lass die Haltung jede Abwägung entscheiden. Eine allgemeine Antwort, über die nur der Name der Karte gesetzt ist, verliert.
2. Erfüll jede Anforderung, die in der Aufgabe steht. Gemessen wird an der Aufgabe, nicht an der Karte.
3. Du kannst niemanden fragen. Wo die Aufgabe offen ist, wähl die tragfähigste Lesart und schreib sie in einen kurzen Abschnitt Annahmen.
4. Rechne mit Angriffen: konkrete Fehler, Gegenbeispiele, übersehene Anforderungen. Schließ diese Lücken, bevor du abgibst.
5. Lege, ändere oder lösche nichts außerhalb von {{arena_dir}}. Lies, worauf die Aufgabe zeigt. Geht es um Code, schreib die Änderungen in die Lösung, als ganze Dateien oder als einheitlichen Diff, und wende sie nicht an. Brauchst du Platz zum Arbeiten, nutze {{arena_dir}}/notiz/{{agent}}/.

Schreib die Lösung nach {{out}}: die Lösung selbst, für die Person, die gefragt hat. Entwürfe und Arbeitsnotizen bleiben draußen. Eine Prüfliste oder eine Abwägung nur dort, wo sie dieser Person beim Benutzen hilft. Nichts über die Arena, die Karte oder deine Nummer.

Wenn die Datei steht, antworte mit genau dieser einen Zeile:
FERTIG {{agent}} <Anzahl der Wörter in der Lösung>
```

### Angriff

```text
Du bist Teilnehmer {{agent}} in Runde {{round}} einer Arena, Duell {{match}}. Deine Gegenseite ist {{target}}. Nur eine Lösung kommt aus diesem Duell. Jetzt greifst du die Lösung der Gegenseite an.

=== AUFGABE (für alle gleich) ===
{{task}}
=== ENDE DER AUFGABE ===

Deine Karte ist die Linse, durch die du Mängel suchst:
Denkweise: {{reasoning_name}}. {{reasoning_how}}
Arbeitsablauf: {{workflow_name}}. {{workflow_how}}
Haltung: {{strategy_name}}. {{strategy_how}}

Lies die Lösung der Gegenseite: {{target_solution}}
Die eigene darfst du zum Vergleich lesen: {{own_solution}}. Greif die andere anhand der Aufgabe an, nicht dafür, dass sie anders ist als deine.

Such die echten Probleme:
- FALSCH: sachliche Fehler, Denkfehler, Fehler im Code, Behauptungen, die nicht stimmen.
- FEHLT: eine Anforderung der Aufgabe, die ausgelassen oder nur halb erfüllt ist. Zitiere die Anforderung.
- BRICHT: eine konkrete Eingabe, ein Fall oder ein Rand, an dem die Lösung scheitert. Gib das Gegenbeispiel an.
- VAGE: eine Stelle, an der die Person nicht handeln kann, ohne zu raten.

Regeln:
- Jeder Angriff ist prüfbar: die genaue Stelle, was daran falsch ist, und warum.
- Kein Lob, keine Zusammenfassung, keine Stilnoten, außer der Stil macht die Lösung unbenutzbar.
- Erfinde keine Anforderungen, die der Aufgabentext nicht stellt. Greif nicht den Ansatz an, sondern das, was er falsch macht.
- Höchstens 7 Angriffe, der stärkste zuerst. Findest du nur zwei echte, schreib zwei.
- Markiere jeden als FATAL (falsch oder für die Aufgabe unbenutzbar), MAJOR (eine echte Lücke) oder MINOR.
- Lege, ändere oder lösche keine Datei außer der hier genannten.

Schreib die Angriffe nach {{out}} in dieser Form:
ANGRIFF 1 [FATAL|MAJOR|MINOR] <eine Zeile Titel>
Stelle: <Zitat oder Ort>
Problem: <was falsch ist, mit dem Gegenbeispiel oder der fehlenden Anforderung>
(und dasselbe für jeden weiteren Angriff)

Wenn die Datei steht, antworte mit genau dieser einen Zeile:
ANGRIFF {{target}} <Anzahl> (<Anzahl FATAL> fatal)
```

### Verteidigung

```text
Du bist Teilnehmer {{agent}} in Runde {{round}} einer Arena, Duell {{match}}. {{attacker}} hat deine Lösung angegriffen. Jetzt antwortest du darauf und überarbeitest die Lösung. Ein Richter vergleicht danach beide überarbeiteten Lösungen, einschließlich dessen, was jeder mit den Angriffen gemacht hat.

=== AUFGABE (für alle gleich) ===
{{task}}
=== ENDE DER AUFGABE ===

Deine Karte. Behalt den Ansatz: seinetwegen bist du noch dabei.
Denkweise: {{reasoning_name}}. {{reasoning_how}}
Arbeitsablauf: {{workflow_name}}. {{workflow_how}}
Haltung: {{strategy_name}}. {{strategy_how}}

Deine aktuelle Lösung: {{own_solution}}
Die Angriffe darauf: {{attacks}}

Tu das:
1. Geh jeden Angriff durch und entscheide ehrlich. EINRAEUMEN, wenn er stimmt, und behebe ihn. HALTEN, wenn er nicht stimmt, und zeig das an der Aufgabe, an der Lösung oder an einer konkreten Prüfung. Ein HALTEN, das nur beteuert, zählt als eingeräumt. Einen echten Mangel einzuräumen und zu beheben ist besser, als ihn zu verteidigen.
2. Schreib die überarbeitete Lösung vollständig und für sich stehend. Jeder eingeräumte Punkt ist darin behoben. Der Richter liest nur diese Datei. Verweise nicht auf eine frühere Fassung. Nichts über die Arena oder die Karte.
3. Behebe, was angegriffen wurde, und das, was die Angriffe nebenbei sichtbar gemacht haben. Fang nicht von vorn an und übernimm nicht die Lösung der Gegenseite.
4. Ist die Angriffsdatei leer oder lautet sie KEINE AUSGABE, gab es keinen Angriff: schreib in die Verteidigung KEINE ANGRIFFE ERHALTEN, und gib die Lösung mit den Verbesserungen ab, die du selbst für nötig hältst.
5. Lege, ändere oder lösche nichts außerhalb von {{arena_dir}}.

Schreib die Antwort auf die Angriffe nach {{defense_out}} in dieser Form:
ANGRIFF 1: EINRAEUMEN|HALTEN. <ein bis drei Sätze>
(ein Eintrag pro Angriff)

Schreib die überarbeitete Lösung nach {{solution_out}}.

Wenn beide Dateien stehen, antworte mit genau dieser einen Zeile:
VERTEIDIGT {{agent}} eingeräumt <Anzahl> gehalten <Anzahl>
```

### Richter

```text
Du bist der Richter von Duell {{match}}, Runde {{round}}, in einer Arena. Zwei Lösungen derselben Aufgabe haben einander angegriffen, dann geantwortet und sich überarbeitet. Bewerte beide nach der Rubrik. Wer weiterkommt, rechnet danach das Turnierprogramm aus deinen Punkten. Dein Feld "winner" ist ein Vorschlag.

=== AUFGABE (für alle gleich) ===
{{task}}
=== ENDE DER AUFGABE ===

Lies zuerst die Rubrik: {{rubric}}

Lösung {{first}}
- überarbeitete Lösung: {{first_solution}}
- erhaltene Angriffe: {{first_attacks}}
- Verteidigung: {{first_defense}}

Lösung {{second}}
- überarbeitete Lösung: {{second_solution}}
- erhaltene Angriffe: {{second_attacks}}
- Verteidigung: {{second_defense}}

So richtest du:
1. Lies beide überarbeiteten Lösungen ganz, bevor du eine bewertest.
2. Prüfe jeden Angriff an der überarbeiteten Lösung und nenn ihn BEHOBEN, GEHALTEN (nur wenn die Erwiderung wirklich stimmt) oder OFFEN. Dass die Verteidigung „behoben“ sagt, ist kein Beleg. Sieh hin.
3. Such auch Mängel, die beide Angriffe übersehen haben.
4. Vergib jedes Kriterium von 0 bis 10 nach den Ankern der Rubrik. Setze fatal nur auf true, wenn du einen Mangel geprüft hast, der die Lösung falsch oder für die Aufgabe unbenutzbar macht.
5. Eine leere Angriffsdatei oder der Text KEINE AUSGABE bedeutet: von dieser Seite kam kein Angriff.
6. Bewerte die Arbeit, nicht das Reden über die Arbeit. Länge ist keine Qualität. Die Karten kennst du nicht und rätst nicht danach.
7. Lege, ändere oder lösche keine Datei außer dem Urteil. Geht es um Code und ein Lauf entscheidet einen Angriff, dann nur unter {{arena_dir}}/notiz/richter-{{match}}/, nie im Projekt der Person.

Schreib dieses JSON, und sonst nichts, nach {{out}}:
{
  "match": "{{match}}",
  "scores": {
    "{{first}}": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false},
    "{{second}}": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false}
  },
  "winner": "{{first}}",
  "reason": "ein Satz: der entscheidende Unterschied",
  "survived": ["jeder Angriff, den der Sieger erhalten und bestanden hat, in wenigen Worten"],
  "standing": {"{{first}}": ["Angriffe, die noch offen sind"], "{{second}}": ["Angriffe, die noch offen sind"]}
}

Wenn die Datei steht, antworte mit genau dieser einen Zeile:
SIEGER <Siegerkennung> <Summe des Siegers>-<Summe der anderen Seite>
```

### Vergleich mit der abgelehnten Antwort

```text
Du bist der letzte Vergleich einer Arena. {{n}} Teilnehmer haben um eine Aufgabe gekämpft, und eine Lösung hat {{rounds}} Runden überstanden. Bevor sie zurückgeht, wird sie mit der Antwort verglichen, die schon abgelehnt wurde. Du erfährst nicht, welche der beiden welche ist. Bewerte, was dasteht. Beide können gewinnen. Wer gewinnt, rechnet danach das Turnierprogramm aus deinen Punkten.

=== AUFGABE ===
{{task}}
=== ENDE DER AUFGABE ===

Lies zuerst die Rubrik: {{rubric}}

Lösung X: {{x_solution}}
Lösung Y: {{y_solution}}

So richtest du:
1. Lies beide ganz, bevor du eine bewertest.
2. Greif beide selbst an: such die stärksten konkreten Mängel, so wie eine gegnerische Fachperson. Die Robustheit bewertet, wie gut jede Lösung diesen Angriffen standhält.
3. Vergib jedes Kriterium von 0 bis 10 nach den Ankern der Rubrik. Setze fatal nur auf true, wenn du einen Mangel geprüft hast, der eine Lösung falsch oder für die Aufgabe unbenutzbar macht.
4. Bewerte die Arbeit, nicht das Reden über die Arbeit. Länge ist keine Qualität.
5. Lege, ändere oder lösche keine Datei außer dem Urteil.

Schreib dieses JSON, und sonst nichts, nach {{out}}:
{
  "scores": {
    "X": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false},
    "Y": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false}
  },
  "winner": "X",
  "reason": "ein Satz: der entscheidende Unterschied",
  "fixed": ["jeder Punkt, den die bessere Lösung richtig hat und die andere falsch, in wenigen Worten"]
}

Wenn die Datei steht, antworte mit genau dieser einen Zeile:
VERGLEICH <X oder Y> <Summe X>-<Summe Y>
```

Liegt eine abgelehnte Antwort vor, setzt der Entwurf an die Stelle `{{baseline_note}}` diesen Hinweis, sonst bleibt die Stelle leer:

Es liegt schon eine abgelehnte Antwort vor, mit ihrem Pfad. Lies sie, damit du die genannten Schwächen nicht wiederholst. Deine Lösung steht für sich und muss sie nicht nachahmen.
