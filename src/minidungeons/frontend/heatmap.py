"""Heatmapa odwiedzin na planszy MiniDungeons 2.

Plansze rysuja funkcje z `game_loop`, wiec obraz mapy jest identyczny jak w grze.
Na wierzchu warstwa cieplna: srednia liczba wizyt bohatera na kaflu na jedna
partie. Podglad jest jednoekranowy, wybor zbioru, persony i skali idzie z linii
polecen.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import math
from pathlib import Path
import pygame

from minidungeons.domain import MiniDungeon
from minidungeons.domain.engine import WALL, Coord
from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR, RESULTS_DIR
from minidungeons.infrastructure.traces import (
    average_visits,
    load_traces,
    mean_visits,
    paths_by_persona,
    trace_path_for,
)

from minidungeons.frontend import game_loop as board

HUD_HEIGHT = 210
MIN_WINDOW_WIDTH = 720
FPS = 30

ALL_PERSONAS = "*"
PERSONA_CHOICES = (ALL_PERSONAS, *PERSONA_NAMES)
PERSONA_LABEL = {
    ALL_PERSONAS: "wszystkie persony (srednia)",
    "runner": "Runner",
    "monster_killer": "Monster Killer",
    "treasure_collector": "Treasure Collector",
    "completionist": "Completionist",
}
# persony w kolejnosci z artykulu, srednia na koncu
PERSONA_ROWS = (*PERSONA_NAMES, ALL_PERSONAS)
PERSONA_ROW_LABEL = {**PERSONA_LABEL, ALL_PERSONAS: "SREDNIA"}

SCALES = ("liniowa", "sqrt", "log")

# metryki Tabeli II: (kolumna CSV, naglowek, format)
STAT_COLUMNS = (
    ("monster_ratio", "potwory", "percent"),
    ("potion_ratio", "mikstury", "percent"),
    ("treasure_ratio", "skarby", "percent"),
    ("interactive_ratio", "interakt.", "percent"),
    ("health_left", "HP", "number"),
    ("turns", "tury", "number"),
)
STAT_NAME_WIDTH = 150
STAT_COLUMN_WIDTH = 74
STAT_LINE_HEIGHT = 16

HINT = ("1-9, 0, - : mapa,  strzalki <- -> : persona,  "
        "kursor nad kaflem: liczba wizyt,  Esc - koniec")

HEAT_STOPS = (
    (0.000, (250, 214, 210)),
    (0.167, (241, 174, 168)),
    (0.333, (228, 133, 126)),
    (0.500, (215, 88, 83)),
    (0.667, (177, 63, 60)),
    (0.833, (137, 43, 42)),
    (1.000, (98, 27, 26)),
)

COLOR_LEGEND_FRAME = (96, 96, 104)
COLOR_HOVER = (255, 255, 255)
COLOR_ACCENT = (255, 214, 0)

# po indeksie mapy w zbiorze, wiec dzialaja tez dla sladow z mniejsza liczba map
_ROW_KEYS = (
    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
    pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0, pygame.K_MINUS,
)
_KEYPAD_KEYS = (
    pygame.K_KP1, pygame.K_KP2, pygame.K_KP3, pygame.K_KP4, pygame.K_KP5,
    pygame.K_KP6, pygame.K_KP7, pygame.K_KP8, pygame.K_KP9, pygame.K_KP0,
    pygame.K_KP_MINUS,
)
MAP_KEYS = {
    key: index for keys in (_ROW_KEYS, _KEYPAD_KEYS) for index, key in enumerate(keys)
}


@dataclass
class Dataset:
    """Slady i wyniki jednego pliku CSV, wczytane raz przy starcie."""

    results_path: Path
    records: list[dict]
    won: dict[tuple[str, str, int], bool]
    rows: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.wins: dict[tuple[str, str], tuple[int, int]] = {}
        for (persona, map_name, _), value in self.won.items():
            for key in ((map_name, persona), (map_name, ALL_PERSONAS)):
                wins, games = self.wins.get(key, (0, 0))
                self.wins[key] = (wins + bool(value), games + 1)
        self.stats = aggregate_stats(self.rows)

    @property
    def label(self) -> str:
        return self.results_path.stem

    def map_names(self) -> list[str]:
        return sorted({record["map"] for record in self.records})


def aggregate_stats(rows: list[dict]) -> dict[tuple[str, str], dict[str, float]]:
    """Srednie metryk na (mapa, persona) oraz na (mapa, wszystkie persony).

    Srednia zbiorcza liczymy po probach, nie po srednich person."""

    totals: dict[tuple[str, str], dict[str, float]] = {}
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        for key in ((row["map"], row["persona"]), (row["map"], ALL_PERSONAS)):
            bucket = totals.setdefault(key, {column: 0.0 for column, _, _ in STAT_COLUMNS})
            for column, _, _ in STAT_COLUMNS:
                try:
                    bucket[column] += float(row[column])
                except (KeyError, TypeError, ValueError):
                    pass  # starszy CSV moze nie miec tej kolumny
            counts[key] = counts.get(key, 0) + 1
    return {
        key: {column: value / counts[key] for column, value in bucket.items()}
        for key, bucket in totals.items()
    }


def load_dataset(results_path: Path) -> Dataset:
    trace_path = trace_path_for(results_path)
    records = load_traces(trace_path)
    if not records:
        raise SystemExit(f"Plik ze sladami jest pusty: {trace_path}")
    rows = load_rows(results_path)
    return Dataset(results_path, records, load_outcomes(results_path), rows)


def load_rows(results_path: Path) -> list[dict]:
    """Wiersze CSV z wynikami. Brak pliku nie jest bledem, metryki sa wtedy puste."""

    if not results_path.exists():
        return []
    with results_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_outcomes(results_path: Path) -> dict[tuple[str, str, int], bool]:
    """(persona, mapa, proba) -> czy wygrana. Slad nie zapisuje wyniku partii."""

    return {
        (row["persona"], row["map"], int(row["trial"])): row["win"] in {"1", "True", "true"}
        for row in load_rows(results_path)
    }


def discover_results() -> list[Path]:
    """CSV z policzonymi wynikami, ktore maja obok siebie slady partii."""

    return [path for path in sorted(RESULTS_DIR.glob("*.csv")) if trace_path_for(path).exists()]


def selected_paths(
    dataset: Dataset, map_name: str, persona: str
) -> tuple[dict[Coord, float], int]:
    """Heatmapa i liczba partii, ktore do niej weszly.

    Dla jednej persony srednia po jej partiach, dla widoku zbiorczego srednia
    srednich, zeby persona z dluzszymi partiami nie przeslonila pozostalych."""

    records = [record for record in dataset.records if record["map"] == map_name]
    grouped = paths_by_persona(records, map_name=map_name)
    if persona == ALL_PERSONAS:
        used = sum(len(paths) for paths in grouped.values())
        return average_visits(grouped), used
    paths = grouped.get(persona, [])
    return mean_visits(paths), len(paths)


def win_rate(dataset: Dataset, map_name: str, persona: str) -> float | None:
    """Win rate z CSV, None gdy nie ma z czego liczyc."""

    wins, games = dataset.wins.get((map_name, persona), (0, 0))
    return wins / games if games else None


# warstwa cieplna --------

def heat_color(fraction: float) -> tuple[int, int, int]:
    """Interpolacja liniowa miedzy przystankami HEAT_STOPS."""

    fraction = min(max(fraction, 0.0), 1.0)
    for (low, low_color), (high, high_color) in zip(HEAT_STOPS, HEAT_STOPS[1:]):
        if fraction <= high:
            span = high - low
            local = 0.0 if span == 0 else (fraction - low) / span
            return tuple(  # type: ignore[return-value]
                round(start + (end - start) * local)
                for start, end in zip(low_color, high_color)
            )
    return HEAT_STOPS[-1][1]


def normalized(value: float, peak: float, scale: str) -> float:
    """Wizyty maja ciezki ogon, wiec skala liniowa splaszcza mape do jednego
    koloru. sqrt i log pokazuja roznice w slabo odwiedzanych rejonach."""

    if peak <= 0:
        return 0.0
    if scale == "sqrt":
        return math.sqrt(value / peak)
    if scale == "log":
        return math.log1p(value) / math.log1p(peak)
    return value / peak


def heat_render(screen, heat: dict[Coord, float], peak: float, scale: str) -> None:
    for cell, value in heat.items():
        pygame.draw.rect(
            screen, heat_color(normalized(value, peak, scale)), board.cell_rect(cell)
        )


def hud_top(env: MiniDungeon) -> int:
    """Pierwszy piksel HUD pod plansza."""

    return board.block_max_size * env.height + 6


def hovered_cell(position, env: MiniDungeon) -> Coord | None:
    """Kafel pod kursorem, tylko podloga. Sciana nie ma wizyt."""

    cell = board.cell_at(position, env)
    if cell is None or env.terrain[cell[0]][cell[1]] == WALL:
        return None
    return cell


def hover_render(screen, cell: Coord | None) -> None:
    if cell is not None:
        pygame.draw.rect(screen, COLOR_HOVER, board.cell_rect(cell), 2)


def legend_render(screen, peak: float, scale: str, top: int) -> None:
    bar = pygame.Rect(10, top, 260, 12)
    for offset in range(bar.width):
        fraction = offset / max(bar.width - 1, 1)
        column = pygame.Rect(bar.left + offset, bar.top, 1, bar.height)
        pygame.draw.rect(screen, heat_color(fraction), column)
    pygame.draw.rect(screen, COLOR_LEGEND_FRAME, bar, 1)
    screen.blit(board.font(19).render("0", True, board.COLOR_TEXT_DIM), (bar.left, bar.bottom + 2))
    peak_text = board.font(19).render(f"{peak:.1f} wizyt/partie", True, board.COLOR_TEXT_DIM)
    screen.blit(peak_text, peak_text.get_rect(topright=(bar.right, bar.bottom + 2)))
    screen.blit(
        board.font(19).render(f"skala {scale}", True, board.COLOR_TEXT_DIM),
        (bar.right + 14, bar.top - 2),
    )


def stat_text(dataset: Dataset, map_name: str, persona: str) -> list[str]:
    """Jeden wiersz tabeli: win rate i srednie metryki persony na tej mapie."""

    rate = win_rate(dataset, map_name, persona)
    cells = ["-" if rate is None else f"{rate:.0%}"]
    stats = dataset.stats.get((map_name, persona), {})
    for column, _, kind in STAT_COLUMNS:
        if column not in stats:
            cells.append("-")
        elif kind == "percent":
            cells.append(f"{stats[column]:.0%}")
        else:
            cells.append(f"{stats[column]:.1f}")
    return cells


def stats_render(screen, dataset: Dataset, map_name: str, view: "View", top: int) -> None:
    """Metryki wszystkich person i srednia. Wiersz pokazywanej heatmapy na zolto."""

    headers = ["win", *(header for _, header, _ in STAT_COLUMNS)]
    for index, header in enumerate(headers):
        text = board.font(18).render(header, True, board.COLOR_TEXT_DIM)
        screen.blit(text, text.get_rect(
            topright=(10 + STAT_NAME_WIDTH + (index + 1) * STAT_COLUMN_WIDTH, top)
        ))
    for row, persona in enumerate(PERSONA_ROWS):
        line = top + STAT_LINE_HEIGHT + row * STAT_LINE_HEIGHT
        shown = persona == view.persona
        color = COLOR_ACCENT if shown else board.COLOR_TEXT
        label = PERSONA_ROW_LABEL[persona] + (" <" if shown else "")
        screen.blit(board.font(18).render(label, True, color), (10, line))
        for index, cell in enumerate(stat_text(dataset, map_name, persona)):
            text = board.font(18).render(cell, True, color)
            screen.blit(text, text.get_rect(
                topright=(10 + STAT_NAME_WIDTH + (index + 1) * STAT_COLUMN_WIDTH, line)
            ))


def hud_render(
    screen,
    dataset: Dataset,
    env: MiniDungeon,
    view: "View",
    heat: dict[Coord, float],
    games: int,
    hovered: Coord | None,
) -> None:
    top = hud_top(env)
    peak = max(heat.values(), default=0.0)

    screen.blit(
        board.font(22).render(
            f"{view.map_name} ({env.height}x{env.width})   |   {dataset.label}   |   "
            f"heatmapa: {PERSONA_LABEL[view.persona]}",
            True, board.COLOR_TEXT,
        ),
        (10, top),
    )
    info = f"partie: {games}   kafli odwiedzonych: {len(heat)}   maks: {peak:.2f} wizyt/partie"
    if hovered is not None:
        value = heat.get(hovered, 0.0)
        info += f"   kafel {hovered}: {value:.2f}" + ("" if value else " (nieodwiedzony)")
    screen.blit(board.font(19).render(info, True, board.COLOR_TEXT), (10, top + 24))

    legend_render(screen, peak, view.scale, top + 48)
    stats_render(screen, dataset, view.map_name, view, top + 82)
    screen.blit(
        board.font(18).render(HINT, True, board.COLOR_TEXT_DIM),
        (10, top + 82 + (len(PERSONA_ROWS) + 1) * STAT_LINE_HEIGHT + 6),
    )


def empty_render(screen, width: int, height: int) -> None:
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((12, 12, 16, 200))
    screen.blit(overlay, (0, 0))
    text = board.font(34).render("brak partii dla tej mapy", True, (226, 180, 72))
    screen.blit(text, text.get_rect(center=(width // 2, height // 2)))


# petla podgladu ----------

@dataclass
class View:
    """Co wlasnie ogladamy."""

    dataset: Dataset
    map_index: int = 0
    persona: str = ALL_PERSONAS
    scale: str = SCALES[0]

    @property
    def map_name(self) -> str:
        names = self.dataset.map_names()
        return names[self.map_index % len(names)]

    def select_map(self, index: int) -> bool:
        """Wybor mapy po indeksie. Poza zakresem nic nie zmienia."""

        if 0 <= index < len(self.dataset.map_names()):
            self.map_index = index
            return True
        return False

    def cycle_persona(self, step: int) -> None:
        """Nastepna/poprzednia persona w kolejnosci z tabeli metryk.

        Kolejnosc jest ta sama co PERSONA_ROWS, wiec podswietlony wiersz HUD
        przesuwa sie zgodnie z tym, co pokazuje heatmapa."""

        try:
            index = PERSONA_ROWS.index(self.persona)
        except ValueError:  # persona z CSV, ktorej nie ma w kolejnosci artykulu
            index = len(PERSONA_ROWS) - 1
        self.persona = PERSONA_ROWS[(index + step) % len(PERSONA_ROWS)]


def main(argv: list[str] | None = None) -> None:
    """Punkt wejscia minidungeons-heatmap. Bez argumentow bierze pierwszy CSV
    z data/results, ktory ma obok slady partii."""

    args = build_parser().parse_args(argv)
    if args.results is not None:
        results_path = args.results
    else:
        found = discover_results()
        if not found:
            raise SystemExit(
                f"Nie znalazlem w {RESULTS_DIR} zadnego CSV ze sladami obok "
                "(*_paths.jsonl). Podaj plik przez --results."
            )
        results_path = found[0]
        for other in found[1:]:
            print(f"pomijam {other.name} - podaj go przez --results, jesli chcesz ten zbior")
    if args.tile_size:
        board.set_block_size(args.tile_size)

    dataset = load_dataset(Path(results_path))
    view = View(dataset, persona=args.persona or ALL_PERSONAS, scale=args.scale)
    if args.map:
        names = dataset.map_names()
        if args.map not in names:
            raise SystemExit(f"Mapy {args.map} nie ma w sladach; dostepne: {', '.join(names)}")
        view.map_index = names.index(args.map)

    print(f"{dataset.label}: {len(dataset.records)} sladow, {len(dataset.map_names())} map")

    pygame.init()
    try:
        run(view, fps=args.fps)
    finally:
        pygame.quit()


def run(view: View, *, fps: int = FPS) -> None:
    clock = pygame.time.Clock()
    screen = None
    size = (0, 0)
    environments: dict[str, MiniDungeon] = {}
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_ESCAPE, pygame.K_q}:
                    running = False
                elif event.key in MAP_KEYS:
                    view.select_map(MAP_KEYS[event.key])
                elif event.key in {pygame.K_RIGHT, pygame.K_TAB}:
                    view.cycle_persona(1)
                elif event.key == pygame.K_LEFT:
                    view.cycle_persona(-1)

        map_name = view.map_name
        if map_name not in environments:
            environments[map_name] = MiniDungeon(MD2_BENCHMARK_DIR / f"{map_name}.txt")
        env = environments[map_name]

        # map05 ma inne wymiary niz reszta
        wanted = (
            max(board.block_max_size * env.width, MIN_WINDOW_WIDTH),
            board.block_max_size * env.height + HUD_HEIGHT,
        )
        if screen is None or wanted != size:
            screen, size = pygame.display.set_mode(wanted), wanted
        pygame.display.set_caption(
            f"MiniDungeons 2 - heatmapa {view.dataset.label} - {map_name}"
        )

        heat, games = selected_paths(view.dataset, map_name, view.persona)
        peak = max(heat.values(), default=0.0)
        hovered = hovered_cell(pygame.mouse.get_pos(), env)

        screen.fill(board.COLOR_OUTLINE)
        board.background_render(screen, env)
        heat_render(screen, heat, peak, view.scale)
        board.object_layer_render(screen, env)
        board.npc_layer_render(screen, env)
        board.player_render(screen, env)  # start bohatera
        hover_render(screen, hovered)
        if not heat:
            empty_render(screen, size[0], board.block_max_size * env.height)
        hud_render(screen, view.dataset, env, view, heat, games, hovered)

        pygame.display.flip()
        clock.tick(fps)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Heatmapa odwiedzin person na planszy MiniDungeons 2.",
    )
    parser.add_argument(
        "--results", type=Path, default=None,
        help="CSV z wynikami; slady brane z pliku *_paths.jsonl obok. "
             "Bez tej opcji brany jest pierwszy taki CSV z data/results",
    )
    parser.add_argument("--map", default=None, help="mapa na start, np. map04")
    parser.add_argument("--persona", default=None, choices=PERSONA_CHOICES,
                        help=f"persona pokazywana na heatmapie; {ALL_PERSONAS} to srednia "
                             "po wszystkich (domyslnie). Tabela metryk zawsze pokazuje wszystkie")
    parser.add_argument("--scale", default=SCALES[0], choices=SCALES)
    parser.add_argument("--tile-size", type=int, default=None, help="rozmiar kafla w px")
    parser.add_argument("--fps", type=int, default=FPS)
    return parser


if __name__ == "__main__":
    main()
