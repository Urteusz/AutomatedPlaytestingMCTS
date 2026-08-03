"""Zapis i odczyt sladow przebytych partii (JSONL obok CSV z metrykami).

Jedna linia = jedna proba: persona, mapa, numer proby, odegrane akcje i kolejne
kafle bohatera. Silnik jest deterministyczny, wiec sama lista akcji wystarcza do
pelnego odtworzenia partii; `path` jest zapisany osobno, zeby agregacja (np.
heatmapa) nie musiala odgrywac tysiecy prob.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, IO, Iterable, Sequence

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
            record["path"] = [(int(row), int(column)) for row, column in record["path"]]
            unique[(record["persona"], record["map"], int(record["trial"]))] = record
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
