from __future__ import annotations

import unittest

from src.minidungeons.domain.gp_fitness import (
    CORE_METRIC,
    TRAINING_MAP_NAMES,
    core_metric_value,
    evaluate_playthrough,
)
from src.minidungeons.domain.mcts import MonteCarloTreeSearch
from src.minidungeons.domain.personas import PERSONA_NAMES, utility_from_metrics
from src.minidungeons.domain.selection_policy import EvolvedPolicy
from src.minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR

MAP = str(MD2_BENCHMARK_DIR / "map01.txt")
FORMULA = "PE + Rbar"


def evaluate(**overrides) -> dict[str, object]:
    arguments = {
        "formula": FORMULA,
        "persona": "runner",
        "map_path": MAP,
        "seed": 0,
        "max_iterations": 40,
        "pe_mode": "graded",
    }
    arguments.update(overrides)
    return evaluate_playthrough(**arguments)  # type: ignore[arg-type]


class TrainingSetTests(unittest.TestCase):
    def test_training_maps_are_the_six_from_section_vi_a(self) -> None:
        self.assertEqual(
            TRAINING_MAP_NAMES, ("map01", "map02", "map03", "map04", "map07", "map10")
        )
        for name in TRAINING_MAP_NAMES:
            self.assertTrue((MD2_BENCHMARK_DIR / f"{name}.txt").exists())

    def test_every_persona_has_a_core_priority_metric(self) -> None:
        self.assertEqual(sorted(CORE_METRIC), sorted(PERSONA_NAMES))

    def test_core_metric_reads_the_persona_specific_field(self) -> None:
        metrics = {
            "reached_exit": True, "monster_ratio": 0.25,
            "treasure_ratio": 0.5, "interactive_ratio": 0.75,
        }
        self.assertEqual(core_metric_value("runner", metrics), 1.0)
        self.assertEqual(core_metric_value("monster_killer", metrics), 0.25)
        self.assertEqual(core_metric_value("treasure_collector", metrics), 0.5)
        self.assertEqual(core_metric_value("completionist", metrics), 0.75)

    def test_unknown_persona_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            core_metric_value("speedrunner", {"reached_exit": True})


class PlaythroughEvaluationTests(unittest.TestCase):
    def test_result_carries_the_cache_key_and_both_scores(self) -> None:
        row = evaluate()
        self.assertEqual(row["formula"], FORMULA)
        self.assertEqual(row["map"], "map01")
        self.assertEqual(row["seed"], 0)
        self.assertIn("utility", row)
        self.assertIn("core", row)
        self.assertIn(row["win"], (0, 1))

    def test_same_seed_gives_the_same_fitness(self) -> None:
        self.assertEqual(evaluate(), evaluate())

    def test_iteration_budget_is_respected_so_fitness_is_reproducible(self) -> None:
        row = evaluate(max_iterations=40)
        self.assertLessEqual(int(row["iterations"]), 40)  # type: ignore[arg-type]

    def test_fitness_is_the_persona_utility_of_the_final_state(self) -> None:
        """f_R = U_R z sekcji VI-A - fitness nie jest osobnym wzorem."""

        policy = EvolvedPolicy(FORMULA, pe_mode="graded")
        agent = MonteCarloTreeSearch(MAP, policy=policy)
        metrics = agent.play_single_tree(
            "runner", time_limit_s=None, seed=0, max_iterations=40
        )
        self.assertAlmostEqual(
            float(evaluate()["utility"]),  # type: ignore[arg-type]
            utility_from_metrics("runner", metrics),
        )

    def test_core_value_of_the_runner_matches_the_win_flag(self) -> None:
        row = evaluate()
        self.assertEqual(float(row["core"]), float(row["win"]))  # type: ignore[arg-type]

    def test_pe_mode_reaches_the_tree_policy(self) -> None:
        """PE binarne i ciagle daja rozne przebiegi - inaczej flaga nic nie robi.

        Mierzone na Completioniscie, nie na Runnerze: przy binarnym PE w utility
        Runner nie zyskuje niczego poza samym wyjsciem, wiec gdy drzewo wyjscia
        nie znajdzie, jego najlepsza odkryta sekwencja jest pusta (stanie w
        miejscu) niezaleznie od ksztaltu drzewa - i fitness przestaje odrozniac
        pe_mode. Completionist ma 0,7*IC, wiec kazda inna sciezka w drzewie daje
        inny stan koncowy.
        """

        arguments = {"persona": "completionist", "max_iterations": 300}
        graded = [evaluate(seed=seed, pe_mode="graded", **arguments) for seed in range(3)]
        binary = [evaluate(seed=seed, pe_mode="binary", **arguments) for seed in range(3)]
        self.assertNotEqual(
            [row["utility"] for row in graded], [row["utility"] for row in binary]
        )


if __name__ == "__main__":
    unittest.main()
