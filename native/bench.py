"""Pomiar przyspieszenia na TYM obciazeniu, ktore ma zyskac: fitness GP.

Jedna partia fitnessu to 2000 iteracji MCTS na jednej mapie. Mierzymy to samo
po obu stronach i przeliczamy wynik na czas pelnej ewolucji (12 uruchomien x
100 generacji x 100 osobnikow x 6 map = 60 000 partii na uruchomienie).

    python native/bench.py
    python native/bench.py --iterations 2000 --repeats 3
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mdnative  # noqa: E402

from minidungeons.domain.gp_fitness import evaluate_playthrough as py_evaluate  # noqa: E402

MAPS = ("map01", "map02", "map03", "map04", "map07", "map10")
FORMULAS = {
    "runner": "6.235*ST*PE*PE*(PE + 1) + Rbar*(1 - HL)",
    "monster_killer": "4*MS*PE*(MS + 2*HL*(PE - IC))",
    "treasure_collector": "2*PD + 2*MS + TO + 3*Rbar + ST + PE + 0.19",
    "completionist": "ST*MS*(ST*ST*MS + IC) + Rbar - TO + IC - PE + 2*ST*PE*(ST*MS + 1)",
}
CONVENTIONS = dict(pe_mode="normalized", utility_pe="normalized", ic_mode="mean3",
                   fallback="visits")

# zmierzone w projekcie: 12 uruchomien GP = 14,6 h, 60 000 partii na uruchomienie
RUNS_IN_FULL_EVOLUTION = 12
GAMES_PER_RUN = 100 * 100 * len(MAPS)


def measure(evaluate, iterations: int) -> tuple[float, int]:
    started = time.perf_counter()
    total_iterations = 0
    for persona, formula in FORMULAS.items():
        for name in MAPS:
            map_path = str(ROOT / "data" / "maps" / "md2" / "benchmark" / f"{name}.txt")
            result = evaluate(formula, persona, map_path, 0, iterations, **CONVENTIONS)
            total_iterations += int(result["iterations"])
    return time.perf_counter() - started, total_iterations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    games = len(FORMULAS) * len(MAPS)
    print(f"partii na powtorzenie: {games} ({len(FORMULAS)} persony x {len(MAPS)} map), "
          f"budzet {args.iterations} iteracji\n")

    # rozgrzewka: pierwszy przebieg C++ buduje poziomy (LOS, dystanse)
    measure(mdnative.evaluate_playthrough, 50)

    python_times, native_times = [], []
    for repeat in range(args.repeats):
        seconds, iterations = measure(py_evaluate, args.iterations)
        python_times.append(seconds)
        print(f"  Python  przebieg {repeat + 1}: {seconds:7.2f} s  "
              f"({iterations / seconds:9.0f} iter/s)")
        seconds, iterations = measure(mdnative.evaluate_playthrough, args.iterations)
        native_times.append(seconds)
        print(f"  C++     przebieg {repeat + 1}: {seconds:7.2f} s  "
              f"({iterations / seconds:9.0f} iter/s)")

    python_best = min(python_times)
    native_best = min(native_times)
    speedup = python_best / native_best
    print(f"\nnajlepszy Python: {python_best:.2f} s")
    print(f"najlepszy C++:    {native_best:.2f} s")
    print(f"PRZYSPIESZENIE:   x{speedup:.1f}")

    per_game = python_best / games
    full = RUNS_IN_FULL_EVOLUTION * GAMES_PER_RUN * per_game / 3600.0
    print(f"\nPelna ewolucja ({RUNS_IN_FULL_EVOLUTION} uruchomien x {GAMES_PER_RUN} partii), "
          f"1 rdzen:")
    print(f"  Python: {full:8.1f} h")
    print(f"  C++:    {full / speedup:8.1f} h")
    print("  (zmierzone historycznie na 12-14 workerach: 14,6 h w Pythonie)")


if __name__ == "__main__":
    main()
