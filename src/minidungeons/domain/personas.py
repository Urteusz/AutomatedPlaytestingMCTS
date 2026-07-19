"""Persona utility functions from the reproduced MCTS paper."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .rules import PROJECT_ROOT

if TYPE_CHECKING:
    from .engine import MiniDungeon


DEFAULT_PERSONAS_PATH = PROJECT_ROOT / "data" / "rules" / "personas.json"

PERSONA_NAMES = (
    "runner",
    "monster_killer",
    "treasure_collector",
    "completionist",
)


# cache, zeby MCTS nie czytal pliku przy kazdej ewaluacji
@lru_cache(maxsize=None)
def _read_personas(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_personas(path: str | Path | None = None) -> dict[str, Any]:
    return _read_personas(str(Path(path or DEFAULT_PERSONAS_PATH).resolve()))


def utility_from_metrics(
    persona: str,
    metrics: Mapping[str, int | float | bool],
    personas_path: str | Path | None = None,
) -> float:
    """Evaluate one paper persona from a complete metric snapshot."""

    data = load_personas(personas_path)
    if persona not in PERSONA_NAMES:
        raise ValueError(f"Unknown persona {persona!r}; expected one of {PERSONA_NAMES}")
    weights = data["personas"][persona]["weights"]
    score = sum(float(metrics[name]) * float(weight) for name, weight in weights.items())
    if bool(metrics.get("died", False)):
        score -= float(data["death_penalty"])
    return score


def utility(persona: str, environment: "MiniDungeon") -> float:
    """Evaluate a live or cloned environment state."""

    return utility_from_metrics(persona, environment.metric_values())
