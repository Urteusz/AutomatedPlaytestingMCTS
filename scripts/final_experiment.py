"""Finalny, wznawialny przebieg porownawczy UCB1 vs eq. (6)-(9).

Domyslne ustawienia odpowiadaja konwencjom odzyskanym z kodu autorow:
PE w [0, 1], pathfinder PE bez krawedzi portali, IC=(MS+PD+TO)/3,
axis8/permissive z glownego rulesetu oraz budzet 20 000 iteracji.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque
from contextlib import ExitStack
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minidungeons.domain import rules as rules_module  # noqa: E402
from minidungeons.domain.engine import DIRECTION_DELTA, MiniDungeon  # noqa: E402
from minidungeons.domain.mcts import MonteCarloTreeSearch  # noqa: E402
from minidungeons.domain.personas import PERSONA_NAMES  # noqa: E402
from minidungeons.domain.selection_policy import (  # noqa: E402
    UCB1Policy,
    evolved_policy_for,
)
from minidungeons.infrastructure.experiment_runner import (  # noqa: E402
    CsvSchema,
    configure_parent_interrupts,
    durable_writer,
    load_results,
    needs_header,
    run_in_pool,
)
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR  # noqa: E402
from minidungeons.infrastructure.traces import (  # noqa: E402
    load_traces,
    trace_path_for,
    trace_record,
    write_trace,
)

SCHEMA = CsvSchema(
    fields=(
        "persona",
        "map",
        "trial",
        "search_policy",
        "win",
        "died",
        "turns",
        "steps",
        "health_left",
        "monster_ratio",
        "potion_ratio",
        "treasure_ratio",
        "interactive_ratio",
        "iterations",
        "time_sec",
    ),
    key=("persona", "map", "trial"),
    integers=frozenset({"trial", "win", "died", "turns", "steps", "health_left", "iterations"}),
    floats=frozenset(
        {"monster_ratio", "potion_ratio", "treasure_ratio", "interactive_ratio", "time_sec"}
    ),
)

_ORIGINAL_RULES_PATH: Path | None = None
_POLICIES_PATH: str | None = None
_ORIGINAL_EXIT_DISTANCES: Any = None
_ORIGINAL_METRIC_VALUES: Any = None


def _exit_distances_without_portals(self: MiniDungeon) -> dict[tuple[int, int], int]:
    """Kardynalny BFS autorow; celowo nie dodaje krawedzi portali."""

    distances = {self.exit: 0}
    queue = deque([self.exit])
    while queue:
        position = queue.popleft()
        for direction in DIRECTION_DELTA:
            neighbor = self._offset(position, direction)
            if neighbor in distances or not self._is_passable(neighbor):
                continue
            distances[neighbor] = distances[position] + 1
            queue.append(neighbor)
    return distances


def _manhattan_proximity(env: MiniDungeon) -> float:
    """PE "cieplej/zimniej" - delegacja do silnika, zeby nie bylo dwoch definicji.

    Patrz `MiniDungeon.manhattan_proximity_to_exit`.
    """

    return env.manhattan_proximity_to_exit()


def _patched_metric_values(*, ic_mean3: bool, utility_pe: str):
    """Zlozenie dwoch odstepstw naraz - `metric_values` mozna podmienic tylko raz.

    `utility_pe` dotyczy PE **w uzytecznosciach person** (eq. 2-5), czyli tego,
    co propaguje sie w drzewie jako R. Domyslne "binary" to kalibracja z
    docs/rules/decisions.md (win rate baseline'u zgodny z Tabela II). Wariant
    "normalized" (1 - d/dmax, 1 na wyjsciu) daje baseline'owi ciagly kompas do
    wyjscia - swiadome odstepstwo, do zaraportowania osobna tabela: win rate
    rosnie do ~47% dla Runnera wobec 10% z Tabeli II.
    """

    def metric_values(self: MiniDungeon) -> dict[str, int | float | bool]:
        values = _ORIGINAL_METRIC_VALUES(self)
        if ic_mean3:
            values["interactive_ratio"] = (
                float(values["monster_ratio"])
                + float(values["potion_ratio"])
                + float(values["treasure_ratio"])
            ) / 3.0
        if utility_pe == "normalized":
            values["proximity_to_exit"] = self.normalized_proximity_to_exit()
        elif utility_pe == "manhattan":
            values["proximity_to_exit"] = _manhattan_proximity(self)
        return values

    return metric_values


def configure_task(
    *, pe_portals: str, ic_mode: str, utility_pe: str = "binary", policies: str | None = None
) -> None:
    """Ustaw kazda zmienna globalna jawnie, takze przy recyklingu workera."""

    global _ORIGINAL_RULES_PATH, _ORIGINAL_EXIT_DISTANCES, _ORIGINAL_METRIC_VALUES
    global _POLICIES_PATH
    _POLICIES_PATH = policies
    if _ORIGINAL_RULES_PATH is None:
        _ORIGINAL_RULES_PATH = rules_module.DEFAULT_RULES_PATH
        _ORIGINAL_EXIT_DISTANCES = MiniDungeon._compute_exit_distances
        _ORIGINAL_METRIC_VALUES = MiniDungeon.metric_values

    rules_module.DEFAULT_RULES_PATH = _ORIGINAL_RULES_PATH
    MiniDungeon._compute_exit_distances = (
        _ORIGINAL_EXIT_DISTANCES if pe_portals == "on" else _exit_distances_without_portals
    )
    MiniDungeon.metric_values = (
        _ORIGINAL_METRIC_VALUES
        if ic_mode == "combined" and utility_pe == "binary"
        else _patched_metric_values(ic_mean3=ic_mode != "combined", utility_pe=utility_pe)
    )


def run_one(
    map_path: str,
    persona: str,
    trial: int,
    iterations: int,
    policy_name: str,
    fallback: str,
    utility_pe: str,
    time_limit: float | None,
    policies: str | None,
    pe_mode: str,
    pe_portals: str,
    ic_mode: str,
) -> dict[str, object]:
    configure_task(
        pe_portals=pe_portals, ic_mode=ic_mode, utility_pe=utility_pe, policies=policies
    )
    # "evolved" = eq. 6-9 z artykulu (data/rules/tree_policies.json),
    # "ours" = formuly z wlasnej ewolucji GP (data/rules/evolved_policies.json)
    if policy_name == "ucb1":
        policy = UCB1Policy()
    elif policy_name == "ours":
        policy = evolved_policy_for(
            persona,
            path=Path(_POLICIES_PATH or ROOT / "data" / "rules" / "evolved_policies.json"),
            pe_mode=pe_mode,
        )
    else:
        policy = evolved_policy_for(persona, pe_mode=pe_mode)
    agent = MonteCarloTreeSearch(map_path, policy=policy)
    start = time.perf_counter()
    metrics = agent.play_single_tree(
        persona,
        time_limit_s=time_limit,
        seed=trial,
        max_iterations=None if time_limit else iterations,
        fallback=fallback,
    )
    elapsed = time.perf_counter() - start
    map_name = Path(map_path).stem
    return {
        "trajectory": trace_record(
            persona=persona,
            map_name=map_name,
            trial=trial,
            actions=agent.played,
            path=agent.path,
            from_tree=agent.from_tree,
        ),
        "persona": persona,
        "map": map_name,
        "trial": trial,
        "search_policy": (
            f"{policy_name}+tree_terminal_only;pe={pe_mode};pe_portals={pe_portals}"
            f";ic={ic_mode};fallback={fallback};upe={utility_pe}"
        ),
        "win": int(metrics["reached_exit"]),
        "died": int(metrics["died"]),
        "turns": metrics["turns"],
        "steps": metrics["steps"],
        "health_left": metrics["health_left"],
        "monster_ratio": round(float(metrics["monster_ratio"]), 3),
        "potion_ratio": round(float(metrics["potion_ratio"]), 3),
        "treasure_ratio": round(float(metrics["treasure_ratio"]), 3),
        "interactive_ratio": round(float(metrics["interactive_ratio"]), 3),
        "iterations": metrics["iterations"],
        "time_sec": round(elapsed, 3),
    }


def key_for(task_or_row: Any) -> tuple[str, str, int]:
    if isinstance(task_or_row, dict):
        return (
            str(task_or_row["persona"]),
            str(task_or_row["map"]),
            int(task_or_row["trial"]),
        )
    return str(task_or_row[1]), Path(task_or_row[0]).stem, int(task_or_row[2])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--policy", choices=("evolved", "ucb1", "ours"), required=True)
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--time-limit", type=float, default=None)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--personas", nargs="*", default=list(PERSONA_NAMES))
    parser.add_argument("--maps", nargs="*", default=None)
    parser.add_argument(
        "--pe-mode",
        choices=("binary", "normalized", "manhattan", "graded"),
        default="normalized",
    )
    parser.add_argument("--pe-portals", choices=("on", "off"), default="off")
    parser.add_argument("--ic-mode", choices=("mean3", "combined"), default="mean3")
    parser.add_argument("--fallback", choices=("utility", "mean", "visits"), default="utility")
    parser.add_argument(
        "--utility-pe", choices=("binary", "normalized", "manhattan"), default="binary"
    )
    parser.add_argument(
        "--policies", default=None,
        help="inny plik formul dla --policy ours (domyslnie data/rules/evolved_policies.json)",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--traces", type=Path, default=None)
    parser.add_argument("--restart", action="store_true")
    return parser


def main() -> None:
    configure_parent_interrupts()
    args = build_parser().parse_args()
    if args.iterations < 1 or args.trials < 0 or args.workers < 1:
        raise SystemExit("iterations/workers musza byc dodatnie, trials nieujemne")

    output = args.out or ROOT / "data" / "results" / f"final_{args.tag}.csv"
    traces = args.traces or trace_path_for(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    map_paths = sorted(MD2_BENCHMARK_DIR.glob("map??.txt"))
    if args.maps:
        requested_maps = set(args.maps)
        map_paths = [path for path in map_paths if path.stem in requested_maps]
    tasks = [
        (
            str(map_path),
            persona,
            trial,
            args.iterations,
            args.policy,
            args.fallback,
            args.utility_pe,
            args.time_limit,
            args.policies,
            args.pe_mode,
            args.pe_portals,
            args.ic_mode,
        )
        for persona in args.personas
        for map_path in map_paths
        for trial in range(args.trials)
    ]

    existing = {} if args.restart else load_results(output, SCHEMA)
    trace_keys: set[tuple[str, str, int]] = set()
    if not args.restart and traces.exists():
        trace_keys = {key_for(record) for record in load_traces(traces)}
    requested = {key_for(task) for task in tasks}
    results = {key: row for key, row in existing.items() if key in requested}
    missing = [
        task for task in tasks if key_for(task) not in results or key_for(task) not in trace_keys
    ]
    print(
        f"{len(tasks)} gier, policy={args.policy}, tag={args.tag}, iter={args.iterations}, "
        f"workers={args.workers}; CSV={len(results)}, slady={len(trace_keys & requested)}, "
        f"pozostalo={len(missing)}",
        flush=True,
    )

    csv_new = needs_header(output, restart=args.restart)
    trace_mode = "w" if args.restart else "a"
    started = time.perf_counter()
    with ExitStack() as stack:
        csv_handle = stack.enter_context(
            output.open("w" if csv_new else "a", newline="", encoding="utf-8")
        )
        append = durable_writer(csv_handle, SCHEMA, write_header=csv_new)
        trace_handle = stack.enter_context(traces.open(trace_mode, encoding="utf-8"))

        def report(row: dict[str, object]) -> None:
            trajectory = row.pop("trajectory")
            key = key_for(row)
            if key not in trace_keys:
                write_trace(trace_handle, trajectory)  # type: ignore[arg-type]
                os.fsync(trace_handle.fileno())
                trace_keys.add(key)
            if key not in results:
                append(row)
                results[key] = row
            print(
                f"[{len(results)}/{len(tasks)}] {row['persona']:18s} {row['map']} "
                f"trial={int(row['trial']):2d} win={row['win']} "
                f"iter={row['iterations']} ({float(row['time_sec']):.3f}s)",
                flush=True,
            )

        interrupted = run_in_pool(run_one, missing, workers=args.workers, on_result=report)

    elapsed = time.perf_counter() - started
    wins = sum(int(row["win"]) for row in results.values())
    print(
        f"Gotowe {len(results)}/{len(tasks)}, wygrane={wins}, czas={elapsed / 60:.1f} min\n"
        f"CSV: {output}\nSlady: {traces}",
        flush=True,
    )
    if interrupted:
        print("Przerwano bez utraty gotowych prob; uruchom ponownie te sama komende.")


if __name__ == "__main__":
    main()
