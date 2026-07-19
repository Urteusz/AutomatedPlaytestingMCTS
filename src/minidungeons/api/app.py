"""REST API adapter for the framework-independent GameService."""

from __future__ import annotations

from typing import Any

from ..application import GameService
from ..errors import GameNotFoundError, InvalidGameActionError, MapNotFoundError

try:
    from fastapi import FastAPI, HTTPException, Response, status
    from pydantic import BaseModel, Field
except ModuleNotFoundError as exc:  # Core simulations do not require HTTP packages.
    FastAPI = None  # type: ignore[assignment,misc]
    _FASTAPI_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _FASTAPI_IMPORT_ERROR = None


if _FASTAPI_IMPORT_ERROR is None:
    class CreateGameRequest(BaseModel):
        map_id: str = Field(default="map01", pattern=r"^map\d{2}$")


    class GameActionRequest(BaseModel):
        kind: str
        direction: str | None = None
        target_id: int | None = None


def create_app(service: GameService | None = None) -> Any:
    """Build the API; dependency injection keeps tests and workers independent."""

    if _FASTAPI_IMPORT_ERROR is not None:
        raise RuntimeError(
            "FastAPI dependencies are not installed. Run: pip install -e .[api]"
        ) from _FASTAPI_IMPORT_ERROR

    game_service = service or GameService()
    api = FastAPI(
        title="MiniDungeons2 MCTS Backend",
        version="0.0.1",
        description="Deterministic MiniDungeons 2 simulations and future MCTS jobs.",
    )
    api.state.game_service = game_service

    @api.get("/health", tags=["system"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "benchmark_id": game_service.maps.benchmark_id,
            "active_sessions": game_service.active_sessions,
        }

    @api.get("/api/v1/maps", tags=["catalog"])
    def list_maps() -> dict[str, Any]:
        return {"items": game_service.list_maps()}

    @api.get("/api/v1/rules", tags=["catalog"])
    def rules() -> dict[str, Any]:
        return game_service.rules_document()

    @api.post("/api/v1/games", status_code=status.HTTP_201_CREATED, tags=["games"])
    def create_game(request: CreateGameRequest) -> dict[str, Any]:
        try:
            return game_service.create_game(request.map_id)
        except MapNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.get("/api/v1/games/{session_id}", tags=["games"])
    def get_game(session_id: str) -> dict[str, Any]:
        try:
            return game_service.get_game(session_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/v1/games/{session_id}/actions", tags=["games"])
    def apply_action(session_id: str, request: GameActionRequest) -> dict[str, Any]:
        try:
            return game_service.apply_action(
                session_id,
                kind=request.kind,
                direction=request.direction,
                target_id=request.target_id,
            )
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidGameActionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/api/v1/games/{session_id}/reset", tags=["games"])
    def reset_game(session_id: str) -> dict[str, Any]:
        try:
            return game_service.reset_game(session_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.delete(
        "/api/v1/games/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["games"],
    )
    def delete_game(session_id: str) -> Response:
        try:
            game_service.delete_game(session_id)
        except GameNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return api


app = create_app() if _FASTAPI_IMPORT_ERROR is None else None
