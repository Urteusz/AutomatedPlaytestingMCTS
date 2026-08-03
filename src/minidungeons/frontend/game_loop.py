"""Reczna rozgrywka w zrekonstruowanym MiniDungeons 2 na PyGame.

Warstwy rysujemy wprost ze stanu silnika (terrain, objects, npcs,
javelin_position), a nie z render_plain(), bo siatka tekstowa gubi nakladajace
sie postacie oraz HP, moc bloba i licznik ogluszenia Minitaura. Akcje bierzemy
zawsze z legal_actions(), wiec front nie powtarza regul gry.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

try:
    import pygame
except ImportError as exc:  # zaleznosc opcjonalna, extras "gui"
    raise SystemExit("Frontend wymaga pygame-ce: pip install -e .[gui]") from exc

# importy absolutne, zeby plik dzialal tez uruchomiony wprost z IDE
from minidungeons.domain import Action, MiniDungeon
from minidungeons.domain.engine import (
    DIRECTION_DELTA,
    SYMBOL_BY_NPC_KIND,
    SYMBOL_BY_OBJECT,
    WALL,
    Coord,
    NPC,
)
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR

block_size = 40
block_gap = 1
block_max_size = block_size + block_gap

DEFAULT_MAP = MD2_BENCHMARK_DIR / "map01.txt"

HUD_HEIGHT = 104
MIN_WINDOW_WIDTH = 640
LOG_LINES = 2
FPS = 60
BLOCKED_FLASH_MS = 220

color_scheme = {
    "#": (0, 0, 0),
    "@": (63, 72, 204),
    "b": (34, 177, 76),
    "p": (255, 60, 89),
    "M": (128, 64, 0),
    "P": (15, 249, 250),
    "^": (74, 74, 74),
    "g": (153, 190, 37),
    "w": (91, 22, 33),
    "r": (232, 175, 41),
    "X": (57, 57, 57),
    "o": (110, 130, 42),
    "j": (115, 41, 23),
}
COLOR_FLOOR = (200, 200, 200)
COLOR_ENTRANCE = (156, 156, 166)
COLOR_TARGET = (255, 214, 0)
COLOR_BLOCKED = (208, 44, 44)
COLOR_OUTLINE = (18, 18, 20)
COLOR_TEXT = (236, 236, 236)
COLOR_TEXT_DIM = (152, 152, 160)
COLOR_HP_BAR = (214, 48, 62)
COLOR_HP_BAR_BACK = (70, 42, 46)
COLOR_PORTAL_LINK = (40, 96, 100)

MOVE_KEYS = {
    pygame.K_w: "N", pygame.K_UP: "N",
    pygame.K_s: "S", pygame.K_DOWN: "S",
    pygame.K_a: "W", pygame.K_LEFT: "W",
    pygame.K_d: "E", pygame.K_RIGHT: "E",
}

def set_block_size(size: int) -> None:
    """Ustawia rozmiar kafla dla calego modulu (opcja --tile-size)."""

    global block_size, block_max_size
    block_size = size
    block_max_size = size + block_gap


def cell_rect(cell: Coord) -> pygame.Rect:
    row, column = cell
    return pygame.Rect(column * block_max_size, row * block_max_size, block_size, block_size)


def cell_center(cell: Coord) -> tuple[float, float]:
    row, column = cell
    return (
        column * block_max_size + block_size / 2,
        row * block_max_size + block_size / 2,
    )


def cell_at(pos, env: MiniDungeon) -> Coord | None:
    """Piksel okna -> (wiersz, kolumna); None poza plansza, np. w pasku HUD."""

    column, row = pos[0] // block_max_size, pos[1] // block_max_size
    if 0 <= row < env.height and 0 <= column < env.width:
        return row, column
    return None



def check_npc(pos, env: MiniDungeon) -> NPC | None:
    """NPC pod kursorem. Dwa NPC nigdy nie stoja na jednym kaflu (kolizje
    i scalanie blobow rozwiazuje silnik), wiec indeks po pozycji wystarcza."""

    cell = cell_at(pos, env)
    if cell is None:
        return None
    for npc in env.npcs.values():
        if npc.position == cell:
            return npc
    return None


def throw_targets(env: MiniDungeon) -> dict[Coord, Action]:
    """Pozycja -> legalny rzut. Zrodlem jest legal_actions(), wiec front nie
    liczy linii wzroku ponownie i nie rozjedzie sie z silnikiem."""

    targets: dict[Coord, Action] = {}
    for action in env.legal_actions():
        if action.kind == "throw":
            npc = env.npcs.get(action.target_id)
            if npc is not None:
                targets[npc.position] = action
    return targets


def describe_event(event: dict) -> str | None:
    """Krotki opis zdarzenia ze step(); None dla szumu (ruchy i postoje NPC)."""

    kind = event.get("type")
    if kind == "hero_damaged":
        return f"-{event['amount']} HP ({event['source']})"
    if kind == "potion":
        return f"mikstura +{event['healed']} HP"
    if kind == "treasure":
        return "skarb otwarty"
    if kind == "trap":
        who = "bohater" if event.get("actor") == "hero" else f"NPC {event.get('actor_id')}"
        return f"pulapka: {who}"
    if kind == "teleport":
        return "portal" if event.get("actor") == "hero" else f"portal: NPC {event.get('actor_id')}"
    if kind == "portal_blocked":
        return "portal zablokowany"
    if kind == "javelin_throw":
        return f"rzut oszczepem w NPC {event['target_id']}"
    if kind == "javelin_pickup":
        return "oszczep podniesiony"
    if kind == "monster_slain":
        return f"{event['target_kind']} zabity"
    if kind == "minitaur_knockout":
        return f"Minitaur ogluszony na {event['stunned_actions']}"
    if kind == "blob_power_lost":
        return f"blob oslabiony do {event['power']}"
    if kind == "blob_merge":
        return f"bloby scalone (moc {event['power']})"
    if kind == "wizard_spell":
        return f"czar czarodzieja -{event['damage']} HP"
    if kind == "collision":
        return f"kolizja z {event.get('target_kind')}"
    if kind == "npc_collision":
        return f"kolizja NPC {event['mover_id']} z {event['occupant_id']}"
    if kind == "death":
        return "bohater zginal"
    if kind == "exit":
        return "wyjscie osiagniete"
    return None


# warstwy rysowania 

def background_render(screen, env: MiniDungeon):
    for row in range(env.height):
        for column in range(env.width):
            is_wall = env.terrain[row][column] == WALL
            color = color_scheme["#"] if is_wall else COLOR_FLOOR
            pygame.draw.rect(screen, color, cell_rect((row, column)))
    glyph_render(screen, env.entrance, "E", COLOR_ENTRANCE)
    for source, destination in env.portal_links.items():
        if source < destination:  # kazda para portali raz
            pygame.draw.line(
                screen, COLOR_PORTAL_LINK, cell_center(source), cell_center(destination), 1
            )


def object_layer_render(screen, env: MiniDungeon):
    """Skarby, mikstury, pulapki, portale i wyjscie - warstwa env.objects."""

    for cell, kind in env.objects.items():
        symbol = SYMBOL_BY_OBJECT[kind]
        color = color_scheme[symbol]
        rect = cell_rect(cell)
        if kind == "trap":
            pygame.draw.polygon(screen, color, [rect.midtop, rect.bottomleft, rect.bottomright])
        elif kind == "portal":
            pygame.draw.circle(screen, color, rect.center, block_size * 0.36, 2)
        elif kind == "potion":
            pygame.draw.circle(screen, color, rect.center, block_size * 0.28)
        else:
            pygame.draw.rect(screen, color, rect.inflate(-block_size * 0.3, -block_size * 0.3))
        if kind in {"exit", "treasure"}:
            glyph_render(screen, cell, symbol, COLOR_TEXT)


def javelin_render(screen, env: MiniDungeon):
    """Lezacy oszczep - render_plain() stawial tu 'j', ale NPC go nadpisywal."""

    if env.javelin_position is None:
        return
    rect = cell_rect(env.javelin_position)
    pygame.draw.line(
        screen, color_scheme["j"],
        (rect.left + block_size * 0.2, rect.bottom - block_size * 0.2),
        (rect.right - block_size * 0.2, rect.top + block_size * 0.2), 3,
    )


def npc_layer_render(screen, env: MiniDungeon):
    # initial_order to kolejnosc tur w silniku - daje deterministyczny rysunek
    for npc in sorted(env.npcs.values(), key=lambda value: value.initial_order):
        npc_render(screen, npc)


def npc_render(screen, npc: NPC):
    symbol = SYMBOL_BY_NPC_KIND[npc.kind]
    rect = cell_rect(npc.position).inflate(-block_size * 0.2, -block_size * 0.2)
    pygame.draw.rect(screen, color_scheme[symbol], rect)
    pygame.draw.rect(screen, COLOR_OUTLINE, rect, 1)
    glyph_render(screen, npc.position, symbol, COLOR_OUTLINE)
    badge_render(screen, npc)


def badge_render(screen, npc: NPC):
    """Stan potwora, ktorego siatka tekstowa nie oddaje: ogluszenie, moc, HP."""

    if npc.stunned_actions > 0:
        label = f"z{npc.stunned_actions}"
    elif npc.kind == "blob":
        label = str(npc.power)
    elif npc.kind == "ogre":
        label = f"{npc.hp}{'*' if npc.fancy else ''}"
    elif npc.hp is not None and npc.hp > 1:
        label = str(npc.hp)
    else:
        return
    text = font(max(11, int(block_size * 0.45))).render(label, True, COLOR_TEXT)
    rect = cell_rect(npc.position)
    screen.blit(text, text.get_rect(bottomright=(rect.right - 1, rect.bottom - 1)))


def player_render(screen, env: MiniDungeon):
    # kolo mniejsze od kafla, wiec ogluszony Minitaur pod bohaterem zostaje widoczny
    center = cell_center(env.hero_position)
    pygame.draw.circle(screen, color_scheme["@"], center, block_size * 0.3)
    pygame.draw.circle(screen, COLOR_OUTLINE, center, block_size * 0.3, 2)


def targets_render(screen, env: MiniDungeon, targets: dict[Coord, Action], active: Coord | None):
    for cell in targets:
        pygame.draw.rect(screen, COLOR_TARGET, cell_rect(cell), 3 if cell == active else 1)
    if active is not None:
        pygame.draw.line(
            screen, COLOR_TARGET, cell_center(env.hero_position), cell_center(active), 1
        )


def blocked_render(screen, cell: Coord | None):
    if cell is not None:
        pygame.draw.rect(screen, COLOR_BLOCKED, cell_rect(cell), 3)


def glyph_render(screen, cell: Coord, symbol: str, color):
    if block_size < 16:  # przy malym kaflu litery robia sie nieczytelne
        return
    text = font(max(12, int(block_size * 0.85))).render(symbol, True, color)
    screen.blit(text, text.get_rect(center=cell_center(cell)))


def hud_render(screen, env: MiniDungeon, log, targets: dict[Coord, Action]):
    metrics = env.metric_values()
    top = block_max_size * env.height + 8

    bar = pygame.Rect(10, top, 150, 14)
    pygame.draw.rect(screen, COLOR_HP_BAR_BACK, bar)
    filled = int(bar.width * env.hero_hp / env.PLAYER_MAX_HP)
    pygame.draw.rect(screen, COLOR_HP_BAR, pygame.Rect(bar.left, bar.top, filled, bar.height))

    javelin = "w rece" if env.javelin_held else f"na {env.javelin_position}"
    screen.blit(
        font(24).render(
            f"HP {env.hero_hp}/{env.PLAYER_MAX_HP}    oszczep: {javelin}    "
            f"cele: {len(targets)}    tura {metrics['turns']}  kroki {metrics['steps']}",
            True, COLOR_TEXT,
        ),
        (bar.right + 12, top - 2),
    )
    screen.blit(
        font(20).render(
            f"mikstury {metrics['potions']} ({metrics['potion_ratio']:.0%})   "
            f"skarby {metrics['treasures']} ({metrics['treasure_ratio']:.0%})   "
            f"potwory {metrics['monsters']} ({metrics['monster_ratio']:.0%})   "
            f"knockouty {metrics['minitaur_knockouts']}   pulapki {metrics['traps']}   "
            f"portale {metrics['teleports']}   rzuty {metrics['javelins']}",
            True, COLOR_TEXT,
        ),
        (10, top + 22),
    )
    screen.blit(
        font(20).render(
            "WSAD/strzalki - ruch,  klik lub Tab+Enter - rzut oszczepem,  R - restart,  Esc - koniec",
            True, COLOR_TEXT_DIM,
        ),
        (10, top + 42),
    )
    for index, entry in enumerate(log):
        screen.blit(font(20).render(entry, True, COLOR_TEXT_DIM), (10, top + 62 + index * 18))


def banner_render(screen, env: MiniDungeon, width: int):
    """Ekran konca gry - bez niego petla kreci sie dalej, a klawisze milcza."""

    map_height = block_max_size * env.height
    overlay = pygame.Surface((width, map_height), pygame.SRCALPHA)
    overlay.fill((12, 12, 16, 190))
    screen.blit(overlay, (0, 0))
    won = env.outcome == "exit"
    text = font(46).render("WYJSCIE" if won else "SMIERC", True,
                           (96, 220, 120) if won else (226, 72, 72))
    screen.blit(text, text.get_rect(center=(width // 2, map_height // 2 - 16)))
    hint = font(24).render("R - nowa proba,  Esc - wyjscie", True, COLOR_TEXT)
    screen.blit(hint, hint.get_rect(center=(width // 2, map_height // 2 + 24)))


_fonts: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    """Fonty tworzone raz - poprzednia wersja robila Font() w kazdej klatce."""

    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


# petla gry --------

def blocked_cell_for(action: Action, env: MiniDungeon) -> Coord | None:
    if action.kind != "move":
        return None
    row, column = env.hero_position
    delta_row, delta_column = DIRECTION_DELTA[action.direction]
    return row + delta_row, column + delta_column


def main(argv: list[str] | None = None) -> None:
    """Punkt wejscia `minidungeons-play` - dziala tez bez argumentow."""

    args = build_parser().parse_args(argv)
    if not args.map.exists():
        raise SystemExit(f"Nie znaleziono mapy: {args.map}")
    if args.tile_size:
        set_block_size(args.tile_size)

    # konstruktor sam czyta mape, reguly i portale - nic wiecej nie trzeba wolac
    env = MiniDungeon(args.map, rules_path=args.rules, portal_pairs_path=args.portal_pairs)
    print(f"Mapa: {args.map.name} ({env.height}x{env.width})  wejscie: {env.entrance}")

    pygame.init()
    try:
        run(env, fps=args.fps)
    finally:
        pygame.quit()


def run(env: MiniDungeon, *, fps: int = FPS) -> None:
    screen_width = max(block_max_size * env.width, MIN_WINDOW_WIDTH)
    screen_height = block_max_size * env.height + HUD_HEIGHT
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(f"MiniDungeons 2 - {env.map_path.name}")
    clock = pygame.time.Clock()

    log: deque[str] = deque(maxlen=LOG_LINES)
    targets = throw_targets(env)
    selected: Coord | None = None
    blocked_cell: Coord | None = None
    blocked_at = 0
    running = True

    while running:
        action: Action | None = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # KEYDOWN daje jedna akcje na zdarzenie; get_just_pressed() pozwalal
            # na dwa wcisniecia w jednej klatce (W+D konczylo sie ruchem na E)
            elif event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_ESCAPE, pygame.K_q}:
                    running = False
                elif event.key == pygame.K_r:
                    env.reset()
                    log.clear()
                    selected, blocked_cell = None, None
                    targets = throw_targets(env)
                elif event.key == pygame.K_TAB and targets:
                    cells = sorted(targets)
                    offset = -1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                    index = cells.index(selected) + offset if selected in cells else 0
                    selected = cells[index % len(cells)]
                elif event.key in MOVE_KEYS:
                    action = Action.move(MOVE_KEYS[event.key])
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                npc = check_npc(event.pos, env)
                cell = cell_at(event.pos, env)
                if npc is not None and npc.position in targets:
                    selected = npc.position
                    action = targets[npc.position]
                elif cell is not None:
                    # sciana, puste pole albo potwor bez linii wzroku
                    blocked_cell, blocked_at = cell, pygame.time.get_ticks()

        if action is not None and not env.done:
            if action in env.legal_actions():
                _, info = env.step(action)
                for event in info["events"]:
                    described = describe_event(event)
                    if described:
                        log.append(described)
                targets = throw_targets(env)
                if selected not in targets:
                    selected = None
            else:
                # nielegalny ruch nie moze byc cichy - mrugamy kaflem docelowym
                blocked_cell = blocked_cell_for(action, env)
                blocked_at = pygame.time.get_ticks()

        if blocked_cell is not None and pygame.time.get_ticks() - blocked_at > BLOCKED_FLASH_MS:
            blocked_cell = None

        hovered = cell_at(pygame.mouse.get_pos(), env)
        active = hovered if hovered in targets else selected

        screen.fill(COLOR_OUTLINE)
        background_render(screen, env)
        object_layer_render(screen, env)
        javelin_render(screen, env)
        targets_render(screen, env, targets, active)
        npc_layer_render(screen, env)
        player_render(screen, env)
        blocked_render(screen, blocked_cell)
        hud_render(screen, env, log, targets)
        if env.done:
            banner_render(screen, env, screen_width)

        pygame.display.flip()
        clock.tick(fps)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reczna rozgrywka w MiniDungeons 2.")
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--rules", type=Path, default=None, help="alternatywny plik regul")
    parser.add_argument("--portal-pairs", type=Path, default=None, help="metadane portali")
    parser.add_argument("--tile-size", type=int, default=None, help="rozmiar kafla w px")
    parser.add_argument("--fps", type=int, default=FPS)
    return parser


if __name__ == "__main__":
    main()
