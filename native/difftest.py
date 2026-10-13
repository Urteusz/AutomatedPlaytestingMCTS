"""Test roznicowy: C++ musi liczyc DOKLADNIE to samo co Python.

Bez tego port jest bezwartosciowy - dokladnie tak przepadlo lustro w C#, ktore
dalo "x195", bo liczylo mniej pracy niz silnik. Trzy poziomy, od najtanszego:

1. **generator** - `randbelow` z C++ wobec `random.Random(seed)._randbelow`;
2. **silnik** - te same sekwencje akcji odegrane po obu stronach, porownanie
   stanu po KAZDYM kroku (pozycja, HP, metryki, zywi NPC);
3. **cala partia** - `evaluate_playthrough` po obu stronach: fitness, glowna
   metryka, liczba iteracji i odegrana sekwencja akcji co do akcji.

Punkt 3 jest rozstrzygajacy: jesli sekwencje sa identyczne, to znaczy, ze
zgadzaja sie i losowanie, i reguly gry, i selekcja, i backpropagacja.

    python native/difftest.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import md2native  # noqa: E402
import mdnative  # noqa: E402

from minidungeons.domain.engine import Action, MiniDungeon  # noqa: E402
from minidungeons.domain.gp_fitness import (  # noqa: E402
    _configure_conventions,
    _configure_pe_portals,
    core_metric_value,
    utility_from_metrics,
)
from minidungeons.domain.gp_fitness import evaluate_playthrough as py_evaluate  # noqa: E402
from minidungeons.domain.mcts import MonteCarloTreeSearch  # noqa: E402
from minidungeons.domain.selection_policy import EvolvedPolicy, UCB1Policy  # noqa: E402

MAPS_DIR = ROOT / "data" / "maps" / "md2" / "benchmark"
MAP_PATHS = sorted(MAPS_DIR.glob("map??.txt"))
DIRECTION_INDEX = {"N": 0, "E": 1, "S": 2, "W": 3}

FORMULAS = {
    # eq. 6-9 z artykulu
    "runner": "6.235*ST*PE*PE*(PE + 1) + Rbar*(1 - HL)",
    "monster_killer": "4*MS*PE*(MS + 2*HL*(PE - IC))",
    "treasure_collector": "2*PD + 2*MS + TO + 3*Rbar + ST + PE + 0.19",
    "completionist": "ST*MS*(ST*ST*MS + IC) + Rbar - TO + IC - PE + 2*ST*PE*(ST*MS + 1)",
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def action_code(action: Action) -> int:
    if action.kind == "move":
        return DIRECTION_INDEX[action.direction]
    return 4 + int(action.target_id)


# --- 1. generator -----------------------------------------------------------


def test_random() -> None:
    for seed in (0, 1, 2, 7, 42, 12345):
        for bound in (2, 3, 4, 5, 7, 16, 17, 100):
            native = md2native.random_probe(seed, bound, 200)
            rng = random.Random(seed)
            expected = [rng._randbelow(bound) for _ in range(200)]
            check(native == expected, f"RNG rozjechal sie dla seed={seed}, bound={bound}")
    print("1. generator losowy: OK" if not failures else "1. generator losowy: BLAD")


# --- 2. silnik --------------------------------------------------------------


def state_fingerprint(env: MiniDungeon) -> tuple:
    width = env.width
    npcs = [npc.position[0] * width + npc.position[1] for npc in
            sorted(env.npcs.values(), key=lambda value: value.npc_id)]
    return (
        env.hero_position[0] * width + env.hero_position[1], env.hero_hp, env.done,
        env.metrics.steps_taken, env.metrics.turns_taken, env.metrics.monsters_slain,
        env.metrics.potions_drunk, env.metrics.treasures_opened, env.metrics.javelins_thrown,
        env.metrics.teleports_used, env.metrics.traps_sprung, env.metrics.minitaur_knockouts,
        env.metrics.reached_exit, env.metrics.died, npcs,
    )


def test_engine(walks: int = 20, length: int = 120) -> None:
    mismatches = 0
    for map_path in MAP_PATHS:
        level = mdnative.level_for(str(map_path))
        for walk in range(walks):
            rng = random.Random(walk)
            env = MiniDungeon(map_path)
            codes: list[int] = []
            for _ in range(length):
                legal = env.legal_actions()
                if not legal:
                    break
                action = rng.choice(legal)
                codes.append(action_code(action))
                env.step(action)
            native = md2native.replay(level, codes)
            expected = state_fingerprint(env)
            got = (
                native["hero"], native["hero_hp"], native["done"], native["steps"],
                native["turns"], native["monsters"], native["potions"], native["treasures"],
                native["javelins"], native["teleports"], native["traps"],
                native["minitaur_knockouts"], native["reached_exit"], native["died"],
                [cell for cell in native["npcs"] if cell >= 0],
            )
            if got != expected:
                mismatches += 1
                if mismatches <= 3:
                    failures.append(
                        f"silnik: {map_path.stem} walk={walk}\n  python={expected}\n  cpp   ={got}"
                    )
    print(f"2. silnik ({len(MAP_PATHS)} map x {walks} przebiegow): "
          + ("OK" if mismatches == 0 else f"BLAD w {mismatches} przebiegach"))


# --- 3. cala partia ---------------------------------------------------------


def python_sequence(formula: str, persona: str, map_path: Path, seed: int, iterations: int,
                    pe_mode: str, fallback: str) -> list[int]:
    policy = EvolvedPolicy(formula, pe_mode=pe_mode, label=persona)
    agent = MonteCarloTreeSearch(str(map_path), policy=policy)
    agent.play_single_tree(persona, time_limit_s=None, seed=seed,
                           max_iterations=iterations, fallback=fallback)
    return [action_code(action) for action in agent.played]


def test_playthrough(iterations: int = 300, seeds: tuple[int, ...] = (0, 1, 2)) -> None:
    mismatches = 0
    checked = 0
    for pe_mode, utility_pe, ic_mode, fallback, pe_portals in (
        ("normalized", "normalized", "mean3", "visits", "off"),
        ("normalized", "normalized", "mean3", "visits", "on"),
        ("manhattan", "manhattan", "mean3", "visits", "off"),
        ("binary", "binary", "combined", "utility", "on"),
    ):
        for persona, formula in FORMULAS.items():
            for map_path in MAP_PATHS[:4]:
                for seed in seeds:
                    checked += 1
                    expected = py_evaluate(
                        formula, persona, str(map_path), seed, iterations,
                        pe_mode=pe_mode, utility_pe=utility_pe, ic_mode=ic_mode,
                        fallback=fallback, pe_portals=pe_portals,
                    )
                    sequence = python_sequence(formula, persona, map_path, seed, iterations,
                                               pe_mode, fallback)
                    got = mdnative.evaluate_playthrough(
                        formula, persona, str(map_path), seed, iterations,
                        pe_mode=pe_mode, utility_pe=utility_pe, ic_mode=ic_mode,
                        fallback=fallback, pe_portals=pe_portals,
                    )
                    same = (
                        got["iterations"] == expected["iterations"]
                        and got["win"] == expected["win"]
                        and abs(got["utility"] - expected["utility"]) < 1e-12
                        and abs(got["core"] - expected["core"]) < 1e-12
                        and list(got["sequence"]) == sequence
                    )
                    if not same:
                        mismatches += 1
                        if mismatches <= 3:
                            failures.append(
                                f"partia: {persona} {map_path.stem} seed={seed} "
                                f"pe={pe_mode} fb={fallback}\n"
                                f"  iteracje  py={expected['iterations']} cpp={got['iterations']}\n"
                                f"  utility   py={expected['utility']!r} cpp={got['utility']!r}\n"
                                f"  core      py={expected['core']!r} cpp={got['core']!r}\n"
                                f"  win       py={expected['win']} cpp={got['win']}\n"
                                f"  dlugosc   py={len(sequence)} cpp={len(got['sequence'])}"
                            )
    print(f"3. cala partia ({checked} kombinacji): "
          + ("OK" if mismatches == 0 else f"BLAD w {mismatches} kombinacjach"))


def test_ucb1_playthrough(iterations: int = 300, seeds: tuple[int, ...] = (0, 1, 2)) -> None:
    """Jak poziom 3, ale z UCB1 zamiast formuly - baseline liczony natywnie."""

    mismatches = 0
    checked = 0
    for utility_pe, ic_mode, fallback, pe_portals in (
        ("normalized", "mean3", "visits", "off"),
        ("normalized", "mean3", "visits", "on"),
        ("binary", "combined", "utility", "on"),
    ):
        _configure_conventions(utility_pe, ic_mode)
        _configure_pe_portals(pe_portals)
        for persona in FORMULAS:
            for map_path in MAP_PATHS[:4]:
                for seed in seeds:
                    checked += 1
                    agent = MonteCarloTreeSearch(str(map_path), policy=UCB1Policy())
                    metrics = agent.play_single_tree(
                        persona, time_limit_s=None, seed=seed, max_iterations=iterations,
                        fallback=fallback,
                    )
                    sequence = [action_code(action) for action in agent.played]
                    got = mdnative.evaluate_playthrough(
                        "0", persona, str(map_path), seed, iterations,
                        pe_mode="binary", utility_pe=utility_pe, ic_mode=ic_mode,
                        fallback=fallback, pe_portals=pe_portals, policy="ucb1",
                    )
                    same = (
                        got["iterations"] == int(metrics["iterations"])
                        and got["win"] == int(bool(metrics["reached_exit"]))
                        and abs(got["utility"] - utility_from_metrics(persona, metrics)) < 1e-12
                        and abs(got["core"] - core_metric_value(persona, metrics)) < 1e-12
                        and list(got["sequence"]) == sequence
                    )
                    if not same:
                        mismatches += 1
                        if mismatches <= 3:
                            failures.append(
                                f"ucb1: {persona} {map_path.stem} seed={seed} upe={utility_pe} "
                                f"fb={fallback}\n"
                                f"  iteracje  py={metrics['iterations']} cpp={got['iterations']}\n"
                                f"  dlugosc   py={len(sequence)} cpp={len(got['sequence'])}"
                            )
    print(f"3b. cala partia UCB1 ({checked} kombinacji): "
          + ("OK" if mismatches == 0 else f"BLAD w {mismatches} kombinacjach"))


if __name__ == "__main__":
    test_random()
    test_engine()
    test_playthrough()
    test_ucb1_playthrough()
    print()
    if failures:
        print(f"NIEZGODNOSCI: {len(failures)} (pierwsze {min(len(failures), 6)}):")
        for failure in failures[:6]:
            print(" -", failure)
        sys.exit(1)
    print("Wszystkie trzy poziomy zgodne - port liczy to samo co Python.")
