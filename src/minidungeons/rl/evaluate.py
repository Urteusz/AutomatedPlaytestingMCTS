"""Ocena wytrenowanych modeli PPO w protokole MCTS: 11 map x `--trials` prob na persone.

CSV ma schemat `ucb1_bfs.csv` (plus `decision_ms`), obok idzie `*_paths.jsonl`,
wiec wynik wchodzi do Tabeli II i do `frontend/heatmap.py` bez zmian w tamtym kodzie.
Akcje sa probkowane z polityki (seed = proba), bo argmax dalby 50 identycznych partii.
`--deterministic` gra argmaxem (gra jest deterministyczna, wiec wszystkie proby na mapie
sa wtedy identyczne). `--shield` naklada tarcze przed smiercia (patrz `rl/env.py`)
takze na modele uczone bez niej.
Czas decyzji mierzony na CPU w jednym watku - tak samo liczy MCTS. Srodowisko
(maska petli, tarcza, limit tur) bierze sie z `config.json` modelu.

    python -m minidungeons.rl.evaluate --variant ppo_gen --deterministic
"""

from __future__ import annotations

import argparse
import csv
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import torch
from sb3_contrib import MaskablePPO

from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.infrastructure.paths import RESULTS_DIR
from minidungeons.infrastructure.traces import trace_path_for, trace_record, write_trace
from minidungeons.rl.env import MiniDungeonsEnv
from minidungeons.rl.train import env_options

ALL_MAPS = tuple(f"map{index:02d}" for index in range(1, 12))
FIELDS = ("persona", "map", "trial", "search_policy", "win", "died", "turns", "steps",
          "health_left", "monster_ratio", "potion_ratio", "treasure_ratio",
          "interactive_ratio", "iterations", "time_sec", "decision_ms")


Job = tuple[str, str, int, int | None, bool]


def evaluate_persona(job: Job) -> tuple[list[dict], list[dict]]:
    variant, persona, trials, shield, deterministic = job
    torch.set_num_threads(1)
    model_dir = RESULTS_DIR / variant / persona
    model = MaskablePPO.load(model_dir / "model", device="cpu")
    options = env_options(model_dir)
    options.pop("win_bonus", None)  # zmienia tylko nagrode, nie gre
    if shield is not None:
        options["shield"] = shield
    env = MiniDungeonsEnv(persona, ALL_MAPS, **options)
    max_wait = options["max_wait"]
    label = (f"{variant};pe=normalized;pe_portals={options['pe_portals']};ic=mean3"
             f";max_steps={options['max_steps']}"
             f";max_wait={'off' if max_wait is None else max_wait}"
             f";shield={options.get('shield', 0)}"
             f";actions={'argmax' if deterministic else 'sample'}")
    rows, traces = [], []
    for map_name in ALL_MAPS:
        for trial in range(trials):
            torch.manual_seed(trial)
            observation, info = env.reset(seed=trial, options={"map": map_name})
            actions, path = [], [env.env.hero_position]
            thinking = 0.0
            done = False
            while not done:
                started = time.perf_counter()
                index, _ = model.predict(observation, action_masks=env.action_masks(),
                                         deterministic=deterministic)
                thinking += time.perf_counter() - started
                actions.append(env.decode(int(index)))
                observation, _, terminated, truncated, info = env.step(int(index))
                path.append(env.env.hero_position)
                done = terminated or truncated
            metrics = info["metrics"]
            ratios = [float(metrics[key]) for key in ("monster_ratio", "potion_ratio",
                                                      "treasure_ratio")]
            decisions = len(actions)
            rows.append({
                "persona": persona, "map": map_name, "trial": trial, "search_policy": label,
                "win": int(info["win"]), "died": int(info["died"]), "turns": info["turns"],
                "steps": metrics["steps"], "health_left": metrics["health_left"],
                "monster_ratio": round(ratios[0], 3), "potion_ratio": round(ratios[1], 3),
                "treasure_ratio": round(ratios[2], 3),
                "interactive_ratio": round(sum(ratios) / 3, 3),
                "iterations": decisions, "time_sec": round(thinking, 4),
                "decision_ms": round(1000 * thinking / max(decisions, 1), 4),
            })
            traces.append(trace_record(persona=persona, map_name=map_name, trial=trial,
                                       actions=actions, path=path, from_tree=None))
    return rows, traces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", required=True, help="katalog w data/results z modelami")
    parser.add_argument("--personas", nargs="*", choices=PERSONA_NAMES, default=list(PERSONA_NAMES))
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--shield", type=int, default=None,
                        help="glebokosc tarczy przed smiercia; domyslnie z config.json")
    parser.add_argument("--deterministic", action="store_true", help="argmax zamiast probkowania")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out = args.out or RESULTS_DIR / f"{args.variant}_eval.csv"
    jobs = [(args.variant, persona, args.trials, args.shield, args.deterministic)
            for persona in args.personas]
    if len(jobs) == 1:  # bez puli: drugi proces z torchem to kolejne ~3 GB pamieci
        results = [evaluate_persona(jobs[0])]
    else:
        with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
            results = list(pool.map(evaluate_persona, jobs))
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for rows, _ in results:
            writer.writerows(rows)
    with trace_path_for(out).open("w", encoding="utf-8") as handle:
        for _, traces in results:
            for record in traces:
                write_trace(handle, record)
    print(f"zapisano {out} i {trace_path_for(out).name}")


if __name__ == "__main__":
    main()
