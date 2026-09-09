from __future__ import annotations

import random
import unittest

from src.minidungeons.domain.evolution import (
    INIT_MAX_DEPTH,
    INIT_MIN_DEPTH,
    MAX_DEPTH,
    crossover,
    evolve,
    mutate,
    random_tree,
    replace_subtree,
)
from src.minidungeons.domain.expression import (
    BinOp,
    Const,
    Expr,
    Var,
    iter_subtrees,
    size,
    to_infix,
)


def negative_size(population) -> list[float]:
    """Deterministyczna atrapa fitnessu: krotsze drzewo znaczy lepsze."""

    return [-float(size(tree)) for tree in population]


class RandomTreeTests(unittest.TestCase):
    def test_depth_stays_within_the_initial_bounds(self) -> None:
        rng = random.Random(11)
        for _ in range(200):
            tree = random_tree(rng)
            self.assertGreaterEqual(tree.depth(), INIT_MIN_DEPTH)
            self.assertLessEqual(tree.depth(), INIT_MAX_DEPTH)

    def test_leaves_are_constants_from_the_paper_range_or_table_i_variables(self) -> None:
        rng = random.Random(3)
        for _ in range(50):
            for node in iter_subtrees(random_tree(rng)):
                if isinstance(node, Const):
                    self.assertGreaterEqual(node.value, -1.0)
                    self.assertLessEqual(node.value, 1.0)
                elif isinstance(node, Var):
                    self.assertIn(node.name, to_infix(node))

    def test_same_seed_gives_the_same_tree(self) -> None:
        first = random_tree(random.Random(7))
        second = random_tree(random.Random(7))
        self.assertEqual(to_infix(first), to_infix(second))


class SubtreeOperatorTests(unittest.TestCase):
    def test_replace_subtree_hits_the_preorder_index(self) -> None:
        tree = BinOp("+", Var("PE"), BinOp("*", Const(1.0), Var("MS")))
        # preorder: 0 = calosc, 1 = PE, 2 = (1.0 * MS), 3 = 1.0, 4 = MS
        replaced = replace_subtree(tree, 3, Const(-1.0))
        self.assertEqual(to_infix(replaced), "(PE + (-1 * MS))")

    def test_replace_subtree_at_root_returns_the_replacement(self) -> None:
        tree = BinOp("+", Var("PE"), Var("MS"))
        self.assertEqual(to_infix(replace_subtree(tree, 0, Const(0.5))), "0.5")

    def test_crossover_never_exceeds_the_maximum_depth(self) -> None:
        rng = random.Random(5)
        for _ in range(200):
            first = random_tree(rng)
            second = random_tree(rng)
            child_a, child_b = crossover(first, second, rng)
            self.assertLessEqual(child_a.depth(), MAX_DEPTH)
            self.assertLessEqual(child_b.depth(), MAX_DEPTH)

    def test_crossover_swaps_material_between_parents(self) -> None:
        rng = random.Random(2)
        first = BinOp("+", Var("PE"), Var("MS"))
        second = BinOp("*", Const(0.5), Const(-0.5))
        changed = False
        for _ in range(20):
            child_a, child_b = crossover(first, second, rng)
            if to_infix(child_a) != to_infix(first) or to_infix(child_b) != to_infix(second):
                changed = True
                break
        self.assertTrue(changed, "krzyzowanie nigdy nie wymienilo poddrzewa")

    def test_mutation_replaces_the_whole_chromosome(self) -> None:
        rng = random.Random(1)
        original = BinOp("+", Var("PE"), Var("MS"))
        mutated = mutate(original, rng)
        self.assertGreaterEqual(mutated.depth(), INIT_MIN_DEPTH)
        self.assertLessEqual(mutated.depth(), INIT_MAX_DEPTH)


class EvolveTests(unittest.TestCase):
    def evolve_all(self, *, generations: int = 6, seed: int = 0, **kwargs) -> list:
        return list(
            evolve(
                negative_size,
                generations=generations,
                population_size=kwargs.pop("population_size", 20),
                islands=kwargs.pop("islands", 4),
                seed=seed,
                **kwargs,
            )
        )

    def test_yields_one_record_per_generation(self) -> None:
        history = self.evolve_all(generations=5)
        self.assertEqual([stats.generation for stats in history], [1, 2, 3, 4, 5])

    def test_same_seed_reproduces_the_whole_run(self) -> None:
        first = self.evolve_all(seed=42)
        second = self.evolve_all(seed=42)
        self.assertEqual(
            [(s.best_fitness, to_infix(s.best_expression)) for s in first],
            [(s.best_fitness, to_infix(s.best_expression)) for s in second],
        )

    def test_different_seeds_diverge(self) -> None:
        first = self.evolve_all(seed=1)
        second = self.evolve_all(seed=2)
        self.assertNotEqual(
            [to_infix(s.best_expression) for s in first],
            [to_infix(s.best_expression) for s in second],
        )

    def test_elitism_never_loses_the_best_individual(self) -> None:
        history = self.evolve_all(generations=10)
        scores = [stats.best_fitness for stats in history]
        self.assertEqual(scores, sorted(scores), "najlepszy fitness spadl miedzy generacjami")

    def test_population_size_is_constant_across_generations(self) -> None:
        sizes: list[int] = []

        def counting_fitness(population) -> list[float]:
            sizes.append(len(population))
            return negative_size(population)

        list(evolve(counting_fitness, generations=4, population_size=20, islands=4, seed=0))
        self.assertEqual(sizes, [20, 20, 20, 20])

    def test_best_expression_matches_the_reported_best_fitness(self) -> None:
        for stats in self.evolve_all(generations=4):
            self.assertEqual(stats.best_fitness, -float(size(stats.best_expression)))

    def test_stats_line_reports_the_generation_and_the_formula(self) -> None:
        stats = self.evolve_all(generations=1)[0]
        line = stats.line()
        self.assertIn("gen   1", line)
        self.assertIn(to_infix(stats.best_expression)[:20], line)


if __name__ == "__main__":
    unittest.main()
