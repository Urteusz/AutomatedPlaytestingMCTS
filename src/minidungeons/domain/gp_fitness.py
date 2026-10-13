"""Fitness tree policy (sekcja VI-A arXiv:1802.06881): utility persony na koncu partii.

Srednia po mapach 1, 2, 3, 4, 7, 10; budzet iteracyjny i staly seed dla odtwarzalnosci.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from .engine import DIRECTION_DELTA, MiniDungeon
from .mcts import MonteCarloTreeSearch
from .personas import PERSONA_NAMES, utility_from_metrics
from .selection_policy import EvolvedPolicy

# mapy treningowe z sekcji VI-A
TRAINING_MAP_NAMES = ("map01", "map02", "map03", "map04", "map07", "map10")

# sekcja VI-A: najlepszy z 3 runow po core priority persony; Runner - dojscie do wyjscia
CORE_METRIC = {
    "runner": "reached_exit",
    "monster_killer": "monster_ratio",
    "treasure_collector": "treasure_ratio",
    "completionist": "interactive_ratio",
}


def core_metric_value(persona: str, metrics: dict[str, int | float | bool]) -> float:
    """Glowna metryka persony - po niej wybieramy najlepsze z 3 uruchomien."""

    if persona not in PERSONA_NAMES:
        raise ValueError(f"Nieznana persona {persona!r}; mam: {PERSONA_NAMES}")
    return float(metrics[CORE_METRIC[persona]])


_PATCHED: tuple[str, str] | None = None
_ORIGINAL_METRIC_VALUES = MiniDungeon.metric_values
_ORIGINAL_EXIT_DISTANCES = MiniDungeon._compute_exit_distances


def exit_distances_without_portals(self: MiniDungeon) -> dict[tuple[int, int], int]:
    """Kardynalny BFS bez krawedzi portali - `pe_portals=off` ramienia oceniajacego."""

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


def exit_distances(environment: MiniDungeon, pe_portals: str) -> dict[tuple[int, int], int]:
    """Dystanse do wyjscia w danej konwencji, niezaleznie od podmiany w `_configure_pe_portals`."""

    if pe_portals == "on":
        return _ORIGINAL_EXIT_DISTANCES(environment)
    if pe_portals == "off":
        return exit_distances_without_portals(environment)
    raise ValueError(f"pe_portals musi byc 'on' albo 'off', jest {pe_portals!r}")


def _configure_pe_portals(pe_portals: str) -> None:
    """Portale w BFS do wyjscia: `on` = silnik (krawedz o koszcie 0), `off` = bez nich."""

    if pe_portals not in ("on", "off"):
        raise ValueError(f"pe_portals musi byc 'on' albo 'off', jest {pe_portals!r}")
    MiniDungeon._compute_exit_distances = (
        _ORIGINAL_EXIT_DISTANCES if pe_portals == "on" else exit_distances_without_portals
    )


def _configure_conventions(utility_pe: str, ic_mode: str) -> None:
    """Ustaw w workerze konwencje ramienia oceniajacego, zeby GP optymalizowalo te sama utility.

    Podmiana musi byc w `metric_values`, bo utility wchodzi i do rolloutow, i do fitnessu.
    """

    global _PATCHED
    if _PATCHED == (utility_pe, ic_mode):
        return

    def metric_values(self: MiniDungeon) -> dict[str, int | float | bool]:
        values = _ORIGINAL_METRIC_VALUES(self)
        if ic_mode == "mean3":
            values["interactive_ratio"] = (
                float(values["monster_ratio"])
                + float(values["potion_ratio"])
                + float(values["treasure_ratio"])
            ) / 3.0
        if utility_pe == "manhattan":
            values["proximity_to_exit"] = self.manhattan_proximity_to_exit()
        elif utility_pe == "normalized":
            values["proximity_to_exit"] = self.normalized_proximity_to_exit()
        return values

    MiniDungeon.metric_values = (
        _ORIGINAL_METRIC_VALUES
        if utility_pe == "binary" and ic_mode == "combined"
        else metric_values
    )
    _PATCHED = (utility_pe, ic_mode)


def evaluate_playthrough(
    formula: str,
    persona: str,
    map_path: str,
    seed: int,
    max_iterations: int,
    pe_mode: str,
    utility_pe: str = "binary",
    ic_mode: str = "combined",
    fallback: str = "utility",
    pe_portals: str = "on",
) -> dict[str, object]:
    """Jedna partia chromosomu na mapie - zadanie dla puli.

    Argumenty sa proste, bo ida przez pickle.
    """

    _configure_conventions(utility_pe, ic_mode)
    _configure_pe_portals(pe_portals)
    policy = EvolvedPolicy(
        formula, pe_mode=pe_mode, label=persona
    )
    agent = MonteCarloTreeSearch(map_path, policy=policy)
    metrics = agent.play_single_tree(
        persona, time_limit_s=None, seed=seed, max_iterations=max_iterations,
        fallback=fallback,
    )
    return {
        "formula": formula,
        "map": Path(map_path).stem,
        "seed": seed,
        "utility": utility_from_metrics(persona, metrics),
        "core": core_metric_value(persona, metrics),
        "win": int(bool(metrics["reached_exit"])),
        "iterations": int(metrics["iterations"]),
    }
