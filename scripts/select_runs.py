"""Wybor zwycieskiego uruchomienia z re-ewolucji `gp_runs_bfs_fix.json`, dwie reguly naraz.

Obie reguly licza sie z tego samego pomiaru: 6 map treningowych x 20 seedow
x 100 tys. iteracji, konwencje ramienia oceniajacego (upe=normalized,
pe=normalized, ic=mean3, fallback=visits, pe_portals=off). Zadnego podgladu
zbioru oceniajacego.

- `core`    - regula artykulu (sekcja VI-A): glowna metryka persony;
- `fitness` - srednia utility persony (ta sama funkcja, ktora optymalizuje GP).

Zapisuje `data/rules/evolved_policies_bfs_fix_core.json` i `..._fitness.json`
oraz pelna tabele do `data/results/select_bfs_fix.csv`, zeby
wynik nie przepadl jak przy `estimator.py`.

    .venv/Scripts/python.exe scripts/select_runs.py [--pe-portals on]

Przy `--pe-portals on` czyta `gp_runs_bfs_on.json` i pisze pliki z sufiksem `_on`.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))

import mdnative  # noqa: E402

TRAIN = ("map01", "map02", "map03", "map04", "map07", "map10")
KW = dict(pe_mode="normalized", utility_pe="normalized", ic_mode="mean3", fallback="visits")
PERSONAS = ("runner", "monster_killer", "treasure_collector", "completionist")
VARIANTS = {
    "off": ("gp_runs_bfs_fix.json", "select_bfs_fix.csv", "evolved_policies_bfs_fix_{rule}.json"),
    "on": ("gp_runs_bfs_on.json", "select_bfs_on.csv", "evolved_policies_bfs_on_{rule}.json"),
}


def task(job: tuple[str, int, str, str, int, str, int]) -> tuple[str, int, float, float]:
    persona, run, formula, map_name, seed, pe_portals, budget = job
    path = str(ROOT / "data" / "maps" / "md2" / "benchmark" / f"{map_name}.txt")
    r = mdnative.evaluate_playthrough(formula, persona, path, seed, budget,
                                      pe_portals=pe_portals, **KW)
    return persona, run, r["core"], r["utility"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pe-portals", choices=("off", "on"), default="off")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--budget", type=int, default=100_000)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    pe_portals, SEEDS, BUDGET = args.pe_portals, args.seeds, args.budget
    runs_name, table_name, policies_name = VARIANTS[pe_portals]
    RUNS_PATH = ROOT / "data" / "results" / runs_name
    TABLE_PATH = ROOT / "data" / "results" / table_name
    document = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
    config = document["config"]
    for key, value in (("utility_pe", "normalized"), ("pe_mode", "normalized"),
                       ("ic_mode", "mean3"), ("fallback", "visits"), ("pe_portals", pe_portals)):
        if config.get(key) != value:
            sys.exit(f"{RUNS_PATH.name}: config {key}={config.get(key)!r}, oczekiwano {value!r}")
    runs = document["runs"]
    by_key = {(r["persona"], r["run"]): r for r in runs}
    jobs = [(r["persona"], r["run"], r["formula"], m, s, pe_portals, BUDGET)
            for r in runs for m in TRAIN for s in range(SEEDS)]
    print(f"{len(jobs)} partii ({len(runs)} uruchomien x {len(TRAIN)} map x {SEEDS} seedow, "
          f"budzet {BUDGET})", flush=True)

    agg: dict[tuple[str, int], dict[str, list[float]]] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (persona, run, core, util) in enumerate(pool.map(task, jobs, chunksize=16), 1):
            entry = agg.setdefault((persona, run), {"core": [], "util": []})
            entry["core"].append(core)
            entry["util"].append(util)
            if i % 480 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    rows = []
    for (persona, run), entry in sorted(agg.items()):
        rows.append({
            "persona": persona, "run": run,
            "core20": statistics.mean(entry["core"]),
            "fitness20": statistics.mean(entry["util"]),
            "core1": by_key[(persona, run)]["core_value"],
            "fitness1": by_key[(persona, run)]["fitness"],
            "formula": by_key[(persona, run)]["formula"],
        })
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TABLE_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for rule in ("core", "fitness"):
        chosen = {}
        for persona in PERSONAS:
            candidates = [row for row in rows if row["persona"] == persona]
            # remis w core rozstrzyga fitness, jak `best_per_persona`
            key = ((lambda row: (row["core20"], row["fitness20"])) if rule == "core"
                   else (lambda row: row["fitness20"]))
            chosen[persona] = max(candidates, key=key)
        payload = {
            "schema_version": 1,
            "source": (f"Re-ewolucja GP ({runs_name}, 10 uruchomien, pe_portals={pe_portals}); "
                       f"wybor po {rule} na 6 mapach treningowych, {SEEDS} seedow, "
                       f"budzet {BUDGET} iteracji"),
            "pe_mode": "normalized",
            "policies": {p: chosen[p]["formula"] for p in PERSONAS},
            "notes": {p: (f"run {chosen[p]['run']} z 10, core20={chosen[p]['core20']:.4f}, "
                          f"fitness20={chosen[p]['fitness20']:.4f}") for p in PERSONAS},
        }
        out = ROOT / "data" / "rules" / policies_name.format(rule=rule)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{rule:8s} -> {out.name}: " + ", ".join(f"{p}=run {chosen[p]['run']}"
                                                      for p in PERSONAS))


if __name__ == "__main__":
    main()
