"""Programowanie genetyczne dla tree policy - sekcja V-B arXiv:1802.06881.

Chromosom to drzewo wyrazenia z `expression.py`. Ewolucja idzie modelem wysp:
migracja w kazdej generacji, po migracji piecioro najlepszych z kazdej wyspy
tworzy jej pule rodzicielska, elitaryzm 15%, mutacja 10% (podmiana calego
chromosomu na losowy - tak to opisuje artykul), krzyzowanie przez wymiane
losowych poddrzew z jednostajnym wyborem rodzicow.

Interpretacje tam, gdzie artykul milczy, sa opisane w docstringach funkcji.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterator, Sequence

from .expression import (
    BINARY_OPS,
    VARIABLE_NAMES,
    BinOp,
    Const,
    Expr,
    Var,
    iter_subtrees,
    size,
    to_infix,
)

INIT_MIN_DEPTH = 2
INIT_MAX_DEPTH = 5
MAX_DEPTH = 8
CONST_RANGE = (-1.0, 1.0)


def random_tree(
    rng: random.Random,
    min_depth: int = INIT_MIN_DEPTH,
    max_depth: int = INIT_MAX_DEPTH,
    depth: int = 0,
) -> Expr:
    """Losowe drzewo o glebokosci z [min_depth, max_depth].

    Ponizej `min_depth` wymuszamy wezel wewnetrzny, powyzej `max_depth` lisc;
    pomiedzy losujemy 50/50 (artykul podaje tylko granice glebokosci).
    """

    if depth >= max_depth:
        force_leaf = True
    elif depth < min_depth:
        force_leaf = False
    else:
        force_leaf = rng.random() < 0.5
    if force_leaf:
        if rng.random() < 0.5:
            return Const(round(rng.uniform(*CONST_RANGE), 4))
        return Var(rng.choice(VARIABLE_NAMES))
    return BinOp(
        rng.choice(BINARY_OPS),
        random_tree(rng, min_depth, max_depth, depth + 1),
        random_tree(rng, min_depth, max_depth, depth + 1),
    )


def replace_subtree(expression: Expr, index: int, replacement: Expr) -> Expr:
    """Podmien poddrzewo o podanym numerze w przejsciu preorder."""

    counter = [0]

    def walk(node: Expr) -> Expr:
        current = counter[0]
        counter[0] += 1
        if current == index:
            return replacement
        if isinstance(node, BinOp):
            left = walk(node.left)
            right = walk(node.right)
            if left is node.left and right is node.right:
                return node
            return BinOp(node.op, left, right)
        return node

    return walk(expression)


def crossover(first: Expr, second: Expr, rng: random.Random) -> tuple[Expr, Expr]:
    """Wymiana losowych poddrzew; przy przekroczeniu MAX_DEPTH ponawiamy proba.

    Artykul nie mowi, co robic z potomkiem za glebokim - po kilku probach
    zwracamy rodzicow bez zmian, zeby operator nigdy nie wywalil populacji.
    """

    first_nodes = list(iter_subtrees(first))
    second_nodes = list(iter_subtrees(second))
    for _ in range(8):
        i = rng.randrange(len(first_nodes))
        j = rng.randrange(len(second_nodes))
        child_a = replace_subtree(first, i, second_nodes[j])
        child_b = replace_subtree(second, j, first_nodes[i])
        if child_a.depth() <= MAX_DEPTH and child_b.depth() <= MAX_DEPTH:
            return child_a, child_b
    return first, second


def mutate(expression: Expr, rng: random.Random) -> Expr:
    """Mutacja z artykulu: podmiana calego chromosomu na losowy nowy."""

    return random_tree(rng)


@dataclass
class GenerationStats:
    generation: int
    best_fitness: float
    mean_fitness: float
    best_expression: Expr
    unique_chromosomes: int

    def line(self) -> str:
        return (
            f"gen {self.generation:>3d}  best={self.best_fitness:+.4f}  "
            f"mean={self.mean_fitness:+.4f}  unikalnych={self.unique_chromosomes:>3d}  "
            f"size={size(self.best_expression):>3d}  {to_infix(self.best_expression)[:70]}"
        )


FitnessFn = Callable[[Sequence[Expr]], list[float]]


def evolve(
    fitness: FitnessFn,
    *,
    generations: int,
    population_size: int = 100,
    islands: int = 5,
    elitism: float = 0.15,
    mutation_rate: float = 0.10,
    mating_pool_top: int = 5,
    seed: int = 0,
) -> Iterator[GenerationStats]:
    """Uruchom ewolucje, oddajac statystyki po kazdej generacji.

    `fitness` dostaje cala populacje naraz (zeby dala sie zrownoleglic) i zwraca
    liste ocen w tej samej kolejnosci. Wyzej znaczy lepiej.
    """

    rng = random.Random(seed)
    per_island = max(2, population_size // islands)
    groups = [[random_tree(rng) for _ in range(per_island)] for _ in range(islands)]

    for generation in range(1, generations + 1):
        flat = [tree for group in groups for tree in group]
        scores = fitness(flat)
        scored: list[list[tuple[float, Expr]]] = []
        offset = 0
        for group in groups:
            chunk = list(zip(scores[offset : offset + len(group)], group))
            chunk.sort(key=lambda pair: pair[0], reverse=True)
            scored.append(chunk)
            offset += len(group)

        best_fitness, best_expression = max(
            (chunk[0] for chunk in scored), key=lambda pair: pair[0]
        )
        yield GenerationStats(
            generation=generation,
            best_fitness=best_fitness,
            mean_fitness=sum(scores) / len(scores),
            best_expression=best_expression,
            unique_chromosomes=len({to_infix(tree) for tree in flat}),
        )
        if generation == generations:
            return

        # migracja pierscieniowa: najlepszy z wyspy trafia na nastepna wyspe
        # (artykul mowi tylko "migration occurs in every generation")
        migrants = [chunk[0][1] for chunk in scored]
        for index, chunk in enumerate(scored):
            chunk.append((float("-inf"), migrants[index - 1]))

        next_groups: list[list[Expr]] = []
        for chunk in scored:
            elite_count = max(1, int(round(elitism * per_island)))
            elites = [tree for _, tree in chunk[:elite_count]]

            pool = [tree for _, tree in chunk[:mating_pool_top]]
            pool = [mutate(tree, rng) if rng.random() < mutation_rate else tree for tree in pool]

            children: list[Expr] = []
            while len(elites) + len(children) < per_island:
                first, second = rng.choice(pool), rng.choice(pool)
                child_a, child_b = crossover(first, second, rng)
                children.append(child_a)
                if len(elites) + len(children) < per_island:
                    children.append(child_b)
            next_groups.append(elites + children)
        groups = next_groups
