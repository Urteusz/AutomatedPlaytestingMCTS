"""Deterministic MiniDungeons 2 environment reconstructed from the papers.

The text map is an initial-state format. At runtime terrain, floor objects,
NPCs, the Hero and the javelin are separate layers so the state can be cloned
safely by MCTS.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
from heapq import heappop, heappush
import json
from pathlib import Path
from typing import Iterable, Iterator

from minidungeons.domain.rules import GameRules, PROJECT_ROOT, load_rules

Coord = tuple[int, int]
WALL, EMPTY, ENTRANCE, EXIT = "#", ".", "E", "X"
TREASURE, POTION, PORTAL, TRAP = "r", "p", "P", "^"
GOBLIN, WIZARD, BLOB, OGRE, MINITAUR = "g", "w", "b", "o", "M"

OBJECT_BY_SYMBOL = {
    EXIT: "exit", TREASURE: "treasure", POTION: "potion",
    PORTAL: "portal", TRAP: "trap",
}
SYMBOL_BY_OBJECT = {value: key for key, value in OBJECT_BY_SYMBOL.items()}
NPC_KIND_BY_SYMBOL = {
    GOBLIN: "goblin", WIZARD: "wizard", BLOB: "blob",
    OGRE: "ogre", MINITAUR: "minitaur",
}
SYMBOL_BY_NPC_KIND = {value: key for key, value in NPC_KIND_BY_SYMBOL.items()}
ALLOWED_MAP_SYMBOLS = {WALL, EMPTY, ENTRANCE, *OBJECT_BY_SYMBOL, *NPC_KIND_BY_SYMBOL}

DIRECTION_DELTA = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}

LOS_GEOMETRIES = frozenset({"axis4", "axis8", "raycast"})
LOS_CORNER_RULES = frozenset({"transparent", "permissive", "strict"})
LOS_DISTANCE_METRICS = frozenset({"chebyshev", "manhattan"})


@dataclass(frozen=True, order=True)
class Action:
    """Hero's action class, depending on the type, direction and target id."""

    kind: str
    direction: str | None = None
    target_id: int | None = None

    @classmethod
    def move(cls, direction: str) -> "Action":
        token = direction.upper()
        if token not in DIRECTION_DELTA:
            raise ValueError(f"Unknown direction: {direction!r}")
        return cls(kind="move", direction=token)

    @classmethod
    def throw(cls, target_id: int) -> "Action":
        return cls(kind="throw", target_id=int(target_id))

    def __str__(self) -> str:
        return f"move:{self.direction}" if self.kind == "move" else f"throw:{self.target_id}"


@dataclass
class NPC:
    npc_id: int
    kind: str
    position: Coord
    initial_order: int
    hp: int | None
    power: int = 1
    stunned_actions: int = 0
    fancy: bool = False


@dataclass
class Metrics:
    """Table I gameplay metrics plus terminal flags."""

    steps_taken: int = 0
    potions_drunk: int = 0
    treasures_opened: int = 0
    minitaur_knockouts: int = 0
    monsters_slain: int = 0
    javelins_thrown: int = 0
    teleports_used: int = 0
    traps_sprung: int = 0
    turns_taken: int = 0
    reached_exit: bool = False
    died: bool = False

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "steps": self.steps_taken, "potions": self.potions_drunk,
            "treasures": self.treasures_opened,
            "minitaur_knockouts": self.minitaur_knockouts,
            "monsters": self.monsters_slain, "javelins": self.javelins_thrown,
            "teleports": self.teleports_used, "traps": self.traps_sprung,
            "turns": self.turns_taken, "reached_exit": self.reached_exit,
            "died": self.died,
        }


