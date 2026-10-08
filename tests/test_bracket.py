import importlib.util
import json
import random
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRACKET = ROOT / "skills" / "arena" / "bracket.py"
SKILL = ROOT / "skills" / "arena" / "SKILL.md"

spec = importlib.util.spec_from_file_location("arena_bracket", BRACKET)
bracket = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bracket)

HIGH = {
    "correctness": 9,
    "completeness": 9,
    "specificity": 8,
    "robustness": 8,
    "clarity": 8,
    "fatal": False,
}
LOW = {
    "correctness": 3,
    "completeness": 3,
    "specificity": 3,
    "robustness": 3,
    "clarity": 3,
    "fatal": False,
}
TASK = "Schreib den Satz.\nZeile zwei mit ü und Leerzeichen. \n\nDritte Zeile.\n"


def run(tmp, args):
    proc = subprocess.run(
        [sys.executable, str(BRACKET), *args],
        cwd=tmp,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + "\n" + proc.stderr)
    return proc.stdout


def latest(tmp):
    name = (Path(tmp) / ".arena" / "LATEST").read_text(encoding="utf-8").strip()
    return Path(tmp) / ".arena" / name


def state_of(tmp):
    return json.loads((latest(tmp) / "arena.json").read_text(encoding="utf-8"))


def befehl(output):
    for line in output.splitlines():
        if line.startswith("BEFEHL:"):
            argv = shlex.split(line.split(":", 1)[1].strip())
            return argv[2:]
    raise AssertionError(output)


def write_task(tmp, text=TASK, baseline=None):
    path = Path(tmp) / "task.md"
    path.write_text(text, encoding="utf-8")
    baseline_path = None
    if baseline is not None:
        baseline_path = Path(tmp) / "baseline.md"
        baseline_path.write_text(baseline, encoding="utf-8")
    return path, baseline_path


def init(tmp, agents, seed, baseline=None, wave=10):
    task, base = write_task(tmp, baseline=baseline)
    args = [
        "init",
        "--agents",
        str(agents),
        "--seed",
        str(seed),
        "--wave",
        str(wave),
        "--task-file",
        str(task),
    ]
    if base is not None:
        args.extend(["--baseline-file", str(base)])
    return run(tmp, args)


def materialise(run, job, scores="smaller"):
    kind = job["kind"]
    if kind == "judge":
        agents = sorted(job["agents"])
        better, worse = agents[0], agents[1]
        if scores == "larger":
            better, worse = worse, better
        payload = {
            "match": job["match"],
            "scores": {better: HIGH, worse: LOW},
            "winner": worse,
            "reason": "Der Test gibt der schwächeren Punktzahl den Zuschlag.",
            "survived": ["Randfall gehalten"],
            "standing": {better: [], worse: ["eine Lücke"]},
        }
        target = run / job["outputs"][0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        return
    if kind == "final":
        payload = {
            "scores": {"X": HIGH, "Y": LOW},
            "winner": "Y",
            "reason": "X ist tragfähiger.",
            "fixed": ["der konkrete Schritt"],
        }
        target = run / job["outputs"][0]
        target.write_text(json.dumps(payload), encoding="utf-8")
        return
    for relative in job["outputs"]:
        target = run / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"Inhalt {job['id']}\n", encoding="utf-8")


def satisfy(tmp):
    run_path = latest(tmp)
    manifest = json.loads((run_path / "jobs.json").read_text(encoding="utf-8"))
    for wave in manifest["waves"]:
        for job in wave:
            materialise(run_path, job)
    return manifest


def play(tmp, limit=4000):
    for _ in range(limit):
        output = run(tmp, ["next"])
        if output.startswith("FERTIG"):
            return run(tmp, ["winner"])
        args = befehl(output)
        if args[0] == "prompts":
            run(tmp, args)
            satisfy(tmp)
        elif args[0] == "winner":
            return run(tmp, args)
        else:
            run(tmp, args)
    raise AssertionError("Turnier läuft nicht zu Ende")


def task_slice(brief):
    begin = "=== AUFGABE (für alle gleich) ===\n"
    end = "\n=== ENDE DER AUFGABE ==="
    return brief.split(begin, 1)[1].split(end, 1)[0]


