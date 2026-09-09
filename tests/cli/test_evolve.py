from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import inspect
import unittest

from src.minidungeons.cli.evolve import (
    PooledFitness,
    best_per_persona,
    format_duration,
    load_runs,
    save_runs,
)
from src.minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR, PROJECT_ROOT

# Uwaga na dwie nazwy tego samego pakietu (README): `cli/evolve.py` importuje
# domene jako `minidungeons.*`, wiec drzewa wyrazen podawane jego funkcjom musza
# pochodzic z tej samej kopii modulu - `isinstance` w `to_infix` nie rozpoznaje
# typow z `src.minidungeons.*`.
from minidungeons.domain.expression import parse
from minidungeons.domain.gp_fitness import evaluate_playthrough


class PooledFitnessTests(unittest.TestCase):
    def make(self, maps=("map01", "map02"), seeds=(0,)) -> PooledFitness:
        return PooledFitness(
            "runner",
            [MD2_BENCHMARK_DIR / f"{name}.txt" for name in maps],
            seeds=seeds,
            max_iterations=10,
            pe_mode="graded",
            workers=1,
        )

    def test_one_task_per_formula_map_and_seed(self) -> None:
        fitness = self.make(seeds=(0, 1))
        tasks = fitness._missing(["PE", "Rbar"])
        self.assertEqual(len(tasks), 2 * 2 * 2)

    def test_duplicated_chromosomes_are_evaluated_once(self) -> None:
        """Elitaryzm i migracja przenosza te same formuly - populacja 100
        osobnikow ma zwykle znacznie mniej unikalnych chromosomow."""

        fitness = self.make()
        self.assertEqual(len(fitness._missing(["PE", "PE", "PE"])), 2)

    def test_cached_results_are_not_recomputed(self) -> None:
        fitness = self.make()
        for map_name in ("map01", "map02"):
            fitness._store({
                "formula": "PE", "map": map_name, "seed": 0,
                "utility": -1.0, "core": 0.0,
            })
        self.assertEqual(fitness._missing(["PE"]), [])
        self.assertEqual(len(fitness._missing(["PE", "Rbar"])), 2)

    def test_score_is_the_mean_utility_over_maps(self) -> None:
        fitness = self.make()
        fitness._store({"formula": "PE", "map": "map01", "seed": 0, "utility": -1.0, "core": 0.0})
        fitness._store({"formula": "PE", "map": "map02", "seed": 0, "utility": 0.0, "core": 1.0})
        self.assertEqual(fitness.scores([parse("PE")]), [-0.5])
        self.assertEqual(fitness.core_value("PE"), 0.5)

    def test_task_arguments_match_the_worker_signature(self) -> None:
        """Straznik zgodnosci krotki zadania z `evaluate_playthrough`.

        Trzy ostatnie pola to konwencje, ktore MUSZA byc te same, co w przebiegu
        oceniajacym - inaczej GP optymalizuje inna funkcje celu niz raportuje
        Tabela II (patrz `gp_fitness._configure_conventions`)."""

        fitness = self.make(maps=("map01",))
        task = fitness._missing(["PE"])[0]
        formula, persona, map_path, seed, iterations, pe_mode, utility_pe, ic_mode, fallback = task
        self.assertEqual(formula, "PE")
        self.assertEqual(persona, "runner")
        self.assertTrue(Path(map_path).exists())
        self.assertEqual((seed, iterations, pe_mode), (0, 10, "graded"))
        self.assertEqual((utility_pe, ic_mode, fallback), ("manhattan", "mean3", "visits"))

        signature = inspect.signature(evaluate_playthrough)
        self.assertEqual(len(task), len(signature.parameters))


class BestRunSelectionTests(unittest.TestCase):
    def entry(self, persona: str, run: int, core: float, fitness: float) -> dict:
        return {
            "persona": persona, "run": run, "seed": run, "formula": f"PE + {run}",
            "fitness": fitness, "core_metric": "reached_exit", "core_value": core,
        }

    def test_core_priority_wins_over_fitness(self) -> None:
        """Artykul wybiera po glownej metryce persony, nie po fitnessie."""

        runs = [self.entry("runner", 0, core=0.2, fitness=9.0),
                self.entry("runner", 1, core=0.8, fitness=1.0)]
        self.assertEqual(best_per_persona(runs)["runner"]["run"], 1)

    def test_fitness_breaks_a_tie(self) -> None:
        runs = [self.entry("runner", 0, core=0.5, fitness=1.0),
                self.entry("runner", 1, core=0.5, fitness=2.0)]
        self.assertEqual(best_per_persona(runs)["runner"]["run"], 1)

    def test_personas_are_selected_independently(self) -> None:
        runs = [self.entry("runner", 0, core=0.9, fitness=1.0),
                self.entry("completionist", 1, core=0.4, fitness=1.0)]
        chosen = best_per_persona(runs)
        self.assertEqual(chosen["runner"]["run"], 0)
        self.assertEqual(chosen["completionist"]["run"], 1)


class RunDocumentTests(unittest.TestCase):
    def test_missing_file_reads_as_an_empty_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = load_runs(Path(directory) / "brak.json")
            self.assertEqual(document["runs"], [])

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            save_runs(path, {"schema_version": 1, "config": {}, "runs": [{"persona": "runner"}]})
            self.assertEqual(load_runs(path)["runs"], [{"persona": "runner"}])
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_duration_is_formatted_as_hours_minutes_seconds(self) -> None:
        self.assertEqual(format_duration(3725), "1:02:05")


class EvolveCliTests(unittest.TestCase):
    """Przebieg mikro-ewolucji przez CLI: wznawianie i przepisanie formul."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        base = Path(self.temp_directory.name)
        self.log = base / "generations.csv"
        self.out = base / "runs.json"
        self.policies = base / "policies.json"

    def run_cli(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, "-m", "src.minidungeons.cli.evolve",
                "--personas", "runner", "--generations", "2", "--population", "4",
                "--islands", "2", "--iterations", "20", "--maps", "map01",
                "--workers", "1", "--log", str(self.log), "--out", str(self.out),
                "--policies-out", str(self.policies), *extra,
            ],
            cwd=PROJECT_ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        )

    def test_runs_are_logged_resumed_and_promoted(self) -> None:
        first = self.run_cli("--runs", "1")
        self.assertIn("gotowe=0, pozostalo=1", first.stdout)

        with self.log.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["generation"] for row in rows], ["1", "2"])
        self.assertEqual({row["persona"] for row in rows}, {"runner"})

        resumed = self.run_cli("--runs", "1")
        self.assertIn("gotowe=1, pozostalo=0", resumed.stdout)

        document = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(len(document["runs"]), 1)
        entry = document["runs"][0]
        self.assertEqual(entry["core_metric"], "reached_exit")
        self.assertEqual(document["config"]["maps"], ["map01"])

        self.run_cli("--promote")
        promoted = json.loads(self.policies.read_text(encoding="utf-8"))
        self.assertEqual(promoted["policies"]["runner"], entry["formula"])
        self.assertEqual(promoted["pe_mode"], "graded")
        parse(promoted["policies"]["runner"])  # formula musi byc czytelna dla EvolvedPolicy

    def test_restart_discards_previous_runs(self) -> None:
        self.run_cli("--runs", "1")
        restarted = self.run_cli("--runs", "1", "--restart")
        self.assertIn("gotowe=0, pozostalo=1", restarted.stdout)
        self.assertEqual(len(json.loads(self.out.read_text(encoding="utf-8"))["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
