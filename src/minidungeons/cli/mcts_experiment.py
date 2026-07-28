"""Eksperyment baseline MCTS-UCB1 wedlug protokolu artykulu (Tabela II)."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import (
    FIRST_COMPLETED,
    CancelledError,
    Future,
    ProcessPoolExecutor,
    as_completed,
    wait,
)
from concurrent.futures.process import BrokenProcessPool
import math
import os
from pathlib import Path
import signal
import statistics
import sys
import time
from collections.abc import Iterator, Mapping
from typing import Any

from ..domain.mcts import MonteCarloTreeSearch
from ..domain.personas import PERSONA_NAMES
from ..infrastructure.paths import MD2_BENCHMARK_DIR, PROJECT_ROOT


RESULTS_DIR = PROJECT_ROOT / "data" / "results"
SEARCH_POLICY = "tree_terminal_only"
FIELDS = [
    "persona", "map", "trial", "search_policy", "win", "died", "turns", "steps", "health_left",
    "monster_ratio", "potion_ratio", "treasure_ratio", "interactive_ratio",
    "iterations", "time_sec",
]
INTEGER_FIELDS = {"trial", "win", "died", "turns", "steps", "health_left", "iterations"}
FLOAT_FIELDS = {
    "monster_ratio", "potion_ratio", "treasure_ratio", "interactive_ratio", "time_sec",
}
ResultKey = tuple[str, str, int]
Task = tuple[str, str, int]
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


def run_one(map_path: str, persona: str, trial: int, time_limit: float) -> dict:
    agent = MonteCarloTreeSearch(map_path)
    start = time.perf_counter()
    metrics = agent.play_single_tree(persona, time_limit_s=time_limit, seed=trial)
    elapsed = time.perf_counter() - start
    return {
        "persona": persona, "map": Path(map_path).stem, "trial": trial,
        "search_policy": SEARCH_POLICY,
        "win": int(metrics["reached_exit"]), "died": int(metrics["died"]),
        "turns": metrics["turns"], "steps": metrics["steps"],
        "health_left": metrics["health_left"],
        "monster_ratio": round(metrics["monster_ratio"], 3),
        "potion_ratio": round(metrics["potion_ratio"], 3),
        "treasure_ratio": round(metrics["treasure_ratio"], 3),
        "interactive_ratio": round(metrics["interactive_ratio"], 3),
        "iterations": metrics["iterations"], "time_sec": round(elapsed, 1),
    }


def result_key(row: Mapping[str, object]) -> ResultKey:
    return str(row["persona"]), str(row["map"]), int(row["trial"])


def task_key(task: Task) -> ResultKey:
    map_path, persona, trial = task
    return persona, Path(map_path).stem, trial


def normalize_row(row: Mapping[str, str]) -> dict[str, object]:
    """Convert a CSV row back to the types returned by run_one()."""

    missing = [field for field in FIELDS if row.get(field) in (None, "")]
    if missing:
        raise ValueError(f"niepelny wiersz CSV; brak pol: {', '.join(missing)}")
    normalized: dict[str, object] = {}
    for field in FIELDS:
        value = row[field]
        if field in INTEGER_FIELDS:
            normalized[field] = int(value)
        elif field in FLOAT_FIELDS:
            normalized[field] = float(value)
        else:
            normalized[field] = value
    return normalized


def load_results(path: Path) -> dict[ResultKey, dict[str, object]]:
    """Load completed trials so an interrupted experiment can resume safely."""

    if not path.exists() or path.stat().st_size == 0:
        return {}
    results: dict[ResultKey, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError(
                f"{path} ma niezgodny naglowek; uzyj innego --out albo --restart"
            )
        for line_number, raw_row in enumerate(reader, start=2):
            try:
                row = normalize_row(raw_row)
            except (TypeError, ValueError) as error:
                raise ValueError(f"bledny wiersz {line_number} w {path}: {error}") from error
            results[result_key(row)] = row
    return results


def ignore_interrupt_in_worker() -> None:
    """Only the parent handles Ctrl+C and lets active trials finish cleanly."""

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)


def configure_parent_interrupts() -> None:
    """Treat Ctrl+Break like Ctrl+C on Windows."""

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)


def submit_next(
    pool: ProcessPoolExecutor,
    task_iterator: Iterator[Task],
    futures: dict[Future, Task],
    time_limit: float,
) -> bool:
    try:
        task = next(task_iterator)
    except StopIteration:
        return False
    futures[pool.submit(run_one, *task, time_limit)] = task
    return True


def save_result(
    row: dict[str, object],
    writer: csv.DictWriter,
    handle: Any,
    results: dict[ResultKey, dict[str, object]],
    total: int,
) -> None:
    key = result_key(row)
    if key in results:
        return
    writer.writerow(row)
    handle.flush()
    os.fsync(handle.fileno())
    results[key] = row
    print(
        f"[{len(results)}/{total}] {row['persona']:18s} {row['map']} "
        f"trial={int(row['trial']):2d} win={row['win']} died={row['died']} "
        f"iter={row['iterations']} ({row['time_sec']}s)",
        flush=True,
    )


def run_pending_tasks(
    tasks: list[Task],
    time_limit: float,
    workers: int,
    writer: csv.DictWriter,
    handle: Any,
    results: dict[ResultKey, dict[str, object]],
    total: int,
) -> bool:
    """Run a bounded number of trials; return True after a graceful pause."""

    task_iterator = iter(tasks)
    futures: dict[Future, Task] = {}
    interrupted = False
    pool = ProcessPoolExecutor(
        max_workers=workers,
        initializer=ignore_interrupt_in_worker,
    )
    try:
        for _ in range(min(workers, len(tasks))):
            submit_next(pool, task_iterator, futures, time_limit)

        try:
            while futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in finished:
                    row = future.result()
                    save_result(row, writer, handle, results, total)
                    del futures[future]
                    submit_next(pool, task_iterator, futures, time_limit)
        except KeyboardInterrupt:
            interrupted = True
            print(
                "\nPrzerwa zgloszona. Koncze i zapisuje aktualnie wykonywane proby; "
                "nie uruchamiam nowych...",
                flush=True,
            )
            for future in list(futures):
                if future.cancel():
                    del futures[future]
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (BrokenProcessPool, CancelledError):
                    # A console signal can reach a newly spawned Windows worker
                    # before its initializer starts. The unfinished trial has no
                    # CSV row, so it will be retried automatically after resume.
                    pass
                else:
                    save_result(row, writer, handle, results, total)
                del futures[future]
    finally:
        pool.shutdown(wait=True, cancel_futures=interrupted)
    return interrupted


def mean_with_ci95(values: list[float]) -> tuple[float, float]:
    """Return the arithmetic mean and a two-sided 95% normal CI half-width."""

    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, 0.0
    ci95 = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return mean, ci95


def format_table_value(mean: float, ci95: float, percentage: bool) -> str:
    if percentage:
        return f"{mean * 100:.0f}% ± {ci95 * 100:.0f}%"
    decimals = 1 if abs(mean) < 10 else 0
    return f"{mean:.{decimals}f} ± {ci95:.{decimals}f}"


def summarize(rows: list[dict[str, object]]) -> None:
    """Print the UCB1 baseline using the metric layout from paper Table II."""

    grouped = {
        persona: [row for row in rows if row["persona"] == persona]
        for _, persona in TABLE_PERSONAS
    }
    label_width = 21
    value_width = 16
    print("\n=== UCB1 BASELINE — TABELA II (średnia ± 95% CI) ===")
    print(
        f"{'Metric':<{label_width}}"
        + "".join(f"{short:>{value_width}}" for short, _ in TABLE_PERSONAS)
    )
    for label, field, percentage in TABLE_METRICS:
        cells: list[str] = []
        for _, persona in TABLE_PERSONAS:
            persona_rows = grouped[persona]
            if not persona_rows:
                cells.append("—")
                continue
            values = [float(row[field]) for row in persona_rows]
            mean, ci95 = mean_with_ci95(values)
            cells.append(format_table_value(mean, ci95, percentage))
        print(
            f"{label:<{label_width}}"
            + "".join(f"{cell:>{value_width}}" for cell in cells)
        )
    print(
        f"{'Liczba prób (n)':<{label_width}}"
        + "".join(
            f"{len(grouped[persona]):>{value_width}}"
            for _, persona in TABLE_PERSONAS
        )
    )


def main() -> None:
    configure_parent_interrupts()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--personas", nargs="*", default=list(PERSONA_NAMES))
    parser.add_argument("--maps", nargs="*", default=None)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "ucb1_tree_terminal.csv",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="nadpisz istniejacy CSV zamiast automatycznie wznowic eksperyment",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="tylko wypisz Tabele II z istniejacego --out; nie uruchamiaj zadnej proby",
    )
    args = parser.parse_args()

    if args.report_only:
        if args.restart:
            parser.error("--report-only i --restart wykluczaja sie")
        if not args.out.exists():
            parser.error(f"nie znaleziono pliku z wynikami: {args.out}")
        try:
            saved = load_results(args.out)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        if not saved:
            parser.error(f"{args.out} nie zawiera zadnych wynikow")
        print(f"Wczytano {len(saved)} prob z: {args.out}")
        summarize(list(saved.values()))
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
        (str(map_path), persona, trial)
        for persona in args.personas
        for map_path in map_paths
        for trial in range(args.trials)
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.restart:
        existing_results: dict[ResultKey, dict[str, object]] = {}
    else:
        try:
            existing_results = load_results(args.out)
        except ValueError as error:
            parser.error(str(error))

    requested_keys = {task_key(task) for task in all_tasks}
    results = {
        key: row for key, row in existing_results.items() if key in requested_keys
    }
    unrelated_count = len(existing_results) - len(results)
    tasks = [task for task in all_tasks if task_key(task) not in results]
    total = len(all_tasks)
    print(
        f"{total} gier (persony={args.personas}, mapy={len(map_paths)}, "
        f"proby={args.trials}, limit={args.time_limit:.0f}s, workers={args.workers}); "
        f"policy={SEARCH_POLICY}, zapisane={len(results)}, pozostalo={len(tasks)}",
        flush=True,
    )
    if unrelated_count:
        print(
            f"Uwaga: CSV zawiera tez {unrelated_count} wynikow spoza aktualnego zakresu; "
            "pozostaja w pliku, ale nie sa liczone w tym podsumowaniu.",
            flush=True,
        )

    start = time.perf_counter()
    create_file = args.restart or not args.out.exists() or args.out.stat().st_size == 0
    mode = "w" if create_file else "a"
    interrupted = False
    with args.out.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if create_file:
            writer.writeheader()
            handle.flush()
            os.fsync(handle.fileno())
        if tasks:
            interrupted = run_pending_tasks(
                tasks,
                args.time_limit,
                args.workers,
                writer,
                handle,
                results,
                total,
            )

    print(f"\nczas calosci: {(time.perf_counter() - start) / 3600:.2f} h")
    summarize(list(results.values()))
    print(f"wyniki: {args.out}")
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
