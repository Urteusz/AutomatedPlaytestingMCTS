"""Baseline UCB1 przy budzecie iteracyjnym z artykulu (2-5 mln wezlow) - port C++.

Pytanie: czy luka obliczeniowa wobec artykulu (u nas ~375 tys. iteracji w 300 s,
u nich 2-5 mln wezlow) tlumaczy rozbieznosc win rate baseline'u. Krzywa
"win rate od budzetu" z `ucb1_bfs.csv` przewiduje ~30-33% przy 3 mln, czyli
DALEJ od artykulu (<15%).

Konwencje identyczne z `ucb1_bfs.csv` (upe=normalized, ic=mean3,
fallback=visits), trial = seed jak w `final_experiment.py`. Budzet iteracyjny,
wiec wynik jest odtwarzalny i niezalezny od sprzetu. UCB1 w C++ zweryfikowany
testem roznicowym (`native/difftest.py`, poziom 3b: 96/96 bit w bit).

Pamiec: wezel ~850 B, 3 mln wezlow = ~2,5 GB na partie -> domyslnie 8 workerow.
Wznawialny: pomija (persona, map, trial) juz zapisane w CSV.
`--policies plik.json` gra formulami GP z pliku zamiast UCB1 (ta sama konwencja).
`--report ref.csv` niczego nie liczy, tylko porownuje `--out` z ramieniem 300 s na
probach kompletnych w obu plikach (niedokonczona proba to glownie szybkie wygrane).

    .venv/Scripts/python.exe scripts/native_budget.py
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))

import mdnative  # noqa: E402

MAPS = [f"map{i:02d}" for i in range(1, 12)]
PERSONAS = ("runner", "monster_killer", "treasure_collector", "completionist")
KW = dict(pe_mode="normalized", utility_pe="normalized", ic_mode="mean3", fallback="visits",
          pe_portals="off")
FIELDS = ["persona", "map", "trial", "search_policy", "win", "died", "turns", "steps",
          "health_left", "monster_ratio", "potion_ratio", "treasure_ratio",
          "interactive_ratio", "iterations", "nodes", "from_tree", "time_sec"]


def task(args: tuple[str, str, int, int, str | None]) -> dict:
    persona, map_name, trial, budget, formula = args
    path = str(ROOT / "data" / "maps" / "md2" / "benchmark" / f"{map_name}.txt")
    start = time.perf_counter()
    policy = "ucb1" if formula is None else "evolved"
    r = mdnative.evaluate_playthrough(formula or "0", persona, path, trial, budget, policy=policy,
                                      **KW)
    return {
        "persona": persona, "map": map_name, "trial": trial,
        "search_policy": (f"{'ucb1' if formula is None else 'ours'}_native;iters={budget};"
                          "pe=normalized;pe_portals=off;ic=mean3;fallback=visits;upe=normalized"),
        "win": r["win"], "died": r["died"], "turns": r["turns"], "steps": r["steps"],
        "health_left": r["health_left"], "monster_ratio": round(r["monster_ratio"], 3),
        "potion_ratio": round(r["potion_ratio"], 3),
        "treasure_ratio": round(r["treasure_ratio"], 3),
        "interactive_ratio": round(r["interactive_ratio"], 3),
        "iterations": r["iterations"], "nodes": r["nodes"], "from_tree": int(r["from_tree"]),
        "time_sec": round(time.perf_counter() - start, 3),
    }


CORE = {"runner": "win", "monster_killer": "monster_ratio",
        "treasure_collector": "treasure_ratio", "completionist": "interactive_ratio"}


def report(budget_csv: Path, reference_csv: Path) -> None:
    def complete(path: Path) -> dict[int, list[dict]]:
        with path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        trials: dict[int, list[dict]] = {}
        for row in rows:
            trials.setdefault(int(row["trial"]), []).append(row)
        return {t: r for t, r in trials.items() if len(r) == len(PERSONAS) * len(MAPS)}

    budget, reference = complete(budget_csv), complete(reference_csv)
    shared = sorted(set(budget) & set(reference))
    print(f"kompletne proby wspolne: {len(shared)} {shared}")
    for persona, core in CORE.items():
        line = [f"{persona:19s}"]
        for name, trials in (("300 s", reference), ("budzet", budget)):
            rows = [r for t in shared for r in trials[t] if r["persona"] == persona]
            if rows:
                win = 100 * statistics.mean(float(r["win"]) for r in rows)
                value = 100 * statistics.mean(float(r[core]) for r in rows)
                line.append(f"{name}: W {win:5.1f} {core} {value:5.1f}")
        print("  ".join(line))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=3_000_000)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--trial-start", type=int, default=0,
                        help="pierwsza proba (rownolegle instancje)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--policies", type=Path, default=None,
                        help="plik formul GP; bez niego UCB1")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data" / "results" / "ucb1_native_3m.csv")
    parser.add_argument("--report", type=Path, default=None,
                        help="CSV ramienia 300 s do porownania; nic nie liczy")
    args = parser.parse_args()
    if args.report:
        report(args.out, args.report)
        return

    done: set[tuple[str, str, int]] = set()
    if args.out.exists():
        with args.out.open(encoding="utf-8") as handle:
            done = {(row["persona"], row["map"], int(row["trial"]))
                    for row in csv.DictReader(handle)}
    formulas = (json.loads(args.policies.read_text(encoding="utf-8"))["policies"]
                if args.policies else {})
    # proba w petli zewnetrznej: przerwany przebieg zostaje zbalansowany po personach i mapach
    jobs = [(p, m, t, args.iterations, formulas.get(p))
            for t in range(args.trial_start, args.trials)
            for p in PERSONAS for m in MAPS if (p, m, t) not in done]
    print(f"{len(jobs)} partii do policzenia ({len(done)} juz jest), budzet {args.iterations}, "
          f"{args.workers} workerow", flush=True)

    new_file = not args.out.exists()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(task, job) for job in jobs]
            for i, future in enumerate(as_completed(futures), 1):
                writer.writerow(future.result())
                handle.flush()
                if i % 50 == 0:
                    print(f"  {i}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
