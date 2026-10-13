"""Tabela zbiorcza: MCTS (UCB1, trzy ramiona GP) wobec wariantow PPO.

Srednia +- 95% CI; wygrane osobno na 6 mapach treningowych GP i 5 testowych.
PPO z `data/results/rl_eval/<wariant>_<tryb>_<persona>.csv` (rl.evaluate per persona).

    .venv/Scripts/python.exe scripts/table_rl_mcts.py
"""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"
OUT = ROOT / "data" / "results" / "tabela_rl_vs_mcts.md"
PERSONAS = ("runner", "monster_killer", "treasure_collector", "completionist")
TRAIN = {"map01", "map02", "map03", "map04", "map07", "map10"}
MCTS = {"UCB1": "ucb1_bfs.csv", "GP on": "ours_bfs_on.csv", "GP off": "ours_bfs.csv",
        "GP off x10": "ours_bfs10.csv", "GP off fix": "ours_bfs_fix.csv"}
PPO = {"PPO 6 map": "ppo_ego", "PPO generator": "ppo_gen", "PPO 11 map*": "ppo_ego11",
       "PPO generator bonus 0,25": "ppo_gen_lb", "PPO 11 map* bonus 0,25": "ppo_ego11_lb"}
MODES = {"sample": "", "argmax": " argmax"}
CORE = {"runner": "win", "monster_killer": "monster_ratio",
        "treasure_collector": "treasure_ratio", "completionist": "interactive_ratio"}
METRICS = (("win", "Win"), ("win_train", "Win 6 map tren."), ("win_test", "Win 5 map test."),
           ("died", "Zgony"), ("monster_ratio", "MS"), ("potion_ratio", "PD"),
           ("treasure_ratio", "TO"), ("interactive_ratio", "IC"))


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def arms() -> dict[str, list[dict]]:
    data = {name: load(RESULTS / file) for name, file in MCTS.items()}
    for name, variant in PPO.items():
        for mode, suffix in MODES.items():
            rows = [row for persona in PERSONAS
                    for row in load(RESULTS / "rl_eval" / f"{variant}_{mode}_{persona}.csv")]
            data[name + suffix] = rows
    return {name: rows for name, rows in data.items() if rows}


def values(rows: list[dict], persona: str, key: str) -> list[float]:
    rows = [row for row in rows if row["persona"] == persona]
    if key == "win_train":
        rows, key = [row for row in rows if row["map"] in TRAIN], "win"
    elif key == "win_test":
        rows, key = [row for row in rows if row["map"] not in TRAIN], "win"
    return [float(row[key]) for row in rows]


def cell(sample: list[float]) -> str:
    if not sample:
        return "-"
    mean = statistics.mean(sample)
    ci = 1.96 * statistics.stdev(sample) / math.sqrt(len(sample)) if len(sample) > 1 else 0.0
    return f"{100 * mean:.1f} ±{100 * ci:.1f}"


def main() -> None:
    data = arms()
    names = list(data)
    lines = ["`*` uczone na mapach oceny (transdukcyjnie) - nie porownywac wprost z GP.",
             "Pogrubione: najlepsza wartosc metryki priorytetu persony."]
    for persona in PERSONAS:
        lines += [f"\n### {persona}\n", "| metryka | " + " | ".join(names) + " |",
                  "| --- |" + " ---: |" * len(names)]
        for key, label in METRICS:
            means = {name: values(data[name], persona, key) for name in names}
            best = max((statistics.mean(v) for v in means.values() if v), default=None)
            cells = []
            for name in names:
                text = cell(means[name])
                if key == CORE[persona] and means[name] and statistics.mean(means[name]) == best:
                    text = f"**{text}**"
                cells.append(text)
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        counts = [str(len(values(data[name], persona, "win"))) for name in names]
        lines.append("| n | " + " | ".join(counts) + " |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
