"""Zapis i odczyt sladow przebytych partii (JSONL obok CSV z metrykami).

Jedna linia = jedna proba: persona, mapa, numer proby, odegrane akcje i kolejne
kafle bohatera. Silnik jest deterministyczny, wiec sama lista akcji wystarcza do
pelnego odtworzenia partii; `path` jest zapisany osobno, zeby agregacja (np.
heatmapa) nie musiala odgrywac tysiecy prob.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, IO, Iterable, Mapping, Sequence

Coord = tuple[int, int]


def trace_path_for(results_path: str | Path) -> Path:
    """Sciezka sidecara: ucb1_tree_terminal.csv -> ucb1_tree_terminal_paths.jsonl."""

    results_path = Path(results_path)
    return results_path.with_name(f"{results_path.stem}_paths.jsonl")


def trace_record(
    *,
    persona: str,
    map_name: str,
    trial: int,
    actions: Iterable[Any],
    path: Sequence[Coord],
    from_tree: bool | None,
) -> dict[str, Any]:
    """Slad w formie gotowej do serializacji."""

    return {
        "persona": persona,
        "map": map_name,
        "trial": int(trial),
        "from_tree": bool(from_tree),
        "actions": [str(action) for action in actions],
        "path": [[int(row), int(column)] for row, column in path],
    }


def write_trace(handle: IO[str], record: dict[str, Any]) -> None:
    """Dopisuje jeden slad. Zapis idzie przed wierszem CSV, bo CSV jest znacznikiem
    wznawiania - lepiej miec slad zdublowany niz zgubiony (loader deduplikuje)."""

    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()


def load_traces(path: str | Path) -> list[dict[str, Any]]:
    """Slady z pliku, z `path` jako lista krotek. Przy powtorzonym kluczu
    (persona, mapa, proba) zostaje ostatni wpis."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku ze sladami: {path}")
    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"bledna linia {line_number} w {path}: {exc}") from exc
            # brakujacy klucz to nie egzotyka: proces ubity w trakcie zapisu
            # zostawia ogon, ktory bywa poprawnym JSON-em bez czesci pol
            try:
                record["path"] = [(int(row), int(column)) for row, column in record["path"]]
                key = (record["persona"], record["map"], int(record["trial"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"bledna linia {line_number} w {path}: {exc}") from exc
            unique[key] = record
    return list(unique.values())


def paths_by_persona(
    records: Iterable[dict[str, Any]],
    *,
    map_name: str | None = None,
) -> dict[str, list[list[Coord]]]:
    """Persona -> lista sciezek. `map_name` zaweza do jednej mapy, bo kafle
    z roznych map nie sumuja sie sensownie."""

    grouped: dict[str, list[list[Coord]]] = {}
    for record in records:
        if map_name is not None and record["map"] != map_name:
            continue
        grouped.setdefault(record["persona"], []).append(record["path"])
    return grouped


def cell_counts(paths: Iterable[Sequence[Coord]]) -> dict[Coord, int]:
    """Kafel -> liczba wizyt we wszystkich podanych sciezkach (wejscie do heatmapy)."""

    counts: dict[Coord, int] = {}
    for path in paths:
        for cell in path:
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def mean_visits(paths: Sequence[Sequence[Coord]]) -> dict[Coord, float]:
    """Kafel -> srednia liczba wizyt **na partie**.

    Dzielimy przez liczbe sciezek, nie przez liczbe krokow, wiec wartosc czyta sie
    jako "ile razy persona stanela na tym kaflu w przecietnej partii". Powtorne
    wejscie w tej samej partii liczy sie osobno - inaczej heatmapa gubilaby
    zawracanie, ktore jest cala roznica miedzy personami.
    """

    if not paths:
        return {}
    return {cell: total / len(paths) for cell, total in cell_counts(paths).items()}


def average_visits(per_persona: Mapping[str, Sequence[Sequence[Coord]]]) -> dict[Coord, float]:
    """Srednia srednich po personach: kazda persona wazy tyle samo.

    Nie da sie tego zastapic `mean_visits` po zlaczonych sciezkach - persona
    z dluzszymi partiami zdominowalaby wynik, a pytanie brzmi "gdzie chodza
    persony", nie "gdzie chodzi wiekszosc krokow".
    """

    means = [mean_visits(paths) for paths in per_persona.values() if paths]
    if not means:
        return {}
    averaged: dict[Coord, float] = {}
    for single in means:
        for cell, value in single.items():
            averaged[cell] = averaged.get(cell, 0.0) + value
    return {cell: value / len(means) for cell, value in averaged.items()}
