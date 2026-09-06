"""Eksperyment MCTS wedlug protokolu artykulu (Tabela II).

Ten modul odpowiada wylacznie za: argumenty, definicje pojedynczej proby
(`run_one`), schemat wiersza wyniku i formatowanie Tabeli II. Wznawianie,
pula procesow i obsluga Ctrl+C siedza w `infrastructure.experiment_runner`,
bo dokladnie tego samego potrzebuje driver ewolucji GP.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from minidungeons.domain.mcts import MonteCarloTreeSearch
from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.domain.selection_policy import (
    SelectionPolicy,
    UCB1Policy,
    evolved_policy_for,
)
from minidungeons.infrastructure.experiment_runner import (
    CsvSchema,
    ResultKey,
    Row,
    configure_parent_interrupts,
    durable_writer,
    load_results,
    mean_with_ci95,
    needs_header,
    run_in_pool,
)
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR, PROJECT_ROOT
from minidungeons.infrastructure.traces import trace_path_for, trace_record, write_trace

RESULTS_DIR = PROJECT_ROOT / "data" / "results"
SEARCH_POLICY = "tree_terminal_only"
TREE_POLICIES = ("ucb1", "evolved", "ours")

POLICY_FILES = {
    "evolved": None,
    "ours": PROJECT_ROOT / "data" / "rules" / "evolved_policies.json",
}
DEFAULT_OUT = {
    "ucb1": RESULTS_DIR / "ucb1_tree_terminal.csv",
    "evolved": RESULTS_DIR / "evolved_tree_terminal.csv",
    "ours": RESULTS_DIR / "gp_evolved.csv",
}

SCHEMA = CsvSchema(
    fields=(
        "persona", "map", "trial", "search_policy", "win", "died", "turns", "steps",
        "health_left", "monster_ratio", "potion_ratio", "treasure_ratio",
        "interactive_ratio", "iterations", "time_sec",
    ),
    key=("persona", "map", "trial"),
    integers=frozenset(
        {"trial", "win", "died", "turns", "steps", "health_left", "iterations"}
    ),
    floats=frozenset(
        {"monster_ratio", "potion_ratio", "treasure_ratio", "interactive_ratio", "time_sec"}
    ),
)
FIELDS = list(SCHEMA.fields)  # zgodnosc wsteczna dla skryptow analitycznych

TABLE_PERSONAS = (
    ("R", "runner"),
    ("MK", "monster_killer"),
    ("TC", "treasure_collector"),
    ("C", "completionist"),
)
TABLE_METRICS = (
    ("Monsters", "monster_ratio", True),
    ("Potions", "potion_ratio", True),
    ("Treasures", "treasure_ratio", True),
    ("Interactive Objects", "interactive_ratio", True),
    ("Win Rate", "win", True),
    ("Time (sec)", "time_sec", False),
)
TABLE_TITLES = {
    "ucb1": "UCB1 BASELINE",
    "evolved": "EVOLVED TREE POLICY (eq. 6-9 z artykulu)",
    "ours": "WLASNA EWOLUCJA GP",
}


# --- pojedyncza proba -------------------------------------------------------


def build_policy(tree_policy: str, persona: str) -> SelectionPolicy:
    """Polityki tworzymy w workerze - skompilowana formula nie jest picklowalna."""

    if tree_policy == "ucb1":
        return UCB1Policy()
    if tree_policy in POLICY_FILES:
        return evolved_policy_for(persona, path=POLICY_FILES[tree_policy])
    raise ValueError(f"Nieznana tree policy {tree_policy!r}; mam: {TREE_POLICIES}")


def run_one(
    map_path: str, persona: str, trial: int, time_limit: float, tree_policy: str = "ucb1"
) -> Row:
    agent = MonteCarloTreeSearch(map_path, policy=build_policy(tree_policy, persona))
    start = time.perf_counter()
    metrics = agent.play_single_tree(persona, time_limit_s=time_limit, seed=trial)
    elapsed = time.perf_counter() - start
    map_name = Path(map_path).stem
    return {
        # slad wraca osobnym kluczem; zapis do CSV zdejmuje go przed wierszem
        "trajectory": trace_record(
            persona=persona, map_name=map_name, trial=trial,
            actions=agent.played, path=agent.path, from_tree=agent.from_tree,
        ),
        "persona": persona, "map": map_name, "trial": trial,
        "search_policy": f"{tree_policy}+{SEARCH_POLICY}",
        "win": int(metrics["reached_exit"]), "died": int(metrics["died"]),
        "turns": metrics["turns"], "steps": metrics["steps"],
        "health_left": metrics["health_left"],
        "monster_ratio": round(metrics["monster_ratio"], 3),
        "potion_ratio": round(metrics["potion_ratio"], 3),
        "treasure_ratio": round(metrics["treasure_ratio"], 3),
        "interactive_ratio": round(metrics["interactive_ratio"], 3),
        "iterations": metrics["iterations"], "time_sec": round(elapsed, 1),
    }


# --- Tabela II --------------------------------------------------------------


def format_table_value(mean: float, ci95: float, percentage: bool) -> str:
    if percentage:
        return f"{mean * 100:.0f}% ± {ci95 * 100:.0f}%"
    decimals = 1 if abs(mean) < 10 else 0
    return f"{mean:.{decimals}f} ± {ci95:.{decimals}f}"


def summarize(rows: list[Row], tree_policy: str = "ucb1") -> None:
    """Wypisz wyniki jednej polityki w ukladzie Tabeli II z artykulu."""

    grouped = {
        persona: [row for row in rows if row["persona"] == persona]
        for _, persona in TABLE_PERSONAS
    }
    label_width, value_width = 21, 16
    title = TABLE_TITLES.get(tree_policy, tree_policy)
    print(f"\n=== {title} — TABELA II (średnia ± 95% CI) ===")
    print(
        f"{'Metric':<{label_width}}"
        + "".join(f"{short:>{value_width}}" for short, _ in TABLE_PERSONAS)
    )
    for label, field_name, percentage in TABLE_METRICS:
        cells: list[str] = []
        for _, persona in TABLE_PERSONAS:
            persona_rows = grouped[persona]
            if not persona_rows:
                cells.append("—")
                continue
            mean, ci95 = mean_with_ci95([float(row[field_name]) for row in persona_rows])
            cells.append(format_table_value(mean, ci95, percentage))
        print(f"{label:<{label_width}}" + "".join(f"{cell:>{value_width}}" for cell in cells))
    print(
        f"{'Liczba prób (n)':<{label_width}}"
        + "".join(f"{len(grouped[persona]):>{value_width}}" for _, persona in TABLE_PERSONAS)
    )


# --- CLI --------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--personas", nargs="*", default=list(PERSONA_NAMES))
    parser.add_argument("--maps", nargs="*", default=None)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument(
        "--policy",
        choices=TREE_POLICIES,
        default="ucb1",
        help="tree policy: UCB1 (baseline) albo ewoluowane formuly eq. 6-9",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="domyslnie data/results/<policy>_tree_terminal.csv",
    )
    parser.add_argument(
        "--traces", type=Path, default=None,
        help="plik JSONL ze sladami partii (domyslnie <out>_paths.jsonl)",
    )
    parser.add_argument(
        "--no-traces", action="store_true",
        help="nie zapisuj sladow partii, tylko metryki w CSV",
    )
    parser.add_argument(
        "--restart", action="store_true",
        help="nadpisz istniejacy CSV zamiast automatycznie wznowic eksperyment",
    )
    parser.add_argument(
        "--report-only", action="store_true",
        help="tylko wypisz Tabele II z istniejacego --out; nie uruchamiaj zadnej proby",
    )
    return parser


def report_only(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.restart:
        parser.error("--report-only i --restart wykluczaja sie")
    if not args.out.exists():
        parser.error(f"nie znaleziono pliku z wynikami: {args.out}")
    try:
        saved = load_results(args.out, SCHEMA)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if not saved:
        parser.error(f"{args.out} nie zawiera zadnych wynikow")
    print(f"Wczytano {len(saved)} prob z: {args.out}")
    summarize(list(saved.values()), args.policy)


def make_reporter(
    append: Any,
    results: dict[ResultKey, Row],
    total: int,
    trace_handle: Any,
) -> Any:
    """Callback puli: zdejmij slad, odsiej duplikat, zapisz wiersz, zamelduj."""

    def on_result(row: Row) -> None:
        trajectory = row.pop("trajectory", None)
        key = SCHEMA.row_key(row)
        if key in results:
            return
        if trace_handle is not None and trajectory is not None:
            write_trace(trace_handle, trajectory)
        append(row)
        results[key] = row
        print(
            f"[{len(results)}/{total}] {row['persona']:18s} {row['map']} "
            f"trial={int(row['trial']):2d} win={row['win']} died={row['died']} "
            f"iter={row['iterations']} ({row['time_sec']}s)",
            flush=True,
        )

    return on_result


def task_key(task: Mapping[str, object] | tuple) -> ResultKey:
    map_path, persona, trial = task[0], task[1], task[2]
    return persona, Path(str(map_path)).stem, int(trial)  # type: ignore[return-value]


def main() -> None:
    configure_parent_interrupts()
    parser = build_parser()
    args = parser.parse_args()
    if args.out is None:
        args.out = DEFAULT_OUT[args.policy]

    if args.report_only:
        report_only(parser, args)
        return

    if args.trials < 0:
        parser.error("--trials nie moze byc ujemne")
    if args.time_limit < 0:
        parser.error("--time-limit nie moze byc ujemny")
    if args.workers < 1:
        parser.error("--workers musi wynosic co najmniej 1")

    map_paths = sorted(MD2_BENCHMARK_DIR.glob("map??.txt"))
    if args.maps:
        map_paths = [path for path in map_paths if path.stem in set(args.maps)]
    all_tasks = [
        (str(map_path), persona, trial, args.time_limit, args.policy)
        for persona in args.personas
        for map_path in map_paths
        for trial in range(args.trials)
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.restart:
        existing_results: dict[ResultKey, Row] = {}
    else:
        try:
            existing_results = load_results(args.out, SCHEMA)
        except ValueError as error:
            parser.error(str(error))

    requested_keys = {task_key(task) for task in all_tasks}
    results = {key: row for key, row in existing_results.items() if key in requested_keys}
    unrelated_count = len(existing_results) - len(results)
    tasks = [task for task in all_tasks if task_key(task) not in results]
    total = len(all_tasks)
    print(
        f"{total} gier (persony={args.personas}, mapy={len(map_paths)}, "
        f"proby={args.trials}, limit={args.time_limit:.0f}s, workers={args.workers}); "
        f"policy={args.policy}+{SEARCH_POLICY}, zapisane={len(results)}, pozostalo={len(tasks)}",
        flush=True,
    )
    if unrelated_count:
        print(
            f"Uwaga: CSV zawiera tez {unrelated_count} wynikow spoza aktualnego zakresu; "
            "pozostaja w pliku, ale nie sa liczone w tym podsumowaniu.",
            flush=True,
        )

    start = time.perf_counter()
    create_file = needs_header(args.out, restart=args.restart)
    mode = "w" if create_file else "a"
    trace_path = None if args.no_traces else (args.traces or trace_path_for(args.out))
    interrupted = False
    with ExitStack() as stack:
        handle = stack.enter_context(args.out.open(mode, newline="", encoding="utf-8"))
        append = durable_writer(handle, SCHEMA, write_header=create_file)
        trace_handle = None
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_handle = stack.enter_context(trace_path.open(mode, encoding="utf-8"))
        if tasks:
            interrupted = run_in_pool(
                run_one,
                tasks,
                workers=args.workers,
                on_result=make_reporter(append, results, total, trace_handle),
            )

    print(f"\nczas calosci: {(time.perf_counter() - start) / 3600:.2f} h")
    summarize(list(results.values()), args.policy)
    print(f"wyniki: {args.out}")
    if trace_path is not None:
        print(f"slady partii: {trace_path}")
    if interrupted:
        print(
            f"Eksperyment wstrzymany ({len(results)}/{total}). "
            "Uruchom ponownie identyczna komende, aby kontynuowac.",
            flush=True,
        )


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    main()
