#!/usr/bin/env python3
"""Turnierstand für die Arena. Nur die Standardbibliothek."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
SELF = Path(__file__).resolve()
WEIGHTS = {
    "correctness": 30,
    "completeness": 25,
    "specificity": 15,
    "robustness": 20,
    "clarity": 10,
}
CRITERIA = (
    "correctness",
    "completeness",
    "specificity",
    "robustness",
    "clarity",
)
BLANK = "KEINE AUSGABE\n"
PHASE_NEXT = {"attack": "defend", "defend": "judge", "judge": "collect"}
PHASE_WORD = {
    "spawn": "entwurf",
    "attack": "angriff",
    "defend": "verteidigung",
    "judge": "richter",
    "collect": "wertung",
    "advance": "weiter",
    "final": "vergleich",
    "final-collect": "vergleich",
    "done": "fertig",
}

SPAWN_TEMPLATE = """Du bist Teilnehmer {{agent}} in einer Arena mit {{n}} Teilnehmern. Alle {{n}} haben dieselbe Aufgabe bekommen, Wort für Wort. Dich unterscheidet nur die Karte unten. Deine Lösung wird angegriffen, überarbeitet und von einem Richter bewertet, bis eine Lösung übrig ist.

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
"""

ATTACK_TEMPLATE = """Du bist Teilnehmer {{agent}} in Runde {{round}} einer Arena, Duell {{match}}. Deine Gegenseite ist {{target}}. Nur eine Lösung kommt aus diesem Duell. Jetzt greifst du die Lösung der Gegenseite an.

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
"""

DEFEND_TEMPLATE = """Du bist Teilnehmer {{agent}} in Runde {{round}} einer Arena, Duell {{match}}. {{attacker}} hat deine Lösung angegriffen. Jetzt antwortest du darauf und überarbeitest die Lösung. Ein Richter vergleicht danach beide überarbeiteten Lösungen, einschließlich dessen, was jeder mit den Angriffen gemacht hat.

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
"""

JUDGE_TEMPLATE = """Du bist der Richter von Duell {{match}}, Runde {{round}}, in einer Arena. Zwei Lösungen derselben Aufgabe haben einander angegriffen, dann geantwortet und sich überarbeitet. Bewerte beide nach der Rubrik. Wer weiterkommt, rechnet danach das Turnierprogramm aus deinen Punkten. Dein Feld "winner" ist ein Vorschlag.

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
"""

FINAL_TEMPLATE = """Du bist der letzte Vergleich einer Arena. {{n}} Teilnehmer haben um eine Aufgabe gekämpft, und eine Lösung hat {{rounds}} Runden überstanden. Bevor sie zurückgeht, wird sie mit der Antwort verglichen, die schon abgelehnt wurde. Du erfährst nicht, welche der beiden welche ist. Bewerte, was dasteht. Beide können gewinnen. Wer gewinnt, rechnet danach das Turnierprogramm aus deinen Punkten.

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
"""

TEMPLATES = {
    "spawn": SPAWN_TEMPLATE,
    "attack": ATTACK_TEMPLATE,
    "defend": DEFEND_TEMPLATE,
    "judge": JUDGE_TEMPLATE,
    "final": FINAL_TEMPLATE,
}

BASELINE_NOTE = (
    "Es liegt schon eine abgelehnte Antwort vor: {{baseline}}. "
    "Lies sie, damit du die genannten Schwächen nicht wiederholst. "
    "Deine Lösung steht für sich und muss sie nicht nachahmen."
)


def die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def command(*parts: str) -> str:
    return "python3 " + " ".join([_quote(str(SELF))] + [_quote(p) for p in parts])


def _quote(text: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


def load_catalog() -> dict:
    path = SKILL_DIR / "strategies.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("reasoning", "workflows", "strategies"):
        ids = [item["id"] for item in data[key]]
        if len(ids) != len(set(ids)):
            die(f"Doppelte Id in {key}.")
        if not ids:
            die(f"{key} ist leer.")
    return data


def catalog_index(catalog: dict) -> dict:
    return {
        key: {item["id"]: item for item in catalog[key]}
        for key in ("reasoning", "workflows", "strategies")
    }


def arena_root(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / ".arena"


def run_dir(cwd: Path | None = None) -> Path:
    pointer = arena_root(cwd) / "LATEST"
    if not pointer.is_file():
        die("Kein Lauf. Zuerst init.")
    name = pointer.read_text(encoding="utf-8").strip()
    path = arena_root(cwd) / name
    if not (path / "arena.json").is_file():
        die(f"Lauf nicht gefunden: {path}")
    return path


def read_state(path: Path) -> dict:
    return json.loads((path / "arena.json").read_text(encoding="utf-8"))


def write_state(path: Path, state: dict) -> None:
    (path / "arena.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load(cwd: Path | None = None) -> tuple[dict, Path]:
    path = run_dir(cwd)
    return read_state(path), path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def mix_seed(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def task_text(state: dict, path: Path) -> str:
    raw = (path / state["task"]).read_bytes()
    if sha256_bytes(raw) != state["task_sha256"]:
        die("task.md wurde nach init verändert.")
    return raw.decode("utf-8")


def ceil_div(value: int, unit: int) -> int:
    return (value + unit - 1) // unit


def forecast(agents: int, wave: int) -> list[dict]:
    if agents < 1:
        die("Teilnehmerzahl muss mindestens 1 sein.")
    if wave < 1:
        die("Wellengröße muss mindestens 1 sein.")
    rows = [
        {
            "round": 0,
            "label": "entwurf",
            "alive": agents,
            "matches": None,
            "bye": False,
            "calls": agents,
            "waves": ceil_div(agents, wave),
        }
    ]
    alive = agents
    number = 1
    while alive > 1:
        matches = alive // 2
        bye = alive % 2 == 1
        attack_calls = matches * 2
        waves = (
            ceil_div(attack_calls, wave)
            + ceil_div(attack_calls, wave)
            + ceil_div(matches, wave)
        )
        rows.append(
            {
                "round": number,
                "label": str(number),
                "alive": alive,
                "matches": matches,
                "bye": bye,
                "calls": matches * 5,
                "waves": waves,
            }
        )
        alive = matches + (1 if bye else 0)
        number += 1
    return rows


def format_forecast(agents: int, wave: int, baseline: bool = False) -> str:
    rows = forecast(agents, wave)
    lines = [
        f"{'runde':>8}  {'dabei':>5}  {'duelle':>6}  {'freilos':>7}  {'aufrufe':>7}  {'wellen':>6}"
    ]
    for row in rows:
        matches = "-" if row["matches"] is None else str(row["matches"])
        bye = "ja" if row["bye"] else "-"
        lines.append(
            f"{row['label']:>8}  {row['alive']:5d}  {matches:>6}  {bye:>7}  {row['calls']:7d}  {row['waves']:6d}"
        )
    calls = sum(row["calls"] for row in rows) + (1 if baseline else 0)
    waves = sum(row["waves"] for row in rows) + (1 if baseline else 0)
    lines.append(f"{'gesamt':>8}  {'':5}  {'':6}  {'':7}  {calls:7d}  {waves:6d}")
    alive = agents
    sequence = [str(alive)]
    while alive > 1:
        alive = alive // 2 + alive % 2
        sequence.append(str(alive))
    lines.append("")
    lines.append("dabei je runde: " + " -> ".join(sequence))
    if baseline:
        lines.append("Mit einer abgelehnten Antwort kommt ein Vergleich dazu.")
    return "\n".join(lines)


def quotas(ids: list[str], count: int, rng: random.Random) -> dict[str, int]:
    order = ids[:]
    rng.shuffle(order)
    base, extra = divmod(count, len(ids))
    return {item: base + (1 if index < extra else 0) for index, item in enumerate(order)}


def realize_edges(
    workflow_quota: dict[str, int],
    strategy_quota: dict[str, int],
    rng: random.Random,
) -> list[tuple[str, str]] | None:
    remaining = dict(strategy_quota)
    edges: list[tuple[str, str]] = []
    workflows = sorted(workflow_quota, key=lambda item: (-workflow_quota[item], rng.random()))
    for workflow in workflows:
        need = workflow_quota[workflow]
        choices = sorted(strategy_quota, key=lambda item: (-remaining[item], rng.random()))
        taken = 0
        for strategy in choices:
            if taken >= need:
                break
            if remaining[strategy] <= 0:
                continue
            edges.append((workflow, strategy))
            remaining[strategy] -= 1
            taken += 1
        if taken != need:
            return None
    if any(value != 0 for value in remaining.values()):
        return None
    return edges


def color_edges(
    edges: list[tuple[str, str]],
    reasoning_quota: dict[str, int],
    rng: random.Random,
) -> dict[tuple[str, str], str] | None:
    colors = list(reasoning_quota)
    used_workflow: dict[str, set[str]] = defaultdict(set)
    used_strategy: dict[str, set[str]] = defaultdict(set)
    size: Counter[str] = Counter()
    order = edges[:]
    rng.shuffle(order)
    assigned: dict[tuple[str, str], str] = {}
    for workflow, strategy in order:
        options = [
            color
            for color in colors
            if size[color] < reasoning_quota[color]
            and color not in used_workflow[workflow]
            and color not in used_strategy[strategy]
        ]
        if not options:
            return None
        options.sort(key=lambda color: (-(reasoning_quota[color] - size[color]), rng.random()))
        chosen = options[0]
        assigned[(workflow, strategy)] = chosen
        used_workflow[workflow].add(chosen)
        used_strategy[strategy].add(chosen)
        size[chosen] += 1
    if any(size[color] != reasoning_quota[color] for color in colors):
        return None
    return assigned


def deal_strict(
    rng: random.Random,
    count: int,
    reasoning: list[str],
    workflows: list[str],
    strategies: list[str],
) -> list[dict] | None:
    for _ in range(250):
        reasoning_quota = quotas(reasoning, count, rng)
        workflow_quota = quotas(workflows, count, rng)
        strategy_quota = quotas(strategies, count, rng)
        edges = realize_edges(workflow_quota, strategy_quota, rng)
        if edges is None or len(edges) != count:
            continue
        coloring = color_edges(edges, reasoning_quota, rng)
        if coloring is None:
            continue
        cards = [
            {"reasoning": color, "workflow": workflow, "strategy": strategy}
            for (workflow, strategy), color in coloring.items()
        ]
        if _cards_ok(cards, reasoning, workflows, strategies, count, strict=True):
            return cards
    return None


def deal_loose(
    rng: random.Random,
    count: int,
    reasoning: list[str],
    workflows: list[str],
    strategies: list[str],
) -> list[dict]:
    for _ in range(200):
        reasoning_quota = quotas(reasoning, count, rng)
        workflow_quota = quotas(workflows, count, rng)
        strategy_quota = quotas(strategies, count, rng)
        reasons = [item for item, qty in reasoning_quota.items() for _ in range(qty)]
        works = [item for item, qty in workflow_quota.items() for _ in range(qty)]
        holds = [item for item, qty in strategy_quota.items() for _ in range(qty)]
        rng.shuffle(reasons)
        rng.shuffle(works)
        rng.shuffle(holds)
        used: set[tuple[str, str, str]] = set()
        cards: list[dict] = []
        stuck = False
        for index in range(count):
            triple = (reasons[index], works[index], holds[index])
            if triple in used:
                swapped = False
                for other in range(index + 1, count):
                    candidate = (reasons[index], works[index], holds[other])
                    partner = (reasons[other], works[other], holds[index])
                    if candidate not in used and partner not in used:
                        holds[index], holds[other] = holds[other], holds[index]
                        triple = candidate
                        swapped = True
                        break
                if not swapped:
                    stuck = True
                    break
            used.add(triple)
            cards.append(
                {"reasoning": triple[0], "workflow": triple[1], "strategy": triple[2]}
            )
        if not stuck and _cards_ok(cards, reasoning, workflows, strategies, count, strict=False):
            return cards
    die("Die Karten konnten nicht gemischt werden.")
    raise AssertionError


def _cards_ok(
    cards: list[dict],
    reasoning: list[str],
    workflows: list[str],
    strategies: list[str],
    count: int,
    strict: bool,
) -> bool:
    if len(cards) != count:
        return False
    triples = [(card["reasoning"], card["workflow"], card["strategy"]) for card in cards]
    if len(set(triples)) != len(triples):
        return False
    for axis, ids in (
        ("reasoning", reasoning),
        ("workflow", workflows),
        ("strategy", strategies),
    ):
        tally = Counter(card[axis] for card in cards)
        values = [tally[item] for item in ids]
        if max(values) - min(values) > 1 or sum(values) != count:
            return False
    if strict:
        for left in range(len(triples)):
            for right in range(left + 1, len(triples)):
                shared = sum(a == b for a, b in zip(triples[left], triples[right]))
                if shared >= 2:
                    return False
    return True


def deal_cards(rng: random.Random, count: int, catalog: dict) -> list[dict]:
    reasoning = [item["id"] for item in catalog["reasoning"]]
    workflows = [item["id"] for item in catalog["workflows"]]
    strategies = [item["id"] for item in catalog["strategies"]]
    room = len(reasoning) * len(workflows) * len(strategies)
    if count > room:
        die(f"Höchstens {room} verschiedene Karten, verlangt sind {count}.")
    pair_room = min(len(reasoning) * len(workflows), len(reasoning) * len(strategies), len(workflows) * len(strategies))
    if count <= pair_room:
        strict = deal_strict(rng, count, reasoning, workflows, strategies)
        if strict is not None:
            return strict
        if count <= 100:
            die("Die Karten konnten nicht so gemischt werden, dass zwei höchstens ein Merkmal teilen.")
    return deal_loose(rng, count, reasoning, workflows, strategies)


def agent_id(index: int, count: int) -> str:
    width = max(3, len(str(count)))
    return f"a{index:0{width}d}"


def choose_pairs(
    alive: list[str],
    meta: dict,
    rng: random.Random,
) -> tuple[list[tuple[str, str]], str | None]:
    pool = list(alive)
    bye = None
    if len(pool) % 2 == 1:
        lowest = min(meta[item]["byes"] for item in pool)
        bye_pool = [item for item in pool if meta[item]["byes"] == lowest]
        rng.shuffle(bye_pool)
        bye = bye_pool[0]
        pool = [item for item in pool if item != bye]
    groups: dict[str, list[str]] = defaultdict(list)
    for item in pool:
        groups[meta[item]["card"]["reasoning"]].append(item)
    for group in groups.values():
        rng.shuffle(group)
    remaining = dict(groups)
    matches: list[tuple[str, str]] = []
    while remaining:
        group_ids = list(remaining)
        rng.shuffle(group_ids)
        longest = max(len(remaining[key]) for key in group_ids)
        reasoning_id = next(key for key in group_ids if len(remaining[key]) == longest)
        left = remaining[reasoning_id].pop()
        if not remaining[reasoning_id]:
            del remaining[reasoning_id]
        others = [key for key in remaining if key != reasoning_id]
        if others:
            rng.shuffle(others)
            longest = max(len(remaining[key]) for key in others)
            other_id = next(key for key in others if len(remaining[key]) == longest)
            right = remaining[other_id].pop()
            if not remaining[other_id]:
                del remaining[other_id]
        else:
            right = remaining[reasoning_id].pop()
            if not remaining[reasoning_id]:
                del remaining[reasoning_id]
        matches.append((left, right))
    return matches, bye


def weighted(score: dict) -> float:
    return sum(float(score[key]) * WEIGHTS[key] for key in CRITERIA) / 10


def standing_count(standing: dict | None, agent: str) -> int:
    if not standing:
        return 0
    items = standing.get(agent) or []
    return len(items)


def decide_winner(
    left: str,
    right: str,
    scores: dict,
    standing: dict | None = None,
) -> tuple[str, str]:
    left_score = scores[left]
    right_score = scores[right]
    left_fatal = bool(left_score.get("fatal"))
    right_fatal = bool(right_score.get("fatal"))
    if left_fatal != right_fatal:
        winner = right if left_fatal else left
        return winner, "Eine fatale Lösung scheidet aus."
    left_total = weighted(left_score)
    right_total = weighted(right_score)
    if left_total != right_total:
        winner = left if left_total > right_total else right
        return winner, "Die höhere gewichtete Summe geht weiter."
    left_open = standing_count(standing, left)
    right_open = standing_count(standing, right)
    if left_open != right_open:
        winner = left if left_open < right_open else right
        return winner, "Weniger offene Angriffe entscheiden."
    if float(left_score["correctness"]) != float(right_score["correctness"]):
        winner = left if float(left_score["correctness"]) > float(right_score["correctness"]) else right
        return winner, "Die höhere Richtigkeit entscheidet."
    winner = min(left, right)
    return winner, "Gleichstand. Die kleinere Kennung geht weiter."


def parse_score(raw: dict) -> dict:
    score = {}
    for key in CRITERIA:
        if key not in raw:
            raise ValueError(f"Punkt fehlt: {key}")
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Ungültige Punktzahl für {key}.")
        if value < 0 or value > 10:
            raise ValueError(f"{key} liegt außerhalb von 0 bis 10.")
        score[key] = value
    score["fatal"] = bool(raw.get("fatal", False))
    return score


def load_json_loose(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Urteil ist kein Objekt.")
    return payload


def blank_file(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return True
    return path.read_text(encoding="utf-8").strip() == "KEINE AUSGABE"


def ready(path: Path, outputs: list[str]) -> bool:
    return all((path / item).is_file() and (path / item).stat().st_size > 0 for item in outputs)


def job_done(state: dict, run: Path, job: dict) -> bool:
    if job.get("kind") == "judge" and job.get("match"):
        for rnd in state["rounds"]:
            for match in rnd["matches"]:
                if match["id"] == job["match"] and match.get("collected"):
                    return True
    return ready(run, job["outputs"])


def attempt_limit(kind: str) -> int:
    return 3 if kind in ("judge", "final") else 2


def current_round(state: dict) -> dict | None:
    if not state["rounds"]:
        return None
    return state["rounds"][-1]


def match_paths(round_number: int, match_id: str, agent: str) -> dict[str, str]:
    folder = f"rounds/r{round_number}/{match_id.split('-')[-1]}"
    return {
        "attack": f"{folder}/attack-{agent}.md",
        "defense": f"{folder}/defense-{agent}.md",
        "solution": f"{folder}/solution-{agent}.md",
        "verdict": f"{folder}/verdict.json",
    }


def build_jobs(state: dict) -> list[dict]:
    phase = state["phase"]
    if phase == "spawn":
        jobs = []
        for agent in state["order"]:
            jobs.append(
                {
                    "id": f"spawn-{agent}",
                    "kind": "spawn",
                    "agent": agent,
                    "outputs": [state["competitors"][agent]["solution"]],
                }
            )
        return jobs
    if phase in ("attack", "defend", "judge", "collect", "advance"):
        rnd = current_round(state)
        if rnd is None:
            return []
        jobs = []
        for match in rnd["matches"]:
            number = rnd["round"]
            paths_a = match_paths(number, match["id"], match["a"])
            paths_b = match_paths(number, match["id"], match["b"])
            if phase == "attack":
                jobs.append(
                    {
                        "id": f"{match['id']}-attack-{match['a']}",
                        "kind": "attack",
                        "agent": match["a"],
                        "target": match["b"],
                        "match": match["id"],
                        "outputs": [paths_a["attack"]],
                    }
                )
                jobs.append(
                    {
                        "id": f"{match['id']}-attack-{match['b']}",
                        "kind": "attack",
                        "agent": match["b"],
                        "target": match["a"],
                        "match": match["id"],
                        "outputs": [paths_b["attack"]],
                    }
                )
            elif phase == "defend":
                for agent, other, paths, other_paths in (
                    (match["a"], match["b"], paths_a, paths_b),
                    (match["b"], match["a"], paths_b, paths_a),
                ):
                    jobs.append(
                        {
                            "id": f"{match['id']}-defend-{agent}",
                            "kind": "defend",
                            "agent": agent,
                            "attacker": other,
                            "match": match["id"],
                            "attacks": other_paths["attack"],
                            "outputs": [paths["defense"], paths["solution"]],
                        }
                    )
            elif phase in ("judge", "collect", "advance"):
                jobs.append(
                    {
                        "id": f"{match['id']}-judge",
                        "kind": "judge",
                        "match": match["id"],
                        "agents": [match["a"], match["b"]],
                        "outputs": [paths_a["verdict"]],
                    }
                )
        return jobs
    if phase in ("final", "final-collect"):
        return [
            {
                "id": "final-judge",
                "kind": "final",
                "outputs": ["final/verdict.json"],
            }
        ]
    return []


def card_fields(agent: str, state: dict, index: dict) -> dict[str, str]:
    card = state["competitors"][agent]["card"]
    reasoning = index["reasoning"][card["reasoning"]]
    workflow = index["workflows"][card["workflow"]]
    strategy = index["strategies"][card["strategy"]]
    return {
        "reasoning_name": reasoning["name"],
        "reasoning_how": reasoning["how"],
        "workflow_name": workflow["name"],
        "workflow_how": workflow["how"],
        "strategy_name": strategy["name"],
        "strategy_how": strategy["how"],
    }


def fill(template: str, mapping: dict[str, str]) -> str:
    sentinel = "\x00TASK\x00"
    rendered = template.replace("{{task}}", sentinel)
    for key, value in mapping.items():
        if key == "task":
            continue
        rendered = rendered.replace("{{" + key + "}}", value)
    rendered = rendered.replace(sentinel, mapping["task"])
    leftover = re.findall(r"\{\{[a-z0-9_]+\}\}", rendered)
    if leftover:
        die("Offene Platzhalter: " + ", ".join(leftover))
    return rendered


def write_brief(job: dict, state: dict, run: Path, index: dict) -> None:
    task = task_text(state, run)
    arena = str(run.resolve())
    common = {
        "task": task,
        "n": str(state["agents_n"]),
        "arena_dir": arena,
        "round": str(state["round"]),
    }
    kind = job["kind"]
    if kind == "spawn":
        agent = job["agent"]
        note = ""
        if state.get("baseline"):
            note = BASELINE_NOTE.replace("{{baseline}}", str((run / state["baseline"]).resolve()))
        mapping = {
            **common,
            **card_fields(agent, state, index),
            "agent": agent,
            "baseline_note": note,
            "out": str((run / job["outputs"][0]).resolve()),
        }
        text = fill(TEMPLATES["spawn"], mapping)
    elif kind == "attack":
        agent = job["agent"]
        rnd = current_round(state)
        assert rnd is not None
        mapping = {
            **common,
            **card_fields(agent, state, index),
            "agent": agent,
            "target": job["target"],
            "match": job["match"],
            "target_solution": str((run / state["competitors"][job["target"]]["solution"]).resolve()),
            "own_solution": str((run / state["competitors"][agent]["solution"]).resolve()),
            "out": str((run / job["outputs"][0]).resolve()),
        }
        text = fill(TEMPLATES["attack"], mapping)
    elif kind == "defend":
        agent = job["agent"]
        paths = match_paths(state["round"], job["match"], agent)
        mapping = {
            **common,
            **card_fields(agent, state, index),
            "agent": agent,
            "attacker": job["attacker"],
            "match": job["match"],
            "own_solution": str((run / state["competitors"][agent]["solution"]).resolve()),
            "attacks": str((run / job["attacks"]).resolve()),
            "defense_out": str((run / paths["defense"]).resolve()),
            "solution_out": str((run / paths["solution"]).resolve()),
        }
        text = fill(TEMPLATES["defend"], mapping)
    elif kind == "judge":
        rnd = current_round(state)
        assert rnd is not None
        match = next(item for item in rnd["matches"] if item["id"] == job["match"])
        first, second = match["a"], match["b"]
        first_paths = match_paths(rnd["round"], match["id"], first)
        second_paths = match_paths(rnd["round"], match["id"], second)
        mapping = {
            **common,
            "match": match["id"],
            "rubric": str((run / state["rubric"]).resolve()),
            "first": first,
            "second": second,
            "first_solution": str((run / first_paths["solution"]).resolve()),
            "first_attacks": str((run / first_paths["attack"]).resolve()),
            "first_defense": str((run / first_paths["defense"]).resolve()),
            "second_solution": str((run / second_paths["solution"]).resolve()),
            "second_attacks": str((run / second_paths["attack"]).resolve()),
            "second_defense": str((run / second_paths["defense"]).resolve()),
            "out": str((run / job["outputs"][0]).resolve()),
        }
        text = fill(TEMPLATES["judge"], mapping)
    elif kind == "final":
        mapping = {
            **common,
            "rounds": str(len(state["rounds"])),
            "rubric": str((run / state["rubric"]).resolve()),
            "x_solution": str((run / "final" / "x.md").resolve()),
            "y_solution": str((run / "final" / "y.md").resolve()),
            "out": str((run / "final" / "verdict.json").resolve()),
        }
        text = fill(TEMPLATES["final"], mapping)
    else:
        die(f"Unbekannte Aufgabe: {kind}")
        raise AssertionError
    for relative in job["outputs"]:
        (run / relative).parent.mkdir(parents=True, exist_ok=True)
    destination = run / "briefs" / f"{job['id']}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    job["brief"] = str(destination.relative_to(run))


def place_blank(run: Path, relative: str) -> None:
    target = run / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.stat().st_size == 0:
        target.write_text(BLANK, encoding="utf-8")


def open_round(state: dict) -> None:
    alive = [agent for agent in state["order"] if state["competitors"][agent]["alive"]]
    rng = random.Random(mix_seed(state["seed"], state["round"], "pair"))
    pairs, bye = choose_pairs(alive, state["competitors"], rng)
    matches = []
    for index, (left, right) in enumerate(pairs, start=1):
        matches.append(
            {
                "id": f"r{state['round']}-m{index:02d}",
                "a": left,
                "b": right,
                "winner": None,
                "reason": None,
                "judge_winner": None,
                "judge_reason": None,
                "override": False,
                "scores": None,
                "standing": None,
                "survived": [],
                "collected": False,
                "manual": False,
            }
        )
    if bye:
        state["competitors"][bye]["byes"] += 1
    state["rounds"].append({"round": state["round"], "bye": bye, "matches": matches})


def copy_revised(state: dict, run: Path) -> None:
    rnd = current_round(state)
    if rnd is None:
        return
    for match in rnd["matches"]:
        for agent in (match["a"], match["b"]):
            source = run / match_paths(rnd["round"], match["id"], agent)["solution"]
            if source.is_file():
                target = run / state["competitors"][agent]["solution"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)


def alive_ids(state: dict) -> list[str]:
    return [agent for agent in state["order"] if state["competitors"][agent]["alive"]]


def enter_after_spawn(state: dict, run: Path) -> None:
    alive = alive_ids(state)
    if len(alive) <= 1:
        enter_finish(state, run)
        return
    state["round"] = 1
    open_round(state)
    state["phase"] = "attack"


def enter_finish(state: dict, run: Path) -> None:
    if state.get("baseline") and not (state.get("final") or {}).get("collected"):
        prepare_final(state, run)
        state["phase"] = "final"
        return
    state["phase"] = "done"


def prepare_final(state: dict, run: Path) -> None:
    champion = alive_ids(state)[0]
    rng = random.Random(mix_seed(state["seed"], "final"))
    champion_first = rng.random() < 0.5
    solution = (run / state["competitors"][champion]["solution"]).read_bytes()
    baseline = (run / state["baseline"]).read_bytes()
    if sha256_bytes(baseline) != state["baseline_sha256"]:
        die("baseline.md wurde nach init verändert.")
    final_dir = run / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    if champion_first:
        (final_dir / "x.md").write_bytes(solution)
        (final_dir / "y.md").write_bytes(baseline)
        mapping = {"X": "champion", "Y": "baseline"}
    else:
        (final_dir / "x.md").write_bytes(baseline)
        (final_dir / "y.md").write_bytes(solution)
        mapping = {"X": "baseline", "Y": "champion"}
    state["final"] = {
        "champion": champion,
        "map": mapping,
        "collected": False,
        "winner_side": None,
        "winner_slot": None,
        "reason": None,
        "scores": None,
        "fixed": [],
        "judge_winner": None,
        "override": False,
    }


def settle(state: dict, run: Path, jobs: list[dict]) -> str:
    for job in jobs:
        if ready(run, job["outputs"]):
            continue
        tries = state["attempts"].get(job["id"], 0)
        if tries >= attempt_limit(job["kind"]) and job["kind"] not in ("judge", "final"):
            for relative in job["outputs"]:
                place_blank(run, relative)
    pending = [job for job in jobs if not job_done(state, run, job)]
    if not pending:
        return "ready"
    blocked = []
    waiting = []
    for job in pending:
        tries = state["attempts"].get(job["id"], 0)
        if tries >= attempt_limit(job["kind"]):
            blocked.append(job)
        else:
            waiting.append(job)
    if waiting:
        phase = state["phase"]
        print(f"Phase: {PHASE_WORD.get(phase, phase)}")
        print(f"Offen: {len(waiting)}")
        print("BEFEHL: " + command("prompts", phase if phase != "final-collect" else "final"))
        return "wait"
    for job in blocked:
        if job["kind"] == "judge":
            agents = " oder ".join(job.get("agents") or [])
            print(
                "Richter ohne Ausgabe nach drei Versuchen. "
                f"Trag das Duell von Hand ein: {command('record', job['match'], agents.split(' oder ')[0], '--reason', 'ohne Richter')}"
            )
        else:
            print("Vergleich ohne Ausgabe nach drei Versuchen. Ein weiterer prompts-Lauf ist nötig, oder record.")
    return "blocked"


def chunk(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def cmd_plan(args: argparse.Namespace) -> None:
    agents = 16 if args.quick else args.agents
    print(format_forecast(agents, args.wave, baseline=args.baseline))


def cmd_init(args: argparse.Namespace) -> None:
    agents = 16 if args.quick else args.agents
    wave = args.wave
    if agents < 1 or wave < 1:
        die("Teilnehmer und Wellengröße müssen mindestens 1 sein.")
    task_path = Path(args.task_file)
    if not task_path.is_file():
        die(f"Aufgabendatei fehlt: {task_path}")
    baseline_path = Path(args.baseline_file) if args.baseline_file else None
    if baseline_path is not None and not baseline_path.is_file():
        die(f"Baseline fehlt: {baseline_path}")
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(0, 2**31)
    catalog = load_catalog()
    cards = deal_cards(random.Random(mix_seed(seed, "deal")), agents, catalog)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    root = arena_root()
    root.mkdir(parents=True, exist_ok=True)
    run_id = f"{stamp}-s{seed}"
    suffix = 2
    while (root / run_id).exists():
        run_id = f"{stamp}-s{seed}-{suffix}"
        suffix += 1
    run = root / run_id
    run.mkdir()
    task_bytes = task_path.read_bytes()
    (run / "task.md").write_bytes(task_bytes)
    baseline_name = None
    baseline_hash = None
    if baseline_path is not None:
        baseline_bytes = baseline_path.read_bytes()
        (run / "baseline.md").write_bytes(baseline_bytes)
        baseline_name = "baseline.md"
        baseline_hash = sha256_bytes(baseline_bytes)
    shutil.copyfile(SKILL_DIR / "rubric.md", run / "rubric.md")
    order = []
    competitors = {}
    for index, card in enumerate(cards, start=1):
        aid = agent_id(index, agents)
        order.append(aid)
        folder = run / "agents" / aid
        folder.mkdir(parents=True)
        (folder / "card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        competitors[aid] = {
            "card": card,
            "alive": True,
            "byes": 0,
            "solution": f"agents/{aid}/solution.md",
            "survived": [],
        }
    state = {
        "version": 1,
        "id": run_id,
        "seed": seed,
        "agents_n": agents,
        "wave": wave,
        "phase": "spawn",
        "round": 0,
        "task": "task.md",
        "task_sha256": sha256_bytes(task_bytes),
        "baseline": baseline_name,
        "baseline_sha256": baseline_hash,
        "rubric": "rubric.md",
        "order": order,
        "competitors": competitors,
        "rounds": [],
        "attempts": {},
        "final": None,
    }
    write_state(run, state)
    (root / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    rows = forecast(agents, wave)
    calls = sum(row["calls"] for row in rows) + (1 if baseline_name else 0)
    rounds = max(row["round"] for row in rows)
    print(f"Lauf: {run}")
    print(f"Seed: {seed}")
    print(f"{agents} Teilnehmer, {rounds} Runden, {calls} Aufrufe.")
    print("BEFEHL: " + command("next"))


def cmd_prompts(args: argparse.Namespace) -> None:
    state, run = load()
    phase = args.phase
    expected = "final" if state["phase"] == "final" else state["phase"]
    if phase != expected:
        die(f"Jetzt ist Phase {state['phase']}. Erwartet wird prompts {expected}.")
    if phase == "final":
        state["phase"] = "final"
    jobs = build_jobs(state)
    missing = [job for job in jobs if not job_done(state, run, job)]
    if not missing:
        print("Nichts offen.")
        print("BEFEHL: " + command("next"))
        return
    index = catalog_index(load_catalog())
    for job in missing:
        state["attempts"][job["id"]] = state["attempts"].get(job["id"], 0) + 1
        write_brief(job, state, run, index)
    waves = chunk(missing, state["wave"])
    manifest = []
    for wave in waves:
        manifest.append(
            [
                {
                    "id": job["id"],
                    "kind": job["kind"],
                    "brief": job["brief"],
                    "outputs": job["outputs"],
                    "agent": job.get("agent"),
                    "agents": job.get("agents"),
                    "match": job.get("match"),
                    "attempt": state["attempts"][job["id"]],
                }
                for job in wave
            ]
        )
    (run / "jobs.json").write_text(
        json.dumps({"phase": phase, "waves": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_state(run, state)
    print(f"Phase: {PHASE_WORD.get(phase, phase)}")
    print(f"Offen: {len(missing)}")
    print(f"Wellen: {len(waves)}")
    for number, wave in enumerate(manifest, start=1):
        print(f"Welle {number}")
        for job in wave:
            outputs = ", ".join(str((run / item).resolve()) for item in job["outputs"])
            print(f"- {job['id']}")
            print(f"  brief: {(run / job['brief']).resolve()}")
            print(f"  ausgabe: {outputs}")


def cmd_next(_: argparse.Namespace) -> None:
    state, run = load()
    for _ in range(12):
        phase = state["phase"]
        if phase == "done":
            print("FERTIG")
            print("BEFEHL: " + command("winner"))
            write_state(run, state)
            return
        if phase in ("collect", "final-collect"):
            print(f"Phase: {PHASE_WORD[phase]}")
            print("BEFEHL: " + command("collect"))
            write_state(run, state)
            return
        if phase == "advance":
            print("Phase: weiter")
            print("BEFEHL: " + command("advance"))
            write_state(run, state)
            return
        jobs = build_jobs(state)
        outcome = settle(state, run, jobs)
        write_state(run, state)
        if outcome != "ready":
            return
        if phase == "spawn":
            enter_after_spawn(state, run)
            write_state(run, state)
            continue
        if phase == "defend":
            copy_revised(state, run)
        if phase in PHASE_NEXT:
            state["phase"] = PHASE_NEXT[phase]
            write_state(run, state)
            continue
        if phase == "final":
            state["phase"] = "final-collect"
            write_state(run, state)
            print("Phase: vergleich")
            print("BEFEHL: " + command("collect"))
            return
        die(f"Phase ohne Übergang: {phase}")
    die("Zu viele Übergänge in einem next.")


def find_match(state: dict, match_id: str) -> tuple[dict, dict]:
    for rnd in state["rounds"]:
        for match in rnd["matches"]:
            if match["id"] == match_id:
                return rnd, match
    die(f"Duell nicht gefunden: {match_id}")
    raise AssertionError


def apply_match(state: dict, run: Path, rnd: dict, match: dict) -> None:
    if match.get("manual") and match.get("collected") and match.get("winner"):
        return
    verdict_path = run / match_paths(rnd["round"], match["id"], match["a"])["verdict"]
    if blank_file(verdict_path):
        die(f"Urteil fehlt oder ist leer: {match['id']}")
    try:
        payload = load_json_loose(verdict_path.read_text(encoding="utf-8"))
        scores = {
            match["a"]: parse_score(payload["scores"][match["a"]]),
            match["b"]: parse_score(payload["scores"][match["b"]]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        die(f"Urteil von {match['id']} ist nicht lesbar: {exc}")
        raise AssertionError
    standing = payload.get("standing") if isinstance(payload.get("standing"), dict) else {}
    left_bad = blank_file(run / match_paths(rnd["round"], match["id"], match["a"])["solution"])
    right_bad = blank_file(run / match_paths(rnd["round"], match["id"], match["b"])["solution"])
    if left_bad or right_bad:
        if left_bad and right_bad:
            winner, reason = min(match["a"], match["b"]), "Beide Seiten ohne Lösung."
        elif left_bad:
            winner, reason = match["b"], "Keine Lösung auf der einen Seite."
        else:
            winner, reason = match["a"], "Keine Lösung auf der einen Seite."
        override = True
    else:
        winner, reason = decide_winner(match["a"], match["b"], scores, standing)
        judge_winner = payload.get("winner")
        override = judge_winner != winner
        if not override and payload.get("reason"):
            reason = str(payload["reason"])
    match["scores"] = scores
    match["standing"] = {agent: list(standing.get(agent) or []) for agent in (match["a"], match["b"])}
    match["winner"] = winner
    match["reason"] = reason
    match["judge_winner"] = payload.get("winner")
    match["judge_reason"] = payload.get("reason")
    match["override"] = override
    match["collected"] = True
    if override:
        survived = [f"{match['id']}: durch die Punktrechnung entschieden"]
    else:
        survived = [str(item) for item in (payload.get("survived") or [])]
    match["survived"] = survived
    state["competitors"][winner]["survived"].extend(survived)


def cmd_collect(_: argparse.Namespace) -> None:
    state, run = load()
    if state["phase"] == "final-collect":
        collect_final(state, run)
        return
    if state["phase"] != "collect":
        die(f"Sammeln passt nicht zur Phase {state['phase']}.")
    rnd = current_round(state)
    if rnd is None:
        die("Keine Runde zum Sammeln.")
    for match in rnd["matches"]:
        apply_match(state, run, rnd, match)
    state["phase"] = "advance"
    write_state(run, state)
    print(f"Runde {rnd['round']} gewertet: {len(rnd['matches'])} Duelle.")
    print("BEFEHL: " + command("advance"))


def collect_final(state: dict, run: Path) -> None:
    final = state.get("final") or {}
    verdict_path = run / "final" / "verdict.json"
    if blank_file(verdict_path):
        die("Vergleichsurteil fehlt.")
    try:
        payload = load_json_loose(verdict_path.read_text(encoding="utf-8"))
        scores = {"X": parse_score(payload["scores"]["X"]), "Y": parse_score(payload["scores"]["Y"])}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        die(f"Vergleichsurteil ist nicht lesbar: {exc}")
        raise AssertionError
    winner, reason = decide_winner("X", "Y", scores, None)
    if payload.get("reason") and payload.get("winner") == winner:
        reason = str(payload["reason"])
    final["scores"] = scores
    final["winner_slot"] = winner
    final["winner_side"] = final["map"][winner]
    final["reason"] = reason
    final["fixed"] = [str(item) for item in (payload.get("fixed") or [])]
    final["judge_winner"] = payload.get("winner")
    final["override"] = payload.get("winner") != winner
    final["collected"] = True
    state["final"] = final
    state["phase"] = "done"
    write_state(run, state)
    side = "die neue Lösung" if final["winner_side"] == "champion" else "die abgelehnte Antwort"
    print(f"Vergleich gewertet. Vorn liegt {side}.")
    print("BEFEHL: " + command("winner"))


def cmd_record(args: argparse.Namespace) -> None:
    state, run = load()
    rnd, match = find_match(state, args.match)
    if args.agent not in (match["a"], match["b"]):
        die(f"{args.agent} spielt nicht in {args.match}.")
    match["winner"] = args.agent
    match["reason"] = args.reason or "Von Hand eingetragen."
    match["manual"] = True
    match["collected"] = True
    match["override"] = True
    match["survived"] = [match["reason"]]
    if rnd == current_round(state) and all(item["collected"] for item in rnd["matches"]):
        if state["phase"] in ("judge", "collect"):
            state["phase"] = "advance"
    write_state(run, state)
    print(f"{args.match}: {args.agent} eingetragen.")
    print("BEFEHL: " + command("next"))


def cmd_advance(_: argparse.Namespace) -> None:
    state, run = load()
    if state["phase"] != "advance":
        die(f"Weiter geht erst nach dem Sammeln. Jetzt: {state['phase']}.")
    rnd = current_round(state)
    if rnd is None:
        die("Keine Runde.")
    for match in rnd["matches"]:
        if not match.get("winner"):
            die(f"Duell ohne Sieger: {match['id']}")
        loser = match["b"] if match["winner"] == match["a"] else match["a"]
        state["competitors"][loser]["alive"] = False
        state["competitors"][match["winner"]]["alive"] = True
    alive = alive_ids(state)
    total = state["agents_n"]
    if len(alive) == 1:
        enter_finish(state, run)
        write_state(run, state)
        print(f"Runde {rnd['round']} fertig: noch 1 von {total}.")
        print("BEFEHL: " + command("next"))
        return
    state["round"] = rnd["round"] + 1
    open_round(state)
    state["phase"] = "attack"
    write_state(run, state)
    print(f"Runde {rnd['round']} fertig: noch {len(alive)} von {total}.")
    print("BEFEHL: " + command("next"))


def cmd_pairings(_: argparse.Namespace) -> None:
    state, _run = load()
    rnd = current_round(state)
    if rnd is None:
        print("Noch keine Paarung.")
        return
    print(f"Runde {rnd['round']}")
    if rnd["bye"]:
        print(f"Freilos: {rnd['bye']}")
    for match in rnd["matches"]:
        winner = match["winner"] or "-"
        print(f"{match['id']}: {match['a']} gegen {match['b']} -> {winner}")


def cmd_status(_: argparse.Namespace) -> None:
    state, run = load()
    alive = alive_ids(state)
    print(f"Lauf: {run}")
    print(f"Phase: {PHASE_WORD.get(state['phase'], state['phase'])}")
    print(f"Runde: {state['round']}")
    print(f"Dabei: {len(alive)} von {state['agents_n']}")
    print("Dabei-Liste: " + ", ".join(alive))
    eliminated = [agent for agent in state["order"] if not state["competitors"][agent]["alive"]]
    print("Ausgeschieden: " + (", ".join(eliminated) if eliminated else "-"))
    rnd = current_round(state)
    if rnd and rnd["bye"]:
        print(f"Freilos dieser Runde: {rnd['bye']}")


def cmd_check(args: argparse.Namespace) -> None:
    state, run = load()
    phase = args.phase or state["phase"]
    saved = state["phase"]
    state["phase"] = phase if phase != "final-collect" else "final"
    jobs = build_jobs(state)
    state["phase"] = saved
    if not jobs:
        print("Keine Dateien in dieser Phase.")
        return
    for job in jobs:
        for relative in job["outputs"]:
            mark = "da" if ready(run, [relative]) else "fehlt"
            print(f"{mark} {(run / relative).resolve()}")


def card_line(agent: str, state: dict, index: dict) -> str:
    fields = card_fields(agent, state, index)
    return f"{fields['reasoning_name']}, {fields['workflow_name']}, {fields['strategy_name']}"


def cmd_winner(_: argparse.Namespace) -> None:
    state, run = load()
    alive = alive_ids(state)
    if state["phase"] != "done":
        die(f"Noch nicht fertig. Phase: {state['phase']}.")
    if len(alive) != 1:
        die("Es ist nicht genau eine Lösung übrig.")
    agent = alive[0]
    index = catalog_index(load_catalog())
    solution = run / state["competitors"][agent]["solution"]
    print(f"Sieger: {agent}")
    print(f"Lösung: {solution.resolve()}")
    print("Karte: " + card_line(agent, state, index))
    print(f"Runden: {len(state['rounds'])}")
    survived = state["competitors"][agent]["survived"]
    if survived:
        print("Bestanden:")
        for item in survived:
            print(f"- {item}")
    else:
        print("Bestanden: keine aufgezeichneten Angriffe")
    final = state.get("final")
    if final and final.get("collected"):
        scores = final["scores"]
        left = weighted(scores["X"])
        right = weighted(scores["Y"])
        side = final["winner_side"]
        if side == "champion":
            print("Gegen die abgelehnte Antwort: die neue Lösung liegt vorn.")
        else:
            print("Gegen die abgelehnte Antwort: die abgelehnte Antwort liegt vorn.")
        print(f"X ({final['map']['X']}): {left:.1f}")
        print(f"Y ({final['map']['Y']}): {right:.1f}")
        print(f"Grund: {final['reason']}")
        for item in final.get("fixed") or []:
            print(f"- {item}")
    print(f"Lauf: {run}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bracket.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--agents", type=int, default=100)
    plan.add_argument("--quick", action="store_true")
    plan.add_argument("--wave", type=int, default=10)
    plan.add_argument("--baseline", action="store_true")
    plan.set_defaults(func=cmd_plan)

    init = sub.add_parser("init")
    init.add_argument("--agents", type=int, default=100)
    init.add_argument("--quick", action="store_true")
    init.add_argument("--seed", type=int)
    init.add_argument("--wave", type=int, default=10)
    init.add_argument("--task-file", required=True)
    init.add_argument("--baseline-file")
    init.set_defaults(func=cmd_init)

    nxt = sub.add_parser("next")
    nxt.set_defaults(func=cmd_next)

    prompts = sub.add_parser("prompts")
    prompts.add_argument("phase")
    prompts.set_defaults(func=cmd_prompts)

    pairings = sub.add_parser("pairings")
    pairings.set_defaults(func=cmd_pairings)

    collect = sub.add_parser("collect")
    collect.set_defaults(func=cmd_collect)

    record = sub.add_parser("record")
    record.add_argument("match")
    record.add_argument("agent")
    record.add_argument("--reason", default="")
    record.set_defaults(func=cmd_record)

    advance = sub.add_parser("advance")
    advance.set_defaults(func=cmd_advance)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    winner = sub.add_parser("winner")
    winner.set_defaults(func=cmd_winner)

    check = sub.add_parser("check")
    check.add_argument("phase", nargs="?")
    check.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
