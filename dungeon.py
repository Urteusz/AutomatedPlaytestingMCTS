"""
Rdzeń srodowiska MiniDungeons (baza pod MD2).

Na tym etapie: siatka, hero, ruch w 4 kierunkach, kolizje, podstawowe
obiekty (skarb, potion, potwor, wyjscie) i zliczanie metryk.

"""

from dataclasses import dataclass

# symbole na mapie
WALL = "#"
EMPTY = "."
ENTRANCE = "E"
EXIT = "X"
TREASURE = "r"
POTION = "p"
MONSTER = "m"

# (dy, dx)
DIRECTIONS = {
    0: (-1, 0),  # gora
    1: (1, 0),   # dol
    2: (0, 1),   # prawo
    3: (0, -1),  # lewo
}

DIR_NAMES = {0: "N", 1: "S", 2: "E", 3: "W"}


@dataclass
class Metrics:
    """Metryki playthrough - odpowiednik Tabeli I z papera (uproszczony)."""
    steps_taken: int = 0
    treasures_opened: int = 0
    potions_drunk: int = 0
    monsters_slain: int = 0
    reached_exit: bool = False
    died: bool = False

    def as_dict(self):
        return {
            "steps": self.steps_taken,
            "treasures": self.treasures_opened,
            "potions": self.potions_drunk,
            "monsters": self.monsters_slain,
            "reached_exit": self.reached_exit,
            "died": self.died,
        }


class MiniDungeon:
    """Stan pojedynczej rozgrywki na jednej mapie."""

    PLAYER_MAX_HP = 40

    def __init__(self, map_path):
        self.grid = self._load_map(map_path)
        self.height = len(self.grid)
        self.width = len(self.grid[0])
        self._find_entrance_and_exit()
        self.reset()

    def _load_map(self, path):
        with open(path) as f:
            return [list(line.rstrip("\n")) for line in f if line.strip()]

    def _find_entrance_and_exit(self):
        self.entrance = self.exit = None
        for y, row in enumerate(self.grid):
            for x, tile in enumerate(row):
                if tile == ENTRANCE:
                    self.entrance = (y, x)
                elif tile == EXIT:
                    self.exit = (y, x)
        if self.entrance is None:
            raise ValueError("Mapa nie ma wejscia (E)")
        if self.exit is None:
            raise ValueError("Mapa nie ma wyjscia (r)")

    def reset(self):
        """Ustawia hero na wejsciu, kopiuje mape (zeby nie niszczyc oryginalu)."""
        self.tiles = [row[:] for row in self.grid]
        self.y, self.x = self.entrance
        self.hp = self.PLAYER_MAX_HP
        self.metrics = Metrics()
        self.done = False
        return self._state()

    def _state(self):
        return {"y": self.y, "x": self.x, "hp": self.hp, "done": self.done}

    def legal_moves(self):
        """Kierunki, w ktore mozna sie ruszyc (nie sciana, nie poza mapa)."""
        moves = []
        for d, (dy, dx) in DIRECTIONS.items():
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < self.height and 0 <= nx < self.width:
                if self.tiles[ny][nx] != WALL:
                    moves.append(d)
        return moves

    def step(self, direction):
        """Wykonuje jeden ruch. Zwraca (state, info_o_ruchu)."""
        if self.done:
            return self._state(), {"event": "already_done"}

        dy, dx = DIRECTIONS[direction]
        ny, nx = self.y + dy, self.x + dx

        if not (0 <= ny < self.height and 0 <= nx < self.width):
            return self._state(), {"event": "wall", "dir": DIR_NAMES[direction]}
        target = self.tiles[ny][nx]
        if target == WALL:
            return self._state(), {"event": "wall", "dir": DIR_NAMES[direction]}

        self.y, self.x = ny, nx
        self.metrics.steps_taken += 1
        event = "move"

        # interakcja z obiektem na docelowym polu
        if target == TREASURE:
            self.metrics.treasures_opened += 1
            self.tiles[ny][nx] = EMPTY
            event = "treasure"
        elif target == POTION:
            self.metrics.potions_drunk += 1
            self.hp = min(self.PLAYER_MAX_HP, self.hp + 10)
            self.tiles[ny][nx] = EMPTY
            event = "potion"
        elif target == MONSTER:
            self.metrics.monsters_slain += 1
            self.hp -= 10
            self.tiles[ny][nx] = EMPTY
            event = "monster"
            if self.hp <= 0:
                self.metrics.died = True
                self.done = True
                event = "died"
        elif target == EXIT:
            self.metrics.reached_exit = True
            self.done = True
            event = "exit"

        return self._state(), {"event": event, "dir": DIR_NAMES[direction]}

    GLYPHS = {
        WALL:     "█",
        EMPTY:    "·",
        ENTRANCE: "E",
        EXIT:     "X",
        TREASURE: "r",
        POTION:   "p",
        MONSTER:  "m",
    }
    HERO_GLYPH = "@"

    def render(self):
        """Rysuje mape w ASCII z hero jako '@', kafelki rozdzielone spacja."""
        col_header = "     " + " ".join(f"{x:>1}" for x in range(self.width))
        sep = "    +" + "-" * (2 * self.width + 1) + "+"
        rows = []
        for y, row in enumerate(self.tiles):
            cells = []
            for x, tile in enumerate(row):
                if (y, x) == (self.y, self.x):
                    cells.append(self.HERO_GLYPH)
                else:
                    cells.append(self.GLYPHS.get(tile, tile))
            rows.append(f" {y:>2} | " + " ".join(cells) + " |")
        header = f"HP: {self.hp}/{self.PLAYER_MAX_HP}  pos:({self.y},{self.x})  done:{self.done}"
        return "\n".join([header, col_header, sep, *rows, sep])
