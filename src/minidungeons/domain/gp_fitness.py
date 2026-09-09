"""Fitness ewolucji tree policy - sekcja VI-A arXiv:1802.06881.

Artykul definiuje fitness osobnika jako **utility persony policzone na koncu
partii** (`f_MK = U_MK`), usrednione po partiach na szesciu mapach treningowych
(1, 2, 3, 4, 7, 10). Chromosom calkowicie zastepuje UCB1 w tree policy; reszta
MCTS - rollout 10 ruchow, backpropagacja utility, jedno drzewo na mape - zostaje
bez zmian.

Dwie decyzje wlasne, bo artykul milczy:

* **budzet iteracyjny, nie czasowy** - `max_iterations` zamiast `time_limit_s`.
  Fitness liczony na czasie nie jest odtwarzalny, wiec ta sama populacja dalaby
  inny wynik przy innym obciazeniu maszyny;
* **staly seed partii** - przy deterministycznym silniku para (mapa, seed)
  jednoznacznie wyznacza wynik chromosomu, wiec ocene mozna cache'owac. Liczbe
  seedow na mape podnosi `--seeds-per-map`, jesli overfitting do jednego seeda
  okaze sie problemem.

Modul nie zna procesow ani plikow: `evaluate_playthrough` jest funkcja zadania
dla `infrastructure.experiment_runner.run_in_pool`, a sciezki map podaje driver.
"""

from __future__ import annotations

from pathlib import Path

from .engine import MiniDungeon
from .mcts import MonteCarloTreeSearch
from .personas import PERSONA_NAMES, utility_from_metrics
from .selection_policy import EvolvedPolicy

# Mapy treningowe z sekcji VI-A: "Evolving agents are tested on maps
# 1, 2, 3, 4, 7, and 10 of Fig. 2".
TRAINING_MAP_NAMES = ("map01", "map02", "map03", "map04", "map07", "map10")

# "The best performing run (based on the persona's core priority, e.g. monsters
# killed for the Monster Killer) is chosen among the three evolutionary runs."
# Runner nie ma metryki zbierania - jego priorytetem jest dojscie do wyjscia.
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
    """Ustaw w workerze te same konwencje, ktorymi mierzy sie ramie oceniajace.

    Bez tego GP optymalizowaloby INNA funkcje celu niz ta, ktora potem raportuje
    Tabela II: `metric_values()` liczy `proximity_to_exit` binarnie, a przebiegi
    porownawcze jada na `manhattan`. Utility persony wchodzi tu dwa razy - jako
    nagroda propagowana w drzewie (kazdy rollout) i jako sam fitness na koncu
    partii - wiec podmiana musi byc na poziomie `metric_values`, nie tylko na
    koncowym slowniku metryk. `ic_mode` dotyczy Completionisty, ktory ma w
    uzytecznosci `0,7*IC`.
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
    """Jedna partia jednego chromosomu na jednej mapie - zadanie dla puli.

    Argumenty sa proste (str/int), bo przechodza przez pickle do workera:
    skompilowana formula i obiekt polityki nie sa picklowalne.
    """

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