class ForecastTests(unittest.TestCase):
    def test_plan_writes_nothing_and_matches_the_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = set(Path(tmp).iterdir())
            output = run(tmp, ["plan", "--agents", "100"])
            self.assertEqual(before, set(Path(tmp).iterdir()))
            self.assertIn("595", output)
            self.assertIn("100 -> 50 -> 25 -> 13 -> 7 -> 4 -> 2 -> 1", output)
            quick = run(tmp, ["plan", "--quick"])
            self.assertIn("91", quick)
            self.assertIn("16 -> 8 -> 4 -> 2 -> 1", quick)
            self.assertEqual(sum(row["calls"] for row in bracket.forecast(64, 10)), 379)
            self.assertEqual(sum(row["calls"] for row in bracket.forecast(32, 10)), 187)
            self.assertEqual(sum(row["calls"] for row in bracket.forecast(8, 10)), 43)
            self.assertEqual(sum(row["waves"] for row in bracket.forecast(100, 10)), 70)


class DealerTests(unittest.TestCase):
    def test_unique_balanced_and_distant(self):
        catalog = bracket.load_catalog()
        axes = {
            "reasoning": [item["id"] for item in catalog["reasoning"]],
            "workflow": [item["id"] for item in catalog["workflows"]],
            "strategy": [item["id"] for item in catalog["strategies"]],
        }
        for count in (1, 7, 16, 100):
            for seed in range(4):
                cards = bracket.deal_cards(
                    random.Random(bracket.mix_seed(seed, "deal")),
                    count,
                    catalog,
                )
                triples = [
                    (card["reasoning"], card["workflow"], card["strategy"]) for card in cards
                ]
                self.assertEqual(len(triples), len(set(triples)))
                for axis, ids in axes.items():
                    tally = [sum(card[axis] == item for card in cards) for item in ids]
                    self.assertLessEqual(max(tally) - min(tally), 1)
                    self.assertEqual(sum(tally), count)
                for left in range(len(triples)):
                    for right in range(left + 1, len(triples)):
                        shared = sum(
                            a == b for a, b in zip(triples[left], triples[right])
                        )
                        self.assertLess(shared, 2)

    def test_same_seed_same_cards(self):
        catalog = bracket.load_catalog()
        one = bracket.deal_cards(random.Random(bracket.mix_seed(7, "deal")), 16, catalog)
        two = bracket.deal_cards(random.Random(bracket.mix_seed(7, "deal")), 16, catalog)
        self.assertEqual(one, two)


class ScoringTests(unittest.TestCase):
    def test_fatal_loses_to_a_lower_total(self):
        fatal = {key: 10 for key in bracket.CRITERIA}
        fatal["fatal"] = True
        weak = {key: 1 for key in bracket.CRITERIA}
        weak["fatal"] = False
        winner, reason = bracket.decide_winner("a", "b", {"a": fatal, "b": weak})
        self.assertEqual(winner, "b")
        self.assertIn("fatal", reason.lower())

    def test_tie_uses_standing_then_correctness(self):
        left = {key: 0 for key in bracket.CRITERIA}
        right = {key: 0 for key in bracket.CRITERIA}
        left["correctness"] = 5
        right["completeness"] = 6
        standing = {"a": ["offen"], "b": []}
        winner, _reason = bracket.decide_winner("a", "b", {"a": left, "b": right}, standing)
        self.assertEqual(winner, "b")
        standing = {"a": [], "b": []}
        winner, _reason = bracket.decide_winner("a", "b", {"a": left, "b": right}, standing)
        self.assertEqual(winner, "a")

    def test_python_overrides_the_judge_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            init(tmp, 2, 5)
            self._through_judge(tmp)
            run_path = latest(tmp)
            verdict = next((run_path / "rounds").rglob("verdict.json"))
            payload = json.loads(verdict.read_text(encoding="utf-8"))
            self.assertEqual(payload["winner"], "a002")
            self.assertEqual(befehl(run(tmp, ["next"])), ["collect"])
            run(tmp, ["collect"])
            match = state_of(tmp)["rounds"][0]["matches"][0]
            self.assertEqual(match["winner"], "a001")
            self.assertTrue(match["override"])

    def test_missing_solution_loses_despite_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            init(tmp, 2, 6)
            self._fill_until(tmp, "defend")
            run(tmp, ["prompts", "defend"])
            run_path = latest(tmp)
            manifest = json.loads((run_path / "jobs.json").read_text(encoding="utf-8"))
            for wave in manifest["waves"]:
                for job in wave:
                    for relative in job["outputs"]:
                        target = run_path / relative
                        if job["agent"] == "a001" and relative.endswith(".md") and "solution-" in relative:
                            target.write_text("KEINE AUSGABE\n", encoding="utf-8")
                        elif "solution-" in relative:
                            target.write_text("Eine brauchbare Lösung.\n", encoding="utf-8")
                        else:
                            target.write_text("ANGRIFF 1: HALTEN. Prüft sich.\n", encoding="utf-8")
            output = run(tmp, ["next"])
            self.assertEqual(befehl(output)[:2], ["prompts", "judge"])
            run(tmp, ["prompts", "judge"])
            manifest = json.loads((latest(tmp) / "jobs.json").read_text(encoding="utf-8"))
            for wave in manifest["waves"]:
                for job in wave:
                    materialise(latest(tmp), job)
            self.assertEqual(befehl(run(tmp, ["next"])), ["collect"])
            run(tmp, ["collect"])
            match = state_of(tmp)["rounds"][0]["matches"][0]
            self.assertEqual(match["winner"], "a002")

    def _fill_until(self, tmp, phase):
        for _ in range(20):
            output = run(tmp, ["next"])
            args = befehl(output)
            if args[:2] == ["prompts", phase]:
                return
            if args[0] == "prompts":
                run(tmp, args)
                satisfy(tmp)
            else:
                run(tmp, args)
        raise AssertionError(phase)

    def _through_judge(self, tmp):
        self._fill_until(tmp, "judge")
        run(tmp, ["prompts", "judge"])
        satisfy(tmp)


