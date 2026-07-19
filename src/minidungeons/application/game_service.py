"""Application service used by REST, CLI and future MCTS workers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from ..domain import Action, MiniDungeon, PERSONA_NAMES, utility
from ..errors import GameNotFoundError, InvalidGameActionError
from ..infrastructure import MapInfo, MapRepository


@dataclass
class GameSession:
    session_id: str
    map_info: MapInfo
    environment: MiniDungeon


class GameService:
    """Own in-memory game sessions while keeping HTTP out of the domain layer."""

    def __init__(
        self,
        maps: MapRepository | None = None,
        *,
        rules_path: str | Path | None = None,
    ) -> None:
        self.maps = maps or MapRepository()
        self.rules_path = Path(rules_path).resolve() if rules_path else None
        self._sessions: dict[str, GameSession] = {}
        # FastAPI obsluguje requesty w watkach, stad blokada na slowniku sesji
        self._lock = RLock()

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._sessions)

    def list_maps(self) -> list[dict[str, Any]]:
        return [map_info.as_dict() for map_info in self.maps.list()]

    def create_environment(self, map_id: str) -> MiniDungeon:
        """Create an unmanaged environment for MCTS, batch jobs or tests."""

        map_info = self.maps.get(map_id)
        return MiniDungeon(map_info.path, rules_path=self.rules_path)

    def create_game(self, map_id: str = "map01") -> dict[str, Any]:
        map_info = self.maps.get(map_id)
        session_id = uuid4().hex
        session = GameSession(session_id, map_info, self.create_environment(map_id))
        with self._lock:
            self._sessions[session_id] = session
            return self._snapshot(session)

    def get_game(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self._snapshot(self._get_session(session_id))

    def apply_action(
        self,
        session_id: str,
        *,
        kind: str,
        direction: str | None = None,
        target_id: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self._get_session(session_id)
            action = self._parse_action(kind, direction, target_id)
            try:
                _, info = session.environment.step(action)
            except ValueError as exc:
                legal = [item["label"] for item in self._legal_actions(session.environment)]
                raise InvalidGameActionError(f"{exc}; legal actions: {legal}") from exc
            response = self._snapshot(session)
            response["last_transition"] = self._json_value(info)
            return response

    def reset_game(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._get_session(session_id)
            session.environment.reset()
            return self._snapshot(session)

    def delete_game(self, session_id: str) -> None:
        with self._lock:
            if self._sessions.pop(session_id, None) is None:
                raise GameNotFoundError(f"Unknown game session {session_id!r}")

    def rules_document(self) -> dict[str, Any]:
        environment = self.create_environment(self.maps.list()[0].map_id)
        return self._json_value(environment.rules.data)

    def _get_session(self, session_id: str) -> GameSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise GameNotFoundError(f"Unknown game session {session_id!r}") from exc

    @staticmethod
    def _parse_action(kind: str, direction: str | None, target_id: int | None) -> Action:
        normalized_kind = kind.strip().lower()
        try:
            if normalized_kind == "move" and direction is not None:
                return Action.move(direction)
            if normalized_kind == "throw" and target_id is not None:
                return Action.throw(target_id)
        except (TypeError, ValueError) as exc:
            raise InvalidGameActionError(str(exc)) from exc
        raise InvalidGameActionError(
            "Use kind='move' with direction N/E/S/W or kind='throw' with target_id"
        )

    def _snapshot(self, session: GameSession) -> dict[str, Any]:
        environment = session.environment
        state = environment.state()
        objects = [
            {"position": list(position), "kind": kind}
            for position, kind in state.pop("objects")
        ]
        state["hero_position"] = list(state["hero_position"])
        for npc in state["npcs"]:
            npc["position"] = list(npc["position"])
        if state["javelin_position"] is not None:
            state["javelin_position"] = list(state["javelin_position"])
        state["objects"] = objects
        return {
            "session_id": session.session_id,
            "map": session.map_info.as_dict(),
            "state": self._json_value(state),
            "legal_actions": self._legal_actions(environment),
            "persona_utilities": {
                persona: utility(persona, environment) for persona in PERSONA_NAMES
            },
            "board": environment.render(),
        }

    @staticmethod
    def _legal_actions(environment: MiniDungeon) -> list[dict[str, Any]]:
        return [
            {
                "kind": action.kind,
                "direction": action.direction,
                "target_id": action.target_id,
                "label": str(action),
            }
            for action in environment.legal_actions()
        ]

    @classmethod
    def _json_value(cls, value: Any) -> Any:
        # zamienia krotki na listy, zeby dalo sie zserializowac do JSON
        if isinstance(value, dict):
            return {str(key): cls._json_value(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [cls._json_value(item) for item in value]
        return value
