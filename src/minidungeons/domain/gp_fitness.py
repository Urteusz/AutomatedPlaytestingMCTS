"""Fitness tree policy (sekcja VI-A arXiv:1802.06881): utility persony na koncu partii.

Srednia po mapach 1, 2, 3, 4, 7, 10; budzet iteracyjny i staly seed dla odtwarzalnosci.
"""

from __future__ import annotations

from pathlib import Path

from .engine import MiniDungeon
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
) -> dict[str, object]:
    """Jedna partia chromosomu na mapie - zadanie dla puli; argumenty proste, bo ida przez pickle."""

    _configure_conventions(utility_pe, ic_mode)
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
