"""Generator map w stylu MD2 do treningu RL bez map benchmarku.

Pokoje z rekurencyjnego podzialu (sciany z przejsciami, jak w map01), potem
pojedyncze sciany dosypywane do docelowej gestosci tylko wtedy, gdy teren zostaje
spojny. Wymiary, odsetek otwartych pol i liczby obiektow z zakresow 11 map
benchmarku; wyjscie co najmniej w polowie najdluzszego dystansu od wejscia.
"""

from __future__ import annotations

import random
from collections import deque

Cell = tuple[int, int]
# symbol: (min, max) liczby na mapie, zakresy z benchmarku
COUNTS = {"g": (1, 7), "w": (1, 6), "b": (1, 3), "o": (0, 2), "p": (2, 8), "r": (2, 8),
          "^": (0, 3)}


def generate(seed: int) -> tuple[list[str], list[tuple[Cell, Cell]]]:
    """Wiersze mapy i pary portali dla danego ziarna."""

    rng = random.Random(seed)
    height, width = (20, 10) if rng.random() < 0.8 else (rng.randint(12, 16), 11)
    grid = [["#"] * width for _ in range(height)]
    for row in range(1, height - 1):
        for column in range(1, width - 1):
            grid[row][column] = "."
    _divide(grid, rng, 1, 1, height - 2, width - 2)
    _fill(grid, rng, rng.uniform(0.35, 0.62))
    open_cells = [(r, c) for r in range(height) for c in range(width) if grid[r][c] == "."]
    entrance = rng.choice(open_cells)
    distance = _distances(grid, entrance)
    far = max(distance.values())
    exit_ = rng.choice([cell for cell, steps in distance.items() if steps >= max(far // 2, 1)])
    grid[entrance[0]][entrance[1]], grid[exit_[0]][exit_[1]] = "E", "X"
    free = [cell for cell in open_cells if cell not in (entrance, exit_)]
    rng.shuffle(free)
    symbols = ["M"] + [symbol for symbol, (low, high) in COUNTS.items()
                       for _ in range(rng.randint(low, high))]
    pairs: list[tuple[Cell, Cell]] = []
    if rng.random() < 0.6 and len(free) > len(symbols) + 2:
        pairs = [(free.pop(), free.pop())]
        for row, column in pairs[0]:
            grid[row][column] = "P"
    for symbol, (row, column) in zip(symbols, free, strict=False):
        grid[row][column] = symbol
    return ["".join(line) for line in grid], pairs


def _divide(grid: list[list[str]], rng: random.Random, top: int, left: int, bottom: int,
            right: int) -> None:
    height, width = bottom - top + 1, right - left + 1
    if (height < 3 and width < 3) or (rng.random() < 0.15 and height * width < 30):
        return
    horizontal = height > width if height != width else rng.random() < 0.5
    if horizontal and height >= 3:
        row = rng.randint(top + 1, bottom - 1)
        doors = set(rng.sample(range(left, right + 1), min(width, rng.randint(1, 2))))
        for column in range(left, right + 1):
            if column not in doors and not _is_door(grid, row, column, vertical=False):
                grid[row][column] = "#"
        _divide(grid, rng, top, left, row - 1, right)
        _divide(grid, rng, row + 1, left, bottom, right)
    elif width >= 3:
        column = rng.randint(left + 1, right - 1)
        doors = set(rng.sample(range(top, bottom + 1), min(height, rng.randint(1, 2))))
        for row in range(top, bottom + 1):
            if row not in doors and not _is_door(grid, row, column, vertical=True):
                grid[row][column] = "#"
        _divide(grid, rng, top, left, bottom, column - 1)
        _divide(grid, rng, top, column + 1, bottom, right)


def _is_door(grid: list[list[str]], row: int, column: int, *, vertical: bool) -> bool:
    """Nowa sciana nie zamyka przejscia w scianie prostopadlej."""

    ends = ((row - 1, column), (row + 1, column)) if vertical else ((row, column - 1),
                                                                   (row, column + 1))
    return any(grid[r][c] == "." and _between_walls(grid, r, c, vertical) for r, c in ends)


def _between_walls(grid: list[list[str]], row: int, column: int, vertical: bool) -> bool:
    if vertical:
        return grid[row][column - 1] == "#" and grid[row][column + 1] == "#"
    return grid[row - 1][column] == "#" and grid[row + 1][column] == "#"


def _fill(grid: list[list[str]], rng: random.Random, target: float) -> None:
    cells = [(r, c) for r in range(len(grid)) for c in range(len(grid[0]))]
    open_cells = [cell for cell in cells if grid[cell[0]][cell[1]] == "."]
    rng.shuffle(open_cells)
    total = len(cells)
    count = len(open_cells)
    for row, column in open_cells:
        if count / total <= target:
            break
        grid[row][column] = "#"
        if _connected(grid, count - 1):
            count -= 1
        else:
            grid[row][column] = "."


def _connected(grid: list[list[str]], count: int) -> bool:
    start = next((r, c) for r in range(len(grid)) for c in range(len(grid[0]))
                 if grid[r][c] != "#")
    return len(_distances(grid, start)) == count


def _distances(grid: list[list[str]], start: Cell) -> dict[Cell, int]:
    distance = {start: 0}
    queue = deque([start])
    while queue:
        row, column = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cell = (row + dr, column + dc)
            if cell not in distance and grid[cell[0]][cell[1]] != "#":
                distance[cell] = distance[(row, column)] + 1
                queue.append(cell)
    return distance
