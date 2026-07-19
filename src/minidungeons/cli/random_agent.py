"""Random-agent smoke runner for the reconstructed MiniDungeons 2 engine."""

from __future__ import annotations

import argparse
from pathlib import Path
import random
import sys
import time

from ..domain import MiniDungeon


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MAP = PROJECT_ROOT / "data" / "maps" / "md2" / "benchmark" / "map01.txt"


def run_one(
    env: MiniDungeon,
    rng: random.Random,
    *,
    max_turns: int = 200,
    verbose: bool = True,
    draw: bool = True,
    delay: float = 0.0,
):
    env.reset()
    for turn in range(max_turns):
        legal = env.legal_actions()
        if not legal:
            break
        action = rng.choice(legal)
        state, info = env.step(action)
        if verbose:
            event_names = ",".join(str(event["type"]) for event in info["events"])
            print(
                f"tura {turn:3d} | {str(action):12s} | HP {state['hp']:2d} | "
                f"pos {state['hero_position']} | {event_names}"
            )
        if draw:
            print(env.render(), "\n")
            if delay:
                time.sleep(delay)
        if env.done:
            break
    return env.metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    env = MiniDungeon(args.map)
    print(f"Mapa: {args.map} ({env.height}x{env.width})")
    print(f"Wejście: {env.entrance}  Wyjście: {env.exit}  ruleset: {env.rules.data['ruleset_id']}\n")

    if args.trials == 1:
        run_one(
            env,
            rng,
            max_turns=args.max_turns,
            verbose=not args.quiet,
            draw=not args.quiet,
        )
        print("\n=== WYNIK ===")
        for key, value in env.metric_values().items():
            print(f"  {key:32s}: {value}")
        print(f"  outcome                         : {env.outcome or 'timeout'}")
        return

    totals = {
        "wins": 0, "deaths": 0, "steps": 0,
        "treasures": 0, "monsters": 0, "potions": 0,
    }
    for _ in range(args.trials):
        metrics = run_one(env, rng, max_turns=args.max_turns, verbose=False, draw=False)
        totals["wins"] += int(metrics.reached_exit)
        totals["deaths"] += int(metrics.died)
        totals["steps"] += metrics.steps_taken
        totals["treasures"] += metrics.treasures_opened
        totals["monsters"] += metrics.monsters_slain
        totals["potions"] += metrics.potions_drunk
    count = args.trials
    print(f"=== STATYSTYKA: {count} prób ===")
    print(f"  win rate      : {totals['wins'] / count:.0%}")
    print(f"  death rate    : {totals['deaths'] / count:.0%}")
    for name in ("steps", "treasures", "monsters", "potions"):
        print(f"  avg {name:9s}: {totals[name] / count:.2f}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    main()
