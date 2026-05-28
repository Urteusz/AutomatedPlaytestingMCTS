"""
Uruchomienie srodowiska z losowym agentem.

To jest sanity check: sprawdzamy, ze
  1. mapa sie wczytuje,
  2. hero rusza sie zgodnie z zasadami (nie wchodzi w sciany),
  3. interakcje dzialaja (skarb/potion/potwor/wyjscie),
  4. metryki sie zliczaja.

Uruchom:
    python run_random.py            # jeden przebieg, krok po kroku
    python run_random.py --quiet    # bez rysowania mapy, tylko log ruchow
    python run_random.py --trials 50  # statystyka z wielu przebiegow
"""

import argparse
import random
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from dungeon import MiniDungeon


def run_one(env, max_steps=200, verbose=True, draw=True, delay=0.0):
    env.reset()
    for i in range(max_steps):
        legal = env.legal_moves()
        if not legal:
            break
        action = random.choice(legal)
        state, info = env.step(action)

        if verbose:
            tag = {
                "move": "  ",
                "treasure": "TT",  # skarb
                "potion": "PP",    # potion
                "monster": "MM",   # potwor
                "exit": ">>",      # wyjscie
                "died": "XX",      # smierc
                "wall": "##",
            }.get(info["event"], "??")
            print(f"krok {i:3d} | {info['dir']} {tag} | "
                  f"HP {state['hp']:3d} | pos ({state['y']:2d},{state['x']:2d}) | "
                  f"{info['event']}")

        if draw:
            print(env.render())
            print()
            if delay:
                time.sleep(delay)

        if env.done:
            break

    return env.metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="maps/map1.txt")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--quiet", action="store_true", help="bez rysowania mapy")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    env = MiniDungeon(args.map)
    print(f"Wczytano mape: {args.map}  ({env.height}x{env.width})")
    print(f"Wejscie: {env.entrance}  Wyjscie: {env.exit}\n")

    if args.trials == 1:
        m = run_one(env, verbose=True, draw=not args.quiet)
        print("\n=== WYNIK ===")
        for k, v in m.as_dict().items():
            print(f"  {k:14s}: {v}")
    else:
        wins = deaths = 0
        tot_steps = tot_treasure = tot_monsters = tot_potions = 0
        for _ in range(args.trials):
            m = run_one(env, verbose=False, draw=False)
            wins += m.reached_exit
            deaths += m.died
            tot_steps += m.steps_taken
            tot_treasure += m.treasures_opened
            tot_monsters += m.monsters_slain
            tot_potions += m.potions_drunk
        n = args.trials
        print(f"=== STATYSTYKA z {n} przebiegow (losowy agent) ===")
        print(f"  win rate     : {wins/n:.0%}")
        print(f"  death rate   : {deaths/n:.0%}")
        print(f"  avg steps    : {tot_steps/n:.1f}")
        print(f"  avg treasures: {tot_treasure/n:.2f}")
        print(f"  avg monsters : {tot_monsters/n:.2f}")
        print(f"  avg potions  : {tot_potions/n:.2f}")


if __name__ == "__main__":
    main()
