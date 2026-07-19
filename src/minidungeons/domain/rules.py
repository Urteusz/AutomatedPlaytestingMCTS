"""Loading of the declarative MiniDungeons 2 ruleset."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES_PATH = PROJECT_ROOT / "data" / "rules" / "md2_rules.json"


class RulesError(ValueError):
    """Raised when the rules JSON is missing or unreadable."""


@dataclass(frozen=True)
class GameRules:
    """Read-only access to the JSON ruleset."""

    data: dict[str, Any]
    source_path: Path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "GameRules":
        source_path = Path(path) if path is not None else DEFAULT_RULES_PATH
        source_path = source_path.resolve()
        try:
            with source_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            raise RulesError(f"Cannot read rules file {source_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RulesError(f"Invalid JSON in {source_path}: {exc}") from exc

        return cls(data=data, source_path=source_path)

    def value(self, *keys: str) -> Any:
        current: Any = self.data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                joined = ".".join(keys)
                raise RulesError(f"Missing rules value: {joined}")
            current = current[key]
        return current


def load_rules(path: str | Path | None = None) -> GameRules:
    """Load the default ruleset or a caller-supplied compatible JSON file."""

    return GameRules.load(path)