class MiniDungeon:
    """Cloneable state of one deterministic MiniDungeons 2 playthrough."""

    PLAYER_MAX_HP = 10
    DEFAULT_PORTAL_PAIRS_PATH = PROJECT_ROOT / "data" / "maps" / "md2" / "benchmark" / "portal_pairs.json"

    def __init__(
            self,
            map_path: str | Path,
            *,
            rules_path: str | Path | None = None,
            portal_pairs_path: str | Path | None = None,
            portal_pairs: Iterable[tuple[Coord, Coord]] | None = None,
    ) -> None:
        self.map_path = Path(map_path).resolve()
        self.rules: GameRules = load_rules(rules_path)
        self.PLAYER_MAX_HP = int(self.rules.value("hero", "max_hp"))
        self._load_line_of_sight_rules()
        self.wizard_moves_without_los = bool(
            self.rules.value("monsters", "wizard", "moves_without_los")
        )
        self._load_blueprint()
        self.portal_links = self._load_portal_links(portal_pairs_path, portal_pairs)
        self.reset()

    def _load_blueprint(self) -> None:
        try:
            with self.map_path.open(encoding="utf-8") as handle:
                rows = [line.rstrip("\r\n") for line in handle if line.strip()]
        except OSError as exc:
            raise ValueError(f"Cannot read map {self.map_path}: {exc}") from exc
        if not rows:
            raise ValueError("Map is empty")
        widths = {len(row) for row in rows}
        if len(widths) != 1:
            raise ValueError(f"Map is not rectangular; widths: {sorted(widths)}")
        unknown = sorted(set("".join(rows)) - ALLOWED_MAP_SYMBOLS)
        if unknown:
            raise ValueError(f"Map contains unknown symbols: {unknown}")

        self.height, self.width = len(rows), len(rows[0])
        terrain = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        objects: dict[Coord, str] = {}
        npc_specs: list[tuple[str, Coord, int]] = []
        entrances: list[Coord] = []
        exits: list[Coord] = []
        order = 0
        for row, line in enumerate(rows):
            for column, symbol in enumerate(line):
                position = (row, column)
                if symbol == WALL:
                    terrain[row][column] = WALL
                elif symbol == ENTRANCE:
                    entrances.append(position)
                elif symbol in OBJECT_BY_SYMBOL:
                    object_kind = OBJECT_BY_SYMBOL[symbol]
                    objects[position] = object_kind
                    if object_kind == "exit":
                        exits.append(position)
                elif symbol in NPC_KIND_BY_SYMBOL:
                    npc_specs.append((NPC_KIND_BY_SYMBOL[symbol], position, order))
                    order += 1
        if len(entrances) != 1 or len(exits) != 1:
            raise ValueError(f"Map needs one E and X; got E={len(entrances)}, X={len(exits)}")

        self.terrain = tuple(tuple(row) for row in terrain)
        self._object_template = objects
        self._npc_specs = tuple(npc_specs)
        self.entrance, self.exit = entrances[0], exits[0]
        self._initial_potions = sum(value == "potion" for value in objects.values())
        self._initial_treasures = sum(value == "treasure" for value in objects.values())
        self._initial_killable_monsters = sum(kind != "minitaur" for kind, _, _ in npc_specs)
        self._initial_completion_objects = self._initial_potions + self._initial_treasures + self._initial_killable_monsters

    def _load_portal_links(
            self,
            portal_pairs_path: str | Path | None,
            explicit_pairs: Iterable[tuple[Coord, Coord]] | None,
    ) -> dict[Coord, Coord]:
        map_portals = {position for position, kind in self._object_template.items() if kind == "portal"}
        pairs: list[tuple[Coord, Coord]] = []
        if explicit_pairs is not None:
            pairs = [(tuple(first), tuple(second)) for first, second in explicit_pairs]
        else:
            metadata_path = Path(portal_pairs_path).resolve() if portal_pairs_path else self.DEFAULT_PORTAL_PAIRS_PATH
            if metadata_path.exists():
                try:
                    with metadata_path.open(encoding="utf-8") as handle:
                        data = json.load(handle)
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(f"Cannot read portal metadata: {exc}") from exc
                raw_pairs = data.get("maps", {}).get(self.map_path.stem, [])
                pairs = [(tuple(pair[0]), tuple(pair[1])) for pair in raw_pairs if len(pair) == 2]
        paired_positions = {position for pair in pairs for position in pair}
        if paired_positions != map_portals and (paired_positions or map_portals):
            raise ValueError(f"Portal metadata {sorted(paired_positions)} != map {sorted(map_portals)}")
        links: dict[Coord, Coord] = {}
        for first, second in pairs:
            if first == second or first in links or second in links:
                raise ValueError("Every portal endpoint must occur in exactly one pair")
            # portal dziala w obie strony
            links[first], links[second] = second, first
        return links

    def reset(self) -> dict[str, object]:
        self.objects = dict(self._object_template)
        self.npcs: dict[int, NPC] = {}
        for npc_id, (kind, position, initial_order) in enumerate(self._npc_specs):
            definition = self.rules.value("monsters", kind)
            power = int(definition["initial_power"]) if kind == "blob" else 1
            hp = power if kind == "blob" else definition["hp"]
            self.npcs[npc_id] = NPC(npc_id, kind, position, initial_order, hp, power)
        self.hero_position = self.entrance
        self.hero_hp = int(self.rules.value("hero", "start_hp"))
        self.javelin_held = bool(self.rules.value("hero", "starts_with_javelin"))
        self.javelin_position: Coord | None = None
        self.metrics = Metrics()
        self.done = False
        self.outcome: str | None = None
        self.last_events: list[dict[str, object]] = []
        return self.state()

    def clone(self) -> "MiniDungeon":
        # Ręczna kopia zamiast deepcopy, aby ograniczyć czas potrzebny do przetworzenia kopia,
        # Teren, reguły, portale i dystanse są niemutowalne, wiec klony je współdzielą,
        # Kopiujemy tylko stan rozgrywki.
        other = object.__new__(MiniDungeon)
        other.__dict__.update(self.__dict__)
        other.objects = dict(self.objects)
        other.npcs = {npc_id: replace(npc) for npc_id, npc in self.npcs.items()}
        other.metrics = replace(self.metrics)
        other.last_events = list(self.last_events)
        return other

    def state(self) -> dict[str, object]:
        npc_state = [
            {
                "id": npc.npc_id, "kind": npc.kind, "position": npc.position,
                "hp": npc.hp, "power": npc.power,
                "stunned_actions": npc.stunned_actions,
                "initial_order": npc.initial_order,
            }
            for npc in sorted(self.npcs.values(), key=lambda value: value.initial_order)
        ]
        return {
            "hp": self.hero_hp,
            "hero_position": self.hero_position,
            "javelin_held": self.javelin_held,
            "javelin_position": self.javelin_position,
            "npcs": npc_state, "objects": tuple(sorted(self.objects.items())),
            "done": self.done, "outcome": self.outcome,
            "metrics": self.metric_values(),
        }

    def state_key(self) -> tuple[object, ...]:
        # caly stan w jednej krotce - do porownywania stanow miedzy klonami
        npc_key = tuple(
            (npc.npc_id, npc.kind, npc.position, npc.hp, npc.power, npc.stunned_actions, npc.fancy)
            for npc in sorted(self.npcs.values(), key=lambda value: value.npc_id)
        )
        return (
            self.hero_position, self.hero_hp, self.javelin_held,
            self.javelin_position, tuple(sorted(self.objects.items())), npc_key,
            tuple(asdict(self.metrics).values()), self.done, self.outcome,
        )

    def metric_values(self) -> dict[str, int | float | bool]:
        values: dict[str, int | float | bool] = self.metrics.as_dict()
        values.update({
            "health_left": self.hero_hp,
            "proximity_to_exit": self.proximity_to_exit(),
            "potion_ratio": self._ratio(self.metrics.potions_drunk, self._initial_potions),
            "treasure_ratio": self._ratio(self.metrics.treasures_opened, self._initial_treasures),
            "monster_ratio": self._ratio(self.metrics.monsters_slain, self._initial_killable_monsters),
            "interactive_ratio": self._ratio(
                self.metrics.potions_drunk + self.metrics.treasures_opened + self.metrics.monsters_slain,
                self._initial_completion_objects,
            ),
            "interactive_non_monster_ratio": self._ratio(
                self.metrics.potions_drunk + self.metrics.treasures_opened,
                self._initial_potions + self._initial_treasures,
            ),
        })
        return values

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    def proximity_to_exit(self) -> float:
        """PE = 0 na kaflu wyjscia, -1 wszedzie indziej."""

        return 0.0 if self.hero_position == self.exit else -1.0

    def legal_actions(self) -> tuple[Action, ...]:
        if self.done:
            return ()
        actions: list[Action] = []
        for token in self.rules.value("movement", "directions"):
            if self._is_passable(self._offset(self.hero_position, token)):
                actions.append(Action.move(token))
        if self.javelin_held:
            for npc in sorted(self.npcs.values(), key=lambda value: value.npc_id):
                if self.has_line_of_sight(self.hero_position, npc.position):
                    actions.append(Action.throw(npc.npc_id))
        return tuple(actions)

    def step(self, action: Action | str) -> tuple[dict[str, object], dict[str, object]]:
        """Apply one Hero action followed by all deterministic NPC responses."""

        if self.done:
            return self.state(), {"event": "already_done", "events": []}
        normalized = self._normalize_action(action)
        if normalized not in self.legal_actions():
            raise ValueError(f"Illegal action in current state: {normalized}")
        self.metrics.turns_taken += 1
        if normalized.kind == "move":
            self.metrics.steps_taken += 1
            events = self._move_hero(normalized.direction or "")
        else:
            events = self._throw_javelin(normalized.target_id)
        hero_event = events[0]["type"] if events else normalized.kind
        if not self.done:
            events.extend(self._run_npc_turn())
        self.last_events = events
        return self.state(), {"event": hero_event, "action": str(normalized), "events": events}

    @staticmethod
    def _normalize_action(action: Action | str) -> Action:
        return action if isinstance(action, Action) else Action.move(action)

    def _move_hero(self, direction: str) -> list[dict[str, object]]:
        target = self._offset(self.hero_position, direction)
        origin = self.hero_position
        occupant = self._npc_at(target)
        events: list[dict[str, object]] = []
        if occupant is None:
            self.hero_position = target
            events.append({"type": "move", "actor": "hero", "from": origin, "to": target})
        elif occupant.kind == "minitaur" and occupant.stunned_actions > 0:
            self.hero_position = target
            events.append({
                "type": "pass_stunned_minitaur", "actor": "hero",
                "target_id": occupant.npc_id, "from": origin, "to": target,
            })
        else:
            events.extend(self._resolve_hero_npc_collision(occupant))
            occupant_after = self.npcs.get(occupant.npc_id)
            may_enter = occupant_after is None or (
                    occupant_after.kind == "minitaur" and occupant_after.stunned_actions > 0
            )
            if not self.done and may_enter:
                self.hero_position = target
        if self.hero_position != origin and not self.done:
            self._pickup_javelin(events)
            events.extend(self._apply_hero_object())
        return events

    def _throw_javelin(self, target_id: int | None) -> list[dict[str, object]]:
        if target_id is None or target_id not in self.npcs:
            raise ValueError("Javelin action requires a living target")
        target = self.npcs[target_id]
        self.javelin_held = False
        self.javelin_position = target.position
        self.metrics.javelins_thrown += 1
        events = [{
            "type": "javelin_throw", "actor": "hero",
            "target_id": target_id, "to": target.position,
        }]
        events.extend(self._damage_npc(
            target_id, int(self.rules.value("javelin", "damage")),
            source="javelin", hero_credit=True,
        ))
        return events

    def _resolve_hero_npc_collision(self, npc: NPC) -> list[dict[str, object]]:
        hero_damage = self._npc_collision_damage(npc)
        events: list[dict[str, object]] = [{
            "type": "collision", "mover": "hero",
            "target_id": npc.npc_id, "target_kind": npc.kind,
        }]
        events.extend(self._damage_npc(
            npc.npc_id, int(self.rules.value("hero", "collision_damage")),
            source="hero_collision", hero_credit=True,
        ))
        events.extend(self._damage_hero(
            hero_damage, source=f"collision:{npc.kind}",
        ))
        return events

    def _damage_hero(self, amount: int, *, source: str) -> list[dict[str, object]]:
        if amount <= 0 or self.done:
            return []
        self.hero_hp -= amount
        events: list[dict[str, object]] = [{
            "type": "hero_damaged", "amount": amount,
            "source": source, "hp": self.hero_hp,
        }]
        if self.hero_hp <= 0:
            self.hero_hp = 0
            self.metrics.died = True
            self.done = True
            self.outcome = "death"
            events.append({"type": "death", "actor": "hero", "source": source})
        return events

    def _damage_npc(
            self,
            npc_id: int,
            amount: int,
            *,
            source: str,
            hero_credit: bool,
    ) -> list[dict[str, object]]:
        npc = self.npcs.get(npc_id)
        if npc is None or amount <= 0:
            return []
        events: list[dict[str, object]] = []
        # minitaur nie ginie, tylko jest ogluszany
        if npc.kind == "minitaur":
            was_active = npc.stunned_actions == 0
            npc.stunned_actions = int(self.rules.value("monsters", "minitaur", "stun_actions"))
            if was_active:
                self.metrics.minitaur_knockouts += 1
            return [{
                "type": "minitaur_knockout", "target_id": npc_id,
                "stunned_actions": npc.stunned_actions, "source": source,
            }]
        # blob zamiast HP traci poziom mocy
        if npc.kind == "blob":
            if npc.power <= 1:
                npc.hp = 0
            else:
                npc.power -= 1
                npc.hp = npc.power
                events.append({
                    "type": "blob_power_lost", "target_id": npc_id,
                    "power": npc.power, "source": source,
                })
        else:
            assert npc.hp is not None
            npc.hp -= amount
        if npc.hp is not None and npc.hp <= 0:
            kind = npc.kind
            del self.npcs[npc_id]
            if hero_credit:
                self.metrics.monsters_slain += 1
            events.append({
                "type": "monster_slain", "target_id": npc_id,
                "target_kind": kind, "source": source,
                "hero_credit": hero_credit,
            })
        else:
            events.append({
                "type": "npc_damaged", "target_id": npc_id,
                "amount": amount, "source": source, "hp": npc.hp,
            })
        return events

    def _apply_hero_object(self) -> list[dict[str, object]]:
        object_kind = self.objects.get(self.hero_position)
        events: list[dict[str, object]] = []
        if object_kind == "potion":
            old_hp = self.hero_hp
            self.hero_hp = min(
                self.PLAYER_MAX_HP,
                self.hero_hp + int(self.rules.value("objects", "potion", "heal")),
            )
            del self.objects[self.hero_position]
            self.metrics.potions_drunk += 1
            events.append({"type": "potion", "healed": self.hero_hp - old_hp, "hp": self.hero_hp})
        elif object_kind == "treasure":
            del self.objects[self.hero_position]
            self.metrics.treasures_opened += 1
            events.append({"type": "treasure"})
        elif object_kind == "trap":
            self.metrics.traps_sprung += 1
            events.append({"type": "trap", "actor": "hero"})
            events.extend(self._damage_hero(
                int(self.rules.value("objects", "trap", "damage")), source="trap",
            ))
        elif object_kind == "portal":
            events.extend(self._teleport_hero())
        elif object_kind == "exit":
            self.metrics.reached_exit = True
            self.done = True
            self.outcome = "exit"
            events.append({"type": "exit", "actor": "hero"})
        return events

    def _pickup_javelin(self, events: list[dict[str, object]]) -> None:
        if not self.javelin_held and self.javelin_position == self.hero_position:
            self.javelin_held = True
            self.javelin_position = None
            events.append({"type": "javelin_pickup", "actor": "hero"})

    def _teleport_hero(self) -> list[dict[str, object]]:
        destination = self.portal_links.get(self.hero_position)
        if destination is None:
            raise RuntimeError(f"Unpaired portal at {self.hero_position}")
        if self._npc_at(destination) is not None:
            return [{
                "type": "portal_blocked", "actor": "hero",
                "from": self.hero_position, "to": destination,
            }]
        origin = self.hero_position
        self.hero_position = destination
        self.metrics.teleports_used += 1
        events: list[dict[str, object]] = [{
            "type": "teleport", "actor": "hero", "from": origin, "to": destination,
        }]
        self._pickup_javelin(events)
        return events

    def _run_npc_turn(self) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        turn_ids = [
            npc.npc_id for npc in sorted(self.npcs.values(), key=lambda value: value.initial_order)
        ]
        for npc_id in turn_ids:
            if self.done:
                break
            npc = self.npcs.get(npc_id)
            if npc is None:
                continue
            if npc.stunned_actions > 0:
                npc.stunned_actions -= 1
                events.append({
                    "type": "stunned_skip", "actor_id": npc_id,
                    "remaining": npc.stunned_actions,
                })
                continue
            events.extend(self._act_npc(npc_id))
        return events

    def _act_npc(self, npc_id: int) -> list[dict[str, object]]:
        npc = self.npcs[npc_id]
        if npc.kind == "goblin":
            return self._act_goblin(npc)
        if npc.kind == "wizard":
            return self._act_wizard(npc)
        if npc.kind == "blob":
            return self._act_target_seeker(npc, preferred_object="potion")
        if npc.kind == "ogre":
            return self._act_target_seeker(npc, preferred_object="treasure")
        if npc.kind == "minitaur":
            return self._act_minitaur(npc)
        raise RuntimeError(f"Unsupported NPC kind: {npc.kind}")

    def _act_goblin(self, npc: NPC) -> list[dict[str, object]]:
        if not self.has_line_of_sight(npc.position, self.hero_position):
            return [{"type": "npc_stay", "actor_id": npc.npc_id, "reason": "no_los"}]
        next_position = self._next_step_bfs(npc.position, self.hero_position, npc.npc_id)
        return self._move_npc_or_stay(npc, next_position, reason="no_path")

    def _act_wizard(self, npc: NPC) -> list[dict[str, object]]:
        # MCTS §IV: czar w LOS do 5 kafli, podejscie w LOS powyzej 5 kafli, bez
        # LOS zadna klauzula nie pozwala dzialac. Opis MD2 mowi przy tej samej
        # regule "otherwise" bez warunku LOS - patrz `wizard_without_los`.
        if self.has_line_of_sight(npc.position, self.hero_position):
            distance = self.sight_distance(npc.position, self.hero_position)
            attack_range = int(self.rules.value("monsters", "wizard", "ranged_range"))
            if distance <= attack_range:
                damage = int(self.rules.value("monsters", "wizard", "ranged_damage"))
                events = [{"type": "wizard_spell", "actor_id": npc.npc_id, "damage": damage}]
                events.extend(self._damage_hero(damage, source="wizard_spell"))
                return events
        elif not self.wizard_moves_without_los:
            return [{"type": "npc_stay", "actor_id": npc.npc_id, "reason": "no_los"}]
        next_position = self._next_step_bfs(npc.position, self.hero_position, npc.npc_id)
        return self._move_npc_or_stay(npc, next_position, reason="no_path")

    def _act_target_seeker(self, npc: NPC, *, preferred_object: str) -> list[dict[str, object]]:
        candidates: list[tuple[int, int, int, int, Coord]] = []
        if self.has_line_of_sight(npc.position, self.hero_position):
            distance = self.sight_distance(npc.position, self.hero_position)
            candidates.append((distance, 1, self.hero_position[0], self.hero_position[1], self.hero_position))
        for position, object_kind in self.objects.items():
            if object_kind == preferred_object and self.has_line_of_sight(npc.position, position):
                distance = self.sight_distance(npc.position, position)
                candidates.append((distance, 0, position[0], position[1], position))
        if not candidates:
            return [{"type": "npc_stay", "actor_id": npc.npc_id, "reason": "no_target"}]
        target = min(candidates)[-1]
        next_position = self._next_step_bfs(npc.position, target, npc.npc_id)
        return self._move_npc_or_stay(npc, next_position, reason="no_path")

    def _act_minitaur(self, npc: NPC) -> list[dict[str, object]]:
        if npc.position == self.hero_position:
            return self._resolve_npc_hero_collision(npc)
        next_position = self._next_step_astar(npc.position, self.hero_position)
        return self._move_npc_or_stay(npc, next_position, reason="no_path")

    def _move_npc_or_stay(
            self, npc: NPC, next_position: Coord | None, *, reason: str,
    ) -> list[dict[str, object]]:
        if next_position is None or next_position == npc.position:
            return [{"type": "npc_stay", "actor_id": npc.npc_id, "reason": reason}]
        return self._move_npc(npc.npc_id, next_position)

    def _move_npc(self, npc_id: int, destination: Coord) -> list[dict[str, object]]:
        npc = self.npcs.get(npc_id)
        if npc is None:
            return []
        if destination == self.hero_position:
            return self._resolve_npc_hero_collision(npc)
        occupant = self._npc_at(destination, exclude_id=npc_id)
        if occupant is not None:
            if npc.kind == occupant.kind == "blob":
                return self._merge_blobs(npc, occupant)
            return self._resolve_npc_npc_collision(npc, occupant)
        origin = npc.position
        npc.position = destination
        events = [{
            "type": "npc_move", "actor_id": npc_id, "actor_kind": npc.kind,
            "from": origin, "to": destination,
        }]
        events.extend(self._apply_npc_object(npc_id))
        return events

    def _resolve_npc_hero_collision(self, npc: NPC) -> list[dict[str, object]]:
        hero_damage = self._npc_collision_damage(npc)
        events: list[dict[str, object]] = [{
            "type": "collision", "mover": npc.npc_id,
            "target": "hero", "target_kind": "hero",
        }]
        events.extend(self._damage_npc(
            npc.npc_id, int(self.rules.value("hero", "collision_damage")),
            source="hero_collision", hero_credit=True,
        ))
        events.extend(self._damage_hero(
            hero_damage, source=f"collision:{npc.kind}",
        ))
        return events

    def _resolve_npc_npc_collision(self, mover: NPC, occupant: NPC) -> list[dict[str, object]]:
        destination = occupant.position
        mover_damage = self._npc_collision_damage(mover)
        occupant_damage = self._npc_collision_damage(occupant)
        events: list[dict[str, object]] = [{
            "type": "npc_collision", "mover_id": mover.npc_id,
            "occupant_id": occupant.npc_id,
        }]
        events.extend(self._damage_npc(
            occupant.npc_id, mover_damage,
            source=f"collision:{mover.kind}", hero_credit=False,
        ))
        events.extend(self._damage_npc(
            mover.npc_id, occupant_damage,
            source=f"collision:{occupant.kind}", hero_credit=False,
        ))
        mover_after = self.npcs.get(mover.npc_id)
        if mover_after is not None and occupant.npc_id not in self.npcs:
            mover_after.position = destination
            events.extend(self._apply_npc_object(mover_after.npc_id))
        return events

    def _merge_blobs(self, first: NPC, second: NPC) -> list[dict[str, object]]:
        destination = second.position
        # zostaje blob, ktory byl wczesniej na mapie
        survivor, removed = (first, second) if first.initial_order <= second.initial_order else (second, first)
        max_power = int(self.rules.value("monsters", "blob", "max_power"))
        survivor.power = min(max_power, first.power + second.power)
        survivor.hp = survivor.power
        survivor.position = destination
        self.npcs.pop(removed.npc_id, None)
        return [{
            "type": "blob_merge", "survivor_id": survivor.npc_id,
            "removed_id": removed.npc_id, "power": survivor.power,
            "position": destination,
        }]

    def _apply_npc_object(self, npc_id: int) -> list[dict[str, object]]:
        npc = self.npcs.get(npc_id)
        if npc is None:
            return []
        object_kind = self.objects.get(npc.position)
        events: list[dict[str, object]] = []
        if object_kind == "potion" and npc.kind == "blob":
            del self.objects[npc.position]
            events.append({"type": "potion_consumed_by_blob", "actor_id": npc_id})
        elif object_kind == "treasure" and npc.kind == "ogre":
            del self.objects[npc.position]
            npc.fancy = True
            events.append({"type": "treasure_consumed_by_ogre", "actor_id": npc_id})
        elif object_kind == "trap":
            events.append({"type": "trap", "actor_id": npc_id, "actor_kind": npc.kind})
            events.extend(self._damage_npc(
                npc_id, int(self.rules.value("objects", "trap", "damage")),
                source="trap", hero_credit=False,
            ))
        elif object_kind == "portal":
            events.extend(self._teleport_npc(npc_id))
        return events

    def _teleport_npc(self, npc_id: int) -> list[dict[str, object]]:
        npc = self.npcs.get(npc_id)
        if npc is None:
            return []
        destination = self.portal_links.get(npc.position)
        if destination is None:
            raise RuntimeError(f"Unpaired portal at {npc.position}")
        if destination == self.hero_position or self._npc_at(destination) is not None:
            return [{
                "type": "portal_blocked", "actor_id": npc_id,
                "from": npc.position, "to": destination,
            }]
        origin = npc.position
        npc.position = destination
        return [{"type": "teleport", "actor_id": npc_id, "from": origin, "to": destination}]

    def _npc_collision_damage(self, npc: NPC) -> int:
        if npc.kind == "blob":
            return npc.power
        return int(self.rules.value("monsters", npc.kind, "collision_damage"))

    def _load_line_of_sight_rules(self) -> None:
        """Geometria LOS nie jest zdefiniowana w publikacjach - patrz
        `line_of_sight_geometry` w docs/rules/decisions.md. Trzymamy ja w
        regulach, zeby dalo sie porownac warianty na benchmarku."""

        self.los_geometry = str(self.rules.value("line_of_sight", "geometry"))
        self.los_corners = str(self.rules.value("line_of_sight", "corners"))
        self.los_distance_metric = str(self.rules.value("line_of_sight", "distance_metric"))
        for value, allowed, name in (
                (self.los_geometry, LOS_GEOMETRIES, "geometry"),
                (self.los_corners, LOS_CORNER_RULES, "corners"),
                (self.los_distance_metric, LOS_DISTANCE_METRICS, "distance_metric"),
        ):
            if value not in allowed:
                raise ValueError(
                    f"Unknown line_of_sight.{name}: {value!r}; expected one of {sorted(allowed)}"
                )

    def has_line_of_sight(
            self, start: Coord, end: Coord, *, max_distance: int | None = None,
    ) -> bool:
        if start == end or not self._is_passable(end):
            return False
        delta_row, delta_column = end[0] - start[0], end[1] - start[1]
        if delta_row and delta_column:
            if self.los_geometry == "axis4":
                return False
            if self.los_geometry == "axis8" and abs(delta_row) != abs(delta_column):
                return False
        if max_distance is not None and self.sight_distance(start, end) > max_distance:
            return False
        return self._sight_is_clear(start, end)

    def sight_distance(self, start: Coord, end: Coord) -> int:
        """Dystans w kaflach uzywany przez zasieg czaru i wybor najblizszego celu.

        Przy LOS osiowym oba warianty sprowadzaja sie do dlugosci odcinka, wiec
        metryka ma znaczenie tylko dla skosow (patrz `los_distance_metric`)."""

        if self.los_distance_metric == "manhattan":
            return self._manhattan(start, end)
        return max(abs(start[0] - end[0]), abs(start[1] - end[1]))

    def _sight_is_clear(self, start: Coord, end: Coord) -> bool:
        """Czy sciana przecina promien srodek-srodek miedzy `start` i `end`.

        DDA na liczbach calkowitych: kolejnosc przejsc przez granice kafli
        porownujemy przez t_wiersz = (2k-1)/(2*span_row) i analogicznie dla
        kolumn, po przemnozeniu na krzyz. Rownosc oznacza, ze promien trafia
        dokladnie w naroznik czterech kafli - o przejrzystosci decyduje wtedy
        `los_corners`. Zdarza sie to dla kazdego kierunku, ktorego zredukowana
        postac ma oba skladniki nieparzyste, nie tylko dla 45 stopni."""

        delta_row, delta_column = end[0] - start[0], end[1] - start[1]
        step_row = (delta_row > 0) - (delta_row < 0)
        step_column = (delta_column > 0) - (delta_column < 0)
        span_row, span_column = abs(delta_row), abs(delta_column)
        row, column = start
        crossings_row = crossings_column = 1
        while crossings_row <= span_row or crossings_column <= span_column:
            if crossings_row > span_row:
                column += step_column
                crossings_column += 1
            elif crossings_column > span_column:
                row += step_row
                crossings_row += 1
            else:
                row_boundary = (2 * crossings_row - 1) * span_column
                column_boundary = (2 * crossings_column - 1) * span_row
                if row_boundary < column_boundary:
                    row += step_row
                    crossings_row += 1
                elif column_boundary < row_boundary:
                    column += step_column
                    crossings_column += 1
                else:
                    sides = ((row + step_row, column), (row, column + step_column))
                    if not self._corner_is_open(sides):
                        return False
                    row += step_row
                    column += step_column
                    crossings_row += 1
                    crossings_column += 1
            if (row, column) != end and not self._is_passable((row, column)):
                return False
        return True

    def _corner_is_open(self, sides: tuple[Coord, Coord]) -> bool:
        if self.los_corners == "transparent":
            return True
        open_sides = [self._is_passable(cell) for cell in sides]
        return all(open_sides) if self.los_corners == "strict" else any(open_sides)

    def _next_step_bfs(self, start: Coord, goal: Coord, actor_id: int) -> Coord | None:
        actor_kind = self.npcs[actor_id].kind
        # wg papieru gobliny omijaja tylko gobliny i czarodziejow; w bloba,
        # ogra i minitaura moga wejsc (kolizja). blob i ogr nie omijaja nikogo
        blocked = set()
        if actor_kind in {"goblin", "wizard"}:
            blocked = {
                npc.position for npc in self.npcs.values()
                if npc.npc_id != actor_id
                   and npc.kind in {"goblin", "wizard"}
                   and npc.position != goal
            }
        if self.hero_position != goal:
            blocked.add(self.hero_position)
        queue = deque([start])
        parents: dict[Coord, Coord | None] = {start: None}
        while queue:
            current = queue.popleft()
            if current == goal:
                break
            for neighbor in self._neighbors(current):
                if neighbor in parents or neighbor in blocked or not self._is_passable(neighbor):
                    continue
                parents[neighbor] = current
                queue.append(neighbor)
        if goal not in parents:
            return None
        return self._first_step(parents, start, goal)

    def _next_step_astar(self, start: Coord, goal: Coord) -> Coord | None:
        frontier: list[tuple[int, int, Coord]] = []
        sequence = 0
        heappush(frontier, (self._manhattan(start, goal), sequence, start))
        parents: dict[Coord, Coord | None] = {start: None}
        costs = {start: 0}
        while frontier:
            _, _, current = heappop(frontier)
            if current == goal:
                break
            for neighbor in self._neighbors(current):
                if not self._is_passable(neighbor):
                    continue
                new_cost = costs[current] + 1
                if neighbor in costs and new_cost >= costs[neighbor]:
                    continue
                costs[neighbor] = new_cost
                parents[neighbor] = current
                sequence += 1
                heappush(frontier, (new_cost + self._manhattan(neighbor, goal), sequence, neighbor))
        if goal not in parents:
            return None
        return self._first_step(parents, start, goal)

    @staticmethod
    def _first_step(parents: dict[Coord, Coord | None], start: Coord, goal: Coord) -> Coord:
        # cofnij sie po rodzicach do pola tuz za startem
        current = goal
        while parents[current] is not None and parents[current] != start:
            current = parents[current]  # type: ignore[assignment]
        return current

    def _neighbors(self, position: Coord) -> Iterator[Coord]:
        for token in self.rules.value("pathfinding", "neighbor_order"):
            yield self._offset(position, token)

    @staticmethod
    def _offset(position: Coord, direction: str) -> Coord:
        dr, dc = DIRECTION_DELTA[direction]
        return position[0] + dr, position[1] + dc

    @staticmethod
    def _manhattan(first: Coord, second: Coord) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

    def _is_inside(self, position: Coord) -> bool:
        return 0 <= position[0] < self.height and 0 <= position[1] < self.width

    def _is_passable(self, position: Coord) -> bool:
        return self._is_inside(position) and self.terrain[position[0]][position[1]] != WALL

    def _npc_at(self, position: Coord, exclude_id: int | None = None) -> NPC | None:
        matches = [
            npc for npc in self.npcs.values()
            if npc.position == position and npc.npc_id != exclude_id
        ]
        return min(matches, key=lambda value: value.initial_order) if matches else None

    def _render_cells(self) -> list[list[str]]:
        """Siatka symboli: terrain pod obiektami, obiekty pod NPC, Hero na wierzchu."""
        cells = [list(row) for row in self.terrain]
        for position, object_kind in self.objects.items():
            cells[position[0]][position[1]] = SYMBOL_BY_OBJECT[object_kind]
        if self.javelin_position is not None:
            row, column = self.javelin_position
            cells[row][column] = "j"
        for npc in self.npcs.values():
            row, column = npc.position
            cells[row][column] = SYMBOL_BY_NPC_KIND[npc.kind]
        cells[self.hero_position[0]][self.hero_position[1]] = "@"
        return cells

    def render(self) -> str:
        cells = self._render_cells()
        column_header = "     " + " ".join(str(column % 10) for column in range(self.width))
        separator = "    +" + "-" * (2 * self.width + 1) + "+"
        rendered_rows = [
            f" {row:>2} | " + " ".join(line) + " |" for row, line in enumerate(cells)
        ]
        header = (
            f"HP: {self.hero_hp}/{self.PLAYER_MAX_HP}  pos:{self.hero_position}  "
            f"javelin:{'held' if self.javelin_held else self.javelin_position}  done:{self.done}"
        )
        return "\n".join([header, column_header, separator, *rendered_rows, separator])