class PairingTests(unittest.TestCase):
    def test_bye_goes_to_whoever_has_had_fewer(self):
        catalog = bracket.load_catalog()
        modes = [item["id"] for item in catalog["reasoning"]]
        meta = {}
        for index in range(13):
            agent = f"a{index + 1:03d}"
            meta[agent] = {
                "byes": 0,
                "alive": True,
                "card": {"reasoning": modes[index % len(modes)]},
            }
        alive = list(meta)
        while len(alive) > 1:
            matches, bye = bracket.choose_pairs(
                alive,
                meta,
                random.Random(bracket.mix_seed(len(alive), "bye")),
            )
            if bye is not None:
                lowest = min(meta[agent]["byes"] for agent in alive)
                self.assertEqual(meta[bye]["byes"], lowest)
                meta[bye]["byes"] += 1
            self.assertEqual(len(matches) * 2 + (1 if bye else 0), len(alive))
            for left, right in matches:
                meta[max(left, right)]["alive"] = False
            alive = [agent for agent in alive if meta[agent]["alive"]]
        self.assertEqual(len(alive), 1)

    def test_same_reasoning_is_not_paired_when_others_exist(self):
        modes = [f"m{index}" for index in range(8)]
        meta = {
            f"a{index:03d}": {
                "byes": 0,
                "card": {"reasoning": modes[index]},
            }
            for index in range(8)
        }
        matches, bye = bracket.choose_pairs(
            list(meta),
            meta,
            random.Random(bracket.mix_seed(3, "spread")),
        )
        self.assertIsNone(bye)
        for left, right in matches:
            self.assertNotEqual(
                meta[left]["card"]["reasoning"],
                meta[right]["card"]["reasoning"],
            )

    def test_same_seed_same_bracket(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            for tmp in (left, right):
                init(tmp, 8, 11)
                run(tmp, ["next"])
                run(tmp, ["prompts", "spawn"])
                satisfy(tmp)
                run(tmp, ["next"])
            one = state_of(left)["rounds"][0]
            two = state_of(right)["rounds"][0]
            self.assertEqual(one["bye"], two["bye"])
            self.assertEqual(
                [(match["a"], match["b"]) for match in one["matches"]],
                [(match["a"], match["b"]) for match in two["matches"]],
            )
            self.assertEqual(
                [state_of(left)["competitors"][agent]["card"] for agent in state_of(left)["order"]],
                [state_of(right)["competitors"][agent]["card"] for agent in state_of(right)["order"]],
            )


class TournamentTests(unittest.TestCase):
    def test_task_text_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            init(tmp, 4, 9)
            run(tmp, ["next"])
            run(tmp, ["prompts", "spawn"])
            run_path = latest(tmp)
            expected = (run_path / "task.md").read_text(encoding="utf-8")
            briefs = list((run_path / "briefs").glob("spawn-*.md"))
            self.assertEqual(len(briefs), 4)
            slices = [task_slice(brief.read_text(encoding="utf-8")) for brief in briefs]
            self.assertTrue(all(item == expected for item in slices))
            satisfy(tmp)
            run(tmp, ["next"])
            run(tmp, ["prompts", "attack"])
            attack_briefs = list((run_path / "briefs").glob("*attack*.md"))
            self.assertGreaterEqual(len(attack_briefs), 2)
            for brief in attack_briefs:
                self.assertEqual(task_slice(brief.read_text(encoding="utf-8")), expected)

    def test_resume_mid_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            init(tmp, 4, 4)
            run(tmp, ["next"])
            run(tmp, ["prompts", "spawn"])
            run_path = latest(tmp)
            manifest = json.loads((run_path / "jobs.json").read_text(encoding="utf-8"))
            jobs = [job for wave in manifest["waves"] for job in wave]
            for job in jobs[:2]:
                materialise(run_path, job)
            again = run(tmp, ["next"])
            self.assertEqual(befehl(again)[:2], ["prompts", "spawn"])
            run(tmp, ["prompts", "spawn"])
            manifest = json.loads((run_path / "jobs.json").read_text(encoding="utf-8"))
            listed = [job for wave in manifest["waves"] for job in wave]
            self.assertEqual(len(listed), 2)
            self.assertTrue(all(job["attempt"] == 2 for job in listed))
            for job in listed:
                materialise(run_path, job)
            moved = run(tmp, ["next"])
            self.assertEqual(befehl(moved)[:2], ["prompts", "attack"])

    def test_second_miss_becomes_blank_and_loses_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            init(tmp, 2, 8)
            run(tmp, ["next"])
            run(tmp, ["prompts", "spawn"])
            run(tmp, ["next"])
            run(tmp, ["prompts", "spawn"])
            moved = run(tmp, ["next"])
            self.assertEqual(befehl(moved)[:2], ["prompts", "attack"])
            for agent in ("a001", "a002"):
                text = (latest(tmp) / "agents" / agent / "solution.md").read_text(encoding="utf-8")
                self.assertEqual(text, "KEINE AUSGABE\n")

    def test_full_tournaments_finish_with_one(self):
        for agents in (100, 16, 7, 1):
            with self.subTest(agents=agents):
                with tempfile.TemporaryDirectory() as tmp:
                    init(tmp, agents, 21)
                    winner = play(tmp)
                    self.assertIn("Sieger: a001", winner)
                    alive = [
                        agent
                        for agent, row in state_of(tmp)["competitors"].items()
                        if row["alive"]
                    ]
                    self.assertEqual(alive, ["a001"])
                    self.assertEqual(state_of(tmp)["phase"], "done")

    def test_baseline_can_win_the_final_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            task, _base = write_task(tmp, baseline="Die alte Antwort.\n")
            run(
                tmp,
                [
                    "init",
                    "--agents",
                    "2",
                    "--seed",
                    "3",
                    "--task-file",
                    str(task),
                    "--baseline-file",
                    str(Path(tmp) / "baseline.md"),
                ],
            )
            for _ in range(30):
                output = run(tmp, ["next"])
                if output.startswith("FERTIG"):
                    break
                args = befehl(output)
                if args[0] == "prompts" and args[1] == "final":
                    run(tmp, args)
                    run_path = latest(tmp)
                    mapping = state_of(tmp)["final"]["map"]
                    scores = {
                        "X": LOW if mapping["X"] == "champion" else HIGH,
                        "Y": LOW if mapping["Y"] == "champion" else HIGH,
                    }
                    (run_path / "final" / "verdict.json").write_text(
                        json.dumps(
                            {
                                "scores": scores,
                                "winner": "X" if mapping["X"] == "champion" else "Y",
                                "reason": "Die alte Fassung trifft die Aufgabe.",
                                "fixed": ["sie nennt den Schritt"],
                            }
                        ),
                        encoding="utf-8",
                    )
                elif args[0] == "prompts":
                    run(tmp, args)
                    satisfy(tmp)
                else:
                    run(tmp, args)
            text = run(tmp, ["winner"])
            self.assertIn("die abgelehnte Antwort liegt vorn", text)

    def test_templates_live_in_the_skill(self):
        skill = SKILL.read_text(encoding="utf-8")
        for name, template in bracket.TEMPLATES.items():
            self.assertIn(template, skill, name)


if __name__ == "__main__":
    unittest.main()
