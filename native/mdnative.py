"""Cienki wrapper nad `md2native` - ta sama sygnatura co `gp_fitness.evaluate_playthrough`.

Reguly, persony, mapy i portale czyta z `data/rules/` i `data/maps/`, czyli
**z tych samych plikow co Python**. Port nie ma wlasnej kopii regul - gdyby
mial, rozjechalaby sie przy pierwszej zmianie w JSON-ie i test roznicowy
przestalby cokolwiek znaczyc.

Poziom (`Level`) budujemy raz na mape: tablica LOS i dystanse do wyjscia sa
funkcja samego terenu, wiec liczenie ich przy kazdej partii byloby czysta
strata. W Pythonie ten sam koszt placi kazde `MiniDungeon(map_path)`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import md2native

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "data" / "rules" / "md2_rules.json"
PERSONAS_PATH = PROJECT_ROOT / "data" / "rules" / "personas.json"
PORTALS_PATH = PROJECT_ROOT / "data" / "maps" / "md2" / "benchmark" / "portal_pairs.json"

PE_MODES = {"binary": 0, "normalized": 1, "manhattan": 2, "graded": 3}
UTILITY_PE = {"binary": 0, "normalized": 1, "manhattan": 2}
IC_MODES = {"combined": 0, "mean3": 1}
FALLBACKS = {"utility": 0, "mean": 1, "visits": 2}
POLICIES = {"evolved": 0, "ucb1": 1}
DIRECTIONS = {"N": 0, "E": 1, "S": 2, "W": 3}
LOS_GEOMETRY = {"axis4": 0, "axis8": 1, "raycast": 2}
LOS_DISTANCE = {"chebyshev": 0, "manhattan": 1}

METRIC_IDS = {
    "proximity_to_exit": 0, "steps": 1, "monster_ratio": 2, "treasure_ratio": 3,
    "potion_ratio": 4, "interactive_ratio": 5, "health_left": 6, "turns": 7,
    "javelins": 8, "teleports": 9, "traps": 10, "minitaur_knockouts": 11,
    "reached_exit": 12, "died": 13, "interactive_non_monster_ratio": 14,
}

# ta sama tabela co `gp_fitness.CORE_METRIC`
CORE_METRIC = {
    "runner": "reached_exit",
    "monster_killer": "monster_ratio",
    "treasure_collector": "treasure_ratio",
    "completionist": "interactive_ratio",
}


@lru_cache(maxsize=1)
def _rules_dict() -> dict:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    monsters = data["monsters"]
    return {
        "hero_start_hp": data["hero"]["start_hp"],
        "hero_max_hp": data["hero"]["max_hp"],
        "hero_collision_damage": data["hero"]["collision_damage"],
        "starts_with_javelin": bool(data["hero"]["starts_with_javelin"]),
        "javelin_damage": data["javelin"]["damage"],
        "potion_heal": data["objects"]["potion"]["heal"],
        "trap_damage": data["objects"]["trap"]["damage"],
        "goblin_hp": monsters["goblin"]["hp"],
        "goblin_collision": monsters["goblin"]["collision_damage"],
        "wizard_hp": monsters["wizard"]["hp"],
        "wizard_collision": monsters["wizard"]["collision_damage"],
        "wizard_ranged_damage": monsters["wizard"]["ranged_damage"],
        "wizard_ranged_range": monsters["wizard"]["ranged_range"],
        "wizard_moves_without_los": bool(monsters["wizard"]["moves_without_los"]),
        "blob_initial_power": monsters["blob"]["initial_power"],
        "blob_max_power": monsters["blob"]["max_power"],
        "ogre_hp": monsters["ogre"]["hp"],
        "ogre_collision": monsters["ogre"]["collision_damage"],
        "minitaur_collision": monsters["minitaur"]["collision_damage"],
        "minitaur_stun_actions": monsters["minitaur"]["stun_actions"],
        "los_geometry": LOS_GEOMETRY[data["line_of_sight"]["geometry"]],
        "los_distance_metric": LOS_DISTANCE[data["line_of_sight"]["distance_metric"]],
        "movement_dirs": [DIRECTIONS[token] for token in data["movement"]["directions"]],
        "neighbor_order": [DIRECTIONS[token] for token in data["pathfinding"]["neighbor_order"]],
    }


@lru_cache(maxsize=1)
def _personas() -> dict:
    return json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))


def persona_spec(persona: str) -> tuple[list[tuple[int, float]], float, int]:
    data = _personas()
    weights = data["personas"][persona]["weights"]
    # kolejnosc z JSON-a ma znaczenie: suma float nie jest przemienna
    pairs = [(METRIC_IDS[name], float(weight)) for name, weight in weights.items()]
    return pairs, float(data["death_penalty"]), METRIC_IDS[CORE_METRIC[persona]]


@lru_cache(maxsize=64)
def level_for(map_path: str, pe_portals: str = "on"):
    path = Path(map_path).resolve()
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [line.rstrip("\r\n") for line in lines if line.strip()]
    portal_pairs: list[list[int]] = []
    if PORTALS_PATH.exists():
        data = json.loads(PORTALS_PATH.read_text(encoding="utf-8"))
        for pair in data.get("maps", {}).get(path.stem, []):
            if len(pair) == 2:
                portal_pairs.append([pair[0][0], pair[0][1], pair[1][0], pair[1][1]])
    rules = dict(_rules_dict(), pe_portals=pe_portals == "on")
    return md2native.make_level(rows, portal_pairs, rules)


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
    pe_portals: str = "on",
    time_limit_s: float | None = None,
    policy: str = "evolved",
) -> dict:
    """Zamiennik `domain.gp_fitness.evaluate_playthrough` - te same argumenty i klucze.

    `policy="ucb1"` wlacza UCB1 z c = sqrt(2) zamiast formuly; `formula` jest wtedy ignorowana.
    """

    weights, death_penalty, core_metric = persona_spec(persona)
    result = md2native.evaluate(
        level_for(map_path, pe_portals), formula, weights, death_penalty, core_metric, int(seed),
        int(max_iterations) if max_iterations else 0,
        float(time_limit_s) if time_limit_s else 0.0,
        PE_MODES[pe_mode], UTILITY_PE[utility_pe], IC_MODES[ic_mode], FALLBACKS[fallback],
        POLICIES[policy],
    )
    result["formula"] = formula
    result["map"] = Path(map_path).stem
    result["seed"] = seed
    return result
