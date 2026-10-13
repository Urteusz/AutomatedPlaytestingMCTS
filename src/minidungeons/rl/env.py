"""Srodowisko Gymnasium dla MiniDungeons 2 - PPO gra ta sama gra co MCTS.

Nagroda to przyrost utility persony (eq. 2-5) w tej samej konwencji co MCTS:
PE = 1 - dystans_BFS/maks (portale wedlug `pe_portals`), IC wedlug `ic_mode`,
kara za smierc z `personas.json`. Suma nagrod w epizodzie jest wiec rowna
`U(koniec) - U(start)`, czyli fitnessowi GP z dokladnoscia do stalej mapy.
`win_bonus` (domyslnie 0) dodaje nagrode za wejscie na wyjscie: utility z ciaglym
PE prawie nie odroznia stania obok wyjscia od wygranej, a MCTS wygrywa tylko
dlatego, ze protokol konczy gre na pierwszym wezle z wyjsciem.
`augment` losuje przy `reset()` symetrie mapy treningowej (odbicia i transpozycje,
8 ukladow), bez siegania do map testowych.
`generated` to udzial map z `rl/mapgen.py` (nazwa `genN`, N = ziarno) w losowaniu przy
`reset()` - trening bez zadnej mapy benchmarku. Pamiec trzyma najwyzej `GENERATED_CACHE`
takich map.
`max_wait` (None = wylaczone) usuwa petle bez postepu. Postep to zmiana HP,
przedmiotow albo potworow; do nastepnego postepu akcja prowadzaca do stanu swiata
juz odwiedzonego jest zaslaniana, a gdy innych nie ma, zostaje ta do stanu
odwiedzonego najdawniej (wyjscie ze slepego zaulka). Gra jest deterministyczna,
wiec powtorzony stan niczego nie daje, a stanow jest skonczenie wiele - kazda petla
sie konczy. Gra nie ma akcji "czekaj", wiec krok tam i z powrotem, gdy potwory sie
ruszaja, jest nowym stanem i jest dozwolony - ale najwyzej `max_wait` razy z rzedu.
`shield` (0 = wylaczona) zaslania akcje, po ktorych bohater ginie w kazdej
kontynuacji krotszej niz `shield` ruchow - przeszukanie modelem gry jak w MCTS,
tylko plytkie. Gdy zginac trzeba w kazdym wariancie, zostaja wszystkie akcje.

Obserwacja to wycinek `EGO`x`EGO` wysrodkowany na bohaterze, uint8. Z kazdego pola
widac cala mape (do 20x20), a "pole na polnoc od bohatera" jest zawsze w tym samym
miejscu tensora - siec uczy sie regul ruchu, a nie tras na konkretnych mapach.
Rzut oszczepem celuje w pole wzgledem bohatera (`4 + i*EGO + j`), a nie w numer NPC -
numer znaczy co innego na kazdej mapie.
Nielegalne akcje zaslania `action_masks()` (MaskablePPO); maska jest tez w `info`,
zeby wektorowe srodowisko nie pytalo o nia osobnym rundtripem.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import gymnasium as gym
import numpy as np

from minidungeons.domain.engine import DIRECTION_DELTA, WALL, Action, MiniDungeon
from minidungeons.domain.gp_fitness import TRAINING_MAP_NAMES, exit_distances
from minidungeons.domain.personas import PERSONA_NAMES, utility_from_metrics
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR
from minidungeons.rl.mapgen import generate

RADIUS = 19  # mapa ma najwyzej 20 pol w kazdym kierunku (takze po transpozycji)
EGO = 2 * RADIUS + 1
TOP = 255  # wartosc "obecnosci" w uint8
GENERATED_CACHE = 64
DIRECTIONS = tuple(DIRECTION_DELTA)  # N, E, S, W - indeksy akcji 0-3
MOVE_ACTIONS = len(DIRECTIONS)
SYMMETRIES = ("", "v", "h", "vh", "t", "tv", "th", "tvh")

NPC_CHANNELS = ("goblin", "wizard", "blob", "ogre", "minitaur")
OBJECT_CHANNELS = ("exit", "treasure", "potion", "portal", "trap")
# wartosc 1 = obecnosc; blob = sila/3, ogre = HP/2, minitaur_stun = ogluszenie/3,
# proximity = PE pola (kompas do wyjscia), hero_hp i javelin_held wypelniaja cala plansze
# poza mapa = sciana; bohater zawsze w srodku, wiec bez kanalu
CHANNELS = ("wall", *OBJECT_CHANNELS, *NPC_CHANNELS, "minitaur_stun",
            "javelin", "proximity", "hero_hp", "javelin_held")


class MiniDungeonsEnv(gym.Env[np.ndarray, int]):
    """Jedna persona, losowa mapa z `maps` przy kazdym `reset()` (albo `options["map"]`)."""

    metadata: ClassVar[dict[str, Any]] = {"render_modes": ["ansi"]}

    def __init__(
        self,
        persona: str,
        maps: tuple[str, ...] = TRAINING_MAP_NAMES,
        *,
        max_steps: int = 500,
        pe_portals: str = "on",
        ic_mode: str = "mean3",
        win_bonus: float = 0.0,
        augment: bool = False,
        max_wait: int | None = None,
        shield: int = 0,
        generated: float = 0.0,
        render_mode: str | None = None,
    ) -> None:
        if persona not in PERSONA_NAMES:
            raise ValueError(f"Nieznana persona {persona!r}; mam: {PERSONA_NAMES}")
        if pe_portals not in ("on", "off"):
            raise ValueError(f"pe_portals musi byc 'on' albo 'off', jest {pe_portals!r}")
        if ic_mode not in ("mean3", "combined"):
            raise ValueError(f"ic_mode musi byc 'mean3' albo 'combined', jest {ic_mode!r}")
        if shield < 0:
            raise ValueError("shield musi byc nieujemne")
        if max_steps < 1:
            raise ValueError("max_steps musi wynosic co najmniej 1")
        self.persona = persona
        self.map_names = tuple(maps)
        self.max_steps = max_steps
        self.pe_portals = pe_portals
        self.ic_mode = ic_mode
        self.win_bonus = win_bonus
        self.augment = augment
        self.max_wait = max_wait
        self.shield = shield
        self.generated = generated
        self.render_mode = render_mode
        self.channel = {name: index for index, name in enumerate(CHANNELS)}
        self.observation_space = gym.spaces.Box(0, TOP, shape=(len(CHANNELS), EGO, EGO),
                                                dtype=np.uint8)
        self.action_count = MOVE_ACTIONS + EGO * EGO
        self.action_space = gym.spaces.Discrete(self.action_count)
        self._levels: dict[str, tuple[MiniDungeon, np.ndarray, dict]] = {}
        self.env: MiniDungeon | None = None
        self.map_name: str | None = None
        self._utility = 0.0
        self._came_from: tuple[int, int] | None = None
        self._waited = 0
        self._seen: dict[tuple, int] = {}
        self._mask: np.ndarray | None = None
        self._children: dict[int, MiniDungeon] = {}

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        name = (options or {}).get("map")
        if name is None and self.generated and self.np_random.random() < self.generated:
            name = f"gen{int(self.np_random.integers(2**31))}"
        elif name is None:
            name = self.map_names[int(self.np_random.integers(len(self.map_names)))]
            if self.augment:
                symmetry = SYMMETRIES[int(self.np_random.integers(len(SYMMETRIES)))]
                name = f"{name}:{symmetry}" if symmetry else name
        environment, _, _ = self._level(name)
        environment.reset()
        self.env, self.map_name = environment, name
        self._utility = self.utility()
        self._came_from, self._waited = None, 0
        self._seen = {self._world(): environment.metrics.turns_taken}
        self._mask, self._children = None, {}
        return self._observation(), self._info()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        environment = self._require_env()
        position, progress, came_from = environment.hero_position, self._progress(), self._came_from
        child = self._children.get(int(action))
        if child is None:
            environment.step(self.decode(int(action)))
        else:
            self.env = environment = child  # stan po tej akcji policzyla juz maska petli
        self._mask, self._children = None, {}
        if progress != self._progress():
            self._seen.clear()
        returned = environment.hero_position == came_from
        self._waited = self._waited + 1 if returned and self._seen else 0
        self._came_from = position
        self._seen[self._world()] = environment.metrics.turns_taken
        utility = self.utility()
        reward = utility - self._utility
        self._utility = utility
        terminated = environment.done
        if environment.metrics.reached_exit:
            reward += self.win_bonus
        truncated = not terminated and environment.metrics.turns_taken >= self.max_steps
        return self._observation(), float(reward), terminated, truncated, self._info()

    def action_masks(self) -> np.ndarray:
        """Maska legalnych akcji dla `sb3_contrib.MaskablePPO`."""

        if self.env is None:
            return np.zeros(self.action_count, dtype=bool)
        if self._mask is None:
            mask = np.zeros(self.action_count, dtype=bool)
            for action in self.env.legal_actions():
                mask[self.encode(action)] = True
            if self.shield and mask.sum() > 1:
                mask = self._mask_deaths(mask)
            if self.max_wait is not None and mask.sum() > 1:
                mask = self._mask_loops(mask)
            self._mask = mask
        return self._mask

    def _child(self, index: int) -> MiniDungeon:
        child = self._children.get(index)
        if child is None:
            child = self._require_env().clone()
            child.step(self.decode(index))
            self._children[index] = child
        return child

    def _mask_deaths(self, mask: np.ndarray) -> np.ndarray:
        safe = mask.copy()
        for index in map(int, np.flatnonzero(mask)):
            safe[index] = _survives(self._child(index), self.shield - 1)
        return safe if safe.any() else mask

    def _mask_loops(self, mask: np.ndarray) -> np.ndarray:
        environment = self._require_env()
        row, column = environment.hero_position
        last_visit: dict[int, int] = {}  # akcja -> tura ostatniej wizyty w stanie po niej
        for index in map(int, np.flatnonzero(mask)):
            child = self._child(index)
            waiting = index < MOVE_ACTIONS and self._waited >= (self.max_wait or 0) and (
                row + DIRECTION_DELTA[DIRECTIONS[index]][0],
                column + DIRECTION_DELTA[DIRECTIONS[index]][1]) == self._came_from
            seen = self._seen.get(self._world(child)) if not child.done else None
            if waiting or seen is not None:
                last_visit[index] = seen if seen is not None else -1
        fresh = mask.copy()
        fresh[list(last_visit)] = False
        if fresh.any():
            return fresh
        oldest = min(last_visit.values())
        fresh[[index for index, turn in last_visit.items() if turn == oldest]] = True
        return fresh

    def _world(self, environment: MiniDungeon | None = None) -> tuple:
        # state_key bez licznikow tur i krokow, ktore rosna zawsze
        return (environment or self._require_env()).state_key()[:6]

    def _progress(self) -> tuple:
        environment = self._require_env()
        return (environment.hero_hp, tuple(sorted(environment.objects.items())),
                tuple((npc.npc_id, npc.hp, npc.power) for npc in environment.npcs.values()))

    def render(self) -> str | None:
        if self.render_mode == "ansi" and self.env is not None:
            return self.env.render()
        return None

    def _origin(self) -> tuple[int, int]:
        """Pole mapy w lewym gornym rogu obserwacji."""

        row, column = self._require_env().hero_position
        return row - RADIUS, column - RADIUS

    def encode(self, action: Action) -> int:
        if action.kind == "move":
            return DIRECTIONS.index(action.direction or "")
        row, column = self._require_env().npcs[int(action.target_id or 0)].position
        top, left = self._origin()
        return MOVE_ACTIONS + (row - top) * EGO + (column - left)

    def decode(self, index: int) -> Action:
        if not 0 <= index < self.action_count:
            raise ValueError(f"Akcja {index} poza zakresem 0..{self.action_count - 1}")
        if index < MOVE_ACTIONS:
            return Action.move(DIRECTIONS[index])
        top, left = self._origin()
        row, column = divmod(index - MOVE_ACTIONS, EGO)
        target = (row + top, column + left)
        # przy dwoch NPC na jednym polu (nie powinno sie zdarzac) cel o nizszym numerze
        for npc in sorted(self._require_env().npcs.values(), key=lambda value: value.npc_id):
            if npc.position == target:
                return Action.throw(npc.npc_id)
        raise ValueError(f"Rzut w pole {target} bez NPC")

    def utility(self) -> float:
        """Utility persony w konwencji MCTS (PE BFS wedlug `pe_portals`, IC wedlug `ic_mode`)."""

        environment = self._require_env()
        _, _, static = self._level(self.map_name or "")
        metrics = environment.metric_values()
        metrics["proximity_to_exit"] = self._proximity(environment.hero_position, static)
        if self.ic_mode == "mean3":
            metrics["interactive_ratio"] = (
                float(metrics["monster_ratio"]) + float(metrics["potion_ratio"])
                + float(metrics["treasure_ratio"])
            ) / 3.0
        return utility_from_metrics(self.persona, metrics)

    @staticmethod
    def _proximity(position: tuple[int, int], static: dict) -> float:
        distance = static["distances"].get(position)
        if distance is None:
            return 0.0
        if not static["span"]:
            return 1.0
        return 1.0 - distance / static["span"]

    def _level(self, name: str) -> tuple[MiniDungeon, np.ndarray, dict]:
        """Silnik mapy, statyczne kanaly na planszy z marginesem `RADIUS` i dystanse PE."""

        if name not in self._levels:
            generated = [key for key in self._levels if key.startswith("gen")]
            if name.startswith("gen") and len(generated) >= GENERATED_CACHE:
                del self._levels[generated[0]]
            environment = _load_level(name)
            height, width = environment.height, environment.width
            if max(height, width) > RADIUS + 1:
                raise ValueError(f"{name}: {height}x{width} wieksza niz {RADIUS + 1} pol")
            distances = exit_distances(environment, self.pe_portals)
            static = {"distances": distances, "span": max(distances.values(), default=0)}
            base = np.zeros((len(CHANNELS), height + 2 * RADIUS, width + 2 * RADIUS),
                            dtype=np.uint8)
            base[self.channel["wall"]] = TOP
            for row in range(height):
                for column in range(width):
                    cell = (row + RADIUS, column + RADIUS)
                    if environment.terrain[row][column] != WALL:
                        base[(self.channel["wall"], *cell)] = 0
                        base[(self.channel["proximity"], *cell)] = (
                            self._proximity((row, column), static) * TOP)
            self._levels[name] = (environment, base, static)
        return self._levels[name]

    def _observation(self) -> np.ndarray:
        environment = self._require_env()
        _, base, _ = self._level(self.map_name or "")
        top, left = self._origin()
        # w planszy z marginesem pole (r, c) mapy lezy na (r + RADIUS, c + RADIUS),
        # wiec wycinek zaczyna sie na polu bohatera
        row, column = environment.hero_position
        observation = base[:, row:row + EGO, column:column + EGO].copy()
        channel, scale = self.channel, TOP

        def put(name: str, position: tuple[int, int], value: float = 1.0) -> None:
            observation[channel[name], position[0] - top, position[1] - left] = value * scale

        for position, kind in environment.objects.items():
            if kind in channel:
                put(kind, position)
        for npc in environment.npcs.values():
            if npc.kind == "blob":
                put("blob", npc.position, min(npc.power / 3.0, 1.0))
            elif npc.kind == "ogre":
                put("ogre", npc.position, min((npc.hp or 0) / 2.0, 1.0))
            else:
                put(npc.kind, npc.position)
                if npc.kind == "minitaur":
                    put("minitaur_stun", npc.position, min(npc.stunned_actions / 3.0, 1.0))
        if environment.javelin_position is not None:
            put("javelin", environment.javelin_position)
        observation[channel["hero_hp"]] = environment.hero_hp / environment.PLAYER_MAX_HP * scale
        observation[channel["javelin_held"]] = scale if environment.javelin_held else 0
        return observation

    def _info(self) -> dict[str, Any]:
        environment = self._require_env()
        info = {
            "map": self.map_name,
            "utility": self._utility,
            "win": bool(environment.metrics.reached_exit),
            "died": bool(environment.metrics.died),
            "turns": environment.metrics.turns_taken,
        }
        if environment.done or environment.metrics.turns_taken >= self.max_steps:
            info["metrics"] = environment.metric_values()
        else:
            info["action_mask"] = self.action_masks()
        return info

    def _require_env(self) -> MiniDungeon:
        if self.env is None:
            raise RuntimeError("Wywolaj reset() przed uzyciem srodowiska")
        return self.env


def _survives(environment: MiniDungeon, depth: int) -> bool:
    if environment.metrics.died:
        return False
    if depth == 0 or environment.done:
        return True
    for action in environment.legal_actions():
        child = environment.clone()
        child.step(action)
        if _survives(child, depth - 1):
            return True
    return False


def _load_level(name: str) -> MiniDungeon:
    """`mapNN` albo `mapNN:sym` (t = transpozycja, potem v/h = odbicia); przeksztalcona
    mapa idzie przez plik tymczasowy i jawne pary portali."""

    base, _, symmetry = name.partition(":")
    if base.startswith("gen"):
        rows, pairs = generate(int(base[3:]))
        return _from_rows(name, rows, pairs)
    path = Path(MD2_BENCHMARK_DIR) / f"{base}.txt"
    if not symmetry:
        return MiniDungeon(path)
    if symmetry not in SYMMETRIES:
        raise ValueError(f"Nieznana symetria {symmetry!r}; mam: {SYMMETRIES[1:]}")
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if "t" in symmetry:
        rows = ["".join(column) for column in zip(*rows, strict=True)]
    height, width = len(rows), len(rows[0])

    def move(cell: list[int]) -> tuple[int, int]:
        row, column = (cell[1], cell[0]) if "t" in symmetry else cell
        return (height - 1 - row if "v" in symmetry else row,
                width - 1 - column if "h" in symmetry else column)

    if "v" in symmetry:
        rows = rows[::-1]
    if "h" in symmetry:
        rows = [row[::-1] for row in rows]
    portal_file = Path(MD2_BENCHMARK_DIR) / "portal_pairs.json"
    portals = json.loads(portal_file.read_text(encoding="utf-8"))["maps"].get(base, [])
    pairs = [(move(a), move(b)) for a, b in portals]
    return _from_rows(f"{base}_{symmetry}", rows, pairs)


def _from_rows(name: str, rows: list[str], pairs: list) -> MiniDungeon:
    # plik na proces: na Windows zastepowanie pliku czytanego przez inny proces sie nie udaje;
    # silnik czyta go tylko w konstruktorze
    folder = Path(tempfile.gettempdir()) / "minidungeons_flips"
    folder.mkdir(exist_ok=True)
    target = folder / f"{name}_{os.getpid()}.txt"
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    try:
        return MiniDungeon(target, portal_pairs=pairs)
    finally:
        target.unlink(missing_ok=True)
